"""Deterministic runtime strategy evidence records."""
from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from triage_core.privacy_invariants import assert_persistent_privacy_safe


SCHEMA_VERSION = "runtime_strategy_evidence.v1"
KIND = "runtime_strategy_evidence"
QUALITY_GATE_STATUSES = frozenset({"not_evaluated", "passed", "failed"})
TOP_LEVEL_FIELDS = frozenset(
    {"schema_version", "kind", "task_id", "strategy", "steps", "totals", "quality_gate"}
)
DELTA_SCHEMA_VERSION = "runtime_strategy_delta.v1"
DELTA_KIND = "runtime_strategy_delta"
DELTA_INTERPRETATIONS = frozenset(
    {
        "token_saving",
        "token_saving_with_added_handoff",
        "token_neutral",
        "orchestration_overhead",
        "invalid_comparison",
    }
)
INVALID_COMPARISON_REASONS = frozenset(
    {
        "task_id_mismatch",
        "identical_strategy",
        "zero_baseline_tokens",
    }
)


@dataclass(frozen=True)
class RuntimeStrategyStep:
    role: str
    backend: str
    model_profile: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    schema_valid: bool

    def __post_init__(self) -> None:
        _require_text(self.role, "role")
        _require_text(self.backend, "backend")
        _require_text(self.model_profile, "model_profile")
        _require_non_negative_int(
            self.estimated_input_tokens,
            "estimated_input_tokens",
        )
        _require_non_negative_int(
            self.estimated_output_tokens,
            "estimated_output_tokens",
        )
        if not isinstance(self.schema_valid, bool):
            raise ValueError("schema_valid must be a boolean")

    @property
    def estimated_total_tokens(self) -> int:
        return self.estimated_input_tokens + self.estimated_output_tokens

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "backend": self.backend,
            "model_profile": self.model_profile,
            "estimated_input_tokens": self.estimated_input_tokens,
            "estimated_output_tokens": self.estimated_output_tokens,
            "estimated_total_tokens": self.estimated_total_tokens,
            "schema_valid": self.schema_valid,
        }


@dataclass(frozen=True)
class RuntimeStrategyTotals:
    estimated_tokens: int
    model_calls: int
    handoffs: int

    def __post_init__(self) -> None:
        _require_non_negative_int(self.estimated_tokens, "estimated_tokens")
        _require_non_negative_int(self.model_calls, "model_calls")
        _require_non_negative_int(self.handoffs, "handoffs")

    def to_dict(self) -> dict[str, int]:
        return {
            "estimated_tokens": self.estimated_tokens,
            "model_calls": self.model_calls,
            "handoffs": self.handoffs,
        }


@dataclass(frozen=True)
class RuntimeStrategyQualityGate:
    status: str
    reason: str

    def __post_init__(self) -> None:
        if self.status not in QUALITY_GATE_STATUSES:
            raise ValueError(f"unsupported quality gate status: {self.status}")
        _require_text(self.reason, "quality_gate.reason")

    def to_dict(self) -> dict[str, str]:
        return {
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class RuntimeStrategyComparison:
    records: Sequence["RuntimeStrategyEvidenceRecord"]

    def __post_init__(self) -> None:
        if len(self.records) < 2:
            raise ValueError("comparison requires at least two strategy records")
        task_ids = {record.task_id for record in self.records}
        if len(task_ids) != 1:
            raise ValueError("comparison records must share one task_id")
        strategies = [record.strategy for record in self.records]
        if len(set(strategies)) != len(strategies):
            raise ValueError("comparison strategies must be unique")

    @property
    def task_id(self) -> str:
        return self.records[0].task_id

    def strategy_names(self) -> list[str]:
        return [record.strategy for record in self.records]

    def estimated_tokens_by_backend(self) -> dict[str, int]:
        totals: dict[str, int] = {}
        for record in self.records:
            for step in record.steps:
                totals[step.backend] = totals.get(step.backend, 0) + step.estimated_total_tokens
        return dict(sorted(totals.items()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "strategies": [
                {
                    "strategy": record.strategy,
                    "estimated_total_tokens": record.totals.estimated_tokens,
                    "model_calls": record.totals.model_calls,
                    "handoffs": record.totals.handoffs,
                    "quality_gate_status": record.quality_gate.status,
                    "estimated_tokens_by_backend": _tokens_by_backend(record),
                }
                for record in self.records
            ],
            "estimated_tokens_by_backend": self.estimated_tokens_by_backend(),
        }

@dataclass(frozen=True)
class RuntimeStrategyEvidenceRecord:
    task_id: str
    strategy: str
    steps: Sequence[RuntimeStrategyStep]
    totals: RuntimeStrategyTotals
    quality_gate: RuntimeStrategyQualityGate
    kind: str = KIND
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.kind != KIND:
            raise ValueError(f"kind must be {KIND}")
        _require_text(self.task_id, "task_id")
        _require_text(self.strategy, "strategy")
        if not self.steps:
            raise ValueError("steps must be non-empty")

        expected_tokens = sum(step.estimated_total_tokens for step in self.steps)
        if self.totals.estimated_tokens != expected_tokens:
            raise ValueError("totals.estimated_tokens must equal summed step tokens")
        if self.totals.model_calls != len(self.steps):
            raise ValueError("totals.model_calls must equal number of steps")
        if self.totals.handoffs > max(0, len(self.steps) - 1):
            raise ValueError("totals.handoffs cannot exceed step transitions")

        assert_persistent_privacy_safe(
            self.to_dict(),
            artifact_name="runtime strategy evidence record",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "task_id": self.task_id,
            "strategy": self.strategy,
            "steps": [step.to_dict() for step in self.steps],
            "totals": self.totals.to_dict(),
            "quality_gate": self.quality_gate.to_dict(),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def build_runtime_strategy_evidence_record(
    *,
    task_id: str,
    strategy: str,
    steps: Sequence[RuntimeStrategyStep],
    handoffs: int,
    quality_gate_status: str,
    quality_gate_reason: str,
) -> RuntimeStrategyEvidenceRecord:
    return RuntimeStrategyEvidenceRecord(
        task_id=task_id,
        strategy=strategy,
        steps=list(steps),
        totals=RuntimeStrategyTotals(
            estimated_tokens=sum(step.estimated_total_tokens for step in steps),
            model_calls=len(steps),
            handoffs=handoffs,
        ),
        quality_gate=RuntimeStrategyQualityGate(
            status=quality_gate_status,
            reason=quality_gate_reason,
        ),
    )


def build_small_first_compact_fixture_record() -> RuntimeStrategyEvidenceRecord:
    return build_runtime_strategy_evidence_record(
        task_id="fixture-doc-summary-001",
        strategy="small_first_compact",
        steps=[
            RuntimeStrategyStep(
                role="extractor",
                backend="ollama",
                model_profile="small_extractor",
                estimated_input_tokens=1200,
                estimated_output_tokens=180,
                schema_valid=True,
            ),
            RuntimeStrategyStep(
                role="reviewer",
                backend="lm_studio",
                model_profile="heavy_reviewer",
                estimated_input_tokens=600,
                estimated_output_tokens=350,
                schema_valid=True,
            ),
        ],
        handoffs=1,
        quality_gate_status="not_evaluated",
        quality_gate_reason="measurement-only strategy fixture",
    )


def build_strategy_comparison_fixture_records() -> list[RuntimeStrategyEvidenceRecord]:
    task_id = "fixture-doc-summary-001"
    quality_status = "not_evaluated"
    quality_reason = "measurement-only strategy comparison fixture"
    return [
        build_runtime_strategy_evidence_record(
            task_id=task_id,
            strategy="heavy_only",
            steps=[
                RuntimeStrategyStep(
                    role="reviewer",
                    backend="lm_studio",
                    model_profile="heavy_reviewer",
                    estimated_input_tokens=4200,
                    estimated_output_tokens=600,
                    schema_valid=True,
                )
            ],
            handoffs=0,
            quality_gate_status=quality_status,
            quality_gate_reason=quality_reason,
        ),
        build_runtime_strategy_evidence_record(
            task_id=task_id,
            strategy="small_first_compact",
            steps=[
                RuntimeStrategyStep(
                    role="extractor",
                    backend="ollama",
                    model_profile="small_extractor",
                    estimated_input_tokens=1200,
                    estimated_output_tokens=180,
                    schema_valid=True,
                ),
                RuntimeStrategyStep(
                    role="reviewer",
                    backend="lm_studio",
                    model_profile="heavy_reviewer",
                    estimated_input_tokens=600,
                    estimated_output_tokens=350,
                    schema_valid=True,
                ),
            ],
            handoffs=1,
            quality_gate_status=quality_status,
            quality_gate_reason=quality_reason,
        ),
        build_runtime_strategy_evidence_record(
            task_id=task_id,
            strategy="small_only",
            steps=[
                RuntimeStrategyStep(
                    role="summarizer",
                    backend="ollama",
                    model_profile="small_summarizer",
                    estimated_input_tokens=1300,
                    estimated_output_tokens=420,
                    schema_valid=True,
                )
            ],
            handoffs=0,
            quality_gate_status=quality_status,
            quality_gate_reason=quality_reason,
        ),
        build_runtime_strategy_evidence_record(
            task_id=task_id,
            strategy="over_orchestrated",
            steps=[
                RuntimeStrategyStep(
                    role="router",
                    backend="ollama",
                    model_profile="tiny_router",
                    estimated_input_tokens=900,
                    estimated_output_tokens=120,
                    schema_valid=True,
                ),
                RuntimeStrategyStep(
                    role="extractor",
                    backend="ollama",
                    model_profile="small_extractor",
                    estimated_input_tokens=1200,
                    estimated_output_tokens=220,
                    schema_valid=True,
                ),
                RuntimeStrategyStep(
                    role="critic",
                    backend="ollama",
                    model_profile="small_critic",
                    estimated_input_tokens=1500,
                    estimated_output_tokens=300,
                    schema_valid=True,
                ),
                RuntimeStrategyStep(
                    role="reviewer",
                    backend="lm_studio",
                    model_profile="heavy_reviewer",
                    estimated_input_tokens=1800,
                    estimated_output_tokens=550,
                    schema_valid=True,
                ),
            ],
            handoffs=3,
            quality_gate_status=quality_status,
            quality_gate_reason=quality_reason,
        ),
    ]


def build_strategy_comparison_fixture() -> RuntimeStrategyComparison:
    return RuntimeStrategyComparison(build_strategy_comparison_fixture_records())


@dataclass(frozen=True)
class RuntimeStrategyDelta:
    baseline_strategy: str
    candidate_strategy: str
    interpretation: str
    task_id: str | None = None
    estimated_tokens_delta: int | None = None
    estimated_percent_delta: float | None = None
    model_calls_delta: int | None = None
    handoffs_delta: int | None = None
    invalid_reason: str | None = None
    kind: str = DELTA_KIND
    schema_version: str = DELTA_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.kind != DELTA_KIND:
            raise ValueError(f"kind must be {DELTA_KIND}")
        _require_text(self.baseline_strategy, "baseline_strategy")
        _require_text(self.candidate_strategy, "candidate_strategy")
        if self.interpretation not in DELTA_INTERPRETATIONS:
            raise ValueError(f"unsupported interpretation: {self.interpretation}")
        if self.interpretation == "invalid_comparison":
            if self.invalid_reason not in INVALID_COMPARISON_REASONS:
                raise ValueError(
                    f"unsupported invalid_comparison reason: {self.invalid_reason}"
                )
        elif self.invalid_reason is not None:
            raise ValueError("invalid_reason is only allowed for invalid_comparison")

        assert_persistent_privacy_safe(
            self.to_dict(),
            artifact_name="runtime strategy delta record",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "kind": self.kind,
            "task_id": self.task_id,
            "baseline_strategy": self.baseline_strategy,
            "candidate_strategy": self.candidate_strategy,
            "estimated_tokens_delta": self.estimated_tokens_delta,
            "estimated_percent_delta": self.estimated_percent_delta,
            "model_calls_delta": self.model_calls_delta,
            "handoffs_delta": self.handoffs_delta,
            "interpretation": self.interpretation,
            "invalid_reason": self.invalid_reason,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


def compute_strategy_delta(
    baseline: RuntimeStrategyEvidenceRecord,
    candidate: RuntimeStrategyEvidenceRecord,
) -> RuntimeStrategyDelta:
    """Compare a candidate strategy record against a baseline record.

    The result is a deterministic, metadata-only delta record. Interpretation
    labels describe estimated token pressure only; they claim nothing about
    output quality while quality gates are not evaluated.
    """
    if baseline.task_id != candidate.task_id:
        return RuntimeStrategyDelta(
            baseline_strategy=baseline.strategy,
            candidate_strategy=candidate.strategy,
            interpretation="invalid_comparison",
            invalid_reason="task_id_mismatch",
        )
    if baseline.strategy == candidate.strategy:
        return RuntimeStrategyDelta(
            baseline_strategy=baseline.strategy,
            candidate_strategy=candidate.strategy,
            interpretation="invalid_comparison",
            task_id=baseline.task_id,
            invalid_reason="identical_strategy",
        )
    if baseline.totals.estimated_tokens == 0:
        return RuntimeStrategyDelta(
            baseline_strategy=baseline.strategy,
            candidate_strategy=candidate.strategy,
            interpretation="invalid_comparison",
            task_id=baseline.task_id,
            invalid_reason="zero_baseline_tokens",
        )

    tokens_delta = candidate.totals.estimated_tokens - baseline.totals.estimated_tokens
    percent_delta = round(
        tokens_delta / baseline.totals.estimated_tokens * 100,
        1,
    )
    handoffs_delta = candidate.totals.handoffs - baseline.totals.handoffs

    if tokens_delta == 0:
        interpretation = "token_neutral"
    elif tokens_delta > 0:
        interpretation = "orchestration_overhead"
    elif handoffs_delta > 0:
        interpretation = "token_saving_with_added_handoff"
    else:
        interpretation = "token_saving"

    return RuntimeStrategyDelta(
        baseline_strategy=baseline.strategy,
        candidate_strategy=candidate.strategy,
        interpretation=interpretation,
        task_id=baseline.task_id,
        estimated_tokens_delta=tokens_delta,
        estimated_percent_delta=percent_delta,
        model_calls_delta=candidate.totals.model_calls - baseline.totals.model_calls,
        handoffs_delta=handoffs_delta,
    )


def compute_fixture_strategy_deltas(
    baseline_strategy: str = "heavy_only",
) -> list[RuntimeStrategyDelta]:
    """Compute deltas for every non-baseline fixture strategy against the baseline."""
    records = {
        record.strategy: record
        for record in build_strategy_comparison_fixture_records()
    }
    if baseline_strategy not in records:
        raise ValueError(f"unknown baseline strategy: {baseline_strategy}")
    baseline = records[baseline_strategy]
    return [
        compute_strategy_delta(baseline, candidate)
        for strategy, candidate in records.items()
        if strategy != baseline_strategy
    ]


DELTA_REPORT_KIND = "runtime_strategy_delta_report"
DELTA_REPORT_SCHEMA_VERSION = "runtime_strategy_delta_report.v1"
DELTA_REPORT_QUALITY_NOTE = "token savings do not imply quality improvement"


def build_fixture_strategy_delta_report(
    baseline_strategy: str = "heavy_only",
) -> dict[str, Any]:
    """Build a deterministic, metadata-only delta report over the fixture records."""
    records = build_strategy_comparison_fixture_records()
    deltas = compute_fixture_strategy_deltas(baseline_strategy)
    report = {
        "schema_version": DELTA_REPORT_SCHEMA_VERSION,
        "kind": DELTA_REPORT_KIND,
        "task_id": records[0].task_id,
        "baseline_strategy": baseline_strategy,
        "deltas": [delta.to_dict() for delta in deltas],
        "quality_gate_statuses": sorted(
            {record.quality_gate.status for record in records}
        ),
        "note": DELTA_REPORT_QUALITY_NOTE,
    }
    assert_persistent_privacy_safe(
        report,
        artifact_name="runtime strategy delta report",
    )
    return report


def format_strategy_delta_report(report: Mapping[str, Any]) -> str:
    """Render the delta report as an aligned plain-text table."""
    # ASCII-only headers: Windows consoles commonly use cp1252, which cannot
    # encode the delta glyph.
    headers = (
        "Strategy",
        "Tokens Delta",
        "Percent Delta",
        "Calls Delta",
        "Handoffs Delta",
        "Interpretation",
    )
    rows = []
    for delta in report["deltas"]:
        rows.append(
            (
                str(delta["candidate_strategy"]),
                _signed_int(delta["estimated_tokens_delta"]),
                _signed_percent(delta["estimated_percent_delta"]),
                _signed_int(delta["model_calls_delta"]),
                _signed_int(delta["handoffs_delta"]),
                str(delta["interpretation"]),
            )
        )

    widths = [
        max(len(headers[column]), *(len(row[column]) for row in rows))
        for column in range(len(headers))
    ]
    lines = [
        "Runtime strategy delta report",
        "",
        f"Baseline: {report['baseline_strategy']}",
        f"Task: {report['task_id']}",
        "",
        "   ".join(
            header.ljust(widths[column]) for column, header in enumerate(headers)
        ).rstrip(),
    ]
    for row in rows:
        lines.append(
            "   ".join(
                cell.ljust(widths[column]) for column, cell in enumerate(row)
            ).rstrip()
        )
    lines.extend(
        [
            "",
            f"Quality gates: {', '.join(report['quality_gate_statuses'])}",
            f"Note: {report['note']}.",
        ]
    )
    return "\n".join(lines)


def _signed_int(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{value:+d}"


def _signed_percent(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.1f}%"

def runtime_strategy_evidence_from_mapping(
    payload: Mapping[str, Any],
) -> RuntimeStrategyEvidenceRecord:
    assert_persistent_privacy_safe(
        dict(payload),
        artifact_name="runtime strategy evidence record",
    )
    _reject_unknown_top_level_fields(payload)

    steps_payload = payload.get("steps")
    if not isinstance(steps_payload, Sequence) or isinstance(
        steps_payload,
        (str, bytes, bytearray),
    ):
        raise ValueError("steps must be a list")

    steps = [
        RuntimeStrategyStep(
            role=_mapping_text(step, "role"),
            backend=_mapping_text(step, "backend"),
            model_profile=_mapping_text(step, "model_profile"),
            estimated_input_tokens=_mapping_int(step, "estimated_input_tokens"),
            estimated_output_tokens=_mapping_int(step, "estimated_output_tokens"),
            schema_valid=_mapping_bool(step, "schema_valid"),
        )
        for step in steps_payload
        if isinstance(step, Mapping)
    ]
    if len(steps) != len(steps_payload):
        raise ValueError("steps must contain only objects")

    totals_payload = payload.get("totals")
    if not isinstance(totals_payload, Mapping):
        raise ValueError("totals must be an object")

    quality_gate_payload = payload.get("quality_gate")
    if not isinstance(quality_gate_payload, Mapping):
        raise ValueError("quality_gate must be an object")

    return RuntimeStrategyEvidenceRecord(
        task_id=_mapping_text(payload, "task_id"),
        strategy=_mapping_text(payload, "strategy"),
        steps=steps,
        totals=RuntimeStrategyTotals(
            estimated_tokens=_mapping_int(totals_payload, "estimated_tokens"),
            model_calls=_mapping_int(totals_payload, "model_calls"),
            handoffs=_mapping_int(totals_payload, "handoffs"),
        ),
        quality_gate=RuntimeStrategyQualityGate(
            status=_mapping_text(quality_gate_payload, "status"),
            reason=_mapping_text(quality_gate_payload, "reason"),
        ),
        kind=str(payload.get("kind", KIND)),
        schema_version=str(payload.get("schema_version", SCHEMA_VERSION)),
    )


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty")


def _require_non_negative_int(value: int, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _mapping_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be non-empty")
    return value


def _mapping_int(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{key} must be an integer")
    return value


def _mapping_bool(payload: Mapping[str, Any], key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def _tokens_by_backend(record: RuntimeStrategyEvidenceRecord) -> dict[str, int]:
    totals: dict[str, int] = {}
    for step in record.steps:
        totals[step.backend] = totals.get(step.backend, 0) + step.estimated_total_tokens
    return dict(sorted(totals.items()))

def _reject_unknown_top_level_fields(payload: Mapping[str, Any]) -> None:
    for key in payload:
        key_text = str(key)
        if key_text not in TOP_LEVEL_FIELDS:
            raise ValueError(f"unknown field: {key_text}")
