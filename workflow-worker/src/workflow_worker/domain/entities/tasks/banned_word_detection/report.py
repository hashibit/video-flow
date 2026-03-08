from pydantic import BaseModel

from workflow_worker.domain.entities.tasks.banned_word_detection.result import BannedWordDetectionResult


class BannedWordDetectionReport(BaseModel):
    """Banned Word Detection Report

    Attributes:
        status (str): status of this rule point
        reasons (list[str]): failed reasons of this rule point
        result (BannedWordDetectionResult): result of job
    """

    status: str = "passed"
    reasons: list[str]
    result: BannedWordDetectionResult | None = None
