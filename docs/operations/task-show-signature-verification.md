# Task-Show Signature Verification (`tc task show --verify-signatures`)

## Purpose

`tc task show <task-id> --verify-signatures` is an opt-in, read-only way to
verify the signatures of the signed ledger events that belong to a single
task, without leaving the task-inspection view. It is the task-scoped
companion to the whole-ledger `tc audit --verify-signatures` command.

## What it does

- Default (no flag): prints the task's metadata and event timeline and does
  **not** check signatures — unchanged behavior.
- With `--verify-signatures`: verifies the signed event types
  (`route_audit`, `validation_result`, `route_decision`) belonging to that
  task and prints:
  - a summary line —
    `valid_signed / invalid_signed / unsigned / malformed / skipped_non_target`;
  - one `PASS`/`FAIL` finding per signed event, including a `reason=` code
    on failures (for example `signature_mismatch`, `unknown_agent`,
    `revoked_agent`, `unauthorized_capability`).

## Fail-closed behavior and exit codes

- `0` — task found and verification clean (no invalid or malformed
  signatures).
- `1` — any invalid or malformed signature; an identity-registry load
  failure (reusing the CR-097 categories: `unreadable_registry`,
  `malformed_registry`, `invalid_identity_record`); or the task was not
  found.
- Unsigned signed-type events are informational and do **not** fail the
  command; there is no `--strict` in this slice.
- An unparseable ledger line cannot be attributed to a task, so it counts
  as `malformed` and is treated fail-closed.

## Scope and guarantees

- Read-only: no changes to the ledger, identity registry, or any approval,
  signing, routing, or execution behavior. No network egress or new
  backends.
- The whole-ledger `tc audit --verify-signatures` command is unchanged and
  remains the tool for global signature and ledger-integrity checks.
- A valid signature is evidence that an event was signed by a known,
  authorized identity — it is not evidence of approval, safety, or
  correctness.

## Example

```powershell
python -m triage_core.tc_cli task show <task-id> --verify-signatures
```
