from typing import Any

from pydantic import BaseModel

from workflow_worker.domain.entities.common.time_patch import TimePatch
from workflow_worker.domain.entities.frame import Frame


class RecogSubtitle(BaseModel):
    id: int
    origin_text: str
    recog_text: str
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    mask: list[bool]
    similarity: float
    frame_time: float
    origin_recog_text: list[str | None] = []


class Subtitle(BaseModel):
    id: int
    rule_id: int
    recog_time_patchs: list[TimePatch]
    time_range_type: int
    text_type: int  # 1=scrolling subtitle, 0=static
    emergency_type: int  # 0=always present, 1=at least once
    text: str
    recog_threshold: float
    min_text_number: int
    continuous_appearance_times: int  # continuous display duration in seconds
    total_continuous_appearance_frame: int | None = 0  # total frames satisfying continuous appearance

    similarity_mapper: dict[float, float | None] = {}  # per-frame similarity scores (total_similarity)
    miss_frame_times: list[float | None] = []
    total_frames_count: int | None = 0
    mask: list[bool | None] = []
    similaritys: list[float | None] = []
    x_min: float | None = 1e10
    y_min: float | None = 1e10
    x_max: float | None = -1
    y_max: float | None = -1

    # whether any frames satisfying the requirement have been tracked
    def is_tracked(self):
        return len(self.miss_frame_times) != self.total_frames_count

class MissResult(BaseModel):
    frame: Frame
    miss_ids: list[int]  # ids of subtitles not found in this frame


class SubtitleJobResult(BaseModel):
    ai_result: dict[str, Any]  # was List[MissResult]; changed to Any for easier refactoring
    recog_results: list[Subtitle] = []
