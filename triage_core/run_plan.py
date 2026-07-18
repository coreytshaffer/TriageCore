"""Pure, non-executing planning for the governed ``tc run`` surface."""

from dataclasses import dataclass
from typing import Sequence

from triage_core.classifier import DangerDetector, TaskClassifier
from triage_core.client import TriageClient
from triage_core.config import default_config
from triage_core.context_planner import plan_context_for_text
from triage_core.privacy_scanner import scan_task_packet
from triage_core.project_steward import ProjectSteward
from triage_core.routing.resilience_router import choose_resilience_route
from triage_core.safe_task_packet import verify_packet
from triage_core.task_packet import PrivacyMetadata, TaskPacket
from triage_core.token_budget import get_token_budget


class RunPlanPrivacyError(ValueError):
    def __init__(self, finding_codes: Sequence[str]):
        self.finding_codes = tuple(finding_codes) or ("privacy_preflight_failed",)
        super().__init__(", ".join(self.finding_codes))


@dataclass(frozen=True)
class ContextSource:
    path: str
    characters: int


def privacy_metadata_for_run(privacy: str, allow_cloud: bool) -> PrivacyMetadata:
    if privacy == "local_only":
        return PrivacyMetadata(external_model_allowed=False)
    return PrivacyMetadata(
        data_class="public",
        external_model_allowed=privacy in {"external_safe", "public"} and allow_cloud,
    )


def build_run_plan(
    *,
    prompt: str,
    data: str,
    sources: Sequence[ContextSource],
    inline_data_characters: int,
    privacy: str,
    allow_cloud: bool,
    model_profile: str,
    task_id: str | None,
) -> dict:
    budget = get_token_budget(model_profile)
    metadata = privacy_metadata_for_run(privacy, allow_cloud)
    packet = TaskPacket(prompt=prompt, data=data, task_id=task_id, privacy_metadata=metadata)
    report = scan_task_packet(packet)
    if not report.passed:
        raise RunPlanPrivacyError(report.finding_codes or ())
    verify_packet(packet)

    category = TaskClassifier.classify_deterministic(prompt)
    danger = DangerDetector.analyze(prompt, [source.path for source in sources])
    steward_evaluation = ProjectSteward(budgets={}).evaluate(prompt, [], [])
    firewall_triggered = bool(steward_evaluation.get("firewall_triggered"))
    steward_insufficient = (
        steward_evaluation.get("local_result_status") == "insufficient"
    )
    qwen_enabled = default_config.get_qwen_enabled()
    qwen_model = default_config.get_qwen_model() if qwen_enabled else "not_enabled"
    local_backend_type = default_config.get_backend_type()
    route_input = TriageClient._build_resilience_route_input(
        category=category, validator=None
    )
    route_input.privacy_level = (
        "local_only" if privacy == "local_only" else "external_safe"
    )
    route_input.internet_ok = qwen_enabled and allow_cloud
    route_input.cloud_primary_available = qwen_enabled and allow_cloud
    route_input.cloud_secondary_available = False
    route_input.cloud_credit_state = (
        "ok" if qwen_enabled and allow_cloud else "none"
    )
    if danger.risk_level == "high":
        route_input.sensitivity = "high"
        route_input.human_review_required = True
    decision = choose_resilience_route(route_input)
    context = plan_context_for_text(
        "assembled tc run input", f"{prompt}\n{data}", budget
    )
    specialist_model, specialist_timeout = _specialist_forecast(category)
    selected_route = decision.selected_route
    route_reason = decision.reason
    fallback_depth = decision.fallback_depth
    human_review_required = decision.human_review_required
    if firewall_triggered or steward_insufficient:
        selected_route = "human_handoff"
        route_reason = "ethical_firewall_requires_human_review"
        fallback_depth = 0
        human_review_required = True

    selected_backend = (
        "qwen:" + qwen_model
        if selected_route.startswith("cloud_")
        else local_backend_type + ":" + specialist_model
        if selected_route.startswith("local_")
        else "none"
    )
    specialist_conditions = []
    if danger.risk_level == "high":
        specialist_conditions.append("high_risk_requires_governed_handoff")
    elif danger.risk_level == "medium":
        specialist_conditions.append(
            "medium_risk_route_depends_on_unobserved_internet_state"
        )
    if len(data) > 30000:
        specialist_conditions.append(
            "large_context_route_depends_on_unobserved_internet_state"
        )
    if firewall_triggered or steward_insufficient:
        specialist_conditions.append("ethical_firewall_requires_human_review")
    escalation = str(steward_evaluation.get("recommended_escalation") or "none")
    if escalation not in {"none", "human_only", "codex", "antigravity"}:
        escalation = "configured_human_review"
    if privacy == "local_only":
        cloud_posture = "prohibited"
    elif allow_cloud:
        cloud_posture = "authorized_for_consideration"
    else:
        cloud_posture = "eligible_but_not_authorized"

    return {
        "task_id": task_id or "not_assigned_until_execution",
        "prompt_characters": len(prompt),
        "sources": tuple(sources),
        "inline_data_characters": inline_data_characters,
        "model_profile": model_profile,
        "estimated_tokens": context.estimated_input_tokens,
        "usable_budget": context.usable_input_budget,
        "budget_status": context.status.replace(" ", "_"),
        "recommended_action": context.recommended_action.replace("\n", "; "),
        "privacy": privacy,
        "privacy_result": "passed",
        "finding_codes": tuple(report.finding_codes or ()),
        "egress_eligible": privacy in {"external_safe", "public"},
        "cloud_authorized": allow_cloud,
        "cloud_posture": cloud_posture,
        "classification": category,
        "risk_level": danger.risk_level,
        "recommended_profile": danger.recommended_profile,
        "specialist_model": specialist_model,
        "specialist_timeout": specialist_timeout,
        "specialist_conditions": tuple(specialist_conditions),
        "route": selected_route,
        "reason": route_reason,
        "fallback_depth": fallback_depth,
        "human_review_required": human_review_required,
        "backend_binding": selected_backend,
        "cloud_backend_enabled": qwen_enabled,
        "cloud_model_binding": qwen_model,
        "local_backend_type": local_backend_type,
        "required_checks": tuple(decision.required_checks),
        "ethical_firewall_status": (
            "triggered" if firewall_triggered or steward_insufficient else "clear"
        ),
        "ethical_firewall_policy_source": "configured_or_hardcoded",
        "ethical_firewall_recommended_escalation": escalation,
    }


def _specialist_forecast(category: str) -> tuple[str, int]:
    if category in {"bugfix", "test_addition", "refactor"}:
        return "qwen2.5-coder-7b-instruct", 30
    if category in {"docs_update", "architecture_planning"}:
        return "deepseek/deepseek-r1-0528-qwen3-8b", 120
    return "qwen2.5-coder-7b-instruct", 45


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
