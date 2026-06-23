# CR-048: External Runtime Adapter Execution-Path Blocking Test

## Status

Implemented

## Scope

- enforce the external runtime manifest contract at the execution admission boundary
- ensure a blocked proposal strictly halts execution via a hard exception
- ensure explicit approval acts as a gate but not as a bypass for structurally invalid models
- decouple classification (descriptive validation) from admission (enforceable blocking)

## Non-Scope

- do not integrate this adapter with general model-routing policy yet
- do not introduce an admission token or broader execution state machine yet
- do not change runtime behavior outside of testing

## Implementation Authority

Code implementation slice containing pure functions, no live cloud or local integration.

## Description

This change introduces the `admit_external_runtime` function and the `RuntimeAdmissionError` to enforce the external runtime manifest contract. By keeping admission enforcement separate from descriptive parsing (`normalize_external_runtime_manifest`), we ensure that structurally invalid or policy-blocked proposals immediately halt the execution path. Explicit human approval satisfies mutation capability requirements, but it cannot override an inherently blocked manifest.

## Acceptance Criteria

- [x] Blocked proposals raise `RuntimeAdmissionError`.
- [x] Proposed proposals pass admission and return the proposal.
- [x] Approval-required proposals raise `RuntimeAdmissionError` without explicit approval.
- [x] Approval-required proposals pass with explicit approval.
- [x] Blocked proposals still fail even with explicit approval.
- [x] `RuntimeAdmissionError` lives in `external_runtime_adapter.py` to keep the boundary narrow.
- [x] Tests confirm all branches.

## Validation

```powershell
python -m py_compile triage_core\external_runtime_adapter.py
python -m pytest tests\test_external_runtime_adapter.py -q
git diff --check
```
