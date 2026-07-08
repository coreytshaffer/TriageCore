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
