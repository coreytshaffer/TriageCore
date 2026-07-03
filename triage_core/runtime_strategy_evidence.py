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


def _reject_unknown_top_level_fields(payload: Mapping[str, Any]) -> None:
    for key in payload:
        key_text = str(key)
        if key_text not in TOP_LEVEL_FIELDS:
            raise ValueError(f"unknown field: {key_text}")
