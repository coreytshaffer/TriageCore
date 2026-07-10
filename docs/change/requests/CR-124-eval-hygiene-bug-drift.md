# CR-124: Eval Handoff Hygiene, Bug, and Drift Slice

## Status

Implemented

## Summary

Close one small post-CR-123 maintenance loop: fix a single-pass iterable bug in
actual outcome export writing, update stale eval sequencing docs so they no
longer imply an internal TriageCore scoring slice, and add focused regression
coverage for both.

## Scope

- Fix `write_actual_outcomes()` so generator and other single-pass iterable
  inputs still write all expected `<case_id>.json` files after duplicate checks.
- Add a focused regression test for generator-backed actual outcome exports.
- Update eval fixture and taxonomy docs to reflect the CR-123 architecture:
  TriageCore may package/validate handoff evidence, while scoring remains
  external.
- Extend the CR-123 handoff documentation tests to catch drift back toward
  internal scoring language.
- Update backlog and changelog after focused validation passes.

## Non-Goals

- No evaluator execution from TriageCore.
- No scoring, pass/fail judgment, aggregate metrics, or score interpretation in
  TriageCore.
- No new actual outcome fields, fixture schema fields, bundle builder, manifest
  writer, or bundle validator.
- No model, backend, endpoint, routing, admission, identity, approval, worker,
  or ledger integration.

## Validation

- Focused: `python -m pytest -q tests/test_eval_outcome_contract.py tests/test_eval_handoff_contract.py tests/test_eval_fixture_cli.py tests/test_eval_fixture_validator.py` -> 34 passed
- Full suite: `python -m pytest -q` -> 937 passed, 2 skipped
