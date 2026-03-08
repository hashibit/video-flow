
from typing import Any
from pydantic import BaseModel


class ReportPerson(BaseModel):
    """ReportPerson represents person related entity in report"""

    url: str | None = ""  # URL indicates the image link
    identity: str | None = ""  # User identity
    identity_type: str | None = "unknown"
    appearance_requirement: str | None = "not display"  # Whether must appear in video
    times: list[dict[str, Any]]


class HumanTackReportResult(BaseModel):
    """HumanTackReportResult represents detailed result information for same frame statistics (person tracking) quality inspection item"""

    cumulative_number: int  # Cumulative number of people appearing
    persons: list[ReportPerson]  # List of all tracked persons in video
    strangers: list[ReportPerson]  # Strangers in video (no photo provided)
    lost_participants: list[ReportPerson]  # List of lost tracked persons
    max_participants: list[ReportPerson]  # List of persons in same frame with maximum count
    ratio_participants: list[ReportPerson]  # List of persons exceeding warning threshold

    status: str
    reasons: list[str]


class PersonTrackingReport(BaseModel):
    status: str
    reasons: list[str]
    result: HumanTackReportResult
