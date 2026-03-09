"""Basic smoke tests for settings loading."""
from workflow_ai.config import settings


def test_defaults():
    assert settings.asr_endpoint.endswith(":50100")
    assert settings.detection_endpoint.endswith(":50101")
    assert settings.max_workers > 0
