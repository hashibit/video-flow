from typing import Any

from workflow_worker.domain.entities.tasks.card_recognition.report import CardRecognitionReport
from workflow_worker.domain.entities.tasks.card_recognition.result import CardRecognitionJobResult
from workflow_worker.domain.entities.rule import RulePoint
from workflow_worker.domain.entities.task import Task
from workflow_worker.applications.modules.base.reporter import Reporter


class CardReporter(Reporter):
    def __init__(self) -> None:
        super().__init__()
        self.job_name = "document_reporter"

    def run(
        self,
        rule_point: RulePoint,
        task: Task,
        card_recog_result: CardRecognitionJobResult,
        **job_results,
    ) -> CardRecognitionReport:
        """Run reporter to get a report for rule point.

        Args:
            rule_point (RulePoint): rule point object
            task (Task): the origin task object
            card_recog_result (CardRecognitionJobResult): job result from card_recog_job.

            Returns:
                CardRecognitionReport: report of the input card rule point.
        """
        report: dict[str, Any] = {"reasons": [], "status": 0}

        self._check_cards(rule_point, card_recog_result, report)
        return CardRecognitionReport(
            reasons=report["reasons"], status="failed" if report["status"] else "passed"
        )

    def _check_cards(
        self, rule_point: RulePoint, card_recog_result: CardRecognitionJobResult, report: dict[str, Any]
    ):
        """Check whether the detected cards satisfy the quality-inspection requirement.
        Current strategy: detecting any card is sufficient to pass.

        Args:
            rule_point (RulePoint): The corresponding rule point.
            card_recog_result (CardRecognitionJobResult): Output from the card recognition job.
            report (Dict): The raw report dict to be mutated.
        """
        need_detection = False
        for card_cfg in rule_point.verification_cfgs:
            if card_cfg and card_cfg.card_content_flag:
                need_detection = True
                break
        if need_detection and len(card_recog_result.results) <= 0:
            report["status"] = 1
            report["reasons"].append("No identity card detected")
