
from pydantic import BaseModel


class DocumentRecognitionReport(BaseModel):
    """Report for document recognition inspection."""

    status: str  # "passed" or "failed"
    reasons: list[str]  # failure reasons
