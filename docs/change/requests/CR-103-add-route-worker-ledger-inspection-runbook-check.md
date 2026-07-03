# CR-103: Add Route/Worker Ledger Inspection Runbook Check

## Status
Implemented

## Scope

- Harden `docs/operations/route-worker-ledger-inspection.md` so the reviewer verification path is explicit, read-only, and one-command.
- Extend the focused fixture demo test coverage to lock the expected summary counts and privacy boundary in place.
- Update backlog and changelog records for the reviewer-readiness slice.

## Non-Goals

- No new CLI command.
- No routing changes.
- No worker execution changes.
- No admission, approval, identity, or persistence-default changes.
- No telemetry append behavior.
- No prompts, raw payloads, raw model outputs, secrets, credentials, environment variables, or unsanitized exception traces.

## Description

CR-100 defined the route/worker telemetry contract, CR-101 added the explicit inspection CLI, and CR-102 added the deterministic demo fixture. CR-103 closes the reviewer lane by making the verification command explicit in the runbook and by adding focused regression checks that keep the summary shape and privacy boundary stable.

## Acceptance Criteria

- [x] The operations note identifies the one-command reviewer smoke path.
- [x] The runbook spells out the expected summary properties reviewers should verify.
- [x] The focused test confirms the demo fixture still validates to 5 total records, 2 route decisions, 3 worker results, and exactly one each of `blocked`, `failed`, and `succeeded`.
- [x] The focused test confirms the fixture stays metadata-only and excludes forbidden raw-content fields.
- [x] No CLI, routing, or execution code is changed.

## Validation

- `python -m pytest tests/test_route_worker_ledger_demo.py -q`
- `python -m pytest tests/test_route_worker_ledger.py tests/test_route_worker_ledger_cli.py tests/test_route_worker_ledger_demo.py -q`
- `python -m pytest -q`
- `tc route-worker-ledger inspect --ledger docs/examples/route_worker_ledger_demo.jsonl`
- `tc doctor`
- `git diff --check`
