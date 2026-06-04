# Evidence Schema

TriageCore should treat every agent/model attempt as one evidence record. This document defines the shared fields that benchmark runs, worker-council dispatch, UI local drafts, handoff packets, and future study exports should converge on.

## Purpose

The schema supports two project goals:

- operate a local-first agentic control plane
- collect scientific evidence about model behavior, token balance, resource use, and human review outcomes

## Core Fields

| Field | Meaning |
| --- | --- |
| `task_id` | Unique run identifier for this task attempt. |
| `created_at` | Timestamp when the task entered the ledger. |
| `updated_at` | Timestamp of the most recent ledger event applied to the task record. |
| `title` | Human-readable task title. |
| `description` | Prompt or task summary. |
| `target_files` | Files or artifacts in scope. |
| `runner` | Execution path, such as `local_benchmark`, `local_llm`, `council`, `codex`, or `antigravity`. |
| `status` | Current state: `pending`, `local_draft_generated`, `handoff_generated`, `reviewed`, or `blocked`. |
| `study_id` | Optional study label, such as `study_001`, used to separate formal experiments from exploratory runs. |
| `run_id` | Optional run or trial label, such as `trial_001`, used to separate repeated attempts inside one study. |

## Routing And Safety Fields

| Field | Meaning |
| --- | --- |
| `risk_level` | Router risk result: `low`, `medium`, or `high`. |
| `permission_profile` | Recommended execution profile. |
| `handoff_reason` | Why local execution was bypassed, stopped, or escalated. |
| `human_review_required` | Whether the task requires explicit review before adoption. |

## Model Evaluation Fields

| Field | Meaning |
| --- | --- |
| `backend_name` | Backend used, such as `ollama`, `vllm`, `llama.cpp`, or `custom`. |
| `model` | Model identifier used for the attempt. |
| `benchmark_task_id` | Stable benchmark fixture ID, when applicable. |
| `benchmark_category` | Benchmark task family, such as `python_repair` or `log_summary`. |
| `expected_status` | Expected benchmark outcome. |
| `observed_status` | Actual benchmark outcome. |
| `timeout_seconds` | Local execution timeout budget. |
| `elapsed_seconds` | Wall-clock task duration. |
| `input_tokens` | Prompt/input tokens reported by backend, when available. |
| `output_tokens` | Completion/output tokens reported by backend, when available. |
| `total_tokens` | Total tokens reported or computed. |
| `tokens_per_second` | Throughput estimate when token counts are available. |
| `validator_passed` | Validator result: `true`, `false`, or `null` when no validator was used. |

## Resource And Review Fields

| Field | Meaning |
| --- | --- |
| `energy_kwh_estimate` | Estimated or measured task energy use. |
| `emissions_gco2e_estimate` | Estimated operational carbon emissions. |
| `grid_intensity_gco2e_per_kwh` | Carbon intensity assumption or measured value. |
| `accepted` | Human accepted this output. |
| `human_review_minutes` | Time spent reviewing, when captured. |
| `review_workload` | Optional reviewer workload label: `not_recorded`, `low`, `medium`, or `high`. |
| `artifact_paths` | Generated handoff packets, reports, or output files. |

## Supervisor Review Fields

| Field | Meaning |
| --- | --- |
| `supervisor_tool` | Supervisory tool or lane, such as `codex`, `antigravity`, `gemini`, or `human`. |
| `supervisor_model` | Supervisor model identifier, when known. |
| `supervisor_profile` | Supervisor mode or profile, such as `high`, `review`, or `supervisor`. |
| `supervisor_decision` | Review outcome: `accepted`, `rejected`, `needs_revision`, or `escalated`. |
| `supervisor_notes` | Human-readable rationale for the supervisory decision. |
| `supervisor_artifact_path` | Packet, transcript, task bundle, or output artifact linked to the review. |
| `supervisor_input_tokens_est` | Estimated supervisor input tokens, if exact usage is unavailable. |
| `supervisor_output_tokens_est` | Estimated supervisor output tokens, if exact usage is unavailable. |
| `supervisor_token_source` | Source label for supervisor token values: `manual_estimate`, `imported_estimate`, or `imported_exact`. |

## Learning Linkage

Learning proposal files should reference ledger evidence by `task_id`. Accepted lessons should remain review records until a human intentionally applies them as config or prompt changes.

Recommended learning artifacts:

- `.triagecore/learning_proposals.jsonl`
- `.triagecore/learning_reviews.jsonl`
- future `config_suggestions/*.md` or TOML patch files

## Design Rule

Every new agentic capability should answer this question before merging:

> What evidence will this feature add to the ledger, and how will a human reviewer interpret it later?
