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

## Strategy Delta Calculation

`compute_strategy_delta(baseline, candidate)` compares two strategy records for the same task id and reports whether the candidate saves estimated tokens or adds orchestration overhead. The output is a deterministic, metadata-only delta record:

```json
{
  "schema_version": "runtime_strategy_delta.v2",
  "kind": "runtime_strategy_delta",
  "task_id": "fixture-doc-summary-001",
  "baseline_strategy": "heavy_only",
  "candidate_strategy": "small_first_compact",
  "estimated_tokens_delta": -2470,
  "estimated_percent_delta": -51.5,
  "model_calls_delta": 1,
  "handoffs_delta": 1,
  "interpretation": "token_saving_with_added_handoff",
  "invalid_reason": null,
  "baseline_quality_gate_status": "not_evaluated",
  "candidate_quality_gate_status": "not_evaluated",
  "quality_gate_effect": "quality_not_evaluated"
}
```

The negative control against the same baseline:

```json
{
  "baseline_strategy": "heavy_only",
  "candidate_strategy": "over_orchestrated",
  "estimated_tokens_delta": 1790,
  "estimated_percent_delta": 37.3,
  "interpretation": "orchestration_overhead"
}
```

Interpretation labels are a closed, deterministic vocabulary:

| Label | Rule |
|---|---|
| `token_neutral` | Candidate and baseline have equal estimated tokens. |
| `orchestration_overhead` | Candidate costs more estimated tokens than the baseline. |
| `token_saving_with_added_handoff` | Candidate saves estimated tokens but adds handoffs. |
| `token_saving` | Candidate saves estimated tokens without adding handoffs. |
| `invalid_comparison` | Records are not comparable; `invalid_reason` is one of `task_id_mismatch`, `identical_strategy`, or `zero_baseline_tokens`. |

Delta rules:

- `estimated_tokens_delta` is candidate minus baseline estimated tokens.
- `estimated_percent_delta` is the token delta as a percentage of the baseline, rounded to one decimal place.
- `model_calls_delta` and `handoffs_delta` are candidate minus baseline counts.
- Invalid comparisons return `invalid_comparison` with null deltas instead of raising.
- The delta record must pass the persistent privacy invariant.

Interpretation labels describe estimated token pressure only. While both records carry `quality_gate.status = "not_evaluated"`, a `token_saving` label claims nothing about output quality — a cheaper strategy that produces unusable output is not a saving.

## Quality-Gate Axis

The delta record carries a second, independent axis: `quality_gate_effect`, derived from the baseline and candidate `quality_gate.status` values. Quality gates never rewrite the cost interpretation — a failed strategy can still be `token_saving`; it is just not acceptable. The two axes are reported side by side and read together.

| Effect | Rule |
|---|---|
| `quality_failed` | Either record's gate failed (failure dominates the pair). |
| `quality_passed` | Both gates passed. |
| `quality_not_evaluated` | Neither gate has been evaluated. |
| `quality_mixed` | One gate passed while the other is not evaluated. |
| `quality_unknown` | Defensive fallback for a status outside the closed vocabulary; unreachable through validated records. |

The delta record also carries `baseline_quality_gate_status` and `candidate_quality_gate_status` so the effect is auditable from the record itself.

## CLI Delta Report

The fixture deltas are available as a read-only, deterministic reviewer command:

```powershell
tc runtime-strategy report
tc runtime-strategy report --json
```

Expected text shape:

```text
Runtime strategy delta report

Baseline: heavy_only
Task: fixture-doc-summary-001

Strategy              Tokens Delta   Percent Delta   Calls Delta   Handoffs Delta   Interpretation                    Quality Effect
small_first_compact   -2470          -51.5%          +1            +1               token_saving_with_added_handoff   quality_not_evaluated
small_only            -3080          -64.2%          +0            +0               token_saving                      quality_not_evaluated
over_orchestrated     +1790          +37.3%          +3            +3               orchestration_overhead            quality_not_evaluated

Quality gates: not_evaluated
Note: token savings do not imply quality improvement.
```

The command reads nothing from disk, writes nothing (no ledger, identity, or
review-state access), makes no model calls, and emits ASCII-only output so it
renders on default Windows consoles. The `--json` form emits the same report
as a deterministic JSON object for scripting.

## Report Artifact Export

The report can be written as a metadata-only JSON artifact to an explicit
path:

```powershell
tc runtime-strategy report --output reports\runtime-strategy-deltas.json
tc runtime-strategy report --output reports\runtime-strategy-deltas.json --force
```

Export rules:

- The artifact is byte-for-byte the same JSON the `--json` form prints: one
  serialization, one schema (`runtime_strategy_delta_report.v2`), no separate
  artifact shape, and no generation timestamp — two exports of the same
  fixtures produce identical bytes.
- There is no default write location: without `--output` the command writes
  nothing.
- `--json` and `--output` are mutually exclusive; with `--output` the command
  prints a single confirmation line.
- Fails closed with `reason=output_directory_missing` when the parent
  directory does not exist, and `reason=output_exists` when the file already
  exists and `--force` was not passed. `--force` requires `--output`.
- Overwrites are atomic (temp file plus replace), so a failed write cannot
  destroy a prior artifact.
- The artifact must remain metadata-only: no prompts, raw context, or model
  outputs.

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
