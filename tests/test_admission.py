import pytest
from triage_core.admission import ExternalRuntimeAdmissionEvidence, render_admission_evidence_markdown

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
