
from pydantic import BaseModel

from workflow_worker.domain.entities.tasks.script_matching.result import ScriptMatchingResult


class ScriptMatchingReport(BaseModel):
    """ScriptMatchingReport

    Attributes:
        status: job report status
        reasons: failed resasons
        result: job result
    """

    status: str = "passed"
    reasons: list[str]
    result: ScriptMatchingResult | None = None
