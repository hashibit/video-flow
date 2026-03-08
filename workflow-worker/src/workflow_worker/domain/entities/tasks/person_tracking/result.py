
from pydantic import BaseModel

from workflow_worker.domain.entities.human import Human
from workflow_worker.domain.entities.service.human_tracking import PersonTrackingResult


class PersonTrackingJobResult(BaseModel):
    """Tracking task result"""

    human_messages: dict[str, list[Human]]  # Retain personnel information for each frame, for debugging
    results: list[PersonTrackingResult]  # Tracking result list
