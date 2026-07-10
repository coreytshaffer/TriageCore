# CR-123: Evaluation Handoff Contract

## Status

Implemented (contract-only)

## Summary

Define the file-contract boundary between TriageCore and the external evaluator
suite after CR-122. TriageCore validates expected fixtures and exports actual
outcome evidence; the external evaluator suite owns scoring, pass/fail
judgment, findings, and aggregate metrics.

## Scope

- Add `docs/evals/evaluation_handoff_contract.md`.
- Define required inputs and outputs for the handoff:
  - `eval_case_v0` expected fixture JSONL.
  - `actual_outcome_export.v0` actual outcome JSON files.
- Pin deterministic path vocabulary for a future bundle:
  - `fixtures/safety_boundaries_v0.jsonl`
  - `actuals/<case_id>.json`
  - `manifest/evaluation_handoff_manifest.json`
- Document TriageCore-side exit-code expectations for fixture validation and
  existing actual-outcome smoke export commands.
- Link the existing fixture and actual-outcome docs to the handoff contract.
- Add focused documentation tests that keep the contract aligned with the
  existing fixture validator and actual outcome writer.
- Update backlog and changelog after focused tests pass.

## Non-Goals

- No scoring, pass/fail judgment, aggregate metrics, partial credit, or score
  interpretation inside TriageCore.
- No evaluator execution from TriageCore.
- No model, completion, chat, embedding, backend, endpoint, or network calls.
- No routing, admission, approval, identity, worker, or ledger integration.
- No ledger writes or durable evaluation-run evidence.
- No bundle builder, manifest writer, bundle validator, result importer, or
  external result display.
- No changes to `eval_case_v0`, actual outcome JSON fields, or the current
  fixture family.
- No adversarial or tampering expansion.

## Validation

- Focused: `python -m pytest -q tests/test_eval_handoff_contract.py tests/test_eval_fixture_cli.py tests/test_eval_fixture_validator.py tests/test_eval_outcome_contract.py` -> 32 passed
- Full suite: `python -m pytest -q` -> 935 passed, 2 skipped
