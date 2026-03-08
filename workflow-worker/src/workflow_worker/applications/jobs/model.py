from enum import IntEnum, StrEnum

from pydantic import BaseModel

from workflow_worker.domain.entities.tasks.banned_word_detection.result import BannedWordDetectionJobResult
from workflow_worker.domain.entities.tasks.person_tracking.result import PersonTrackingJobResult
from workflow_worker.domain.entities.tasks.script_matching.result import ScriptMatchingJobResult


class JobName(StrEnum):
    """Enumeration of all job names."""
    PersonTracking = "person_tracking"
    ScriptMatching = "script_matching"
    BannedWordDetection = "banned_word_detection"
    SpeechRecognition = "speech_recognition"
    SubtitleMatching = "subtitle_matching"
    CardRecognition = "card_recognition"
    SignatureRecognition = "signature_recognition"
    DocumentRecognition = "document_recognition"


class TaskResultCategory(IntEnum):
    """Enumeration of task result categories."""
    Empty = 0
    PersonTracking = 1
    ScriptMatching = 2
    BannedWordDetection = 3
    RuleTypeTest = 100


class TaskResult(BaseModel):
    """Model representing task results."""
    category: TaskResultCategory = TaskResultCategory.Empty  # default is empty
    person_tracking: PersonTrackingJobResult | None = None
    script_matching: ScriptMatchingJobResult | None = None
    banned_word_detection: BannedWordDetectionJobResult | None = None
    rule_type_test: list[str | None] = []


class TaskEvent(BaseModel):
    """Model representing task events."""
    pass
