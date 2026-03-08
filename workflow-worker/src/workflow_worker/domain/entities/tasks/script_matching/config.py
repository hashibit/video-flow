
from pydantic import BaseModel

from workflow_worker.domain.entities.audio import Audio


class SingleScriptMatchingJobCfg(BaseModel):
    id: int
    script: str
    script_threshold: float
    key_words: list[str | None] = []
    key_word_threshold: float | None = 0.4
    answer_flag: bool | None = False


class ScriptMatchingJobCfg(BaseModel):
    """Configuration for the script matching job."""

    id: int
    audio: Audio | None
    configs: list[SingleScriptMatchingJobCfg]
