# CR-101: Add Route/Worker Ledger Inspection CLI

## Status
Implemented

## Scope

- Add `tc route-worker-ledger inspect --ledger <path>` as an explicit-path, read-only inspection command.
- Validate every JSONL record with the CR-100 route/worker ledger contract.
- Print reviewer-oriented counts by event type and worker-result status.
- Fail closed on missing files, malformed JSON, invalid records, and unknown or prohibited fields.
- Keep routing, execution, admission, approval, identity, and persistence defaults unchanged.

## Non-Goals

- No routing integration.
- No worker execution.
- No ledger append or mutation.
- No default `.triagecore` path discovery for this command.
- No persistence of prompts, raw payloads, model outputs, secrets, credentials, environment variables, or unsanitized exception traces.

## Description

CR-100 made route and worker telemetry records possible as a standalone metadata-only JSONL contract. CR-101 adds the reviewer lens for those facts. Operators can point the CLI at an explicit route/worker telemetry file and receive a bounded validation summary without changing runtime behavior or writing any files.

## Acceptance Criteria

- [x] `tc route-worker-ledger inspect --ledger <path>` reads only the provided file path.
- [x] Valid mixed route/worker ledgers print total records, event-type counts, worker-status counts, and validation status.
- [x] Missing files fail closed with a bounded error.
- [x] Malformed JSON and invalid records fail closed with line context.
- [x] The command is read-only and does not mutate the inspected file or create additional files.
- [x] Existing routing and execution files are not changed.

## Validation

- `python -m pytest tests/test_route_worker_ledger.py tests/test_route_worker_ledger_cli.py -q`
- `python -m pytest -q`
- `tc doctor`
- `git diff --check`
