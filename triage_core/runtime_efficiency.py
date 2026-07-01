"""Deterministic runtime efficiency ledger records."""
from dataclasses import dataclass
import json
from typing import Any, Dict, Optional

from .runtime_backends import RuntimeBackendProfile


SCHEMA_VERSION = "runtime_efficiency_record.v1"
MEASUREMENT_TIERS = {
    "token_proxy",
    "runtime_proxy",
    "software_energy_estimate",
    "wall_power_measured",
}


@dataclass(frozen=True)
class TokenMetrics:
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    token_budget: Optional[int] = None

    def __post_init__(self) -> None:
        for field_name in (
            "prompt_tokens",
            "completion_tokens",
            "total_tokens",
            "token_budget",
        ):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} must be non-negative when present")
        if self.total_tokens is None:
            if self.prompt_tokens is not None and self.completion_tokens is not None:
                object.__setattr__(
                    self, "total_tokens", self.prompt_tokens + self.completion_tokens
                )

    def to_dict(self) -> Dict[str, Optional[int]]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "token_budget": self.token_budget,
        }


@dataclass(frozen=True)
class LatencyMetrics:
    total_latency_ms: Optional[float] = None
    time_to_first_token_ms: Optional[float] = None
    decode_tokens_per_second: Optional[float] = None
    prompt_tokens_per_second: Optional[float] = None

    def __post_init__(self) -> None:
        for field_name in (
            "total_latency_ms",
            "time_to_first_token_ms",
            "decode_tokens_per_second",
            "prompt_tokens_per_second",
        ):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} must be non-negative when present")

    def to_dict(self) -> Dict[str, Optional[float]]:
        return {
            "total_latency_ms": self.total_latency_ms,
            "time_to_first_token_ms": self.time_to_first_token_ms,
            "decode_tokens_per_second": self.decode_tokens_per_second,
            "prompt_tokens_per_second": self.prompt_tokens_per_second,
        }


@dataclass(frozen=True)
class EnergyEvidence:
    baseline_energy_wh: Optional[float] = None
    estimated_energy_wh: Optional[float] = None
    measured_energy_wh: Optional[float] = None
    measurement_method: Optional[str] = None
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        for field_name in (
            "baseline_energy_wh",
            "estimated_energy_wh",
            "measured_energy_wh",
        ):
            value = getattr(self, field_name)
            if value is not None and value < 0:
                raise ValueError(f"{field_name} must be non-negative when present")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline_energy_wh": self.baseline_energy_wh,
            "estimated_energy_wh": self.estimated_energy_wh,
            "measured_energy_wh": self.measured_energy_wh,
            "measurement_method": self.measurement_method,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class QualityGate:
    passed: bool
    method: str
    notes: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.method:
            raise ValueError("quality_gate method must be non-empty")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "method": self.method,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class RuntimeEfficiencyRecord:
    run_id: str
    created_at: str
    task_digest: str
    task_class: str
    baseline_route: str
    selected_route: str
    runtime_backend: RuntimeBackendProfile
    baseline_tokens: TokenMetrics
    selected_tokens: TokenMetrics
    baseline_latency: LatencyMetrics
    selected_latency: LatencyMetrics
    energy: EnergyEvidence
    measurement_tier: str
    quality_gate: QualityGate
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        required_strings = {
            "run_id": self.run_id,
            "created_at": self.created_at,
            "task_digest": self.task_digest,
            "task_class": self.task_class,
            "baseline_route": self.baseline_route,
            "selected_route": self.selected_route,
        }
        for field_name, value in required_strings.items():
            if not value:
                raise ValueError(f"{field_name} must be non-empty")
        if self.measurement_tier not in MEASUREMENT_TIERS:
            raise ValueError(f"unsupported measurement_tier: {self.measurement_tier}")
        selected_total = self.selected_tokens.total_tokens
        token_budget = self.selected_tokens.token_budget
        if selected_total is not None and token_budget is not None:
            if selected_total > token_budget:
                raise ValueError("selected route total tokens exceed token budget")
        benefits = self.compute_benefits()
        if benefits["tokens_saved"] is None:
            if self.baseline_tokens.total_tokens is not None:
                raise ValueError(
                    "token-savings claims require baseline and selected token totals"
                )
        if benefits["measured_energy_saved_wh"] is not None:
            if not self.energy.measurement_method:
                raise ValueError(
                    "measured energy savings require an explicit measurement method"
                )
        if self.measurement_tier == "wall_power_measured":
            if self.energy.measured_energy_wh is None:
                raise ValueError("wall_power_measured requires measured_energy_wh")
            if not self.energy.measurement_method:
                raise ValueError("wall_power_measured requires measurement_method")

    def compute_benefits(self) -> Dict[str, Any]:
        tokens_saved = None
        token_reduction_ratio = None
        if (
            self.baseline_tokens.total_tokens is not None
            and self.selected_tokens.total_tokens is not None
        ):
            tokens_saved = (
                self.baseline_tokens.total_tokens - self.selected_tokens.total_tokens
            )
            if self.baseline_tokens.total_tokens > 0:
                token_reduction_ratio = tokens_saved / self.baseline_tokens.total_tokens

        latency_saved_ms = None
        if (
            self.baseline_latency.total_latency_ms is not None
            and self.selected_latency.total_latency_ms is not None
        ):
            latency_saved_ms = (
                self.baseline_latency.total_latency_ms
                - self.selected_latency.total_latency_ms
            )

        measured_energy_saved_wh = None
        if (
            self.energy.baseline_energy_wh is not None
            and self.energy.measured_energy_wh is not None
        ):
            measured_energy_saved_wh = (
                self.energy.baseline_energy_wh - self.energy.measured_energy_wh
            )

        return {
            "claims_valid": self.quality_gate.passed,
            "tokens_saved": tokens_saved,
            "token_reduction_ratio": token_reduction_ratio,
            "latency_saved_ms": latency_saved_ms,
            "measured_energy_saved_wh": measured_energy_saved_wh,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "created_at": self.created_at,
            "task_digest": self.task_digest,
            "task_class": self.task_class,
            "baseline_route": self.baseline_route,
            "selected_route": self.selected_route,
            "runtime_backend": self.runtime_backend.to_dict(),
            "token_metrics": {
                "baseline": self.baseline_tokens.to_dict(),
                "selected": self.selected_tokens.to_dict(),
            },
            "latency_metrics": {
                "baseline": self.baseline_latency.to_dict(),
                "selected": self.selected_latency.to_dict(),
            },
            "benefits": self.compute_benefits(),
            "energy": self.energy.to_dict(),
            "measurement_tier": self.measurement_tier,
            "quality_gate": self.quality_gate.to_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
