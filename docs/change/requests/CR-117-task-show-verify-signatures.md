# CR-117: Task-Show Opt-In Signature Verification

## Status

Implemented (runtime-safe, evidence-only)

## Summary

Add an opt-in `tc task show --verify-signatures` flag that verifies the
signatures of the signed ledger events belonging to the shown task and
reports the result inline. This decouples signature checking from the
whole-ledger audit command's CLI-abort mechanics by introducing a
task-scoped verification helper that returns a categorized summary and
never calls `sys.exit`; the command decides its own exit behavior. It
reuses the CR-097 fail-closed identity-registry-load categories. No
runtime, approval, signing, routing, or execution semantics change.

## Scope

- Add `verify_task_event_signatures(ledger_path, task_id)` to
  `triage_core/task_ledger.py`. It reuses the existing per-event verifiers
  (`route_audit`, `validation_result`, `route_decision`) and the shared
  `LedgerSignatureVerificationSummary` / `LedgerSignatureVerificationFinding`
  types, restricts attention to events whose `task_id` matches the request,
  and covers all three signed event types in a single pass. It never calls
  `sys.exit`. The whole-ledger `verify_ledger_event_signatures_in_ledger`
  is left unchanged.
- Add `--verify-signatures` (default off) to the `tc task show` parser and
  extend `tc_task_show` to run the task-scoped verifier when the flag is
  set, printing a summary and per-event findings in place of the existing
  static "not checked" line.
- On identity-registry load failure, reuse CR-097's
  `_handle_registry_load_failure` (prints `reason=registry_load_failed`
  plus category, exits 1).

## Behavior and exit codes

- Flag off (default): output is byte-for-byte unchanged, including the
  "Signature verification: not checked by this command; run tc audit
  --verify-signatures" line.
- Flag on: prints `valid_signed / invalid_signed / unsigned / malformed /
  skipped_non_target` plus per-event `PASS`/`FAIL` findings.
- Exit codes: `0` when the task is found and verification is clean;
  `1` for invalid or malformed signatures (fail-closed via
  `should_fail(strict=False)`), identity-registry load failure, or the
  existing task-not-found case. Unsigned signed-type events remain
  informational and do not fail; there is no `--strict` in this slice.
- An unparseable ledger line cannot be attributed to a task, so it is
  counted as `malformed` fail-closed rather than silently ignored.

## Non-Goals

- No change to whole-ledger `tc audit --verify-signatures` behavior.
- No `--strict` flag and no failing on unsigned events in this slice.
- No change to signing, approval, routing, admission, or execution
  semantics; verification only surfaces existing evidence.
- No new backends, network egress, dependencies, or ledger writes; the
  command is read-only over the local ledger and identity registry.

## Validation

- New `tests/test_cr_117_task_show_verify_signatures.py`: flag-off output
  unchanged; valid signed event exits 0; tampered signature exits 1;
  malformed ledger line exits 1; unsigned signed-type event exits 0;
  identity-registry load failure exits 1 with `category=malformed_registry`;
  task-not-found exits 1.
- Focused suite (task show, audit CLI, CR-097 registry load, task ledger,
  tc CLI) plus the full `python -m pytest -q` regression.

## Notes

A valid signature is evidence that an event was signed by a known,
authorized identity — not evidence of approval, safety, or correctness.
Claiming CR-117 shifts the telemetry lane references to CR-118+ (schema
candidate CR-118, probe candidate CR-119+) in active planning and handoff
docs, following the same renumbering precedent CR-115 and CR-116 set.
