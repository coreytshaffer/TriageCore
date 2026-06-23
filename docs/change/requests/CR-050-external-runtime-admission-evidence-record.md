# CR-050: External Runtime Admission Evidence Record

## Status

Implemented

## Scope

- add a pure structured evidence/result class `ExternalRuntimeAdmissionEvidence` for `execute_external_runtime_stub(...)`
- include explicitly defined audit fields: `execution_performed`, `admitted`, `runtime_name`, `proposal_status`, `approval_used`, `blocked_reasons`
- do not write to ledger yet
- do not add network calls or launch runtimes
- do not introduce admission tokens

## Implementation Authority

Code implementation slice containing pure functions, no live cloud or local integration.

## Description

This change formalizes the output of the execution-path admission stub into an explicitly structured, inert admission evidence record. By separating the fact of admission from the act of execution—and formalizing it in an auditable dataclass—TriageCore can verifiably state that a proposal was admitted without falsely claiming any execution side-effects occurred. This keeps the execution stub strictly pure for robust deterministic testing and review.

## Acceptance Criteria

- [x] Adds `ExternalRuntimeAdmissionEvidence` dataclass
- [x] Execution stub returns the structured evidence
- [x] Tests confirm `test_execute_stub_returns_admission_evidence` behaves correctly
- [x] Tests confirm `test_execute_stub_records_explicit_approval_when_used` reflects approval usage
- [x] Tests confirm `test_execute_stub_does_not_emit_success_for_blocked_proposal`
- [x] No side-effects, ledger entries, or runtime launches are performed
- [x] Tracks via backlog and change log

## Validation

```powershell
python -m py_compile triage_core\external_runtime_adapter.py
python -m pytest tests\test_external_runtime_adapter.py -q
git diff HEAD --check
```
