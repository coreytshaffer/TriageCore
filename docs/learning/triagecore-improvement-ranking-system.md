# TriageCore Improvement Ranking System

## Purpose

This ranking system scores each proposed TriageCore performance learning as it arrives.

The goal is to protect attention. High-confidence, high-return improvements should move into the active candidate set. Low-confidence or poorly evidenced ideas should go into a low-priority container until more evidence appears.

## Design Rule

Do not rank by excitement alone.

Rank each proposed improvement by:

- expected performance gain
- evidence quality
- implementation effort
- risk
- fit with the local LLM assignment goal
- readiness for verification

## Intake Record

Each proposed learning should start with a compact intake record:

```json
{
  "candidate_id": "TCP-007",
  "title": "Improvement Ranking Gate",
  "source_project": "SafeTask AI",
  "proposal_type": "assignment_policy",
  "expected_gain": "high",
  "evidence_quality": "medium",
  "implementation_effort": "low",
  "risk_level": "low",
  "local_llm_fit": "high",
  "verification_ready": true,
  "confidence_score": 0.78,
  "priority_bucket": "active_review"
}
```

## Scoring Factors

| Factor | Weight | High score means |
| --- | --- | --- |
| Expected gain | 25 | The improvement should reduce waste, improve confidence, or expand assignable task variety. |
| Evidence quality | 25 | The idea is grounded in observed outcomes, repo evidence, or repeated failure patterns. |
| Local LLM fit | 20 | The improvement directly helps assign work to local model/tool combinations. |
| Verification readiness | 15 | There is a practical way to test whether the improvement helped. |
| Low implementation effort | 10 | The first slice can be done without a broad rewrite. |
| Low risk | 5 | The improvement does not silently automate sensitive decisions or blur project boundaries. |

## Confidence Buckets

| Confidence score | Bucket | Action |
| --- | --- | --- |
| `0.80` to `1.00` | `active_candidate` | Add to active roadmap for review or implementation. |
| `0.65` to `0.79` | `active_review` | Keep visible, but require more evidence or a smaller first slice. |
| `0.40` to `0.64` | `low_priority` | Store in the low-priority container. Revisit when evidence improves. |
| below `0.40` | `parking_lot` | Keep only as a note; do not spend implementation time yet. |

## Low-Priority Rule

If a proposed improvement scores below `0.65`, put it in the low-priority container unless Corey explicitly promotes it.

Low priority does not mean bad. It means one of these is true:

- not enough evidence yet
- unclear performance gain
- too much implementation effort for the expected return
- too risky without more safeguards
- not directly tied to local LLM assignment performance

## Example Ranking

| Candidate | Expected gain | Evidence | Effort | Risk | Score | Bucket |
| --- | --- | --- | --- | --- | --- | --- |
| TCP-004 assignment preflight | high | high | low | low | 0.91 | `active_candidate` |
| TCP-006 context packaging | high | medium | medium | low | 0.82 | `active_candidate` |
| TCP-005 replay benchmark | high | medium | medium | low | 0.76 | `active_review` |
| speculative autonomous reassignment | high | low | high | high | 0.38 | `parking_lot` |

## Review Loop

1. Capture the proposed improvement.
2. Score it with the weighted factors.
3. Assign a bucket.
4. Move low-confidence items to the low-priority container.
5. Promote only when new outcome telemetry, benchmarks, or user approval increases confidence.

## Promotion Rule

A low-priority candidate can move up when it gains one of:

- three relevant outcome records
- one successful replay benchmark result
- clearer verification criteria
- reduced implementation scope
- explicit Corey approval to prioritize despite low confidence

## Boundary

This is a TriageCore prioritization mechanism. It should not change SafeTask AI behavior, approve local LLM outputs, or silently reassign sensitive work.
