"""MediaStreamFactory and the module-level singleton used by job runners."""
import traceback

from workflow_worker.domain.entities.task import Task
from workflow_worker.infrastructure.media_stream.frame_channel import FrameChannel
from workflow_worker.infrastructure.media_stream.stream import MediaStream
from workflow_worker.applications.workflows.task_context import task_context_store


class MediaStreamFactory:
    """Manages MediaStream instances keyed by task ID.

    Callers should:
      1. Call build_frame_channel_for_algo() for each algorithm that needs frames.
      2. Call start_media_stream() once all channels are registered.
      3. Call stop_media_stream() when the task is done.
    """

    def __init__(self):
        self._streams: dict[str, MediaStream] = {}

    def build_frame_channel_for_algo(self, task: Task, name: str, fps: float = 0) -> FrameChannel | None:
        """Register an algorithm's frame channel, creating the MediaStream if needed."""
        try:
            key = self._key(task)
            if key not in self._streams:
                self._streams[key] = MediaStream(task)
            return self._streams[key].add_channel(task, name, fps)
        except Exception:
            task_context_store.get_task_logger(task.id).error(
                f"build_frame_channel_for_algo failed:\n{traceback.format_exc()}"
            )
            return None

    def start_media_stream(self, task: Task) -> None:
        """Start streaming for the task. All channels must be registered first."""
        try:
            stream = self._streams.get(self._key(task))
            if stream:
                stream.start()
        except Exception:
            task_context_store.get_task_logger(task.id).error(
                f"start_media_stream failed:\n{traceback.format_exc()}"
            )

    def stop_media_stream(self, task: Task) -> None:
        """Force-stop and remove the MediaStream for the task."""
        try:
            stream = self._streams.pop(self._key(task), None)
            if stream:
                stream.force_stop()
        except Exception:
            task_context_store.get_task_logger(task.id).error(
                f"stop_media_stream failed:\n{traceback.format_exc()}"
            )

    @staticmethod
    def _key(task: Task) -> str:
        return f"task_{task.id}"


# Module-level singleton consumed by job runners.
stream_factory = MediaStreamFactory()
