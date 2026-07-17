# CR-127 — Evaluation Handoff Bundle Builder

## Status

Implemented

## Purpose

Add a deterministic file-only builder that packages an explicit validated
fixture and explicit actual-outcome directory for an external evaluator while
preserving the CR-123 boundary that TriageCore does not score or interpret
evaluation results.

## Scope

- Add `triage_core/evaluation_handoff_bundle.py`.
- Add `tc eval build-handoff --fixture <jsonl> --actuals-dir <dir> --out-dir <new-dir>`.
- Emit the fixed fixture, actuals, and manifest layout documented by
  `evaluation_handoff_manifest.v0`.
- Copy source evidence byte-for-byte and record deterministic SHA-256 hashes.
- Validate all inputs before staging, enforce persistent privacy invariants,
  and publish with a sibling atomic rename.
- Add focused pure-module and CLI coverage.

## Non-Goals

- No scoring, pass/fail judgment, score interpretation, or approval claim.
- No evaluator, model, backend, endpoint, or network invocation.
- No automatic file discovery, defaults, overwrite, or `--force`.
- No routing, admission, ledger, approval, or worker integration.
- No new fixture, decision, or boundary-family vocabulary.
- No validation of an already-created bundle; integrity validation is a
  separate future CR.

## Validation

- Focused:
  `python -m pytest -q tests/test_evaluation_handoff_bundle.py tests/test_evaluation_handoff_bundle_cli.py tests/test_eval_handoff_contract.py tests/test_eval_outcome_contract.py tests/test_eval_fixture_validator.py tests/test_eval_fixture_cli.py`
  -> 60 passed
- Full suite: `python -m pytest -q` -> 971 passed, 2 skipped
- `git diff --check`
