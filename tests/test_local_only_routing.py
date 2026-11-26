import pytest
import requests
from unittest.mock import patch, MagicMock

from triage_core.client import TriageClient
from triage_core.task_packet import TaskPacket, PrivacyMetadata
from triage_core.privacy_scanner import PrivacyViolationError
from triage_core.safe_task_packet import LocalRouteUnavailableError
from triage_core.routing.resilience_router import ResilienceRouteDecision
from triage_core.engine import TriageEngine
from test_endpoint_transport_guard import record_adapter, transport_tripwires


def test_implicit_private_task_uses_only_the_sealed_local_backend(monkeypatch):
    transport_tripwires(monkeypatch)
    sends = record_adapter(monkeypatch)
    monkeypatch.setenv("HTTPS_PROXY", "http://example.invalid:8080")
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", "synthetic-ca.pem")
    client = TriageClient(
        backend_type="ollama", model="fixture", base_url="http://127.0.0.1:11434"
    )
    with (
        patch("triage_core.classifier.TaskClassifier.classify") as classify,
        patch("triage_core.routers.is_internet_available") as probe,
        patch(
            "triage_core.project_steward.ProjectSteward.evaluate",
            return_value={"local_result_status": "sufficient"},
        ),
    ):
        result = client.run_task("Summarize this", "Synthetic local data")

    classify.assert_not_called()
    probe.assert_not_called()
    assert result["status"] == "success"
    [(request, settings)] = sends
    assert request.url == "http://127.0.0.1:11434/api/chat"
    assert settings["proxies"] == {}
    assert settings["verify"] is True
    assert "Authorization" not in request.headers


def test_unverified_injected_backend_is_refused_without_invocation(monkeypatch):
    transport_tripwires(monkeypatch)
    sends = record_adapter(monkeypatch)
    backend = MagicMock()
    backend.name = "fixture"
    backend.base_url = "http://127.0.0.1:11434"
    backend.model = "fixture"
    client = TriageClient(backend=backend)
    with (
        patch("triage_core.classifier.TaskClassifier.classify"),
        patch("triage_core.routers.is_internet_available"),
        patch(
            "triage_core.project_steward.ProjectSteward.evaluate",
            return_value={"local_result_status": "sufficient"},
        ),
    ):
        result = client.run_task("Summarize this", "Synthetic local data")

    assert result["status"] == "handoff_required"
    assert "backend_protocol_unsupported" in result["reason"]
    assert result["worker_result_status"] == "not_attempted"
    backend.generate.assert_not_called()
    assert not sends


@pytest.mark.parametrize("base_url", ["http://example.invalid/v1", "http://localhost:1234/v1"])
def test_unapproved_configured_local_destination_is_refused(monkeypatch, base_url):
    transport_tripwires(monkeypatch)
    sends = record_adapter(monkeypatch)
    client = TriageClient(backend_type="custom", model="fixture", base_url=base_url)
    result = client.run_task(task_packet=TaskPacket("Summarize this", "Synthetic data"))

    assert result["status"] == "handoff_required"
    assert result["worker_result_status"] == "not_attempted"
    assert "hostname_not_literal_loopback" in result["reason"]
    assert base_url not in result["reason"]
    assert not sends


def test_changed_bound_destination_refuses_before_the_first_send(monkeypatch):
    transport_tripwires(monkeypatch)
    sends = record_adapter(monkeypatch)
    client = TriageClient(backend_type="ollama", base_url="http://127.0.0.1:11434")
    execute = TriageEngine.execute_task

    def change_endpoint(engine, **kwargs):
        engine.backend.base_url = "http://127.0.0.1:11435"
        return execute(engine, **kwargs)

    monkeypatch.setattr(TriageEngine, "execute_task", change_endpoint)
    result = client.run_task("Summarize this", "Synthetic data")

    assert result["status"] == "handoff_required"
    assert "destination_binding_mismatch" in result["reason"]
    assert result["worker_result_status"] == "not_attempted"
    assert not sends


def test_loopback_discovery_and_generation_use_the_same_binding(monkeypatch):
    transport_tripwires(monkeypatch)
    sends = record_adapter(monkeypatch)
    client = TriageClient(
        backend_type="lmstudio", model="auto", base_url="http://[::1]:1234/v1"
    )
    monkeypatch.setattr(client.router.specialist, "route_task", lambda *a, **k: {"model": "auto"})
    result = client.run_task("Summarize this", "Synthetic data")

    assert result["status"] == "success"
    assert [(request.method, request.url) for request, _ in sends] == [
        ("GET", "http://[::1]:1234/v1/models"),
        ("POST", "http://[::1]:1234/v1/chat/completions"),
    ]
    assert client.engine.backend.model == "auto"


def test_redirect_returns_bounded_handoff_without_following(monkeypatch):
    transport_tripwires(monkeypatch)
    sends = []

    def send(self, request, **settings):
        sends.append(request.url)
        response = requests.Response()
        response.status_code = 307
        response.headers["Location"] = "https://example.invalid/redirect"
        response._content_consumed = True
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    client = TriageClient(backend_type="ollama", base_url="http://127.0.0.1:11434")
    result = client.run_task("Summarize this", "Synthetic data")

    assert result["status"] == "handoff_required"
    assert "endpoint_redirect_refused" in result["reason"]
    assert "example.invalid" not in result["reason"]
    assert result["worker_result_status"] == "worker_failed"
    assert sends == ["http://127.0.0.1:11434/api/chat"]

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

def test_local_only_packet_allows_explicit_local_route(monkeypatch):
    transport_tripwires(monkeypatch)
    sends = record_adapter(monkeypatch)
    client = TriageClient(backend_type="ollama", base_url="http://127.0.0.1:11434")
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
                result = client.run_task(task_packet=packet)
    assert result["status"] == "success"
    assert result["output"] == "done"
    assert [request.method for request, _ in sends] == ["POST"]

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
            # If specialist router recommends offload. CR-DD-018: the mocked result
            # must supply the bounded structured cause a real route_task() invocation
            # would carry, since specialist evidence is built from this same result
            # and is never re-derived.
            offload_result = {
                "offload_recommended": True,
                "specialist_offload_cause": {
                    "offload_reason_code": "high_risk",
                    "risk_level": "high",
                    "risk_categories": ["destructive_ops"],
                },
            }
            with patch.object(client.router.specialist, "route_task", return_value=offload_result):
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
