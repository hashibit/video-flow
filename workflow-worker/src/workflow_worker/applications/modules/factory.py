import functools
from typing import Any

from workflow_worker.domain.entities.task import Task
from workflow_worker.applications.modules.banned_word_detection.module import BannedWordDetectionModule
from workflow_worker.applications.modules.card_recognition.module import CardRecognitionModule
from workflow_worker.applications.modules.person_tracking.module import PersonTrackingModule
from workflow_worker.applications.modules.model import JobName
from workflow_worker.applications.modules.script_matching.module import ScriptMatchingModule
from workflow_worker.applications.modules.signature_recognition.module import SignatureRecognitionModule
from workflow_worker.applications.modules.speech_recognition.module import SpeechRecognitionModule
from workflow_worker.applications.modules.subtitle_matching.module import SubtitleMatchingModule
from workflow_worker.interfaces.events.event_factory import event_factory
from workflow_worker.infrastructure.media_stream.stream_factory import stream_factory
from workflow_worker.applications.workflows.task_context import TaskContext


def need_speech_detection(task: Task) -> bool:
    """Check if speech detection is needed for this task.

    Args:
        task: The task to check

    Returns:
        bool: True if speech detection is needed
    """
    job = SubtitleMatchingModule(task)
    job_configs = job.parse_task(task)
    if job_configs:
        return True
    job = ScriptMatchingModule(task)
    job_config = job.parse_task(task)
    if job_config and job_config.configs:
        return True
    job = BannedWordDetectionModule(task)
    job_config = job.parse_task(task)
    if job_config and job_config.configs:
        return True
    return False


def create_speech_recognition_modules(task: Task, task_context: TaskContext):
    """Create speech recognition modules.

    Args:
        task: The task to process
        task_context: The task context

    Returns:
        Dictionary of modules
    """
    modules: dict[str, Any] = {}
    name = JobName.SpeechRecognition
    if need_speech_detection(task):
        job = SpeechRecognitionModule(task)
        event_ch = event_factory.build_event_collector_for_algo(task, name)
        frame_ch = stream_factory.build_frame_channel_for_algo(task, name)

        modules[name] = functools.partial(job.run)
        task_context.frame_channels[name] = frame_ch
        task_context.event_channels[name] = event_ch

    return modules


def create_subtitle_matching_modules(task: Task, task_context: TaskContext):
    """Create subtitle matching modules.

    Args:
        task: The task to process
        task_context: The task context

    Returns:
        Dictionary of modules
    """
    modules: dict[str, Any] = {}
    name = JobName.SubtitleMatching
    job = SubtitleMatchingModule(task)
    job_configs = job.parse_task(task)
    if job_configs:
        event_ch_list = []
        frame_ch_list = []
        for i in range(len(job_configs)):
            event_ch_list.append(event_factory.build_event_collector_for_algo(task, name + str(i)))
            frame_ch_list.append(stream_factory.build_frame_channel_for_algo(task,
                                                                             name + str(i),
                                                                             fps=job_configs[i].fps))

        # Refresh job_configs after updating task information (e.g., media metadata)
        job_configs = job.parse_task(task)
        modules[name] = functools.partial(job.run, job_configs)
        task_context.frame_channels[name] = frame_ch_list
        task_context.event_channels[name] = event_ch_list

    return modules


def create_card_recognition_modules(task: Task, task_context: TaskContext):
    """Create card recognition modules.

    Args:
        task: The task to process
        task_context: The task context

    Returns:
        Dictionary of modules
    """
    modules: dict[str, Any] = {}
    name = JobName.CardRecognition
    job = CardRecognitionModule(task)
    job_config = job.parse_task(task)
    if job_config and job_config.configs:
        event_ch = event_factory.build_event_collector_for_algo(task, name)
        frame_ch = stream_factory.build_frame_channel_for_algo(task, name, fps=job_config.fps)

        # Refresh job_config after updating task information (e.g., media metadata)
        job_config = job.parse_task(task)
        modules[name] = functools.partial(job.run, job_config)
        task_context.frame_channels[name] = frame_ch
        task_context.event_channels[name] = event_ch

    return modules


def create_signature_recognition_modules(task: Task, task_context: TaskContext):
    """Create signature recognition modules.

    Args:
        task: The task to process
        task_context: The task context

    Returns:
        Dictionary of modules
    """
    modules: dict[str, Any] = {}
    name = JobName.SignatureRecognition
    job = SignatureRecognitionModule(task)
    job_config = job.parse_task(task)
    if job_config and job_config.configs:
        event_ch = event_factory.build_event_collector_for_algo(task, name)
        frame_ch = stream_factory.build_frame_channel_for_algo(task, name)

        # Refresh job_config after updating task information (e.g., media metadata)
        job_config = job.parse_task(task)
        modules[name] = functools.partial(job.run, job_config)
        task_context.frame_channels[name] = frame_ch
        task_context.event_channels[name] = event_ch

    return modules


def create_person_tracking_modules(task: Task, task_context: TaskContext):
    """Create person tracking modules.

    Args:
        task: The task to process
        task_context: The task context

    Returns:
        Dictionary of modules
    """
    modules: dict[str, Any] = {}
    name = JobName.PersonTracking
    job = PersonTrackingModule(task)
    job_config = job.parse_task(task)
    if job_config and job_config.configs:
        event_ch = event_factory.build_event_collector_for_algo(task, name)
        frame_ch = stream_factory.build_frame_channel_for_algo(task, name, fps=job_config.configs[0].fps)

        # Refresh job_config after updating task information (e.g., media metadata)
        job_config = job.parse_task(task)
        modules[name] = functools.partial(job.run, job_config)
        task_context.frame_channels[name] = frame_ch
        task_context.event_channels[name] = event_ch

    return modules


def create_banned_word_detection_modules(task: Task, task_context: TaskContext):
    """Create banned word detection modules.

    Args:
        task: The task to process
        task_context: The task context

    Returns:
        Dictionary of modules
    """
    modules: dict[str, Any] = {}
    name = JobName.BannedWordDetection
    job = BannedWordDetectionModule(task)
    job_config = job.parse_task(task)
    if job_config and job_config.configs:
        event_ch = event_factory.build_event_collector_for_algo(task, name)

        # Refresh job_config after updating task information (e.g., media metadata)
        job_config = job.parse_task(task)
        modules[name] = functools.partial(job.run, job_config)
        task_context.frame_channels[name] = None
        task_context.event_channels[name] = event_ch

    return modules


def create_script_matching_modules(task: Task, task_context: TaskContext):
    """Create script matching modules.

    Args:
        task: The task to process
        task_context: The task context

    Returns:
        Dictionary of modules
    """
    modules: dict[str, Any] = {}
    name = JobName.ScriptMatching
    job = ScriptMatchingModule(task)
    job_config = job.parse_task(task)
    if job_config and job_config.configs:
        event_ch = event_factory.build_event_collector_for_algo(task, name)

        # Refresh job_config after updating task information (e.g., media metadata)
        job_config = job.parse_task(task)
        modules[name] = functools.partial(job.run, job_config)
        task_context.frame_channels[name] = None
        task_context.event_channels[name] = event_ch

    return modules


def mock_speech_recognition_modules(task: Task):
    """Mock speech recognition modules for testing."""
    modules: dict[str, Any] = {}
    return modules


def mock_subtitle_matching_modules(task: Task):
    """Mock subtitle matching modules for testing."""
    modules: dict[str, Any] = {}
    return modules


def mock_person_tracking_modules(task: Task):
    """Mock person tracking modules for testing."""
    modules: dict[str, Any] = {}
    return modules


def mock_banned_word_detection_modules(task: Task):
    """Mock banned word detection modules for testing."""
    modules: dict[str, Any] = {}
    return modules


def mock_script_matching_modules(task: Task):
    """Mock script matching modules for testing."""
    modules: dict[str, Any] = {}
    return modules
