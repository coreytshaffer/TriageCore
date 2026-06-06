# TriageCore Assignment Preflight Schema

## Purpose

This schema defines the record TriageCore should create before assigning a task to a local LLM and tool combination.

Preflight records prevent waste before it starts. They classify the task, identify required context, choose a candidate local combo, and define stop conditions before generation begins.

## Design Rule

Every non-trivial local LLM assignment should have a preflight decision.

The preflight decision should be small enough to fill quickly, but specific enough to answer:

1. What task class is this?
2. What context is required before a model call?
3. Which local combo is the smallest reliable starting point?
4. What checks must pass?
5. When should TriageCore stop, downgrade, escalate, or ask Corey?

## Record Shape

| Field | Required | Description |
| --- | --- | --- |
| `preflight_id` | yes | Stable ID for the preflight decision. |
| `created_at` | yes | Date the preflight was recorded. |
| `source_project` | yes | Project providing the task example, such as `SafeTask AI`. |
| `assignment_goal` | yes | Short statement of the intended work. |
| `task_class` | yes | Predicted task class. |
| `complexity` | yes | `low`, `medium`, or `high`. |
| `sensitivity` | yes | `low`, `medium`, `high`, or `human_review_required`. |
| `required_context` | yes | Context that must be collected before model generation. |
| `context_pack_type` | yes | Context pack template to use. |
| `candidate_combo` | yes | Local model/tool combo selected before work starts. |
| `required_checks` | yes | Checks that must run before the outcome is trusted. |
| `stop_conditions` | yes | Conditions that should stop retries or trigger escalation. |
| `downgrade_candidate` | no | Smaller combo to try if the work proves easy. |
| `escalation_candidate` | no | Stronger combo to use if the first combo is underpowered. |
| `human_review_required` | yes | Whether Corey or another human must review the result. |
| `confidence_before_assignment` | yes | `low`, `medium`, or `high`. |
| `rationale` | yes | Brief reason for the selected combo. |

## JSONL Example

```json
{"preflight_id":"preflight-safetask-source-registry-display-2026-06-05","created_at":"2026-06-05","source_project":"SafeTask AI","assignment_goal":"Expose documented compliance source records in a read-only Admin Governance panel without adding registry writes.","task_class":"ui_api_slice","complexity":"medium","sensitivity":"medium","required_context":["source registry contract","Admin Governance UI markup","Flask compliance routes","existing JavaScript loaders"],"context_pack_type":"code_slice_pack","candidate_combo":["reasoning-coder-placeholder","deterministic-syntax-checks"],"required_checks":["python_py_compile","node_check","endpoint_smoke","diff_check"],"stop_conditions":["same_error_twice","scope_expands_to_database_writes","missing_source_contract"],"downgrade_candidate":["medium-drafter-placeholder","deterministic-route-scan"],"escalation_candidate":["stronger-reasoner-placeholder","integration-smoke-checks"],"human_review_required":true,"confidence_before_assignment":"medium","rationale":"The task spans UI, API, and docs, so it needs a coding-capable combo plus deterministic checks."}
```

## Confidence Before Assignment

Use `high` when:

- task class is known
- source context is already available
- required checks are deterministic
- similar outcome records succeeded with low correction burden

Use `medium` when:

- task class is known but spans multiple files
- context is available but integration risk exists
- similar examples exist but are few

Use `low` when:

- scope is ambiguous
- required source context is missing
- task class is new
- human review or sensitive judgment dominates the result

## Relationship To Outcome Records

The matching outcome record should reference the preflight by `preflight_id`.

TriageCore can then compare:

- predicted task class vs actual task class
- selected combo vs result quality
- required checks vs checks actually run
- stop conditions vs waste signals
- confidence before assignment vs confidence after review
