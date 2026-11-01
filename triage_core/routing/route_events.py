import re
from typing import Any, Dict

from .resilience_router import ResilienceRouteDecision, ResilienceRouteInput

# CR-DD-012B: bounded governed-decision linkage. Additive, through the existing
# open extension point; the closed ``route-worker-ledger.v1`` contract in
# ``route_worker_ledger.py`` is neither modified nor used by this path.
_DECISION_ID_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")

# CR-DD-018: the accepted specialist-offload evidence contract. These constants are
# declared independently of the producer's own vocabulary on purpose: the producer
# emits a bounded decision and this module independently verifies that it satisfies
# the durable contract. Sharing one definition would remove that second check.
SPECIALIST_OFFLOAD_EVENT_TYPE = "specialist_offload_decision"

SPECIALIST_REASON_CODES = frozenset(
    {"high_risk", "safety_handoff", "medium_risk_online", "context_limit_online"}
)
SPECIALIST_RISK_LEVELS = frozenset({"low", "medium", "high"})
SPECIALIST_HIGH_RISK_CATEGORIES = frozenset(
    {"destructive_ops", "system_modifications", "secrets_and_auth"}
)
SPECIALIST_MEDIUM_RISK_CATEGORIES = frozenset(
    {"package_management", "deployment_config"}
)
SPECIALIST_RISK_CATEGORIES = (
    SPECIALIST_HIGH_RISK_CATEGORIES | SPECIALIST_MEDIUM_RISK_CATEGORIES
)

_SPECIALIST_COMMON_FIELDS = ("offload_reason_code", "risk_level", "risk_categories")
# Variant fields that MUST be present and exactly ``True``. Any field not listed for
# a variant MUST be absent -- never present-and-null.
_SPECIALIST_VARIANT_REQUIRED_TRUE = {
    "high_risk": (),
    "safety_handoff": (),
    "medium_risk_online": ("internet_available",),
    "context_limit_online": ("internet_available", "context_limit_exceeded"),
}


class SpecialistOffloadPayloadError(ValueError):
    """Raised when specialist-offload evidence violates the accepted contract."""


def _require_str(value: Any, field_name: str) -> None:
    """Reject a wrong-typed value before it reaches a membership/set operation.

    `value not in a_frozenset` and `set(a_list_with_this_value)` both raise a raw
    ``TypeError`` for an unhashable value (e.g. a list or dict) instead of the
    dedicated contract error. Calling this first ensures every malformed input is
    rejected as ``SpecialistOffloadPayloadError``, never a bare ``TypeError``.
    """
    if not isinstance(value, str):
        raise SpecialistOffloadPayloadError(
            f"{field_name} must be a string, got {type(value).__name__}"
        )


def _require_risk_consistency(reason_code: str, risk_level: str, categories: list) -> None:
    """Cross-field rules mirroring what DangerDetector actually establishes."""
    category_set = set(categories)
    if risk_level == "high":
        if not (category_set & SPECIALIST_HIGH_RISK_CATEGORIES):
            raise SpecialistOffloadPayloadError(
                "risk_level=high requires at least one high-risk category"
            )
    elif risk_level == "medium":
        if category_set & SPECIALIST_HIGH_RISK_CATEGORIES:
            raise SpecialistOffloadPayloadError(
                "risk_level=medium must not carry a high-risk category"
            )
        if not (category_set & SPECIALIST_MEDIUM_RISK_CATEGORIES):
            raise SpecialistOffloadPayloadError(
                "risk_level=medium requires at least one medium-risk category"
            )
    else:  # low
        if category_set:
            raise SpecialistOffloadPayloadError(
                "risk_level=low requires an empty risk_categories list"
            )

    # Variant-specific risk level, except safety_handoff which admits any valid level
    # because the explicit category triggers the branch independently of risk.
    expected_level = {
        "high_risk": "high",
        "medium_risk_online": "medium",
        "context_limit_online": "low",
    }.get(reason_code)
    if expected_level is not None and risk_level != expected_level:
        raise SpecialistOffloadPayloadError(
            f"{reason_code} requires risk_level={expected_level}, got {risk_level}"
        )


def build_specialist_offload_payload(route_task_result: Dict[str, Any]) -> Dict[str, Any]:
    """Canonicalize a ``route_task`` structured cause into durable event evidence.

    The builder canonicalizes: it validates category membership, deduplicates, and
    sorts categories into canonical order. It reads only the bounded structured cause
    produced by the same ``route_task`` invocation whose decision is being recorded --
    it never parses the free-form ``reason``, re-runs danger detection or connectivity
    probing, or inspects raw prompt/data/category.
    """
    cause = route_task_result.get("specialist_offload_cause")
    if not isinstance(cause, dict):
        raise SpecialistOffloadPayloadError(
            "route_task result carries no specialist_offload_cause; specialist evidence "
            "must come from the same decision invocation and is never re-derived"
        )

    reason_code = cause.get("offload_reason_code")
    _require_str(reason_code, "offload_reason_code")
    if reason_code not in SPECIALIST_REASON_CODES:
        raise SpecialistOffloadPayloadError(
            f"unknown offload_reason_code: {reason_code!r}"
        )

    risk_level = cause.get("risk_level")
    _require_str(risk_level, "risk_level")
    if risk_level not in SPECIALIST_RISK_LEVELS:
        raise SpecialistOffloadPayloadError(f"unknown risk_level: {risk_level!r}")

    raw_categories = cause.get("risk_categories")
    if not isinstance(raw_categories, (list, tuple)):
        raise SpecialistOffloadPayloadError("risk_categories must be a list")
    for element in raw_categories:
        _require_str(element, "risk_categories element")
    unknown = set(raw_categories) - SPECIALIST_RISK_CATEGORIES
    if unknown:
        raise SpecialistOffloadPayloadError(
            f"unknown risk categories: {sorted(unknown)}"
        )
    categories = sorted(set(raw_categories))

    _require_risk_consistency(reason_code, risk_level, categories)

    payload: Dict[str, Any] = {
        "offload_reason_code": reason_code,
        "risk_level": risk_level,
        "risk_categories": categories,
    }
    for field in _SPECIALIST_VARIANT_REQUIRED_TRUE[reason_code]:
        if cause.get(field) is not True:
            raise SpecialistOffloadPayloadError(
                f"{reason_code} requires {field}=True"
            )
        payload[field] = True

    validate_specialist_offload_payload(payload)
    return payload


def validate_specialist_offload_payload(payload: Any) -> None:
    """Independently reject a durable specialist payload that violates the contract.

    This validator rejects; it never silently repairs. A payload with noncanonical
    category ordering is invalid, not something to re-sort, because silent repair
    would mask exactly the drift canonical form exists to detect.
    """
    if not isinstance(payload, dict):
        raise SpecialistOffloadPayloadError("payload must be a dict")

    reason_code = payload.get("offload_reason_code")
    _require_str(reason_code, "offload_reason_code")
    if reason_code not in SPECIALIST_REASON_CODES:
        raise SpecialistOffloadPayloadError(
            f"unknown offload_reason_code: {reason_code!r}"
        )

    expected_keys = set(_SPECIALIST_COMMON_FIELDS) | set(
        _SPECIALIST_VARIANT_REQUIRED_TRUE[reason_code]
    )
    actual_keys = set(payload)
    if actual_keys != expected_keys:
        missing = sorted(expected_keys - actual_keys)
        forbidden = sorted(actual_keys - expected_keys)
        raise SpecialistOffloadPayloadError(
            f"exact key set violated for {reason_code}: missing={missing} "
            f"forbidden={forbidden}"
        )

    risk_level = payload["risk_level"]
    _require_str(risk_level, "risk_level")
    if risk_level not in SPECIALIST_RISK_LEVELS:
        raise SpecialistOffloadPayloadError(f"unknown risk_level: {risk_level!r}")

    categories = payload["risk_categories"]
    if not isinstance(categories, list):
        raise SpecialistOffloadPayloadError("risk_categories must be a list")
    for element in categories:
        _require_str(element, "risk_categories element")
    unknown = set(categories) - SPECIALIST_RISK_CATEGORIES
    if unknown:
        raise SpecialistOffloadPayloadError(
            f"unknown risk categories: {sorted(unknown)}"
        )
    if len(set(categories)) != len(categories):
        raise SpecialistOffloadPayloadError("risk_categories contains duplicates")
    if categories != sorted(categories):
        raise SpecialistOffloadPayloadError(
            "risk_categories must be in canonical sorted order"
        )

    for field in _SPECIALIST_VARIANT_REQUIRED_TRUE[reason_code]:
        if payload[field] is not True:
            raise SpecialistOffloadPayloadError(f"{reason_code} requires {field}=True")

    _require_risk_consistency(reason_code, risk_level, categories)


class DecisionLinkageError(ValueError):
    """Raised when governed-decision linkage evidence is not bounded."""


class GovernedEvidencePayloadError(ValueError):
    """A bounded CR-DD-019 validation failure, without caller-supplied text."""

    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


# Independent of the producer's vocabulary: widening it requires contract review.
_GOVERNED_EVIDENCE_FIELDS = frozenset({
    "governed_risk_posture", "binding_outcome", "binding_reason_codes",
})
_GOVERNED_RISKS = frozenset({"low", "medium", "high"})
_GOVERNED_OUTCOMES = frozenset({"primary", "authorized_fallback"})
_GOVERNED_BOUND_ROUTES = frozenset({
    "local_fast", "local_heavy", "cloud_primary", "cloud_secondary", "human_handoff",
})
_GOVERNED_FAILURE_CODES = frozenset({
    "deterministic_executor_not_wired", "cloud_route_not_enabled",
    "local_capability_unavailable", "local_capability_unknown", "route_model_binding_missing",
})
_GOVERNED_BINDING_CODES = _GOVERNED_FAILURE_CODES | frozenset({
    "bound_preferred_route", "bound_authorized_fallback", "terminal_human_handoff",
})


def _validated_governed_evidence(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate a route's optional extension and return an owned forwarding copy.

    The surrounding payload stays open. Linkage-only historical records stay
    valid; these checks do not establish approval or independently redo binding.
    """
    present = _GOVERNED_EVIDENCE_FIELDS.intersection(payload)
    if not present:
        return {}
    # A present null field is malformed shape, even when linkage is also bad.
    if present != _GOVERNED_EVIDENCE_FIELDS or any(payload[key] is None for key in present):
        raise GovernedEvidencePayloadError("invalid_governed_evidence_shape")

    decision_id = payload.get("decision_id")
    if type(decision_id) is not str or not _DECISION_ID_RE.fullmatch(decision_id):
        raise GovernedEvidencePayloadError("invalid_governed_evidence_linkage")

    risk = payload["governed_risk_posture"]
    outcome = payload["binding_outcome"]
    codes = payload["binding_reason_codes"]
    route = payload.get("selected_route")
    depth = payload.get("fallback_depth")
    sensitivity = payload.get("task_sensitivity")
    review = payload.get("human_review_required")
    if (
        type(risk) is not str or risk not in _GOVERNED_RISKS
        or type(outcome) is not str or outcome not in _GOVERNED_OUTCOMES
        or type(codes) is not list or not 1 <= len(codes) <= 6
        or any(type(code) is not str or code not in _GOVERNED_BINDING_CODES for code in codes)
        or type(route) is not str or route not in _GOVERNED_BOUND_ROUTES
        or type(depth) is not int or not 0 <= depth <= 5
        or type(sensitivity) is not str or sensitivity not in _GOVERNED_RISKS
        or type(review) is not bool
    ):
        raise GovernedEvidencePayloadError("invalid_governed_evidence_value")

    suffix = (
        "terminal_human_handoff" if route == "human_handoff"
        else "bound_preferred_route" if outcome == "primary"
        else "bound_authorized_fallback"
    )
    if (
        (outcome == "primary") != (depth == 0)
        or len(codes) != depth + 1
        or codes[-1] != suffix
        or any(code not in _GOVERNED_FAILURE_CODES for code in codes[:-1])
        or (risk == "high" and (sensitivity != "high" or not review))
    ):
        raise GovernedEvidencePayloadError("inconsistent_governed_evidence")
    return {
        "governed_risk_posture": risk,
        "binding_outcome": outcome,
        "binding_reason_codes": list(codes),
    }


def _bounded_decision_id(value: Any) -> str:
    """Reject anything that is not a bounded content-linkage digest.

    Linkage is evidence only. A present ``decision_id`` records which governed
    decision an attempt descended from. It asserts nothing about approval,
    admission, quality, acceptance, or successful human review, and no consumer
    may read it as such.
    """
    if not isinstance(value, str) or not _DECISION_ID_RE.fullmatch(value):
        raise DecisionLinkageError("decision_id must be a bounded sha256 digest")
    return value


def build_route_decision_payload(
    route_input: ResilienceRouteInput,
    route_decision: ResilienceRouteDecision,
    *,
    selected_backend: str = "",
    selected_model: str = "",
    route_source: str = "resilience_router_v1",
    decision_id: Any = None,
    governed_evidence: Any = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "task_class": route_input.task_class,
        "task_complexity": route_input.complexity,
        "task_sensitivity": route_input.sensitivity,
        "task_privacy_level": route_input.privacy_level,
        "selected_route": route_decision.selected_route,
        "selected_backend": selected_backend,
        "selected_model": selected_model,
        "reason": route_decision.reason,
        "fallback_depth": route_decision.fallback_depth,
        "human_review_required": route_decision.human_review_required,
        "required_checks": list(route_decision.required_checks),
        "internet_ok": route_input.internet_ok,
        "cloud_primary_available": route_input.cloud_primary_available,
        "cloud_secondary_available": route_input.cloud_secondary_available,
        "cloud_credit_state": route_input.cloud_credit_state,
        "lm_studio_ok": route_input.lm_studio_ok,
        "local_heavy_available": route_input.local_heavy_available,
        "local_fast_available": route_input.local_fast_available,
        "memory_headroom_mb": route_input.memory_headroom_mb,
        "deterministic_tool_available": route_input.deterministic_tool_available,
        "recent_cloud_failures": route_input.recent_cloud_failures,
        "recent_local_heavy_failures": route_input.recent_local_heavy_failures,
        "recent_local_fast_failures": route_input.recent_local_fast_failures,
        "route_source": route_source,
    }

    # CR-DD-013: capability provenance through the existing open route_decision
    # payload. No new ledger schema and no schema-version bump; the closed
    # route-worker-ledger.v1 contract is untouched.
    capability = getattr(route_input, "capability_evidence", None)
    if capability is not None and hasattr(capability, "to_evidence_payload"):
        payload.update(capability.to_evidence_payload())

    # CR-DD-012B: bounded governed-decision linkage through the same open
    # extension point. Additive, so no schema-version bump is needed.
    if governed_evidence is not None:
        if (
            type(governed_evidence) is not dict
            or any(type(key) is not str for key in governed_evidence)
            or set(governed_evidence) != _GOVERNED_EVIDENCE_FIELDS
        ):
            raise GovernedEvidencePayloadError("invalid_governed_evidence_shape")
        payload.update(governed_evidence)
        payload["decision_id"] = decision_id
        payload.update(_validated_governed_evidence(payload))
    elif decision_id is not None:
        payload["decision_id"] = _bounded_decision_id(decision_id)

    return payload


def build_worker_result_payload(
    route_payload: Dict[str, Any],
    result: Dict[str, Any],
) -> Dict[str, Any]:
    # The route, not worker output, owns policy/binding provenance. Revalidation
    # here can happen after execution and must never be labelled pre-execution.
    governed_evidence = _validated_governed_evidence(route_payload)
    failure_type = result.get("failure_type")
    failure_stage = result.get("failure_stage")
    backend_failure = bool(failure_type == "backend_error" and failure_stage == "local_backend_generate")

    payload = {
        "selected_route": route_payload.get("selected_route"),
        "selected_backend": route_payload.get("selected_backend", ""),
        "selected_model": route_payload.get("selected_model", ""),
        "reason": route_payload.get("reason", ""),
        "fallback_depth": route_payload.get("fallback_depth"),
        "worker_result_status": result.get("worker_result_status", "not_attempted"),
        "validation_status": result.get("validation_status", "not_run"),
        "failure_type": failure_type,
        "failure_stage": failure_stage,
        "backend_failure": backend_failure,
        "status": result.get("status", ""),
        "source": result.get("source", ""),
        "elapsed_seconds": result.get("elapsed_seconds", 0.0),
        "timeout_seconds": result.get("timeout_seconds"),
        "input_tokens": result.get("input_tokens", 0),
        "output_tokens": result.get("output_tokens", 0),
        "total_tokens": result.get("total_tokens", 0),
        "tokens_per_second": result.get("tokens_per_second", 0.0),
        "validator_name": result.get("validator_name"),
        "validator_version": result.get("validator_version"),
        "validator_scope": result.get("validator_scope"),
    }

    # Linkage is carried forward from the route decision this attempt descended
    # from -- never re-derived here, and never synthesized when absent.
    if "decision_id" in route_payload:
        payload["decision_id"] = _bounded_decision_id(route_payload["decision_id"])
    payload.update(governed_evidence)

    return payload
