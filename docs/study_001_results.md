# Study 001 Results

## Run Summary

Formal Study 001 execution began on 2026-06-04 after adding `study_id` support to the benchmark ledger and report pipeline.

Backend configuration:

- backend: `ollama`
- model: `qwen2.5-coder:7b-triagecore`
- study label: `study_001`
- fixture file: `benchmarks/tasks.jsonl`
- generated local report: `reports/study_001_benchmark_report.md`

## Outcomes

| Metric | Value |
| --- | ---: |
| Formal benchmark runs | 5 |
| Success rate | 80.0% |
| Handoff rate | 20.0% |
| Mismatches | 0 |
| Validator failures | 0 |
| Average seconds | 2.79 |
| Total tokens | 527 |
| Average tokens per second | 41.76 |

The safety handoff fixture produced the expected `handoff_required` outcome. The four non-destructive benchmark fixtures produced the expected `success` outcome.

## Learning Proposals

Running `triagecore propose-lessons --study-id study_001` produced no learning proposals because the formal Study 001 records had no mismatches, unexpected handoffs, or validator failures.

Earlier exploratory benchmark records produced pending proposal candidates, but those records are intentionally excluded from the formal Study 001 report because they do not carry the `study_001` label.

## Validator Hardening Rerun

After the initial baseline, Study 001 validation was strengthened for the log-summary and structured-extraction fixtures:

- `log_summary_markdown_v1` now checks that warning and error content are present and INFO-only content is excluded.
- `json_extraction_small_v1` now checks exact environmental JSON fields and values.

The stronger validators surfaced one useful mismatch: `json_extraction_small_v1` triggered `handoff_required` instead of the expected `success`. This should be treated as evidence for prompt/model/validator review, not as a silent failure.

The rerun also exposed the next evidence-design decision: `study_id` separates formal study records from exploratory history, but repeated runs inside the same study still aggregate together. A future slice should add a `run_id` or `trial_id` before comparing multiple prompt, model, or validator versions inside Study 001.

## Interpretation

This is a successful first operational baseline, not a broad claim about model quality. The current benchmark set is intentionally small and should be expanded before using Study 001 as strong evidence in the paper.
