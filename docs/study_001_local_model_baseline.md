# Study 001: Local Model Baseline

## Purpose

This study establishes the first repeatable baseline for TriageCore as a local-first agent operations workbench and scientific data gathering tool.

## Research Question

Can TriageCore route and evaluate small agentic coding and parsing tasks through local models while preserving safety, auditability, token-efficiency, and human review?

## Hypothesis

Small local code models should complete simple generation, syntax repair, log summary, and structured extraction tasks with lower cost and acceptable validation outcomes, while destructive or secret-related tasks should trigger handoff before local execution.

## Benchmark Set

Use the stable fixture file:

```bash
benchmarks/tasks.jsonl
```

Initial benchmark tasks:

- `python_generation_small_v1`
- `python_repair_syntax_v1`
- `log_summary_markdown_v1` with deterministic warning/error markdown validation
- `json_extraction_small_v1` with deterministic environmental JSON station ID and field/value validation
- `safety_handoff_destructive_v1`

## Candidate Models And Backends

Record exact model identifiers and backend versions when available.

Initial candidates:

- Ollama with `qwen2.5-coder:7b-triagecore`
- Ollama with a smaller code model, if available
- LM Studio custom endpoint with a local model, if available
- vLLM endpoint, if available

## Procedure

1. Confirm `triagecore.toml` contains the intended backend, model, timeout, ledger, and benchmark paths.
2. Run the benchmark list without contacting a backend:

   ```bash
   triagecore benchmark --list-only
   ```

3. Run the benchmark set for one backend/model pair:

   ```bash
   triagecore benchmark --study-id study_001 --run-id trial_001
   ```

4. Generate a markdown report:

   ```bash
   triagecore benchmark-report --study-id study_001 --run-id trial_001 --output reports/study_001_benchmark_report.md
   ```

5. Generate pending learning proposals:

   ```bash
   triagecore propose-lessons --study-id study_001 --run-id trial_001
   ```

6. Review any learning proposals manually:

   ```bash
   triagecore review-lesson <proposal_id> --decision accepted --notes "Reason for accepting."
   ```

7. Repeat for additional backend/model pairs, changing only the configured backend/model or explicit CLI flags.

## Metrics

Primary metrics:

- benchmark success rate
- handoff rate
- expected versus observed mismatch count
- validator failure count
- elapsed seconds
- input tokens
- output tokens
- total tokens
- tokens per second

Resource metrics:

- estimated kWh
- estimated gCO2e
- estimated water use, when available
- human review minutes, when available

Human-review metrics:

- accepted outputs
- rejected outputs
- pending learning proposals
- accepted learning proposals
- rejected learning proposals

## Evidence Artifacts

Expected artifacts:

- `.triagecore/ledger.jsonl`
- `.triagecore/learning_proposals.jsonl`
- `.triagecore/learning_reviews.jsonl`
- `reports/study_001_benchmark_report.md`

Use `study_001` as the ledger `study_id` for formal Study 001 records. Use a unique `run_id`, such as `trial_001`, for each formal attempt. Exploratory benchmark records without those labels should not be included in the final Study 001 report.

Generated reports should be treated as local experimental observations, not universal claims about model performance.

## Reproducibility Notes

Record:

- operating system
- Python version
- backend name and version
- model identifier
- quantization, if known
- CPU/GPU hardware
- power measurement method or heuristic profile
- configured timeout
- benchmark fixture version

## Limitations

- Initial task count is small.
- Token reporting may vary by backend.
- Energy and carbon values may be heuristic if live measurement is unavailable.
- Human review decisions are subjective but should be documented.
- Results are local to this machine and should not be generalized without additional runs.

## Success Criteria

This study is complete when:

- each benchmark task has at least one recorded run
- a benchmark report is generated
- any mismatches or handoffs are documented
- at least one learning proposal review decision is recorded when proposals exist
- findings are summarized in a future paper draft or study note
