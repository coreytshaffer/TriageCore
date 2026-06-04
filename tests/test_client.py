from triage_core.backends import BackendResponse
from triage_core.client import TriageClient


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
    assert "Risk level high" in result["reason"]
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
    assert result["backend_name"] == "fake"
    assert result["model"] == "fake-model"
    assert result["input_tokens"] == 3
    assert result["output_tokens"] == 2
    assert result["total_tokens"] == 5
    assert backend.called is True
