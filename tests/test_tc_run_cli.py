"""Offline tests for the governed ``tc run`` CLI surface (CR-DD-009).

All tests run fully offline with an injected mock backend and a temporary
ledger directory, so no real backend is contacted and the real ledger is never
written. They assert the governed loop behavior and the CR-DD-009 exit-code
contract:

    0  local execution succeeded
    1  input / IO / argument error
    2  privacy or safety fail-closed
    3  governed handoff_required
"""

import json
from types import SimpleNamespace

import pytest
import requests

from triage_core import tc_cli
from triage_core.backends import BackendResponse
from triage_core.client import TriageClient
from triage_core.task_packet import PrivacyMetadata


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
    """Fails the test if the backend is ever invoked (proves fail-closed)."""

    def generate(self, messages, temperature=0.1, timeout=45, **kwargs):
        self.called = True
        raise AssertionError("Backend must not run for a fail-closed task.")


class ErrorBackend(RecordingBackend):
    """Local backend raises; engine should convert this into a handoff."""

    def generate(self, messages, temperature=0.1, timeout=45, **kwargs):
        self.called = True
        raise requests.exceptions.Timeout("Timed out")


def _args(prompt, **overrides):
    base = dict(
        prompt=prompt,
        files=[],
        data=None,
        privacy="local_only",
        allow_cloud=False,
        ledger_dir=None,
        task_id=None,
        output=None,
        print_output=False,
        no_ledger=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _event_types(ledger_path):
    return [
        json.loads(line)["event_type"]
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class RecordingClient:
    def __init__(self):
        self.packet = None

    def run_task(self, task_packet, ledger=None, task_id=None):
        self.packet = task_packet
        return {
            "status": "success",
            "output": "CLIENT_RAN",
            "selected_route": "local_fast",
        }


def test_local_success_exits_zero_and_records_governed_evidence(tmp_path, capsys):
    backend = RecordingBackend()
    client = TriageClient(backend=backend)
    args = _args("Summarize this text", ledger_dir=str(tmp_path))

    tc_cli.tc_run(args, client=client)  # returns normally == exit 0

    assert backend.called is True
    ledger_file = tmp_path / "ledger.jsonl"
    assert ledger_file.exists()
    types = _event_types(ledger_file)
    # Proves the run went through the resilience router and wrote evidence.
    assert "task_created" in types
    assert "runner_selected" in types
    assert "route_decision" in types
    assert "worker_result" in types
    assert "Success: task ran locally" in capsys.readouterr().out


def test_handoff_required_exits_3(tmp_path):
    client = TriageClient(backend=ErrorBackend())
    args = _args("Summarize this text", ledger_dir=str(tmp_path))

    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(args, client=client)

    assert exc.value.code == 3


def test_high_risk_local_only_fails_closed_exit_2(tmp_path):
    backend = FailingBackend()
    client = TriageClient(backend=backend)
    args = _args(
        "delete all files and wipe secrets",
        data="small data",
        ledger_dir=str(tmp_path),
    )

    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(args, client=client)

    assert exc.value.code == 2
    # Fail-closed: the backend must never have been invoked.
    assert backend.called is False


def test_no_ledger_warns_and_writes_nothing(tmp_path, capsys):
    backend = RecordingBackend()
    client = TriageClient(backend=backend)
    args = _args("Summarize this text", ledger_dir=str(tmp_path), no_ledger=True)

    tc_cli.tc_run(args, client=client)

    out = capsys.readouterr().out
    assert "Warning: --no-ledger" in out
    assert not (tmp_path / "ledger.jsonl").exists()
    assert backend.called is True


def test_missing_input_file_exits_1(tmp_path):
    client = TriageClient(backend=RecordingBackend())
    args = _args(
        "do it",
        files=[str(tmp_path / "does_not_exist.txt")],
        ledger_dir=str(tmp_path),
    )

    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(args, client=client)

    assert exc.value.code == 1


def test_output_written_and_printed(tmp_path, capsys):
    client = TriageClient(backend=RecordingBackend())
    out_file = tmp_path / "out.txt"
    args = _args(
        "Summarize this text",
        ledger_dir=str(tmp_path),
        output=str(out_file),
        print_output=True,
    )

    tc_cli.tc_run(args, client=client)

    assert out_file.read_text(encoding="utf-8") == "LOCAL_RAN"
    assert "LOCAL_RAN" in capsys.readouterr().out


@pytest.mark.parametrize("privacy", ["external_safe", "public"])
def test_non_local_privacy_defaults_cloud_disabled_without_allow_flag(tmp_path, privacy):
    client = RecordingClient()
    args = _args(
        "Summarize this text",
        privacy=privacy,
        ledger_dir=str(tmp_path),
        allow_cloud=False,
    )

    tc_cli.tc_run(args, client=client)

    assert isinstance(client.packet.privacy_metadata, PrivacyMetadata)
    assert client.packet.privacy_metadata.external_model_allowed is False


@pytest.mark.parametrize("privacy", ["external_safe", "public"])
def test_non_local_privacy_can_enable_cloud_with_allow_flag(tmp_path, privacy):
    client = RecordingClient()
    args = _args(
        "Summarize this text",
        privacy=privacy,
        ledger_dir=str(tmp_path),
        allow_cloud=True,
    )

    tc_cli.tc_run(args, client=client)

    assert isinstance(client.packet.privacy_metadata, PrivacyMetadata)
    assert client.packet.privacy_metadata.external_model_allowed is True


def test_local_only_with_allow_cloud_exits_1_before_run(tmp_path, capsys):
    client = RecordingClient()
    args = _args(
        "Summarize this text",
        privacy="local_only",
        ledger_dir=str(tmp_path),
        allow_cloud=True,
    )

    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(args, client=client)

    assert exc.value.code == 1
    assert client.packet is None
    assert "--allow-cloud cannot be used with --privacy local_only" in capsys.readouterr().out
