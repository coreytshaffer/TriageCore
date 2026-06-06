# TriageCore Assignment Outcome Schema

## Purpose

This schema defines the compact outcome record TriageCore should collect when it studies work from source projects such as SafeTask AI.

The record is meant to improve local LLM assignment decisions. It is not an approval record, compliance finding, or SafeTask AI runtime object.

## Design Rule

Each outcome record should answer:

1. What task was assigned?
2. Which local model and tool combination handled it?
3. What happened after review or verification?
4. Was the assignment efficient, wasteful, underpowered, or appropriately scoped?

## Record Shape

| Field | Required | Description |
| --- | --- | --- |
| `task_id` | yes | Stable ID for the observed assignment. |
| `preflight_id` | no | Preflight decision that selected the task class, context, checks, and local combo. |
| `context_pack_id` | no | Context pack used for the assignment. |
| `observed_at` | yes | Date the outcome was recorded. |
| `source_project` | yes | Project that produced the example, such as `SafeTask AI`. |
| `source_artifacts` | yes | Files, docs, routes, or checks that produced the evidence. |
| `task_class` | yes | Work type, such as `documentation_synthesis`, `ui_api_slice`, `smoke_check_design`, or `configuration_review`. |
| `complexity` | yes | `low`, `medium`, or `high`. |
| `sensitivity` | yes | `low`, `medium`, `high`, or `human_review_required`. |
| `assignment_goal` | yes | Short statement of the intended work. |
| `model_combo` | yes | Local LLM roles or model classes used. Use placeholders when the exact model is not yet tracked. |
| `tool_path` | yes | Deterministic tools or checks used with the model output. |
| `result_status` | yes | `accepted`, `accepted_with_minor_edits`, `needs_rework`, `failed`, or `deferred`. |
| `verification` | yes | Checks used to validate the result. |
| `correction_burden` | yes | `none`, `low`, `medium`, or `high`. |
| `waste_signal` | yes | `none`, `overpowered`, `underpowered`, `repeated_retry`, `missing_context`, `tool_should_handle`, or `scope_ambiguous`. |
| `confidence_after_review` | yes | `low`, `medium`, or `high`. |
| `lesson` | yes | One-sentence routing or assignment lesson. |
| `next_assignment_rule` | no | Suggested future routing rule for similar tasks. |
| `human_review_required` | yes | Whether TriageCore should require human review before trusting this task class. |
| `notes` | no | Short caveats or boundary notes. |

## JSONL Example

```json
{"task_id":"safetask-doc-source-registry-2026-06-05","preflight_id":"preflight-safetask-doc-source-registry-2026-06-05","context_pack_id":"ctx-safetask-doc-source-registry-2026-06-05","observed_at":"2026-06-05","source_project":"SafeTask AI","source_artifacts":["docs/compliance/source-registry.md","docs/backlog-surveillance-compliance-platform.md"],"task_class":"documentation_synthesis","complexity":"medium","sensitivity":"medium","assignment_goal":"Summarize source-registry examples into a reusable learning record.","model_combo":["local-drafter-placeholder","deterministic-diff-check"],"tool_path":["repo_search","file_edit","diff_check"],"result_status":"accepted_with_minor_edits","verification":["git diff --check"],"correction_burden":"low","waste_signal":"none","confidence_after_review":"high","lesson":"Scoped documentation synthesis can use a medium local drafter plus deterministic diff checks.","next_assignment_rule":"Route similar scoped docs work to a medium local drafter with repo search and diff checks.","human_review_required":true,"notes":"SafeTask remains the source project; TriageCore owns lesson synthesis."}
```

## Early Task Classes

| Task class | Description | Likely local combo |
| --- | --- | --- |
| `repo_search_summary` | Find and summarize project evidence. | small summarizer plus deterministic search |
| `documentation_synthesis` | Turn repo evidence into scoped docs. | medium drafter plus diff check |
| `ui_api_slice` | Small UI/API integration slice. | stronger reasoning model plus syntax checks |
| `smoke_check_design` | Create practical verification checklists. | medium drafter plus route/code scan |
| `configuration_review` | Review dependencies, config, and deployment assumptions. | medium reasoning model plus file inspection |
| `code_patch_planning` | Plan a code change before implementation. | medium reasoning model plus static inspection |

## Waste Signals

| Signal | Meaning | TriageCore response |
| --- | --- | --- |
| `none` | The assignment fit the task. | Keep the current combo candidate. |
| `overpowered` | A larger/slower model was unnecessary. | Try a smaller combo next time. |
| `underpowered` | The model could not handle the task reliably. | Escalate or add deterministic checks. |
| `repeated_retry` | Multiple attempts failed for the same reason. | Stop and inspect the exact failure. |
| `missing_context` | The model lacked source evidence. | Run repo search or ask for context first. |
| `tool_should_handle` | Deterministic tooling would be better. | Route to parser, validator, or shell check first. |
| `scope_ambiguous` | The task needed clarification. | Ask one clarifying question before assignment. |

## Preflight Linkage

When `preflight_id` and `context_pack_id` are present, TriageCore should compare the expected assignment plan to the final outcome:

- Did the predicted task class match the real task?
- Did the selected context pack prevent missing-context waste?
- Did required checks run?
- Did the selected local combo perform as expected?
- Should the task class move toward a smaller combo, stronger combo, or human review?
