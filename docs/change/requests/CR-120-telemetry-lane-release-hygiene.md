# CR-120: Telemetry Lane Release Hygiene

## Status

Implemented (docs-only)

## Summary

Record the post-merge state of the completed CR-117 through CR-119 telemetry
and reviewer-readiness lane, and correct stale CR numbering in the telemetry
brief so reviewers do not confuse the CR-114 checkpoint with the probe
validation work.

This slice is release hygiene only. It adds no runtime behavior, no probe
execution, no schema changes, no routing integration, no ledger writes, and no
new model/backend calls.

## Scope

- Add a concise telemetry lane release-hygiene note under operations docs.
- Update the active backlog so the reviewer checkpoint/release-hygiene
  candidate is marked done as CR-120.
- Correct `docs/operations/local-backend-telemetry.md` status language so the
  implemented anchors are CR-118 for the record contract and CR-119 for the
  probe emission validation gate.
- Update the future-agent handoff with a post-handoff note that CR-117,
  CR-118, CR-119, and CR-120 are complete.
- Add a changelog entry for the docs-only hygiene slice.

## Non-Goals

- No probe execution changes.
- No new telemetry schema fields or validator behavior.
- No routing, route-input, circuit-breaker, degraded-mode, or daily-driver
  integration.
- No CLI behavior changes.
- No ledger writes or new persisted evidence records.
- No full release certification or tag creation.

## Validation

- `git diff --check`

Docs-only validation is sufficient because this slice edits documentation only.
