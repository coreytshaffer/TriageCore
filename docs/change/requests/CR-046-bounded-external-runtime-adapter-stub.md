# CR-046: Add Bounded External Runtime Adapter Stub

## Status

Implemented

## Scope

- define a bounded external runtime adapter stub interface
- normalize declared runtime metadata into a TriageCore-native proposed record
- keep the stub inert: no execution, no authority grant, no adapter loading
- add focused tests for safe normalization and blocked authority-incomplete
  manifests
- update backlog framing so adapter stub work is complete and policy or
  execution validation remains future work

## Non-Scope

- no external runtime execution
- no shell, browser, plugin, skill, or network access
- no OpenClaw dependency
- no credential access
- no mutation authority
- no scheduled automation
- no cloud model escalation
- no approval bypass
- no live adapter loading

## Implementation Authority

Pure-Python policy stub only. No IO or external execution.

## Description

This change turns the CR-043 through CR-045 documentation spine into a tiny
bounded enforcement seam. The stub accepts a declared external runtime manifest
as input and returns a TriageCore-native proposed record that is always inert:
authority is not granted, execution remains disabled, and mutation-capable
profiles are surfaced as approval-required rather than executable. Invalid or
authority-incomplete manifests stay blocked.

## Acceptance Criteria

- [x] A bounded external runtime adapter stub exists.
- [x] The stub can normalize declared runtime metadata into a TriageCore-native
  proposed record.
- [x] The stub defaults to `authority_granted=false`.
- [x] The stub requires approval for any mutation-capable profile.
- [x] The stub performs no IO, network calls, shell calls, dynamic imports,
  credential access, or external execution.
- [x] Tests prove read-only and draft-only manifests normalize safely.
- [x] Tests prove invalid or authority-incomplete manifests do not receive
  authority.
- [x] `docs/current_backlog.md` reflects that adapter stub work is complete and
  policy tests remain future work.

## Validation

```powershell
python -m py_compile triage_core\external_runtime_adapter.py
python -m pytest tests\test_external_runtime_adapter.py -q
git diff --check
git status --short
```