from datetime import datetime

from workflow_worker.domain.entities.tasks.person_tracking.config import (
    PersonTrackingJobCfg,
    SinglePersonTrackingJobCfg,
)
from workflow_worker.domain.entities.tasks.person_tracking.result import PersonTrackingJobResult
from workflow_worker.domain.entities.tasks.person_tracking.report import HumanTackReportResult
from workflow_worker.domain.entities.task import Task
from workflow_worker.applications.modules.person_tracking.processor import PersonTrackingProcessor
from workflow_worker.shared.logging._logging import get_logger
from workflow_worker.services.ai.det.service import DetService
from workflow_worker.services.ai.track.service import TrackService
from workflow_worker.applications.modules.module import ModuleBase
from workflow_worker.applications.modules.model import JobName
from workflow_worker.interfaces.events.event_factory import JobEvent
from workflow_worker.infrastructure.media_stream.utils import gather_batch_frames_from_generator
from workflow_worker.applications.workflows.task_context import TaskContext

logger = get_logger(__name__)


class PersonTrackingModule(ModuleBase):
    def __init__(self, task: Task) -> None:
        super().__init__(task)

    def parse_task(self, task: Task) -> PersonTrackingJobCfg:
        """Parse task to dict.

        Args:
            task (Task): task config.

        Returns:
            dict: human tacking config.

        ex:
            task.scenario:{
                "rule_sections": [
                  {
                    "rule_points": [
                      {
                        "same_frame_cfg": {
                          "fps": 2.0,
                          "min_time_interval": 5.0,
                          "face_verification_threshold": 0.6, // Face verification threshold
                          "cumulative_number": 3, // Cumulative number of people appearing
                          "stranger_warning_flag": false, // Stranger warning flag
                          "num_of_people": 2, // Maximum number of people in same frame
                          "lost_warning_threshold": 1.0, // Lost warning duration threshold
                          "ratio": 1.0 // Same-frame duration ratio
                        },
                        "id": 9
                      }
                    ]
                  },
                ],
            }
        """
        configs = []
        for rule_section in task.scenario.rule_sections:
            for rule_point in rule_section.rule_points:
                if rule_point and rule_point.same_frame_cfg:
                    cfg = rule_point.same_frame_cfg
                    config = SinglePersonTrackingJobCfg(
                        id=rule_point.id,
                        frame_infos={},
                        fps=cfg.fps,  # Previously in rule.fps, now moved to same_frame_cfg to be consistent with other jobs
                        min_time_interval=cfg.min_time_interval * 1000,
                        batch_size=10,
                        verification_threshold=cfg.face_verification_threshold,
                        cumulative_number=cfg.cumulative_number,
                        stranger_warning_flag=cfg.stranger_warning_flag,
                        num_of_people=cfg.num_of_people,
                        lost_warning_threshold=cfg.lost_warning_threshold,
                        ratio=cfg.ratio,
                    )
                    configs.append(config)
        return PersonTrackingJobCfg(id=task.id, media=task.media, configs=configs)

    def run(self, job_cfg: PersonTrackingJobCfg, task_context: TaskContext) -> HumanTackReportResult:
        """Parse the config from job_cfg and tracking human.

        Args:
            job_cfg (PersonTrackingJobCfg): the config parsed from task.
            task_context (TaskContext): The global task context.

        Returns:
            PersonTrackingReport: the tacking job result.
        """
        # TaskConfigInfo

        frame_ch = task_context.frame_channels[JobName.PersonTracking]
        event_ch = task_context.event_channels[JobName.PersonTracking]
        assert not isinstance(frame_ch, list) and frame_ch is not None
        assert not isinstance(event_ch, list) and event_ch is not None

        cfg: SinglePersonTrackingJobCfg = job_cfg.configs[0]
        fps = cfg.fps
        batch_size = cfg.batch_size
        min_time_interval = int(cfg.min_time_interval)
        verification_threshold = cfg.verification_threshold

        event_id = 0
        event_ch.put(JobEvent(
            id=event_id,
            task_id=self.task_uuid,
            name="PersonTrackingStarted",
            algo=JobName.PersonTracking,
            created_at=datetime.now(),
        ))

        # FaceDetectionService
        detection_service = DetService()
        # TrackingService
        tracking_service = TrackService(
            fps, min_time_interval, verification_threshold
        )

        # human_messages records all FaceInfo recognized in each frame, with timestamp as key
        human_messages = {}

        media_meta = job_cfg.media.meta
        media_fps = 25
        if media_meta and media_meta.fps:
            media_fps = int(float(media_meta.fps))
        process_fps = cfg.fps
        process_step = int(media_fps / process_fps)

        frame_gen = frame_ch.output()
        for batch_frame in gather_batch_frames_from_generator(frame_gen, process_step, batch_size):
            # logger.info(f"get frame from generator. batch size: {batch_frame.batch_size}, "
            #             f"largest frame-id: {batch_frame.frames[-1].id}")
            # get the face_infos & body_infos from detection service.
            detection_results = detection_service.run(batch_frame)
            # using the detection results to do tracking and get the temp
            # tracking results. human_message is a dict saved timestamp and human_infos
            # to debug.
            human_message = tracking_service.run(detection_results, batch_frame)
            human_messages.update(human_message)
        frame_gen.close()

        tracking_service.sequence_manager.merge()
        tracking_service.sequence_manager.filter_burr()
        tracking_service.sequence_manager.filter_noface_human()
        tracking_result = tracking_service.get_result()
        job_result = PersonTrackingJobResult(
            human_messages=human_messages, results=tracking_result
        )
        processor = PersonTrackingProcessor()
        # TODO: type renaming
        return processor.run(cfg, self.task, job_result)
