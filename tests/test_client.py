from triage_core.backends import OllamaBackend
from test_endpoint_transport_guard import transport_tripwires
from triage_core.client import TriageClient
from triage_core.agent_identity import AgentIdentityRegistry
from triage_core.task_ledger import TaskLedger
from triage_core.task_packet import TaskPacket, PrivacyMetadata

import tempfile
import uuid

import pytest
import requests


ROUTED_MODEL = "qwen2.5-coder:7b-triagecore"


@pytest.fixture
def local_client(monkeypatch):
    transport_tripwires(monkeypatch)
    calls = []

    def send(self, request, **settings):
        calls.append(request)
        response = requests.Response()
        response.status_code = 200
        response._content = (
            b'{"message":{"content":"LOCAL_RAN"},"prompt_eval_count":3,"eval_count":2}'
        )
        response._content_consumed = True
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    client = TriageClient(
        backend_type="ollama", model="fixture", base_url="http://127.0.0.1:11434"
    )
    return client, calls


class FailingBackend:
    name = "fixture"
    base_url = "http://127.0.0.1:11434"
    model = "fixture"

    def __init__(self):
        self.called = False

    def generate(self, *args, **kwargs):
        self.called = True
        raise AssertionError("Backend should never run for high-risk prompts.")

def test_high_risk_task_is_handed_off_before_backend_runs():
    backend = FailingBackend()
    client = TriageClient(backend=backend)

    result = client.run_task("delete all files and wipe secrets", "small data")

    assert result["status"] == "handoff_required"
    assert result["source"] == "router"
    assert "Human handoff required by the resilience route" in result["reason"]
    assert result["route_reason"] == "sensitivity_requires_human_review"
    assert backend.called is False


def test_low_risk_task_runs_backend(local_client):
    client, calls = local_client

    result = client.run_task("Summarize this text", "small data")

    assert result["status"] == "success"
    assert result["source"] == "local"
    assert result["output"] == "LOCAL_RAN"
    assert result["backend_name"] == "ollama"
    assert result["model"] == ROUTED_MODEL
    assert result["input_tokens"] == 3
    assert result["output_tokens"] == 2
    assert result["total_tokens"] == 5
    assert [request.method for request in calls] == ["POST"]


def test_validator_failure_records_model_and_token_context(local_client):
    client, calls = local_client
    result = client.run_task(
        "Summarize this text",
        "small data",
        validator=lambda _output: False,
    )

    assert result["status"] == "handoff_required"
    assert result["source"] == "local_engine"
    assert result["validator_passed"] is False
    assert result["worker_result_status"] == "completed"
    assert result["validation_status"] == "failed"
    assert result["backend_name"] == "ollama"
    assert result["model"] == ROUTED_MODEL
    assert result["input_tokens"] == 3
    assert result["output_tokens"] == 2
    assert result["total_tokens"] == 5
    assert [request.method for request in calls] == ["POST"]


@pytest.mark.parametrize("failure, expected", [
    (requests.exceptions.Timeout("Timed out"), ("timed_out", "timeout", "local_backend_generate")),
    (RuntimeError("Synthetic backend failure"), ("worker_failed", "backend_error", "local_backend_generate")),
    (ValueError("Missing response content"), ("invalid_output", "invalid_backend_response", "response_parse")),
])
def test_engine_failure_statuses_pass_through_client(monkeypatch, local_client, failure, expected):
    client, calls = local_client

    def fail_generate(self, **kwargs):
        assert kwargs["_verified_transport"].owner is self
        raise failure

    monkeypatch.setattr(OllamaBackend, "generate", fail_generate)
    result = client.run_task("Summarize this", "Synthetic data")
    assert tuple(result[key] for key in ("worker_result_status", "failure_type", "failure_stage")) == expected
    assert not calls

def test_router_safety_handoff_is_not_counted_as_backend_failure():
    backend = FailingBackend()
    client = TriageClient(backend=backend)
    result = client.run_task("delete all files and wipe secrets", "small data")
    assert result["worker_result_status"] == "not_attempted"
    assert result["failure_type"] == "safety_handoff"
    assert result["failure_stage"] == "router"

def test_client_run_task_with_explicit_task_packet(local_client):
    client, _ = local_client
    metadata = PrivacyMetadata(data_class="restricted", external_model_allowed=False)
    packet = TaskPacket(
        prompt="Analyze sensitive data",
        data="Name: Secret",
        privacy_metadata=metadata,
        task_id="tp-001"
    )
    result = client.run_task(task_packet=packet)
    assert result["status"] == "success"
    assert result["output"] == "LOCAL_RAN"


def test_run_task_writes_route_decision_and_worker_result_events(local_client):
    client, _ = local_client

    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())
        ledger.append_event(task_id, "task_created", {"title": "Route Event Task"})

        result = client.run_task(
            "Summarize this text",
            "small data",
            ledger=ledger,
            task_id=task_id,
        )
        events = ledger.get_events(task_id)

    event_types = [event["event_type"] for event in events]

    assert result["status"] == "success"
    assert "route_decision" in event_types
    assert "worker_result" in event_types

    route_event = next(event for event in events if event["event_type"] == "route_decision")
    worker_event = next(event for event in events if event["event_type"] == "worker_result")

    assert route_event["payload"]["selected_route"] == result["selected_route"]
    assert worker_event["payload"]["worker_result_status"] == "completed"
    assert worker_event["payload"]["backend_failure"] is False


def test_run_task_can_write_signed_route_decision_event(local_client):
    client, _ = local_client

    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        registry = AgentIdentityRegistry(ledger_dir=temp_dir)
        registry.generate_identity(
            "router-tools",
            "router_tools",
            ["route_decision:sign"],
        )
        task_id = str(uuid.uuid4())
        ledger.append_event(task_id, "task_created", {"title": "Signed Route Decision Task"})

        result = client.run_task(
            "Summarize this text",
            "small data",
            ledger=ledger,
            task_id=task_id,
            route_decision_signing_registry=registry,
            route_decision_signing_agent_id="router-tools",
        )
        route_event = next(
            event for event in ledger.get_events(task_id) if event["event_type"] == "route_decision"
        )

    assert result["status"] == "success"
    assert route_event["signature_metadata"]["agent_id"] == "router-tools"
    assert route_event["signature_metadata"]["capability"] == "route_decision:sign"


def test_router_handoff_event_is_recorded_without_backend_failure():
    backend = FailingBackend()
    client = TriageClient(backend=backend)

    with tempfile.TemporaryDirectory() as temp_dir:
        ledger = TaskLedger(ledger_dir=temp_dir)
        task_id = str(uuid.uuid4())
        ledger.append_event(task_id, "task_created", {"title": "Safety Route Task"})

        result = client.run_task(
            "delete all files and wipe secrets",
            "small data",
            ledger=ledger,
            task_id=task_id,
        )
        worker_event = next(
            event for event in ledger.get_events(task_id) if event["event_type"] == "worker_result"
        )

    assert result["status"] == "handoff_required"
    assert worker_event["payload"]["worker_result_status"] == "not_attempted"
    assert worker_event["payload"]["backend_failure"] is False
