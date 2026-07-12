# CR-123: Eval Scoring Scope Boundary

## Status

Implemented (docs-only scope)

## Summary

Define the allowed shape of a future safety-boundary eval scoring slice after
CR-121 fixture validation and CR-122 fixture validation CLI stabilization.

This slice is intentionally documentation-only. It clarifies that a future
TriageCore scoring surface may compare already-exported actual-outcome files
against already-validated fixture expectations, but must not execute model
work, probe runtimes, mutate ledgers, approve actions, or replace the
independent `agent-control-evals` harness.

## Scope

- Add an eval scoring scope note for the CR-077 through CR-122 fixture lane.
- Update backlog and fixture docs so the next implementation slice is bounded
  before code is added.
- Preserve the distinction between fixture expectation validation, static
  actual-outcome comparison, and independent evaluator scoring.
- Keep the first future implementation candidate limited to explicit input
  files and deterministic summary output.

## Non-Goals

- No scoring CLI in this slice.
- No observed-behavior execution.
- No model, completion, chat, embedding, backend, endpoint, or network calls.
- No routing, admission, ledger, identity, approval, or runtime integration.
- No mutation of actual-outcome files or fixture files.
- No adversarial tampering suite or new fixture families.
- No claim that TriageCore can certify itself.

## Validation

- `git diff --check`

Docs-only validation is sufficient because this slice edits documentation only.
