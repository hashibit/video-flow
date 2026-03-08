"""Factory for creating the appropriate data source based on environment config."""
from workflow_worker.domain.entities.task import Task
from workflow_worker.shared.utils.env import get_env
from workflow_worker.infrastructure.media_stream.base import AbstractDataSource


def create_data_source(task: Task, **kwargs) -> AbstractDataSource:
    """Instantiate the correct data source for the current environment.

    Reads ``env.media_data_source`` to decide which implementation to use:
      - ``local_ffmpeg``   → DataSourceFFmpeg (reads from local file via ffmpeg)
      - ``media_manager``  → DataSourceGRPC   (streams from remote media manager)
    """
    # Lazy imports to avoid circular dependencies at module load time.
    from workflow_worker.infrastructure.media_stream.data_source_ffmpeg import DataSourceFFmpeg
    from workflow_worker.infrastructure.media_stream.data_source_grpc import DataSourceGRPC

    env = get_env()
    src = env.media_data_source
    if src == "local_ffmpeg":
        return DataSourceFFmpeg(task, media_url=task.media.path, **kwargs)
    elif src == "media_manager":
        return DataSourceGRPC(task, media_manager_host=env.get_media_manager_host(), **kwargs)
    raise ValueError(f"Unsupported media_data_source: {src!r}")
