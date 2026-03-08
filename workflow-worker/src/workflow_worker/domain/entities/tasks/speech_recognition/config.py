
from pydantic import BaseModel

from workflow_worker.domain.entities.audio import Audio


class SpeechRecognitionJobCfg(BaseModel):
    id: int
    audio: Audio
