# Benchmarks

This folder contains stable benchmark tasks for evaluating local models and backend configurations. Each task is a small, repeatable experiment that can be logged to the TriageCore ledger.

## Format

Benchmark tasks are stored as JSON Lines in `tasks.jsonl`. Each line is one task object.

Required fields:

- `task_id`: Stable identifier for citation and comparison.
- `category`: Task family, such as `python_generation`, `log_summary`, or `safety_handoff`.
- `prompt`: Instruction sent to the model.
- `data`: Input context sent with the prompt.
- `validator`: Optional validator name. Use `python_syntax` or `none`.
- `expected_status`: Expected result class, usually `success` or `handoff_required`.

Optional fields:

- `notes`: Short explanation of what the task measures.
- `target_files`: File paths relevant to the task, if any.

## Running

List benchmark tasks without contacting a backend:

```bash
triagecore benchmark --list-only
```

Run the benchmark set against the default Ollama preset:

```bash
triagecore benchmark --model qwen2.5-coder:7b
```

Run against a custom OpenAI-compatible endpoint:

```bash
triagecore benchmark --backend-type custom --base-url http://localhost:1234/v1 --model local-model
```

Results are appended to `.triagecore/ledger.jsonl` as local experimental observations.

Generate a markdown summary from the ledger:

```bash
triagecore benchmark-report
triagecore benchmark-report --output reports/benchmark-report.md
```
