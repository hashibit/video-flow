from workflow_worker.domain.entities.tasks.banned_word_detection.report import BannedWordDetectionReport
from workflow_worker.domain.entities.tasks.banned_word_detection.result import BannedWordDetectionJobResult
from workflow_worker.domain.entities.rule import RulePoint
from workflow_worker.domain.entities.task import Task
from workflow_worker.applications.modules.base.reporter import Reporter


class BannedWordDetectionReporter(Reporter):
    def __init__(self) -> None:
        super().__init__()
        self.job_name = "banned_word_detection"

    def run(
        self,
        rule_point: RulePoint,
        task: Task,
        banned_word_detection_job_result: BannedWordDetectionJobResult,
        **job_results
    ) -> BannedWordDetectionReport:
        """Run reporter to get a report for rule point

        Args:
            rule_point (RulePoint): rule point object
            task (Task): the origin task object
            banned_word_detection_job_result (BannedWordDetectionJobResult): banned word detection result

        Returns:
            BannedWordDetectionReport: report of the banned word detection rule point
        """
        status = "passed"
        reasons: list[str] = []
        result = None
        for (
            banned_word_detection_result
        ) in banned_word_detection_job_result.banned_word_detection_results:
            if banned_word_detection_result.id == rule_point.id:
                result = banned_word_detection_result
                reasons = []
                if len(banned_word_detection_result.detected_banned_words):
                    status = "failed"
                    reasons.append("Banned word detected")
                break

        return BannedWordDetectionReport(reasons=reasons, status=status, result=result)
