"""MediaStream: manages the full lifecycle of a single task's media pipeline."""
import asyncio
import threading
import uuid
from typing import Any

import janus  # pyright: ignore[reportMissingImports]

from workflow_worker.domain.entities.task import Task
from workflow_worker.infrastructure.circular_queue import CircularQueue
from workflow_worker.infrastructure.media_stream.data_source import create_data_source
from workflow_worker.infrastructure.media_stream.frame_channel import FrameChannel
from workflow_worker.infrastructure.media_stream.model import StreamMessage
from workflow_worker.applications.workflows.task_context import task_context_store


class MediaStream:
    """Manages a media pipeline for one task with three concurrent async tasks:

    - stream_thread:   reads from the data source, buffers messages in a circular queue.
    - dispatch_thread: dequeues messages and fans them out to registered FrameChannels.
    - stat_thread:     logs throughput stats at regular intervals.
    """

    def __init__(self, task: Task, cache_size: int = 1024, **kwargs):
        self.id = f"MediaStream-{task.id}-{uuid.uuid4().hex[:4]}"
        self.logger = task_context_store.get_task_logger(task.id).getChild(self.id)

        self.is_stopped = False
        self.is_streaming = False
        self.is_dispatching = False

        self.message_channels: dict[str, FrameChannel] = {}
        self.process_steps: dict[str, int] = {}

        self._cache = CircularQueue(cache_size)
        self._cache_lock = asyncio.Lock()
        self._tasks: set[asyncio.Task[Any]] = set()

        self._stat_cache_id = 0
        self._stat_dispatch_id = 0
        self._stat_interval_s = 2

        self.data_source = create_data_source(task, **kwargs)
        self.metadata = self.data_source.extract_metadata()
        self.media_decode_fps = 0

    # ── Public API ──────────────────────────────────────────────────────────

    def add_channel(self, task: Task, name: str, fps: float) -> FrameChannel:
        ch = FrameChannel(task, name, fps)
        self.message_channels[ch.id] = ch
        return ch

    def start(self):
        for coro, name in [
            (self._dispatch_loop(), "dispatch_thread"),
            (self._stat_loop(),     "stat_thread"),
            (self._stream_loop(),   "stream_thread"),
        ]:
            t = asyncio.create_task(coro, name=name)
            self._tasks.add(t)
            t.add_done_callback(self._tasks.discard)
        self.logger.info(f"MediaStream started: {self.id}")

    def force_stop(self):
        self.logger.info("Force-stopping MediaStream...")
        self.is_stopped = True
        for t in self._tasks:
            if not t.done():
                self.logger.info(f"Cancelling task: {t.get_name()}")
                t.cancel()
        self._close_all_channels()

    # ── Stream thread ────────────────────────────────────────────────────────

    async def _stream_loop(self):
        self.logger.info("stream_thread started")
        self.media_decode_fps = self._choose_decode_fps()
        self._recalc_process_steps(self.media_decode_fps)
        try:
            await self.data_source.setup(self.media_decode_fps)
            self.is_streaming = True
            while not self.is_dispatching:
                self.logger.info("Waiting for dispatch_thread to be ready...")
                await asyncio.sleep(1)
            await self.data_source.stream(self._on_message)
        except asyncio.CancelledError:
            self.logger.error("stream_thread cancelled")
        except Exception:
            import traceback
            self.logger.error(f"stream_thread exception, force-stopping:\n{traceback.format_exc()}")
            self.force_stop()
        finally:
            self.is_streaming = False

    async def _on_message(self, msg: StreamMessage) -> bool:
        """Accept a message from the data source into the cache. Returns True to stop."""
        if self.is_stopped:
            return True
        while True:
            async with self._cache_lock:
                if self._cache.enqueue(msg):
                    break
            thread_names = [t.name for t in threading.enumerate()]
            self.logger.warning(
                f"Cache full (msg={msg.id}), retrying in 1s. "
                f"threads={thread_names}, "
                f"read={self._cache.front}, write={self._cache.rear}"
            )
            await asyncio.sleep(1)
        self._stat_cache_id = msg.id
        if not self.message_channels:
            self.logger.info("No channels, telling source to stop.")
            return True
        return bool(msg.is_last)

    # ── Dispatch thread ──────────────────────────────────────────────────────

    async def _dispatch_loop(self):
        self.logger.info("dispatch_thread started")
        try:
            self.is_dispatching = True
            await self._dispatch()
        except asyncio.CancelledError:
            self.logger.error("dispatch_thread cancelled")
        except Exception:
            import traceback
            self.logger.error(f"dispatch_thread exception, force-stopping:\n{traceback.format_exc()}")
            self.force_stop()
        finally:
            self.is_dispatching = False

    async def _dispatch(self):
        while True:
            await asyncio.sleep(0)
            if self.is_stopped:
                self.logger.info("Dispatch stopped.")
                break
            async with self._cache_lock:
                msg: StreamMessage | None = self._cache.dequeue()
            if not msg:
                continue
            self._stat_dispatch_id = msg.id
            await self._broadcast(msg)
            if msg.is_last:
                self.logger.info("Last message dispatched, closing all channels.")
                self._close_all_channels()
                break
            if not self.message_channels:
                self.logger.info("All channels closed, stopping dispatch.")
                break

    async def _broadcast(self, msg: StreamMessage) -> None:
        for ch_id in list(self.message_channels):
            if self._should_skip(msg, ch_id):
                continue
            while True:
                try:
                    stopped = self.message_channels[ch_id].input(msg)
                except janus.AsyncQueueFull:
                    self.logger.warning(
                        f"Channel {ch_id} full for msg-{msg.id}, retrying in 1s. "
                        f"Speed up the algo!"
                    )
                    await asyncio.sleep(1)
                    continue
                if stopped:
                    self.logger.info(f"Channel {ch_id} stopped, removing.")
                    self._remove_channel(ch_id)
                break

    def _should_skip(self, msg: StreamMessage, ch_id: str) -> bool:
        return bool(msg.image) and msg.id % self.process_steps[ch_id] != 0

    # ── Stat thread ──────────────────────────────────────────────────────────

    async def _stat_loop(self):
        while True:
            c1, d1 = self._stat_cache_id, self._stat_dispatch_id
            await asyncio.sleep(self._stat_interval_s)
            c2, d2 = self._stat_cache_id, self._stat_dispatch_id
            dt = self._stat_interval_s
            if self.is_streaming:
                self.logger.info(
                    f"cache fps={(c2 - c1) / dt:.1f}, "
                    f"read={self._cache.front}, write={self._cache.rear}"
                )
            if self.is_dispatching:
                self.logger.info(
                    f"dispatch fps={(d2 - d1) / dt:.1f}, "
                    f"channels={len(self.message_channels)}"
                )

    # ── FPS helpers ──────────────────────────────────────────────────────────

    def _choose_decode_fps(self) -> int:
        channel_fps = [ch.fps for ch in self.message_channels.values() if ch.fps > 0]
        meta_fps = self.metadata.fps

        if not channel_fps and not meta_fps:
            raise RuntimeError(
                "Cannot determine decode fps: no FrameChannel fps set and no fps in media metadata."
            )

        max_channel_fps = max(channel_fps) if channel_fps else 0
        if not max_channel_fps:
            fps = int(float(meta_fps or "0"))
            self.logger.info(f"Using metadata fps={fps} (no channel fps set)")
            return fps

        if not meta_fps:
            self.logger.info(f"No metadata fps, using channel max fps={max_channel_fps}")
            return int(max_channel_fps)

        meta_fps_int = int(float(meta_fps))
        if max_channel_fps > meta_fps_int:
            self.logger.info(
                f"Channel fps {max_channel_fps} > metadata fps {meta_fps_int}, capping to metadata fps."
            )
            return meta_fps_int
        return int(max_channel_fps)

    def _recalc_process_steps(self, decode_fps: int) -> None:
        for ch_id, ch in self.message_channels.items():
            step = int(decode_fps / ch.fps) if ch.fps > 0 else 1
            self.process_steps[ch_id] = step
            self.logger.info(f"{ch_id}: fps={ch.fps}, step={step} at decode_fps={decode_fps}")

    # ── Channel management ───────────────────────────────────────────────────

    def _close_all_channels(self):
        for ch_id in list(self.message_channels):
            self._remove_channel(ch_id)

    def _remove_channel(self, ch_id: str):
        self.message_channels[ch_id].mark_close()
        self.message_channels.pop(ch_id)
