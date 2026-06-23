from dataclasses import dataclass
from typing import Any, Literal


class RuntimeAdmissionError(RuntimeError):
    """Raised when an external runtime proposal is not admitted for execution."""


ProposalStatus = Literal["proposed", "approval_required", "blocked"]

ALLOWED_CAPABILITY_PROFILES = {
    "read_only_summary",
    "draft_only",
    "approved_mutation",
    "scheduled_check",
}
MUTATION_CAPABLE_PROFILES = {"approved_mutation", "scheduled_check"}
ALIAS_ONLY_IDENTITIES = {"", "default", "fast", "latest", "unknown"}
REQUIRED_STRING_FIELDS = (
    "schema_version",
    "runtime_name",
    "runtime_version",
    "runtime_kind",
    "adapter_version",
    "capability_profile",
    "tool_policy_hash",
    "sandbox_mode",
    "network_access",
    "credential_access",
    "model_provider",
    "model_identity",
)
REQUIRED_BOOL_FIELDS = (
    "approval_required",
    "provenance_required",
    "revocation_supported",
)
UNKNOWN_BOUNDARY_FIELDS = (
    "runtime_kind",
    "sandbox_mode",
    "network_access",
    "credential_access",
    "model_provider",
)


@dataclass(frozen=True)
class ExternalRuntimeAdapterProposal:
    status: ProposalStatus
    runtime_name: str
    runtime_kind: str
    capability_profile: str
    authority_granted: bool
    execution_allowed: bool
    approval_required: bool
    manifest_valid: bool
    blocked_reasons: tuple[str, ...]
    proposed_record: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "runtime_name": self.runtime_name,
            "runtime_kind": self.runtime_kind,
            "capability_profile": self.capability_profile,
            "authority_granted": self.authority_granted,
            "execution_allowed": self.execution_allowed,
            "approval_required": self.approval_required,
            "manifest_valid": self.manifest_valid,
            "blocked_reasons": list(self.blocked_reasons),
            "proposed_record": dict(self.proposed_record),
        }


@dataclass(frozen=True)
class ExternalRuntimeAdmissionEvidence:
    evidence_kind: str
    status: str
    execution_performed: bool
    admitted: bool
    runtime_name: str
    proposal_status: ProposalStatus
    approval_used: bool
    blocked_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "evidence_kind": self.evidence_kind,
            "status": self.status,
            "execution_performed": self.execution_performed,
            "admitted": self.admitted,
            "runtime_name": self.runtime_name,
            "proposal_status": self.proposal_status,
            "approval_used": self.approval_used,
            "blocked_reasons": list(self.blocked_reasons),
        }


def normalize_external_runtime_manifest(
    manifest: dict[str, Any] | Any,
) -> ExternalRuntimeAdapterProposal:
    if not isinstance(manifest, dict):
        return _build_proposal(
            runtime_name="",
            schema_version="",
            runtime_kind="",
            capability_profile="",
            approval_required=True,
            blocked_reasons=("invalid_manifest_root",),
        )

    schema_version = _normalize(manifest.get("schema_version"))
    runtime_name = _normalize(manifest.get("runtime_name"))
    runtime_kind = _normalize(manifest.get("runtime_kind"))
    capability_profile = _normalize(manifest.get("capability_profile"))
    tool_policy_hash = _normalize(manifest.get("tool_policy_hash"))
    model_provider = _normalize(manifest.get("model_provider"))
    model_identity = _normalize(manifest.get("model_identity"))

    approval_required = _bool_value(manifest.get("approval_required"), default=True)
    provenance_required = _bool_value(manifest.get("provenance_required"), default=True)
    revocation_supported = _bool_value(manifest.get("revocation_supported"), default=False)

    blocked_reasons: list[str] = []

    for field in REQUIRED_STRING_FIELDS:
        if _normalize(manifest.get(field)) == "":
            blocked_reasons.append(f"missing_or_blank:{field}")

    for field in REQUIRED_BOOL_FIELDS:
        if not isinstance(manifest.get(field), bool):
            blocked_reasons.append(f"invalid_bool:{field}")

    runtime_version = _normalize(manifest.get("runtime_version"))
    if runtime_version in {"default", "latest"}:
        blocked_reasons.append("runtime_version_alias_only")

    if capability_profile not in ALLOWED_CAPABILITY_PROFILES:
        blocked_reasons.append("unsupported_capability_profile")

    for field in UNKNOWN_BOUNDARY_FIELDS:
        if _normalize(manifest.get(field)) == "unknown":
            blocked_reasons.append(f"unknown_boundary:{field}")

    if model_provider != "none" and model_identity in ALIAS_ONLY_IDENTITIES:
        blocked_reasons.append("model_identity_alias_only")

    if not approval_required:
        blocked_reasons.append("approval_required_false")

    if not provenance_required:
        blocked_reasons.append("provenance_required_false")

    if not revocation_supported:
        blocked_reasons.append("revocation_not_supported")

    approval_required = approval_required or capability_profile in MUTATION_CAPABLE_PROFILES

    return _build_proposal(
        runtime_name=runtime_name,
        schema_version=schema_version,
        runtime_kind=runtime_kind,
        capability_profile=capability_profile,
        approval_required=approval_required,
        blocked_reasons=tuple(dict.fromkeys(blocked_reasons)),
        tool_policy_hash=tool_policy_hash,
        model_provider=model_provider,
        model_identity=model_identity,
    )


def admit_external_runtime(
    proposal: ExternalRuntimeAdapterProposal,
    *,
    explicit_approval: bool = False,
) -> ExternalRuntimeAdapterProposal:
    if proposal.status == "blocked":
        reasons = "; ".join(proposal.blocked_reasons)
        raise RuntimeAdmissionError(f"External runtime proposal blocked: {reasons}")

    if proposal.status == "approval_required" and not explicit_approval:
        raise RuntimeAdmissionError(
            "External runtime proposal requires explicit approval before admission."
        )

    return proposal


def _build_proposal(
    *,
    runtime_name: str,
    schema_version: str,
    runtime_kind: str,
    capability_profile: str,
    approval_required: bool,
    blocked_reasons: tuple[str, ...],
    tool_policy_hash: str = "",
    model_provider: str = "",
    model_identity: str = "",
) -> ExternalRuntimeAdapterProposal:
    manifest_valid = not blocked_reasons
    status: ProposalStatus
    if blocked_reasons:
        status = "blocked"
    elif capability_profile in MUTATION_CAPABLE_PROFILES:
        status = "approval_required"
    else:
        status = "proposed"

    proposed_record = {
        "record_type": "external_runtime_capability_proposal",
        "schema_version": schema_version,
        "runtime_name": runtime_name,
        "runtime_kind": runtime_kind,
        "capability_profile": capability_profile,
        "tool_policy_hash": tool_policy_hash,
        "model_provider": model_provider,
        "model_identity": model_identity,
        "authority_granted": False,
        "execution_allowed": False,
        "approval_required": approval_required,
    }

    return ExternalRuntimeAdapterProposal(
        status=status,
        runtime_name=runtime_name,
        runtime_kind=runtime_kind,
        capability_profile=capability_profile,
        authority_granted=False,
        execution_allowed=False,
        approval_required=approval_required,
        manifest_valid=manifest_valid,
        blocked_reasons=blocked_reasons,
        proposed_record=proposed_record,
    )


def _bool_value(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    return default


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def execute_external_runtime_stub(
    proposal: ExternalRuntimeAdapterProposal,
    *,
    explicit_approval: bool = False,
) -> ExternalRuntimeAdmissionEvidence:
    """
    A minimal caller stub representing the first execution-path boundary.
    All external runtime execution must first pass admission.
    """
    admitted = admit_external_runtime(proposal, explicit_approval=explicit_approval)

    return ExternalRuntimeAdmissionEvidence(
        evidence_kind="external_runtime_admission_stub",
        status="stubbed",
        execution_performed=False,
        admitted=True,
        runtime_name=admitted.runtime_name,
        proposal_status=admitted.status,
        approval_used=explicit_approval,
        blocked_reasons=admitted.blocked_reasons,
    )