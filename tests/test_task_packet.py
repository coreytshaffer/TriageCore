import pytest
from triage_core.task_packet import TaskPacket, PrivacyMetadata

def test_privacy_metadata_defaults():
    metadata = PrivacyMetadata()
    assert metadata.data_class == "public"
    assert metadata.contains_pii is False
    assert metadata.contains_sensitive_content is False
    assert metadata.contains_precise_location is False
    assert metadata.external_model_allowed is True
    assert metadata.retention_policy == "default"
    assert metadata.redaction_required is False

def test_task_packet_creates_default_metadata():
    packet = TaskPacket(prompt="Hello", data="World")
    assert isinstance(packet.privacy_metadata, PrivacyMetadata)
    assert packet.privacy_metadata.data_class == "public"
    assert packet.privacy_metadata.external_model_allowed is True

def test_task_packet_accepts_explicit_metadata():
    custom_metadata = PrivacyMetadata(
        data_class="restricted",
        contains_pii=True,
        external_model_allowed=False,
        redaction_required=True
    )
    packet = TaskPacket(
        prompt="Analyze user",
        data="Name: Alice",
        privacy_metadata=custom_metadata
    )
    assert packet.privacy_metadata.data_class == "restricted"
    assert packet.privacy_metadata.contains_pii is True
    assert packet.privacy_metadata.external_model_allowed is False
    assert packet.privacy_metadata.redaction_required is True
