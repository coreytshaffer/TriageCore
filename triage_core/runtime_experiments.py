"""Controlled runtime experiment plans and synthetic result records."""
from dataclasses import dataclass
import json
from typing import Any, Dict, Mapping, Optional, Sequence

from .agent_group_profiles import AgentGroupProfile
from .runtime_efficiency import MEASUREMENT_TIERS, RuntimeEfficiencyRecord


PLAN_SCHEMA_VERSION = "runtime_experiment_plan.v1"
RESULT_SCHEMA_VERSION = "runtime_experiment_result.v1"
ENERGY_MEASUREMENT_TIERS = {"software_energy_estimate", "wall_power_measured"}


@dataclass(frozen=True)
class ExperimentQualityGate:
    required: bool
    rubric: str

    def __post_init__(self) -> None:
        if self.required and not self.rubric:
            raise ValueError("quality_gate rubric must be non-empty when required")

    def to_dict(self) -> Dict[str, Any]:
        return {"required": self.required, "rubric": self.rubric}


@dataclass(frozen=True)
class MeasurementConfig:
    token_metrics: bool
    latency_metrics: bool
    energy_tier: str

    def __post_init__(self) -> None:
        if self.energy_tier not in MEASUREMENT_TIERS:
            raise ValueError(f"unsupported energy_tier: {self.energy_tier}")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "token_metrics": self.token_metrics,
            "latency_metrics": self.latency_metrics,
            "energy_tier": self.energy_tier,
        }


@dataclass(frozen=True)
class RuntimeExperimentPlan:
    experiment_id: str
    task_class: str
    task_fixture: str
    baseline_group: str
    candidate_groups: Sequence[str]
    repetitions: int
    quality_gate: ExperimentQualityGate
    measurement_config: MeasurementConfig
    allowed_runtime_backends: Sequence[str]
    token_budget: int
    notes: Optional[str] = None
    schema_version: str = PLAN_SCHEMA_VERSION

    def __post_init__(self) -> None:
        required_strings = {
            "experiment_id": self.experiment_id,
            "task_class": self.task_class,
            "task_fixture": self.task_fixture,
            "baseline_group": self.baseline_group,
        }
        for field_name, value in required_strings.items():
            if not value:
                raise ValueError(f"{field_name} must be non-empty")
        if self.repetitions <= 0:
            raise ValueError("repetitions must be positive")
        if self.token_budget <= 0:
            raise ValueError("token_budget must be positive")
        if not self.allowed_runtime_backends:
            raise ValueError("allowed_runtime_backends must be non-empty")

    def validate_group_profiles(
        self, group_profiles: Mapping[str, AgentGroupProfile]
    ) -> None:
        if self.baseline_group not in group_profiles:
            raise ValueError("baseline group is missing from available group profiles")
        for group_id in self.candidate_groups:
            if group_id not in group_profiles:
                raise ValueError(f"candidate group is missing: {group_id}")
        for group_id in (self.baseline_group, *self.candidate_groups):
            group_profiles[group_id].validate_allowed_backends(
                self.allowed_runtime_backends
            )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "task_class": self.task_class,
            "task_fixture": self.task_fixture,
            "baseline_group": self.baseline_group,
            "candidate_groups": list(self.candidate_groups),
            "repetitions": self.repetitions,
            "quality_gate": self.quality_gate.to_dict(),
            "measurement_config": self.measurement_config.to_dict(),
            "allowed_runtime_backends": list(self.allowed_runtime_backends),
            "token_budget": self.token_budget,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ResultQualityGate:
    passed: bool
    method: str
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.method:
            raise ValueError("quality gate method must be non-empty")

    def to_dict(self) -> Dict[str, Any]:
        return {"passed": self.passed, "method": self.method, "notes": self.notes}


@dataclass(frozen=True)
class ClaimValidity:
    efficiency_claim_valid: bool
    reason: Optional[str] = None
    token_efficiency_claimed: bool = False
    latency_efficiency_claimed: bool = False
    energy_efficiency_claimed: bool = False

    def __post_init__(self) -> None:
        if not self.efficiency_claim_valid and not self.reason:
            raise ValueError("invalid efficiency claims require a reason")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "efficiency_claim_valid": self.efficiency_claim_valid,
            "reason": self.reason,
            "token_efficiency_claimed": self.token_efficiency_claimed,
            "latency_efficiency_claimed": self.latency_efficiency_claimed,
            "energy_efficiency_claimed": self.energy_efficiency_claimed,
        }


@dataclass(frozen=True)
class RuntimeExperimentResult:
    experiment_id: str
    run_id: str
    group_id: str
    task_class: str
    repetition_index: int
    runtime_efficiency_record: RuntimeEfficiencyRecord
    quality_gate: ResultQualityGate
    claim_validity: ClaimValidity
    baseline_group: str
    baseline_run_id: str
    failure_reason: Optional[str] = None
    schema_version: str = RESULT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        required_strings = {
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "group_id": self.group_id,
            "task_class": self.task_class,
            "baseline_group": self.baseline_group,
            "baseline_run_id": self.baseline_run_id,
        }
        for field_name, value in required_strings.items():
            if not value:
                raise ValueError(f"{field_name} must be non-empty")
        if self.repetition_index < 0:
            raise ValueError("repetition_index must be non-negative")
        if not self.quality_gate.passed and self.claim_validity.efficiency_claim_valid:
            raise ValueError("failed quality gate cannot claim efficiency benefit")
        if self.claim_validity.energy_efficiency_claimed:
            if self.runtime_efficiency_record.measurement_tier not in ENERGY_MEASUREMENT_TIERS:
                raise ValueError("energy-saving claims require an energy measurement tier")
            energy = self.runtime_efficiency_record.energy
            if energy.baseline_energy_wh is None or energy.measured_energy_wh is None:
                raise ValueError("energy-saving claims require measured energy values")
        if self.claim_validity.token_efficiency_claimed:
            benefits = self.runtime_efficiency_record.compute_benefits()
            if benefits["tokens_saved"] is None:
                raise ValueError("token efficiency claims require baseline comparison fields")
        if self.failure_reason and self.quality_gate.passed:
            raise ValueError("failure_reason requires a failed quality gate")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "experiment_id": self.experiment_id,
            "run_id": self.run_id,
            "group_id": self.group_id,
            "task_class": self.task_class,
            "repetition_index": self.repetition_index,
            "runtime_efficiency_record": self.runtime_efficiency_record.to_dict(),
            "quality_gate": self.quality_gate.to_dict(),
            "claim_validity": self.claim_validity.to_dict(),
            "baseline_group": self.baseline_group,
            "baseline_run_id": self.baseline_run_id,
            "failure_reason": self.failure_reason,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
