"""Validated, non-durable runtime observation for governed execution binding.

CR-DD-012B. A :class:`RuntimeObservation` is created **after** a valid governed
decision exists. It never enters ``decision_body`` or ``decision_id``, is never
persisted as its own schema, and lives only long enough to validate envelope
compliance and populate bounded evidence.

Subsumption without re-derivation. ``capability_evidence.CapabilityResolution``
remains the sole source of local capability evidence: this module adds no probe,
no second resolver, and no independent availability check. It *carries* the
already-resolved capability state as provenance and adds only what CR-DD-013
does not model -- the selected envelope member, the actual backend/model
binding, whether a fallback occurred, and bounded reason codes.

Capability constrains **binding only**. It answers "can the already-authorized
plan execute right now?" and never "what policy or route should this task
receive?" (CR-DD-012B Resolved Question 1). Nothing here may synthesize a route,
reorder the envelope, append to it, widen egress, downgrade privacy, waive human
review, or enable cloud that the governed decision did not permit.

CR-DD-013's observed/configured/unknown distinction is preserved verbatim: an
absent or unknown observation resolves to unknown. It never becomes an observed
failure, and it never becomes health.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional, Tuple

from triage_core.governed_decision import (
    GovernedDecision,
    verify_governed_decision_id,
)

_DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")

OBSERVATION_CONTRACT_VERSION = "governed_runtime_observation.v1"

BINDING_OUTCOMES = frozenset({"primary", "authorized_fallback", "closed"})

#: Closed vocabulary. A reason code names *why* one envelope member did or did
#: not bind; it never encodes a route name, a path, or any operator content.
BINDING_REASON_CODES = frozenset(
    {
        "bound_preferred_route",
        "bound_authorized_fallback",
        "terminal_human_handoff",
        "deterministic_executor_not_wired",
        "cloud_route_not_enabled",
        "local_capability_unavailable",
        "local_capability_unknown",
        "route_model_binding_missing",
        "no_authorized_binding_available",
    }
)

#: CR-DD-013 capability states, carried verbatim. Never flattened or promoted.
CAPABILITY_STATES = frozenset(
    {
        "observed_available",
        "observed_unavailable",
        "configured",
        "unknown",
    }
)

_LOCAL_ROUTES = frozenset({"local_fast", "local_heavy"})
_CLOUD_ROUTES = frozenset({"cloud_primary", "cloud_secondary"})


class RuntimeObservationError(ValueError):
    """A bounded runtime-observation validation failure."""


class GovernedBindingError(RuntimeObservationError):
    """Fail-closed: the attempt terminates before backend construction."""


def _require_text(value: Any, name: str) -> str:
    if type(value) is not str:
        raise RuntimeObservationError(f"{name} must be text")
    return value


@dataclass(frozen=True, slots=True)
class RuntimeObservation:
    """One validated, internal, non-durable execution-binding observation."""

    contract_version: str
    decision_id: str
    binding_outcome: str
    selected_route: Optional[str]
    envelope_position: Optional[int]
    backend_binding: str
    model_binding: str
    fallback_occurred: bool
    capability_state: Optional[str]
    capability_source_type: Optional[str]
    capability_evidence_tier: Optional[str]
    capability_freshness_seconds: Optional[int]
    reason_codes: Tuple[str, ...]

    def __post_init__(self) -> None:
        if self.contract_version != OBSERVATION_CONTRACT_VERSION:
            raise RuntimeObservationError("unsupported observation contract")
        if not _DIGEST_RE.fullmatch(_require_text(self.decision_id, "decision_id")):
            raise RuntimeObservationError("decision_id is not a bounded digest")
        if self.binding_outcome not in BINDING_OUTCOMES:
            raise RuntimeObservationError("unsupported binding outcome")
        if type(self.reason_codes) is not tuple:
            raise RuntimeObservationError("reason_codes must be an ordered tuple")
        for code in self.reason_codes:
            if code not in BINDING_REASON_CODES:
                raise RuntimeObservationError(f"unbounded reason code: {code!r}")
        if type(self.fallback_occurred) is not bool:
            raise RuntimeObservationError("fallback_occurred must be boolean")
        _require_text(self.backend_binding, "backend_binding")
        _require_text(self.model_binding, "model_binding")

        if self.binding_outcome == "closed":
            if self.selected_route is not None or self.envelope_position is not None:
                raise RuntimeObservationError("a closed binding selects no route")
            if self.backend_binding or self.model_binding:
                raise RuntimeObservationError("a closed binding names no backend")
            if self.fallback_occurred:
                raise RuntimeObservationError("a closed binding is not a fallback")
        else:
            _require_text(self.selected_route, "selected_route")
            if type(self.envelope_position) is not int:
                raise RuntimeObservationError("envelope_position must be an integer")
            if self.envelope_position < 0:
                raise RuntimeObservationError("envelope_position must be non-negative")
            if (self.binding_outcome == "primary") != (self.envelope_position == 0):
                raise RuntimeObservationError(
                    "primary binding is exactly envelope position zero"
                )
            if self.fallback_occurred != (
                self.binding_outcome == "authorized_fallback"
            ):
                raise RuntimeObservationError("fallback flag contradicts the outcome")

        if (
            self.capability_state is not None
            and self.capability_state not in CAPABILITY_STATES
        ):
            raise RuntimeObservationError("unsupported capability state")
        if self.capability_freshness_seconds is not None:
            if type(self.capability_freshness_seconds) is not int:
                raise RuntimeObservationError("capability freshness must be an integer")
            if self.capability_freshness_seconds < 0:
                raise RuntimeObservationError(
                    "capability freshness must be non-negative"
                )


def _capability_provenance(capability: Any) -> dict:
    """Carry already-resolved CR-DD-013 state. Never re-derive or relabel it."""

    evidence = getattr(capability, "evidence", None)
    state = getattr(evidence, "state", None)
    return {
        "capability_state": state if state in CAPABILITY_STATES else None,
        "capability_source_type": getattr(evidence, "source_type", None),
        "capability_evidence_tier": getattr(evidence, "evidence_tier", None),
        "capability_freshness_seconds": getattr(capability, "freshness_seconds", None),
    }


def _member_binding(
    route: str,
    *,
    capability: Any,
    cloud_enabled: bool,
    local_backend_type: str,
    cloud_model: str,
) -> Tuple[bool, str, str, str]:
    """Filter one envelope member. Returns ``(bound, backend, model, code)``.

    This is a *filter over a closed set*, never a selection over the space of
    backends: it is only ever called with a member the governed decision already
    authorized, and it can only say yes or no to that member.
    """

    if route == "human_handoff":
        return True, "", "", "terminal_human_handoff"
    if route == "deterministic":
        return False, "", "", "deterministic_executor_not_wired"
    if route in _CLOUD_ROUTES:
        if not cloud_enabled:
            return False, "", "", "cloud_route_not_enabled"
        return True, "qwen", cloud_model, "bound_preferred_route"
    if route in _LOCAL_ROUTES:
        if capability is None:
            # Missing observation is not unavailability (CR-DD-013).
            return False, "", "", "local_capability_unknown"
        available = bool(
            getattr(capability, "lm_studio_ok", False)
            and getattr(capability, f"{route}_available", False)
        )
        if not available:
            state = getattr(getattr(capability, "evidence", None), "state", None)
            if state == "unknown":
                return False, "", "", "local_capability_unknown"
            return False, "", "", "local_capability_unavailable"
        model = capability.model_for_route(route) or ""
        if not model:
            return False, "", "", "route_model_binding_missing"
        return True, local_backend_type, model, "bound_preferred_route"
    raise GovernedBindingError("envelope member is not a known logical route")


def envelope_members(decision: GovernedDecision) -> Tuple[str, ...]:
    """The closed, ordered set of routes this decision authorizes."""

    if type(decision) is not GovernedDecision:
        raise GovernedBindingError("a governed decision is required")
    policy = decision.policy
    return (policy.preferred_logical_route, *policy.permitted_fallback_envelope)


def observe_route_binding(
    *,
    decision: GovernedDecision,
    capability: Any,
    cloud_enabled: bool,
    local_backend_type: str,
    cloud_model: str,
) -> RuntimeObservation:
    """Bind the governed decision to a runtime route, or fail closed.

    Exactly three outcomes are reachable, matching CR-DD-012B's runtime outcome
    model: the primary member binds, an already-authorized envelope member binds,
    or no authorized binding exists and the attempt closes. There is no fourth
    outcome -- a route outside the envelope is unreachable by construction,
    because the loop only ever visits members the decision already named.
    """

    if type(decision) is not GovernedDecision:
        raise GovernedBindingError("a governed decision is required")
    if not verify_governed_decision_id(decision):
        raise GovernedBindingError("decision_id does not match the decision body")

    provenance = _capability_provenance(capability)
    members = envelope_members(decision)
    reason_codes: list[str] = []

    for position, route in enumerate(members):
        bound, backend, model, code = _member_binding(
            route,
            capability=capability,
            cloud_enabled=cloud_enabled,
            local_backend_type=local_backend_type,
            cloud_model=cloud_model,
        )
        if not bound:
            reason_codes.append(code)
            continue
        if code == "terminal_human_handoff":
            selected_code = code
        elif position == 0:
            selected_code = "bound_preferred_route"
        else:
            selected_code = "bound_authorized_fallback"
        reason_codes.append(selected_code)
        return RuntimeObservation(
            contract_version=OBSERVATION_CONTRACT_VERSION,
            decision_id=decision.decision_id,
            binding_outcome="primary" if position == 0 else "authorized_fallback",
            selected_route=route,
            envelope_position=position,
            backend_binding=backend,
            model_binding=model,
            fallback_occurred=position != 0,
            reason_codes=tuple(reason_codes),
            **provenance,
        )

    reason_codes.append("no_authorized_binding_available")
    return RuntimeObservation(
        contract_version=OBSERVATION_CONTRACT_VERSION,
        decision_id=decision.decision_id,
        binding_outcome="closed",
        selected_route=None,
        envelope_position=None,
        backend_binding="",
        model_binding="",
        fallback_occurred=False,
        reason_codes=tuple(reason_codes),
        **provenance,
    )


def validate_envelope_compliance(
    observation: RuntimeObservation,
    decision: GovernedDecision,
) -> None:
    """Independently reject a binding that escaped the governed envelope.

    Declared separately from the producer on purpose, following the CR-DD-018
    precedent in ``routing/route_events.py``: the producer emits a bounded
    binding and this checker independently verifies it satisfies the envelope.
    Sharing one definition would remove the second check.
    """

    if type(observation) is not RuntimeObservation:
        raise GovernedBindingError("a validated runtime observation is required")
    if observation.decision_id != getattr(decision, "decision_id", None):
        raise GovernedBindingError("observation is bound to a different decision")
    if not verify_governed_decision_id(decision):
        raise GovernedBindingError("decision_id does not match the decision body")
    if observation.binding_outcome == "closed":
        return
    members = envelope_members(decision)
    position = observation.envelope_position
    if position is None or position >= len(members):
        raise GovernedBindingError("binding position is outside the envelope")
    if members[position] != observation.selected_route:
        raise GovernedBindingError("runtime binding is outside the governed envelope")
