# CR-014: Qwen Cloud Backend Adapter

## Status
Implemented

## Scope
- Add a Qwen Cloud backend adapter behind the existing backend interface.
- Read Qwen enablement, API key, base URL, and model from environment/config accessors.
- Allow a minimal cloud execution path only for already external-safe packets on cloud-selected routes.
- Preserve local-only fail-closed privacy enforcement and mocked tests with no live Qwen dependency.

## Implementation Authority
Implemented in repo.

## Description
TriageCore now includes a narrow Qwen Cloud adapter and an explicit cloud execution path that only activates after privacy verification and external-safe conversion succeed. Local-only packets remain blocked before adapter invocation, missing credentials fail safely into handoff behavior, and route audit behavior remains privacy-safe for allowed and blocked decisions.

## Acceptance Criteria
- [x] Qwen Cloud backend adapter exists behind a narrow interface.
- [x] Adapter reads credentials/config from environment or config accessors only.
- [x] Missing credentials fail gracefully.
- [x] Local-only packets cannot route to Qwen Cloud execution.
- [x] External-safe packets can route to Qwen Cloud when explicitly allowed.
- [x] Route audit records are emitted for Qwen Cloud allowed and blocked decisions.
- [x] Tests use mocked Qwen Cloud responses.
- [x] Full test suite passes.
