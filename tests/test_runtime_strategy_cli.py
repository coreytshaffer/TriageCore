import json
import os
import subprocess
import sys
from pathlib import Path

from triage_core.runtime_strategy_evidence import (
    DELTA_REPORT_QUALITY_NOTE,
    DELTA_REPORT_SCHEMA_VERSION,
    build_fixture_strategy_delta_report,
    compute_fixture_strategy_deltas,
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
