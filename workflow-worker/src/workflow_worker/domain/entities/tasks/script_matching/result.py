from typing import Any

from pydantic import BaseModel


class ScriptMatchingReply(BaseModel):
    text: str
    start_time: int
    end_time: int


class ScriptMatchingResult(BaseModel):
    id: int  # corresponding RulePoint id
    start_time: int
    end_time: int
    auc_text: str  # detected script text
    start_idx: int  # start index of this text within the full Dialogue
    end_idx: int  # end index
    score: float  # similarity score
    replys: list[ScriptMatchingReply] = []  # customer reply segments
    diff_text: list[str] = []  # diff text for comparison display


class ScriptMatchingJobResult(BaseModel):
    results: list[ScriptMatchingResult]
    ai_result: dict[str, Any]
