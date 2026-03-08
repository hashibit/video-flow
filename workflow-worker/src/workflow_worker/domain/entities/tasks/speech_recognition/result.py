from typing import Any

from pydantic import BaseModel


class SpeechRecognitionResult(BaseModel):
    ai_result: dict[str, Any]
