import json

from triage_core.backends import BackendResponse
from triage_core.classifier import TaskClassifier
from triage_core.client import TriageClient
from triage_core.qwen_demo import (
    DEMO_PROMPT,
    build_public_demo_packet,
    run_qwen_demo,
    validate_qwen_demo_response,
)


class UnavailableClassifierBackend:
    called = False

    def generate(self, **kwargs):
        self.called = True
        raise RuntimeError("offline")


class RecordingLocalBackend:
    name = "fake"
    base_url = "http://localhost"
    model = "local-test"

    def __init__(self) -> None:
        self.called = False

    def generate(self, messages, temperature=0.1, timeout=45, **kwargs):
        self.called = True
        return BackendResponse(
            text="LOCAL_RAN",
            raw={},
            backend_name=self.name,
        )


class RecordingQwenBackend:
    name = "qwen"
    base_url = "https://qwen.example/v1"
    model = "qwen-test"

    def __init__(self) -> None:
        self.called = False

    def generate(self, messages, temperature=0.1, timeout=45, **kwargs):
        self.called = True
        return BackendResponse(
            text=json.dumps(
                {
                    "summary": "Use a public synthetic task.",
                    "qwen_role": "Provide bounded cloud reasoning.",
                    "safeguards": [
                        "Require external-safe classification.",
                        "Write metadata-only route evidence.",
                    ],
                    "next_step": "Review the result and audit record.",
                }
            ),
            raw={},
            usage={
                "prompt_tokens": 20,
                "completion_tokens": 15,
                "total_tokens": 35,
            },
            backend_name=self.name,
        )


def test_novel_design_classifier_falls_back_to_cloud_eligible_category():
    backend = UnavailableClassifierBackend()
    category = TaskClassifier.classify(
        DEMO_PROMPT,
        backend=backend,
    )

    assert category == "novel_design"
    assert backend.called is False


def test_public_demo_packet_is_explicitly_external_safe():
    packet = build_public_demo_packet("demo-task")

    assert packet.task_id == "demo-task"
    assert packet.privacy_metadata.data_class == "public"
    assert packet.privacy_metadata.external_model_allowed is True
    assert packet.privacy_metadata.contains_pii is False
    assert packet.privacy_metadata.contains_sensitive_content is False


def test_qwen_demo_response_validator_requires_exact_schema():
    assert validate_qwen_demo_response(
        json.dumps(
            {
                "summary": "Summary",
                "qwen_role": "Role",
                "safeguards": ["One"],
                "next_step": "Next",
            }
        )
    )
    assert not validate_qwen_demo_response('{"summary": "missing fields"}')
    assert not validate_qwen_demo_response("not json")


def test_run_qwen_demo_uses_real_policy_path_and_records_evidence(
    tmp_path,
    monkeypatch,
):
    local_backend = RecordingLocalBackend()
    qwen_backend = RecordingQwenBackend()
    client = TriageClient(backend=local_backend)

    monkeypatch.setattr(
        "triage_core.classifier.TaskClassifier.classify",
        lambda prompt: "novel_design",
    )
    monkeypatch.setattr(
        "triage_core.routers.is_internet_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "triage_core.client.default_config.get_qwen_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "triage_core.client.default_config.get_qwen_api_key",
        lambda: "test-key",
    )
    monkeypatch.setattr(
        "triage_core.client.default_config.get_qwen_base_url",
        lambda: qwen_backend.base_url,
    )
    monkeypatch.setattr(
        "triage_core.client.default_config.get_qwen_model",
        lambda: qwen_backend.model,
    )
    monkeypatch.setattr(
        "triage_core.qwen_demo.default_config.get_qwen_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "triage_core.qwen_demo.default_config.get_qwen_api_key",
        lambda: "test-key",
    )
    monkeypatch.setattr(
        "triage_core.client.create_backend",
        lambda **kwargs: qwen_backend,
    )

    evidence = run_qwen_demo(
        ledger_dir=str(tmp_path),
        task_id="qwen-proof-test",
        client=client,
    )

    assert evidence.status == "success"
    assert evidence.source == "cloud"
    assert evidence.selected_route == "cloud_primary"
    assert evidence.selected_backend == "qwen"
    assert evidence.privacy_level == "external_safe"
    assert evidence.route_decision == "allowed"
    assert evidence.validation_status == "passed"
    assert evidence.total_tokens == 35
    assert local_backend.called is False
    assert qwen_backend.called is True

    ledger_text = tmp_path.joinpath("ledger.jsonl").read_text(encoding="utf-8")
    assert DEMO_PROMPT not in ledger_text
    assert '"prompt"' not in ledger_text
    assert '"data"' not in ledger_text
