# CR-108: Quality-Gate-Aware Delta Interpretation

## Status

Implemented

## Scope

- Add a `quality_gate_effect` axis to strategy delta records, derived from the
  baseline and candidate `quality_gate.status` values with a closed
  vocabulary: `quality_not_evaluated`, `quality_passed`, `quality_failed`,
  `quality_mixed`, and `quality_unknown`.
- Carry `baseline_quality_gate_status` and `candidate_quality_gate_status` on
  the delta record so the effect is auditable from the record itself.
- Keep the existing cost interpretation labels intact: quality gates never
  rewrite the cost interpretation.
- Add a `Quality Effect` column to the text report and include the new fields
  in the JSON report.
- Bump delta and report schema versions to `v2`.
- Keep report output ASCII-only.

## Non-Goals

- No strategy recommendation, ranking, or "best strategy" selection.
- No quality scoring rubric.
- No combined cost-plus-quality labels (two independent axes only).
- No live model calls, telemetry adapters, or automatic routing.

## Description

CR-106 and CR-107 established token-based delta interpretation and the
read-only report command. This slice adds the quality axis conservatively:
the goal is not to pick the best strategy but to qualify token-based
interpretations using quality-gate status.

The two axes stay independent by design. A failed strategy can still be
token-saving — it is just not acceptable — so the delta record reports
`interpretation: token_saving` and `quality_gate_effect: quality_failed`
side by side rather than collapsing them into a combined judgment. A
regression test pins this boundary directly.

Effect derivation precedence: any failed gate dominates the pair, then fully
passed, then fully not evaluated, then partially evaluated pairs are mixed.
`quality_unknown` is a defensive fallback that is unreachable through
validated records.

## Acceptance Criteria

- [x] Delta records carry both gate statuses and a closed-vocabulary
  `quality_gate_effect`.
- [x] A token-saving candidate with a failed gate keeps its `token_saving`
  cost interpretation while reporting `quality_failed`.
- [x] The derivation matrix is tested for all status pairs, including the
  defensive fallback.
- [x] Invalid comparisons still report the quality fields.
- [x] Text and JSON reports include the quality axis; text output remains
  ASCII-only.

## Validation

- `python -m pytest tests/test_runtime_strategy_evidence.py tests/test_runtime_strategy_cli.py`
- `python -m py_compile triage_core/runtime_strategy_evidence.py`
- `python -m pytest`
- `tc doctor`
- `git diff --check`
