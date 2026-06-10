import pytest
from unittest.mock import patch, MagicMock

from triage_core.client import TriageClient
from triage_core.task_packet import TaskPacket, PrivacyMetadata
from triage_core.privacy_scanner import PrivacyViolationError
from triage_core.safe_task_packet import LocalRouteUnavailableError
from triage_core.routing.resilience_router import ResilienceRouteDecision

@pytest.fixture
def client():
    return TriageClient(backend=MagicMock())

def test_privacy_failed_packet_does_not_call_router(client):
    packet = TaskPacket(
        prompt="Dirty prompt",
        data="SSN 123-45-6789",
        privacy_metadata=PrivacyMetadata(contains_pii=False)
    )
    with patch("triage_core.classifier.TaskClassifier.classify") as mock_classify:
        with pytest.raises(PrivacyViolationError):
            client.run_task(task_packet=packet)
        mock_classify.assert_not_called()

def test_local_only_packet_blocks_remote_route(client):
    packet = TaskPacket(
        prompt="Sensitive prompt",
        data="Sensitive data",
        privacy_metadata=PrivacyMetadata(contains_pii=True) # local-only
    )
    with patch("triage_core.classifier.TaskClassifier.classify", return_value="general"):
        # Even if router were to mistakenly pick cloud_primary, the fail-closed logic stops it
        decision = ResilienceRouteDecision(
            selected_route="cloud_primary", reason="", fallback_depth=0, human_review_required=False
        )
        with patch("triage_core.client.choose_resilience_route", return_value=decision):
            with pytest.raises(LocalRouteUnavailableError, match="is not proven local-safe"):
                client.run_task(task_packet=packet)

def test_local_only_packet_allows_explicit_local_route(client):
    packet = TaskPacket(
        prompt="Sensitive prompt",
        data="Sensitive data",
        privacy_metadata=PrivacyMetadata(contains_pii=True) # local-only
    )
    with patch("triage_core.classifier.TaskClassifier.classify", return_value="general"):
        decision = ResilienceRouteDecision(
            selected_route="local_heavy", reason="", fallback_depth=0, human_review_required=False
        )
        with patch("triage_core.client.choose_resilience_route", return_value=decision):
            with patch("triage_core.project_steward.ProjectSteward.evaluate", return_value={"local_result_status": "sufficient"}):
                with patch.object(client.engine, "execute_task", return_value={"status": "success", "output": "ok"}):
                    # Should pass without LocalRouteUnavailableError
                    result = client.run_task(task_packet=packet)
                    assert result["status"] == "success"

def test_unknown_or_ambiguous_route_fails_closed(client):
    packet = TaskPacket(
        prompt="Sensitive prompt",
        data="Sensitive data",
        privacy_metadata=PrivacyMetadata(contains_pii=True) # local-only
    )
    with patch("triage_core.classifier.TaskClassifier.classify", return_value="general"):
        # "human_handoff" is an ambiguous/non-local-executable route.
        decision = ResilienceRouteDecision(
            selected_route="human_handoff", reason="", fallback_depth=0, human_review_required=False
        )
        with patch("triage_core.client.choose_resilience_route", return_value=decision):
            with pytest.raises(LocalRouteUnavailableError, match="is not proven local-safe"):
                client.run_task(task_packet=packet)

def test_local_only_packet_offload_recommended_fails_closed(client):
    packet = TaskPacket(
        prompt="Sensitive prompt",
        data="Sensitive data",
        privacy_metadata=PrivacyMetadata(contains_pii=True) # local-only
    )
    with patch("triage_core.classifier.TaskClassifier.classify", return_value="general"):
        decision = ResilienceRouteDecision(
            selected_route="local_heavy", reason="", fallback_depth=0, human_review_required=False
        )
        with patch("triage_core.client.choose_resilience_route", return_value=decision):
            # If specialist router recommends offload
            with patch.object(client.router.specialist, "route_task", return_value={"offload_recommended": True}):
                with pytest.raises(LocalRouteUnavailableError, match="Specialist router recommended offload"):
                    client.run_task(task_packet=packet)

def test_normal_privacy_passing_non_local_packet_still_routes(client):
    packet = TaskPacket(
        prompt="Public code",
        data="Public data",
        privacy_metadata=PrivacyMetadata(
            contains_pii=False,
            contains_sensitive_content=False,
            contains_precise_location=False,
            redaction_required=False,
            external_model_allowed=True,
            data_class="public"
        ) # External Safe
    )
    with patch("triage_core.classifier.TaskClassifier.classify", return_value="general"):
        decision = ResilienceRouteDecision(
            selected_route="cloud_primary", reason="", fallback_depth=0, human_review_required=False
        )
        with patch("triage_core.client.choose_resilience_route", return_value=decision):
            # For a normal external safe packet, offload recommended just returns a handoff response
            with patch.object(client.router.specialist, "route_task", return_value={"offload_recommended": True}):
                result = client.run_task(task_packet=packet)
                assert result["status"] == "handoff_required"
                assert result["selected_route"] == "cloud_primary"
