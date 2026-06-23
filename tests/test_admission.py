import pytest
from triage_core.admission import ExternalRuntimeAdmissionEvidence, render_admission_evidence_markdown, admission_evidence_from_mapping

def test_render_admitted_state():
    evidence = ExternalRuntimeAdmissionEvidence(
        admitted=True,
        execution_performed=False,
        requested_runtime="python-local",
        requested_capability="read_only",
        approval_required=False,
        approval_used=False,
        blocked_reasons=(),
        manifest_or_source_evidence='{ "script": "test.py" }',
        approval_evidence=None,
    )
    markdown = render_admission_evidence_markdown(evidence)
    
    assert "**Admitted:** true" in markdown
    assert "**Execution Performed:** false" in markdown
    assert "**Approval Required:** false" in markdown
    assert "**Approval Used:** false" in markdown
    assert "- None" in markdown

def test_render_blocked_state():
    evidence = ExternalRuntimeAdmissionEvidence(
        admitted=False,
        execution_performed=False,
        requested_runtime="python-local",
        requested_capability="read_write",
        approval_required=False,
        approval_used=False,
        blocked_reasons=("runtime not declared in manifest",),
        manifest_or_source_evidence='{ "script": "write.py" }',
        approval_evidence=None,
    )
    markdown = render_admission_evidence_markdown(evidence)
    
    assert "**Admitted:** false" in markdown
    assert "**Execution Performed:** false" in markdown
    assert "- runtime not declared in manifest" in markdown

def test_render_approval_required_state():
    evidence = ExternalRuntimeAdmissionEvidence(
        admitted=False,
        execution_performed=False,
        requested_runtime="python-local",
        requested_capability="read_write",
        approval_required=True,
        approval_used=False,
        blocked_reasons=("explicit approval required",),
        manifest_or_source_evidence='{ "script": "dangerous.py" }',
        approval_evidence=None,
    )
    markdown = render_admission_evidence_markdown(evidence)
    
    assert "**Admitted:** false" in markdown
    assert "**Approval Required:** true" in markdown
    assert "**Approval Used:** false" in markdown
    assert "- explicit approval required" in markdown

def test_render_admitted_with_approval_used():
    evidence = ExternalRuntimeAdmissionEvidence(
        admitted=True,
        execution_performed=False,
        requested_runtime="python-local",
        requested_capability="read_write",
        approval_required=True,
        approval_used=True,
        blocked_reasons=(),
        manifest_or_source_evidence='{ "script": "dangerous.py" }',
        approval_evidence="operator-approved: CR-062-demo",
    )
    markdown = render_admission_evidence_markdown(evidence)
    
    assert "**Admitted:** true" in markdown
    assert "**Approval Required:** true" in markdown
    assert "**Approval Used:** true" in markdown
    assert "**Approval Evidence:** operator-approved: CR-062-demo" in markdown
    assert "- None" in markdown

def test_admission_evidence_from_mapping_valid():
    payload = {
        "admitted": True,
        "execution_performed": False,
        "requested_runtime": "python-local",
        "requested_capability": "read_write",
        "approval_required": True,
        "approval_used": True,
        "blocked_reasons": ["explicit approval required"],
        "manifest_or_source_evidence": "{\"script\": \"test.py\"}",
        "approval_evidence": "approved!"
    }
    evidence = admission_evidence_from_mapping(payload)
    assert evidence.admitted is True
    assert evidence.blocked_reasons == ("explicit approval required",)

def test_admission_evidence_from_mapping_rejects_missing_bool():
    payload = {
        # missing "admitted"
        "execution_performed": False,
        "requested_runtime": "python-local",
        "requested_capability": "read_only",
        "approval_required": False,
        "approval_used": False,
        "blocked_reasons": [],
        "manifest_or_source_evidence": "{}",
        "approval_evidence": None
    }
    with pytest.raises(ValueError, match="Missing or invalid boolean field: 'admitted'"):
        admission_evidence_from_mapping(payload)

def test_admission_evidence_from_mapping_rejects_bad_bool_type():
    payload = {
        "admitted": "true", # string instead of bool
        "execution_performed": False,
        "requested_runtime": "python-local",
        "requested_capability": "read_only",
        "approval_required": False,
        "approval_used": False,
        "blocked_reasons": [],
        "manifest_or_source_evidence": "{}",
        "approval_evidence": None
    }
    with pytest.raises(ValueError, match="Missing or invalid boolean field: 'admitted'"):
        admission_evidence_from_mapping(payload)

def test_admission_evidence_from_mapping_rejects_empty_required_string():
    payload = {
        "admitted": True,
        "execution_performed": False,
        "requested_runtime": "   ", # empty/whitespace
        "requested_capability": "read_only",
        "approval_required": False,
        "approval_used": False,
        "blocked_reasons": [],
        "manifest_or_source_evidence": "{}",
        "approval_evidence": None
    }
    with pytest.raises(ValueError, match="Missing or empty string field: 'requested_runtime'"):
        admission_evidence_from_mapping(payload)

def test_admission_evidence_from_mapping_allows_empty_blocked_reasons():
    payload = {
        "admitted": True,
        "execution_performed": False,
        "requested_runtime": "python-local",
        "requested_capability": "read_only",
        "approval_required": False,
        "approval_used": False,
        "blocked_reasons": [], # empty list allowed
        "manifest_or_source_evidence": "{}",
        "approval_evidence": None
    }
    evidence = admission_evidence_from_mapping(payload)
    assert evidence.blocked_reasons == ()

def test_admission_evidence_from_mapping_rejects_bad_blocked_reason_item():
    payload = {
        "admitted": True,
        "execution_performed": False,
        "requested_runtime": "python-local",
        "requested_capability": "read_only",
        "approval_required": False,
        "approval_used": False,
        "blocked_reasons": ["valid reason", "   ", 42],
        "manifest_or_source_evidence": "{}",
        "approval_evidence": None
    }
    with pytest.raises(ValueError, match="Invalid item in list field 'blocked_reasons': must be non-empty string"):
        admission_evidence_from_mapping(payload)

def test_admission_evidence_from_mapping_allows_null_approval_evidence():
    payload = {
        "admitted": True,
        "execution_performed": False,
        "requested_runtime": "python-local",
        "requested_capability": "read_only",
        "approval_required": False,
        "approval_used": False,
        "blocked_reasons": [],
        "manifest_or_source_evidence": "{}",
        "approval_evidence": None # null allowed
    }
    evidence = admission_evidence_from_mapping(payload)
    assert evidence.approval_evidence is None

