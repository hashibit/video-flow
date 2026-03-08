
from pydantic import BaseModel

from workflow_worker.domain.entities.frame import Frame
from workflow_worker.domain.entities.task import Media


class SinglePersonTrackingJobCfg(BaseModel):
    """Same frame statistics task configuration entity"""

    id: int
    frame_infos: dict[str, Frame | None]  # Mapping list of {time: frame}, for compatibility
    fps: float  # Frame extraction frequency
    min_time_interval: float  # Tracking time interval, will split into two tracking segments if greater than this value
    batch_size: int  # Maximum frames per extraction
    verification_threshold: float  # Face recognition threshold
    lost_warning_threshold: float  # Lost warning duration threshold
    cumulative_number: int  # Cumulative number of people appearing
    stranger_warning_flag: bool  # Stranger warning flag
    num_of_people: int  # Maximum number of people in same frame
    ratio: float  # Same frame duration ratio


class PersonTrackingJobCfg(BaseModel):
    """Same frame statistics task configuration entity with media related information"""

    id: int
    media: Media
    configs: list[SinglePersonTrackingJobCfg]
