# CR-094: Token Efficiency Evidence

## Status

Implemented

## Scope

- Add a deterministic token-efficiency evidence record.
- Reuse the project's simple character-count token estimator for measurement-only evidence.
- Add two deterministic local smoke fixtures for baseline and compact context.
- Add a `tc tokens smoke-test` CLI path that prints a bounded reviewer summary.
- Add focused tests and a short operator document.

## Numbering Note

This checkout already contains CR-095 and higher-numbered slices. CR-094 remained unused, so this implementation uses that open number instead of introducing a new out-of-sequence identifier.

## Non-Goals

- No live LLM calls.
- No automatic routing changes.
- No quality-improvement claims.
- No cost-dollar claims.
- No energy or emissions claims from token-only estimates.
- No dashboards, model comparisons, or orchestration policy changes.

## Acceptance Criteria

- [x] `triage_core/token_efficiency.py` exists.
- [x] The evidence record uses estimated tokens, not actual-token claims.
- [x] The estimator stays deterministic and dependency-light.
- [x] The smoke fixture proves baseline > candidate and computes savings correctly.
- [x] `tc tokens smoke-test` prints a bounded success summary.
- [x] Focused tests cover the record builder and CLI smoke path.
- [x] Reviewer-facing docs explain the measurement-only boundary.

## Validation

- `python -m pytest tests/test_token_efficiency.py tests/test_tokens_cli.py`
- `python -m pytest`
- `tc doctor`
- `git diff --check`
- `git status --short`
