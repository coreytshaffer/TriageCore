from datetime import datetime, timezone

import pytest
from unittest.mock import patch, MagicMock

from triage_core.client import TriageClient
from triage_core.task_packet import TaskPacket, PrivacyMetadata
from triage_core.privacy_scanner import PrivacyViolationError
from triage_core.safe_task_packet import LocalRouteUnavailableError
from triage_core.routing.resilience_router import ResilienceRouteDecision
from triage_core import capability_evidence as cap
from triage_core.local_backend_probe import LocalBackendProbeRecord

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

# --- CR-DD-017: blocked local-only route evidence parity -------------------

def test_sensitivity_blocked_route_records_route_decision(client, ledger):
    """Real choose_resilience_route: usable local capability + high sensitivity
    resolves to human_handoff via sensitivity_requires_human_review, and that
    cause is persisted on the route_decision event before the raise."""
    packet = TaskPacket(
        task_id="task-128",
        prompt="Sensitive prompt",
        data="Sensitive data",
        privacy_metadata=PrivacyMetadata(contains_pii=True)
    )
    with patch("triage_core.classifier.TaskClassifier.classify", return_value="security_review"):
        with pytest.raises(LocalRouteUnavailableError):
            client.run_task(task_packet=packet, ledger=ledger)

    assert [e for e, _ in ledger.events] == ["route_audit", "route_decision"]
    audit = ledger.events[0][1]
    decision = ledger.events[1][1]

    assert audit["decision"] == "blocked"
    assert audit["reason_code"] == "ambiguous_or_remote_route"
    assert decision["selected_route"] == "human_handoff"
    assert decision["reason"] == "sensitivity_requires_human_review"


def _observed_unavailable_capability():
    now = datetime(2026, 8, 11, 12, 0, 0, tzinfo=timezone.utc)
    record = LocalBackendProbeRecord(
        source_type="lm_studio",
        base_url="http://localhost:1234",
        reachable=False,
        evidence_tier="operator_recorded",
        error_category="endpoint_unreachable",
        observed_at=now.isoformat(),
    )
    return cap.resolve_capability(
        record=record,
        declare_local_fast=True,
        declare_local_heavy=True,
        config_reference="test:[capability]",
        now=now,
        freshness_seconds=300,
        local_fast_model="qwen2.5-coder:7b-triagecore",
        local_heavy_model="deepseek-r1:latest",
    )


def _unknown_capability():
    return cap.resolve_capability(
        record=None,
        declare_local_fast=False,
        declare_local_heavy=False,
        config_reference="test:[capability]",
        freshness_seconds=300,
    )


@pytest.mark.parametrize(
    "capability, expected_capability_state",
    [
        pytest.param(_unknown_capability(), "unknown", id="unknown"),
        pytest.param(_observed_unavailable_capability(), "observed_unavailable", id="observed_unavailable"),
    ],
)
def test_capability_exhaustion_blocked_route_records_capability_state(
    client, ledger, capability, expected_capability_state
):
    """Real choose_resilience_route: normal sensitivity + no usable local
    capability resolves to human_handoff via no_reliable_automated_route_available
    for both Unknown and ObservedUnavailable capability evidence, and the
    route_decision payload distinguishes which one actually occurred."""
    packet = TaskPacket(
        task_id="task-129",
        prompt="Sensitive prompt",
        data="Sensitive data",
        privacy_metadata=PrivacyMetadata(contains_pii=True)
    )
    with patch("triage_core.classifier.TaskClassifier.classify", return_value="general"):
        with pytest.raises(LocalRouteUnavailableError):
            client.run_task(task_packet=packet, ledger=ledger, capability=capability)

    assert [e for e, _ in ledger.events] == ["route_audit", "route_decision"]
    audit = ledger.events[0][1]
    decision = ledger.events[1][1]

    assert audit["decision"] == "blocked"
    assert audit["reason_code"] == "ambiguous_or_remote_route"
    assert decision["selected_route"] == "human_handoff"
    assert decision["reason"] == "no_reliable_automated_route_available"
    assert decision["capability_state"] == expected_capability_state


def test_blocked_route_evidence_persistence_failure_propagates_without_worker(client, ledger):
    """An evidence-persistence/signing failure on the blocked branch must not be
    masked as LocalRouteUnavailableError, must not synthesize a worker_result,
    and must not fall through to an allowed route (Invariant 3)."""
    packet = TaskPacket(
        task_id="task-130",
        prompt="Sensitive prompt",
        data="Sensitive data",
        privacy_metadata=PrivacyMetadata(contains_pii=True)
    )
    decision = ResilienceRouteDecision(
        selected_route="human_handoff", reason="no_reliable_automated_route_available",
        fallback_depth=0, human_review_required=True
    )
    with patch("triage_core.classifier.TaskClassifier.classify", return_value="general"):
        with patch("triage_core.client.choose_resilience_route", return_value=decision):
            with patch.object(
                TriageClient,
                "_append_route_decision_event",
                side_effect=RuntimeError("ledger evidence persistence failed"),
            ):
                with pytest.raises(RuntimeError):
                    client.run_task(task_packet=packet, ledger=ledger)

    assert [e for e, _ in ledger.events] == ["route_audit"]
    assert ledger.events[0][1]["reason_code"] == "ambiguous_or_remote_route"
