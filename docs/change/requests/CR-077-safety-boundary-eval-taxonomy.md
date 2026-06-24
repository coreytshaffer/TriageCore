# CR-077: Safety Boundary Eval Taxonomy and Fixture Schema

## Status
Implemented

## Scope

- Add `docs/research/eval_taxonomy.md`.
- Add `docs/research/eval_fixture_schema.md`.
- Add `tests/fixtures/evals/README.md`.
- Add `tests/fixtures/evals/safety_boundaries_v0.jsonl` with a small representative set of boundary cases.
- Update `docs/current_backlog.md`.
- Update `docs/change/change_log.md`.

## Non-Goals

- No `tc eval` CLI
- No live model dependencies
- No network calls
- No routing behavior changes
- No validator implementation
- No production safety certification claim

## Description

This slice defines the first benchmark surface for TriageCore's safety-boundary research track. It answers what an eval case is, which boundary families the first suite covers, what deterministic pass/fail/block vocabulary should mean, and what fixture structure later validator and CLI work should consume. The included JSONL file is intentionally toy-scale and inert so the repo gains a concrete evaluation contract without smuggling in runtime behavior.

## Acceptance Criteria

- [x] `docs/research/eval_taxonomy.md` defines eval-case shape, boundary families, deterministic outcome vocabulary, and out-of-scope limits.
- [x] `docs/research/eval_fixture_schema.md` defines the v0 JSONL fixture contract and required fields.
- [x] `tests/fixtures/evals/README.md` explains fixture intent and constraints.
- [x] `tests/fixtures/evals/safety_boundaries_v0.jsonl` includes representative privacy, routing, identity, provenance, audit, and human-approval cases.
- [x] Backlog and change log reflect this slice and preserve the follow-on sequence of schema validation before evaluator CLI work.
- [x] No runtime, CLI, routing, or network behavior changes were introduced.
- [x] `git diff --check` is clean.
- [x] Tests may be skipped with an explicit note because this slice changes docs and inert fixture data only.
