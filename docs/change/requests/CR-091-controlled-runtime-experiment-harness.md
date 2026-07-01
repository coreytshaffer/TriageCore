# CR-091: Controlled Runtime Experiment Harness

## Status

Implemented

## Scope

- Add deterministic agent group profiles for controlled runtime experiments.
- Add experiment plans with baseline group, candidate groups, repetitions,
  quality gate, measurement config, allowed runtime backends, and token budget.
- Add synthetic result records that embed a runtime efficiency record and enforce
  claim validity.
- Add JSON schemas for experiment plans and results.
- Add focused tests for valid plans, invalid groups, turn limits, quality-gate
  failures, token-efficiency claims, energy-claim rejection, and deterministic
  JSON output.
- Add operator documentation for comparing model/runtime/agent configurations.

## Numbering Note

The pasted request suggested CR-089, but this checkout already contains CR-089
and this branch already uses CR-090 for the runtime efficiency ledger. This
follow-on slice uses CR-091 to avoid reusing an existing change-request number.

## Non-Goals

- No default runtime behavior changes.
- No live model calls.
- No live benchmark execution.
- No autonomous orchestration.
- No migration from Ollama to llama.cpp.
- No crypto token, custody, payment, wallet, or API-spend behavior.

## Acceptance Criteria

- [x] `triage_core/runtime_experiments.py` exists.
- [x] `triage_core/agent_group_profiles.py` exists.
- [x] `schemas/runtime_experiment_plan.schema.json` exists.
- [x] `schemas/runtime_experiment_result.schema.json` exists.
- [x] Experiment plans reject missing baseline groups.
- [x] Experiment validation rejects missing candidate groups.
- [x] Agent group profiles reject empty groups and groups exceeding turn limits.
- [x] Results reject efficiency benefit claims when quality gates fail.
- [x] Energy-saving claims require an energy-capable measurement tier and
  measured energy values.
- [x] Token-proxy experiments can omit measured energy fields.

## Validation

- `python -m pytest tests/test_agent_group_profiles.py tests/test_runtime_experiments.py tests/test_runtime_backend_profile.py tests/test_runtime_efficiency.py -q`
- `git diff --check`
