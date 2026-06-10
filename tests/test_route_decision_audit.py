import pytest
from unittest.mock import patch, MagicMock

from triage_core.client import TriageClient
from triage_core.task_packet import TaskPacket, PrivacyMetadata
from triage_core.privacy_scanner import PrivacyViolationError
from triage_core.safe_task_packet import LocalRouteUnavailableError
from triage_core.routing.resilience_router import ResilienceRouteDecision

@pytest.fixture
def ledger():
    mock = MagicMock()
    # Track the events added
    mock.events = []
    def mock_append(task_id, event_type, payload):
        mock.events.append((event_type, payload))
    mock.append_event = mock_append
    return mock

@pytest.fixture
def client():
    return TriageClient(backend=MagicMock(name="fake"))

def test_privacy_failed_packet_audit(client, ledger):
    packet = TaskPacket(
        task_id="task-123",
        prompt="Dirty prompt",
        data="SSN 123-45-6789",
        privacy_metadata=PrivacyMetadata(contains_pii=False)
    )
    with pytest.raises(PrivacyViolationError):
        client.run_task(task_packet=packet, ledger=ledger)
        
    audit_events = [p for e, p in ledger.events if e == "route_audit"]
    assert len(audit_events) == 1
    audit = audit_events[0]
    
    assert audit["decision"] == "blocked"
    assert audit["reason_code"] == "privacy_violation"
    assert audit["privacy_scan_passed"] is False
    assert "prompt" not in audit
    assert "data" not in audit
    assert "SSN" not in str(audit)

def test_local_only_remote_route_blocked_audit(client, ledger):
    packet = TaskPacket(
        task_id="task-124",
        prompt="Sensitive prompt",
        data="Sensitive data",
        privacy_metadata=PrivacyMetadata(contains_pii=True)
    )
    decision = ResilienceRouteDecision(
        selected_route="cloud_primary", reason="", fallback_depth=0, human_review_required=False
    )
    with patch("triage_core.classifier.TaskClassifier.classify", return_value="general"):
        with patch("triage_core.client.choose_resilience_route", return_value=decision):
            with pytest.raises(LocalRouteUnavailableError):
                client.run_task(task_packet=packet, ledger=ledger)
                
    audit_events = [p for e, p in ledger.events if e == "route_audit"]
    assert len(audit_events) == 1
    audit = audit_events[0]
    
    assert audit["decision"] == "blocked"
    assert audit["reason_code"] == "ambiguous_or_remote_route"
    assert audit["is_local_only"] is True
    assert "prompt" not in audit
    assert "Sensitive data" not in str(audit)

def test_local_only_explicit_local_route_allowed_audit(client, ledger):
    packet = TaskPacket(
        task_id="task-125",
        prompt="Sensitive prompt",
        data="Sensitive data",
        privacy_metadata=PrivacyMetadata(contains_pii=True)
    )
    decision = ResilienceRouteDecision(
        selected_route="local_heavy", reason="", fallback_depth=0, human_review_required=False
    )
    with patch("triage_core.classifier.TaskClassifier.classify", return_value="general"):
        with patch("triage_core.client.choose_resilience_route", return_value=decision):
            with patch("triage_core.project_steward.ProjectSteward.evaluate", return_value={"local_result_status": "sufficient"}):
                with patch.object(client.engine, "execute_task", return_value={"status": "success", "output": "ok"}):
                    client.run_task(task_packet=packet, ledger=ledger)
                    
    audit_events = [p for e, p in ledger.events if e == "route_audit"]
    assert len(audit_events) == 1
    audit = audit_events[0]
    
    assert audit["decision"] == "allowed"
    assert audit["reason_code"] == "route_allowed"
    assert audit["is_local_only"] is True
    assert audit["recommended_route"] == "local_heavy"
    assert "prompt" not in audit

def test_ambiguous_route_blocked_audit(client, ledger):
    packet = TaskPacket(
        task_id="task-126",
        prompt="Sensitive prompt",
        data="Sensitive data",
        privacy_metadata=PrivacyMetadata(contains_pii=True)
    )
    decision = ResilienceRouteDecision(
        selected_route="human_handoff", reason="", fallback_depth=0, human_review_required=False
    )
    with patch("triage_core.classifier.TaskClassifier.classify", return_value="general"):
        with patch("triage_core.client.choose_resilience_route", return_value=decision):
            with pytest.raises(LocalRouteUnavailableError):
                client.run_task(task_packet=packet, ledger=ledger)
                
    audit_events = [p for e, p in ledger.events if e == "route_audit"]
    assert len(audit_events) == 1
    audit = audit_events[0]
    
    assert audit["decision"] == "blocked"
    assert audit["reason_code"] == "ambiguous_or_remote_route"
    assert "prompt" not in audit

def test_normal_non_sensitive_routing_audit(client, ledger):
    packet = TaskPacket(
        task_id="task-127",
        prompt="Public code",
        data="Public data",
        privacy_metadata=PrivacyMetadata(
            contains_pii=False,
            contains_sensitive_content=False,
            contains_precise_location=False,
            redaction_required=False,
            external_model_allowed=True,
            data_class="public"
        )
    )
    decision = ResilienceRouteDecision(
        selected_route="cloud_primary", reason="", fallback_depth=0, human_review_required=False
    )
    with patch("triage_core.classifier.TaskClassifier.classify", return_value="general"):
        with patch("triage_core.client.choose_resilience_route", return_value=decision):
            with patch.object(client.router.specialist, "route_task", return_value={"offload_recommended": True}):
                client.run_task(task_packet=packet, ledger=ledger)
                
    audit_events = [p for e, p in ledger.events if e == "route_audit"]
    assert len(audit_events) == 1
    audit = audit_events[0]
    
    assert audit["decision"] == "allowed"
    assert audit["reason_code"] == "route_allowed"
    assert audit["is_local_only"] is False
    assert audit["privacy_level"] == "external_safe"
    assert audit["recommended_route"] == "cloud_primary"
    assert "prompt" not in audit
    assert "data" not in audit
