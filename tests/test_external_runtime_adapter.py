import pytest

from triage_core.external_runtime_adapter import (
    ExternalRuntimeAdmissionEvidence,
    RuntimeAdmissionError,
    admit_external_runtime,
    execute_external_runtime_stub,
    normalize_external_runtime_manifest,
)


def _read_only_manifest(**overrides: object) -> dict[str, object]:
    manifest = {
        "schema_version": "1.0.0",
        "runtime_name": "example-read-only-runtime",
        "runtime_version": "0.1.0",
        "runtime_kind": "external_agent",
        "adapter_version": "0.1.0",
        "capability_profile": "read_only_summary",
        "tool_policy_hash": "sha256:example-read-only-policy",
        "sandbox_mode": "read_only",
        "network_access": "blocked",
        "credential_access": "none",
        "model_provider": "none",
        "model_identity": "none",
        "approval_required": True,
        "provenance_required": True,
        "revocation_supported": True,
    }
    manifest.update(overrides)
    return manifest


def _draft_only_manifest(**overrides: object) -> dict[str, object]:
    manifest = {
        "schema_version": "1.0.0",
        "runtime_name": "example-draft-runtime",
        "runtime_version": "0.1.0",
        "runtime_kind": "automation_gateway",
        "adapter_version": "0.1.0",
        "capability_profile": "draft_only",
        "tool_policy_hash": "sha256:example-draft-policy",
        "sandbox_mode": "workspace_write",
        "network_access": "blocked",
        "credential_access": "none",
        "model_provider": "local_only",
        "model_identity": "example-local-model@sha256:placeholder",
        "approval_required": True,
        "provenance_required": True,
        "revocation_supported": True,
    }
    manifest.update(overrides)
    return manifest


def test_read_only_manifest_normalizes_to_inert_proposal():
    proposal = normalize_external_runtime_manifest(_read_only_manifest())

    assert proposal.status == "proposed"
    assert proposal.manifest_valid is True
    assert proposal.authority_granted is False
    assert proposal.execution_allowed is False
    assert proposal.approval_required is True
    assert proposal.blocked_reasons == ()
    assert proposal.proposed_record["record_type"] == "external_runtime_capability_proposal"
    assert proposal.proposed_record["schema_version"] == "1.0.0"
    assert proposal.proposed_record["runtime_name"] == "example-read-only-runtime"


def test_draft_only_manifest_normalizes_safely_without_execution():
    proposal = normalize_external_runtime_manifest(_draft_only_manifest())

    assert proposal.status == "proposed"
    assert proposal.manifest_valid is True
    assert proposal.authority_granted is False
    assert proposal.execution_allowed is False
    assert proposal.approval_required is True
    assert proposal.proposed_record["capability_profile"] == "draft_only"


def test_mutation_capable_profile_requires_approval_but_stays_inert():
    proposal = normalize_external_runtime_manifest(
        _draft_only_manifest(capability_profile="approved_mutation")
    )

    assert proposal.status == "approval_required"
    assert proposal.manifest_valid is True
    assert proposal.authority_granted is False
    assert proposal.execution_allowed is False
    assert proposal.approval_required is True


def test_invalid_manifest_stays_blocked_without_authority():
    proposal = normalize_external_runtime_manifest(
        {
            "schema_version": "1.0.0",
            "runtime_name": "example-invalid-runtime",
            "runtime_version": "latest",
            "runtime_kind": "unknown",
            "adapter_version": "",
            "capability_profile": "approved_mutation",
            "tool_policy_hash": "",
            "sandbox_mode": "unknown",
            "network_access": "unknown",
            "credential_access": "unknown",
            "model_provider": "unknown",
            "model_identity": "default",
            "approval_required": False,
            "provenance_required": False,
            "revocation_supported": False,
        }
    )

    assert proposal.status == "blocked"
    assert proposal.manifest_valid is False
    assert proposal.authority_granted is False
    assert proposal.execution_allowed is False
    assert "runtime_version_alias_only" in proposal.blocked_reasons
    assert "unknown_boundary:runtime_kind" in proposal.blocked_reasons
    assert "approval_required_false" in proposal.blocked_reasons
    assert "provenance_required_false" in proposal.blocked_reasons
    assert "revocation_not_supported" in proposal.blocked_reasons


def test_missing_schema_version_blocks_without_authority():
    manifest = _read_only_manifest()
    manifest.pop("schema_version")

    proposal = normalize_external_runtime_manifest(manifest)

    assert proposal.status == "blocked"
    assert proposal.manifest_valid is False
    assert proposal.authority_granted is False
    assert proposal.execution_allowed is False
    assert "missing_or_blank:schema_version" in proposal.blocked_reasons


def test_non_dict_manifest_root_blocks_immediately():
    proposal = normalize_external_runtime_manifest(["not", "a", "dict"])

    assert proposal.status == "blocked"
    assert proposal.manifest_valid is False
    assert proposal.authority_granted is False
    assert proposal.execution_allowed is False
    assert proposal.blocked_reasons == ("invalid_manifest_root",)


def test_proposed_status_passes_admission():
    proposal = normalize_external_runtime_manifest(_read_only_manifest())
    admitted = admit_external_runtime(proposal)
    assert admitted is proposal


def test_blocked_proposal_raises_admission_error():
    manifest = _read_only_manifest()
    manifest.pop("schema_version")
    proposal = normalize_external_runtime_manifest(manifest)

    with pytest.raises(RuntimeAdmissionError, match="External runtime proposal blocked: missing_or_blank:schema_version"):
        admit_external_runtime(proposal)


def test_approval_required_blocks_without_explicit_approval():
    proposal = normalize_external_runtime_manifest(
        _draft_only_manifest(capability_profile="approved_mutation")
    )

    with pytest.raises(RuntimeAdmissionError, match="External runtime proposal requires explicit approval before admission"):
        admit_external_runtime(proposal, explicit_approval=False)


def test_approval_required_passes_with_explicit_approval():
    proposal = normalize_external_runtime_manifest(
        _draft_only_manifest(capability_profile="approved_mutation")
    )

    admitted = admit_external_runtime(proposal, explicit_approval=True)
    assert admitted is proposal


def test_blocked_proposal_cannot_be_admitted_with_explicit_approval():
    manifest = _read_only_manifest()
    manifest.pop("schema_version")
    proposal = normalize_external_runtime_manifest(manifest)

    with pytest.raises(RuntimeAdmissionError, match="External runtime proposal blocked: missing_or_blank:schema_version"):
        admit_external_runtime(proposal, explicit_approval=True)


def test_execute_stub_does_not_emit_success_for_blocked_proposal():
    manifest = _read_only_manifest()
    manifest.pop("schema_version")
    proposal = normalize_external_runtime_manifest(manifest)

    with pytest.raises(RuntimeAdmissionError, match="External runtime proposal blocked: missing_or_blank:schema_version"):
        execute_external_runtime_stub(proposal)


def test_execute_stub_returns_admission_evidence():
    proposal = normalize_external_runtime_manifest(_read_only_manifest())
    evidence = execute_external_runtime_stub(proposal)

    assert isinstance(evidence, ExternalRuntimeAdmissionEvidence)
    assert evidence.evidence_kind == "external_runtime_admission_stub"
    assert evidence.status == "stubbed"
    assert evidence.execution_performed is False
    assert evidence.admitted is True
    assert evidence.runtime_name == "example-read-only-runtime"
    assert evidence.proposal_status == "proposed"
    assert evidence.approval_used is False
    assert evidence.blocked_reasons == ()


def test_execute_stub_records_explicit_approval_when_used():
    proposal = normalize_external_runtime_manifest(
        _draft_only_manifest(capability_profile="approved_mutation")
    )
    evidence = execute_external_runtime_stub(proposal, explicit_approval=True)

    assert evidence.admitted is True
    assert evidence.proposal_status == "approval_required"
    assert evidence.approval_used is True
