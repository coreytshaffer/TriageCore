import json

import pytest

from triage_core.agent_group_profiles import AgentGroupProfile, ExperimentAgent
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
    ExperimentQualityGate,
    MeasurementConfig,
    ResultQualityGate,
    RuntimeExperimentPlan,
    RuntimeExperimentResult,
)


def group(group_id="single_large_model"):
    return AgentGroupProfile(
        group_id=group_id,
        description=f"Synthetic profile for {group_id}.",
        agents=[
            ExperimentAgent(
                role="worker",
                model="qwen2.5-coder-7b",
                runtime_backend=RuntimeBackendProfile.ollama("qwen2.5-coder:7b"),
                token_budget=1000,
                required_output_contract="route_decision_review_packet.v1",
            )
        ],
    )


def plan(**overrides):
    values = {
        "experiment_id": "exp-route-decision-001",
        "task_class": "route_decision",
        "task_fixture": "fixtures/tasks/route_decision_001.json",
        "baseline_group": "single_large_model",
        "candidate_groups": ["small_specialist_agents"],
        "repetitions": 2,
        "quality_gate": ExperimentQualityGate(
            required=True,
            rubric="deterministic_schema_and_policy_check",
        ),
        "measurement_config": MeasurementConfig(
            token_metrics=True,
            latency_metrics=True,
            energy_tier="token_proxy",
        ),
        "allowed_runtime_backends": ["ollama", "llama_cpp"],
        "token_budget": 2000,
        "notes": "Synthetic deterministic plan.",
    }
    values.update(overrides)
    return RuntimeExperimentPlan(**values)


def efficiency_record(**overrides):
    values = {
        "run_id": "run-candidate-001",
        "created_at": "2026-06-30T00:00:00Z",
        "task_digest": "sha256:task",
        "task_class": "route_decision",
        "baseline_route": "single_large_model",
        "selected_route": "small_specialist_agents",
        "runtime_backend": RuntimeBackendProfile.ollama("qwen2.5-coder:7b"),
        "baseline_tokens": TokenMetrics(prompt_tokens=900, completion_tokens=100),
        "selected_tokens": TokenMetrics(prompt_tokens=500, completion_tokens=100),
        "baseline_latency": LatencyMetrics(total_latency_ms=2000.0),
        "selected_latency": LatencyMetrics(total_latency_ms=1500.0),
        "energy": EnergyEvidence(),
        "measurement_tier": "token_proxy",
        "quality_gate": QualityGate(passed=True, method="schema_policy_check"),
    }
    values.update(overrides)
    return RuntimeEfficiencyRecord(**values)


def result(**overrides):
    values = {
        "experiment_id": "exp-route-decision-001",
        "run_id": "result-001",
        "group_id": "small_specialist_agents",
        "task_class": "route_decision",
        "repetition_index": 0,
        "runtime_efficiency_record": efficiency_record(),
        "quality_gate": ResultQualityGate(passed=True, method="schema_policy_check"),
        "claim_validity": ClaimValidity(
            efficiency_claim_valid=True,
            token_efficiency_claimed=True,
        ),
        "baseline_group": "single_large_model",
        "baseline_run_id": "run-baseline-001",
    }
    values.update(overrides)
    return RuntimeExperimentResult(**values)


def test_valid_experiment_plan_loads():
    experiment_plan = plan()
    profiles = {
        "single_large_model": group("single_large_model"),
        "small_specialist_agents": group("small_specialist_agents"),
    }

    experiment_plan.validate_group_profiles(profiles)

    assert experiment_plan.to_dict()["experiment_id"] == "exp-route-decision-001"


def test_invalid_plan_without_baseline_fails():
    with pytest.raises(ValueError, match="baseline_group must be non-empty"):
        plan(baseline_group="")


def test_invalid_candidate_group_fails():
    experiment_plan = plan(candidate_groups=["missing_group"])

    with pytest.raises(ValueError, match="candidate group is missing"):
        experiment_plan.validate_group_profiles(
            {"single_large_model": group("single_large_model")}
        )


def test_result_with_failed_quality_gate_cannot_claim_efficiency_benefit():
    with pytest.raises(ValueError, match="failed quality gate"):
        result(
            quality_gate=ResultQualityGate(
                passed=False,
                method="schema_policy_check",
                notes="Invalid route decision packet.",
            ),
            claim_validity=ClaimValidity(
                efficiency_claim_valid=True,
                token_efficiency_claimed=True,
            ),
        )


def test_result_with_token_savings_and_passed_quality_gate_can_claim_token_efficiency():
    experiment_result = result()

    assert experiment_result.to_dict()["claim_validity"]["efficiency_claim_valid"]
    assert (
        experiment_result.to_dict()["runtime_efficiency_record"]["benefits"][
            "tokens_saved"
        ]
        == 400
    )


def test_measured_energy_claim_rejected_without_measured_energy_values():
    with pytest.raises(ValueError, match="energy measurement tier"):
        result(
            claim_validity=ClaimValidity(
                efficiency_claim_valid=True,
                energy_efficiency_claimed=True,
            )
        )


def test_deterministic_json_output_for_fixed_synthetic_result():
    experiment_result = result()

    encoded = experiment_result.to_json()
    decoded = json.loads(encoded)

    assert encoded == experiment_result.to_json()
    assert decoded["schema_version"] == "runtime_experiment_result.v1"
    assert decoded["baseline_group"] == "single_large_model"
