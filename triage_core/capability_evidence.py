"""Observed local capability binding for governed routing (CR-DD-013).

Projects the existing validated ``local_backend_probe_record.v1`` observation
into the route-input booleans the resilience router already reads, so missing,
disabled, stale, invalid, or insufficient evidence can no longer masquerade as
observed local health.

This module adds no probe. It never opens a socket, spawns a subprocess, or
invokes a model; it consumes a record that was recorded earlier by ``tc probe``
or injected directly by a caller.

Two facts drive the design:

* A metadata probe proves *runtime reachability*. It does not prove that
  ``local_fast`` or ``local_heavy`` is executable, because those classes imply
  model, memory, and context requirements the probe does not measure. Route
  class availability therefore requires an explicit operator declaration until
  G3 separates route-to-backend/model bindings.
* Negative and positive observations are not symmetric. A fresh observed
  failure rules out every route depending on that runtime and cannot be
  overridden by a declaration. A fresh reachable result confirms reachability
  only.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Tuple, Union

from .local_backend_probe import (
    LocalBackendProbeRecord,
    local_backend_probe_record_from_mapping,
)

ROUTE_CLASS_LOCAL_FAST = "local_fast"
ROUTE_CLASS_LOCAL_HEAVY = "local_heavy"
ROUTE_CLASSES: Tuple[str, ...] = (ROUTE_CLASS_LOCAL_FAST, ROUTE_CLASS_LOCAL_HEAVY)

OPERATOR_CONFIG_SOURCE = "operator_config"

STATE_OBSERVED_AVAILABLE = "observed_available"
STATE_OBSERVED_UNAVAILABLE = "observed_unavailable"
STATE_CONFIGURED = "configured"
STATE_UNKNOWN = "unknown"

# ``stale`` covers both an expired observation and one whose freshness cannot be
# established at all (a ``synthetic_fixture`` record is forbidden from carrying
# ``observed_at``, so it can validate a projection but never prove freshness).
UNKNOWN_MISSING = "missing"
UNKNOWN_PROBE_DISABLED = "probe_disabled"
UNKNOWN_STALE = "stale"
UNKNOWN_INVALID_RECORD = "invalid_record"
UNKNOWN_INSUFFICIENT_MODEL_EVIDENCE = "insufficient_model_evidence"

UNKNOWN_REASONS = frozenset(
    {
        UNKNOWN_MISSING,
        UNKNOWN_PROBE_DISABLED,
        UNKNOWN_STALE,
        UNKNOWN_INVALID_RECORD,
        UNKNOWN_INSUFFICIENT_MODEL_EVIDENCE,
    }
)


class CapabilityEvidenceError(ValueError):
    """Raised when a capability-evidence value is semantically impossible."""


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CapabilityEvidenceError(f"missing required field: {field_name}")
    return value


def _validate_route_classes(value: Any, field_name: str) -> None:
    if not isinstance(value, tuple):
        raise CapabilityEvidenceError(f"{field_name} must be a tuple")
    for route_class in value:
        if route_class not in ROUTE_CLASSES:
            raise CapabilityEvidenceError(
                f"{field_name} contains unknown route class: {route_class}"
            )


def _validate_freshness(value: Any) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise CapabilityEvidenceError("freshness_seconds must be a positive integer")


@dataclass(frozen=True)
class ObservedAvailable:
    """A fresh, validated record showed the runtime reachable.

    ``supported_route_classes`` names only classes the record itself supports.
    The current record schema carries no class-specific evidence, so this is
    normally empty: reachability alone is not a class availability claim.
    """

    source_type: str
    evidence_tier: str
    observed_at: str
    freshness_seconds: int
    supported_route_classes: Tuple[str, ...] = ()

    state = STATE_OBSERVED_AVAILABLE

    def __post_init__(self) -> None:
        _require_text(self.source_type, "source_type")
        if self.source_type == OPERATOR_CONFIG_SOURCE:
            raise CapabilityEvidenceError(
                "observed variants must not carry a configured-capability marker"
            )
        _require_text(self.evidence_tier, "evidence_tier")
        _require_text(self.observed_at, "observed_at")
        _validate_freshness(self.freshness_seconds)
        _validate_route_classes(self.supported_route_classes, "supported_route_classes")


@dataclass(frozen=True)
class ObservedUnavailable:
    """A fresh, validated record showed the runtime not answering."""

    source_type: str
    evidence_tier: str
    observed_at: str
    freshness_seconds: int
    error_category: str
    affected_route_classes: Tuple[str, ...]

    state = STATE_OBSERVED_UNAVAILABLE

    def __post_init__(self) -> None:
        _require_text(self.source_type, "source_type")
        if self.source_type == OPERATOR_CONFIG_SOURCE:
            raise CapabilityEvidenceError(
                "observed variants must not carry a configured-capability marker"
            )
        _require_text(self.evidence_tier, "evidence_tier")
        _require_text(self.observed_at, "observed_at")
        _validate_freshness(self.freshness_seconds)
        _require_text(self.error_category, "error_category")
        _validate_route_classes(self.affected_route_classes, "affected_route_classes")
        if not self.affected_route_classes:
            raise CapabilityEvidenceError(
                "affected_route_classes must name at least one route class"
            )


@dataclass(frozen=True)
class Configured:
    """An explicit operator declaration, not an observation.

    Structurally cannot carry ``observed_at`` or a probe ``evidence_tier``:
    those fields do not exist on this variant, so a configured declaration can
    never fabricate probe provenance.
    """

    config_reference: str
    declared_route_classes: Tuple[str, ...]
    config_digest: Optional[str] = None
    source_type: str = OPERATOR_CONFIG_SOURCE

    state = STATE_CONFIGURED

    def __post_init__(self) -> None:
        if self.source_type != OPERATOR_CONFIG_SOURCE:
            raise CapabilityEvidenceError(
                f"configured evidence requires source_type={OPERATOR_CONFIG_SOURCE}"
            )
        _require_text(self.config_reference, "config_reference")
        _validate_route_classes(self.declared_route_classes, "declared_route_classes")
        if not self.declared_route_classes:
            raise CapabilityEvidenceError(
                "declared_route_classes must name at least one route class"
            )
        if self.config_digest is not None:
            _require_text(self.config_digest, "config_digest")


@dataclass(frozen=True)
class Unknown:
    """No usable evidence. Never a positive availability claim."""

    reason: str

    state = STATE_UNKNOWN

    def __post_init__(self) -> None:
        _require_text(self.reason, "reason")
        if self.reason not in UNKNOWN_REASONS:
            raise CapabilityEvidenceError(f"unknown reason code: {self.reason}")


CapabilityEvidence = Union[ObservedAvailable, ObservedUnavailable, Configured, Unknown]


@dataclass(frozen=True)
class CapabilityResolution:
    """Resolved capability plus the route-input booleans it justifies."""

    evidence: CapabilityEvidence
    lm_studio_ok: bool
    local_fast_available: bool
    local_heavy_available: bool
    declared_route_classes: Tuple[str, ...] = ()
    freshness_seconds: Optional[int] = None

    def to_evidence_payload(self) -> dict:
        """Privacy-safe provenance for the existing route_decision payload."""
        evidence = self.evidence
        payload: dict = {
            "capability_state": evidence.state,
            "capability_declared_route_classes": list(self.declared_route_classes),
        }
        if self.freshness_seconds is not None:
            payload["capability_freshness_seconds"] = self.freshness_seconds

        if isinstance(evidence, ObservedAvailable):
            payload.update(
                {
                    "capability_source_type": evidence.source_type,
                    "capability_evidence_tier": evidence.evidence_tier,
                    "capability_observed_at": evidence.observed_at,
                    "capability_supported_route_classes": list(
                        evidence.supported_route_classes
                    ),
                }
            )
        elif isinstance(evidence, ObservedUnavailable):
            payload.update(
                {
                    "capability_source_type": evidence.source_type,
                    "capability_evidence_tier": evidence.evidence_tier,
                    "capability_observed_at": evidence.observed_at,
                    "capability_error_category": evidence.error_category,
                    "capability_affected_route_classes": list(
                        evidence.affected_route_classes
                    ),
                }
            )
        elif isinstance(evidence, Configured):
            payload.update(
                {
                    "capability_source_type": evidence.source_type,
                    "capability_config_reference": evidence.config_reference,
                }
            )
            if evidence.config_digest is not None:
                payload["capability_config_digest"] = evidence.config_digest
        else:
            payload["capability_unknown_reason"] = evidence.reason
        return payload


def _parse_observed_at(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def project_probe_record(
    record: Optional[LocalBackendProbeRecord],
    *,
    now: datetime,
    freshness_seconds: int,
) -> CapabilityEvidence:
    """Project a probe record into observation evidence. Never raises on data."""
    _validate_freshness(freshness_seconds)

    if record is None:
        return Unknown(UNKNOWN_MISSING)
    if record.error_category == "probe_disabled":
        return Unknown(UNKNOWN_PROBE_DISABLED)
    if not record.observed_at:
        # Freshness cannot be established (e.g. a synthetic_fixture record).
        return Unknown(UNKNOWN_STALE)

    observed_at = _parse_observed_at(record.observed_at)
    if observed_at is None:
        return Unknown(UNKNOWN_INVALID_RECORD)
    if (now - observed_at).total_seconds() > freshness_seconds:
        return Unknown(UNKNOWN_STALE)

    if not record.reachable:
        return ObservedUnavailable(
            source_type=record.source_type,
            evidence_tier=record.evidence_tier,
            observed_at=record.observed_at,
            freshness_seconds=freshness_seconds,
            error_category=record.error_category or "endpoint_unreachable",
            affected_route_classes=ROUTE_CLASSES,
        )

    # Reachable. The record carries no class-specific evidence, so it supports
    # no route class on its own; declarations supply class availability.
    return ObservedAvailable(
        source_type=record.source_type,
        evidence_tier=record.evidence_tier,
        observed_at=record.observed_at,
        freshness_seconds=freshness_seconds,
        supported_route_classes=(),
    )


def resolve_capability(
    *,
    record: Optional[LocalBackendProbeRecord],
    declare_local_fast: bool,
    declare_local_heavy: bool,
    config_reference: str,
    now: Optional[datetime] = None,
    freshness_seconds: int,
    record_invalid: bool = False,
) -> CapabilityResolution:
    """Apply the CR-DD-013 resolution precedence.

    1. A fresh observed-unavailable runtime suppresses every dependent route and
       cannot be overridden by a declaration.
    2. A fresh reachable runtime confirms reachability only.
    3. Route-class availability comes from explicit declarations.
    4. No usable observation and no declaration leaves capability unknown.
    """
    now = now or datetime.now(timezone.utc)
    declared = tuple(
        route_class
        for route_class, declared_flag in (
            (ROUTE_CLASS_LOCAL_FAST, declare_local_fast),
            (ROUTE_CLASS_LOCAL_HEAVY, declare_local_heavy),
        )
        if declared_flag
    )

    if record_invalid:
        observation: CapabilityEvidence = Unknown(UNKNOWN_INVALID_RECORD)
    else:
        observation = project_probe_record(
            record, now=now, freshness_seconds=freshness_seconds
        )

    # 1. A fresh negative observation is conclusive and beats declarations.
    if isinstance(observation, ObservedUnavailable):
        return CapabilityResolution(
            evidence=observation,
            lm_studio_ok=False,
            local_fast_available=False,
            local_heavy_available=False,
            declared_route_classes=declared,
            freshness_seconds=freshness_seconds,
        )

    fast = ROUTE_CLASS_LOCAL_FAST in declared
    heavy = ROUTE_CLASS_LOCAL_HEAVY in declared

    # 2. Fresh reachable: runtime confirmed; classes still require declarations.
    if isinstance(observation, ObservedAvailable):
        return CapabilityResolution(
            evidence=observation,
            lm_studio_ok=True,
            local_fast_available=fast,
            local_heavy_available=heavy,
            declared_route_classes=declared,
            freshness_seconds=freshness_seconds,
        )

    # 3. Unknown observation with an explicit declaration: route consideration is
    #    permitted, but the recorded state is Configured, never ObservedAvailable.
    if declared:
        return CapabilityResolution(
            evidence=Configured(
                config_reference=config_reference,
                declared_route_classes=declared,
            ),
            lm_studio_ok=True,
            local_fast_available=fast,
            local_heavy_available=heavy,
            declared_route_classes=declared,
            freshness_seconds=freshness_seconds,
        )

    # 4. Nothing usable. Local capability stays unknown and is not healthy.
    return CapabilityResolution(
        evidence=observation,
        lm_studio_ok=False,
        local_fast_available=False,
        local_heavy_available=False,
        declared_route_classes=(),
        freshness_seconds=freshness_seconds,
    )


def load_probe_record(path: str) -> Tuple[Optional[LocalBackendProbeRecord], bool]:
    """Read a recorded probe record. Returns ``(record, invalid)``.

    Never raises for operator data problems: a missing file yields
    ``(None, False)`` and a malformed or contract-violating file yields
    ``(None, True)`` so the caller can resolve it to ``invalid_record``.
    """
    if not path:
        return None, False
    candidate = Path(path)
    if not candidate.is_file():
        return None, False
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, True
    if not isinstance(payload, Mapping):
        return None, True
    try:
        return local_backend_probe_record_from_mapping(payload), False
    except Exception:
        return None, True


def resolve_from_config(config, *, now: Optional[datetime] = None) -> CapabilityResolution:
    """Resolve capability from the ``[capability]`` configuration section.

    Reads an already-recorded probe record when one is configured. It never
    probes: no network, subprocess, or model call happens here.
    """
    record_path = config.get_capability_probe_record_path()
    record, invalid = load_probe_record(record_path)
    return resolve_capability(
        record=record,
        declare_local_fast=config.get_capability_declare_local_fast(),
        declare_local_heavy=config.get_capability_declare_local_heavy(),
        config_reference="triagecore.toml:[capability]",
        now=now,
        freshness_seconds=config.get_capability_freshness_seconds(),
        record_invalid=invalid,
    )


def unknown_resolution(reason: str = UNKNOWN_MISSING) -> CapabilityResolution:
    """A resolution asserting nothing. Used where evidence is unavailable."""
    return CapabilityResolution(
        evidence=Unknown(reason),
        lm_studio_ok=False,
        local_fast_available=False,
        local_heavy_available=False,
    )


def describe_for_operator(resolution: CapabilityResolution) -> str:
    """One-line operator-facing summary. Never claims an unobserved failure."""
    evidence = resolution.evidence
    if isinstance(evidence, ObservedAvailable):
        return (
            f"local capability: runtime reachable (observed via {evidence.source_type}); "
            f"route classes from declaration: "
            f"{', '.join(resolution.declared_route_classes) or 'none'}"
        )
    if isinstance(evidence, ObservedUnavailable):
        return (
            f"local capability: runtime unavailable (observed via "
            f"{evidence.source_type}, {evidence.error_category})"
        )
    if isinstance(evidence, Configured):
        return (
            "local capability: unknown (no usable observation); proceeding on the "
            f"explicit declaration in {evidence.config_reference}"
        )
    return f"local capability: unknown ({evidence.reason}); no local route is asserted"
