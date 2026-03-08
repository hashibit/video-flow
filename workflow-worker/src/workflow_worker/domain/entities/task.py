
from pydantic import BaseModel

from workflow_worker.domain.entities.rule import Rule, Scenario


class Card(BaseModel):
    """ID card"""

    category: str  # Card type
    number: str  # Card number of the card holder
    name: str  # Name of the card holder


class Participant(BaseModel):
    """Participant"""

    name: str | None
    role: str | None
    requirement: str | None
    picture: str | None
    cards: list[Card | None]


class MediaMeta(BaseModel):
    """Media metadata"""

    resolution: str | None
    size: str | None
    duration: float | None
    bitrate: str | None
    fps: str | None
    width: int | None
    height: int | None
    format_name: str | None


class Media(BaseModel):
    """Media"""

    path: str
    media_url: str  # New field
    has_video: bool | None = False
    has_audio: bool | None = False
    meta: MediaMeta | None

    video_valid_start_time: int | None = 0
    video_valid_end_time: int | None = 0


class Task(BaseModel):
    """Task entity"""
    """This entity needs to be refactored"""

    name: str  # Task name
    id: int  # Task id
    ignore_invalid_time_range: int = 0
    media: Media  # Media object
    scenario: Scenario  # Scenario object
    rule: Rule | None
    participants: list[Participant | None] = []
