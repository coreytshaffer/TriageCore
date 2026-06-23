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

def admission_evidence_from_mapping(payload: dict) -> ExternalRuntimeAdmissionEvidence:
    """
    Constructs and validates an ExternalRuntimeAdmissionEvidence from a raw dictionary mapping.
    Raises ValueError if validation rules are violated.
    """
    required_booleans = [
        "admitted", "execution_performed", "approval_required", "approval_used"
    ]
    for field in required_booleans:
        if field not in payload or not isinstance(payload[field], bool):
            raise ValueError(f"Missing or invalid boolean field: '{field}'")

    required_strings = [
        "requested_runtime", "requested_capability", "manifest_or_source_evidence"
    ]
    for field in required_strings:
        if field not in payload or not isinstance(payload[field], str) or not payload[field].strip():
            raise ValueError(f"Missing or empty string field: '{field}'")

    if "blocked_reasons" not in payload or not isinstance(payload["blocked_reasons"], list):
        raise ValueError("Missing or invalid list field: 'blocked_reasons'")
    
    for item in payload["blocked_reasons"]:
        if not isinstance(item, str) or not item.strip():
            raise ValueError("Invalid item in list field 'blocked_reasons': must be non-empty string")

    approval_evidence = payload.get("approval_evidence")
    if approval_evidence is not None and (not isinstance(approval_evidence, str) or not approval_evidence.strip()):
        raise ValueError("Invalid 'approval_evidence': must be null or non-empty string")

    return ExternalRuntimeAdmissionEvidence(
        admitted=payload["admitted"],
        execution_performed=payload["execution_performed"],
        requested_runtime=payload["requested_runtime"],
        requested_capability=payload["requested_capability"],
        approval_required=payload["approval_required"],
        approval_used=payload["approval_used"],
        blocked_reasons=tuple(payload["blocked_reasons"]),
        manifest_or_source_evidence=payload["manifest_or_source_evidence"],
        approval_evidence=approval_evidence
    )
