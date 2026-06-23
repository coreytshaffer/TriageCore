from dataclasses import dataclass
from typing import Optional

@dataclass(frozen=True)
class ExternalRuntimeAdmissionEvidence:
    admitted: bool
    execution_performed: bool
    requested_runtime: str
    requested_capability: str
    approval_required: bool
    approval_used: bool
    blocked_reasons: tuple[str, ...]
    manifest_or_source_evidence: str
    approval_evidence: Optional[str] = None

def _render_list(items: tuple[str, ...]) -> str:
    if not items:
        return "- None"
    return "\n".join(f"- {item}" for item in items)

def render_admission_evidence_markdown(evidence: ExternalRuntimeAdmissionEvidence) -> str:
    lines = [
        "# External Runtime Admission Readout",
        "",
        f"**Admitted:** {str(evidence.admitted).lower()}",
        f"**Execution Performed:** {str(evidence.execution_performed).lower()}",
        f"**Requested Runtime:** {evidence.requested_runtime}",
        f"**Requested Capability:** {evidence.requested_capability}",
        f"**Approval Required:** {str(evidence.approval_required).lower()}",
        f"**Approval Used:** {str(evidence.approval_used).lower()}",
        f"**Approval Evidence:** {evidence.approval_evidence if evidence.approval_evidence is not None else 'None'}",
        "",
        "## Blocked Reasons",
        "",
        _render_list(evidence.blocked_reasons),
        "",
        "## Manifest / Source Evidence",
        "",
        "```json",
        evidence.manifest_or_source_evidence,
        "```",
    ]
    return "\n".join(lines)
