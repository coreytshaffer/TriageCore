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
| `schema_version` | The version of the ledger event schema (e.g., `0.2.0`). Old events may lack this field. |
| `role_taxonomy_version` | The version of the role taxonomy used (e.g., `2026-06-worker-council-v2`). Old events may lack this field. |
| `created_at` | Timestamp when the task entered the ledger. |
| `updated_at` | Timestamp of the most recent ledger event applied to the task record. |
| `title` | Human-readable task title. |
| `description` | Operator-safe task summary. `tc run` stores a fixed content-withheld marker rather than prompt text. |
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

## Context Budget Fields

These fields are produced by the advisory context budget planner before model
dispatch. They estimate what the task is about to send or preserve as context;
they do not replace exact backend token usage.

| Field | Meaning |
| --- | --- |
| `context_pack_path` | JSON artifact that records the prompt, included context, excluded context, token estimates, and rationale. |
| `context_strategy` | Planner version or strategy, currently `context_budget_planner_v1`. |
| `context_estimated_tokens` | Pre-dispatch context token estimate using the project estimator. |
| `context_budget_tokens` | Advisory token budget selected for the runner or benchmark category. |
| `context_budget_status` | `within_budget` or `over_budget`. |
| `context_required_items` | Count of context items classified as required. |
| `context_helpful_items` | Count of context items classified as helpful. |
| `context_optional_items` | Count of context items classified as optional. |
| `context_excluded_items` | Count of context items excluded from the initial pack. |

## Resource And Review Fields

| Field | Meaning |
| --- | --- |
| `energy_kwh_estimate` | Estimated or measured task energy use. |
| `emissions_gco2e_estimate` | Estimated operational carbon emissions. |
| `grid_intensity_gco2e_per_kwh` | Carbon intensity assumption or measured value. |
| `accepted` | Human accepted this output. |
| `review_decision` | Recorded review outcome: `accepted`, `accepted_with_minor_edits`, or `rejected`. |
| `task_outcome` | Whether the underlying task ended `resolved` or `unresolved`, as recorded or revised by review events. |
| `reviewer_notes` | Human-readable rationale recorded with the review decision. |
| `correction_summary` | Optional summary of corrections the reviewer applied or required. |
| `affected_files` | Files the review decision or outcome revision identified as affected. |
| `remaining_risk` | Optional reviewer note on risk left open after the decision. |
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

> **Note on Tool Support**: As of the current IDE build, the Antigravity engine does not export a machine-readable exact token usage log. Therefore, `manual_estimate` is formally accepted as the permanent fallback default for Antigravity-supervised workflows.


## Learning Linkage

Learning proposal files should reference ledger evidence by `task_id`. Accepted lessons should remain review records until a human intentionally applies them as config or prompt changes.

Recommended learning artifacts:

- `.triagecore/learning_proposals.jsonl`
- `.triagecore/learning_reviews.jsonl`
- future `config_suggestions/*.md` or TOML patch files

## Design Rule

Every new agentic capability should answer this question before merging:

> What evidence will this feature add to the ledger, and how will a human reviewer interpret it later?
