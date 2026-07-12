# Eval Scoring Scope Boundary

This note scopes the first scoring-capable follow-on after the CR-121 fixture
validator and CR-122 `tc eval validate-fixtures` command.

## Allowed First Scoring Slice

A future scoring slice may be a deterministic, explicit-file comparison between:

- a validated `eval_case_v0` JSONL fixture file
- a directory or file of already-exported actual-outcome contract JSON records

The comparison may report:

- total fixture cases considered
- missing actuals by `case_id`
- unexpected actuals not present in the fixture
- decision matches or mismatches against `expected_control_plane_decision`
- boundary-family counts
- expected eval outcome counts from the fixture
- a bounded pass/fail/block summary for the static comparison

The comparison must treat invalid fixtures or invalid actual-outcome records as
fail-closed input errors, not as softer test failures.

## Required Boundaries

The scoring slice must remain offline and read-only. It must not call model
backends, execute prompts, probe endpoints, mutate source files, write ledger
events, update approval state, or route work.

TriageCore may compare static files that already exist. It must not claim that
the comparison certifies production safety, approves execution, or replaces an
external evaluator.

## Relationship To External Evals

The independent `agent-control-evals` harness remains the authoritative place
for cross-repository evaluation runs. TriageCore can provide local smoke
comparison for exported actuals only so operators can catch obvious contract
drift before handing artifacts to the external harness.

## Out Of Scope For The First Slice

- adversarial or tampering fixture expansion
- behavioral route diffing
- benchmark ranking
- model quality scoring
- automatic discovery of actuals
- default output locations
- ledger persistence
- policy enforcement
- human approval decisions
