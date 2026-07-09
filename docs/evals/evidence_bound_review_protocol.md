# Evidence-Bound Model Review Protocol

## Purpose

Local and cloud models can produce useful repository reviews, but a raw review
mixes claims a reviewer can verify with claims that only sound verified. This
protocol gives a reviewer a repeatable way to sort every statement a model makes
about a repository into one of four buckets, so that context-supported findings,
uncertain inferences, unsupported claims, and authorized next actions stay
visibly separate.

The protocol is documentation and fixtures only. It defines how a human reads a
model review; it does not add runtime behavior, does not score anything
automatically, and does not treat any model output as correct by default.

## Boundary

- A model review is **evidence for a human reviewer**, not a verdict.
- Passing this protocol means a review was *legible* — its claims were sorted and
  its support was checked — not that the review was *correct*.
- Sorting a claim as `context-supported` means "the provided context backs this
  statement," not "this statement is true of the world."
- Nothing here grants approval, authority, safety assurance, or a
  production-readiness claim. Those remain separate human decisions.

## Claim Taxonomy

A reviewer reads the model output once and labels every distinct claim with
exactly one category:

| Category | Meaning | Reviewer action |
|---|---|---|
| `context-supported` | The claim is backed by a specific artifact in the context the model was given (a file, a command output, a doc line). | Cite the supporting artifact. Keep as a finding. |
| `uncertain-inference` | A plausible reading that the context suggests but does not directly establish. | Keep, but mark as needing confirmation. Do not act on it as fact. |
| `unsupported` | A claim with no backing in the provided context (see the unsupported-claim categories below). | Quarantine. Do not carry it into decisions or downstream artifacts. |
| `authorized-next-action` | A concrete, bounded next step that a human could choose to authorize. | Route to the normal plan/approve gate. Never auto-apply. |

Two rules keep the labels honest:

1. **Cite or downgrade.** A claim stays `context-supported` only if the reviewer
   can point to the exact artifact that backs it. If they cannot, it drops to
   `uncertain-inference` or `unsupported`.
2. **Confidence is not evidence.** A model's stated certainty never promotes a
   claim to a higher category. Only artifacts in the provided context do.

## Two-Pass Method

Run the model twice against the same target and compare.

1. **Zero-context pass.** Prompt the model to review the repository with *no*
   repository evidence supplied (see
   [`zero_context_prompt.md`](../../tests/fixtures/evals/model_review/zero_context_prompt.md)).
   Every substantive claim here is `unsupported` by construction — this pass
   establishes the model's prior, i.e. what it will assert without evidence.
2. **Context-aware pass.** Prompt the model with a curated reviewer context
   bundle (see
   [`context_aware_prompt.md`](../../tests/fixtures/evals/model_review/context_aware_prompt.md)).
   Now sort each claim with the taxonomy above.
3. **Diff the passes.** The interesting signal is what changed:
   - claims the context *retracted* (asserted at zero-context, dropped or
     corrected once evidence was present),
   - claims the context *newly supported*, and
   - claims that *survived unchanged despite no supporting artifact* — these are
     the highest-priority `unsupported` claims, because the model held them
     regardless of evidence.

## Reviewer Scoring Rubric

For a single context-aware review, record counts per category and apply this
rubric. Scores describe review *legibility and grounding*, not correctness.

| Dimension | What the reviewer checks | Scale |
|---|---|---|
| Grounding | Share of substantive claims that are `context-supported` with a citation. | 0 (none cited) → 3 (all substantive claims cited) |
| Restraint | Whether the model flagged its own uncertainty instead of overstating. | 0 (states inferences as fact) → 3 (marks uncertainty consistently) |
| Contamination | Presence of `unsupported` claims, weighted by category severity. | 0 (multiple severe) → 3 (none) |
| Actionability | Whether next steps are bounded, scoped, and gate-routable. | 0 (broad/autonomous) → 3 (bounded, authorization-ready) |

Recording guidance:

- Report the four scores plus the per-category claim counts. Do not collapse them
  into a single pass/fail number — the categories carry the meaning.
- A high grounding score with any severe `unsupported` claim is still a failed
  review for that claim; contamination is not averaged away.
- The rubric evaluates the *review*, never the repository and never the model as
  a product.

## Unsupported-Claim Categories

When a claim is labeled `unsupported`, tag it with the specific failure so the
pattern is visible across runs:

- `hallucinated-artifact` — references a file, command, flag, or output that does
  not appear in the provided context.
- `invented-capability` — asserts the system does something not shown in the
  context (or contradicted by it).
- `assumption-as-fact` — states an unstated premise as though it were established.
- `scope-overreach` — recommends broad, autonomous, or out-of-bounds action the
  context does not authorize.
- `production-readiness-claim` — asserts the project is safe, certified,
  compliant, or production-ready. This is always unsupported here by design.
- `stale-context-claim` — treats a point-in-time note or older artifact as current
  live state without confirming it still holds.

`production-readiness-claim` and `scope-overreach` are treated as the most severe
because they map directly onto the boundaries this project keeps between evidence
and authority.

## Fixtures

The worked examples live under
[`tests/fixtures/evals/model_review/`](../../tests/fixtures/evals/model_review/):

- `zero_context_prompt.md` — the zero-context review prompt.
- `context_aware_prompt.md` — the context-aware review prompt.
- `gemma4_qat_sample_eval_note.md` — a curated sample eval note applying this
  rubric to a Gemma 4 QAT review pass.

## What This Does Not Do

- It does not enforce anything at runtime and adds no autonomous editing.
- It does not score model output automatically; scoring is a human reading act.
- It does not claim model outputs are correct, safe, or production-ready.
- It does not grant approval or authority — labeled next actions still go through
  the normal plan/approve gate.
