# CR-107: Runtime Strategy Delta Report Command

## Status

Implemented

Pushed and CI verified: `origin/main` at `7a5f58c`, GitHub Actions run `28686645590` passed on Python 3.10, 3.11, and 3.12 (Node 20 deprecation annotations only; no failures). Reviewers can now run `tc runtime-strategy report` locally to see the fixture-derived deltas — `small_first_compact` saving 51.5% with one added handoff, `small_only` saving 64.2%, and the `over_orchestrated` negative control costing 37.3% more than the `heavy_only` baseline — in one deterministic, read-only command.

## Scope

- Add a read-only `tc runtime-strategy report` command that renders the
  existing fixture-derived strategy deltas against the `heavy_only` baseline.
- Include baseline strategy, task id, per-candidate token/percent/model-call/
  handoff deltas, interpretation labels, quality-gate status, and the quality
  non-claim note in the text output.
- Add a `--json` flag emitting the same report as a deterministic JSON object.
- Keep output ASCII-only so the report renders on default Windows consoles.
- Add focused CLI tests covering text content, JSON parity with the computed
  deltas, determinism, ASCII-safety, and read-only behavior.
- Update operator documentation, changelog, and backlog.

## Non-Goals

- No live Ollama or LM Studio calls.
- No model telemetry adapters.
- No routing decisions or strategy recommendation engine.
- No quality scoring.
- No saved report artifacts or dashboards.
- No ledger, identity, or review-state reads or writes.

## Description

The runtime-strategy evidence lane is CI-green on `origin/main` at `62b95e7`,
covering CR-104 evidence records, CR-105 comparison fixtures, and CR-106
strategy delta calculation. The fixture deltas show `small_first_compact`
saving 2470 estimated tokens versus `heavy_only`, `small_only` saving 3080,
and the `over_orchestrated` negative control adding 1790 — proving that
additional orchestration can create measurable overhead.

This slice exposes those deltas through a reviewer/operator-facing CLI command
so the measurable story is runnable locally in one command instead of living
only in tests. It is a natural future attachment point for real run records,
model telemetry, and quality-gate outcomes, but this slice stays read-only and
deterministic over the existing fixtures.

## Acceptance Criteria

- [x] `tc runtime-strategy report` prints the baseline, all three candidate
  deltas, interpretation labels, quality-gate status, and the quality
  non-claim note.
- [x] `tc runtime-strategy report --json` output matches the computed fixture
  deltas exactly.
- [x] The report is deterministic across invocations.
- [x] The text output is ASCII-only and renders on cp1252 Windows consoles.
- [x] The command performs no filesystem writes and no model calls.

## Validation

- `python -m pytest tests/test_runtime_strategy_evidence.py tests/test_runtime_strategy_cli.py`
- `python -m py_compile triage_core/runtime_strategy_evidence.py`
- `python -m pytest`
- `tc doctor`
- `git diff --check`
