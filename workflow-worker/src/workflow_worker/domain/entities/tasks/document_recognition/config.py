
from pydantic import BaseModel

from workflow_worker.domain.entities.frame import Frame
from workflow_worker.domain.entities.task import Media


class SingleDocumentRecognitionJobCfg(BaseModel):
    """Configuration entity for a single document detection & recognition task."""

    id: int
    frame_infos: dict[str, Frame | None]  # {time: frame} mapping list, kept for compatibility

    title: str  # document title
    doc_id: str  # tracking id for this document
    detection_threshold: float | None = -1  # detection threshold
    recog_threshold: float | None = -1  # recognition threshold
    need_detection: bool | None = True  # flag: whether to perform document detection
    need_recog: bool | None = False  # flag: whether to perform document recognition


class DocumentRecognitionJobCfg(BaseModel):
    """Configuration entity for the document recognition job."""

    fps: float  # frame sampling rate
    batch_size: int  # max number of frames per batch
    media: Media  # media information
    configs: list[SingleDocumentRecognitionJobCfg]  # list of document recognition configs
