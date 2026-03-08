
from pydantic import BaseModel

from workflow_worker.domain.entities.frame import Frame
from workflow_worker.domain.entities.task import Media


class SingleSignatureRecognitionJobCfg(BaseModel):
    """Configuration entity for a single signature detection & recognition task."""

    id: int
    frame_infos: dict[str, Frame | None]  # {time: frame} mapping list, kept for compatibility

    text: str  # expected signature content
    sign_id: str  # tracking id for this signature
    detection_threshold: float | None = -1  # detection threshold
    recog_threshold: float | None = -1  # recognition threshold (signature recognition not yet supported)
    need_detection: bool | None = True  # flag: whether to perform signature detection
    need_recog: bool | None = False  # flag: whether to perform signature recognition


class SignatureRecognitionJobCfg(BaseModel):
    """Configuration entity for the signature detection & recognition job."""

    fps: float  # frame sampling rate
    batch_size: int  # max number of frames per batch
    media: Media  # media information
    configs: list[SingleSignatureRecognitionJobCfg]  # list of signature recognition configs
