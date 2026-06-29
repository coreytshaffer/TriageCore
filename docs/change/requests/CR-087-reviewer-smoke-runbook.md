# CR-087: Reviewer Smoke Runbook

## Status
Implemented

## Scope

- Add a reviewer-facing smoke runbook for the current stabilization checkpoint.
- Document clean-tree expectations before running reviewer validation commands.
- Document the expected interpretation for `tc --help`, `tc doctor`, `triagecore benchmark --list-only`, and `tc audit --privacy-invariants`.
- Include an optional focused unittest command with boundaries.
- Update backlog and change log wording for this docs-only stabilization slice.

## Non-Goals

- No runtime behavior changes.
- No new cryptographic surface area.
- No new signed event types.
- No identity lifecycle changes.
- No new execution pathways.
- No new agent authority.
- No Qwen or cloud integration changes.
- No GUI changes.
- No package publishing or installer changes.

## Acceptance Criteria

- [x] `docs/operations/reviewer-smoke-runbook.md` provides a clean reviewer validation sequence.
- [x] The runbook documents expected outputs or interpretation notes for each smoke command.
- [x] The runbook explains how to interpret dirty-tree warnings.
- [x] The runbook states what the smoke path does not claim.
- [x] `docs/current_backlog.md` reflects CR-087 as a stabilization/readiness slice.
- [x] `docs/change/change_log.md` records CR-087.

## Validation

- `git diff --check`
- `tc --help`
- `tc doctor`
- `triagecore benchmark --list-only`
- `tc audit --privacy-invariants`
