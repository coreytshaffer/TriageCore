# TriageCore Low-Priority Improvements

## Purpose

This container holds proposed TriageCore performance learnings that are not ready for active review or implementation.

Low priority does not mean rejected. It means the current confidence score is below the active-review threshold.

## Entry Criteria

Put a candidate here when:

- confidence score is below `0.65`
- evidence quality is low
- verification is unclear
- implementation effort is high relative to expected gain
- the idea risks blurring SafeTask AI and TriageCore boundaries
- the idea is interesting but not directly tied to local LLM assignment performance

## Container Format

| Candidate ID | Title | Score | Reason | Promotion trigger |
| --- | --- | --- | --- | --- |
| PARK-001 | Speculative autonomous reassignment | 0.38 | High risk and low evidence; could silently route sensitive work. | Promote only after manual assignment telemetry and explicit approval rules exist. |

## Promotion Checklist

A candidate can leave this container when it has at least one strong promotion trigger:

- three relevant assignment outcome records
- one successful replay benchmark
- a smaller first implementation slice
- clear verification criteria
- reduced sensitivity or risk
- explicit Corey approval to prioritize despite low confidence

## Review Cadence

Review this container only after active candidates have changed or new telemetry appears.

Do not spend implementation time on this list during normal work unless Corey asks to promote an item.
