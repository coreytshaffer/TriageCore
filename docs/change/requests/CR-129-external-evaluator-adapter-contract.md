# CR-129 — External Evaluator Adapter Contract

## Status

Implemented locally; pending review.

## Purpose

Define the contract and stop conditions required before a future TriageCore
wrapper may launch a version-pinned external evaluator. This slice is
documentation and drift enforcement only.

## Scope

- Add `external_evaluator_adapter_contract.v0`.
- Reserve a closed-profile future CLI shape without implementing it.
- Define required profile identity, executable/version, argv mapping, cwd,
  result ownership, exit, output, network, environment, timeout, and
  process-tree termination requirements.
- Require CR-128 bundle validation before any future launch.
- Add focused drift tests that keep CR-129 contract-only.

## Non-Goals

- No CLI, subprocess, executable selection, argv forwarding, or process launch.
- No result parsing/import/rendering/persistence or evaluator output creation.
- No scoring, evaluator interpretation, ledger write, network/model/backend
  call, routing, admission, approval, identity, or worker integration.
- No external evaluator profile; that authoritative versioned artifact is a
  prerequisite for a separately approved code-bearing CR.

## Validation

- Focused:
  `python -m pytest -q tests/test_external_evaluator_adapter_contract.py tests/test_eval_handoff_contract.py`
  -> 10 passed.
- `git diff --check` -> clean.
