import json

import pytest

from triage_core.runtime_strategy_evidence import (
    SCHEMA_VERSION,
    RuntimeStrategyEvidenceRecord,
    RuntimeStrategyQualityGate,
    RuntimeStrategyStep,
    RuntimeStrategyTotals,
    build_runtime_strategy_evidence_record,
    build_small_first_compact_fixture_record,
    runtime_strategy_evidence_from_mapping,
)


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
