# CR-121: Eval Fixture Validator

## Status

Implemented (validator-only)

## Summary

Add a pure, deterministic JSONL validator for the CR-077 safety-boundary eval
fixture contract. The validator checks fixture integrity before any evaluator
CLI or scoring surface exists, preserving the boundary between valid input
shape and evaluation execution.

## Scope

- Add `triage_core/eval_fixture_validator.py`.
- Validate one JSON object per JSONL line with line-aware diagnostics.
- Fail closed on malformed JSON, non-object lines, empty lines, missing
  required fields, empty `case_id`, duplicate `case_id`, and closed-vocabulary
  violations.
- Validate the v0 nested contract shape for `task_packet`,
  `policy_expectation`, `simulated_behavior`, and `expected_audit_outcome`.
- Add synthetic unit tests only.
- Update backlog, changelog, and eval research docs after focused validator
  tests pass.

## Non-Goals

- No `tc eval` CLI.
- No fixture scoring or observed-behavior comparison.
- No model, completion, chat, embedding, backend, endpoint, or network calls.
- No routing, admission, ledger, identity, approval, or runtime integration.
- No adversarial tampering tests.
- No new fixture families or expansion of `safety_boundaries_v0.jsonl`.

## Validation

- Focused: `python -m pytest -q tests/test_eval_fixture_validator.py` -> 12 passed
- Full suite: `python -m pytest -q` -> 928 passed, 2 skipped
