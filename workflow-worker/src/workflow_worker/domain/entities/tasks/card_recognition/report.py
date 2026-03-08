
from pydantic import BaseModel


class CardRecognitionReport(BaseModel):
    """Report for card recognition inspection."""

    status: str  # "passed" or "failed"
    reasons: list[str]  # failure reasons
