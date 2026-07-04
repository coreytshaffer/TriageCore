import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from triage_core.runtime_strategy_evidence import (
    DELTA_REPORT_QUALITY_NOTE,
    DELTA_REPORT_SCHEMA_VERSION,
    build_fixture_strategy_delta_report,
    compute_fixture_strategy_deltas,
    render_strategy_delta_report_json,
)
from triage_core.tc_cli import tc_runtime_strategy_report


def test_report_text_output_shows_fixture_deltas(capsys):
    tc_runtime_strategy_report()

    out = capsys.readouterr().out
    assert "Runtime strategy delta report" in out
    assert "Baseline: heavy_only" in out
    assert "Task: fixture-doc-summary-001" in out
    assert "small_first_compact" in out
    assert "-2470" in out
    assert "-51.5%" in out
    assert "token_saving_with_added_handoff" in out
    assert "small_only" in out
    assert "-3080" in out
    assert "-64.2%" in out
    assert "over_orchestrated" in out
    assert "+1790" in out
    assert "+37.3%" in out
    assert "orchestration_overhead" in out
    assert "Quality gates: not_evaluated" in out
    assert f"Note: {DELTA_REPORT_QUALITY_NOTE}." in out
    assert "Quality Effect" in out
    assert out.count("quality_not_evaluated") == 3


def test_report_json_output_matches_computed_deltas(capsys):
    tc_runtime_strategy_report(as_json=True)

    payload = json.loads(capsys.readouterr().out)
    assert payload["schema_version"] == DELTA_REPORT_SCHEMA_VERSION
    assert payload["kind"] == "runtime_strategy_delta_report"
    assert payload["baseline_strategy"] == "heavy_only"
    assert payload["quality_gate_statuses"] == ["not_evaluated"]
    assert payload["deltas"] == [
        delta.to_dict() for delta in compute_fixture_strategy_deltas()
    ]


def test_report_is_deterministic():
    assert (
        build_fixture_strategy_delta_report()
        == build_fixture_strategy_delta_report()
    )


def test_report_text_is_ascii_only(capsys):
    tc_runtime_strategy_report()

    out = capsys.readouterr().out
    # Windows consoles commonly use cp1252; the report must never crash there.
    out.encode("ascii")


def test_export_writes_exact_report_artifact(tmp_path, capsys):
    output_path = tmp_path / "runtime-strategy-deltas.json"

    tc_runtime_strategy_report(output=str(output_path))

    out = capsys.readouterr().out
    assert f"Success: wrote runtime strategy delta report to {output_path}" in out
    expected_bytes = render_strategy_delta_report_json(
        build_fixture_strategy_delta_report()
    ).encode("utf-8")
    assert output_path.read_bytes() == expected_bytes
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == DELTA_REPORT_SCHEMA_VERSION
    assert payload["deltas"] == [
        delta.to_dict() for delta in compute_fixture_strategy_deltas()
    ]
    # No temp file left behind.
    assert sorted(path.name for path in tmp_path.iterdir()) == [output_path.name]


def test_export_is_byte_deterministic(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    tc_runtime_strategy_report(output=str(first))
    tc_runtime_strategy_report(output=str(second))

    assert first.read_bytes() == second.read_bytes()


def test_export_artifact_is_metadata_only_and_untimestamped(tmp_path):
    output_path = tmp_path / "report.json"

    tc_runtime_strategy_report(output=str(output_path))

    content = output_path.read_text(encoding="utf-8")
    for forbidden in (
        "prompt",
        "raw_context",
        "model_output",
        "generated",
        "timestamp",
        "created_at",
    ):
        assert forbidden not in content


def test_export_fails_closed_on_existing_file(tmp_path, capsys):
    output_path = tmp_path / "report.json"
    output_path.write_text("preserve-me\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        tc_runtime_strategy_report(output=str(output_path))

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "reason=output_exists" in out
    assert "Pass --force to overwrite." in out
    assert output_path.read_text(encoding="utf-8") == "preserve-me\n"


def test_export_force_overwrites_existing_file(tmp_path):
    output_path = tmp_path / "report.json"
    output_path.write_text("stale artifact\n", encoding="utf-8")

    tc_runtime_strategy_report(output=str(output_path), force=True)

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["kind"] == "runtime_strategy_delta_report"


def test_export_fails_closed_when_parent_directory_missing(tmp_path, capsys):
    output_path = tmp_path / "missing" / "report.json"

    with pytest.raises(SystemExit) as exc:
        tc_runtime_strategy_report(output=str(output_path))

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "reason=output_directory_missing" in out
    assert not (tmp_path / "missing").exists()


def test_json_and_output_flags_are_mutually_exclusive(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(repo_root)
        if not existing_pythonpath
        else str(repo_root) + os.pathsep + existing_pythonpath
    )

    exclusive = subprocess.run(
        [
            sys.executable,
            "-m",
            "triage_core.tc_cli",
            "runtime-strategy",
            "report",
            "--json",
            "--output",
            str(tmp_path / "report.json"),
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    assert exclusive.returncode == 2
    assert "not allowed with argument" in exclusive.stderr

    force_without_output = subprocess.run(
        [
            sys.executable,
            "-m",
            "triage_core.tc_cli",
            "runtime-strategy",
            "report",
            "--force",
        ],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    assert force_without_output.returncode == 2
    assert "--force requires --output" in force_without_output.stderr
    assert not (tmp_path / "report.json").exists()


def test_report_cli_is_read_only(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(repo_root)
        if not existing_pythonpath
        else str(repo_root) + os.pathsep + existing_pythonpath
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "triage_core.tc_cli",
            "runtime-strategy",
            "report",
        ],
        capture_output=True,
        text=True,
        cwd=workspace,
        env=env,
    )

    assert result.returncode == 0
    assert "Runtime strategy delta report" in result.stdout
    assert list(workspace.iterdir()) == []
