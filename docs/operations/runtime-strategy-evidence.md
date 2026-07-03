# Runtime Strategy Evidence

## Purpose

This document defines the current runtime strategy evidence record.

The goal is to capture one orchestration shape as structured, metadata-only evidence before changing routing behavior. This is the layer above token-efficiency records: it records which model/runtime steps were proposed or measured, their estimated token pressure, and whether a quality gate has been evaluated.

## Example Record

```json
{
  "kind": "runtime_strategy_evidence",
  "task_id": "fixture-doc-summary-001",
  "strategy": "small_first_compact",
  "steps": [
    {
      "role": "extractor",
      "backend": "ollama",
      "model_profile": "small_extractor",
      "estimated_input_tokens": 1200,
      "estimated_output_tokens": 180,
      "estimated_total_tokens": 1380,
      "schema_valid": true
    },
    {
      "role": "reviewer",
      "backend": "lm_studio",
      "model_profile": "heavy_reviewer",
      "estimated_input_tokens": 600,
      "estimated_output_tokens": 350,
      "estimated_total_tokens": 950,
      "schema_valid": true
    }
  ],
  "totals": {
    "estimated_tokens": 2330,
    "model_calls": 2,
    "handoffs": 1
  },
  "quality_gate": {
    "status": "not_evaluated",
    "reason": "measurement-only strategy fixture"
  }
}
```

## Model Role Boundary

The intended local architecture is:

- LM Studio heavy model: reviewer, planner, escalation judge, and final synthesis.
- Ollama workers: bounded typed workers for extraction, summarization, test triage, and compact evidence production.
- TriageCore: router, budgeter, evidence ledger, and quality-gate boundary.

The record describes this strategy. It does not execute it.

## Strategy Comparison Fixtures

The deterministic comparison fixture covers four strategies for the same task id:

| Strategy | Purpose | Expected interpretation |
|---|---|---|
| `heavy_only` | Baseline single LM Studio reviewer call | Simple but sends the full context to the heavy model. |
| `small_first_compact` | Ollama extractor followed by LM Studio reviewer | Tests whether compact worker evidence can reduce heavy-model context. |
| `small_only` | Single Ollama summarizer path | Cheapest local estimate, with quality still unevaluated. |
| `over_orchestrated` | Router, extractor, critic, then heavy reviewer | Negative-control fixture showing that extra orchestration can waste tokens. |

The fixture derives:

- strategy name
- model-call count
- handoff count
- estimated total tokens
- estimated tokens by backend
- quality-gate status

The negative-control strategy matters because token-aware orchestration should be able to show when a multi-step plan costs more than the heavy-only baseline.

## Validation Rules

- Each step must declare a role, backend, model profile, estimated input tokens, estimated output tokens, and schema-validity status.
- `estimated_total_tokens` is derived from input plus output estimates.
- `totals.estimated_tokens` must equal the sum of all step totals.
- `totals.model_calls` must equal the number of steps.
- `totals.handoffs` cannot exceed the number of step transitions.
- The record must pass the persistent privacy invariant.

## Non-Claims

- No live model call is made.
- No automatic routing behavior changes.
- No quality improvement is claimed while `quality_gate.status` is `not_evaluated`.
- No cost, energy, or emissions claim is made from this record.
- No raw prompts, raw context, or raw model outputs are persisted.

## Related Docs

- [token-efficiency-evidence.md](token-efficiency-evidence.md)
- [runtime-efficiency-ledger.md](runtime-efficiency-ledger.md)
- [controlled-runtime-experiments.md](controlled-runtime-experiments.md)
- [experiment-observability-traces.md](experiment-observability-traces.md)
