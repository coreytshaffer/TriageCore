import json

import pytest

from triage_core.runtime_strategy_evidence import (
    DELTA_SCHEMA_VERSION,
    SCHEMA_VERSION,
    RuntimeStrategyEvidenceRecord,
    RuntimeStrategyQualityGate,
    RuntimeStrategyStep,
    RuntimeStrategyTotals,
    build_runtime_strategy_evidence_record,
    build_strategy_comparison_fixture,
    build_strategy_comparison_fixture_records,
    build_small_first_compact_fixture_record,
    compute_fixture_strategy_deltas,
    compute_strategy_delta,
    runtime_strategy_evidence_from_mapping,
)


def _fixture_records_by_strategy():
    return {
        record.strategy: record
        for record in build_strategy_comparison_fixture_records()
    }


def test_small_first_compact_fixture_record_shape():
    record = build_small_first_compact_fixture_record()
    data = record.to_dict()

    assert data["schema_version"] == SCHEMA_VERSION
    assert data["kind"] == "runtime_strategy_evidence"
    assert data["task_id"] == "fixture-doc-summary-001"
    assert data["strategy"] == "small_first_compact"
    assert data["totals"] == {
        "estimated_tokens": 2330,
        "model_calls": 2,
        "handoffs": 1,
    }
    assert data["quality_gate"] == {
        "status": "not_evaluated",
        "reason": "measurement-only strategy fixture",
    }
    assert data["steps"][0]["backend"] == "ollama"
    assert data["steps"][1]["backend"] == "lm_studio"


def test_record_json_is_deterministic_and_metadata_only():
    record = build_small_first_compact_fixture_record()

    encoded = record.to_json()

    assert encoded == record.to_json()
    assert json.loads(encoded)["totals"]["estimated_tokens"] == 2330
    assert "raw_context" not in encoded
    assert "model_output" not in encoded
    assert "prompt" not in encoded


def test_builder_derives_totals_from_steps():
    record = build_runtime_strategy_evidence_record(
        task_id="fixture-002",
        strategy="heavy_only",
        steps=[
            RuntimeStrategyStep(
                role="reviewer",
                backend="lm_studio",
                model_profile="heavy_reviewer",
                estimated_input_tokens=1800,
                estimated_output_tokens=600,
                schema_valid=True,
            )
        ],
        handoffs=0,
        quality_gate_status="not_evaluated",
        quality_gate_reason="measurement-only fixture",
    )

    assert record.totals.estimated_tokens == 2400
    assert record.totals.model_calls == 1
    assert record.totals.handoffs == 0


def test_rejects_totals_that_do_not_match_steps():
    with pytest.raises(ValueError, match="estimated_tokens"):
        RuntimeStrategyEvidenceRecord(
            task_id="fixture-003",
            strategy="small_first_compact",
            steps=[
                RuntimeStrategyStep(
                    role="extractor",
                    backend="ollama",
                    model_profile="small_extractor",
                    estimated_input_tokens=100,
                    estimated_output_tokens=20,
                    schema_valid=True,
                )
            ],
            totals=RuntimeStrategyTotals(
                estimated_tokens=999,
                model_calls=1,
                handoffs=0,
            ),
            quality_gate=RuntimeStrategyQualityGate(
                status="not_evaluated",
                reason="test",
            ),
        )


def test_rejects_handoffs_above_step_transitions():
    with pytest.raises(ValueError, match="handoffs"):
        build_runtime_strategy_evidence_record(
            task_id="fixture-004",
            strategy="over_orchestrated",
            steps=[
                RuntimeStrategyStep(
                    role="reviewer",
                    backend="lm_studio",
                    model_profile="heavy_reviewer",
                    estimated_input_tokens=100,
                    estimated_output_tokens=20,
                    schema_valid=True,
                )
            ],
            handoffs=1,
            quality_gate_status="not_evaluated",
            quality_gate_reason="test",
        )


def test_mapping_loader_rejects_raw_persistent_content_keys():
    payload = build_small_first_compact_fixture_record().to_dict()
    payload["raw_model_output"] = "secret model text"

    with pytest.raises(ValueError, match="raw_model_output|forbidden"):
        runtime_strategy_evidence_from_mapping(payload)


def test_mapping_loader_round_trips_record():
    original = build_small_first_compact_fixture_record()

    loaded = runtime_strategy_evidence_from_mapping(original.to_dict())

    assert loaded.to_dict() == original.to_dict()

def test_strategy_comparison_fixture_contains_expected_strategies():
    records = build_strategy_comparison_fixture_records()

    assert [record.strategy for record in records] == [
        "heavy_only",
        "small_first_compact",
        "small_only",
        "over_orchestrated",
    ]
    assert {record.task_id for record in records} == {"fixture-doc-summary-001"}
    assert {record.quality_gate.status for record in records} == {"not_evaluated"}


def test_strategy_comparison_fixture_derives_per_strategy_metrics():
    comparison = build_strategy_comparison_fixture()
    data = comparison.to_dict()
    strategies = {item["strategy"]: item for item in data["strategies"]}

    assert strategies["heavy_only"] == {
        "strategy": "heavy_only",
        "estimated_total_tokens": 4800,
        "model_calls": 1,
        "handoffs": 0,
        "quality_gate_status": "not_evaluated",
        "estimated_tokens_by_backend": {"lm_studio": 4800},
    }
    assert strategies["small_first_compact"] == {
        "strategy": "small_first_compact",
        "estimated_total_tokens": 2330,
        "model_calls": 2,
        "handoffs": 1,
        "quality_gate_status": "not_evaluated",
        "estimated_tokens_by_backend": {"lm_studio": 950, "ollama": 1380},
    }
    assert strategies["small_only"] == {
        "strategy": "small_only",
        "estimated_total_tokens": 1720,
        "model_calls": 1,
        "handoffs": 0,
        "quality_gate_status": "not_evaluated",
        "estimated_tokens_by_backend": {"ollama": 1720},
    }


def test_over_orchestrated_fixture_is_negative_control():
    comparison = build_strategy_comparison_fixture()
    strategies = {item["strategy"]: item for item in comparison.to_dict()["strategies"]}

    assert strategies["over_orchestrated"]["estimated_total_tokens"] == 6590
    assert strategies["over_orchestrated"]["model_calls"] == 4
    assert strategies["over_orchestrated"]["handoffs"] == 3
    assert strategies["over_orchestrated"]["estimated_total_tokens"] > strategies["heavy_only"]["estimated_total_tokens"]
    assert strategies["over_orchestrated"]["estimated_total_tokens"] > strategies["small_first_compact"]["estimated_total_tokens"]


def test_strategy_comparison_fixture_derives_backend_totals():
    comparison = build_strategy_comparison_fixture()

    assert comparison.strategy_names() == [
        "heavy_only",
        "small_first_compact",
        "small_only",
        "over_orchestrated",
    ]
    assert comparison.estimated_tokens_by_backend() == {
        "lm_studio": 8100,
        "ollama": 7340,
    }


def test_small_first_compact_delta_beats_heavy_only_baseline():
    records = _fixture_records_by_strategy()

    delta = compute_strategy_delta(
        records["heavy_only"],
        records["small_first_compact"],
    )
    data = delta.to_dict()

    assert data["schema_version"] == DELTA_SCHEMA_VERSION
    assert data["kind"] == "runtime_strategy_delta"
    assert data["task_id"] == "fixture-doc-summary-001"
    assert data["baseline_strategy"] == "heavy_only"
    assert data["candidate_strategy"] == "small_first_compact"
    assert data["estimated_tokens_delta"] == -2470
    assert data["estimated_percent_delta"] == -51.5
    assert data["model_calls_delta"] == 1
    assert data["handoffs_delta"] == 1
    assert data["interpretation"] == "token_saving_with_added_handoff"
    assert data["invalid_reason"] is None


def test_over_orchestrated_delta_loses_to_heavy_only_baseline():
    records = _fixture_records_by_strategy()

    delta = compute_strategy_delta(
        records["heavy_only"],
        records["over_orchestrated"],
    )
    data = delta.to_dict()

    assert data["estimated_tokens_delta"] == 1790
    assert data["estimated_percent_delta"] == 37.3
    assert data["model_calls_delta"] == 3
    assert data["handoffs_delta"] == 3
    assert data["interpretation"] == "orchestration_overhead"


def test_small_only_delta_is_token_saving_without_added_handoff():
    records = _fixture_records_by_strategy()

    delta = compute_strategy_delta(records["heavy_only"], records["small_only"])
    data = delta.to_dict()

    assert data["estimated_tokens_delta"] == -3080
    assert data["estimated_percent_delta"] == -64.2
    assert data["model_calls_delta"] == 0
    assert data["handoffs_delta"] == 0
    assert data["interpretation"] == "token_saving"


def test_equal_token_totals_are_token_neutral():
    baseline = _fixture_records_by_strategy()["heavy_only"]
    candidate = build_runtime_strategy_evidence_record(
        task_id=baseline.task_id,
        strategy="heavy_only_alternate",
        steps=[
            RuntimeStrategyStep(
                role="reviewer",
                backend="lm_studio",
                model_profile="heavy_reviewer_alt",
                estimated_input_tokens=4200,
                estimated_output_tokens=600,
                schema_valid=True,
            )
        ],
        handoffs=0,
        quality_gate_status="not_evaluated",
        quality_gate_reason="token-neutral synthetic candidate",
    )

    delta = compute_strategy_delta(baseline, candidate)

    assert delta.estimated_tokens_delta == 0
    assert delta.estimated_percent_delta == 0.0
    assert delta.interpretation == "token_neutral"


def test_task_id_mismatch_is_invalid_comparison():
    records = _fixture_records_by_strategy()
    other_task = build_runtime_strategy_evidence_record(
        task_id="fixture-other-task-002",
        strategy="small_only",
        steps=[
            RuntimeStrategyStep(
                role="summarizer",
                backend="ollama",
                model_profile="small_summarizer",
                estimated_input_tokens=100,
                estimated_output_tokens=20,
                schema_valid=True,
            )
        ],
        handoffs=0,
        quality_gate_status="not_evaluated",
        quality_gate_reason="mismatched task fixture",
    )

    delta = compute_strategy_delta(records["heavy_only"], other_task)
    data = delta.to_dict()

    assert data["interpretation"] == "invalid_comparison"
    assert data["invalid_reason"] == "task_id_mismatch"
    assert data["task_id"] is None
    assert data["estimated_tokens_delta"] is None
    assert data["estimated_percent_delta"] is None


def test_identical_strategy_is_invalid_comparison():
    records = _fixture_records_by_strategy()

    delta = compute_strategy_delta(records["heavy_only"], records["heavy_only"])

    assert delta.interpretation == "invalid_comparison"
    assert delta.invalid_reason == "identical_strategy"
    assert delta.estimated_tokens_delta is None


def test_zero_baseline_tokens_is_invalid_comparison():
    zero_baseline = build_runtime_strategy_evidence_record(
        task_id="fixture-doc-summary-001",
        strategy="zero_baseline",
        steps=[
            RuntimeStrategyStep(
                role="noop",
                backend="ollama",
                model_profile="noop_profile",
                estimated_input_tokens=0,
                estimated_output_tokens=0,
                schema_valid=True,
            )
        ],
        handoffs=0,
        quality_gate_status="not_evaluated",
        quality_gate_reason="zero-token synthetic baseline",
    )
    candidate = _fixture_records_by_strategy()["small_only"]

    delta = compute_strategy_delta(zero_baseline, candidate)

    assert delta.interpretation == "invalid_comparison"
    assert delta.invalid_reason == "zero_baseline_tokens"
    assert delta.estimated_percent_delta is None


def test_fixture_strategy_deltas_cover_all_candidates():
    deltas = {
        delta.candidate_strategy: delta
        for delta in compute_fixture_strategy_deltas()
    }

    assert set(deltas) == {"small_first_compact", "small_only", "over_orchestrated"}
    assert all(
        delta.baseline_strategy == "heavy_only" for delta in deltas.values()
    )
    assert deltas["small_first_compact"].interpretation == (
        "token_saving_with_added_handoff"
    )
    assert deltas["small_only"].interpretation == "token_saving"
    assert deltas["over_orchestrated"].interpretation == "orchestration_overhead"


def test_delta_json_is_deterministic_and_metadata_only():
    records = _fixture_records_by_strategy()

    delta = compute_strategy_delta(
        records["heavy_only"],
        records["small_first_compact"],
    )
    encoded = delta.to_json()

    assert encoded == delta.to_json()
    assert "prompt" not in encoded
    assert "raw_context" not in encoded
    assert "model_output" not in encoded
