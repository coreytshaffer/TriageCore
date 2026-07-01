import json
from pathlib import Path

import pytest

from triage_core.experiment_trace_smoke import (
    TRACE_RECORD_FILE_NAME,
    TRACE_SUMMARY_FILE_NAME,
    build_synthetic_experiment_trace,
    export_experiment_trace_smoke,
)


def test_smoke_export_writes_trace_record_and_summary(tmp_path):
    output_dir = tmp_path / "experiment-trace"

    result = export_experiment_trace_smoke(output_dir)

    assert result.trace_id == "trace-route-review-001"
    assert result.trace_path == output_dir / TRACE_RECORD_FILE_NAME
    assert result.summary_path == output_dir / TRACE_SUMMARY_FILE_NAME
    assert result.trace_path.exists()
    assert result.summary_path.exists()


def test_summary_markdown_is_deterministic(tmp_path):
    output_dir = tmp_path / "experiment-trace"

    first = export_experiment_trace_smoke(output_dir)
    first_summary = first.summary_path.read_text(encoding="utf-8")

    second = export_experiment_trace_smoke(output_dir)
    second_summary = second.summary_path.read_text(encoding="utf-8")

    assert first_summary == second_summary
    assert "Token proxy evidence is not measured energy evidence." in first_summary


def test_missing_output_dir_fails_closed():
    with pytest.raises(ValueError, match="output_dir must be provided"):
        export_experiment_trace_smoke(None)

    with pytest.raises(ValueError, match="output_dir must be provided"):
        export_experiment_trace_smoke("   ")


def test_output_dir_pointing_to_file_fails_closed(tmp_path):
    output_file = tmp_path / "not-a-directory.txt"
    output_file.write_text("x", encoding="utf-8")

    with pytest.raises(ValueError, match="output_dir must point to a directory"):
        export_experiment_trace_smoke(output_file)


def test_exported_trace_validates_under_cr092_rules(tmp_path):
    output_dir = tmp_path / "experiment-trace"
    export_experiment_trace_smoke(output_dir)

    data = json.loads((output_dir / TRACE_RECORD_FILE_NAME).read_text(encoding="utf-8"))

    assert data["schema_version"] == "experiment_trace_record.v1"
    assert data["quality_gate_result"]["passed"] is True
    assert data["claim_validity"]["efficiency_claim_valid"] is True
    assert data["lineage"]["candidate_group_id"] == "small_first_escalation"


def test_exported_trace_does_not_claim_measured_energy_savings(tmp_path):
    output_dir = tmp_path / "experiment-trace"
    export_experiment_trace_smoke(output_dir)

    data = json.loads((output_dir / TRACE_RECORD_FILE_NAME).read_text(encoding="utf-8"))

    assert data["claim_validity"]["energy_claim_valid"] is False
    assert data["runtime_efficiency_record"]["measurement_tier"] == "token_proxy"
    assert data["runtime_efficiency_record"]["benefits"]["measured_energy_saved_wh"] is None


def test_repeated_exports_produce_stable_json_content(tmp_path):
    output_dir = tmp_path / "experiment-trace"

    first = export_experiment_trace_smoke(output_dir)
    first_json = first.trace_path.read_text(encoding="utf-8")

    second = export_experiment_trace_smoke(output_dir)
    second_json = second.trace_path.read_text(encoding="utf-8")

    assert first_json == second_json


def test_invalid_synthetic_trace_fails_closed_without_writing_files(tmp_path, monkeypatch):
    output_dir = tmp_path / "experiment-trace"

    def raise_invalid_trace():
        raise ValueError("synthetic trace failed validation")

    monkeypatch.setattr(
        "triage_core.experiment_trace_smoke.build_synthetic_experiment_trace",
        raise_invalid_trace,
    )

    with pytest.raises(ValueError, match="synthetic trace failed validation"):
        export_experiment_trace_smoke(output_dir)

    assert not output_dir.exists()


def test_efficiency_claim_requires_passing_quality_gate():
    with pytest.raises(ValueError, match="failed quality gate"):
        build_synthetic_experiment_trace(
            efficiency_claim_valid=True,
            quality_gate_passed=False,
        )


def test_energy_claim_rejected_for_token_proxy_tier():
    with pytest.raises(ValueError, match="energy measurement tier"):
        build_synthetic_experiment_trace(energy_claim_valid=True)


def test_missing_quality_gate_method_fails_closed():
    with pytest.raises(ValueError, match="quality_gate method must be non-empty"):
        build_synthetic_experiment_trace(quality_gate_method="")

