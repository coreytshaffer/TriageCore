from unittest.mock import MagicMock, patch

import pytest

from triage_core.backends import BackendResponse
from triage_core.client import TriageClient
from triage_core.routing.resilience_router import ResilienceRouteDecision
from triage_core.safe_task_packet import LocalRouteUnavailableError
from triage_core.task_packet import PrivacyMetadata, TaskPacket


class RecordingBackend:
    name = "fake"
    base_url = "http://localhost"
    model = "fake-model"

    def __init__(self) -> None:
        self.called = False

    def generate(self, messages, temperature=0.1, timeout=45, **kwargs):
        self.called = True
        return BackendResponse(
            text="LOCAL_RAN",
            raw={},
            usage={"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            backend_name=self.name,
        )


class RecordingQwenBackend:
    name = "qwen"
    base_url = "https://qwen.example/v1"
    model = "qwen-test"

    def __init__(self) -> None:
        self.called = False
        self.last_messages = None

    def generate(self, messages, temperature=0.1, timeout=45, **kwargs):
        self.called = True
        self.last_messages = messages
        return BackendResponse(
            text="QWEN_RAN",
            raw={},
            usage={"prompt_tokens": 7, "completion_tokens": 4, "total_tokens": 11},
            backend_name=self.name,
        )


@pytest.fixture
def ledger():
    mock = MagicMock()
    mock.events = []

    def append_event(task_id, event_type, payload):
        mock.events.append((event_type, payload))

    mock.append_event = append_event
    return mock


def test_external_safe_cloud_route_runs_qwen_and_emits_allowed_audit(ledger):
    local_backend = RecordingBackend()
    qwen_backend = RecordingQwenBackend()
    client = TriageClient(backend=local_backend)
    packet = TaskPacket(
        task_id="task-qwen-allowed",
        prompt="Plan a public hackathon demo architecture.",
        data="Only public repo facts.",
        privacy_metadata=PrivacyMetadata(
            contains_pii=False,
            contains_sensitive_content=False,
            contains_precise_location=False,
            external_model_allowed=True,
            data_class="public",
        ),
    )
    decision = ResilienceRouteDecision(
        selected_route="cloud_primary",
        reason="explicit_qwen_demo_route",
        fallback_depth=0,
        human_review_required=False,
    )

    with patch("triage_core.classifier.TaskClassifier.classify", return_value="architecture_planning"):
        with patch.object(client.router.specialist, "route_task", return_value={"offload_recommended": False}):
            with patch("triage_core.client.choose_resilience_route", return_value=decision):
                with patch("triage_core.client.create_backend", return_value=qwen_backend):
                    with patch("triage_core.client.default_config.get_qwen_enabled", return_value=True):
                        with patch("triage_core.client.default_config.get_qwen_api_key", return_value="qwen-key"):
                            with patch("triage_core.client.default_config.get_qwen_base_url", return_value="https://qwen.example/v1"):
                                with patch("triage_core.client.default_config.get_qwen_model", return_value="qwen-test"):
                                    with patch("triage_core.project_steward.ProjectSteward.evaluate", return_value={"local_result_status": "sufficient"}):
                                        result = client.run_task(task_packet=packet, ledger=ledger)

    assert result["status"] == "success"
    assert result["source"] == "cloud"
    assert result["backend_name"] == "qwen"
    assert result["output"] == "QWEN_RAN"
    assert local_backend.called is False
    assert qwen_backend.called is True

    audit_events = [payload for event_type, payload in ledger.events if event_type == "route_audit"]
    assert len(audit_events) == 1
    audit = audit_events[0]
    assert audit["decision"] == "allowed"
    assert audit["selected_backend"] == "qwen"
    assert audit["privacy_level"] == "external_safe"
    assert "prompt" not in audit
    assert "data" not in audit


def test_local_only_packet_never_invokes_qwen_adapter():
    client = TriageClient(backend=RecordingBackend())
    packet = TaskPacket(
        task_id="task-qwen-blocked",
        prompt="Sensitive prompt",
        data="Sensitive data",
        privacy_metadata=PrivacyMetadata(contains_pii=True),
    )
    decision = ResilienceRouteDecision(
        selected_route="cloud_primary",
        reason="forced_remote_route",
        fallback_depth=0,
        human_review_required=False,
    )

    with patch("triage_core.classifier.TaskClassifier.classify", return_value="general"):
        with patch("triage_core.client.choose_resilience_route", return_value=decision):
            with patch("triage_core.client.create_backend") as mock_create_backend:
                with pytest.raises(LocalRouteUnavailableError):
                    client.run_task(task_packet=packet)

    mock_create_backend.assert_not_called()


def test_cloud_route_missing_credentials_fails_gracefully():
    client = TriageClient(backend=RecordingBackend())
    packet = TaskPacket(
        task_id="task-qwen-missing-creds",
        prompt="Plan a public architecture memo.",
        data="Public repo information only.",
        privacy_metadata=PrivacyMetadata(
            contains_pii=False,
            contains_sensitive_content=False,
            contains_precise_location=False,
            external_model_allowed=True,
            data_class="public",
        ),
    )
    decision = ResilienceRouteDecision(
        selected_route="cloud_primary",
        reason="forced_cloud_route",
        fallback_depth=0,
        human_review_required=False,
    )

    with patch("triage_core.classifier.TaskClassifier.classify", return_value="architecture_planning"):
        with patch.object(client.router.specialist, "route_task", return_value={"offload_recommended": False}):
            with patch("triage_core.client.choose_resilience_route", return_value=decision):
                with patch("triage_core.client.default_config.get_qwen_enabled", return_value=True):
                    with patch("triage_core.client.default_config.get_qwen_api_key", return_value=None):
                        with patch("triage_core.client.default_config.get_qwen_base_url", return_value="https://qwen.example/v1"):
                            with patch("triage_core.client.default_config.get_qwen_model", return_value="qwen-test"):
                                result = client.run_task(task_packet=packet)

    assert result["status"] == "handoff_required"
    assert result["source"] == "router"
    assert "not configured" in result["reason"]
