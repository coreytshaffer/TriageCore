# CR-056: Task Envelope CLI Documentation + Examples

## Status

Implemented

## Goal

Add a stable command reference and usage examples for the `tc task-envelope` commands (`preview` and `draft`). This prevents the upcoming interactive wizard from drifting away from the explicit flag-based contract.

## Scope

- Add `docs/operations/task-envelope-cli.md` detailing the preview and draft commands.
- Provide a full command-line example showcasing all required flags for the `draft` command.
- Documentation slice only. No code changes, no runtime behavior modifications.
- Update `docs/change/change_log.md` and `docs/current_backlog.md`.

## Acceptance Criteria

- [x] Documentation accurately reflects the required and optional flags in `triage_core/tc_cli.py`.
- [x] Provides a full `tc task-envelope draft` example command.
- [x] No side-effects or Python code modified.
