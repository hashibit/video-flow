from logging import Logger
from typing import Any

from workflow_worker.domain.entities.audio import Audio
from workflow_worker.domain.entities.tasks.banned_word_detection.result import BannedWordDetectionJobResult
from workflow_worker.domain.entities.tasks.script_matching.result import ScriptMatchingJobResult
from workflow_worker.domain.entities.tasks.person_tracking.result import PersonTrackingJobResult
from workflow_worker.domain.entities.tasks.speech_recognition.result import SpeechRecognitionResult
from workflow_worker.domain.entities.tasks.subtitle_matching.result import SubtitleJobResult
from workflow_worker.domain.entities.report import Report
from workflow_worker.domain.entities.service.auc import AUCServiceResult
from workflow_worker.domain.entities.task import Task
from workflow_worker.applications.jobs.data_loader import DataLoader  # pyright: ignore[reportImportCycles]
from workflow_worker.applications.jobs.model import JobName
from workflow_worker.applications.jobs.report.job import ReportJob
from workflow_worker.interfaces.events.event_factory import EventCollector
from workflow_worker.infrastructure.media_stream.frame_channel import FrameChannel


class TaskContext(object):
    """Context object for task execution."""

    def __init__(self, task: Task, task_logger: Logger):
        """Initialize task context.

        Args:
            task: The task to execute
            task_logger: Global logger for the task
        """
        self.task = task
        self.task_uuid = task.id

        self.frame_channels: dict[JobName, None | FrameChannel | list[FrameChannel]] = {}
        self.event_channels: dict[JobName, None | EventCollector | list[EventCollector]] = {}

        self.speech_recognition_result: SpeechRecognitionResult | None = None
        self.script_matching_result: ScriptMatchingJobResult | None = None
        self.person_tracking_result: PersonTrackingJobResult | None = None
        self.banned_word_detection_result: BannedWordDetectionJobResult | None = None
        self.subtitle_matching_result: SubtitleJobResult | None = None

        self.task_logger = task_logger
        self.logger = task_logger.getChild(f"TaskContext-{task.id}")

        self.data_loader = DataLoader()

    def get_task_logger(self):
        """Get the task logger."""
        return self.task_logger

    def update_module_results(self, results: dict[str, Any]):
        """Update results from module execution.

        Args:
            results: Dictionary of module results
        """
        for module_name, module_result in results.items():
            if JobName.SpeechRecognition in module_name:
                self.speech_recognition_result = module_result
            elif JobName.ScriptMatching in module_name:
                self.script_matching_result = module_result
            elif JobName.PersonTracking in module_name:
                self.person_tracking_result = module_result
            elif JobName.BannedWordDetection in module_name:
                self.banned_word_detection_result = module_result
            elif JobName.SubtitleMatching in module_name:
                self.subtitle_matching_result = module_result
            else:
                self.logger.error("Unknown module name: %s" % module_name)

    def create_job_report(self) -> Report:
        """Create a job report from all module results.

        Returns:
            Report: The generated job report
        """
        report_job = ReportJob()
        job_reporters = report_job.parse_task(self.task)

        job_results = {}
        if self.speech_recognition_result:
            job_results[JobName.SpeechRecognition + "_job_result"] = self.speech_recognition_result
        if self.script_matching_result:
            job_results[JobName.ScriptMatching + "_job_result"] = self.script_matching_result
        if self.person_tracking_result:
            job_results[JobName.PersonTracking + "_job_result"] = self.person_tracking_result
        if self.banned_word_detection_result:
            job_results[JobName.BannedWordDetection + "_job_result"] = self.banned_word_detection_result
        if self.subtitle_matching_result:
            job_results[JobName.SubtitleMatching + "_job_result"] = self.subtitle_matching_result

        self.logger.info(f'[third result] -> {job_results}')
        report = report_job.run(self.task, job_reporters, **job_results)

        return report

    def set_audio_object(self, audio: Audio):
        """Set the audio object for this task."""
        return self.data_loader.set_audio_object(self.task_uuid, audio)

    def get_audio_object(self) -> Audio | None:
        """Get the audio object for this task."""
        return self.data_loader.get_audio_object(self.task_uuid)

    def get_auc_service_result(self) -> AUCServiceResult | None:
        """Get the AUC service result."""
        return self.data_loader.get_auc_service_result(self.task_uuid)

    def set_auc_service_result(self, auc_service_result: AUCServiceResult):
        """Set the AUC service result."""
        return self.data_loader.set_auc_service_result(self.task_uuid, auc_service_result)


class TaskContextStore(object):
    """Storage for task contexts."""

    def __init__(self):
        """Initialize the store."""
        self.container: dict[int, TaskContext] = {}

    def store(self, task_id, task_context: TaskContext):
        """Store a task context.

        Args:
            task_id: The task ID
            task_context: The task context to store
        """
        self.container[task_id] = task_context

    def fetch(self, task_id) -> TaskContext:
        """Fetch a task context by ID.

        Args:
            task_id: The task ID

        Returns:
            TaskContext: The task context

        Raises:
            KeyError: If task_id is not stored
        """
        return self.container[task_id]

    def clear(self, task_id):
        """Clear a task context by ID.

        Args:
            task_id: The task ID to clear
        """
        if task_id in self.container:
            self.container.pop(task_id)

    def get_task_logger(self, task_id):
        """Get the task logger by ID.

        Args:
            task_id: The task ID

        Returns:
            The task logger
        """
        return self.fetch(task_id).get_task_logger()


task_context_store = TaskContextStore()
