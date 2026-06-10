import pytest
from unittest.mock import patch, MagicMock

from triage_core.task_packet import TaskPacket, PrivacyMetadata
from triage_core.privacy_scanner import scan_task_packet, PrivacyViolationError
from triage_core.client import TriageClient

def test_clean_public_packet_passes():
    packet = TaskPacket(
        prompt="Write a hello world program.",
        data="Nothing special here.",
        privacy_metadata=PrivacyMetadata()
    )
    report = scan_task_packet(packet)
    assert report.passed is True
    assert len(report.violations) == 0

def test_ssn_like_with_public_metadata_fails():
    packet = TaskPacket(
        prompt="Process this record.",
        data="The ID is 123-45-6789.",
        privacy_metadata=PrivacyMetadata(contains_pii=False)
    )
    report = scan_task_packet(packet)
    assert report.passed is False
    assert any("SSN pattern" in v for v in report.violations)
    assert "123-45-6789" not in report.violations[0]

def test_valid_cc_like_with_public_metadata_fails():
    # 4111111111111111 is a valid Luhn (Visa test card)
    packet = TaskPacket(
        prompt="Process payment.",
        data="Card is 4111111111111111.",
        privacy_metadata=PrivacyMetadata(contains_pii=False)
    )
    report = scan_task_packet(packet)
    assert report.passed is False
    assert any("credit card" in v for v in report.violations)

def test_sensitive_keyword_with_public_metadata_fails():
    packet = TaskPacket(
        prompt="Review this document.",
        data="This is CONFIDENTIAL.",
        privacy_metadata=PrivacyMetadata(data_class="public", contains_sensitive_content=False)
    )
    report = scan_task_packet(packet)
    assert report.passed is False
    assert any("sensitive keyword" in v for v in report.violations)

def test_secret_api_key_with_public_metadata_fails():
    packet = TaskPacket(
        prompt="Deploy code.",
        data="token=ABC123XYZ890",
        privacy_metadata=PrivacyMetadata(contains_sensitive_content=False)
    )
    report = scan_task_packet(packet)
    assert report.passed is False
    assert any("secret or API key" in v for v in report.violations)

def test_precise_coordinate_with_public_metadata_fails():
    packet = TaskPacket(
        prompt="Find restaurants.",
        data="Location: 37.7749, -122.4194",
        privacy_metadata=PrivacyMetadata(contains_precise_location=False)
    )
    report = scan_task_packet(packet)
    assert report.passed is False
    assert any("precise coordinate" in v for v in report.violations)

def test_detected_pii_with_accurate_metadata_passes():
    packet = TaskPacket(
        prompt="Process this record.",
        data="The ID is 123-45-6789.",
        privacy_metadata=PrivacyMetadata(contains_pii=True)
    )
    report = scan_task_packet(packet)
    assert report.passed is True

def test_detected_sensitive_with_accurate_metadata_passes():
    packet = TaskPacket(
        prompt="Deploy code.",
        data="token=ABC123XYZ890",
        privacy_metadata=PrivacyMetadata(contains_sensitive_content=True)
    )
    report = scan_task_packet(packet)
    assert report.passed is True

def test_integration_run_task_raises_error_before_router():
    # Provide dirty data via legacy prompt/data params.
    # TriageClient should wrap it in a default public TaskPacket and fail closed.
    client = TriageClient(backend=MagicMock())
    
    with patch("triage_core.classifier.TaskClassifier.classify") as mock_classify:
        with pytest.raises(PrivacyViolationError) as exc_info:
            client.run_task(
                prompt="Check this code",
                data="api_key=sk-1234567890abcdef1234567890abcdef"
            )
        
        # Router/classifier was NOT called
        mock_classify.assert_not_called()
        assert "Privacy scan failed" in str(exc_info.value)
        assert "secret or API key pattern" in str(exc_info.value)

def test_email_pattern_with_public_metadata_fails():
    packet = TaskPacket(
        prompt="Contact user",
        data="Email: user@example.com",
        privacy_metadata=PrivacyMetadata(contains_pii=False)
    )
    report = scan_task_packet(packet)
    assert report.passed is False
    assert any("email address" in v for v in report.violations)

def test_phone_pattern_with_public_metadata_fails():
    packet = TaskPacket(
        prompt="Call user",
        data="Phone: +1 555-019-8472",
        privacy_metadata=PrivacyMetadata(contains_pii=False)
    )
    report = scan_task_packet(packet)
    assert report.passed is False
    assert any("phone number" in v for v in report.violations)

def test_email_phone_content_with_accurate_metadata_passes():
    packet = TaskPacket(
        prompt="Contact user",
        data="Email: user@example.com, Phone: +1 555-019-8472",
        privacy_metadata=PrivacyMetadata(contains_pii=True)
    )
    report = scan_task_packet(packet)
    assert report.passed is True

def test_sanitized_messages_no_raw_data_leak():
    secret_value = "token=ABC123XYZ890"
    coord_value = "37.7749, -122.4194"
    packet = TaskPacket(
        prompt="Deploy code.",
        data=f"{secret_value} at {coord_value}",
        privacy_metadata=PrivacyMetadata(contains_sensitive_content=False, contains_precise_location=False)
    )
    report = scan_task_packet(packet)
    assert report.passed is False
    
    # Assert raw values do not appear in any violation
    for violation in report.violations:
        assert secret_value not in violation
        assert "ABC123XYZ890" not in violation
        assert coord_value not in violation
        assert "37.7749" not in violation
        
    # Also test that PrivacyViolationError doesn't leak them
    client = TriageClient(backend=MagicMock())
    with patch("triage_core.classifier.TaskClassifier.classify"):
        with pytest.raises(PrivacyViolationError) as exc_info:
            client.run_task(task_packet=packet)
        err_msg = str(exc_info.value)
        assert secret_value not in err_msg
        assert "ABC123XYZ890" not in err_msg
        assert coord_value not in err_msg
        assert "37.7749" not in err_msg
