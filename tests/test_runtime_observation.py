"""CR-DD-012B: envelope constraint and runtime/decision separation.

Every test here is deterministic and fully offline: no network, socket,
subprocess, model call, or real runtime is involved.

The property under test is the one the slice exists to establish -- a volatile
runtime observation may decide *whether* an already-authorized plan can execute
right now, and never *what* policy or route the task receives.
"""

from __future__ import annotations

import pytest

from triage_core import capability_evidence
from triage_core.governed_decision import (
    CLASSIFICATION_POLICY_VERSION,
    CONFIGURATION_VERSION,
    POLICY_VERSION,
    ROUTE_POLICY_VERSION,
    VERIFICATION_POLICY_VERSION,
    DecisionPolicyConfiguration,
    build_governed_decision,
)
from triage_core.governed_run_snapshot import (
    build_governed_run_input_snapshot,
    normalize_operator_declarations,
    resolve_context_model_profile,
    sha256_digest,
    SourceBytesInput,
    WorkerSystemMessageBinding,
)
from triage_core.run_plan import (
    DEFAULT_RUN_MODEL_PROFILE,
    RUN_SNAPSHOT_LIMITS,
    WORKER_SYSTEM_MESSAGE,
    WORKER_SYSTEM_MESSAGE_VERSION,
    configuration_digest,
    context_model_profiles,
)
from triage_core.runtime_observation import (
    BINDING_REASON_CODES,
    OBSERVATION_CONTRACT_VERSION,
    GovernedBindingError,
    RuntimeObservation,
    RuntimeObservationError,
    envelope_members,
    observe_route_binding,
    validate_envelope_compliance,
)

LOCAL_FAST_MODEL = "qwen2.5-coder:7b-triagecore"
LOCAL_HEAVY_MODEL = "deepseek-r1:latest"


def _snapshot(*, prompt="Summarize this text", privacy="local_only", cloud=False):
    profile = resolve_context_model_profile(
        DEFAULT_RUN_MODEL_PROFILE,
        default_profile=DEFAULT_RUN_MODEL_PROFILE,
        profiles=context_model_profiles(),
    )
    return build_governed_run_input_snapshot(
        prompt=prompt,
        sources=(),
        inline_input=None,
        declarations=normalize_operator_declarations(
            task_id=None,
            declared_privacy=privacy,
            cloud_intent=cloud,
            resolved_profile=profile,
        ),
        resolved_profile=profile,
        worker_system_message=WorkerSystemMessageBinding(
            version=WORKER_SYSTEM_MESSAGE_VERSION,
            sha256=sha256_digest(WORKER_SYSTEM_MESSAGE.encode("utf-8")),
        ),
        limits=RUN_SNAPSHOT_LIMITS,
    )


def _decision(
    preferred,
    envelope=(),
    *,
    privacy="local_only",
    cloud=False,
    human_review="not_required",
    prompt="Summarize this text",
):
    snapshot = _snapshot(prompt=prompt, privacy=privacy, cloud=cloud)
    configuration = DecisionPolicyConfiguration(
        configuration_version=CONFIGURATION_VERSION,
        configuration_sha256=configuration_digest(
            cloud_backend_enabled=False,
            cloud_model_binding="not_enabled",
            local_backend_type="ollama",
        ),
        policy_version=POLICY_VERSION,
        classification_policy_version=CLASSIFICATION_POLICY_VERSION,
        route_policy_version=ROUTE_POLICY_VERSION,
        verification_policy_version=VERIFICATION_POLICY_VERSION,
        estimated_input_tokens=8,
        usable_input_tokens=6912,
        privacy_preflight="passed",
        classification="refactor",
        risk_posture="low",
        classification_reason_codes=("deterministic_classifier_default",),
        preferred_logical_route=preferred,
        permitted_fallback_envelope=tuple(envelope),
        route_reason_codes=("policy_selected",),
        terminal_escalation="none",
        ethical_firewall="clear",
        human_review=(
            "required" if preferred == "human_handoff" else human_review
        ),
        escalation_conditions=(),
        required_checks=("packet_verification", "privacy_preflight"),
    )
    return snapshot, build_governed_decision(snapshot, configuration)


def _capability(*, fast=True, heavy=True, observed=True):
    if not observed:
        return capability_evidence.unknown_resolution()
    return capability_evidence.resolve_capability(
        record=None,
        declare_local_fast=fast,
        declare_local_heavy=heavy,
        local_fast_model=LOCAL_FAST_MODEL if fast else "",
        local_heavy_model=LOCAL_HEAVY_MODEL if heavy else "",
        config_reference="test:[capability]",
        freshness_seconds=300,
    )


def _observe(decision, capability, **overrides):
    kwargs = dict(
        decision=decision,
        capability=capability,
        cloud_enabled=False,
        local_backend_type="ollama",
        cloud_model="",
    )
    kwargs.update(overrides)
    return observe_route_binding(**kwargs)


# --------------------------------------------------------------------------
# Outcome 1 and 2: primary binding, and an already-authorized fallback.
# --------------------------------------------------------------------------


def test_primary_envelope_member_binds_as_outcome_one():
    _, decision = _decision("local_heavy", ("local_fast", "human_handoff"))
    observation = _observe(decision, _capability())

    assert observation.binding_outcome == "primary"
    assert observation.selected_route == "local_heavy"
    assert observation.envelope_position == 0
    assert observation.fallback_occurred is False
    assert observation.model_binding == LOCAL_HEAVY_MODEL
    validate_envelope_compliance(observation, decision)


def test_unavailable_primary_binds_an_authorized_fallback_as_outcome_two():
    _, decision = _decision("local_heavy", ("local_fast", "human_handoff"))
    observation = _observe(decision, _capability(heavy=False))

    assert observation.binding_outcome == "authorized_fallback"
    assert observation.selected_route == "local_fast"
    assert observation.envelope_position == 1
    assert observation.fallback_occurred is True
    assert "local_capability_unavailable" in observation.reason_codes
    assert "bound_authorized_fallback" in observation.reason_codes
    validate_envelope_compliance(observation, decision)


def test_no_authorized_binding_closes_as_outcome_three():
    _, decision = _decision("local_heavy", ("local_fast",))
    observation = _observe(decision, _capability(fast=False, heavy=False))

    assert observation.binding_outcome == "closed"
    assert observation.selected_route is None
    assert observation.envelope_position is None
    assert observation.backend_binding == ""
    assert observation.reason_codes[-1] == "no_authorized_binding_available"
    validate_envelope_compliance(observation, decision)


# --------------------------------------------------------------------------
# The forbidden fourth outcome, asserted directly rather than assumed.
# --------------------------------------------------------------------------


def test_binding_never_leaves_the_governed_envelope():
    """No capability posture can produce a route the decision did not name."""

    _, decision = _decision("local_heavy", ("human_handoff",))
    permitted = set(envelope_members(decision))

    for fast, heavy, observed in (
        (True, True, True),
        (True, False, True),
        (False, True, True),
        (False, False, True),
        (False, False, False),
    ):
        observation = _observe(
            decision, _capability(fast=fast, heavy=heavy, observed=observed)
        )
        assert observation.selected_route in permitted | {None}
        validate_envelope_compliance(observation, decision)


def test_envelope_compliance_rejects_a_route_outside_the_envelope():
    _, decision = _decision("local_heavy", ("human_handoff",))
    forged = RuntimeObservation(
        contract_version=OBSERVATION_CONTRACT_VERSION,
        decision_id=decision.decision_id,
        binding_outcome="authorized_fallback",
        selected_route="cloud_primary",
        envelope_position=1,
        backend_binding="qwen",
        model_binding="qwen-max",
        fallback_occurred=True,
        capability_state=None,
        capability_source_type=None,
        capability_evidence_tier=None,
        capability_freshness_seconds=None,
        reason_codes=("bound_authorized_fallback",),
    )
    with pytest.raises(GovernedBindingError):
        validate_envelope_compliance(forged, decision)


def test_envelope_compliance_rejects_a_position_past_the_envelope():
    _, decision = _decision("human_handoff")
    forged = RuntimeObservation(
        contract_version=OBSERVATION_CONTRACT_VERSION,
        decision_id=decision.decision_id,
        binding_outcome="authorized_fallback",
        selected_route="human_handoff",
        envelope_position=4,
        backend_binding="",
        model_binding="",
        fallback_occurred=True,
        capability_state=None,
        capability_source_type=None,
        capability_evidence_tier=None,
        capability_freshness_seconds=None,
        reason_codes=("bound_authorized_fallback",),
    )
    with pytest.raises(GovernedBindingError):
        validate_envelope_compliance(forged, decision)


def test_observation_from_one_decision_is_rejected_against_another():
    _, first = _decision("local_heavy", ("human_handoff",))
    _, second = _decision("local_fast", ("human_handoff",), prompt="Fix the bug")
    observation = _observe(first, _capability())

    with pytest.raises(GovernedBindingError):
        validate_envelope_compliance(observation, second)


# --------------------------------------------------------------------------
# Approval gate 4: capability volatility cannot reach decision identity.
# --------------------------------------------------------------------------


def test_capability_change_after_decision_formation_changes_no_policy():
    snapshot, decision = _decision("local_heavy", ("local_fast", "human_handoff"))
    decision_id = decision.decision_id
    preferred = decision.policy.preferred_logical_route
    envelope = decision.policy.permitted_fallback_envelope

    healthy = _observe(decision, _capability())
    degraded = _observe(decision, _capability(heavy=False))
    dark = _observe(decision, _capability(fast=False, heavy=False))
    unknown = _observe(decision, _capability(observed=False))

    # The observations differ. The decision does not.
    assert healthy.selected_route == "local_heavy"
    assert degraded.selected_route == "local_fast"
    assert dark.selected_route == "human_handoff"
    assert unknown.selected_route == "human_handoff"

    assert decision.decision_id == decision_id
    assert decision.policy.preferred_logical_route == preferred
    assert decision.policy.permitted_fallback_envelope == envelope
    for observation in (healthy, degraded, dark, unknown):
        assert observation.decision_id == decision_id
        validate_envelope_compliance(observation, decision)


# --------------------------------------------------------------------------
# Approval gate 5: unavailable capability produces only an authorized fallback
# or a closed failure -- never an unauthorized route.
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("envelope", "expected_outcome", "expected_route"),
    [
        (("local_fast", "human_handoff"), "authorized_fallback", "local_fast"),
        (("human_handoff",), "authorized_fallback", "human_handoff"),
        ((), "closed", None),
    ],
)
def test_unavailable_capability_falls_back_or_closes(
    envelope, expected_outcome, expected_route
):
    _, decision = _decision("local_heavy", envelope)
    observation = _observe(decision, _capability(heavy=False))

    assert observation.binding_outcome == expected_outcome
    assert observation.selected_route == expected_route
    validate_envelope_compliance(observation, decision)


def test_missing_model_binding_is_not_a_route_invention():
    _, decision = _decision("local_heavy", ("human_handoff",))
    capability = capability_evidence.resolve_capability(
        record=None,
        declare_local_heavy=True,
        declare_local_fast=False,
        local_heavy_model="",
        config_reference="test:[capability]",
        freshness_seconds=300,
    )
    observation = _observe(decision, capability)

    assert observation.selected_route == "human_handoff"
    assert observation.binding_outcome == "authorized_fallback"
    validate_envelope_compliance(observation, decision)


def test_cloud_member_does_not_bind_when_cloud_is_not_enabled():
    _, decision = _decision(
        "cloud_primary",
        ("human_handoff",),
        privacy="public",
        cloud=True,
    )
    observation = _observe(decision, _capability(), cloud_enabled=False)

    assert observation.selected_route == "human_handoff"
    assert "cloud_route_not_enabled" in observation.reason_codes


# --------------------------------------------------------------------------
# CR-DD-013 subsumption: carried, never re-derived, never relabelled.
# --------------------------------------------------------------------------


def test_capability_provenance_is_carried_verbatim():
    capability = _capability()
    _, decision = _decision("local_heavy", ("human_handoff",))
    observation = _observe(decision, capability)

    assert observation.capability_state == capability.evidence.state
    assert observation.capability_source_type == capability.evidence.source_type
    assert observation.capability_freshness_seconds == capability.freshness_seconds


def test_unknown_capability_is_not_recorded_as_an_observed_failure():
    _, decision = _decision("local_heavy", ("human_handoff",))
    observation = _observe(decision, _capability(observed=False))

    assert observation.capability_state == "unknown"
    assert "local_capability_unknown" in observation.reason_codes
    assert "local_capability_unavailable" not in observation.reason_codes


def test_absent_capability_resolves_to_unknown_not_unavailable():
    _, decision = _decision("local_heavy", ("human_handoff",))
    observation = _observe(decision, None)

    assert observation.capability_state is None
    assert "local_capability_unknown" in observation.reason_codes
    assert "local_capability_unavailable" not in observation.reason_codes


def test_observation_adds_no_probe_and_no_second_resolver(monkeypatch):
    """The observation carries capability; it never resolves any itself."""

    def _forbidden(*args, **kwargs):
        raise AssertionError("runtime observation must not resolve capability")

    monkeypatch.setattr(capability_evidence, "resolve_from_config", _forbidden)
    monkeypatch.setattr(capability_evidence, "resolve_capability", _forbidden)
    monkeypatch.setattr(capability_evidence, "load_probe_record", _forbidden)

    _, decision = _decision("local_heavy", ("human_handoff",))
    observation = _observe(decision, None)
    assert observation.binding_outcome == "authorized_fallback"


# --------------------------------------------------------------------------
# The observation value is validated, bounded, and internal.
# --------------------------------------------------------------------------


def test_reason_codes_stay_inside_the_closed_vocabulary():
    _, decision = _decision("local_heavy", ("local_fast", "human_handoff"))
    for capability in (
        _capability(),
        _capability(heavy=False),
        _capability(fast=False, heavy=False),
        None,
    ):
        observation = _observe(decision, capability)
        assert set(observation.reason_codes) <= BINDING_REASON_CODES


def test_observation_rejects_an_unbounded_reason_code():
    _, decision = _decision("human_handoff")
    with pytest.raises(RuntimeObservationError):
        RuntimeObservation(
            contract_version=OBSERVATION_CONTRACT_VERSION,
            decision_id=decision.decision_id,
            binding_outcome="primary",
            selected_route="human_handoff",
            envelope_position=0,
            backend_binding="",
            model_binding="",
            fallback_occurred=False,
            capability_state=None,
            capability_source_type=None,
            capability_evidence_tier=None,
            capability_freshness_seconds=None,
            reason_codes=("route_looked_fine_to_me",),
        )


def test_observation_rejects_a_primary_outcome_at_a_fallback_position():
    _, decision = _decision("local_heavy", ("human_handoff",))
    with pytest.raises(RuntimeObservationError):
        RuntimeObservation(
            contract_version=OBSERVATION_CONTRACT_VERSION,
            decision_id=decision.decision_id,
            binding_outcome="primary",
            selected_route="human_handoff",
            envelope_position=1,
            backend_binding="",
            model_binding="",
            fallback_occurred=False,
            capability_state=None,
            capability_source_type=None,
            capability_evidence_tier=None,
            capability_freshness_seconds=None,
            reason_codes=("bound_preferred_route",),
        )


def test_observation_rejects_a_closed_outcome_that_names_a_backend():
    _, decision = _decision("human_handoff")
    with pytest.raises(RuntimeObservationError):
        RuntimeObservation(
            contract_version=OBSERVATION_CONTRACT_VERSION,
            decision_id=decision.decision_id,
            binding_outcome="closed",
            selected_route=None,
            envelope_position=None,
            backend_binding="ollama",
            model_binding=LOCAL_FAST_MODEL,
            fallback_occurred=False,
            capability_state=None,
            capability_source_type=None,
            capability_evidence_tier=None,
            capability_freshness_seconds=None,
            reason_codes=("no_authorized_binding_available",),
        )


def test_observation_is_immutable():
    _, decision = _decision("human_handoff")
    observation = _observe(decision, None)
    with pytest.raises(Exception):
        observation.selected_route = "local_heavy"  # type: ignore[misc]


def test_binding_requires_a_governed_decision():
    with pytest.raises(GovernedBindingError):
        _observe("not-a-decision", None)
