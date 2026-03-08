
from pydantic import BaseModel

from workflow_worker.domain.entities.frame import ContinuousFrame
from workflow_worker.domain.entities.tasks.banned_word_detection.report import BannedWordDetectionReport
from workflow_worker.domain.entities.tasks.person_tracking.report import PersonTrackingReport
from workflow_worker.domain.entities.tasks.script_matching.report import ScriptMatchingReport
from workflow_worker.domain.entities.tasks.subtitle_matching.report import SubtitleMatchingReport
from workflow_worker.domain.entities.tasks.subtitle_matching.result import MissResult
from workflow_worker.domain.entities.rule import (
    BanwordCfg,
    DocumentCfg,
    SameFrameCfg,
    ScriptCfg,
    SubtitleCfg,
    VerificationCfg,
)
from workflow_worker.domain.entities.service.auc import AUCServiceResult
from workflow_worker.domain.entities.task import Media


class AiResult(BaseModel):
    auc: AUCServiceResult | None
    subtitle: list[MissResult | None]
    subtitle_continuous_appear: list[ContinuousFrame | None]
    # docs: list[DocumentRecognitionResult]
    # cards: list[CardRecognitionResult]
    # actions: list[ActionRecogResult]
    # signatures: list[SignatureRecognitionResult]


class RulePointReport(BaseModel):
    """Quality inspection item entity"""

    name: str
    id: int
    biz_category: int
    temporal_scope_category: int
    category: str  # Quality inspection item category

    script_match_report: ScriptMatchingReport | None  # Script quality inspection result
    banword_detection_report: BannedWordDetectionReport | None  # Banned word quality inspection result
    person_tracking_report: PersonTrackingReport | None
    subtitle_matching_report: SubtitleMatchingReport | None
    # action_recog_report: ActionRecogReport | None
    # doc_recog_report: DocumentRecognitionJobReport | None
    # card_recog_report: CardRecognitionReport | None
    # sign_recog_report: SignatureRecognitionReport | None

    # keep a copy of rule point
    script_cfg: ScriptCfg | None  # Script quality inspection item
    verification_cfgs: list[VerificationCfg | None]  # Identity verification quality inspection item
    document_cfgs: list[DocumentCfg | None]  # Document detection quality inspection item
    same_frame_cfg: SameFrameCfg | None  # Same frame statistics quality inspection item
    banword_cfg: BanwordCfg | None  # Banned word quality inspection item
    subtitle_cfg: SubtitleCfg | None  # Subtitle/label quality inspection item

    reasons: list[str] = []  # List of reasons for quality inspection failure


class RuleSectionReport(BaseModel):
    """Quality inspection section entity"""

    name: str
    id: int
    rule_point_reports: list[RulePointReport] = []

    status: str = "passed"
    checked_status: str = "passed"

    reasons: list[str] = []


class Report(BaseModel):
    """Report entity"""

    name: str
    id: int
    media: Media
    rule_section_reports: list[RuleSectionReport] = []

    status: str = "passed"
    checked_status: str = "passed"

    reasons: list[list[str]] = []
    ai_result: AiResult
