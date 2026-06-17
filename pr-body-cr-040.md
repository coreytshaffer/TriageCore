## Summary

Adds a minimal pure-Python routing policy that classifies task routing decisions across local, deterministic, and AMD cloud targets.

This strengthens the AMD hackathon path by turning the documented routing concept into executable, test-backed policy evidence without adding live AMD credentials, backend calls, or runtime cloud integration.

## What changed

- Added `RouteDecision`
- Added `classify_route(task_packet, manifest)`
- Added focused tests for:
  - local routing
  - deterministic routing
  - AMD cloud approval-required routing
  - AMD cloud blocked routing
  - AMD cloud allowed-after-approval routing
- Exported the policy API from the routing package
- Updated AMD example TaskPacket and manifest docs with the minimal fields used by the policy
- Added CR-040 documentation and change log entry

## Validation

- `python -m py_compile triage_core\routing\policy.py`
- `python -m pytest tests\test_routing_policy.py -q`
  - `5 passed`
- `python -m pytest -q`
  - `351 passed, 2 skipped`
- `git diff --check`
  - line-ending warnings only; no content failures

## Scope boundary

This PR intentionally does not add:

- AMD credentials
- ROCm SDK calls
- live API calls
- cloud deployment scripts
- backend client code
- runtime cloud execution
- Qwen route changes

## Residual risk

The policy is not wired into runtime execution yet. That is intentional for this CR. The evidence added here is an executable policy module plus tests, not a live AMD client path.
