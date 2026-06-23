# CR-052: Task Envelope Template Contract

## Status

Implemented

## Scope

- define the minimal, reusable Task Envelope contract that future CLI, Markdown report, and TUI tools will render
- specify required, conditionally required, and optional fields for the envelope
- include a blank copyable template
- include a completed example of a docs-only slice (e.g., CR-051)
- reference `.triagecore/ledger.jsonl` as a future historical source of truth only
- remain strictly documentation-based: no active CLI implementation, no TUI, no Python execution changes, and no ledger reads/writes

## Implementation Authority

Code implementation slice containing pure documentation; no live Python code, network, or ledger integration.

## Description

This change formalizes the Task Envelope concept introduced in CR-051 into a concrete contract and template. By documenting the exact shape and field requirements of the envelope, we create a stable foundation for the next phases of operator UX: the Markdown report export and the CLI task-envelope wizard. This slice ensures all future interfaces consistently represent execution boundaries, risk, and admission state to the operator in a calm, legible format without prematurely building UI scaffolding.

## Acceptance Criteria

- [x] `docs/operations/task-envelope-template.md` defines the contract clearly
- [x] The template is copyable and usable for future bounded CR work
- [x] The example demonstrates a completed docs-only slice
- [x] The document clearly supports future CLI/report/TUI work without implementing it
- [x] Backlog points to Markdown report export or CLI wizard as later slices
- [x] Changelog records CR-052
- [x] `git diff --check` passes
- [x] Strict adherence to docs-only constraints (no `CR-050` UX file revival)

## Validation

```powershell
git diff --check
```
