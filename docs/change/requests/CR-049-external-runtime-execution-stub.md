# CR-049: External Runtime Admission Caller Stub

## Status

Implemented

## Scope

- add a tiny caller/stub/helper representing the first execution-path boundary
- prove that blocked proposals cannot reach execution logic
- do not perform live external runtime execution
- do not add network calls
- do not add admission tokens yet

## Implementation Authority

Code implementation slice containing pure functions, no live cloud or local integration.

## Description

This change introduces `execute_external_runtime_stub`, a minimal function that demonstrates the execution boundary. By calling `admit_external_runtime` as its first action, it ensures no execution steps proceed for structurally invalid, policy-blocked, or unapproved proposals. It decouples the act of validation from the actual initiation of execution, providing a strong guarantee of admission enforcement.

## Acceptance Criteria

- [x] Adds `execute_external_runtime_stub`
- [x] Tests prove blocked proposals raise `RuntimeAdmissionError` before stub execution
- [x] Tests prove admitted proposals return a stub success status
- [x] No live execution or network calls are introduced
- [x] Tracks via backlog and change log

## Validation

```powershell
python -m py_compile triage_core\external_runtime_adapter.py
python -m pytest tests\test_external_runtime_adapter.py -q
git diff --check
```
