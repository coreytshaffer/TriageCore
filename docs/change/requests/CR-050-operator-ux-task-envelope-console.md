# CR-050: Operator UX And Task Envelope Console

## Status

Implemented

## Scope

- add a docs-only operator UX design note for a calm, governance-first console
- add a reusable task-envelope template for daily operator work
- update backlog guidance so follow-on UX slices stay small and reviewable
- do not change runtime behavior or CLI commands in this slice

## Non-Scope

- do not implement a web dashboard
- do not add Textual or terminal UI code
- do not rename existing CLI commands yet
- do not introduce autonomous execution controls

## Implementation Authority

Documentation-only slice. No runtime or policy behavior changes.

## Description

This change turns the current operator UX direction into concrete repo artifacts without adding interface code prematurely. The design note defines the UX north star, recommended surface order, risk language, agent-lane model, evidence expectations, and failure-message shape. The task-envelope template translates that guidance into a copyable operational document that keeps scope, allowed files, approval gates, and evidence visible before implementation work starts.

Because `CR-049` is already used in this repository for the external runtime admission caller stub, this UX slice is recorded as `CR-050` to preserve chronological consistency.

## Acceptance Criteria

- [x] Adds a docs-only operator console design note under `docs/ux/`
- [x] Adds a reusable task-envelope template under `docs/operations/`
- [x] Records the slice as `CR-050` without conflicting with existing CR numbering
- [x] Updates `docs/current_backlog.md` with bounded follow-on UX work
- [x] Updates `docs/change/change_log.md`
- [x] Makes safe behavior, approval gates, and evidence visibility explicit

## Validation

```powershell
git diff --check
```
