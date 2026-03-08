
from typing import Any
from workflow_worker.domain.entities.tasks.document_recognition.report import DocumentRecognitionReport
from workflow_worker.domain.entities.tasks.document_recognition.result import DocumentRecognitionJobResult
from workflow_worker.domain.entities.tasks.signature_recognition.result import SignatureRecognitionJobResult
from workflow_worker.domain.entities.rule import RulePoint
from workflow_worker.domain.entities.task import Task
from workflow_worker.applications.jobs.base.reporter import Reporter


class DocumentReporter(Reporter):
    def __init__(self) -> None:
        super().__init__()
        self.job_name = "document_reporter"

    def run(
        self,
        rule_point: RulePoint,
        task: Task,
        doc_recog_result: DocumentRecognitionJobResult,
        sign_recog_result: SignatureRecognitionJobResult,
        **job_results,
    ) -> DocumentRecognitionReport:
        """Run reporter to get a report for rule point.

        Args:
            rule_point (RulePoint): Rule point object
            task (Task): The origin task object
            doc_recog_result (DocumentRecognitionJobResult): Job result from doc_recog_job.
            sign_recog_result (SignatureRecognitionJobResult): Job result from sing_recog_job.

            Returns:
                DocumentRecognitionReport: Report of the input document rule point.
        """
        report: dict[str, Any] = {"reasons": [], "status": 0}

        self._check_doc_title(rule_point, doc_recog_result, report)
        self._check_signature(rule_point, sign_recog_result, report)
        return DocumentRecognitionReport(
            reasons=report["reasons"], status="failed" if report["status"] else "passed"
        )

    def _check_doc_title(
        self, rule_point: RulePoint, doc_recog_result: DocumentRecognitionJobResult, report: dict[str, Any]
    ):
        """Check whether all required document titles have been recognized. All titles must be detected to pass."""
        # Get all title needs recognition from rule point.
        doc_titles = set()
        for doc_cfg in rule_point.document_cfgs:
            if doc_cfg:
                doc_titles.add(doc_cfg.document_title)

        # Get all recog doc title from doc_recog_result
        rule_point_id = rule_point.id
        recog_doc_titles = set()
        for id, recog_result in doc_recog_result.results:
            if id == rule_point_id:
                recog_doc_titles.add(recog_result.origin_texts[0])

        miss_titles = doc_titles - recog_doc_titles
        for miss_title in miss_titles:
            report["status"] = 1
            report["reasons"].append("Document with title '{}' not detected".format(miss_title))

    def _check_signature(
        self, rule_point: RulePoint, sign_recog_result: SignatureRecognitionJobResult, report: dict[str, Any]
    ):
        """Check whether signatures satisfy the quality-inspection requirement.
        Current strategy: detecting any signature is sufficient to pass."""
        need_detection = False
        for doc_cfg in rule_point.document_cfgs:
            if not doc_cfg:
                continue
            for sign_info in doc_cfg.signature_infos:
                if sign_info and sign_info.signature_detection_flag:
                    need_detection = True
                    break
        if need_detection and len(sign_recog_result.results) <= 0:
            report["status"] = 1
            report["reasons"].append("No signature detected")
