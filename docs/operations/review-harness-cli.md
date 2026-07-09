# `tc eval review` CLI

`tc eval review` is a thin, read-only wrapper around the evidence-bound review
harness. It validates a pre-tagged review submission, runs the deterministic
checker against an explicitly supplied context packet, and renders or writes the
result. It adds no checking logic of its own.

## Boundary

> This result verifies structural grounding and routing only. It is not a
> correctness, safety, certification, or production-readiness verdict.

The command executes nothing, calls no model, classifies no raw prose, and
approves no action. It reads the submission and the context packet, and the only
file it may write is the caller-supplied `--output` path — it touches no ledger,
identity, or other runtime state.

## Usage

```bash
python -m triage_core.tc_cli eval review \
  --submission <path-to-review_submission_v0.json> \
  --context-packet <path-to-context-packet.md> \
  [--changed-path <repo/relative/path> ...] \
  [--output <path-to-review_result_v0.json>] \
  [--print-json] \
  [--fail-on-gate]
```

## Arguments

| Argument | Required | Purpose |
|---|---|---|
| `--submission` | yes | Path to a `review_submission_v0` JSON file. Validated before use. |
| `--context-packet` | yes | Path to the context bundle text (with `FILE:` markers) the review was performed against. |
| `--changed-path` | no | A repo-relative changed path for the scope check. Repeatable. Omitted → `scope_check: not_checked`. |
| `--output` | no | Write the `review_result_v0` JSON here. Omitted → render to stdout. |
| `--print-json` | no | Also print the JSON result to stdout. |
| `--fail-on-gate` | no | Exit non-zero (`3`) when `grounding_gate` is `fail`. |

## Output and exit codes

- **No `--output`:** prints the rendered review result (ASCII, leak-safe — ids,
  codes, counts, and the boundary line only) to stdout.
- **`--output`:** writes the JSON result to that path and prints a short
  `Success:` line instead of the rendered result.
- **`--print-json`:** prints the JSON result to stdout in addition to the normal
  behavior.
- **Exit codes:**
  - `0` — validation and checking succeeded (the grounding-gate outcome is data,
    reported in the result).
  - `1` — input or validation error (missing or unparseable submission,
    structural validation failures, missing context packet). No result is
    produced.
  - `3` — only with `--fail-on-gate`, after successful validation and checking,
    when `grounding_gate == fail`.

## Example

Running the shipped example fixtures produces an intentional grounding-gate
**FAIL** (one `context-supported` citation anchor does not resolve):

```bash
python -m triage_core.tc_cli eval review \
  --submission tests/fixtures/evals/model_review/review_submission_v0.example.json \
  --context-packet tests/fixtures/evals/model_review/review_context_packet.example.md
```

## Related

- [Review Harness Submission Schema](../evals/review_harness_submission_schema.md)
- [Review Harness Result Contract](../evals/review_harness_result_contract.md)
- [Evidence-Bound Model Review Protocol](../evals/evidence_bound_review_protocol.md)
