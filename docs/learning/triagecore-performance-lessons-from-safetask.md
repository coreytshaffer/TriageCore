# TriageCore Performance Lessons From SafeTask AI

## Boundary

This is a learning extract for TriageCore, not a SafeTask AI feature specification.

SafeTask AI is the source project. Its development work can provide examples, telemetry needs, failure modes, task classes, and routing patterns.

TriageCore is the separate routing and local-LLM assignment learner. It can study SafeTask AI development data, but it should not be merged into SafeTask's compliance platform, UI, database, or authority model unless a future change explicitly creates an integration boundary.

## Goal

Use SafeTask AI development experience to help TriageCore:

- get higher useful output per local model call
- lower wasted retries, overpowered model use, and vague task attempts
- increase the variety of tasks that can be confidently assigned to local LLM combinations
- learn which model/tool/person handoff pattern fits each kind of task
- keep uncertainty visible instead of pretending a weak local result is ready

Performance means useful work completed with the smallest reliable local model/tool combination, not just faster responses.

Backlog: see [triagecore-performance-backlog.md](triagecore-performance-backlog.md) for the current implementation path and status.

## What SafeTask AI Contributes

SafeTask AI can provide:

- task examples: docs drafting, route explanation, smoke-check design, UI wiring, data validation, governance review, and code edits
- workflow evidence: where local drafting is useful, where deterministic checks are better, and where human approval is required
- waste signals: repeated retries, vague prompts, ambiguous scope, low-confidence outputs, and overuse of expensive models for simple tasks
- quality signals: accepted edits, reviewer corrections, smoke-check passes, broken assumptions, and rollback notes
- routing patterns: how a task moves between local LLM drafting, deterministic tools, repo checks, and human review

SafeTask AI should not become:

- the TriageCore product
- the TriageCore lesson store
- the universal router for unrelated projects
- a hidden training system that silently changes routing behavior

## Current Learning Problem

TriageCore needs telemetry that answers four practical questions:

1. What kind of task is this?
2. Which local LLM combination handled it?
3. Did the result pass review or need correction?
4. Was the selected model/tool path wasteful, underpowered, or appropriate?

Without those answers, TriageCore can only guess which local model combination should receive the next task.

## Top 3 TriageCore Lesson Candidates

### TCP-001: Capture Assignment Outcome Telemetry

Status: `approved`

Approval note: Corey approved beginning this learning target. Start with portable outcome records from SafeTask AI development slices before adding any automation.

Lesson for TriageCore:

Every local LLM assignment should produce a compact outcome record. The record should describe the task, the selected local model combination, the tools used, the quality result, the correction burden, and whether the assignment was overpowered, underpowered, or appropriate.

Performance value:

- Creates evidence for routing instead of relying on memory or vibes.
- Shows which tasks small local models can handle confidently.
- Reveals waste from unnecessary retries or oversized model choices.
- Helps identify tasks that need deterministic tooling before any model call.

Suggested outcome record:

```json
{
  "task_id": "safetask-doc-source-registry-2026-06-05",
  "source_project": "SafeTask AI",
  "task_class": "documentation_synthesis",
  "complexity": "medium",
  "model_combo": ["local-small-drafter", "deterministic-diff-check"],
  "tool_path": ["repo_search", "file_edit", "diff_check"],
  "result_status": "accepted_with_minor_edits",
  "correction_burden": "low",
  "waste_signal": "none",
  "confidence_after_review": "high",
  "lesson": "Small local drafting plus deterministic checks is enough for scoped documentation updates."
}
```

Approval boundary:

Approve as telemetry capture only. Do not use outcome records to silently auto-assign sensitive tasks until enough reviewed examples exist.

Implementation start:

- [x] Define a reusable assignment outcome schema.
- [x] Seed initial SafeTask-derived outcome examples.
- [ ] Connect the schema to an actual TriageCore lesson store outside the SafeTask AI app.

### TCP-002: Build A Task-Class To Local-Combo Routing Map

Status: `approved`

Approval note: Corey approved this learning target. Start with a small routing map that assigns task classes to the smallest reliable local model/tool combination.

Lesson for TriageCore:

TriageCore should learn task classes and assign them to the smallest reliable local LLM/tool combination. The point is not to find one best local model. The point is to find dependable combinations for different work shapes.

Performance value:

- Reduces wasted use of larger or slower local models.
- Expands the number of tasks that can be safely delegated.
- Makes routing decisions explainable to Corey.
- Helps local systems specialize instead of treating every task as open-ended chat.

Starting task classes:

| Task class | Candidate local combo | Confidence target |
| --- | --- | --- |
| Repo search and summarization | small local summarizer + deterministic search | high after source citation |
| Scoped documentation edit | medium local drafter + diff check | high after review |
| Code patch planning | medium local reasoning model + static checks | medium until smoke tested |
| UI copy cleanup | small local editor + visual/layout check | medium-high |
| Test/smoke checklist drafting | medium local drafter + repo route scan | high after route verification |
| Compliance-sensitive interpretation | local drafter + human approval | low until source-approved |
| Multi-file code edit | stronger local reasoner + deterministic tests | medium after tests |

Approval boundary:

Approve as an assignment map, not as full automation. Each task class should still carry required checks and stop conditions.

Implementation start:

- [x] Define a starter task-class to local-combo routing map.
- [ ] Connect outcome telemetry to confidence updates for each task class.
- [ ] Move the routing map into the TriageCore lesson store outside the SafeTask AI app.

### TCP-003: Add Waste Controls And Escalation Rules

Status: `approved`

Approval note: Corey approved this learning target. Start with explicit stop, retry, downgrade, and escalation rules for local LLM assignments.

Lesson for TriageCore:

TriageCore should stop or escalate when a local model combination is wasting effort. Waste can mean repeated retries, low-confidence output, missing source evidence, broken syntax, circular planning, or using a large model for a task that deterministic tooling could handle.

Performance value:

- Prevents long loops on weak local outputs.
- Sends tasks to deterministic tools when tools are more reliable than language generation.
- Escalates only when the current model/tool combo has evidence of being underpowered.
- Protects Corey from accepting polished but unsupported local-model answers.

Starting waste rules:

| Waste signal | TriageCore action |
| --- | --- |
| Two failed attempts at the same patch | escalate model or switch to deterministic inspection |
| Missing source citation for repo claim | run repo search before continuing |
| Syntax check fails twice | stop drafting and inspect exact error |
| Task scope is ambiguous | ask one clarifying question |
| Output is accepted with no edits repeatedly | consider assigning that task class to a smaller local combo |
| High correction burden repeatedly | route future tasks to stronger combo or add a checklist |

Approval boundary:

Approve as routing discipline. Waste controls should reduce loops; they should not block urgent human-directed work.

Implementation start:

- [x] Define starter waste controls and escalation rules.
- [ ] Track waste signals from assignment outcome records.
- [ ] Use repeated waste signals to revise local-combo routing decisions.

## Recommended Order

1. TCP-001 first: outcome telemetry creates the evidence base.
2. TCP-002 second: task-class routing turns evidence into better assignments.
3. TCP-003 third: waste controls keep local LLM experimentation from becoming expensive noise.

## Next ROI Candidates

After the first approved loop, see [triagecore-next-roi-performance-candidates.md](triagecore-next-roi-performance-candidates.md) for the next high-return candidates:

- TCP-004: assignment preflight classification
- TCP-005: local combo replay benchmark
- TCP-006: context packaging and budget rules
- TCP-007: resilience and capability-aware routing for degraded cloud/local/offline modes

New proposals should pass through [triagecore-improvement-ranking-system.md](triagecore-improvement-ranking-system.md). Candidates below the active-review threshold should move to [triagecore-low-priority-improvements.md](triagecore-low-priority-improvements.md) until their evidence improves.

## First SafeTask AI Examples To Mine

Use these SafeTask AI development slices as initial examples for TriageCore:

- source registry docs and read-only Admin Governance display
- security smoke checklist drafting
- dependency/configuration review
- Authority Matrix route explanation gaps
- handoff/backlog synchronization after feature slices

These are useful because they include different task shapes: documentation synthesis, UI wiring, API work, governance review, and verification.

## Reviewer Action

Corey can approve a TriageCore learning candidate by saying the candidate ID and approval intent, such as:

`Approve TCP-001.`

After approval, update this file's candidate status to `approved` and keep the SafeTask/TriageCore boundary intact.
