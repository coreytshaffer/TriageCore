# CR-100: Record Route-Decision and Worker-Result Ledger Events

## Status
Implemented

## Scope

- Add a standalone route/worker telemetry ledger contract in `triage_core/route_worker_ledger.py`.
- Add validated builders for `route_decision_recorded` and `worker_result_recorded` events.
- Add a deterministic JSONL append helper for explicit ledger paths.
- Add focused tests for valid events, missing fields, prohibited raw/secret-like keys, bounded append behavior, and accepted worker statuses.
- Update backlog and changelog records for the reviewer-readiness slice.

## Non-Goals

- No routing policy changes.
- No execution-policy changes.
- No approval behavior changes.
- No identity mutation.
- No automatic live-worker execution wiring.
- No persistence of prompts, raw payloads, raw model outputs, secrets, credentials, environment variables, or unsanitized exception traces.

## Description

This slice makes route choices and worker outcomes measurable as metadata-only facts without increasing TriageCore authority. The new contract records the selected route/backend/worker class and decision basis for route decisions, and records worker/backend identity, bounded status, optional coarse duration, and optional sanitized error category for worker outcomes.

The helper is intentionally standalone. Existing routing behavior and ledger reducers remain unchanged; future code can call the helper only where an explicit, reviewed telemetry append seam is appropriate.

## Acceptance Criteria

- [x] Route-decision telemetry requires task/request identity, selected route, backend, worker class, decision basis, and timestamp.
- [x] Worker-result telemetry requires task/request identity, worker/backend identity, bounded status, and timestamp.
- [x] Worker-result status is restricted to `succeeded`, `failed`, `blocked`, or `skipped`.
- [x] Prohibited raw-data and secret-like keys fail closed.
- [x] The append helper writes only the requested JSONL file and does not create parent directories or other artifacts.
- [x] Existing routing and execution files are not changed.

## Validation

- `python -m pytest tests/test_route_worker_ledger.py -q`
- `python -m pytest -q`
- `tc doctor`
- `git diff --check`
