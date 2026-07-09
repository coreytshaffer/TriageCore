# Review Harness Result Contract (`review_result_v0`)

## Purpose

`review_result_v0` is the output contract for the deterministic checker core of
the evidence-bound review harness (`triage_core/review_result.py`,
`build_review_result`). The checker consumes a validated
[`review_submission_v0`](review_harness_submission_schema.md) plus an explicitly
supplied context packet string and produces this result.

## Boundary

> This result verifies structural grounding and routing only. It is not a
> correctness, safety, certification, or production-readiness verdict.

The checker is **not an oracle**. It performs only mechanically-decidable checks.
It does not classify raw model prose, decide whether any claim is true, execute
the declared `validation` commands, call a model, or approve real-world actions.
The exact boundary line above is emitted in the result (`boundary` field) and by
`render_review_result`.

## Inputs

`build_review_result(submission, context_packet, changed_paths=None)`:

- `submission` — an already-validated `review_submission_v0` (validate it with
  `validate_review_submission` first).
- `context_packet` — the raw bundle text the review was performed against,
  using `FILE: <path>` section markers.
- `changed_paths` — optional list of repo-relative paths that actually changed.
  When omitted, the scope check reports `not_checked` rather than guessing.

## Checks

- **Citation resolution (section-scoped).** For each `context-supported` claim,
  the cited `FILE: <path>` must appear as a section marker in the packet; if the
  citation includes a `#<anchor>`, the anchor must appear **within that file's
  section**, not merely somewhere in the packet.
- **Grounding gate fails** if any of:
  - an `unsupported` claim is in a **severe** category
    (`production-readiness-claim`, `scope-overreach`),
  - a `context-supported` claim's citation does **not** resolve
    (`unresolved_citation`),
  - a `changed_paths` entry falls outside `declared_scope` (`scope_violation`,
    only evaluated when `changed_paths` is supplied).

  Otherwise the gate passes.
- **Human-review routing.** Every `declared_actions[]` with
  `requires_human_review: true` is listed in `human_review_required` and is never
  selectable as the next action.
- **Next safe action.** Only when the gate passes, the first
  `authorized-next-action` claim (in submission order) is selected, identified by
  `claim_id` only.
- **Warnings (non-blocking).** `uncertain-inference` claims and non-severe
  `unsupported` claims are surfaced as warnings.

## Output Shape

```json
{
  "schema_version": "review_result_v0",
  "boundary": "This result verifies structural grounding and routing only. It is not a correctness, safety, certification, or production-readiness verdict.",
  "grounding_gate": "pass",
  "gate_failures": [],
  "citation_map": [
    {"claim_id": "c1", "resolved": true, "matched_file": "pyproject.toml"}
  ],
  "unsupported_claims": [],
  "warnings": [],
  "scope_check": {"status": "not_checked", "out_of_scope": []},
  "human_review_required": [],
  "next_safe_action": {"claim_id": "c12"}
}
```

### Field reference

| Field | Type | Notes |
|---|---|---|
| `schema_version` | string | Always `review_result_v0`. |
| `boundary` | string | The fixed boundary line above. |
| `grounding_gate` | enum | `pass` or `fail`. |
| `gate_failures` | array | `{claim_id?, code}`. Codes: `unresolved_citation`, `severe_unsupported_category`, `scope_violation` (the last has no `claim_id`). |
| `citation_map` | array | `{claim_id, resolved, matched_file?}` for each `context-supported` claim. `matched_file` is present when the file marker resolved, even if an anchor failed. |
| `unsupported_claims` | array | `{claim_id, unsupported_category}`. |
| `warnings` | array | `{claim_id, code}`. Codes: `uncertain_inference`, `non_severe_unsupported`. |
| `scope_check` | object | `{status: pass \| fail \| not_checked, out_of_scope: [path]}`. |
| `human_review_required` | array | `{action_index}` for each human-review-required declared action. |
| `next_safe_action` | object \| null | `{claim_id}` when the gate passes and an authorized-next-action claim exists; otherwise `null`. |

Outputs are leak-safe: claims and actions are identified by id/index, never by
echoing claim or action text.

## Worked Example (an Intentional FAIL)

The shipped fixtures resolve the
[example submission](../../tests/fixtures/evals/model_review/review_submission_v0.example.json)
against the
[example context packet](../../tests/fixtures/evals/model_review/review_context_packet.example.md)
to produce
[`review_result_v0.example.json`](../../tests/fixtures/evals/model_review/review_result_v0.example.json).

That example **fails the grounding gate**: claim `c4` cites
`FILE: pyproject.toml#dependencies.cryptography`, whose anchor does not resolve
within the pyproject section, so it is an `unresolved_citation`. This is the
intended lesson — a conservative, mostly-grounded model review still fails the
gate when a `context-supported` citation does not mechanically resolve. Because
the gate fails, `next_safe_action` is `null` even though an
`authorized-next-action` claim is present.

## CLI

The checker is exposed read-only via `tc eval review` — see the
[`tc eval review` CLI](../operations/review-harness-cli.md). The CLI adds no
checking logic; it validates a submission, runs `build_review_result`, and
renders or writes the result.

## What This Does Not Do

- No model calls, no command execution, no raw-prose classification.
- No citation *quality* judgment beyond section-scoped anchor resolution.
- No action approval and no correctness, safety, certification, or
  production-readiness verdict.

## Related

- [Review Harness Submission Schema](review_harness_submission_schema.md)
- [Evidence-Bound Model Review Protocol](evidence_bound_review_protocol.md)
