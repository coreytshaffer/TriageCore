"""Deterministic token-efficiency evidence records."""
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict

from .context_budget import estimate_tokens


SCHEMA_VERSION = "token_efficiency_record.v1"
SMOKE_TASK_ID = "fixture-doc-summary-001"
SMOKE_BASELINE_STRATEGY = "raw_context"
SMOKE_CANDIDATE_STRATEGY = "compact_context"
SMOKE_BASELINE_OUTPUT_TOKENS = 600
SMOKE_CANDIDATE_OUTPUT_TOKENS = 500
SMOKE_QUALITY_GATE_STATUS = "not_evaluated"
SMOKE_QUALITY_GATE_REASON = "measurement-only smoke fixture"
QUALITY_GATE_STATUSES = {"not_evaluated", "passed", "failed"}


@dataclass(frozen=True)
class TokenEstimate:
    strategy: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_total_tokens: int

    def __post_init__(self) -> None:
        if not self.strategy:
            raise ValueError("strategy must be non-empty")
        for field_name in (
            "estimated_input_tokens",
            "estimated_output_tokens",
            "estimated_total_tokens",
        ):
            value = getattr(self, field_name)
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")
        expected_total = self.estimated_input_tokens + self.estimated_output_tokens
        if self.estimated_total_tokens != expected_total:
            raise ValueError("estimated_total_tokens must equal input plus output")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "estimated_input_tokens": self.estimated_input_tokens,
            "estimated_output_tokens": self.estimated_output_tokens,
            "estimated_total_tokens": self.estimated_total_tokens,
        }


@dataclass(frozen=True)
class TokenSavings:
    estimated_tokens_saved: int
    estimated_percent_saved: float

    def __post_init__(self) -> None:
        if not isinstance(self.estimated_tokens_saved, int):
            raise ValueError("estimated_tokens_saved must be an integer")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "estimated_tokens_saved": self.estimated_tokens_saved,
            "estimated_percent_saved": self.estimated_percent_saved,
        }


@dataclass(frozen=True)
class QualityGateStatus:
    status: str
    reason: str

    def __post_init__(self) -> None:
        if self.status not in QUALITY_GATE_STATUSES:
            raise ValueError(f"unsupported quality gate status: {self.status}")
        if not self.reason:
            raise ValueError("quality gate reason must be non-empty")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class TokenEfficiencyRecord:
    task_id: str
    baseline: TokenEstimate
    candidate: TokenEstimate
    savings: TokenSavings
    quality_gate: QualityGateStatus
    kind: str = "token_efficiency"
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.task_id:
            raise ValueError("task_id must be non-empty")
        if self.kind != "token_efficiency":
            raise ValueError("kind must be token_efficiency")
        if self.baseline.estimated_total_tokens <= 0:
            raise ValueError("baseline estimated total tokens must be positive")

        expected_saved = (
            self.baseline.estimated_total_tokens - self.candidate.estimated_total_tokens
        )
        expected_percent = round(
            (expected_saved / self.baseline.estimated_total_tokens) * 100.0,
            1,
        )
        if self.savings.estimated_tokens_saved != expected_saved:
            raise ValueError("estimated_tokens_saved does not match baseline/candidate totals")
        if self.savings.estimated_percent_saved != expected_percent:
            raise ValueError("estimated_percent_saved does not match baseline/candidate totals")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "task_id": self.task_id,
            "baseline": self.baseline.to_dict(),
            "candidate": self.candidate.to_dict(),
            "savings": self.savings.to_dict(),
            "quality_gate": self.quality_gate.to_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def build_token_efficiency_record(
    task_id: str,
    baseline_strategy: str,
    baseline_text: str,
    baseline_output_tokens: int,
    candidate_strategy: str,
    candidate_text: str,
    candidate_output_tokens: int,
    quality_gate_status: str,
    quality_gate_reason: str,
) -> TokenEfficiencyRecord:
    baseline = TokenEstimate(
        strategy=baseline_strategy,
        estimated_input_tokens=estimate_tokens(baseline_text),
        estimated_output_tokens=baseline_output_tokens,
        estimated_total_tokens=estimate_tokens(baseline_text) + baseline_output_tokens,
    )
    candidate = TokenEstimate(
        strategy=candidate_strategy,
        estimated_input_tokens=estimate_tokens(candidate_text),
        estimated_output_tokens=candidate_output_tokens,
        estimated_total_tokens=estimate_tokens(candidate_text) + candidate_output_tokens,
    )
    estimated_tokens_saved = (
        baseline.estimated_total_tokens - candidate.estimated_total_tokens
    )
    estimated_percent_saved = round(
        (estimated_tokens_saved / baseline.estimated_total_tokens) * 100.0,
        1,
    )
    return TokenEfficiencyRecord(
        task_id=task_id,
        baseline=baseline,
        candidate=candidate,
        savings=TokenSavings(
            estimated_tokens_saved=estimated_tokens_saved,
            estimated_percent_saved=estimated_percent_saved,
        ),
        quality_gate=QualityGateStatus(
            status=quality_gate_status,
            reason=quality_gate_reason,
        ),
    )


def smoke_fixture_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "docs" / "examples" / "token_efficiency"


def smoke_fixture_paths() -> Dict[str, Path]:
    fixture_dir = smoke_fixture_dir()
    return {
        "baseline": fixture_dir / "baseline_context.txt",
        "candidate": fixture_dir / "compact_context.txt",
    }


def build_smoke_test_record() -> TokenEfficiencyRecord:
    fixture_paths = smoke_fixture_paths()
    baseline_text = fixture_paths["baseline"].read_text(encoding="utf-8")
    candidate_text = fixture_paths["candidate"].read_text(encoding="utf-8")
    return build_token_efficiency_record(
        task_id=SMOKE_TASK_ID,
        baseline_strategy=SMOKE_BASELINE_STRATEGY,
        baseline_text=baseline_text,
        baseline_output_tokens=SMOKE_BASELINE_OUTPUT_TOKENS,
        candidate_strategy=SMOKE_CANDIDATE_STRATEGY,
        candidate_text=candidate_text,
        candidate_output_tokens=SMOKE_CANDIDATE_OUTPUT_TOKENS,
        quality_gate_status=SMOKE_QUALITY_GATE_STATUS,
        quality_gate_reason=SMOKE_QUALITY_GATE_REASON,
    )
