
from pydantic import BaseModel

from workflow_worker.domain.entities.tasks.subtitle_matching.result import Subtitle


class SubtitleMatchingSingleResult(BaseModel):
    subtitle_result: Subtitle
    reasons: list[str]


class SubtitleMatchingReport(BaseModel):
    """Subtitle Matching Report

    Attributes:
        status (str): status of this rule point
        reasons (list[str]): failed reasons of this rule point
        result (list[SubtitleMatchingSingleResult]): result of job
    """

    status: str = "passed"
    reasons: list[str]
    result: list[SubtitleMatchingSingleResult] = []
