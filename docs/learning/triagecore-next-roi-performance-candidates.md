# TriageCore Next ROI Performance Candidates

## Purpose

This document captures the next highest-return TriageCore improvements after the first approved loop:

1. assignment outcome telemetry
2. task-class to local-combo routing
3. waste controls and escalation rules

These candidates are still TriageCore learning work. SafeTask AI remains a source of examples, not the owner of the TriageCore router.

## Selection Rule

Prefer improvements that reduce wasted local model calls before they happen.

The next best gains should help TriageCore:

- pick the right task class sooner
- collect the right context before calling a local model
- compare local model combinations with repeatable evidence
- expand confident delegation without hiding uncertainty

## Next Top 3 Candidates

### TCP-004: Add Assignment Preflight Classification

Status: `implementation_started`

ROI: highest.

Lesson for TriageCore:

Before sending work to a local LLM combination, TriageCore should run a lightweight assignment preflight. The preflight should classify the task, sensitivity, required context, required checks, likely model combo, and stop conditions.

Why this improves performance:

- Prevents vague tasks from reaching the wrong model.
- Catches missing repo/data context before generation starts.
- Avoids using a stronger model when deterministic search or a small summarizer should go first.
- Expands safe local delegation by making the assignment criteria explicit.

Suggested preflight record:

```json
{
  "task_class": "ui_api_slice",
  "sensitivity": "medium",
  "required_context": ["target files", "existing UI pattern", "API route behavior"],
  "required_checks": ["syntax_check", "endpoint_smoke", "diff_check"],
  "default_combo": "reasoning_coder_plus_deterministic_checks",
  "stop_conditions": ["same_error_twice", "scope_expands", "missing_source_file"],
  "human_review_required": true
}
```

First implementation:

Add a preflight checklist or JSON schema that can be filled before each assignment outcome record.

Implementation start:

- [x] Define assignment preflight schema.
- [x] Seed SafeTask-derived preflight examples.
- [ ] Connect preflight records to a TriageCore lesson store outside the SafeTask AI app.

### TCP-005: Build A Local Combo Replay Benchmark

Status: `review_ready`

ROI: very high.

Lesson for TriageCore:

TriageCore should replay a small set of known tasks against candidate local model/tool combinations and compare outcomes. The goal is not a public benchmark; it is a practical local assignment benchmark for Corey's work.

Why this improves performance:

- Replaces guesswork about which local combo is "good enough."
- Shows when a smaller model can handle a task class.
- Reveals which tasks need deterministic tools more than stronger models.
- Creates confidence scores from repeated outcomes instead of one-off impressions.

Starter replay set:

| Replay task | Task class | Pass signal |
| --- | --- | --- |
| Summarize source-registry docs | `documentation_synthesis` | cites correct files and preserves SafeTask/TriageCore boundary |
| Draft security smoke checklist | `smoke_check_design` | includes sensitive routes and pass/fail checks |
| Review dependency/config assumptions | `configuration_review` | avoids unsupported version claims |
| Plan UI/API source registry slice | `code_patch_planning` | identifies files, risks, and smoke checks |
| Classify a vague user request | `repo_search_summary` or `scope_triage` | asks one clarifying question or runs search first |

First implementation:

Create a small benchmark manifest with task prompts, required context, expected checks, and pass/fail criteria.

### TCP-007: Add Resilience And Capability-Aware Routing

Status: `active_candidate`

ROI: high.

Lesson for TriageCore:

TriageCore should route work based on current system conditions, not just task class. Internet availability, cloud/API credits, LM Studio health, local model availability, memory headroom, privacy, deterministic tool availability, and recent failures should influence which worker receives the task.

Why this improves performance:

- Keeps work moving when cloud tools, credits, or internet access fail.
- Promotes the heavier LM Studio workhorse from "backup model" to explicit degraded-mode route.
- Prevents repeated calls to failing providers through circuit breakers.
- Makes local autonomy measurable through route and result ledger events.

First implementation:

Use [triagecore-resilience-routing.md](triagecore-resilience-routing.md) as the static policy design for route modes, fallback chains, circuit breakers, and route/result ledger events.

### TCP-006: Add Context Packaging And Budget Rules

Status: `implementation_started`

ROI: high.

Lesson for TriageCore:

TriageCore should prepare compact context packs for local LLM combinations. Each pack should include only the source files, snippets, constraints, and prior outcomes needed for the task class.

Why this improves performance:

- Reduces local context-window waste.
- Prevents missing-context failures.
- Makes smaller models more useful because they receive cleaner inputs.
- Improves repeatability across local model combinations.

Context pack types:

| Context pack | Best for | Contents |
| --- | --- | --- |
| `repo_evidence_pack` | search summaries, doc synthesis | file paths, key snippets, current status |
| `code_slice_pack` | scoped edits | target files, call sites, constraints, smoke checks |
| `review_packet_pack` | human approval work | decision, evidence, risks, approval boundary |
| `benchmark_pack` | replay tests | prompt, allowed context, expected checks, pass criteria |
| `handoff_pack` | continuing work | latest status, completed files, next safe step |

First implementation:

Define context pack templates and add a `context_pack_id` field to assignment outcome records.

Implementation start:

- [x] Define context pack templates.
- [x] Add `context_pack_id` linkage to assignment outcome schema.
- [x] Seed SafeTask-derived context pack examples.
- [ ] Use context pack quality to adjust future local-combo confidence.

## Recommended Order

1. TCP-004 first: preflight classification prevents waste before it starts.
2. TCP-006 second: context packaging makes every local combo more effective.
3. TCP-007 third: resilience routing keeps TriageCore useful when cloud routes are degraded.
4. TCP-005 fourth: replay benchmarks prove which combos actually work.

TCP-005 can start in parallel as a tiny manual benchmark, but it becomes much more valuable after preflight, context-pack, and route-decision fields exist.

## Approval Boundary

Approving these candidates should mean "start the learning artifacts and small manual workflows." It should not mean automatic reassignment, silent training, or hidden changes to SafeTask AI.
