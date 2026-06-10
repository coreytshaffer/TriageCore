# CR-012: Environment Doctor Cli

## Status
Implemented

## Scope


## Implementation Authority
Not authorized for implementation. This CR must be approved prior to any code changes.

## Description


## Acceptance Criteria
- [x] `tc_cli.py` supports a read-only `doctor` command.
- [x] `tc doctor` prints a human-readable environment report.
- [x] Report includes current directory, repo root, Python executable, Python version, `triage_core` import path, `tc` path, Git branch, and Git status.
- [x] Report includes ledger, handoff, pytest config, and scratch exclusion status when discoverable.
- [x] Git failures are handled gracefully as `unavailable`.
- [x] The command does not modify files.
- [x] Tests cover normal output, graceful Git failure, scratch exclusion detection, and read-only behavior.
