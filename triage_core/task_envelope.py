from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class TaskEnvelope:
    task_id: str
    title: str
    objective: str
    repo: str
    operator_agent_lane: str
    route: str
    risk_level: str
    requested_capability: str
    allowed_files: tuple[str, ...]
    forbidden_files_or_areas: tuple[str, ...]
    explicit_non_scope: tuple[str, ...]
    approval_gates: str
    validation_plan: str
    evidence_to_produce: tuple[str, ...]
    current_status: str
    operator_decision: str
    next_allowed_action: str
    failure_modes_or_blocked_reasons: Optional[str] = None
    approval_evidence: Optional[str] = None
    admission_evidence: Optional[str] = None

def _render_list(items: tuple[str, ...]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)

def render_task_envelope_markdown(envelope: TaskEnvelope) -> str:
    lines = [
        f"# {envelope.task_id} Task Envelope",
        "",
        f"**Title:** {envelope.title}",
        f"**Objective:** {envelope.objective}",
        f"**Repo:** {envelope.repo}",
        f"**Operator / Agent Lane:** {envelope.operator_agent_lane}",
        f"**Route:** {envelope.route}",
        "",
        "## Scope & Risk",
        f"**Risk Level:** {envelope.risk_level}",
        f"**Requested Capability:** {envelope.requested_capability}",
        "**Allowed Files:**",
        _render_list(envelope.allowed_files),
        "**Forbidden Files or Areas:**",
        _render_list(envelope.forbidden_files_or_areas),
        "**Explicit Non-Scope:**",
        _render_list(envelope.explicit_non_scope),
        "",
        "## Governance",
        f"**Approval Gates:** {envelope.approval_gates}",
        f"**Validation Plan:** {envelope.validation_plan}",
        "**Evidence to Produce:**",
        _render_list(envelope.evidence_to_produce),
        "",
        "## Admission State",
        f"**Current Status:** {envelope.current_status}",
        f"**Operator Decision:** {envelope.operator_decision}",
        f"**Failure Modes / Blocked Reasons:** {envelope.failure_modes_or_blocked_reasons if envelope.failure_modes_or_blocked_reasons else 'None'}",
    ]
    
    if envelope.approval_evidence is not None:
        lines.append(f"**Approval Evidence:** {envelope.approval_evidence}")
    if envelope.admission_evidence is not None:
        lines.append(f"**Admission Evidence:** {envelope.admission_evidence}")
        
    lines.append(f"**Next Allowed Action:** {envelope.next_allowed_action}")

    return "\n".join(lines) + "\n"
