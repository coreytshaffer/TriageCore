"""Offline tests for the governed ``tc run`` CLI surface (CR-DD-009).

All tests run fully offline with a recording HTTP adapter and a temporary
ledger directory, so no real backend is contacted and the real ledger is never
written. They assert the governed loop behavior and the CR-DD-009 exit-code
contract:

    0  local execution succeeded
    1  input / IO / argument error
    2  privacy or safety fail-closed
    3  governed handoff_required
"""

import json
import re
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import requests

from triage_core import capability_evidence, tc_cli
from test_governed_consumption_parity import recorded_http  # noqa: F401 (pytest fixture)
from triage_core.local_backend_probe import LocalBackendProbeRecord
from triage_core.routing.resilience_router import ResilienceRouteDecision
from triage_core.task_packet import PrivacyMetadata


@pytest.fixture(autouse=True)
def declared_local_capability(monkeypatch):
    """Declare both local route classes for this module (CR-DD-013).

    ``tc run`` no longer treats local capability as healthy without evidence,
    so these tests state that assumption explicitly instead of relying on an
    optimistic default. Tests needing a different posture patch
    ``resolve_from_config`` themselves.
    """
    resolution = capability_evidence.resolve_capability(
        record=None,
        declare_local_fast=True,
        declare_local_heavy=True,
        config_reference="test:[capability]",
        freshness_seconds=300,
        local_fast_model="qwen2.5-coder:7b-triagecore",
        local_heavy_model="deepseek-r1:latest",
    )
    monkeypatch.setattr(
        capability_evidence, "resolve_from_config", lambda *a, **k: resolution
    )
    return resolution


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


def _ledger_events(ledger_path):
    return [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class RecordingClient:
    def __init__(self):
        self.packet = None

    def run_task(
        self,
        task_packet,
        ledger=None,
        task_id=None,
        capability=None,
        snapshot=None,
        decision=None,
        governed_context=None,
    ):
        self.packet = task_packet
        self.capability = capability
        self.snapshot = snapshot
        self.decision = decision
        return {
            "status": "success",
            "output": "CLIENT_RAN",
            "selected_route": "local_fast",
        }


def test_local_success_exits_zero_and_records_governed_evidence(recorded_http, tmp_path, capsys):
    args = _args("Summarize this text", ledger_dir=str(tmp_path))

    tc_cli.tc_run(args)  # returns normally == exit 0

    assert len(recorded_http.calls) == 1
    ledger_file = tmp_path / "ledger.jsonl"
    assert ledger_file.exists()
    types = _event_types(ledger_file)
    # Proves the run went through the resilience router and wrote evidence.
    assert "task_created" in types
    assert "runner_selected" in types
    assert "route_decision" in types
    assert "worker_result" in types
    assert "Success: task ran locally" in capsys.readouterr().out


def test_route_and_worker_evidence_share_cli_reported_task_id(recorded_http, tmp_path, capsys):
    # No --task-id, so the identifier is the one tc run generated for itself.
    # Reading it back out of the success line is what proves the persisted
    # evidence belongs to the run the operator was told about.
    args = _args("Summarize this text", ledger_dir=str(tmp_path))

    tc_cli.tc_run(args)

    reported = re.search(r"task_id=([^)]+)\)", capsys.readouterr().out)
    assert reported, "tc run must report the task_id it ran under."
    reported_task_id = reported.group(1)

    events = _ledger_events(tmp_path / "ledger.jsonl")
    route_decision = next(e for e in events if e["event_type"] == "route_decision")
    worker_result = next(e for e in events if e["event_type"] == "worker_result")

    assert route_decision["task_id"] == worker_result["task_id"]
    assert route_decision["task_id"] == reported_task_id
    assert worker_result["task_id"] == reported_task_id


def test_tc_run_persists_metadata_without_prompt_or_data_content(recorded_http, tmp_path):
    prompt = "PROMPT_SENTINEL_ONLY_FOR_PRIVACY_TEST"
    data = "DATA_SENTINEL_ONLY_FOR_PRIVACY_TEST"
    args = _args(prompt, data=data, ledger_dir=str(tmp_path))

    tc_cli.tc_run(args)

    ledger_file = tmp_path / "ledger.jsonl"
    ledger_text = ledger_file.read_text(encoding="utf-8")
    assert prompt not in ledger_text
    assert data not in ledger_text

    task_created = next(
        event
        for event in _ledger_events(ledger_file)
        if event["event_type"] == "task_created"
    )
    assert task_created["payload"] == {
        "title": "tc run task",
        "description": "Prompt content withheld from ledger.",
        "prompt_length": len(prompt),
        "data_length": len(data),
        "target_files": [],
    }


def test_tc_run_privacy_block_leaves_no_ledger_event(recorded_http, tmp_path):
    args = _args("Process this record", data="123-45-6789", ledger_dir=str(tmp_path))

    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(args)

    assert exc.value.code == 2
    assert recorded_http.calls == []
    assert not (tmp_path / "ledger.jsonl").exists()


def test_early_local_block_records_binding_issue_on_runner_selected(
    recorded_http, tmp_path, monkeypatch
):
    record = LocalBackendProbeRecord(
        source_type="lm_studio",
        base_url="http://localhost:11434",
        reachable=True,
        evidence_tier="operator_recorded",
        observed_at=datetime.now(timezone.utc).isoformat(),
        observed_models=["qwen2.5-coder:7b-triagecore"],
    )
    resolution = capability_evidence.resolve_capability(
        record=record,
        declare_local_fast=False,
        declare_local_heavy=True,
        local_heavy_model="deepseek-r1:latest",
        config_reference="test:[capability]",
        freshness_seconds=300,
    )
    monkeypatch.setattr(
        capability_evidence, "resolve_from_config", lambda *a, **k: resolution
    )

    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(
            _args("Update the docs", ledger_dir=str(tmp_path)),
        )

    assert exc.value.code == 2
    assert recorded_http.calls == []
    events = _ledger_events(tmp_path / "ledger.jsonl")
    runner = next(event for event in events if event["event_type"] == "runner_selected")
    assert runner["payload"]["capability_declared_route_classes"] == ["local_heavy"]
    assert runner["payload"]["capability_route_binding_issues"] == {
        "local_heavy": "model_not_observed"
    }
    assert any(event["event_type"] == "route_decision" for event in events)


@pytest.mark.parametrize("handoff", [False, True], ids=["success", "timeout"])
@pytest.mark.parametrize("cloud", [False, True], ids=["ollama", "qwen"])
def test_attempted_destination_in_output_and_worker_result(
    recorded_http, monkeypatch, tmp_path, capsys, cloud, handoff
):
    from triage_core.destination_policy import normalize_endpoint

    secret = "synthetic-test-key"
    local_url = "http://127.0.0.1:11434"
    cloud_url = "https://dashscope-intl.aliyuncs.com:443/compatible-mode/v1"
    monkeypatch.setenv("TRIAGE_BACKEND_TYPE", "ollama")
    monkeypatch.setenv("TRIAGE_BASE_URL", local_url)
    monkeypatch.setenv("TRIAGE_QWEN_ENABLED", "1")
    monkeypatch.setenv("TRIAGE_QWEN_BASE_URL", cloud_url)
    monkeypatch.setenv("TRIAGE_QWEN_MODEL", "qwen-max")
    monkeypatch.setenv("TRIAGE_QWEN_API_KEY", secret)
    if cloud:
        monkeypatch.setattr(
            capability_evidence, "resolve_from_config",
            lambda *a, **kw: capability_evidence.unknown_resolution(),
        )
    args = _args(
        "Summarize this text", privacy="public" if cloud else "local_only",
        allow_cloud=cloud, ledger_dir=str(tmp_path),
    )

    if handoff:
        recorded_http.error = requests.Timeout("Timed out")
        with pytest.raises(SystemExit) as exc:
            tc_cli.tc_run(args)
        assert exc.value.code == 3
    else:
        tc_cli.tc_run(args)

    assert len(recorded_http.calls) == 1
    expected = normalize_endpoint(
        cloud_url if cloud else local_url, "cloud_primary" if cloud else "local_heavy"
    )
    out = capsys.readouterr().out
    assert f"Destination: {expected.safe_label} ({expected.identity_sha256})" in out
    worker = next(
        e["payload"] for e in _ledger_events(tmp_path / "ledger.jsonl")
        if e["event_type"] == "worker_result"
    )
    assert worker["destination_safe_label"] == expected.safe_label
    assert worker["destination_identity_sha256"] == expected.identity_sha256
    for text in (out, json.dumps(worker)):
        assert secret not in text
        assert local_url not in text
        assert cloud_url not in text


def test_unconfigured_qwen_handoff_omits_destination_evidence(
    recorded_http, monkeypatch, tmp_path, capsys
):
    monkeypatch.setenv("TRIAGE_QWEN_ENABLED", "1")
    monkeypatch.delenv("TRIAGE_QWEN_API_KEY", raising=False)
    monkeypatch.setattr(
        capability_evidence, "resolve_from_config",
        lambda *a, **kw: capability_evidence.unknown_resolution(),
    )
    args = _args("Summarize this text", privacy="public", allow_cloud=True, ledger_dir=str(tmp_path))
    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(args)
    assert exc.value.code == 3 and recorded_http.calls == []
    worker = next(
        e["payload"] for e in _ledger_events(tmp_path / "ledger.jsonl")
        if e["event_type"] == "worker_result"
    )
    assert worker["selected_route"] == "cloud_primary"
    assert "destination_safe_label" not in worker and "destination_identity_sha256" not in worker
    assert "Destination:" not in capsys.readouterr().out


@pytest.mark.parametrize(
    ("preferred_route", "reason", "bound_route"),
    [
        ("human_handoff", "sensitivity_requires_human_review", "human_handoff"),
        # CR-DD-012B: ``deterministic`` has no executor wired into the governed
        # loop, so it can never *bind*. It falls through to the next already
        # authorized envelope member rather than executing anything.
        (
            "deterministic",
            "deterministic_tool_available_for_task_class",
            "human_handoff",
        ),
    ],
)
def test_terminal_routes_exit_3_without_backend_execution(
    recorded_http, tmp_path, preferred_route, reason, bound_route, capsys
):
    args = _args(
        "Summarize public text",
        privacy="public",
        allow_cloud=True,
        ledger_dir=str(tmp_path),
    )
    # CR-DD-012B: the logical route now comes from the governed decision built
    # at the seam, so the router is driven there -- once -- rather than inside
    # ``run_task``. The seam asks the router for its own fallback ordering by
    # re-asking with the selected route made unavailable, hence the sequence.
    ordering = [
        ResilienceRouteDecision(
            selected_route=preferred_route,
            reason=reason,
            fallback_depth=0,
            human_review_required=preferred_route == "human_handoff",
        ),
        ResilienceRouteDecision(
            selected_route="human_handoff",
            reason="no_reliable_automated_route_available",
            fallback_depth=1,
            human_review_required=True,
        ),
    ]

    def _staged_route(route_input):
        return ordering[0] if len(ordering) == 1 else ordering.pop(0)

    with patch("triage_core.run_plan.choose_resilience_route", _staged_route):
        with pytest.raises(SystemExit) as exc:
            tc_cli.tc_run(args)

    assert exc.value.code == 3
    assert recorded_http.calls == []

    events = [
        json.loads(line)
        for line in (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    worker_result = next(event for event in events if event["event_type"] == "worker_result")
    assert "Destination:" not in capsys.readouterr().out
    assert "destination_safe_label" not in worker_result["payload"]
    assert "destination_identity_sha256" not in worker_result["payload"]
    assert worker_result["payload"]["selected_route"] == bound_route
    assert worker_result["payload"]["worker_result_status"] == "not_attempted"
    assert worker_result["payload"]["failure_type"] == "safety_handoff"


def test_high_risk_local_only_fails_closed_exit_2(recorded_http, tmp_path):
    args = _args(
        "delete all files and wipe secrets",
        data="small data",
        ledger_dir=str(tmp_path),
    )

    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(args)

    assert exc.value.code == 2
    # Fail-closed: the backend must never have been invoked.
    assert recorded_http.calls == []


def test_no_ledger_warns_and_writes_nothing(recorded_http, tmp_path, capsys):
    args = _args("Summarize this text", ledger_dir=str(tmp_path), no_ledger=True)

    tc_cli.tc_run(args)

    out = capsys.readouterr().out
    assert "Warning: --no-ledger" in out
    assert not (tmp_path / "ledger.jsonl").exists()
    assert len(recorded_http.calls) == 1


def test_missing_input_file_exits_1(recorded_http, tmp_path):
    args = _args(
        "do it",
        files=[str(tmp_path / "does_not_exist.txt")],
        ledger_dir=str(tmp_path),
    )

    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(args)

    assert exc.value.code == 1


def test_output_written_and_printed(recorded_http, tmp_path, capsys):
    out_file = tmp_path / "out.txt"
    args = _args(
        "Summarize this text",
        ledger_dir=str(tmp_path),
        output=str(out_file),
        print_output=True,
    )

    tc_cli.tc_run(args)

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


@pytest.mark.parametrize(("configured_type", "name", "base_url", "suffix"), [
    ("", "ollama", "http://127.0.0.1:11434", "/api/chat"),
    ("lm_studio", "lmstudio", "http://127.0.0.1:1234/v1", "/chat/completions"),
    ("llamacpp", "llama.cpp", "http://127.0.0.1:8080/v1", "/chat/completions"),
])
def test_audit_records_the_dispatched_backend(
    recorded_http, tmp_path, monkeypatch, configured_type, name, base_url, suffix
):
    monkeypatch.setenv("TRIAGE_BACKEND_TYPE", configured_type)
    monkeypatch.setenv("TRIAGE_BASE_URL", base_url)

    tc_cli.tc_run(_args("Summarize this text", ledger_dir=str(tmp_path)))

    assert [(r.method, r.url) for r, _ in recorded_http.calls] == [("POST", base_url + suffix)]
    event_types = {"route_audit", "route_decision", "worker_result"}
    selections = [
        (event["event_type"], event["payload"]["selected_backend"])
        for event in _ledger_events(tmp_path / "ledger.jsonl")
        if event["event_type"] in event_types
    ]
    assert selections == [("route_audit", name), ("route_decision", name), ("worker_result", name)]
