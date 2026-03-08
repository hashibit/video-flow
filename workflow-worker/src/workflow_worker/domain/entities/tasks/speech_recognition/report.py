
from pydantic import BaseModel

from workflow_worker.domain.entities.tasks.speech_recognition.result import SpeechRecognitionResult


class SpeechRecognitionReport(BaseModel):
    status: str = "passed"
    reasons: list[str]
    result: SpeechRecognitionResult
