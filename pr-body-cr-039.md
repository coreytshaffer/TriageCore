## Summary

Adds AMD hackathon submission materials for the TriageCore AMD cloud routing demo path.

This PR keeps the AMD submission story separate from the Qwen MemoryAgent path and points judges toward the executable routing-policy evidence added in CR-040.

## What changed

- Added judge-facing AMD routing policy evidence note
- Added AMD cloud submission overview content
- Added AMD routing demo documentation
- Added AMD route audit ledger example
- Added architecture diagram
- Added CR-039 documentation
- Updated the change log

## Relationship to CR-040 / PR #30

This PR is intentionally separate from PR #30.

PR #30 adds the executable routing-policy evidence. This PR explains the AMD submission story and points judges to that evidence.

Merge order should be:

1. PR #30 / CR-040
2. This PR / CR-039

## Validation

- `git diff --check`
  - line-ending warnings only; no content failures

## Scope boundary

This PR does not add:

- AMD credentials
- live AMD backend calls
- ROCm SDK integration
- runtime cloud execution
- Qwen route changes
- executable routing-policy code

## Residual risk

The AMD routing path is still a governed demo and policy-evidence path, not a live AMD cloud execution backend. That is intentional for this submission slice.
