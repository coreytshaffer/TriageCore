# TriageCore Waste Controls

## Purpose

This document defines starter rules for reducing wasted local LLM work.

Waste means effort that does not improve the result: repeated retries, oversized model use, unsupported claims, vague task attempts, skipped checks, or using a model where deterministic tooling would be more reliable.

## Design Rule

TriageCore should optimize for useful verified work, not raw model output.

A local LLM assignment should either:

- complete the task with appropriate checks
- produce a clear partial result and stop
- escalate to a stronger combo
- downgrade to a smaller combo
- switch to deterministic tooling
- ask Corey one clarifying question

## Waste Signals

| Waste signal | Meaning | Default action |
| --- | --- | --- |
| `none` | The assignment fit the task. | Keep the combo candidate. |
| `overpowered` | A larger/slower model was unnecessary. | Try a smaller combo for similar future tasks. |
| `underpowered` | The model could not handle the task reliably. | Escalate model or add deterministic checks. |
| `repeated_retry` | The same failure repeated. | Stop and inspect the exact error or missing input. |
| `missing_context` | The model lacked source evidence. | Run repo search, file read, or ask for context. |
| `tool_should_handle` | A deterministic tool would be better. | Route to parser, validator, shell check, or test first. |
| `scope_ambiguous` | The task needs a decision before work can continue. | Ask one clarifying question. |
| `human_review_required` | The task involves judgment beyond local model authority. | Produce a draft or review packet, not an approval. |

## Retry Rules

| Situation | Rule |
| --- | --- |
| First failure with clear error | Inspect the exact error and try one targeted fix. |
| Second failure with same error | Stop retrying and switch strategy. |
| Failure caused by missing source evidence | Run deterministic search before another model call. |
| Failure caused by ambiguous goal | Ask Corey one clarifying question. |
| Failure caused by unsupported dependency or network need | Label the blocker and request approval only if needed. |

## Downgrade Rules

Downgrade to a smaller local combo when:

- similar tasks are repeatedly accepted with no or low correction burden
- deterministic checks carry most of the reliability
- the task is mostly summarization, formatting, or scoped copy cleanup
- the source artifacts are simple and already available

Examples:

- repo search summary after source files are identified
- narrow documentation cleanup
- short handoff note updates
- formatting a known JSONL outcome record

## Escalation Rules

Escalate to a stronger local combo when:

- the task spans several modules or contracts
- medium/high correction burden repeats for the task class
- code behavior changes need reasoning across UI, API, and persistence
- the task requires tradeoff analysis before editing
- the model misses constraints that were present in source files

Escalation should add capability, not just tokens. A stronger combo should also include better tools, checks, or source context.

## Deterministic-First Rules

Use deterministic tooling before model generation when the question is:

- whether JSON parses
- whether Python or JavaScript syntax is valid
- whether a route exists
- whether a string appears in the repo
- whether a file changed
- whether a schema-required field is missing

The model can interpret the result afterward, but it should not guess these facts.

## Human Review Rules

Require human review when the task involves:

- compliance interpretation
- safety or emergency guidance
- evidence release or custody
- production deployment boundaries
- approval of a routing lesson
- changing the assignment policy itself

For these tasks, TriageCore should produce a review packet and wait for Corey approval.

## Initial Thresholds

| Metric | Starter threshold | Action |
| --- | --- | --- |
| Same error repeats | 2 attempts | stop and inspect |
| Correction burden | `medium` or `high` twice in same task class | escalate or add checklist |
| Accepted with low burden | 3 similar records | consider downgrade |
| Missing context | any occurrence | run source search before continuing |
| Human review required | any occurrence | do not auto-approve |

## Next Integration Step

Connect these rules to assignment outcome records. TriageCore should revise routing confidence when waste signals repeat across similar task classes.
