# CR-DD-009: Governed `tc run` Planning Surface

## Status

Candidate — not implemented. First implementation slice proposed by CR-DD-000 (M0).

> Numbering note: CR-DD-001 through CR-DD-008 are already used (CR-DD-001 was the `tc status`
> command). The next free number in the daily-driver series is CR-DD-009, used here for the
> `tc run` surface originally sketched as "CR-DD-001."

This CR defines the boundaries for the highest-leverage daily-driver slice: a single governed
operator command that surfaces the existing `TriageClient.run_task` loop. This document is the
planning/definition record; the implementation lands under this CR only after review.

## Scope

- Add a `tc run` command that wraps the existing `TriageClient.run_task` governed loop:
  privacy scan (fail-closed) → external-safe packet gate → classify → specialist route →
  resilience route (`choose_resilience_route`) → local execution → justified cloud escalation
  via the existing bounded Qwen path.
- Accept a prompt, optional `--files`, and an optional validator; stream output; write
  route/worker/token evidence to `.triagecore/ledger.jsonl`.
- Use the resilience router for the routing decision (unlike `triagecore run-pipeline`, which
  calls the engine directly and bypasses routing).
- Designate `tc` as the single daily-driver surface and document `triagecore` as the
  internal/benchmark CLI, without removing existing commands.

## Non-Goals

- No new backends. Cloud remains the existing bounded Qwen path only; **no** Claude/GPT/Gemini
  backends in this slice (that is M2 / a future CR).
- No live capability probe and no circuit breakers (M1 / future CRs); route inputs remain as
  they are today.
- No budget *enforcement* or pre-send compaction (M3); token accounting stays advisory and
  recorded.
- No changes to privacy, external-safe, or human-review invariants; `tc run` inherits them
  unchanged and must fail closed exactly as `run_task` does today.
- No autonomous or background execution; the command runs one operator-initiated task.
- No TriageDesk execution surface changes (M4).
- No claims of energy, cost, quality, or safety improvement.

## Description

`TriageClient.run_task` already performs the full governed local-first-then-cloud loop and is
covered by tests, but it is reachable only as a library call and via the benchmark harness.
`triagecore run-pipeline` runs the engine directly and does not invoke the resilience router
or the cloud-escalation branch. As a result, the project's central capability is invisible in
daily use and produces no operator-initiated evidence.

`tc run` closes that gap by surfacing the existing loop as one command. It is the correct
first slice because it converts hidden library capability into daily-use evidence and makes
every later readiness claim verifiable: whether local-first actually happened, whether cloud
escalation occurred only when justified, whether token-budget evidence was recorded, whether
privacy fail-closed held, and whether the operator used the surface daily (see the Evidence
Requirements in `docs/architecture/daily_driver_orchestrator_spec.md`).

This slice deliberately adds no new routing intelligence, backends, probes, or enforcement.
It wires what exists into an operator-facing, evidence-producing command, keeping the change
small and reviewable and preserving every current invariant.

## Acceptance Criteria

- [ ] `tc run` executes an arbitrary task through `run_task` and returns a usable result.
- [ ] The command's routing decision comes from `choose_resilience_route`, not a direct engine
  call.
- [ ] Each run writes `route_decision`, `worker_result`, and token evidence to the ledger.
- [ ] Local-only / sensitive packets fail closed with no external egress, matching current
  `run_task` behavior; the CR-021 privacy-invariant scan stays clean.
- [ ] Cloud escalation uses only the existing bounded Qwen path and only on a justified route;
  no new provider is added.
- [ ] `tc` is documented as the daily-driver surface; existing `triagecore` commands are
  unchanged.
- [ ] Tests cover local execution, justified escalation, and fail-closed local-only handling,
  running offline with mocked backends per the existing test convention.

## Validation

- `python -m pytest -q`
- `tc audit --privacy-invariants` (CR-021 invariant remains clean)
- `git diff --check`
- Manual: `tc run` a small task against a local backend and confirm route/worker/token events
  appear via `tc audit`.

## Dependencies / Sequencing

- Depends on CR-DD-000 (planning normalization) being accepted.
- Precedes M1 (live capability probe + circuit breakers) and M2 (frontier backends). Frontier
  backends must not be started before this slice and M1 land.
