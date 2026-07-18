from argparse import Namespace
import json
import os
from pathlib import Path
import socket
import subprocess

import pytest

from triage_core import tc_cli
from triage_core.run_plan_artifact import (
    CANONICALIZATION_VERSION,
    CONTRACT_VERSION,
    RunPlanArtifactError,
    canonical_json_bytes,
    prepare_confirmation,
    publish_artifact,
    sha256_digest,
    validate_artifact_bytes,
)
from triage_core.task_ledger import TaskLedger


def _args(tmp_path: Path, **overrides) -> Namespace:
    values = {
        "prompt": "Review bounded documentation",
        "files": [],
        "data": None,
        "privacy": "local_only",
        "allow_cloud": False,
        "ledger_dir": None,
        "task_id": "task-dd-011",
        "output": None,
        "print_output": False,
        "no_ledger": False,
        "plan": True,
        "model": "generic-8k",
        "plan_output": str(tmp_path / "plan.json"),
    }
    values.update(overrides)
    return Namespace(**values)


def _write_plan(tmp_path: Path, capsys, **overrides):
    args = _args(tmp_path, **overrides)
    tc_cli.tc_run(args)
    output = capsys.readouterr().out
    artifact_bytes = Path(args.plan_output).read_bytes()
    artifact, body_digest, artifact_digest = validate_artifact_bytes(
        artifact_bytes
    )
    return args, output, artifact_bytes, artifact, body_digest, artifact_digest


def test_plan_artifact_is_deterministic_canonical_and_metadata_only(
    tmp_path, capsys
):
    source = tmp_path / "raw-locator-marker.txt"
    source.write_text("raw-source-marker", encoding="utf-8")
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    common = {
        "prompt": "Review raw-prompt-marker documentation",
        "data": "raw-inline-marker",
        "files": [str(source)],
        "task_id": "deterministic-task",
    }

    _, first_out, first_bytes, artifact, body_digest, byte_digest = _write_plan(
        tmp_path, capsys, plan_output=str(first), **common
    )
    _, _, second_bytes, _, _, _ = _write_plan(
        tmp_path, capsys, plan_output=str(second), **common
    )

    assert first_bytes == second_bytes
    assert first_bytes == canonical_json_bytes(artifact)
    assert not first_bytes.endswith(b"\n")
    assert artifact["contract_version"] == CONTRACT_VERSION
    assert (
        artifact["canonicalization_version"] == CANONICALIZATION_VERSION
    )
    assert artifact["plan_body_digest"] == sha256_digest(
        canonical_json_bytes(artifact["plan_body"])
    )
    assert byte_digest == sha256_digest(first_bytes)
    assert body_digest != byte_digest
    assert f"plan_body_digest: {body_digest}" in first_out
    assert f"artifact_byte_digest: {byte_digest}" in first_out
    assert "ledger_written: false" in first_out
    assert "plan_artifact_written: true" in first_out
    for raw_value in (
        "raw-prompt-marker",
        "raw-inline-marker",
        "raw-source-marker",
        str(source),
    ):
        assert raw_value.encode("utf-8") not in first_bytes
    assert not (tmp_path / ".triagecore").exists()


@pytest.mark.parametrize(
    "overrides, expected",
    [
        ({"plan": False}, "--plan-output requires --plan"),
        ({"model": None}, "--model is required"),
        ({"task_id": None}, "--task-id is required"),
    ],
)
def test_plan_output_requires_plan_model_and_task_id(
    tmp_path, capsys, overrides, expected
):
    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(_args(tmp_path, **overrides))
    assert exc.value.code == 1
    assert expected in capsys.readouterr().out
    assert not (tmp_path / "plan.json").exists()


def test_stdout_only_plan_remains_unchanged(tmp_path, capsys):
    args = _args(tmp_path, plan_output=None)
    tc_cli.tc_run(args)
    output = capsys.readouterr().out
    assert "Preview Boundaries\n" in output
    assert "Plan artifact:" not in output
    assert "artifact_byte_digest:" not in output


def test_privacy_failure_writes_no_artifact_or_ledger(
    tmp_path, capsys
):
    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(_args(tmp_path, data="123-45-6789"))
    assert exc.value.code == 2
    output = capsys.readouterr().out
    assert "privacy fail-closed" in output
    assert "123-45-6789" not in output
    assert not (tmp_path / "plan.json").exists()
    assert not (tmp_path / ".triagecore").exists()


def test_publish_is_atomic_no_overwrite_and_cleans_staging_file(
    tmp_path, monkeypatch
):
    target = tmp_path / "plan.json"
    target.write_bytes(b"original")
    with pytest.raises(RunPlanArtifactError, match="already exists"):
        publish_artifact(target, b"replacement", protected_directories=())
    assert target.read_bytes() == b"original"

    target.unlink()

    def fail_link(*_args, **_kwargs):
        raise OSError("simulated publication failure")

    monkeypatch.setattr(os, "link", fail_link)
    with pytest.raises(RunPlanArtifactError, match="could not publish"):
        publish_artifact(target, b"partial", protected_directories=())
    assert not target.exists()
    assert list(tmp_path.glob(".plan.json.*.tmp")) == []


def test_plan_output_rejects_missing_parent_and_protected_state(
    tmp_path, capsys, monkeypatch
):
    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(
            _args(tmp_path, plan_output=str(tmp_path / "missing" / "plan.json"))
        )
    assert exc.value.code == 1
    assert "parent does not exist" in capsys.readouterr().out

    protected = tmp_path / "protected"
    protected.mkdir()
    monkeypatch.setattr(
        tc_cli.default_config, "get_ledger_dir", lambda: str(protected)
    )
    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(
            _args(tmp_path, plan_output=str(protected / "plan.json"))
        )
    assert exc.value.code == 1
    assert "inside protected state" in capsys.readouterr().out
    assert not (protected / "plan.json").exists()


def test_plan_output_rejects_symlink_parent(tmp_path, capsys):
    real_parent = tmp_path / "real"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked"
    try:
        linked_parent.symlink_to(real_parent, target_is_directory=True)
    except (NotImplementedError, OSError):
        pytest.skip("directory symlinks are unavailable")

    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(
            _args(tmp_path, plan_output=str(linked_parent / "plan.json"))
        )
    assert exc.value.code == 1
    assert "parent chain is linked" in capsys.readouterr().out
    assert not (real_parent / "plan.json").exists()


def test_parent_link_check_uses_operator_supplied_chain(
    tmp_path, monkeypatch
):
    import triage_core.run_plan_artifact as artifact_module

    supplied_parent = tmp_path / "operator-parent"
    supplied_parent.mkdir()
    monkeypatch.setattr(
        artifact_module,
        "_is_link_or_reparse",
        lambda path: path == supplied_parent,
    )
    with pytest.raises(RunPlanArtifactError, match="parent chain is linked"):
        publish_artifact(
            supplied_parent / "plan.json",
            b"bounded",
            protected_directories=(),
        )
    assert not (supplied_parent / "plan.json").exists()


@pytest.mark.parametrize(
    "artifact_bytes",
    [
        b'{"contract_version":"a","contract_version":"b"}',
        b'{"floating":1.5}',
        b'{"trailing":"newline"}\n',
        b"\xef\xbb\xbf{}",
        b'{"spaced": true}',
    ],
)
def test_noncanonical_or_malformed_artifact_fails_closed(artifact_bytes):
    with pytest.raises(RunPlanArtifactError):
        validate_artifact_bytes(artifact_bytes)


def test_nested_unknown_field_and_unsupported_version_fail_closed(
    tmp_path, capsys
):
    _, _, artifact_bytes, artifact, _, _ = _write_plan(tmp_path, capsys)

    changed = json.loads(artifact_bytes)
    changed["plan_body"]["route_forecast"]["unexpected"] = False
    changed["plan_body_digest"] = sha256_digest(
        canonical_json_bytes(changed["plan_body"])
    )
    with pytest.raises(RunPlanArtifactError, match="closed route forecast"):
        validate_artifact_bytes(canonical_json_bytes(changed))

    changed = json.loads(artifact_bytes)
    changed["canonicalization_version"] = "unknown.v2"
    with pytest.raises(RunPlanArtifactError, match="unsupported canonicalization"):
        validate_artifact_bytes(canonical_json_bytes(changed))


@pytest.mark.parametrize(
    "digest_transform",
    [
        lambda value: value[:-1],
        lambda value: value.upper(),
        lambda value: "sha256:" + ("0" * 64),
    ],
)
def test_confirmation_rejects_inexact_artifact_digest_before_ledger(
    tmp_path, capsys, monkeypatch, digest_transform
):
    args, _, _, _, _, artifact_digest = _write_plan(tmp_path, capsys)
    monkeypatch.setattr(
        tc_cli,
        "TaskLedger",
        lambda *_args, **_kwargs: pytest.fail(
            "ledger must not open before artifact validation"
        ),
    )
    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run_plan_confirm(
            Namespace(
                plan=args.plan_output,
                artifact_digest=digest_transform(artifact_digest),
                ledger_dir=str(tmp_path / "ledger"),
            )
        )
    assert exc.value.code == 1
    assert "Error:" in capsys.readouterr().out
    assert not (tmp_path / "ledger").exists()


def test_mutated_artifact_and_embedded_body_digest_fail_before_ledger(
    tmp_path, capsys, monkeypatch
):
    args, _, artifact_bytes, artifact, _, artifact_digest = _write_plan(
        tmp_path, capsys
    )
    artifact["plan_body"]["cloud_intent"] = True
    mutated = canonical_json_bytes(artifact)
    Path(args.plan_output).write_bytes(mutated)
    monkeypatch.setattr(
        tc_cli,
        "TaskLedger",
        lambda *_args, **_kwargs: pytest.fail(
            "ledger must not open for a mutated artifact"
        ),
    )
    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run_plan_confirm(
            Namespace(
                plan=args.plan_output,
                artifact_digest=sha256_digest(mutated),
                ledger_dir=str(tmp_path / "ledger"),
            )
        )
    assert exc.value.code == 1
    assert "plan body digest mismatch" in capsys.readouterr().out
    assert artifact_digest != sha256_digest(mutated)


def test_confirmation_writes_metadata_only_is_idempotent_and_conflict_safe(
    tmp_path, capsys
):
    first = tmp_path / "first.json"
    args, _, first_bytes, _, body_digest, artifact_digest = _write_plan(
        tmp_path,
        capsys,
        plan_output=str(first),
        prompt="Review raw-confirmation-marker documentation",
        task_id="linked-task",
    )
    ledger_dir = tmp_path / "ledger"
    confirm_args = Namespace(
        plan=args.plan_output,
        artifact_digest=artifact_digest,
        ledger_dir=str(ledger_dir),
    )
    tc_cli.tc_run_plan_confirm(confirm_args)
    assert "Run plan review linkage: confirmed" in capsys.readouterr().out
    tc_cli.tc_run_plan_confirm(confirm_args)
    assert "Run plan review linkage: already_confirmed" in capsys.readouterr().out

    ledger = TaskLedger(ledger_dir=str(ledger_dir))
    events = ledger.get_events("linked-task")
    assert [event["event_type"] for event in events] == [
        "task_created",
        "run_plan_review_confirmed",
    ]
    payload = events[-1]["payload"]
    assert payload["plan_body_digest"] == body_digest
    assert payload["artifact_byte_digest"] == artifact_digest
    for field in (
        "artifact_accepted",
        "cloud_authorization",
        "execution_authority",
        "general_approval",
        "human_review_gate_satisfied",
    ):
        assert payload[field] is False
    ledger_bytes = (ledger_dir / "ledger.jsonl").read_bytes()
    assert b"raw-confirmation-marker" not in ledger_bytes

    second = tmp_path / "second.json"
    second_args, _, _, _, _, second_digest = _write_plan(
        tmp_path,
        capsys,
        plan_output=str(second),
        prompt="Review different bounded documentation",
        task_id="linked-task",
    )
    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run_plan_confirm(
            Namespace(
                plan=second_args.plan_output,
                artifact_digest=second_digest,
                ledger_dir=str(ledger_dir),
            )
        )
    assert exc.value.code == 1
    assert "conflicting plan confirmation" in capsys.readouterr().out
    assert len(ledger.get_events("linked-task")) == 2
    assert first.read_bytes() == first_bytes


def test_task_show_reads_custom_ledger_and_bounds_linkage(
    tmp_path, capsys
):
    args, _, _, _, _, artifact_digest = _write_plan(tmp_path, capsys)
    ledger_dir = tmp_path / "isolated-ledger"
    tc_cli.tc_run_plan_confirm(
        Namespace(
            plan=args.plan_output,
            artifact_digest=artifact_digest,
            ledger_dir=str(ledger_dir),
        )
    )
    capsys.readouterr()

    tc_cli.tc_task_show("task-dd-011", ledger_dir=str(ledger_dir))
    output = capsys.readouterr().out
    assert "Run plan review linkage:" in output
    assert "exact_plan_review_confirmation: present" in output
    assert f"artifact_byte_digest: {artifact_digest}" in output
    assert "execution_authority: false" in output
    assert "execution_linkage: not_implemented" in output
    assert "Review bounded documentation" not in output


def test_ethical_firewall_artifact_and_linkage_are_bounded(
    tmp_path, capsys
):
    sensitive_term = "tribal"
    args, _, artifact_bytes, artifact, _, artifact_digest = _write_plan(
        tmp_path,
        capsys,
        prompt=f"Summarize {sensitive_term} context",
        task_id="firewall-task",
    )
    body = artifact["plan_body"]
    assert body["ethical_firewall"] == {
        "recommended_escalation": "human_only",
        "status": "triggered",
    }
    assert body["route_forecast"]["route"] == "human_handoff"
    assert sensitive_term.encode("utf-8") not in artifact_bytes

    ledger_dir = tmp_path / "ledger"
    tc_cli.tc_run_plan_confirm(
        Namespace(
            plan=args.plan_output,
            artifact_digest=artifact_digest,
            ledger_dir=str(ledger_dir),
        )
    )
    capsys.readouterr()
    tc_cli.tc_task_show("firewall-task", ledger_dir=str(ledger_dir))
    output = capsys.readouterr().out
    assert "ethical_firewall_status: triggered" in output
    assert "route_posture: human_handoff" in output
    assert sensitive_term not in output


def test_task_show_rejects_malformed_confirmation_without_echo(
    tmp_path, capsys
):
    ledger_dir = tmp_path / "ledger"
    ledger = TaskLedger(ledger_dir=str(ledger_dir))
    ledger.append_event(
        "malformed-task",
        "task_created",
        {"title": "bounded", "description": "bounded"},
    )
    ledger.append_event(
        "malformed-task",
        "run_plan_review_confirmed",
        {"route_posture": "raw-malformed-marker"},
    )

    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_task_show("malformed-task", ledger_dir=str(ledger_dir))
    assert exc.value.code == 1
    output = capsys.readouterr().out
    assert "reason=invalid_run_plan_review_linkage" in output
    assert "raw-malformed-marker" not in output


def test_confirmation_fails_closed_on_malformed_ledger(
    tmp_path, capsys
):
    args, _, _, _, _, artifact_digest = _write_plan(tmp_path, capsys)
    ledger_dir = tmp_path / "malformed-ledger"
    ledger_dir.mkdir()
    ledger_path = ledger_dir / "ledger.jsonl"
    original = b"{not-json}\n"
    ledger_path.write_bytes(original)

    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run_plan_confirm(
            Namespace(
                plan=args.plan_output,
                artifact_digest=artifact_digest,
                ledger_dir=str(ledger_dir),
            )
        )
    assert exc.value.code == 1
    assert "could not record plan confirmation" in capsys.readouterr().out
    assert ledger_path.read_bytes() == original


def test_confirmation_fails_closed_on_ledger_write_error(
    tmp_path, capsys, monkeypatch
):
    args, _, _, _, _, artifact_digest = _write_plan(tmp_path, capsys)

    class FailingLedger:
        def get_events(self, _task_id):
            return []

        def get_task(self, _task_id):
            return None

        def append_event(self, *_args, **_kwargs):
            raise OSError("simulated ledger write failure")

    monkeypatch.setattr(
        tc_cli, "TaskLedger", lambda *_args, **_kwargs: FailingLedger()
    )
    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run_plan_confirm(
            Namespace(
                plan=args.plan_output,
                artifact_digest=artifact_digest,
                ledger_dir=str(tmp_path / "ledger"),
            )
        )
    assert exc.value.code == 1
    assert "could not record plan confirmation" in capsys.readouterr().out


def test_plan_write_and_confirmation_trap_backend_network_and_subprocess(
    tmp_path, capsys, monkeypatch
):
    def forbidden(*_args, **_kwargs):
        pytest.fail("forbidden model, backend, network, or subprocess call")

    import triage_core.backends as backends
    from triage_core.client import TriageClient

    monkeypatch.setattr(backends, "create_backend", forbidden)
    monkeypatch.setattr(TriageClient, "run_task", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "check_output", forbidden)
    monkeypatch.chdir(tmp_path)

    args, _, _, _, _, artifact_digest = _write_plan(tmp_path, capsys)
    tc_cli.tc_run_plan_confirm(
        Namespace(
            plan=args.plan_output,
            artifact_digest=artifact_digest,
            ledger_dir=None,
        )
    )
    assert "execution_authority: false" in capsys.readouterr().out
    tc_cli.tc_task_show("task-dd-011")
    assert "execution_linkage: not_implemented" in capsys.readouterr().out


def test_main_dispatches_plan_output_confirm_and_custom_task_show(
    tmp_path, capsys, monkeypatch
):
    plan_path = tmp_path / "plan.json"
    ledger_dir = tmp_path / "ledger"
    monkeypatch.setattr(
        "sys.argv",
        [
            "tc",
            "run",
            "Review bounded docs",
            "--plan",
            "--model",
            "generic-8k",
            "--task-id",
            "parser-task",
            "--plan-output",
            str(plan_path),
        ],
    )
    tc_cli.main()
    _, _, artifact_digest = validate_artifact_bytes(plan_path.read_bytes())
    capsys.readouterr()

    monkeypatch.setattr(
        "sys.argv",
        [
            "tc",
            "run-plan",
            "confirm",
            "--plan",
            str(plan_path),
            "--artifact-digest",
            artifact_digest,
            "--ledger-dir",
            str(ledger_dir),
        ],
    )
    tc_cli.main()
    assert "Run plan review linkage: confirmed" in capsys.readouterr().out

    monkeypatch.setattr(
        "sys.argv",
        [
            "tc",
            "task",
            "show",
            "parser-task",
            "--ledger-dir",
            str(ledger_dir),
        ],
    )
    tc_cli.main()
    assert "execution_linkage: not_implemented" in capsys.readouterr().out
