"""Central configuration for workflow-ai services.

All settings are read from environment variables prefixed with ``WORKFLOW_AI_``.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class GrpcListenSettings(BaseSettings):
    """gRPC listen addresses for each service."""
    model_config = SettingsConfigDict(env_prefix="WORKFLOW_AI_")

    # Listen endpoints (host:port)
    asr_endpoint: str = "0.0.0.0:50100"
    detection_endpoint: str = "0.0.0.0:50101"
    face_feature_endpoint: str = "0.0.0.0:50102"
    ocr_general_endpoint: str = "0.0.0.0:50103"
    ocr_handwriting_endpoint: str = "0.0.0.0:50104"
    ocr_document_endpoint: str = "0.0.0.0:50105"
    ocr_id_card_endpoint: str = "0.0.0.0:50106"

    # gRPC server concurrency
    max_workers: int = 4

    # ASR settings
    asr_model: str = "paraformer-zh"
    asr_device: str = "cpu"

    # Detection model
    detection_model_path: str = "models/detection"
    detection_face_threshold: float = 0.7
    detection_body_threshold: float = 0.7

    # Face feature model
    face_feature_model_path: str = "models/face_feature"
    face_feature_similarity_threshold: float = 0.7

    # OCR settings
    ocr_device: str = "cpu"
    ocr_lang: str = "ch"

    # Logging
    log_level: str = "INFO"
    is_debug: bool = False


settings = GrpcListenSettings()
