"""Pure, non-executing planning for the governed ``tc run`` surface.

CR-DD-012B. This module holds the single construction seam for the governed
``tc run`` decision and the projection of that decision into the existing plan
dictionary.

Two things are load-bearing here:

* :func:`build_governed_run_context` constructs **one** immutable snapshot and
  **one** canonical governed decision per invocation. Context sources are read
  exactly once, by the caller, before this function is entered; nothing below
  reopens a source. That is what closes the preview/execution TOCTOU gap.
* :func:`build_run_plan` **projects** a completed decision. It calls no
  classifier, privacy evaluator, context planner, specialist-policy selector,
  and no router. Silent recomputation downstream of the seam is the specific
  failure mode this slice exists to make impossible.

Capability resolution never reaches decision formation (CR-DD-012B Resolved
Question 1). It is carried alongside the decision for presentation and for
execution *binding* only.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Mapping, Optional, Sequence

from triage_core.classifier import DangerDetector, TaskClassifier
from triage_core import capability_evidence
from triage_core.client import TriageClient
from triage_core.config import default_config
from triage_core.context_planner import plan_context_for_text
from triage_core.governed_decision import (
    CLASSIFICATION_POLICY_VERSION,
    CONFIGURATION_VERSION,
    POLICY_VERSION,
    ROUTE_REASON_CODES,
    ROUTE_POLICY_VERSION,
    VERIFICATION_POLICY_VERSION,
    DecisionPolicyConfiguration,
    GovernedDecision,
    build_governed_decision,
)
from triage_core.governed_run_snapshot import (
    ContextModelProfile,
    GovernedRunInputSnapshot,
    SnapshotConstructionLimits,
    SourceBytesInput,
    WorkerSystemMessageBinding,
    build_governed_run_input_snapshot,
    normalize_operator_declarations,
    resolve_context_model_profile,
    sha256_digest,
)
from triage_core.privacy_scanner import scan_task_packet
from triage_core.project_steward import ProjectSteward
from triage_core.routing.resilience_router import (
    ResilienceRouteInput,
    choose_resilience_route,
)
from triage_core.safe_task_packet import verify_packet
from triage_core.task_packet import PrivacyMetadata, TaskPacket
from triage_core.token_budget import MODEL_PROFILES, get_token_budget


class RunPlanPrivacyError(ValueError):
    def __init__(self, finding_codes: Sequence[str]):
        self.finding_codes = tuple(finding_codes) or ("privacy_preflight_failed",)
        super().__init__(", ".join(self.finding_codes))


@dataclass(frozen=True)
class ContextSource:
    path: str
    characters: int


#: The worker system message the local engine pins for every governed run. It is
#: duplicated here rather than imported because ``engine.py`` is outside this
#: slice's file allowlist; ``tests/test_governed_consumption_parity.py`` asserts
#: the two spellings have not drifted.
WORKER_SYSTEM_MESSAGE = (
    "You are a rigid parsing worker. Output ONLY raw code or markdown "
    "requested. No chat."
)
WORKER_SYSTEM_MESSAGE_VERSION = "tc_run_worker_system_message.v1"

#: The profile used when the operator declares none. ``tc run --plan`` requires
#: ``--model``; the execution path does not, and a governed decision needs a
#: resolved context/model profile either way.
DEFAULT_RUN_MODEL_PROFILE = "generic-8k"

_MIB = 1 << 20

#: Explicit finite construction bounds. The snapshot contract refuses to build
#: without them, and their digest is part of the decision identity.
RUN_SNAPSHOT_LIMITS = SnapshotConstructionLimits(
    max_source_count=256,
    max_instruction_bytes=4 * _MIB,
    max_inline_input_bytes=64 * _MIB,
    max_source_bytes_per_source=64 * _MIB,
    max_total_source_bytes=256 * _MIB,
    max_normalized_component_bytes_per_source=(64 * _MIB) + 4096,
    max_total_normalized_component_bytes=(256 * _MIB) + (256 * 4096),
    max_task_data_bytes=320 * _MIB,
    max_assembled_execution_bytes=384 * _MIB,
)

#: Which availability flag makes one logical route unselectable. Used only to
#: walk the router's own fallback ordering; the router's decision logic is not
#: modified, mirrored, or reimplemented.
_ROUTE_AVAILABILITY_FIELD = {
    "cloud_primary": "cloud_primary_available",
    "cloud_secondary": "cloud_secondary_available",
    "local_heavy": "local_heavy_available",
    "local_fast": "local_fast_available",
    "deterministic": "deterministic_tool_available",
}


def privacy_metadata_for_run(privacy: str, allow_cloud: bool) -> PrivacyMetadata:
    if privacy == "local_only":
        return PrivacyMetadata(external_model_allowed=False)
    return PrivacyMetadata(
        data_class="public",
        external_model_allowed=privacy in {"external_safe", "public"} and allow_cloud,
    )


@dataclass(frozen=True)
class GovernedRunPresentation:
    """Bounded non-policy facts resolved once at the seam.

    Everything here is either an operator-visible forecast or a configuration
    projection. None of it enters ``decision_body`` or ``decision_id``.
    """

    sources: tuple[ContextSource, ...]
    inline_data_characters: int
    finding_codes: tuple[str, ...]
    declared_privacy: str
    cloud_authorized: bool
    cloud_posture: str
    model_profile: str
    recommended_profile: str
    route_reason: str
    fallback_depth: int
    local_backend_type: str
    cloud_backend_enabled: bool
    cloud_model_binding: str
    specialist_model: str
    specialist_timeout: int
    specialist_conditions: tuple[str, ...]
    backend_binding: str
    recommended_escalation: str
    budget_status: str
    recommended_action: str
    capability: Any


@dataclass(frozen=True)
class GovernedRunContext:
    """One snapshot, one governed decision, and the facts both projections need."""

    snapshot: GovernedRunInputSnapshot
    decision: GovernedDecision
    presentation: GovernedRunPresentation
    packet: TaskPacket


def context_model_profiles() -> Mapping[str, ContextModelProfile]:
    """The declared context/model profiles, as immutable snapshot profiles."""

    return {
        name: ContextModelProfile(
            profile_id=name,
            context_window_tokens=budget.context_window,
            reserved_output_tokens=budget.reserved_output_tokens,
            safety_margin_tokens=budget.safety_margin_tokens,
        )
        for name, budget in MODEL_PROFILES.items()
    }


def configuration_digest(
    *,
    cloud_backend_enabled: bool,
    cloud_model_binding: str,
    local_backend_type: str,
) -> str:
    """Digest the decision-relevant configuration. Never volatile observations."""

    lines = (
        CONFIGURATION_VERSION,
        f"cloud_backend_enabled={cloud_backend_enabled}",
        f"cloud_model_binding={cloud_model_binding}",
        f"local_backend_type={local_backend_type}",
        f"policy_version={POLICY_VERSION}",
        f"classification_policy_version={CLASSIFICATION_POLICY_VERSION}",
        f"route_policy_version={ROUTE_POLICY_VERSION}",
        f"verification_policy_version={VERIFICATION_POLICY_VERSION}",
    )
    return sha256_digest("\n".join(lines).encode("utf-8"))


def _bounded_route_reason(reason: str) -> str:
    """Map a router reason onto the decision's closed reason vocabulary.

    ``choose_resilience_route`` emits one reason the governed contract does not
    enumerate -- ``sensitivity_requires_human_review`` -- and
    ``governed_decision.py`` is outside this slice's file allowlist, so the
    vocabulary is not widened to admit it. The unenumerated case records the
    generic ``policy_selected`` in the decision body; the router's own spelling
    is still what the operator-facing plan renders, so no fidelity is lost where
    a reader looks for it.
    """

    return reason if reason in ROUTE_REASON_CODES else "policy_selected"


def _classification_reason_code(prompt: str, category: str) -> str:
    """Distinguish a keyword match from the classifier's default fallback.

    ``TaskClassifier.classify_deterministic`` returns ``refactor`` both for an
    explicit refactor request and as its terminal default, and it exposes no
    provenance. This reproduces only that last branch's condition -- not the
    classifier's policy -- so the decision does not claim a match it did not get.
    """

    lowered = prompt.lower()
    if category == "refactor" and not any(
        word in lowered for word in ("refactor", "rewrite")
    ):
        return "deterministic_classifier_default"
    return "deterministic_classifier_match"


def _route_envelope(
    route_input: ResilienceRouteInput,
) -> tuple[str, str, int, bool, tuple[str, ...]]:
    """Ask the router for its own ordered fallback sequence.

    Returns ``(preferred_route, reason, fallback_depth, human_review_required,
    envelope)``. The envelope is produced by re-asking the *existing* router
    with the previously selected route made unavailable, so the ordering is the
    router's, never a copy of it. This runs once, at the seam; no consumer
    downstream re-enters it.
    """

    working = replace(route_input)
    ordered: list[str] = []
    preferred = ""
    reason = ""
    depth = 0
    review = False

    for step in range(len(_ROUTE_AVAILABILITY_FIELD) + 1):
        decision = choose_resilience_route(working)
        route = decision.selected_route
        if step == 0:
            preferred = route
            reason = decision.reason
            depth = decision.fallback_depth
            review = decision.human_review_required
        elif route == preferred or route in ordered:
            # The envelope is a closed *set*: a repeat means the router stopped
            # narrowing, so the sequence ends here rather than growing a
            # duplicate member.
            break
        else:
            ordered.append(route)
        if route == "human_handoff":
            break
        working = replace(working, **{_ROUTE_AVAILABILITY_FIELD[route]: False})

    return preferred, reason, depth, review, tuple(ordered)


def _specialist_timeout_forecast(category: str) -> int:
    if category in {"bugfix", "test_addition", "refactor"}:
        return 30
    if category in {"docs_update", "architecture_planning"}:
        return 120
    return 45


def normalized_source_text(source) -> str:
    """The exact normalized content bytes this source contributed, as text."""

    component = source.normalized_component_bytes
    header_length = source.component_byte_length - source.normalized_byte_length
    return component[header_length:].decode("utf-8")


def build_governed_run_context(
    *,
    prompt: str,
    sources: Sequence[SourceBytesInput],
    inline_data: Optional[str],
    privacy: str,
    allow_cloud: bool,
    model_profile: Optional[str],
    task_id: Optional[str],
    capability: Any = None,
) -> GovernedRunContext:
    """The single construction seam: one snapshot, one governed decision.

    Called once per ``tc run`` invocation, after argument assembly and privacy
    mapping and before the preview/execution branch. Both consumers descend from
    the value returned here; neither constructs a snapshot or decision of its own.

    ``sources`` carries bytes the caller already read. Nothing here opens a file.
    """

    requested = model_profile or DEFAULT_RUN_MODEL_PROFILE
    if requested not in MODEL_PROFILES:
        raise KeyError(requested)
    budget = get_token_budget(requested)
    resolved_profile = resolve_context_model_profile(
        requested,
        default_profile=DEFAULT_RUN_MODEL_PROFILE,
        profiles=context_model_profiles(),
    )
    declarations = normalize_operator_declarations(
        task_id=task_id,
        declared_privacy=privacy,
        cloud_intent=bool(allow_cloud),
        resolved_profile=resolved_profile,
    )
    snapshot = build_governed_run_input_snapshot(
        prompt=prompt,
        sources=tuple(sources),
        inline_input=inline_data,
        declarations=declarations,
        resolved_profile=resolved_profile,
        worker_system_message=WorkerSystemMessageBinding(
            version=WORKER_SYSTEM_MESSAGE_VERSION,
            sha256=sha256_digest(WORKER_SYSTEM_MESSAGE.encode("utf-8")),
        ),
        limits=RUN_SNAPSHOT_LIMITS,
    )

    instruction_text = snapshot.instruction_bytes.decode("utf-8")
    task_data_text = snapshot.task_data_bytes.decode("utf-8")
    assembled_text = snapshot.assembled_execution_bytes.decode("utf-8")

    metadata = privacy_metadata_for_run(privacy, allow_cloud)
    packet = TaskPacket(
        prompt=instruction_text,
        data=task_data_text,
        task_id=task_id,
        privacy_metadata=metadata,
    )
    report = scan_task_packet(packet)
    if not report.passed:
        raise RunPlanPrivacyError(report.finding_codes or ())
    verify_packet(packet)

    source_paths = [source.path_spelling for source in snapshot.sources]
    category = TaskClassifier.classify_deterministic(instruction_text)
    danger = DangerDetector.analyze(instruction_text, source_paths)
    steward_evaluation = ProjectSteward(budgets={}).evaluate(instruction_text, [], [])
    firewall_triggered = bool(steward_evaluation.get("firewall_triggered"))
    steward_insufficient = (
        steward_evaluation.get("local_result_status") == "insufficient"
    )
    firewall = firewall_triggered or steward_insufficient

    cloud_backend_enabled = default_config.get_qwen_enabled()
    cloud_model_binding = (
        default_config.get_qwen_model() if cloud_backend_enabled else "not_enabled"
    )
    local_backend_type = default_config.get_backend_type()

    # Route policy is a function of governed inputs alone. No capability
    # resolution reaches this input, so a model server that briefly disappears
    # cannot change the decision ID (CR-DD-012B Resolved Question 1).
    route_input = TriageClient._build_resilience_route_input(
        category=category, validator=None, capability=None
    )
    route_input.privacy_level = (
        "local_only" if privacy == "local_only" else "external_safe"
    )
    route_input.internet_ok = cloud_backend_enabled and allow_cloud
    route_input.cloud_primary_available = cloud_backend_enabled and allow_cloud
    route_input.cloud_secondary_available = False
    route_input.cloud_credit_state = (
        "ok" if cloud_backend_enabled and allow_cloud else "none"
    )
    if danger.risk_level == "high":
        route_input.sensitivity = "high"
        route_input.human_review_required = True

    preferred, route_reason, fallback_depth, router_review, envelope = _route_envelope(
        route_input
    )
    if firewall:
        preferred = "human_handoff"
        route_reason = "ethical_firewall_requires_human_review"
        fallback_depth = 0
        router_review = True
        envelope = ()

    context = plan_context_for_text("assembled tc run input", assembled_text, budget)

    raw_escalation = str(steward_evaluation.get("recommended_escalation") or "none")
    recommended_escalation = (
        raw_escalation
        if raw_escalation in {"none", "human_only", "codex", "antigravity"}
        else "configured_human_review"
    )
    terminal_escalation = (
        raw_escalation
        if raw_escalation in {"none", "human_only"}
        else "configured_human_review"
    )

    human_review = (
        "required"
        if (
            router_review
            or firewall
            or danger.risk_level == "high"
            or preferred == "human_handoff"
            or terminal_escalation != "none"
        )
        else "not_required"
    )

    escalation_conditions: list[str] = []
    if envelope:
        escalation_conditions.append("route_unavailable_at_execution")
    if danger.risk_level == "high":
        escalation_conditions.append("sensitivity_requires_governed_handoff")
    if privacy != "local_only" and not allow_cloud:
        escalation_conditions.append("egress_requires_explicit_authorization")
    if firewall:
        escalation_conditions.append("ethical_firewall_requires_human_review")
    if context.status != "fits":
        escalation_conditions.append("context_budget_overrun_requires_review")

    required_checks = [
        "packet_verification",
        "privacy_preflight",
        "route_policy_conformance",
        "decision_identity_verification",
    ]
    if human_review == "required":
        required_checks.append("human_review")

    configuration = DecisionPolicyConfiguration(
        configuration_version=CONFIGURATION_VERSION,
        configuration_sha256=configuration_digest(
            cloud_backend_enabled=cloud_backend_enabled,
            cloud_model_binding=cloud_model_binding,
            local_backend_type=local_backend_type,
        ),
        policy_version=POLICY_VERSION,
        classification_policy_version=CLASSIFICATION_POLICY_VERSION,
        route_policy_version=ROUTE_POLICY_VERSION,
        verification_policy_version=VERIFICATION_POLICY_VERSION,
        estimated_input_tokens=context.estimated_input_tokens,
        usable_input_tokens=context.usable_input_budget,
        privacy_preflight="passed",
        classification=category,
        risk_posture=danger.risk_level,
        classification_reason_codes=(
            _classification_reason_code(instruction_text, category),
        ),
        preferred_logical_route=preferred,
        permitted_fallback_envelope=envelope,
        route_reason_codes=(_bounded_route_reason(route_reason),),
        terminal_escalation=terminal_escalation,
        ethical_firewall="triggered" if firewall else "clear",
        human_review=human_review,
        escalation_conditions=tuple(escalation_conditions),
        required_checks=tuple(required_checks),
    )
    decision = build_governed_decision(snapshot, configuration)

    # Presentation only. The capability resolution below is carried for the
    # operator-facing forecast and for execution binding; it did not and cannot
    # reach the decision above.
    if capability is None:
        capability = capability_evidence.resolve_from_config(default_config)
    if preferred.startswith("local_"):
        specialist_model = capability.model_for_route(preferred) or "none"
    elif preferred.startswith("cloud_"):
        specialist_model = cloud_model_binding
    else:
        specialist_model = "none"
    if preferred.startswith("cloud_"):
        backend_binding = "qwen:" + cloud_model_binding
    elif preferred.startswith("local_"):
        backend_binding = local_backend_type + ":" + specialist_model
    else:
        backend_binding = "none"

    specialist_conditions: list[str] = []
    if danger.risk_level == "high":
        specialist_conditions.append("high_risk_requires_governed_handoff")
    elif danger.risk_level == "medium":
        specialist_conditions.append(
            "medium_risk_route_depends_on_unobserved_internet_state"
        )
    if len(task_data_text) > 30000:
        specialist_conditions.append(
            "large_context_route_depends_on_unobserved_internet_state"
        )
    if firewall:
        specialist_conditions.append("ethical_firewall_requires_human_review")

    if privacy == "local_only":
        cloud_posture = "prohibited"
    elif allow_cloud:
        cloud_posture = "authorized_for_consideration"
    else:
        cloud_posture = "eligible_but_not_authorized"

    presentation = GovernedRunPresentation(
        sources=tuple(
            ContextSource(
                path=source.path_spelling,
                characters=len(normalized_source_text(source)),
            )
            for source in snapshot.sources
        ),
        inline_data_characters=len(snapshot.inline_input_bytes.decode("utf-8")),
        finding_codes=tuple(report.finding_codes or ()),
        declared_privacy=privacy,
        cloud_authorized=bool(allow_cloud),
        cloud_posture=cloud_posture,
        model_profile=requested,
        recommended_profile=danger.recommended_profile,
        route_reason=route_reason,
        fallback_depth=fallback_depth,
        local_backend_type=local_backend_type,
        cloud_backend_enabled=cloud_backend_enabled,
        cloud_model_binding=cloud_model_binding,
        specialist_model=specialist_model,
        specialist_timeout=_specialist_timeout_forecast(category),
        specialist_conditions=tuple(specialist_conditions),
        backend_binding=backend_binding,
        recommended_escalation=recommended_escalation,
        budget_status=context.status.replace(" ", "_"),
        recommended_action=context.recommended_action.replace("\n", "; "),
        capability=capability,
    )
    return GovernedRunContext(
        snapshot=snapshot,
        decision=decision,
        presentation=presentation,
        packet=packet,
    )


def build_run_plan(context: GovernedRunContext) -> dict:
    """Project a completed governed decision into the existing plan dictionary.

    This is a projection, not a computation. It calls no classifier, no privacy
    evaluator, no context planner, no specialist-policy selector, and no router,
    and it never constructs a second snapshot or decision.
    """

    if type(context) is not GovernedRunContext:
        raise TypeError("build_run_plan projects a GovernedRunContext")
    policy = context.decision.policy
    binding = context.decision.snapshot_binding
    view = context.presentation

    return {
        "task_id": binding.task_id or "not_assigned_until_execution",
        "prompt_characters": len(context.snapshot.instruction_bytes.decode("utf-8")),
        "sources": view.sources,
        "inline_data_characters": view.inline_data_characters,
        "model_profile": view.model_profile,
        "estimated_tokens": policy.estimated_input_tokens,
        "usable_budget": policy.usable_input_tokens,
        "budget_status": view.budget_status,
        "recommended_action": view.recommended_action,
        "privacy": view.declared_privacy,
        "privacy_result": policy.privacy_preflight,
        "finding_codes": view.finding_codes,
        "egress_eligible": view.declared_privacy in {"external_safe", "public"},
        "cloud_authorized": view.cloud_authorized,
        "cloud_posture": view.cloud_posture,
        "classification": policy.classification,
        "risk_level": policy.risk_posture,
        "recommended_profile": view.recommended_profile,
        "specialist_model": view.specialist_model,
        "specialist_timeout": view.specialist_timeout,
        "specialist_conditions": view.specialist_conditions,
        "route": policy.preferred_logical_route,
        "reason": view.route_reason,
        "fallback_depth": view.fallback_depth,
        "human_review_required": policy.human_review == "required",
        "backend_binding": view.backend_binding,
        "cloud_backend_enabled": view.cloud_backend_enabled,
        "cloud_model_binding": view.cloud_model_binding,
        "local_backend_type": view.local_backend_type,
        "required_checks": tuple(policy.required_checks),
        "permitted_fallback_envelope": tuple(policy.permitted_fallback_envelope),
        "ethical_firewall_status": (
            "triggered" if policy.ethical_firewall == "triggered" else "clear"
        ),
        "ethical_firewall_policy_source": "configured_or_hardcoded",
        "ethical_firewall_recommended_escalation": view.recommended_escalation,
    }


def _ascii(value: object) -> str:
    return str(value).encode("ascii", errors="backslashreplace").decode("ascii")


def render_run_plan(plan: dict, *, artifact_written: bool = False) -> str:
    source_lines = [
        f"- source[{index}]: {_ascii(source.path)} ({source.characters} chars)"
        for index, source in enumerate(plan["sources"], 1)
    ] or ["- sources: none"]
    checks = ", ".join(_ascii(item) for item in plan["required_checks"]) or "none"
    findings = ", ".join(_ascii(item) for item in plan["finding_codes"]) or "none"
    conditions = (
        ", ".join(_ascii(item) for item in plan["specialist_conditions"])
        or "none"
    )
    envelope = (
        ", ".join(_ascii(item) for item in plan["permitted_fallback_envelope"])
        or "none"
    )
    lines = [
        "Task",
        f"- task_id: {_ascii(plan['task_id'])}",
        f"- prompt_present: {plan['prompt_characters'] > 0}",
        f"- prompt_characters: {plan['prompt_characters']}",
        f"- inline_data_present: {plan['inline_data_characters'] > 0}",
        f"- inline_data_characters: {plan['inline_data_characters']}",
        *source_lines,
        "",
        "Context",
        f"- model_profile: {_ascii(plan['model_profile'])}",
        f"- estimated_input_tokens: {plan['estimated_tokens']}",
        f"- usable_input_budget: {plan['usable_budget']}",
        f"- status: {plan['budget_status']}",
        f"- recommended_action: {_ascii(plan['recommended_action'])}",
        "",
        "Privacy and Egress",
        f"- declared_privacy: {_ascii(plan['privacy'])}",
        f"- privacy_preflight: {plan['privacy_result']}",
        f"- finding_codes: {findings}",
        f"- egress_eligible: {plan['egress_eligible']}",
        f"- cloud_authorized: {plan['cloud_authorized']}",
        f"- cloud_posture: {_ascii(plan['cloud_posture'])}",
        "",
        "Logical Route",
        f"- deterministic_classification: {_ascii(plan['classification'])}",
        f"- deterministic_risk_level: {_ascii(plan['risk_level'])}",
        f"- recommended_profile: {_ascii(plan['recommended_profile'])}",
        f"- proposed_route: {_ascii(plan['route'])}",
        f"- route_reason: {_ascii(plan['reason'])}",
        f"- permitted_fallback_envelope: {envelope}",
        f"- fallback_depth: {plan['fallback_depth']}",
        f"- human_review_required: {plan['human_review_required']}",
        f"- configured_backend_binding: {_ascii(plan['backend_binding'])}",
        f"- specialist_model_forecast: {_ascii(plan['specialist_model'])}",
        f"- specialist_timeout_forecast_seconds: {plan['specialist_timeout']}",
        f"- specialist_conditional_behavior: {conditions}",
        f"- ethical_firewall_status: {_ascii(plan['ethical_firewall_status'])}",
        "- ethical_firewall_policy_source: configured_or_hardcoded",
        (
            "- ethical_firewall_recommended_escalation: "
            f"{_ascii(plan['ethical_firewall_recommended_escalation'])}"
        ),
        "- route_input_provenance: declared_or_static",
        "- live_health_observed: false",
        "",
        "Escalation Conditions",
        "- another_local_route: current logical route unavailable at execution time",
        "- governed_handoff: sensitivity or no reliable automated route",
        "- qwen_cloud: external egress eligible, explicitly authorized, configured, and selected by policy",
        "",
        "Expected Verification",
        "- packet_verification: required",
        "- privacy_preflight: required",
        f"- route_required_checks: {checks}",
        "- output_validation: not_configured",
        f"- human_review_required: {plan['human_review_required']}",
        "",
        "Preview Boundaries",
        "- advisory_only: true",
        "- deterministic_classification_is_preview_assumption: true",
        "- backend_probe_performed: false",
        "- unobserved: availability, memory_headroom, recent_failures, cloud_credit_health",
        "- execution_performed: false",
        *(
            [
                "- ledger_written: false",
                "- plan_artifact_written: true",
            ]
            if artifact_written
            else ["- ledger_or_artifact_written: false"]
        ),
        "- approval_granted: false",
    ]
    return "\n".join(lines) + "\n"
