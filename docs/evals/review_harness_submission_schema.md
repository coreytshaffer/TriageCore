# Review Harness Submission Schema (`review_submission_v0`)

## Purpose

`review_submission_v0` is the input contract for the (future) Evidence-Bound
Review Harness. It is a **pre-tagged** review submission: a human (or a separate
model pass performed elsewhere) has already sorted a model review's claims using
the [Evidence-Bound Model Review Protocol](evidence_bound_review_protocol.md)
taxonomy, and this packet records that sorted result in a structured, checkable
form.

This document defines the input shape and the structural rules enforced by the
Slice 1 validator (`triage_core/review_submission.py`, `validate_review_submission`).

## Boundary

- The validator checks **structure, types, taxonomy enums, citation/anchor
  format, and legibility** only.
- A submission that passes validation is **well-formed and readable** — it is
  **not** thereby correct, safe, approved, or production-ready.
- The validator does **not** resolve citations against a context packet, does
  **not** classify raw model prose, does **not** decide whether a claim is true,
  does **not** execute the declared `validation` commands, and does **not**
  approve any declared action.

## Contract Shape

```json
{
  "schema_version": "review_submission_v0",
  "context_packet_ref": "scratch/gemma_triagecore_reviewer_context.md",
  "claims": [
    {
      "id": "c1",
      "text": "TriageCore is a local-compute-first orchestration harness.",
      "category": "context-supported",
      "citation": "FILE: pyproject.toml"
    },
    {
      "id": "c7",
      "text": "TriageCore should not claim to be a cloud IAM system.",
      "category": "unsupported",
      "unsupported_category": "assumption-as-fact"
    }
  ],
  "declared_actions": [
    {
      "text": "Add a Governance & Identity Model documentation section.",
      "requires_human_review": true
    }
  ],
  "validation": [
    {"command": "python -m pytest -q", "recorded_result": "not_recorded"}
  ],
  "declared_scope": ["docs/evals/", "tests/fixtures/evals/model_review/"],
  "repo_diff_ref": null
}
```

## Field Reference

| Field | Required | Type | Notes |
|---|---|---|---|
| `schema_version` | yes | string | Must equal `review_submission_v0`. |
| `context_packet_ref` | yes | string (non-empty) | A reference to the bundle the review was done against. Stored as a reference; not resolved. |
| `claims` | yes | non-empty array | See claim fields below. |
| `claims[].id` | yes | string (non-empty, unique) | Stable identifier within the submission. |
| `claims[].text` | yes | string (non-empty) | The claim as stated. |
| `claims[].category` | yes | enum | One of the claim categories below. |
| `claims[].citation` | conditional | string | **Required** when `category` is `context-supported`; optional otherwise. Format-checked (see below). |
| `claims[].unsupported_category` | conditional | enum | **Required** when `category` is `unsupported`; optional otherwise. |
| `declared_actions` | no | array | Proposed next actions. |
| `declared_actions[].text` | yes* | string (non-empty) | *Required if the action object is present. |
| `declared_actions[].requires_human_review` | yes* | boolean | *Required if the action object is present. |
| `validation` | no | array | Declared commands and their recorded results. **Never executed by the validator.** |
| `validation[].command` | yes* | string (non-empty) | *Required if the validation item is present. |
| `validation[].recorded_result` | no | string | Submitter-declared; not verified or executed. |
| `declared_scope` | no | array of strings | Paths/globs the change was authorized to touch. |
| `repo_diff_ref` | no | string | Reference to a diff artifact (used by a later slice, not this one). |

Unknown extra fields are ignored (forward-compatible).

## Enums

**`category`** (claim taxonomy):

- `context-supported`
- `uncertain-inference`
- `unsupported`
- `authorized-next-action`

**`unsupported_category`**:

- `hallucinated-artifact`
- `invented-capability`
- `assumption-as-fact`
- `scope-overreach`
- `production-readiness-claim`
- `stale-context-claim`

## Citation Format

The validator checks citation **format only**, never resolution. A citation is
well-formed if it is either:

- a bundle file marker: `FILE: <path>` (e.g. `FILE: pyproject.toml`), or
- a `<ref>#<anchor>` pair (e.g.
  `FILE: tests/test_identity_cli.py#test_identity_init_creates_key_and_public_metadata`).

Whether the referenced artifact actually appears in the context packet is a
resolution check performed by the checker core, not this validator. See the
[Review Harness Result Contract](review_harness_result_contract.md) for
section-scoped citation resolution.

## Validator Errors

`validate_review_submission(obj)` returns a list of
`{"path": ..., "code": ...}` dicts (empty list = structurally valid). Error
values carry no claim text or file paths. Stable codes include:
`wrong_type`, `missing_field`, `empty_value`, `invalid_schema_version`,
`empty_claims`, `duplicate_claim_id`, `invalid_category`, `missing_citation`,
`invalid_citation_format`, `missing_unsupported_category`,
`invalid_unsupported_category`.

## Delivered By Later Slices

- `review_result_v0` output contract and the deterministic checker core
  (section-scoped citation resolution, severe-contamination gate, scope check,
  human-review routing, next-safe-action selection) — see the
  [Review Harness Result Contract](review_harness_result_contract.md).

## CLI

- `tc eval review` validates a submission and runs the checker against a
  supplied context packet — see the
  [`tc eval review` CLI](../operations/review-harness-cli.md).

## Related

- [Evidence-Bound Model Review Protocol](evidence_bound_review_protocol.md)
- [`tests/fixtures/evals/model_review/`](../../tests/fixtures/evals/model_review/) — example submission and worked review fixtures.
