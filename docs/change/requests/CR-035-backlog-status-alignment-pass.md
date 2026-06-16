# CR-035: Backlog and Status Alignment Pass

## Status

Implemented

## Scope

Update documentation so the public project status matches the merged state
after CR-034.

This change:

- updates `docs/current_backlog.md` to reflect the post-CR-034 state
- adds CR-034 to the completed safety spine
- distinguishes active identity lifecycle work, model/runtime integrity work,
  and completed repository hygiene work
- checks README proof markers for stale release/status language
- records the change in the changelog

## Non-Scope

- Do not implement runtime integrity enforcement.
- Do not expand signing beyond `route_audit`.
- Do not change packaging or security behavior.
- Do not add new runtime code.

## Acceptance Criteria

- [x] `docs/current_backlog.md` reflects the post-CR-034 state.
- [x] Completed safety spine includes CR-034.
- [x] Current recommendation distinguishes three lanes:
  - identity lifecycle work remains under Issue #4
  - model/runtime integrity builds on CR-031 through CR-033
  - repository hygiene baseline from CR-034 is complete
- [x] README has no stale claim that the first release tag is still pending.
- [x] No runtime code changes.
- [x] Full test suite still passes.

## Validation

```powershell
python -m pytest -q
git diff --check
git status --short
```
