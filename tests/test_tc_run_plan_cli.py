from argparse import Namespace
import builtins
import subprocess

import pytest

from triage_core import tc_cli
from triage_core.classifier import TaskClassifier


def _args(prompt="Summarize the documentation", **overrides):
    values = {
        "prompt": prompt,
        "files": [],
        "data": None,
        "privacy": "local_only",
        "allow_cloud": False,
        "ledger_dir": None,
        "task_id": None,
        "output": None,
        "print_output": False,
        "no_ledger": False,
        "plan": True,
        "model": "generic-8k",
    }
    values.update(overrides)
    return Namespace(**values)


def test_plan_renders_all_sections_without_execution_or_ledger(tmp_path, monkeypatch, capsys):
    from triage_core.client import TriageClient

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        TriageClient,
        "run_task",
        lambda *args, **kwargs: pytest.fail("run_task must not be called"),
    )

    raw_prompt = "Summarize UNIQUE_RAW_PROMPT documentation"
    tc_cli.tc_run(_args(prompt=raw_prompt))

    out = capsys.readouterr().out
    for section in (
        "Task", "Context", "Privacy and Egress", "Logical Route",
        "Escalation Conditions", "Expected Verification", "Preview Boundaries",
    ):
        assert f"{section}\n" in out
    assert "output_validation: not_configured" in out
    assert "backend_probe_performed: false" in out
    assert raw_prompt not in out
    assert not (tmp_path / ".triagecore").exists()


def test_plan_context_sources_order_and_budget_match_existing_calculation(
    tmp_path, capsys
):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("a" * 40, encoding="utf-8")
    second.write_text("b" * 80, encoding="utf-8")

    tc_cli.tc_run(
        _args(files=[str(first), str(second)], data="c" * 20)
    )

    out = capsys.readouterr().out
    assert out.index(str(first)) < out.index(str(second))
    assert f"{first} (40 chars)" in out
    assert f"{second} (80 chars)" in out
    assert "inline_data_characters: 20" in out
    assert "model_profile: generic-8k" in out
    assert "usable_input_budget: 6912" in out


def test_plan_over_budget_and_repeated_output_is_identical(capsys):
    args = _args(data="x" * 30000)
    tc_cli.tc_run(args)
    first = capsys.readouterr().out
    tc_cli.tc_run(args)
    second = capsys.readouterr().out

    assert "status: over_budget" in first
    assert first == second


@pytest.mark.parametrize(
    ("privacy", "allow_cloud", "posture"),
    [
        ("external_safe", False, "eligible_but_not_authorized"),
        ("external_safe", True, "authorized_for_consideration"),
        ("public", False, "eligible_but_not_authorized"),
        ("public", True, "authorized_for_consideration"),
    ],
)
def test_plan_distinguishes_egress_from_cloud_authorization(
    privacy, allow_cloud, posture, capsys
):
    tc_cli.tc_run(_args(privacy=privacy, allow_cloud=allow_cloud))
    out = capsys.readouterr().out
    assert "egress_eligible: true" in out.lower()
    assert f"cloud_posture: {posture}" in out


def test_plan_privacy_failure_is_bounded_and_does_not_echo_match(capsys):
    secret = "123-45-6789"
    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(_args(data=secret))
    out = capsys.readouterr().out
    assert exc.value.code == 2
    assert "finding_codes=" in out
    assert secret not in out
    assert "SSN pattern" not in out


def test_plan_rejects_local_only_cloud_and_execution_flags(capsys):
    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(_args(allow_cloud=True))
    assert exc.value.code == 1
    assert "--allow-cloud cannot be used" in capsys.readouterr().out

    for field, value, flag in (
        ("output", "result.txt", "--output"),
        ("print_output", True, "--print"),
        ("ledger_dir", "ledger", "--ledger-dir"),
        ("no_ledger", True, "--no-ledger"),
    ):
        with pytest.raises(SystemExit) as exc:
            tc_cli.tc_run(_args(**{field: value}))
        assert exc.value.code == 1
        assert flag in capsys.readouterr().out


def test_plan_requires_known_model(capsys):
    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(_args(model=None))
    assert exc.value.code == 1
    assert "--model is required" in capsys.readouterr().out

    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(_args(model="missing-profile"))
    assert exc.value.code == 1
    assert "Unknown model profile" in capsys.readouterr().out


def test_plan_preserves_existing_ledger_bytes(tmp_path):
    ledger_dir = tmp_path / ".triagecore"
    ledger_dir.mkdir()
    ledger = ledger_dir / "ledger.jsonl"
    original = b'{"existing":true}\n'
    ledger.write_bytes(original)

    tc_cli.tc_run(_args())

    assert ledger.read_bytes() == original


def test_deterministic_classifier_does_not_construct_backend(monkeypatch):
    import triage_core.backends as backends

    monkeypatch.setattr(
        backends,
        "create_backend",
        lambda *args, **kwargs: pytest.fail("backend construction is forbidden"),
    )
    assert TaskClassifier.classify_deterministic("Update the docs") == "docs_update"


@pytest.mark.parametrize(
    ("prompt", "route", "review_required"),
    [
        ("Update the docs", "local_fast", "false"),
        ("Design the architecture", "local_heavy", "true"),
        ("Perform a security review", "human_handoff", "true"),
    ],
)
def test_plan_renders_deterministic_route_shapes(
    prompt, route, review_required, capsys
):
    tc_cli.tc_run(_args(prompt=prompt))
    out = capsys.readouterr().out.lower()
    assert f"proposed_route: {route}" in out
    assert f"human_review_required: {review_required}" in out


def test_plan_reports_specialist_risk_conditions_and_model_binding(capsys):
    tc_cli.tc_run(_args(prompt="Update the docs"))
    docs_out = capsys.readouterr().out
    assert "specialist_model_forecast: deepseek/deepseek-r1-0528-qwen3-8b" in docs_out
    assert (
        "configured_backend_binding: "
        + tc_cli.default_config.get_backend_type()
        + ":deepseek/deepseek-r1-0528-qwen3-8b"
    ) in docs_out

    tc_cli.tc_run(_args(prompt="pip install requests"))
    package_out = capsys.readouterr().out
    assert "deterministic_risk_level: medium" in package_out
    assert "recommended_profile: workspace-write-with-approval" in package_out
    assert "medium_risk_route_depends_on_unobserved_internet_state" in package_out

    tc_cli.tc_run(_args(prompt="Delete all files"))
    high_risk_out = capsys.readouterr().out
    assert "deterministic_risk_level: high" in high_risk_out
    assert "proposed_route: human_handoff" in high_risk_out
    assert "high_risk_requires_governed_handoff" in high_risk_out

    tc_cli.tc_run(_args(data="x" * 30001, model="generic-128k"))
    large_out = capsys.readouterr().out
    assert "large_context_route_depends_on_unobserved_internet_state" in large_out


def test_plan_output_escapes_unicode_path_task_id_and_configured_model(
    tmp_path, monkeypatch, capsys
):
    source = tmp_path / "caf\u00e9-\u2603.txt"
    source.write_text("bounded", encoding="utf-8")
    monkeypatch.setattr(
        tc_cli.default_config, "get_backend_type", lambda: "l\u00f6cal-\u2603"
    )

    tc_cli.tc_run(
        _args(
            prompt="Refactor this",
            files=[str(source)],
            task_id="t\u00e2sk-\u2603",
        )
    )

    out = capsys.readouterr().out
    out.encode("ascii")
    assert "t\\xe2sk-\\u2603" in out
    assert "caf\\xe9-\\u2603.txt" in out
    assert "l\\xf6cal-\\u2603:" in out


def test_plan_traps_network_subprocess_backend_ledger_and_writes(
    tmp_path, monkeypatch, capsys
):
    import socket
    import triage_core.backends as backends
    import triage_core.project_steward as project_steward

    def forbidden(*args, **kwargs):
        pytest.fail("forbidden planning side effect")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "check_output", forbidden)
    monkeypatch.setattr(backends, "create_backend", forbidden)
    monkeypatch.setattr(tc_cli, "TaskLedger", forbidden)
    monkeypatch.setattr(project_steward, "TaskLedger", forbidden)
    from triage_core.client import TriageClient
    monkeypatch.setattr(TriageClient, "run_task", forbidden)

    real_open = builtins.open

    def read_only_open(file, mode="r", *args, **kwargs):
        if any(marker in mode for marker in ("w", "a", "x", "+")):
            pytest.fail("planning attempted a file write")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", read_only_open)
    tc_cli.tc_run(_args())
    assert "execution_performed: false" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_plan_forecasts_ethical_firewall_without_echo_or_ledger(
    monkeypatch, capsys
):
    import triage_core.project_steward as project_steward

    sensitive_term = "tribal"
    monkeypatch.setattr(
        project_steward,
        "TaskLedger",
        lambda *args, **kwargs: pytest.fail(
            "ethical-firewall preview must not read the ledger"
        ),
    )

    tc_cli.tc_run(_args(prompt=f"Summarize {sensitive_term} context"))

    out = capsys.readouterr().out.lower()
    assert sensitive_term not in out
    assert "ethical_firewall_status: triggered" in out
    assert "ethical_firewall_policy_source: configured_or_hardcoded" in out
    assert "ethical_firewall_recommended_escalation: human_only" in out
    assert "proposed_route: human_handoff" in out
    assert "human_review_required: true" in out
    assert "configured_backend_binding: none" in out


def test_main_parser_dispatches_plan(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        [
            "tc",
            "run",
            "Update the docs",
            "--plan",
            "--model",
            "generic-8k",
        ],
    )
    tc_cli.main()
    assert "Preview Boundaries\n" in capsys.readouterr().out
