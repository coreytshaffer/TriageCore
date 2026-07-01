import json

import pytest

from triage_core.runtime_backends import RuntimeBackendProfile
from triage_core.runtime_efficiency import (
    EnergyEvidence,
    LatencyMetrics,
    QualityGate,
    RuntimeEfficiencyRecord,
    TokenMetrics,
)


def fixed_record(**overrides):
    values = {
        "run_id": "run-001",
        "created_at": "2026-06-30T00:00:00Z",
        "task_digest": "sha256:abc123",
        "task_class": "routing_smoke",
        "baseline_route": "large-local",
        "selected_route": "small-local",
        "runtime_backend": RuntimeBackendProfile.llama_cpp(
            model_file="qwen.gguf",
            quantization="Q4_K_M",
            context_size=8192,
            threads=12,
            gpu_layers=35,
            device="cuda",
        ),
        "baseline_tokens": TokenMetrics(
            prompt_tokens=900,
            completion_tokens=100,
            token_budget=2000,
        ),
        "selected_tokens": TokenMetrics(
            prompt_tokens=500,
            completion_tokens=80,
            token_budget=1000,
        ),
        "baseline_latency": LatencyMetrics(total_latency_ms=2000.0),
        "selected_latency": LatencyMetrics(total_latency_ms=1200.0),
        "energy": EnergyEvidence(),
        "measurement_tier": "token_proxy",
        "quality_gate": QualityGate(passed=True, method="fixture_assertion"),
    }
    values.update(overrides)
    return RuntimeEfficiencyRecord(**values)


def test_deterministic_json_output_for_fixed_fixture():
    record = fixed_record()

    encoded = record.to_json()
    decoded = json.loads(encoded)

    assert encoded == record.to_json()
    assert decoded["schema_version"] == "runtime_efficiency_record.v1"
    assert decoded["benefits"]["tokens_saved"] == 420
    assert decoded["runtime_backend"]["name"] == "llama_cpp"


def test_token_savings_computed_correctly():
    record = fixed_record()

    assert record.to_dict()["benefits"]["tokens_saved"] == 420
    assert record.to_dict()["benefits"]["token_reduction_ratio"] == 0.42


def test_latency_savings_computed_when_latency_values_exist():
    record = fixed_record()

    assert record.to_dict()["benefits"]["latency_saved_ms"] == 800.0


def test_energy_savings_rejected_without_measurement_evidence():
    with pytest.raises(ValueError, match="measurement method"):
        fixed_record(
            energy=EnergyEvidence(
                baseline_energy_wh=10.0,
                measured_energy_wh=7.0,
            ),
            measurement_tier="wall_power_measured",
        )


def test_selected_route_over_budget_rejected():
    with pytest.raises(ValueError, match="exceed token budget"):
        fixed_record(
            selected_tokens=TokenMetrics(
                prompt_tokens=900,
                completion_tokens=200,
                token_budget=1000,
            )
        )


def test_token_proxy_records_may_have_null_energy_fields():
    record = fixed_record(energy=EnergyEvidence(), measurement_tier="token_proxy")

    assert record.to_dict()["energy"]["estimated_energy_wh"] is None
    assert record.to_dict()["energy"]["measured_energy_wh"] is None


def test_token_savings_rejected_when_selected_total_missing():
    with pytest.raises(ValueError, match="baseline and selected token totals"):
        fixed_record(
            selected_tokens=TokenMetrics(
                prompt_tokens=None,
                completion_tokens=None,
                total_tokens=None,
                token_budget=1000,
            )
        )


def test_quality_gate_required_before_claims_are_valid():
    record = fixed_record(
        quality_gate=QualityGate(passed=False, method="manual_review_failed")
    )

    assert record.to_dict()["benefits"]["claims_valid"] is False
