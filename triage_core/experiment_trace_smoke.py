"""Deterministic reviewer-facing smoke export for experiment trace artifacts."""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from .experiment_traces import ExperimentTraceRecord, TraceClaimValidity
from .runtime_backends import RuntimeBackendProfile
from .runtime_efficiency import (
    EnergyEvidence,
    LatencyMetrics,
    QualityGate,
    RuntimeEfficiencyRecord,
    TokenMetrics,
)
from .runtime_experiments import ClaimValidity, ResultQualityGate, RuntimeExperimentResult


TRACE_RECORD_FILE_NAME = "experiment_trace_record.json"
TRACE_SUMMARY_FILE_NAME = "experiment_trace_summary.md"


@dataclass(frozen=True)
class ExperimentTraceSmokeExportResult:
    output_dir: Path
    trace_path: Path
    summary_path: Optional[Path]
    trace_id: str


def build_synthetic_experiment_trace(
    *,
    efficiency_claim_valid: bool = True,
    energy_claim_valid: bool = False,
    quality_gate_passed: bool = True,
    quality_gate_method: str = "route_decision_review_v0",
) -> ExperimentTraceRecord:
    """Build one deterministic synthetic experiment trace record."""
    runtime_efficiency_record = RuntimeEfficiencyRecord(
        run_id="run-candidate-001",
        created_at="2026-06-30T00:00:00Z",
        task_digest="sha256:fixture-001",
        task_class="route_decision",
        baseline_route="single_large_model",
        selected_route="small_first_escalation",
        runtime_backend=RuntimeBackendProfile.llama_cpp(
            model_file="qwen.gguf",
            quantization="Q4_K_M",
            context_size=8192,
            threads=12,
            gpu_layers=20,
        ),
        baseline_tokens=TokenMetrics(
            prompt_tokens=900,
            completion_tokens=100,
            token_budget=1200,
        ),
        selected_tokens=TokenMetrics(
            prompt_tokens=500,
            completion_tokens=120,
            token_budget=900,
        ),
        baseline_latency=LatencyMetrics(total_latency_ms=2100.0),
        selected_latency=LatencyMetrics(total_latency_ms=1300.0),
        energy=EnergyEvidence(),
        measurement_tier="token_proxy",
        quality_gate=QualityGate(
            passed=quality_gate_passed,
            method=quality_gate_method,
            notes=None if quality_gate_passed else "Synthetic quality gate failure.",
        ),
    )

    experiment_result = RuntimeExperimentResult(
        experiment_id="exp-route-review-001",
        run_id="result-001",
        group_id="small_first_escalation",
        task_class="route_decision",
        repetition_index=0,
        runtime_efficiency_record=runtime_efficiency_record,
        quality_gate=ResultQualityGate(
            passed=quality_gate_passed,
            method=quality_gate_method,
            notes=None if quality_gate_passed else "Synthetic quality gate failure.",
        ),
        claim_validity=ClaimValidity(
            efficiency_claim_valid=efficiency_claim_valid,
            reason=None if efficiency_claim_valid else "quality gate failed",
            token_efficiency_claimed=efficiency_claim_valid,
            energy_efficiency_claimed=energy_claim_valid,
        ),
        baseline_group="single_large_model",
        baseline_run_id="run-baseline-001",
        failure_reason=None if quality_gate_passed else "quality_gate_failed",
    )

    claim_reason = None
    if not efficiency_claim_valid and not energy_claim_valid:
        claim_reason = "quality gate failed"
    elif efficiency_claim_valid and not energy_claim_valid:
        claim_reason = "token_proxy_only"
    elif not efficiency_claim_valid and energy_claim_valid:
        claim_reason = "invalid_energy_claim"

    return ExperimentTraceRecord.from_experiment_result(
        trace_id="trace-route-review-001",
        created_at="2026-06-30T00:00:00Z",
        task_fixture_digest="sha256:fixture-001",
        runtime_backend_profile_id="llama_cpp_qwen_7b_q4",
        runtime_efficiency_record_id="eff-run-candidate-001",
        quality_gate_id="route_decision_review_v0",
        claim_validity=TraceClaimValidity(
            efficiency_claim_valid=efficiency_claim_valid,
            energy_claim_valid=energy_claim_valid,
            reason=claim_reason,
        ),
        result=experiment_result,
    )


def render_experiment_trace_summary(trace: ExperimentTraceRecord) -> str:
    """Render a deterministic reviewer-facing summary for the synthetic trace."""
    trace_dict = trace.to_dict()
    benefits = trace_dict["runtime_efficiency_record"]["benefits"]
    return "\n".join(
        [
            "# Experiment Trace Smoke Summary",
            "",
            "This is a deterministic reviewer-facing dry-run artifact.",
            "It proves trace export shape, not live runtime benchmarking.",
            "",
            f"- trace_id: `{trace.trace_id}`",
            f"- experiment_id: `{trace.experiment_id}`",
            f"- run_id: `{trace.run_id}`",
            f"- agent_group_id: `{trace.agent_group_id}`",
            f"- runtime_backend_profile_id: `{trace.runtime_backend_profile_id}`",
            f"- quality_gate_id: `{trace.quality_gate_id}`",
            f"- efficiency_claim_valid: `{trace.claim_validity.efficiency_claim_valid}`",
            f"- energy_claim_valid: `{trace.claim_validity.energy_claim_valid}`",
            f"- tokens_saved: `{benefits['tokens_saved']}`",
            f"- latency_saved_ms: `{benefits['latency_saved_ms']}`",
            "",
            "Token proxy evidence is not measured energy evidence.",
        ]
    )


def export_experiment_trace_smoke(
    output_dir: Union[str, Path],
    *,
    write_summary: bool = True,
) -> ExperimentTraceSmokeExportResult:
    """Write one deterministic synthetic experiment trace artifact to disk."""
    if output_dir is None:
        raise ValueError("output_dir must be provided")
    if isinstance(output_dir, str) and not output_dir.strip():
        raise ValueError("output_dir must be provided")

    dir_path = Path(output_dir)
    if dir_path.exists() and not dir_path.is_dir():
        raise ValueError("output_dir must point to a directory")

    trace = build_synthetic_experiment_trace()

    dir_path.mkdir(parents=True, exist_ok=True)
    trace_path = dir_path / TRACE_RECORD_FILE_NAME
    trace_path.write_text(trace.to_json() + "\n", encoding="utf-8")

    summary_path: Optional[Path] = None
    if write_summary:
        summary_path = dir_path / TRACE_SUMMARY_FILE_NAME
        summary_path.write_text(
            render_experiment_trace_summary(trace) + "\n",
            encoding="utf-8",
        )

    return ExperimentTraceSmokeExportResult(
        output_dir=dir_path,
        trace_path=trace_path,
        summary_path=summary_path,
        trace_id=trace.trace_id,
    )
