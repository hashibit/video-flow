
from pydantic import BaseModel

from workflow_worker.domain.entities.common.time_patch import TimePatch
from workflow_worker.domain.entities.task import Media


class TimeRangeType:
    ALL_VIDEO = 0
    PART_VIDEO = 1


class EmergencyType:
    ALL_TIME = 0
    AT_LEAST_ONE = 1


class TextType:
    ALL_TEXT = 0
    PART_TEXT = 1


class SingleSubtitleJobCfg(BaseModel):
    text_index: int
    text: str
    threshold: float
    time_patchs: list[TimePatch]
    time_range_type: int  # 0=full video, 1=video segment
    emergency_type: int  # 0=always present, 1=at least once
    text_type: int  # 0=full display, 1=partial display
    min_text_number: int | None = -1  # minimum character count requirement
    cumulative_threshold: float | None = -1  # cumulative display ratio
    continuous_appearance_times: int  # continuous appearance duration in seconds


class SubtitleJobCfg(BaseModel):
    """Subtitle / on-screen text inspection rule point configuration."""

    id: int  # task id
    rule_id: int  # rule id
    media: Media
    fps: float
    configs: list[SingleSubtitleJobCfg]
