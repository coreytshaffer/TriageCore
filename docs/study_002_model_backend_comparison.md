# Study 002: Model And Backend Comparison

## Purpose

Study 002 compares local model/backend pairs using the same benchmark fixture set and the same evidence schema. The goal is not to crown a universal best model. The goal is to learn which local configurations are reliable, efficient, and reviewable on this machine for TriageCore's current task mix.

## Research Question

Which local backend/model pairs provide the best balance of benchmark success, expected safety handoff behavior, validator pass rate, token efficiency, elapsed time, and human review burden?

## Hypothesis

Different backend/model pairs will trade off speed, validator reliability, and handoff behavior. A configuration should only be preferred when it improves accepted benchmark outcomes without increasing unexpected handoffs, validator failures, or human review burden.

## Benchmark Set

Use the stable Study 001 fixture file unless a later benchmark-expansion story changes it:

```powershell
benchmarks\tasks.jsonl
```

Required fixture IDs:

- `python_generation_small_v1`
- `python_repair_syntax_v1`
- `log_summary_markdown_v1`
- `json_extraction_small_v1`
- `safety_handoff_destructive_v1`

## Candidate Matrix

Start with configurations that are already available locally.

| Backend type | Base URL | Model | Run ID example |
| --- | --- | --- | --- |
| `ollama` | default | `qwen2.5-coder:7b-triagecore` | `ollama_qwen25_coder_7b_trial_001` |
| `custom` | `http://localhost:1234/v1` | LM Studio loaded model name | `lmstudio_loaded_model_trial_001` |
| `ollama` | default | second installed code model, if available | `ollama_second_model_trial_001` |

Do not compare a backend/model pair unless the exact model identifier is recorded in the command and report.

## Procedure

1. List benchmark fixtures without contacting a backend:

   ```powershell
   triagecore benchmark --list-only --study-id study_002
   ```

2. Run one backend/model pair with a unique `run_id`:

   ```powershell
   triagecore benchmark --study-id study_002 --run-id ollama_qwen25_coder_7b_trial_001 --backend-type ollama --model qwen2.5-coder:7b-triagecore
   ```

3. Run LM Studio through the OpenAI-compatible custom endpoint when a model is loaded:

   ```powershell
   triagecore benchmark --study-id study_002 --run-id lmstudio_loaded_model_trial_001 --backend-type custom --base-url http://localhost:1234/v1 --model <loaded-model-name>
   ```

4. Generate a combined comparison report:

   ```powershell
   triagecore benchmark-report --study-id study_002 --output reports\study_002_model_backend_comparison.md
   ```

5. Generate run-specific reports when investigating a failure:

   ```powershell
   triagecore benchmark-report --study-id study_002 --run-id ollama_qwen25_coder_7b_trial_001 --output reports\study_002_ollama_qwen25_coder_7b_trial_001.md
   ```

6. Generate learning proposals only after reviewing the comparison report:

   ```powershell
   triagecore propose-lessons --study-id study_002
   ```

## Metrics

Primary comparison metrics:

- success rate
- expected versus observed mismatch count
- unexpected handoff rate
- validator failure count
- elapsed seconds
- total tokens
- tokens per second

Secondary evidence:

- backend grouping from the `By Backend` report section
- backend/model grouping from the `By Model` report section
- human review minutes, when review is performed
- optional `review_workload`, when review is performed

## Decision Rules

- Prefer configurations with zero unexpected safety failures before optimizing for speed.
- Treat expected destructive-task handoff as correct behavior, not as a model failure.
- Do not apply learning proposals until a human review decision is recorded.
- Do not compare runs with different benchmark fixture sets.
- Do not claim broad model quality from this small benchmark set.

## Completion Criteria

Study 002 is ready for interpretation when:

- at least two backend/model pairs have complete runs under `study_002`
- each run has a unique `run_id`
- a combined `study_002` report exists
- unexpected mismatches, handoffs, and validator failures are reviewed
- any learning proposals are accepted or rejected by a human
