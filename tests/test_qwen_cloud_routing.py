from datetime import date
from unittest.mock import MagicMock, patch

import pytest
import requests

from triage_core.backends import BackendResponse
from triage_core.client import TriageClient
from triage_core.routing.resilience_router import ResilienceRouteDecision
from triage_core.safe_task_packet import LocalRouteUnavailableError
from triage_core.task_ledger import TaskLedger
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


@pytest.fixture
def ledger():
    mock = MagicMock()
    mock.events = []

    def append_event(task_id, event_type, payload):
        mock.events.append((event_type, payload))

    mock.append_event = append_event
    return mock


@pytest.mark.parametrize("status_code", [200, 307])
def test_external_safe_cloud_route_runs_qwen_and_emits_allowed_audit(ledger, monkeypatch, status_code):
    local_backend = RecordingBackend()
    sends = []

    def send(self, request, **settings):
        sends.append(request)
        response = requests.Response()
        response.status_code = status_code
        response._content = b'{"choices":[{"message":{"content":"QWEN_RAN"}}]}'
        response._content_consumed = True
        if status_code == 307:
            response.headers["Location"] = "https://example.test/"
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
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

    with (
        patch("triage_core.classifier.TaskClassifier.classify", return_value="architecture_planning"),
        patch.object(client.router.specialist, "route_task", return_value={"offload_recommended": False}),
        patch("triage_core.client.choose_resilience_route", return_value=decision),
        patch("triage_core.client.default_config.get_qwen_enabled", return_value=True),
        patch("triage_core.client.default_config.get_qwen_api_key", return_value="synthetic-key"),
        patch("triage_core.client.default_config.get_qwen_base_url",
              return_value="https://dashscope-intl.aliyuncs.com/compatible-mode/v1"),
        patch("triage_core.client.default_config.get_qwen_model", return_value="qwen-test"),
        patch("triage_core.project_steward.ProjectSteward.evaluate", return_value={"local_result_status": "sufficient"}),
    ):
        result = client.run_task(task_packet=packet, ledger=ledger)

    assert result["source"] == "cloud"
    if status_code == 200:
        assert result["status"] == "success"
        assert result["backend_name"] == "qwen"
        assert result["output"] == "QWEN_RAN"
    else:
        assert result["status"] == "handoff_required"
        assert "endpoint_redirect_refused" in result["reason"]
        assert "https://example.test/" not in str(result)
        assert "synthetic-key" not in str(result)
    assert local_backend.called is False
    [request] = sends
    assert request.method == "POST"
    assert request.url == "https://dashscope-intl.aliyuncs.com:443/compatible-mode/v1/chat/completions"
    assert request.headers["Authorization"] == "Bearer synthetic-key"

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


@pytest.mark.parametrize("enabled, api_key, model, reason", [
    (True, None, "qwen-test", "not configured"),
    (True, "synthetic-key", "qwen-test", "cloud_endpoint_not_approved"),
    (True, "synthetic-key", ["synthetic-model"], "cloud_model_unbound"),
    (True, "synthetic-key", date(2026, 1, 1), "cloud_model_unbound"),
    (False, "synthetic-key", "qwen-test", "not enabled"),
])
def test_legacy_cloud_setup_handoff_before_send(enabled, api_key, model, reason, monkeypatch, caplog, tmp_path):
    base_url = "https://example.test/v1"
    ledger = TaskLedger(str(tmp_path / "ledger"))
    monkeypatch.delenv("TRIAGE_QWEN_API_KEY", raising=False)
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

    with (
        patch("triage_core.classifier.TaskClassifier.classify", return_value="architecture_planning"),
        patch.object(client.router.specialist, "route_task", return_value={"offload_recommended": False}),
        patch("triage_core.client.choose_resilience_route", return_value=decision),
        patch("triage_core.client.default_config.get_qwen_enabled", return_value=enabled),
        patch("triage_core.client.default_config.get_qwen_api_key", return_value=api_key),
        patch("triage_core.client.default_config.get_qwen_base_url", return_value=base_url),
        patch("triage_core.client.default_config.get_qwen_model", return_value=model),
        patch("requests.adapters.HTTPAdapter.send") as send,
    ):
        result = client.run_task(task_packet=packet, ledger=ledger)

    send.assert_not_called()
    assert result["status"] == "handoff_required"
    assert result["source"] == "router"
    assert reason in result["reason"]
    assert base_url not in str(result) + caplog.text
    assert "synthetic-key" not in str(result) + caplog.text
    assert result["selected_model"] == (model if isinstance(model, str) else "")
