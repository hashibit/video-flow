"""Abstract base class for media data sources."""
from abc import ABC, abstractmethod

from workflow_worker.domain.entities.task import MediaMeta, Task
from workflow_worker.applications.workflows.task_context import task_context_store


class AbstractDataSource(ABC):
    """Base for all media data sources.

    Subclasses implement the three-phase lifecycle:
      1. extract_metadata() — synchronous, called at construction time
      2. setup(decode_fps)  — async, prepares the source for streaming
      3. stream(callback)   — async, delivers StreamMessage objects via callback
    """

    def __init__(self, task: Task):
        self.task = task
        self.logger = task_context_store.get_task_logger(task.id).getChild(self.__class__.__name__)

    @abstractmethod
    def extract_metadata(self) -> MediaMeta:
        """Extract media metadata and store it on task.media.meta."""

    @abstractmethod
    async def setup(self, decode_fps: int = 0) -> None:
        """Prepare the source for streaming at the given fps."""

    @abstractmethod
    async def stream(self, callback) -> None:
        """Stream messages by calling callback(StreamMessage).

        callback returns True to request early termination.
        """

    async def close(self) -> None:
        """Release resources. Override when cleanup is needed."""
