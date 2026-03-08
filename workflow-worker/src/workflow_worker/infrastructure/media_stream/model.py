from pydantic import BaseModel

from workflow_worker.domain.entities.audio import Audio
from workflow_worker.domain.entities.frame import Frame


class StreamMessage(BaseModel):
    id: int
    image: Frame | None = None
    audio: Audio | None = None
    is_last: bool = False
