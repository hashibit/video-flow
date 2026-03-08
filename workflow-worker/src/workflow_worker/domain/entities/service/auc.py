
from pydantic import BaseModel

from workflow_worker.domain.entities.dialogue import Dialogue


class AUCServiceResult(BaseModel):
    """Result returned by the AUC (Audio Understanding Chain) service."""

    dialogue: Dialogue
    request_id: str | None = None  # speech service request id
