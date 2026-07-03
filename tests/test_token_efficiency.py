import json

from triage_core.token_efficiency import (
    SCHEMA_VERSION,
    build_smoke_test_record,
    build_token_efficiency_record,
    smoke_fixture_paths,
)


def test_smoke_fixture_paths_exist():
    paths = smoke_fixture_paths()

    assert paths["baseline"].exists()
    assert paths["candidate"].exists()



def test_smoke_record_matches_expected_totals_and_savings():
    record = build_smoke_test_record()

    assert record.schema_version == SCHEMA_VERSION
    assert record.kind == "token_efficiency"
    assert record.task_id == "fixture-doc-summary-001"
    assert record.baseline.strategy == "raw_context"
    assert record.baseline.estimated_input_tokens == 4200
    assert record.baseline.estimated_output_tokens == 600
    assert record.baseline.estimated_total_tokens == 4800
    assert record.candidate.strategy == "compact_context"
    assert record.candidate.estimated_input_tokens == 1300
    assert record.candidate.estimated_output_tokens == 500
    assert record.candidate.estimated_total_tokens == 1800
    assert record.savings.estimated_tokens_saved == 3000
    assert record.savings.estimated_percent_saved == 62.5
    assert record.quality_gate.status == "not_evaluated"



def test_custom_record_uses_character_count_estimator():
    record = build_token_efficiency_record(
        task_id="tiny-task",
        baseline_strategy="raw_context",
        baseline_text="A" * 16,
        baseline_output_tokens=8,
        candidate_strategy="compact_context",
        candidate_text="B" * 8,
        candidate_output_tokens=4,
        quality_gate_status="not_evaluated",
        quality_gate_reason="deterministic test",
    )

    assert record.baseline.estimated_input_tokens == 4
    assert record.candidate.estimated_input_tokens == 2
    assert record.savings.estimated_tokens_saved == 6
    assert record.savings.estimated_percent_saved == 50.0



def test_record_json_is_deterministic_and_contains_no_raw_context_text():
    record = build_smoke_test_record()

    encoded = record.to_json()
    decoded = json.loads(encoded)

    assert encoded == record.to_json()
    assert decoded["savings"]["estimated_tokens_saved"] == 3000
    assert "baseline context for token efficiency smoke test" not in encoded
    assert "compact context for token efficiency smoke test" not in encoded
