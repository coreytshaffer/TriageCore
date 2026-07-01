import json

import pytest

from triage_core.experiment_traces import (
    ExperimentTraceRecord,
    TraceClaimValidity,
    TraceLineage,
)
from triage_core.runtime_backends import RuntimeBackendProfile
from triage_core.runtime_efficiency import (
    EnergyEvidence,
    LatencyMetrics,
    QualityGate,
    RuntimeEfficiencyRecord,
    TokenMetrics,
)
from triage_core.runtime_experiments import (
    ClaimValidity,
    ResultQualityGate,
    RuntimeExperimentResult,
)


def efficiency_record(**overrides):
    values = {
        "run_id": "run-candidate-001",
        "created_at": "2026-06-30T00:00:00Z",
        "task_digest": "sha256:task",
        "task_class": "route_decision",
        "baseline_route": "single_large_model",
        "selected_route": "small_first_escalation",
        "runtime_backend": RuntimeBackendProfile.llama_cpp(
            model_file="qwen.gguf",
            quantization="Q4_K_M",
            context_size=8192,
            threads=12,
            gpu_layers=20,
        ),
        "baseline_tokens": TokenMetrics(prompt_tokens=900, completion_tokens=100),
        "selected_tokens": TokenMetrics(prompt_tokens=500, completion_tokens=120),
        "baseline_latency": LatencyMetrics(total_latency_ms=2100.0),
        "selected_latency": LatencyMetrics(total_latency_ms=1300.0),
        "energy": EnergyEvidence(),
        "measurement_tier": "token_proxy",
        "quality_gate": QualityGate(passed=True, method="route_decision_review_v0"),
    }
    values.update(overrides)
    return RuntimeEfficiencyRecord(**values)


def experiment_result(**overrides):
    values = {
        "experiment_id": "exp-route-review-001",
        "run_id": "result-001",
        "group_id": "small_first_escalation",
        "task_class": "route_decision",
        "repetition_index": 0,
        "runtime_efficiency_record": efficiency_record(),
        "quality_gate": ResultQualityGate(
            passed=True,
            method="route_decision_review_v0",
        ),
        "claim_validity": ClaimValidity(
            efficiency_claim_valid=True,
            token_efficiency_claimed=True,
        ),
        "baseline_group": "single_large_model",
        "baseline_run_id": "run-baseline-001",
    }
    values.update(overrides)
    return RuntimeExperimentResult(**values)


def trace_record(**overrides):
    values = {
        "trace_id": "trace-route-review-001",
        "created_at": "2026-06-30T00:00:00Z",
        "experiment_id": "exp-route-review-001",
        "run_id": "run-candidate-001",
        "task_fixture_digest": "sha256:fixture-001",
        "agent_group_id": "small_first_escalation",
        "runtime_backend_profile_id": "llama_cpp_qwen_7b_q4",
        "runtime_efficiency_record_id": "eff-run-candidate-001",
        "runtime_efficiency_record": efficiency_record(),
        "quality_gate_id": "route_decision_review_v0",
        "quality_gate_result": ResultQualityGate(
            passed=True,
            method="route_decision_review_v0",
        ),
        "claim_validity": TraceClaimValidity(
            efficiency_claim_valid=True,
            energy_claim_valid=False,
            reason="token_proxy_only",
        ),
        "lineage": TraceLineage(
            baseline_group_id="single_large_model",
            candidate_group_id="small_first_escalation",
        ),
        "failure_reason": None,
    }
    values.update(overrides)
    return ExperimentTraceRecord(**values)


def test_trace_record_accepts_valid_candidate_trace():
    trace = trace_record()

    assert trace.to_dict()["experiment_id"] == "exp-route-review-001"
    assert trace.to_dict()["lineage"]["baseline_group_id"] == "single_large_model"


def test_trace_record_requires_experiment_id():
    with pytest.raises(ValueError, match="experiment_id must be non-empty"):
        trace_record(experiment_id="")


def test_efficiency_claim_requires_passed_quality_gate_result():
    with pytest.raises(ValueError, match="passed quality gate result"):
        trace_record(
            quality_gate_result=ResultQualityGate(
                passed=False,
                method="route_decision_review_v0",
                notes="schema mismatch",
            ),
            runtime_efficiency_record=efficiency_record(
                quality_gate=QualityGate(
                    passed=False,
                    method="route_decision_review_v0",
                )
            ),
            failure_reason="schema_mismatch",
            claim_validity=TraceClaimValidity(
                efficiency_claim_valid=True,
                energy_claim_valid=False,
                reason="quality gate failed",
            ),
        )


def test_energy_claim_rejected_without_energy_capable_measurement_tier():
    with pytest.raises(ValueError, match="energy-capable measurement tier"):
        trace_record(
            claim_validity=TraceClaimValidity(
                efficiency_claim_valid=True,
                energy_claim_valid=True,
            )
        )


def test_failed_quality_gate_requires_failure_reason():
    with pytest.raises(ValueError, match="require failure_reason"):
        trace_record(
            quality_gate_result=ResultQualityGate(
                passed=False,
                method="route_decision_review_v0",
            ),
            runtime_efficiency_record=efficiency_record(
                quality_gate=QualityGate(
                    passed=False,
                    method="route_decision_review_v0",
                )
            ),
            claim_validity=TraceClaimValidity(
                efficiency_claim_valid=False,
                energy_claim_valid=False,
                reason="quality gate failed",
            ),
            failure_reason=None,
        )


def test_from_experiment_result_links_existing_result_contract():
    result = experiment_result()

    trace = ExperimentTraceRecord.from_experiment_result(
        trace_id="trace-route-review-001",
        created_at="2026-06-30T00:00:00Z",
        task_fixture_digest="sha256:fixture-001",
        runtime_backend_profile_id="llama_cpp_qwen_7b_q4",
        runtime_efficiency_record_id="eff-run-candidate-001",
        quality_gate_id="route_decision_review_v0",
        claim_validity=TraceClaimValidity(
            efficiency_claim_valid=True,
            energy_claim_valid=False,
            reason="token_proxy_only",
        ),
        result=result,
    )

    assert trace.run_id == result.runtime_efficiency_record.run_id
    assert trace.lineage.candidate_group_id == result.group_id


def test_deterministic_json_output_for_fixed_trace_record():
    trace = trace_record()

    encoded = trace.to_json()
    decoded = json.loads(encoded)

    assert encoded == trace.to_json()
    assert decoded["schema_version"] == "experiment_trace_record.v1"
    assert decoded["runtime_backend_profile_id"] == "llama_cpp_qwen_7b_q4"
