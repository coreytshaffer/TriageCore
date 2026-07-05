# Reviewer Traceability

## Purpose

This document answers one reviewer question using existing surfaces only:

> Can a reviewer trace a route decision or proposed action from input, to decision/evidence record, to approval or rejection state, to verification or test evidence?

It walks the trace chain in plain language, catalogs the ledger event types that carry the trace, and points at the exact CLI command for each hop. It adds no runtime behavior, no new authority, and no change to the approval model: humans review one exact task record and its artifacts, not "the agent."

## Claim Boundary

A completed trace shows that the recorded evidence is present, linked by `task_id`, privacy-safe, and (where signing was used) tamper-evident. It does not by itself prove correctness, safety, authorization, production readiness, or model-safety properties. Signatures prove provenance and tamper evidence only.

## The Trace Chain

1. **Input.** A task enters as a `TaskPacket` ([task_packet.py](../../triage_core/task_packet.py)) with explicit privacy metadata, or as a task envelope ([task_envelope.py](../../triage_core/task_envelope.py)). Raw prompt and data content are never persisted to the ledger.
2. **Route decision and evidence record.** `TriageClient.run_task` ([client.py](../../triage_core/client.py)) privacy-scans the packet and appends metadata-only events to the append-only ledger at `.triagecore/ledger.jsonl` via `TaskLedger` ([task_ledger.py](../../triage_core/task_ledger.py)): a `route_audit` event for the allow/block outcome, a `route_decision` event for the routing choice (optionally signed), then `worker_result` and `validator_completed` events for execution and validation outcomes.
3. **Reduced record.** `TaskLedger._apply_event` folds all events for one `task_id` into a single `TaskRecord`. The field meanings are documented in [evidence_schema.md](../evidence_schema.md).
4. **Approval or rejection state.** When classification, routing, or a handoff sets `human_review_required`, the task appears in the review queue ([review_queue.py](../../triage_core/review_queue.py), `tc review list`) until a `review_completed` event records `review_decision` (`accepted`, `accepted_with_minor_edits`, or `rejected`) and `task_outcome`.
5. **Verification and test evidence.** `tc audit --privacy-invariants` checks that persisted events contain no forbidden raw-content keys; `tc audit --verify-signatures` checks signed event provenance; the pytest suite (including the traceability regression test below) is the repeatable test evidence.

## Ledger Event Types That Carry the Trace

| Event type | Typically appended by | Trace evidence it contributes |
| --- | --- | --- |
| `task_created` | `TriageClient.run_task`, benchmark/pipeline runners | `created_at`, `title`, `description`, `target_files` |
| `task_classified` | classification step in `run_task` | `risk_level`, `permission_profile`; medium/high risk sets `human_review_required` |
| `route_audit` | privacy/route gate in `run_task` ([route_audit.py](../../triage_core/route_audit.py)) | allow/block `decision` and `reason_code`; inspected as raw events via `tc audit --kind route_audit`, not reduced into named `TaskRecord` fields |
| `route_decision` | `run_task` via [routing/route_events.py](../../triage_core/routing/route_events.py); optionally signed | `selected_route`, `route_reason`, `route_source`, `fallback_depth`, `selected_backend`, model; can set `human_review_required` |
| `worker_result` | execution engine result path | `worker_result_status`, failure metadata, token/timing metadata |
| `validator_completed` | validator step | `validator_passed`, `validation_status`, validator name/version/scope, checked files |
| `handoff_generated` / `local_draft_generated` / `council_completed` / `task_blocked` | handoff and blocking paths | `status`, `handoff_reason`, artifact paths; handoff and blocked paths set `human_review_required` |
| `review_completed` | human review surfaces (see below) | `review_decision`, `task_outcome`, `accepted`, `reviewer_notes`, `human_review_minutes`, `review_workload` |
| `supervisor_reviewed` | supervisor import/record commands | supervisor tool, model, decision, notes, linked artifact |

Other event types (`context_budgeted`, `energy_estimated`, `outcome_revised`, `identity_rotation`, demo/smoke events) add supporting evidence but are not required for the core trace.

## Where Approval Decisions Are Recorded

`review_completed` events currently appear to be written by the desk UI ([ui/app.py](../../triage_core/ui/app.py)) and the local web server ([web/server.py](../../triage_core/web/server.py)). No `tc` CLI command writes `review_completed`. `tc review list` is read-only. This keeps recording an approval or rejection a deliberate human action against one specific task record and its exact artifacts.

## Worked Example

A deterministic, metadata-only example of one full lifecycle is provided at [ledger_task_lifecycle.example.jsonl](../examples/ledger_task_lifecycle.example.jsonl): `task_created` → `task_classified` (high risk, review required) → `route_decision` (kept local) → `worker_result` (completed) → `validator_completed` (passed) → `review_completed` (accepted, resolved).

The regression test [tests/test_reviewer_traceability.py](../../tests/test_reviewer_traceability.py) replays this fixture and asserts that:

- the fixture stays metadata-only under the persistent privacy invariant,
- the events reduce to one `TaskRecord` carrying route, validation, and review evidence,
- the task appears in the review queue before `review_completed` and clears after,
- `tc review list` reflects both states.

## Trace Commands, Hop by Hop

From the repository root, against a real local ledger:

```powershell
tc audit --kind route_audit --last 10        # allow/block decisions with reason codes
tc audit --kind route_decision --last 10     # routing choices and route source
tc audit --kind worker_result --last 10      # execution outcome metadata
tc audit --kind review_completed --last 10   # recorded approval/rejection state
tc review list                               # tasks still awaiting a review decision
tc audit --privacy-invariants                # persisted evidence contains no raw content
tc audit --verify-signatures --kind route_decision   # provenance check for signed events, when present
tc task show <task_id>                       # show one task's complete evidence chain (displays ledger evidence, does not verify signatures)
```

If the `tc` console-script shim is unavailable (for example, blocked by a local application-control policy), each `tc ...` command above can be run as `python -m triage_core.tc_cli ...` — e.g., `python -m triage_core.tc_cli review list`.

Repeatable test evidence:

```powershell
python -m pytest tests/test_reviewer_traceability.py -q
```

Signed `route_decision` events are opt-in; see [signed-route-decision-verification.md](signed-route-decision-verification.md). An unsigned event is still valid ledger evidence — it simply carries no provenance claim.

## What This Document Does Not Add

- runtime behavior or new CLI commands
- new signing, identity, or approval mechanics
- any claim that a complete trace equals safety, correctness, or authorization
