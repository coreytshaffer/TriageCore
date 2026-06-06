# TriageCore Context Pack Templates

## Purpose

Context packs define the minimum useful context a local LLM combination should receive for a task.

The goal is to reduce context-window waste and missing-context failures while making smaller local models more useful.

## Design Rule

Give the local model enough context to do the task, but not enough noise to blur the task.

Each pack should include:

- task goal
- source artifacts
- only the relevant snippets or summaries
- constraints and stop conditions
- required checks
- prior outcome hints when available

## Pack Types

### `repo_evidence_pack`

Best for:

- repo search summaries
- documentation synthesis
- initial task classification

Include:

- target repo path
- relevant file paths
- short evidence snippets
- current status or known dirty-worktree note
- unanswered questions
- required citations or file references

Avoid:

- large unrelated files
- speculative summaries without file evidence

### `code_slice_pack`

Best for:

- scoped UI/API edits
- small backend route changes
- local integration slices

Include:

- target files
- relevant call sites
- existing patterns to preserve
- expected behavior
- required checks
- rollback or scope boundary

Avoid:

- broad architecture history unless directly needed
- unrelated refactor opportunities

### `review_packet_pack`

Best for:

- human approval decisions
- sensitive lessons
- compliance, safety, evidence, or deployment boundary work

Include:

- proposed decision
- evidence
- risks
- approval boundary
- what is not being approved
- next safe action

Avoid:

- presenting draft model output as approved fact

### `benchmark_pack`

Best for:

- local combo replay tests
- comparing model/tool combinations

Include:

- replay prompt
- allowed context
- forbidden shortcuts
- expected checks
- pass/fail criteria
- scoring notes

Avoid:

- leaking the expected final answer when testing reasoning

### `handoff_pack`

Best for:

- continuing work across sessions
- resuming after interruption

Include:

- current goal
- completed files
- pending files
- validations already run
- known blockers
- next safe step

Avoid:

- stale assumptions without dates or verification notes

## Template Record

```json
{
  "context_pack_id": "ctx-safetask-source-registry-display-2026-06-05",
  "pack_type": "code_slice_pack",
  "source_project": "SafeTask AI",
  "task_goal": "Expose source registry examples in Admin Governance without adding registry writes.",
  "source_artifacts": [
    "docs/compliance/source-registry.md",
    "safetask/apps/surveillance_command_center/app.py",
    "safetask/apps/surveillance_command_center/app.js",
    "safetask/apps/surveillance_command_center/index.html"
  ],
  "constraints": [
    "read-only display",
    "no database writes",
    "keep SafeTask and TriageCore separate"
  ],
  "required_checks": [
    "python_py_compile",
    "node_check",
    "endpoint_smoke",
    "diff_check"
  ]
}
```

## Budget Rules

Use a smaller pack when:

- the task is summarization or formatting
- source files are short
- deterministic checks carry most of the confidence

Use a larger pack when:

- the task spans UI, API, and persistence
- prior attempts failed from missing context
- human review depends on seeing evidence and boundary notes

Stop and rebuild the pack when:

- the model asks for facts already present in the repo
- the model invents source behavior
- the task drifts into unrelated files
- checks fail because a required artifact was omitted
