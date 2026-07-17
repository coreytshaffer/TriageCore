# CR-128 — Evaluation Handoff Integrity Validator

## Status

Implemented locally; pending review.

## Purpose

Add a deterministic, read-only validator for an existing CR-127 evaluation
handoff bundle. The validator checks the closed manifest contract, exact
inventory, declared byte hashes, fixture and actual contracts, and persistent
privacy invariants without scoring or repairing the bundle.

## Scope

- Add `triage_core/evaluation_handoff_validator.py`.
- Add `tc eval validate-handoff --bundle <bundle-root>`.
- Reject symlink/reparse traversal, unexpected inventory, unsafe manifest
  paths, schema drift, count drift, hash drift, contract drift, unknown cases,
  and privacy-invariant failures with stable closed reason codes.
- Reuse the fixture validator and CR-127 broad actual-outcome validation.
- Add focused pure-module, CLI, mutation, read-only, and contract-drift tests.

## Non-Goals

- No repair, normalization, report creation, or ledger write.
- No expected-vs-actual comparison, scoring, pass/fail judgment, or approval.
- No evaluator, model, backend, endpoint, or network invocation.
- No routing, admission, identity, approval, or worker integration.
- No authenticity, provenance, certification, safety, or correctness claim.

## Trust Boundary

A successful validation proves that current bundle bytes and inventory agree
with the bundled manifest and declared file contracts. SHA-256 detects drift
relative to that manifest; it does not authenticate who created the manifest
or establish provenance, approval, safety, or correctness.

## Validation

- Focused eval surface:
  `python -m pytest -q tests/test_evaluation_handoff_validator.py tests/test_evaluation_handoff_validator_cli.py tests/test_evaluation_handoff_bundle.py tests/test_evaluation_handoff_bundle_cli.py tests/test_eval_handoff_contract.py tests/test_eval_fixture_cli.py tests/test_eval_fixture_validator.py tests/test_eval_outcome_contract.py`
  -> 86 passed, 1 skipped (symlink creation unavailable).
- Full suite: `python -m pytest -q` -> 997 passed, 3 skipped.
- `git diff --check` -> clean.
