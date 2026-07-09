# Model Review Fixtures

Worked examples for the
[Evidence-Bound Model Review Protocol](../../../../docs/evals/evidence_bound_review_protocol.md).

## Current contents

- `zero_context_prompt.md` — example prompt for the zero-context review pass
  (model reviews TriageCore with no repository evidence supplied).
- `context_aware_prompt.md` — example prompt for the context-aware review pass
  (model reviews against a curated reviewer context bundle).
- `gemma4_qat_sample_eval_note.md` — a curated sample eval note that applies the
  protocol's claim taxonomy and rubric to a Gemma 4 QAT review pass.
- `review_submission_v0.example.json` — an example pre-tagged review submission
  in the `review_submission_v0` input contract, derived from the Gemma 4 QAT
  sample eval note. See the
  [Review Harness Submission Schema](../../../../docs/evals/review_harness_submission_schema.md)
  for the field reference and the structural rules the validator enforces.
- `review_context_packet.example.md` — a small deterministic context bundle
  (with `FILE:` section markers) used to exercise section-scoped citation
  resolution in the checker core.
- `review_result_v0.example.json` — the `review_result_v0` output produced by
  running the deterministic checker over the example submission and example
  context packet. It is an intentional grounding-gate **FAIL** (one
  `context-supported` citation anchor does not resolve). See the
  [Review Harness Result Contract](../../../../docs/evals/review_harness_result_contract.md).

## Intent

These fixtures show a human reviewer how to run the two-pass method and how to
sort a model's claims. They define an input/reading convention; they do not add
runtime behavior, do not call any model, and do not score anything automatically.

## Constraints

- Keep fixtures small and hand-readable.
- Prefer one representative example per artifact before adding variants.
- Do not add live model calls, network dependencies, or filesystem side effects.
- Treat these files as research infrastructure, not production safety
  certification, and not evidence that any model output is correct.
