# Token Efficiency Evidence

## Purpose

This document defines the current measurement-only token-efficiency evidence path.

The goal is to show that TriageCore can record structured evidence that one context strategy used fewer **estimated tokens** than a baseline for the same task, without claiming quality improvement yet.

## Command

Run the deterministic smoke path from the repository root:

```powershell
tc tokens smoke-test
```

Expected output:

```text
Token efficiency smoke test passed
baseline_estimated_total=4800
candidate_estimated_total=1800
estimated_tokens_saved=3000
estimated_percent_saved=62.5
```

## Record Shape

The smoke command builds a metadata-only record with this structure:

```json
{
  "kind": "token_efficiency",
  "task_id": "fixture-doc-summary-001",
  "baseline": {
    "strategy": "raw_context",
    "estimated_input_tokens": 4200,
    "estimated_output_tokens": 600,
    "estimated_total_tokens": 4800
  },
  "candidate": {
    "strategy": "compact_context",
    "estimated_input_tokens": 1300,
    "estimated_output_tokens": 500,
    "estimated_total_tokens": 1800
  },
  "savings": {
    "estimated_tokens_saved": 3000,
    "estimated_percent_saved": 62.5
  },
  "quality_gate": {
    "status": "not_evaluated",
    "reason": "measurement-only smoke fixture"
  }
}
```

## Estimator

The current estimator is deliberately simple and deterministic:

```text
estimated_tokens = ceil(character_count / 4)
```

This is proxy evidence only. It is not tokenizer-specific telemetry.

## Fixture Boundary

The smoke path uses two deterministic local fixture files:

- [baseline_context.txt](../examples/token_efficiency/baseline_context.txt)
- [compact_context.txt](../examples/token_efficiency/compact_context.txt)

The command compares their estimated token loads and prints a bounded summary.

## Non-Claims

- No live model call is made.
- No routing behavior changes.
- No quality improvement is claimed.
- No cost, energy, or emissions claim is made from this token-only record.
- No raw task content is written to persistent artifacts by this smoke path.

## Related Docs

- [runtime-efficiency-ledger.md](runtime-efficiency-ledger.md)
- [controlled-runtime-experiments.md](controlled-runtime-experiments.md)
- [experiment-observability-traces.md](experiment-observability-traces.md)
