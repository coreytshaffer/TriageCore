# CR-111: Reviewer Runbook Note for `tc` Console-Script Shim Fallback

## Status

Implemented

## Scope

- Docs-only. Add a short "If `tc` is blocked or not found" note to the
  reviewer-facing runbooks that use bare `tc` commands:
  - `docs/operations/reviewer-smoke-runbook.md` (new section with one
    worked example),
  - `docs/operations/reviewer-entrypoints.md` (Validation Path section),
  - `docs/operations/reviewer-traceability.md` (Trace Commands section).
- The note states that every `tc ...` command can be run as
  `python -m triage_core.tc_cli ...` when the console-script shim is
  unavailable — for example, not on `PATH` or blocked by a local
  application-control policy.

## Non-Goals

- No runtime code, CLI behavior, or entry-point changes.
- No new commands, flags, or output changes.
- No packaging, installer, or publishing changes.
- No claim that the fallback bypasses or should bypass any local
  security policy; it is a documented alternate launch form only.

## Description

On at least one reviewer environment (observed 2026-07-05), a local
Windows Application Control policy blocked the installed console-script
shim (`...\Python\pythoncore-3.14-64\Scripts\tc.exe`) with "An
Application Control policy has blocked this file." The identical
functionality is reachable via `python -m triage_core.tc_cli <args>`:
`pyproject.toml` maps the `tc` script to `triage_core.tc_cli:main`, and
the module's `__main__` guard calls the same `main()`, so both forms
invoke the same CLI entry point.

Without a documented fallback, a reviewer hitting this block could
misread the smoke path as broken. This slice adds a short note to the
three reviewer-facing runbooks that use bare `tc` commands so the
substitution is discoverable at the point of use.

## Acceptance Criteria

- [x] The smoke runbook has an "If `tc` Is Blocked Or Not Found" section
  with one `python -m triage_core.tc_cli doctor` example and a statement
  that the substitution does not change command behavior.
- [x] The reviewer entrypoints Validation Path section carries a
  one-paragraph version of the note linking back to the smoke runbook.
- [x] The reviewer traceability trace-commands section carries a
  one-sentence version of the note.
- [x] No runtime files are changed.

## Validation

- `git diff --check`
- `python -m pytest tests/test_tc_cli.py -q` (sanity check that the
  documented module entry point's test surface still passes; no code
  changed in this slice)
