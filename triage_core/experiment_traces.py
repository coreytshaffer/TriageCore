"""Durable experiment observability traces for controlled runtime studies."""
from dataclasses import dataclass
import json
from typing import Any, Dict, Optional

from .runtime_efficiency import RuntimeEfficiencyRecord
from .runtime_experiments import ENERGY_MEASUREMENT_TIERS, ResultQualityGate


SCHEMA_VERSION = "experiment_trace_record.v1"


@dataclass(frozen=True)
class TraceClaimValidity:
    efficiency_claim_valid: bool
    energy_claim_valid: bool
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        if (not self.efficiency_claim_valid or not self.energy_claim_valid) and not self.reason:
            raise ValueError("invalid trace claims require a reason")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "efficiency_claim_valid": self.efficiency_claim_valid,
            "energy_claim_valid": self.energy_claim_valid,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class TraceLineage:
    baseline_group_id: str
    candidate_group_id: str

    def __post_init__(self) -> None:
        if not self.baseline_group_id:
            raise ValueError("baseline_group_id must be non-empty")
        if not self.candidate_group_id:
            raise ValueError("candidate_group_id must be non-empty")

    def to_dict(self) -> Dict[str, str]:
        return {
            "baseline_group_id": self.baseline_group_id,
            "candidate_group_id": self.candidate_group_id,
        }


@dataclass(frozen=True)
class ExperimentTraceRecord:
    trace_id: str
    created_at: str
    experiment_id: str
    run_id: str
    task_fixture_digest: str
    agent_group_id: str
    runtime_backend_profile_id: str
    runtime_efficiency_record_id: str
    runtime_efficiency_record: RuntimeEfficiencyRecord
    quality_gate_id: str
    quality_gate_result: ResultQualityGate
    claim_validity: TraceClaimValidity
    lineage: TraceLineage
    failure_reason: Optional[str] = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        required_strings = {
            "trace_id": self.trace_id,
            "created_at": self.created_at,
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "task_fixture_digest": self.task_fixture_digest,
            "agent_group_id": self.agent_group_id,
            "runtime_backend_profile_id": self.runtime_backend_profile_id,
            "runtime_efficiency_record_id": self.runtime_efficiency_record_id,
            "quality_gate_id": self.quality_gate_id,
        }
        for field_name, value in required_strings.items():
            if not value:
                raise ValueError(f"{field_name} must be non-empty")

        if self.run_id != self.runtime_efficiency_record.run_id:
            raise ValueError("trace run_id must match runtime efficiency record run_id")
        if self.agent_group_id != self.lineage.candidate_group_id:
            raise ValueError("agent_group_id must match lineage candidate_group_id")
        if self.quality_gate_result.passed != self.runtime_efficiency_record.quality_gate.passed:
            raise ValueError("quality gate result must match runtime efficiency quality gate")

        if self.claim_validity.efficiency_claim_valid and not self.quality_gate_result.passed:
            raise ValueError("efficiency claims require a passed quality gate result")

        if self.claim_validity.energy_claim_valid:
            if self.runtime_efficiency_record.measurement_tier not in ENERGY_MEASUREMENT_TIERS:
                raise ValueError(
                    "energy claims require an energy-capable measurement tier"
                )
            energy = self.runtime_efficiency_record.energy
            if energy.baseline_energy_wh is None or energy.measured_energy_wh is None:
                raise ValueError("energy claims require measured energy comparison values")

        if self.failure_reason and self.quality_gate_result.passed:
            raise ValueError("failure_reason requires a failed quality gate result")
        if not self.quality_gate_result.passed and not self.failure_reason:
            raise ValueError("failed quality gate results require failure_reason")

    @classmethod
    def from_experiment_result(
        cls,
        *,
        trace_id: str,
        created_at: str,
        task_fixture_digest: str,
        runtime_backend_profile_id: str,
        runtime_efficiency_record_id: str,
        quality_gate_id: str,
        claim_validity: TraceClaimValidity,
        result: Any,
        failure_reason: Optional[str] = None,
    ) -> "ExperimentTraceRecord":
        return cls(
            trace_id=trace_id,
            created_at=created_at,
            experiment_id=result.experiment_id,
            run_id=result.runtime_efficiency_record.run_id,
            task_fixture_digest=task_fixture_digest,
            agent_group_id=result.group_id,
            runtime_backend_profile_id=runtime_backend_profile_id,
            runtime_efficiency_record_id=runtime_efficiency_record_id,
            runtime_efficiency_record=result.runtime_efficiency_record,
            quality_gate_id=quality_gate_id,
            quality_gate_result=result.quality_gate,
            claim_validity=claim_validity,
            lineage=TraceLineage(
                baseline_group_id=result.baseline_group,
                candidate_group_id=result.group_id,
            ),
            failure_reason=failure_reason or result.failure_reason,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "trace_id": self.trace_id,
            "created_at": self.created_at,
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "task_fixture_digest": self.task_fixture_digest,
            "agent_group_id": self.agent_group_id,
            "runtime_backend_profile_id": self.runtime_backend_profile_id,
            "runtime_efficiency_record_id": self.runtime_efficiency_record_id,
            "runtime_efficiency_record": self.runtime_efficiency_record.to_dict(),
            "quality_gate_id": self.quality_gate_id,
            "quality_gate_result": self.quality_gate_result.to_dict(),
            "claim_validity": self.claim_validity.to_dict(),
            "lineage": self.lineage.to_dict(),
            "failure_reason": self.failure_reason,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
