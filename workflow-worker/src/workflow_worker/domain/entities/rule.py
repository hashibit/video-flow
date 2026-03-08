
from pydantic import BaseModel

from workflow_worker.domain.entities.common.time_patch import TimePatch


class EngineCfg(BaseModel):
    """Engine configuration."""

    fps: float
    min_time_interval: float


class ScriptCfg(BaseModel):
    """Script compliance check rule point configuration."""

    require_jobs: list[str] = ["script_matching"]
    script: str
    script_threshold: float
    key_words: list[str | None] = []
    key_word_threshold: float | None = 0.4
    answer_flag: bool | None = False


class FieldInfo(BaseModel):
    """Field-level data for identity verification."""

    field_num: int
    field_key: str
    field_text_threshold: float


class VerificationCfg(BaseModel):
    """Identity verification rule point configuration."""

    required_jobs: list[str] = []
    card_display_duration: float  # reserved, not used yet
    card_detection_threshold: float
    card_type: str
    card_content_flag: bool
    field_infos: list[FieldInfo | None] = []


class SignatureInfo(BaseModel):
    """Signature field configuration."""

    signer_role: str  # role of the signer
    signer_threshold: float  # role detection threshold
    signature_flag: bool  # whether to enable signature detection
    signature_detection_flag: bool  # whether to detect signatures
    signature_content_type: str  # category of signature content
    signature_threshold: float  # recognition threshold
    signing_action_flag: bool  # whether to detect signing action
    signing_action_threshold: float  # signing action detection threshold


class DocumentCfg(BaseModel):
    """Document detection rule point configuration."""

    require_jobs: list[str] = []
    document_name: str
    document_display_duration: float
    document_detection_threshold: float
    document_title: str
    document_title_threshold: float
    signature_infos: list[SignatureInfo | None] = []  # one or more signatures


class SameFrameCfg(BaseModel):
    """Co-occurrence (same-frame) statistics rule point configuration."""

    fps: int
    min_time_interval: int
    require_jobs: list[str] = ["person_tracking"]
    ratio: float
    lost_warning_threshold: float
    num_of_people: int
    stranger_warning_flag: bool
    face_verification_threshold: float
    cumulative_number: int


class BanwordCfg(BaseModel):
    """Banned word detection rule point configuration."""

    require_jobs: list[str] = ["banned_word_detection"]
    banwords: list[str | None] = []
    banword_group_id: int
    require_words: list[str | None] = []


class SubtitleText(BaseModel):
    text_index: int
    text: str
    threshold: float
    time_patchs: list[TimePatch | None] = []
    time_range_type: int  # 0=full video, 1=video segment
    emergency_type: int  # 0=always present, 1=at least once
    text_type: int  # 0=full display, 1=partial display; OCR detection uses 0, subtitle uses 1
    min_text_number: int | None = -1  # minimum character count requirement
    cumulative_threshold: float | None = -1  # cumulative display ratio
    continuous_appearance_times: int  # continuous appearance duration in seconds


class SubtitleCfg(BaseModel):
    require_jobs: list[str] = ["subtitle_matching"]
    fps: float
    texts: list[SubtitleText]


class RulePoint(BaseModel):
    """Individual inspection rule point entity."""

    id: int  # rule point id
    name: str  # rule point name
    category: str  # rule point category, e.g. "banword" / "subtitle_match"
    script_cfg: ScriptCfg | None  # script compliance check config
    banword_cfg: BanwordCfg | None  # banned word detection config
    subtitle_cfg: SubtitleCfg | None  # subtitle / on-screen text config

    biz_category: int
    temporal_scope_category: int
    verification_cfgs: list[VerificationCfg | None]  # identity verification configs
    document_cfgs: list[DocumentCfg | None]  # document detection configs
    same_frame_cfg: SameFrameCfg | None  # co-occurrence statistics config


class RuleSection(BaseModel):
    """A section grouping one or more rule points."""

    id: int  # rule section id
    name: str  # rule section name
    type: int  # rule section category
    rule_points: list[RulePoint | None] = []

    biz_category: int
    temporal_scope_category: int


class Scenario(BaseModel):
    """Inspection scenario containing multiple rule sections."""

    id: int
    name: str  # scenario name
    rule_sections: list[RuleSection] = []


class Rule(BaseModel):
    """Top-level inspection rule for a task."""

    name: str
    # engine_cfg: EngineCfg
    fps: float
    min_time_interval: float
    rule_sections: list[RuleSection] = []
    biz_category: int
    product_id: str | None = ""
