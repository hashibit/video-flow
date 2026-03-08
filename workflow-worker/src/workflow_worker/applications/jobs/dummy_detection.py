import time
from dataclasses import dataclass, field
from datetime import datetime

from workflow_worker.interfaces.api.media_service_pb2 import NotifyStatus
from workflow_worker.shared.logging._logging import get_logger
from workflow_worker.domain.entities.task import Task
from workflow_worker.applications.jobs.module import ModuleBase
from workflow_worker.applications.jobs.model import TaskResult, TaskResultCategory
from workflow_worker.interfaces.events.event_factory import JobEvent

logger = get_logger(__name__)


class SingleDummyDetectionJobCfg:
    pass


@dataclass
class DummyDetectionJobCfg:
    configs: list[SingleDummyDetectionJobCfg] = field(default_factory=list)


class DummyDetection(ModuleBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rule_idx: int = 0

    def parse_task(self, task: Task) -> DummyDetectionJobCfg:
        configs = []
        for rule_section in task.scenario.rule_sections:
            for rule_point in rule_section.rule_points:
                if rule_point and rule_point.same_frame_cfg:
                    config = SingleDummyDetectionJobCfg()
                    configs.append(config)
        return DummyDetectionJobCfg(configs=configs)

    def run(self, task: Task, job_cfg: DummyDetectionJobCfg, frame_ch, event_q) -> TaskResult:
        event_id = 10000
        event_q.put(JobEvent(
            id=event_id,
            task_id=task.id,
            name=f"Task_{task.id}_Rule_{self.rule_idx}_DummyDetectionStarted_{event_id}",
            algo="dummy_detection",
            created_at=datetime.now(),
        ))

        i = 0
        frame_gen = frame_ch.output()
        for frame in frame_gen:
            if frame.status == NotifyStatus.finish:
                logger.info("frame queue drained, quit")
                break
            logger.info(f"process frame: {frame.id}")
            # process frame
            logger.info("DummyDetection is running...")

            # simulate slow process speed: 2f/s
            time.sleep(2)

            event_id = 10000 + i + 1
            logger.info("produce event")
            event_q.put(JobEvent(
                id=event_id,
                task_id=task.id,
                name=f"Task_{task.id}_Rule_{self.rule_idx}_DummyDetectionRunning_{event_id}",
                algo="dummy_detection",
                created_at=datetime.now(),
            ))

            i += 1

        frame_gen.close()

        event_id = 20000
        event_q.put(JobEvent(
            id=event_id,
            task_id=task.id,
            name=f"Task_{task.id}_Rule_{self.rule_idx}_DummyDetectionFinished_{event_id}",
            algo="dummy_detection",
            created_at=datetime.now(),
        ))

        task_result = TaskResult(category=TaskResultCategory.RuleTypeTest,
                                 rule_type_test=["a", "b", "c"], )
        return task_result
