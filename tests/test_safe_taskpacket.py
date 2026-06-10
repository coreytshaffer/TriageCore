import pytest
from unittest.mock import patch, MagicMock

from triage_core.task_packet import TaskPacket, PrivacyMetadata
from triage_core.privacy_scanner import PrivacyViolationError, PrivacyReport
from triage_core.safe_task_packet import (
    verify_packet,
    make_external_safe_packet,
    VerifiedTaskPacket,
    ExternalSafeTaskPacket,
    UnsafePacketError
)
from triage_core.client import TriageClient

def test_verify_packet_upgrades_clean_packet():
    packet = TaskPacket(
        prompt="Clean prompt",
        data="Clean data",
        privacy_metadata=PrivacyMetadata()
    )
    verified = verify_packet(packet)
    assert isinstance(verified, VerifiedTaskPacket)
    assert verified.scan_report.passed is True
    assert verified.prompt == "Clean prompt"

def test_verify_packet_raises_on_dirty_packet():
    packet = TaskPacket(
        prompt="Dirty prompt",
        data="SSN is 123-45-6789",
        privacy_metadata=PrivacyMetadata(contains_pii=False)
    )
    with pytest.raises(PrivacyViolationError):
        verify_packet(packet)

def test_make_external_safe_packet_success():
    packet = TaskPacket(
        prompt="Public code",
        data="public data",
        privacy_metadata=PrivacyMetadata(
            contains_pii=False,
            contains_sensitive_content=False,
            contains_precise_location=False,
            redaction_required=False,
            external_model_allowed=True,
            data_class="public"
        )
    )
    verified = verify_packet(packet)
    safe_packet = make_external_safe_packet(verified)
    assert isinstance(safe_packet, ExternalSafeTaskPacket)

def test_make_external_safe_packet_rejects_various_flags():
    # Base clean packet
    def get_clean_verified(mutator_kwargs):
        meta = PrivacyMetadata(**mutator_kwargs)
        # Create a manually verified packet because passing PII via scan with contains_pii=True works, 
        # but here we just want to test the safe packet factory flags directly
        packet = TaskPacket(prompt="test", data="test", privacy_metadata=meta)
        report = PrivacyReport(passed=True, violations=[])
        return VerifiedTaskPacket(
            prompt="test", data="test", task_id=None, validator=None, privacy_metadata=meta, scan_report=report
        )

    # 1. contains_pii = True
    v_pii = get_clean_verified({"contains_pii": True})
    with pytest.raises(UnsafePacketError, match="contains PII"):
        make_external_safe_packet(v_pii)

    # 2. contains_sensitive_content = True
    v_sens = get_clean_verified({"contains_sensitive_content": True})
    with pytest.raises(UnsafePacketError, match="contains sensitive content"):
        make_external_safe_packet(v_sens)

    # 3. contains_precise_location = True
    v_loc = get_clean_verified({"contains_precise_location": True})
    with pytest.raises(UnsafePacketError, match="contains precise location"):
        make_external_safe_packet(v_loc)

    # 4. redaction_required = True
    v_red = get_clean_verified({"redaction_required": True})
    with pytest.raises(UnsafePacketError, match="redaction required"):
        make_external_safe_packet(v_red)

    # 5. external_model_allowed = False
    v_ext = get_clean_verified({"external_model_allowed": False})
    with pytest.raises(UnsafePacketError, match="external models not allowed"):
        make_external_safe_packet(v_ext)

    # 6. data_class != public
    v_class = get_clean_verified({"data_class": "confidential"})
    with pytest.raises(UnsafePacketError, match="data_class is 'confidential'"):
        make_external_safe_packet(v_class)

    # 7. Scan didn't pass
    v_fail = get_clean_verified({})
    v_fail.scan_report = PrivacyReport(passed=False, violations=["Test violation"])
    with pytest.raises(UnsafePacketError, match="scan report did not pass"):
        make_external_safe_packet(v_fail)

def test_client_verifies_before_routing_and_legacy_callers_work():
    client = TriageClient(backend=MagicMock())
    
    # 1. Legacy string callers still work and are verified correctly
    # By mocking classify to raise an exception, we prove it passed the verify_packet guard successfully
    with patch("triage_core.classifier.TaskClassifier.classify", side_effect=RuntimeError("stop")):
        with pytest.raises(RuntimeError, match="stop"):
            client.run_task(prompt="Hello", data="World")
                
def test_raw_taskpacket_cannot_cross_boundary():
    # If someone tries to pass a TaskPacket directly, verify_packet will upgrade it.
    # What if they mock verify_packet to return a raw TaskPacket?
    client = TriageClient(backend=MagicMock())
    
    packet = TaskPacket(prompt="test", data="test")
    
    with patch("triage_core.safe_task_packet.verify_packet", return_value=packet):
        with pytest.raises(UnsafePacketError, match="Only VerifiedTaskPacket may enter routing boundary"):
            client.run_task(task_packet=packet)
