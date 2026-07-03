# Route/Worker Ledger Inspection

## Purpose

This note shows how reviewers can inspect the CR-100 route/worker telemetry fixture with the CR-101 read-only CLI command. The fixture is deterministic, metadata-only, and does not require any routing, backend, worker, approval, or identity setup.

## Command

From the repository root:

```powershell
tc route-worker-ledger inspect --ledger docs/examples/route_worker_ledger_demo.jsonl
```

This is the reviewer smoke path for the route/worker ledger lane. It validates the fixture through the same CR-101 inspection path used for any explicit route/worker telemetry ledger.

Expected summary shape:

```text
Route/Worker Ledger Inspection
Validation: passed
Total records: 5
- route_decision_recorded: 2
- worker_result_recorded: 3
- blocked: 1
- failed: 1
- succeeded: 1
Mutation: none
```

The exact `Ledger:` path line depends on the operator's working directory.

## Runbook Check

Reviewers can verify the route/worker telemetry path with one command:

```powershell
tc route-worker-ledger inspect --ledger docs/examples/route_worker_ledger_demo.jsonl
```

Treat the check as passed when the output confirms all of the following:

- `Validation: passed`
- `Total records: 5`
- `route_decision_recorded: 2`
- `worker_result_recorded: 3`
- `blocked: 1`
- `failed: 1`
- `succeeded: 1`
- `Mutation: none`

This check is read-only. It does not create files, append telemetry, execute workers, or load runtime state outside the explicit fixture path.

## What This Demonstrates

- A route decision can be recorded as a metadata-only fact.
- A worker result can be recorded with a bounded status.
- The inspection command validates every JSONL record before summarizing it.
- The CLI can summarize event types and worker outcomes without touching runtime state.

## Privacy Boundary

The demo ledger intentionally excludes prompts, raw request payloads, raw model outputs, secrets, credentials, environment variables, and unsanitized exception traces. Evidence references are short labels only.

## Non-Goals

- No routing integration.
- No worker execution.
- No ledger append or mutation.
- No approval, admission, identity, or persistence-default changes.
- No claim that a telemetry event proves correctness, safety, or approval.
