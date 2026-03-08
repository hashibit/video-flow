from workflow_worker.services.ai.auc.service import AUCService
from workflow_worker.applications.modules.model import JobName

from workflow_worker.domain.entities.tasks.banned_word_detection.config import (
    BannedWordDetectionJobCfg,
    SingleBannedWordDetectionJobCfg,
)
from workflow_worker.domain.entities.tasks.banned_word_detection.result import (
    BannedWordDetectionJobResult,
    BannedWordDetectionResult,
    DetectedBannedWord,
)
from workflow_worker.domain.entities.service.auc import AUCServiceResult
from workflow_worker.domain.entities.task import Task
from workflow_worker.applications.modules.module import ModuleBase
from workflow_worker.applications.workflows.task_context import TaskContext


class BannedWordDetectionModule(ModuleBase):
    def __init__(self, task) -> None:
        super().__init__(task)
        self.required_jobs = ["script_match"]
        self.symbols_translate_table = str.maketrans(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz", ",;.!，；、。！ "
        )

    def parse_task(self, task: Task) -> BannedWordDetectionJobCfg:
        """Parse task to job config.

        Args:
            task (Task): task entity.
            auc_service_result (AUCServiceResult): AUC Service's result

        Returns:
            BannedWordDetectionJobCfg: banned word detection config.
        """
        configs = []
        for rule_section in task.scenario.rule_sections:
            for rule_point in rule_section.rule_points:
                if rule_point and rule_point.banword_cfg:
                    config = SingleBannedWordDetectionJobCfg(
                        id=rule_point.id,
                        banned_words=[w for w in rule_point.banword_cfg.banwords if w is not None],
                        require_words=[w for w in rule_point.banword_cfg.require_words if w is not None],
                    )
                    configs.append(config)

        return BannedWordDetectionJobCfg(id=task.id, auc_service_result=None, configs=configs)

    def run(self, banned_word_detection_job_cfg: BannedWordDetectionJobCfg, task_context: TaskContext) -> BannedWordDetectionJobResult | None:
        """Run banned word detection job.

        Args:
            banned_word_detection_job_cfg (BannedWordDetectionJobCfg): banned word detection job config.
            task_context (TaskContext): TaskContext

        Returns:
            BannedWordDetectionResult: banned word detection job results.
        """

        _event_ch = task_context.event_channels[JobName.BannedWordDetection]

        logger = task_context.get_task_logger().getChild("Module.BannedWordDetection")

        auc_service_result: AUCServiceResult | None = task_context.get_auc_service_result()
        if not auc_service_result:
            if auc_service_result is None:
                logger.error("no auc service result in task_context?? fallback: use audio to extract one.")
                audio = task_context.get_audio_object()
                if not audio:
                    logger.error("no audio in task_context?? return None result")
                    return None
                service = AUCService()
                auc_service_result = service.run(audio)
                task_context.set_auc_service_result(auc_service_result)

        results = []
        for cfg in banned_word_detection_job_cfg.configs:
            banned_words = cfg.banned_words
            detected_banned_words = []
            for utterence in auc_service_result.dialogue.utterances:
                utterence_clean = utterence.text.translate(self.symbols_translate_table)
                # Detect banned words
                for banned_word in banned_words:
                    banned_word_clean = banned_word.translate(self.symbols_translate_table)
                    if banned_word_clean in utterence_clean:
                        left_comma_index = utterence.text.rfind(
                            "，", 0, utterence.text.find(banned_word_clean[0])
                        )
                        right_comma_index = utterence.text.find(
                            "，",
                            utterence.text.rfind(banned_word_clean[len(banned_word_clean) - 1]),
                        )
                        detected_banned_words.append(
                            DetectedBannedWord(
                                start_time=utterence.start_time,
                                end_time=utterence.end_time,
                                banned_word=banned_word,
                                text=utterence.text[
                                     left_comma_index + 1 : right_comma_index
                                     if right_comma_index > 0
                                     else len(utterence.text)
                                     ],
                            )
                        )

            results.append(
                BannedWordDetectionResult(
                    id=cfg.id,
                    detected_banned_words=detected_banned_words,
                )
            )

        logger.info(f"banned_word_detection_results results: {results}")
        # no need for saving word-level info
        # for i in range(len(auc_service_result.dialogue.utterances)):
        #     auc_service_result.dialogue.utterances[i].words = []
        return BannedWordDetectionJobResult(
            banned_word_detection_results=results, ai_result={"auc": auc_service_result}
        )
