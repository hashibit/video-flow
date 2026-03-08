import uuid
from typing import Generator

import janus  # pyright: ignore[reportMissingImports]

from workflow_worker.domain.entities.task import Task
from workflow_worker.infrastructure.media_stream.model import StreamMessage


class FrameChannel(object):
    def __init__(self, task: Task, name: str, fps: float, channel_size: int = 100):
        self.id = f"FrameChannel-{name}-{uuid.uuid4().hex[0:4]}"
        self.name = name
        self.queue = janus.Queue(channel_size)
        self.fps = fps

        # local import. lazy import.
        from workflow_worker.applications.workflows.task_context import task_context_store
        self.logger = task_context_store.get_task_logger(task.id).getChild(self.id)
        self.logger.info(f"create {self.id} with fps: {self.fps}")

        self.mark_closed = False

    def get_name(self):
        return self.name

    # non-blocking
    # NOTE: If an algorithm consumes too slowly, input() throws janus.AsyncQueueFull exception to upper layer,
    # upper layer is responsible for retry
    def input(self, stream_msg: StreamMessage) -> bool:
        if self.queue.closed:
            self.logger.info("input queue is closed, don't put anything into queue")
            return True
        if self.mark_closed:
            self.logger.error("cannot call input() after mark_close()")
            return True
        try:
            self.queue.async_q.put_nowait(stream_msg)
            # self.logger.debug(f"after put, frame channel async_q.qsize {self.queue.async_q.qsize()}")
        except janus.AsyncQueueFull:
            self.logger.error(f"msg channel is full(when write), qsize {self.queue.async_q.qsize()}, "
                              f"please speed up algo module! ")
            # Propagate exception upwards for upper layer to handle retry
            raise
        except RuntimeError as e:
            if "Operation on the closed queue is forbidden" in str(e):
                self.logger.warn("msg channel queue is closed(when write).")
                return True
            import traceback
            self.logger.error(f"RuntimeError while input to queue, tb: {traceback.format_exc()}")
        except Exception:
            import traceback
            self.logger.error(f"Error while input to queue, tb: {traceback.format_exc()}")
        return False

    # generator-style get
    def output(self) -> Generator[StreamMessage, None, None]:
        try:
            self.logger.info("frame channel output generator started.")
            while True:
                if self.mark_closed:
                    self.logger.info("msg channel is mark closed and drained. stop reading.")
                    break
                try:
                    stream_msg = self.queue.sync_q.get(block=True, timeout=10)
                    self.queue.sync_q.task_done()
                    yield stream_msg
                    # self.logger.debug(f"after get, frame channel sync_q.qsize {self.queue.sync_q.qsize()}")
                except janus.SyncQueueEmpty:
                    self.logger.info("msg channel is empty(when read)...")
                    continue
                except GeneratorExit:
                    self.logger.info("msg channel output generator exited.")
                    return
                except RuntimeError as e:
                    if "Operation on the closed queue is forbidden" in str(e):
                        self.logger.warn("msg channel is closed(when read).")
                        return
                    import traceback
                    self.logger.error(f"RuntimeError while input to queue, tb: {traceback.format_exc()}")
        finally:
            # close generator will enter this.
            self.logger.info("msg channel output gen is closed by consumer, or, "
                             "channel is mark_closed by stream factory."
                             "either way, close this queue.")
            self.queue.close()

    def mark_close(self):
        self.logger.info("mark channel to be closed.")
        self.mark_closed = True
