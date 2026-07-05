import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from triage_core.runtime_strategy_evidence import (
    DELTA_REPORT_QUALITY_NOTE,
    DELTA_REPORT_SCHEMA_VERSION,
    RECORDED_DELTA_REPORT_SCHEMA_VERSION,
    build_fixture_strategy_delta_report,
    build_recorded_strategy_delta_report,
    compute_fixture_strategy_deltas,
    load_recorded_strategy_evidence_records,
    render_strategy_delta_report_json,
)
from triage_core.tc_cli import (
    tc_runtime_strategy_recorded_report,
    tc_runtime_strategy_report,
)

RECORDS_EXAMPLE_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "examples"
    / "runtime_strategy_records.example.json"
)
RECORDS_INVALID_EXAMPLE_PATH = (
    RECORDS_EXAMPLE_PATH.parent
    / "runtime_strategy_records.invalid_duplicate_strategy.example.json"
)


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


def _example_records_payload():
    return json.loads(RECORDS_EXAMPLE_PATH.read_text(encoding="utf-8"))


def _write_records(tmp_path, payload) -> Path:
    input_path = tmp_path / "records.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")
    return input_path


def test_recorded_report_renders_text_from_example_file(capsys):
    tc_runtime_strategy_recorded_report(str(RECORDS_EXAMPLE_PATH))

    out = capsys.readouterr().out
    assert "Recorded runtime strategy delta report" in out
    assert "Input records: 3" in out
    assert "Baseline: heavy_only" in out
    assert "Task: recorded-doc-summary-001" in out
    assert "small_first_compact" in out
    assert "-2270" in out
    assert "-51.6%" in out
    assert "token_saving_with_added_handoff" in out
    assert "small_only" in out
    assert "-2750" in out
    assert "token_saving" in out
    assert "quality_not_evaluated" in out
    assert f"Note: {DELTA_REPORT_QUALITY_NOTE}." in out
    out.encode("ascii")


def test_recorded_report_json_is_deterministic_and_matches_builder(capsys):
    tc_runtime_strategy_recorded_report(str(RECORDS_EXAMPLE_PATH), as_json=True)
    first = capsys.readouterr().out
    tc_runtime_strategy_recorded_report(str(RECORDS_EXAMPLE_PATH), as_json=True)
    second = capsys.readouterr().out

    assert first == second
    payload = json.loads(first)
    assert payload["schema_version"] == RECORDED_DELTA_REPORT_SCHEMA_VERSION
    assert payload["kind"] == "recorded_runtime_strategy_delta_report"
    assert payload["record_count"] == 3
    assert payload["strategies"] == [
        "heavy_only",
        "small_first_compact",
        "small_only",
    ]
    expected = build_recorded_strategy_delta_report(
        load_recorded_strategy_evidence_records(RECORDS_EXAMPLE_PATH)
    )
    assert payload == expected


def test_recorded_report_baseline_override(capsys):
    tc_runtime_strategy_recorded_report(
        str(RECORDS_EXAMPLE_PATH),
        baseline="small_only",
    )

    out = capsys.readouterr().out
    assert "Baseline: small_only" in out
    assert "heavy_only" in out
    assert "orchestration_overhead" in out


def test_recorded_report_missing_file_fails_closed(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        tc_runtime_strategy_recorded_report(str(tmp_path / "missing.json"))

    assert exc.value.code == 1
    assert "reason=input_not_found" in capsys.readouterr().out


def test_recorded_report_malformed_json_fails_closed(tmp_path, capsys):
    input_path = tmp_path / "records.json"
    input_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        tc_runtime_strategy_recorded_report(str(input_path))

    assert exc.value.code == 1
    assert "reason=malformed_json" in capsys.readouterr().out


def test_recorded_report_rejects_non_list_top_level(tmp_path, capsys):
    input_path = _write_records(tmp_path, {"records": _example_records_payload()})

    with pytest.raises(SystemExit) as exc:
        tc_runtime_strategy_recorded_report(str(input_path))

    assert exc.value.code == 1
    assert "reason=unsupported_top_level_shape" in capsys.readouterr().out


def test_recorded_report_rejects_invalid_record(tmp_path, capsys):
    payload = _example_records_payload()
    payload[1]["totals"]["estimated_tokens"] = 999999
    input_path = _write_records(tmp_path, payload)

    with pytest.raises(SystemExit) as exc:
        tc_runtime_strategy_recorded_report(str(input_path))

    out = capsys.readouterr().out
    assert exc.value.code == 1
    assert "reason=invalid_record" in out
    assert "record[1]" in out


def test_recorded_report_rejects_unknown_field(tmp_path, capsys):
    payload = _example_records_payload()
    payload[0]["surprise_field"] = "nope"
    input_path = _write_records(tmp_path, payload)

    with pytest.raises(SystemExit) as exc:
        tc_runtime_strategy_recorded_report(str(input_path))

    out = capsys.readouterr().out
    assert exc.value.code == 1
    assert "reason=invalid_record" in out


def test_recorded_report_rejects_raw_content_field(tmp_path, capsys):
    payload = _example_records_payload()
    payload[0]["prompt"] = "raw prompt text must never be accepted"
    input_path = _write_records(tmp_path, payload)

    with pytest.raises(SystemExit) as exc:
        tc_runtime_strategy_recorded_report(str(input_path))

    out = capsys.readouterr().out
    assert exc.value.code == 1
    assert "reason=invalid_record" in out
    assert "raw prompt text must never be accepted" not in out


def test_recorded_report_rejects_mixed_task_ids(tmp_path, capsys):
    payload = _example_records_payload()
    payload[2]["task_id"] = "recorded-other-task-002"
    input_path = _write_records(tmp_path, payload)

    with pytest.raises(SystemExit) as exc:
        tc_runtime_strategy_recorded_report(str(input_path))

    assert exc.value.code == 1
    assert "reason=mixed_task_ids" in capsys.readouterr().out


def test_recorded_report_rejects_duplicate_strategy_example(capsys):
    with pytest.raises(SystemExit) as exc:
        tc_runtime_strategy_recorded_report(str(RECORDS_INVALID_EXAMPLE_PATH))

    assert exc.value.code == 1
    assert "reason=duplicate_strategy" in capsys.readouterr().out


def test_recorded_report_rejects_missing_baseline(capsys):
    with pytest.raises(SystemExit) as exc:
        tc_runtime_strategy_recorded_report(
            str(RECORDS_EXAMPLE_PATH),
            baseline="not_a_strategy",
        )

    assert exc.value.code == 1
    assert "reason=baseline_not_found" in capsys.readouterr().out


def test_recorded_report_rejects_single_record(tmp_path, capsys):
    payload = _example_records_payload()[:1]
    input_path = _write_records(tmp_path, payload)

    with pytest.raises(SystemExit) as exc:
        tc_runtime_strategy_recorded_report(str(input_path))

    assert exc.value.code == 1
    assert "reason=too_few_records" in capsys.readouterr().out


def test_recorded_export_writes_exact_report_artifact(tmp_path, capsys):
    output_path = tmp_path / "recorded-deltas.json"

    tc_runtime_strategy_recorded_report(
        str(RECORDS_EXAMPLE_PATH),
        output=str(output_path),
    )

    out = capsys.readouterr().out
    assert (
        f"Success: wrote recorded runtime strategy delta report to {output_path}"
        in out
    )
    assert "Recorded runtime strategy delta report" not in out
    expected_bytes = render_strategy_delta_report_json(
        build_recorded_strategy_delta_report(
            load_recorded_strategy_evidence_records(RECORDS_EXAMPLE_PATH)
        )
    ).encode("utf-8")
    assert output_path.read_bytes() == expected_bytes
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["kind"] == "recorded_runtime_strategy_delta_report"
    assert payload["schema_version"] == RECORDED_DELTA_REPORT_SCHEMA_VERSION
    # Only the explicitly named output exists; no temp file left behind.
    assert sorted(path.name for path in tmp_path.iterdir()) == [output_path.name]


def test_recorded_export_is_byte_deterministic(tmp_path):
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    tc_runtime_strategy_recorded_report(
        str(RECORDS_EXAMPLE_PATH), output=str(first)
    )
    tc_runtime_strategy_recorded_report(
        str(RECORDS_EXAMPLE_PATH), output=str(second)
    )

    assert first.read_bytes() == second.read_bytes()


def test_recorded_export_artifact_is_metadata_only_and_untimestamped(tmp_path):
    output_path = tmp_path / "recorded.json"

    tc_runtime_strategy_recorded_report(
        str(RECORDS_EXAMPLE_PATH), output=str(output_path)
    )

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


def test_recorded_export_fails_closed_on_existing_file(tmp_path, capsys):
    output_path = tmp_path / "recorded.json"
    output_path.write_text("preserve-me\n", encoding="utf-8")

    with pytest.raises(SystemExit) as exc:
        tc_runtime_strategy_recorded_report(
            str(RECORDS_EXAMPLE_PATH), output=str(output_path)
        )

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "reason=output_exists" in out
    assert "Pass --force to overwrite." in out
    assert output_path.read_text(encoding="utf-8") == "preserve-me\n"


def test_recorded_export_force_overwrites_existing_file(tmp_path):
    output_path = tmp_path / "recorded.json"
    output_path.write_text("stale artifact\n", encoding="utf-8")

    tc_runtime_strategy_recorded_report(
        str(RECORDS_EXAMPLE_PATH), output=str(output_path), force=True
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["kind"] == "recorded_runtime_strategy_delta_report"


def test_recorded_export_fails_closed_when_parent_directory_missing(
    tmp_path, capsys
):
    output_path = tmp_path / "missing" / "recorded.json"

    with pytest.raises(SystemExit) as exc:
        tc_runtime_strategy_recorded_report(
            str(RECORDS_EXAMPLE_PATH), output=str(output_path)
        )

    assert exc.value.code == 1
    assert "reason=output_directory_missing" in capsys.readouterr().out
    assert not (tmp_path / "missing").exists()


def test_recorded_export_flag_combinations_rejected(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(repo_root)
        if not existing_pythonpath
        else str(repo_root) + os.pathsep + existing_pythonpath
    )
    base_args = [
        sys.executable,
        "-m",
        "triage_core.tc_cli",
        "runtime-strategy",
        "recorded-report",
        "--input",
        str(RECORDS_EXAMPLE_PATH),
    ]

    exclusive = subprocess.run(
        base_args + ["--json", "--output", str(tmp_path / "recorded.json")],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    assert exclusive.returncode == 2
    assert "not allowed with argument" in exclusive.stderr

    force_without_output = subprocess.run(
        base_args + ["--force"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
    )
    assert force_without_output.returncode == 2
    assert "--force requires --output" in force_without_output.stderr
    assert not (tmp_path / "recorded.json").exists()


def test_recorded_export_does_not_modify_input_or_create_extra_files(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    input_path = workspace / "records.json"
    input_bytes = RECORDS_EXAMPLE_PATH.read_bytes()
    input_path.write_bytes(input_bytes)
    output_path = workspace / "recorded-deltas.json"

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
            "recorded-report",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        cwd=workspace,
        env=env,
    )

    assert result.returncode == 0
    assert "Success: wrote recorded runtime strategy delta report" in result.stdout
    assert input_path.read_bytes() == input_bytes
    # Exactly the input and the explicitly named output; no ledger,
    # no .triagecore, no temp files.
    assert sorted(path.name for path in workspace.iterdir()) == [
        output_path.name,
        input_path.name,
    ]


def test_recorded_report_cli_is_read_only(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    input_path = workspace / "records.json"
    input_bytes = RECORDS_EXAMPLE_PATH.read_bytes()
    input_path.write_bytes(input_bytes)

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
            "recorded-report",
            "--input",
            str(input_path),
        ],
        capture_output=True,
        text=True,
        cwd=workspace,
        env=env,
    )

    assert result.returncode == 0
    assert "Recorded runtime strategy delta report" in result.stdout
    # Input file untouched, no ledger or other files created.
    assert input_path.read_bytes() == input_bytes
    assert sorted(path.name for path in workspace.iterdir()) == ["records.json"]


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
