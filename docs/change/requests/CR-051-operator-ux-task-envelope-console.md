# CR-051: Operator UX and Task Envelope Console Design

## Status

Implemented

## Scope

- design the operator flow for visualizing task envelopes, admission evidence, and boundaries
- include concrete CLI-style mockups for `proposed`, `blocked`, `approval_required`, and `admitted` states
- highlight the `execution_performed=false` invariant to ensure the operator trusts the console's inertness
- handle the presentation of `RuntimeAdmissionError` and `blocked_reasons` for blocked proposals
- establish `.triagecore/ledger.jsonl` as the future source of truth for rendering historical envelopes
- keep the slice purely documentation-based
- do not implement CLI/TUI logic, ledger reads/writes, or real runtime execution

## Implementation Authority

Code implementation slice containing pure documentation; no live Python code, network, or ledger integration.

## Description

This change introduces the UX design for the TriageCore operator console. By documenting the visual presentation of "Task Envelopes" and explicit state transitions, the project lays the groundwork for a calm, transparent command-line or text-based user interface. This ensures that operators can easily audit external runtime proposals, understand blocked boundaries, and verify that no covert execution occurs, all before any live UI framework is introduced.

## Acceptance Criteria

- [x] Design explains the task envelope model
- [x] Design shows how blocked reasons and `RuntimeAdmissionError` are surfaced
- [x] Design shows how `approval_required` should be presented
- [x] Design shows how explicit approval would be represented later
- [x] Design clearly represents `execution_performed=false` across states
- [x] Design references `.triagecore/ledger.jsonl` only as a future rendering source
- [x] Design includes at least one non-binding CLI-style mockup
- [x] CR remains documentation-only
- [x] Tracks via backlog and change log

## Validation

```powershell
git diff --check
```
