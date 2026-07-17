from triage_core.backends import BackendResponse
from triage_core.client import TriageClient
from triage_core.agent_identity import AgentIdentityRegistry
from triage_core.task_ledger import TaskLedger
from triage_core.task_packet import TaskPacket, PrivacyMetadata

import tempfile
import uuid


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


class FailingBackend(RecordingBackend):
    def generate(self, messages, temperature=0.1, timeout=45, **kwargs):
        self.called = True
        raise AssertionError("Backend should not run for high-risk prompts.")


def test_high_risk_task_is_handed_off_before_backend_runs():
    backend = FailingBackend()
    client = TriageClient(backend=backend)

    result = client.run_task("delete all files and wipe secrets", "small data")

    assert result["status"] == "handoff_required"
    assert result["source"] == "router"
    assert "Human handoff required by the resilience route" in result["reason"]
    assert result["route_reason"] == "sensitivity_requires_human_review"
    assert backend.called is False


def test_low_risk_task_runs_backend():
    backend = RecordingBackend()
    client = TriageClient(backend=backend)

    result = client.run_task("Summarize this text", "small data")

    assert result["status"] == "success"
    assert result["source"] == "local"
    assert result["output"] == "LOCAL_RAN"
    assert result["backend_name"] == "fake"
    assert result["model"] == "fake-model"
    assert result["input_tokens"] == 3
    assert result["output_tokens"] == 2
    assert result["total_tokens"] == 5
    assert backend.called is True


def test_validator_failure_records_model_and_token_context():
    backend = RecordingBackend()
    client = TriageClient(backend=backend)

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
    assert result["backend_name"] == "fake"
    assert result["model"] == "fake-model"
    assert result["input_tokens"] == 3
    assert result["output_tokens"] == 2
    assert result["total_tokens"] == 5
    assert backend.called is True


import requests

class TimeoutBackend(RecordingBackend):
    def generate(self, messages, temperature=0.1, timeout=45, **kwargs):
        raise requests.exceptions.Timeout("Timed out")

class ErrorBackend(RecordingBackend):
    def generate(self, messages, temperature=0.1, timeout=45, **kwargs):
        raise Exception("Some random error")

class InvalidOutputBackend(RecordingBackend):
    def generate(self, messages, temperature=0.1, timeout=45, **kwargs):
        raise ValueError("Backend returned no message content.")


def test_timeout_returns_timed_out_status():
    client = TriageClient(backend=TimeoutBackend())
    result = client.run_task("do it", "data")
    assert result["worker_result_status"] == "timed_out"
    assert result["failure_type"] == "timeout"
    assert result["failure_stage"] == "local_backend_generate"

def test_backend_error_returns_worker_failed_status():
    client = TriageClient(backend=ErrorBackend())
    result = client.run_task("do it", "data")
    assert result["worker_result_status"] == "worker_failed"
    assert result["failure_type"] == "backend_error"
    assert result["failure_stage"] == "local_backend_generate"

def test_invalid_output_returns_invalid_output_status():
    client = TriageClient(backend=InvalidOutputBackend())
    result = client.run_task("do it", "data")
    assert result["worker_result_status"] == "invalid_output"
    assert result["failure_type"] == "invalid_backend_response"
    assert result["failure_stage"] == "response_parse"

def test_router_safety_handoff_is_not_counted_as_backend_failure():
    backend = FailingBackend()
    client = TriageClient(backend=backend)
    result = client.run_task("delete all files and wipe secrets", "small data")
    assert result["worker_result_status"] == "not_attempted"
    assert result["failure_type"] == "safety_handoff"
    assert result["failure_stage"] == "router"

def test_client_run_task_with_explicit_task_packet():
    client = TriageClient(backend=RecordingBackend())
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


def test_run_task_writes_route_decision_and_worker_result_events():
    backend = RecordingBackend()
    client = TriageClient(backend=backend)

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


def test_run_task_can_write_signed_route_decision_event():
    backend = RecordingBackend()
    client = TriageClient(backend=backend)

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
