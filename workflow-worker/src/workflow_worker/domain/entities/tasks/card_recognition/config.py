
from pydantic import BaseModel

from workflow_worker.domain.entities.frame import Frame
from workflow_worker.domain.entities.task import Media


class SingleCardRecognitionJobCfg(BaseModel):
    """Configuration entity for a single card detection & recognition task."""

    id: int
    frame_infos: dict[str, Frame | None]  # {time: frame} mapping list, kept for compatibility

    card_id: str  # tracking id for this card
    # card field info e.g. {"name": {"text": "xxxxx", "similarity_threshold": 0.75}}
    card_infos: dict[str, dict[str, object] | None] = {}
    # keys to recognize e.g. ['name', 'card_number'...]
    recog_keys: list[str | None] = []
    detection_threshold: float | None = -1  # detection threshold
    need_detection: bool | None = True  # whether to run detection
    need_recog: bool | None = False  # whether to run recognition


class CardRecognitionJobCfg(BaseModel):
    """Configuration entity for the card recognition job."""

    fps: float  # frame sampling rate
    batch_size: int  # max number of frames per service call
    media: Media  # video media information
    configs: list[SingleCardRecognitionJobCfg]  # list of card recognition task configs
