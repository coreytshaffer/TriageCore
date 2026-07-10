"""CR-117: opt-in ``tc task show --verify-signatures`` fail-closed path.

Verifies the signed ledger events belonging to a single task, reusing the
CR-097 fail-closed categories. Fail-closed: invalid or malformed signatures
exit 1; unsigned signed-type events remain informational (exit 0). The
default (flag-off) output must be byte-for-byte unchanged.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from triage_core.tc_cli import tc_task_show
from triage_core.task_ledger import TaskLedger
from triage_core.agent_identity import AgentIdentityRegistry


def _seed_task(ledger, task_id, title="Task"):
    ledger.append_event(
        task_id, "task_created", {"title": title, "description": "x"}
    )


def test_flag_off_output_is_unchanged_and_exits_normally(tmp_path, capsys):
    ledger_dir = tmp_path / ".triagecore"
    ledger = TaskLedger(str(ledger_dir))
    _seed_task(ledger, "t1", title="Build UI Dashboard")

    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_dir / "ledger.jsonl"):
        tc_task_show("t1")  # default: verify_signatures=False

    out = capsys.readouterr().out
    assert "Task ID: t1" in out
    assert (
        "Signature verification: not checked by this command; "
        "run tc audit --verify-signatures" in out
    )
    # No summary lines are emitted when the flag is off.
    assert "valid_signed=" not in out


def test_verify_valid_signed_route_decision_exits_0(tmp_path, capsys):
    ledger_dir = tmp_path / ".triagecore"
    ledger = TaskLedger(str(ledger_dir))
    registry = AgentIdentityRegistry(ledger_dir=ledger_dir)
    registry.generate_identity("router-tools", "router_tools", ["route_decision:sign"])

    _seed_task(ledger, "t-valid")
    ledger.append_signed_route_decision_event(
        "t-valid",
        {
            "selected_route": "local_fast",
            "reason": "signed_ok",
            "route_source": "resilience_router",
        },
        signing_registry=registry,
        signing_agent_id="router-tools",
    )

    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_dir / "ledger.jsonl"):
        tc_task_show("t-valid", verify_signatures=True)  # no SystemExit

    out = capsys.readouterr().out
    assert "Signature verification:" in out
    assert "valid_signed=1" in out
    assert "invalid_signed=0" in out
    assert "PASS event_type=route_decision task_id=t-valid agent_id=router-tools" in out


def test_verify_tampered_signature_exits_1(tmp_path, capsys):
    ledger_dir = tmp_path / ".triagecore"
    ledger = TaskLedger(str(ledger_dir))
    registry = AgentIdentityRegistry(ledger_dir=ledger_dir)
    registry.generate_identity("router-tools", "router_tools", ["route_decision:sign"])

    _seed_task(ledger, "t-bad")
    ledger.append_signed_route_decision_event(
        "t-bad",
        {
            "selected_route": "local_fast",
            "reason": "tamper_target",
            "route_source": "resilience_router",
        },
        signing_registry=registry,
        signing_agent_id="router-tools",
    )

    # Tamper only the signed line; keep task_created so the task is still found.
    ledger_path = ledger_dir / "ledger.jsonl"
    new_lines = []
    for line in ledger_path.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("event_type") == "route_decision":
            event["payload"] = dict(event["payload"])
            event["payload"]["selected_route"] = "cloud_primary"
        new_lines.append(json.dumps(event))
    ledger_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_path):
        with pytest.raises(SystemExit) as exc:
            tc_task_show("t-bad", verify_signatures=True)

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "invalid_signed=1" in out
    assert "reason=signature_mismatch" in out
    assert "tamper_target" not in out


def test_verify_malformed_ledger_line_exits_1(tmp_path, capsys):
    ledger_dir = tmp_path / ".triagecore"
    ledger = TaskLedger(str(ledger_dir))
    _seed_task(ledger, "t-mal")

    ledger_path = ledger_dir / "ledger.jsonl"
    with ledger_path.open("a", encoding="utf-8") as f:
        f.write("{not json\n")

    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_path):
        with pytest.raises(SystemExit) as exc:
            tc_task_show("t-mal", verify_signatures=True)

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "malformed=1" in out


def test_verify_unsigned_signed_type_event_exits_0(tmp_path, capsys):
    ledger_dir = tmp_path / ".triagecore"
    ledger = TaskLedger(str(ledger_dir))
    _seed_task(ledger, "t-uns")
    ledger.append_event(
        "t-uns",
        "route_audit",
        {"decision": "allowed", "reason_code": "legacy_unsigned"},
    )

    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_dir / "ledger.jsonl"):
        tc_task_show("t-uns", verify_signatures=True)  # no SystemExit

    out = capsys.readouterr().out
    assert "unsigned=1" in out
    assert "invalid_signed=0" in out


def test_verify_signatures_registry_load_failure_exits_1(tmp_path, capsys):
    ledger_dir = tmp_path / ".triagecore"
    ledger = TaskLedger(str(ledger_dir))
    _seed_task(ledger, "t-reg")

    registry = AgentIdentityRegistry(ledger_dir=ledger_dir)
    registry.registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry.registry_path.write_text('{ "agents": [', encoding="utf-8")  # malformed

    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_dir / "ledger.jsonl"):
        with patch("triage_core.tc_cli._identity_registry", return_value=registry):
            with pytest.raises(SystemExit) as exc:
                tc_task_show("t-reg", verify_signatures=True)

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "reason=registry_load_failed" in out
    assert "category=malformed_registry" in out
    assert "Traceback" not in out


def test_task_not_found_exits_1_even_with_flag(tmp_path, capsys):
    ledger_dir = tmp_path / ".triagecore"
    TaskLedger(str(ledger_dir))  # create empty ledger dir

    with patch("triage_core.tc_cli._ledger_path", return_value=ledger_dir / "ledger.jsonl"):
        with pytest.raises(SystemExit) as exc:
            tc_task_show("does-not-exist", verify_signatures=True)

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "reason=task_not_found" in out
