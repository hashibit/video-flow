
from pydantic import BaseModel

from workflow_worker.domain.entities.common.time_patch import TimePatch
from workflow_worker.domain.entities.frame import Frame


class PersonTrackingResult(BaseModel):
    """Tracking result for a single person returned by the tracking service."""

    id: int  # unused for now

    time_patchs: list[TimePatch]  # time segments in which the person appears in the video
    tracking_id: str  # tracking id, unique across all tracked persons
    frame: Frame  # best representative frame
    bbox: list[int]  # face bounding box
