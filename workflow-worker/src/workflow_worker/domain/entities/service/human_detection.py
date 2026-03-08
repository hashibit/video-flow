
from pydantic import BaseModel

from workflow_worker.domain.entities.human import Body, Face


class HumanDetectionServiceResult(BaseModel):
    """Result returned by the human body detection service."""

    face_infos: list[Face]  # with score & face_bbox
    body_infos: list[Body]  # with confidence & body_bbox
