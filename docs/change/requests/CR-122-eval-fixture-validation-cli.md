# CR-122: Eval Fixture Validation CLI

## Status

Implemented (validator CLI only)

## Summary

Expose the CR-121 eval fixture validator through a narrow `tc eval`
subcommand so reviewers can validate an explicit safety-boundary fixture JSONL
file without scoring cases or executing any evaluation workflow.

## Scope

- Add `tc eval validate-fixtures --input <path>`.
- Reuse `triage_core.eval_fixture_validator.load_eval_fixture_jsonl`.
- Print a bounded success message with the number of cases checked.
- Fail closed with line-aware diagnostics for invalid fixtures.
- Fail closed with reason-coded missing/read failure handling.
- Add synthetic CLI tests only.
- Update backlog, changelog, and eval fixture docs after focused tests pass.

## Non-Goals

- No scoring or observed-behavior comparison.
- No new actual outcome contract fields.
- No model, completion, chat, embedding, backend, endpoint, or network calls.
- No routing, admission, ledger, identity, approval, or runtime integration.
- No adversarial tampering tests.
- No new fixture families or expansion of `safety_boundaries_v0.jsonl`.

## Validation

- Focused: `python -m pytest -q tests/test_eval_fixture_cli.py tests/test_eval_fixture_validator.py` -> 15 passed
- Focused eval surface: `python -m pytest -q tests/test_eval_fixture_cli.py tests/test_eval_fixture_validator.py tests/test_tc_cli.py tests/test_eval_review_cli.py` -> 37 passed
- Full suite: `python -m pytest -q` -> 931 passed, 2 skipped
