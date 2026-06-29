# CR-083: Signed Route Decision Smoke Example

## Status
Implemented

## Scope

- Add a minimal operator smoke command that emits a metadata-only signed `route_decision` event.
- Add a reviewer-facing doc showing the unsigned default path, the opt-in signed path, and `tc audit --verify-signatures --kind route_decision` expected behavior.
- Add focused tests proving the route-decision smoke path stays valid.
- Update backlog and change log wording to reflect the new reviewer-facing evidence slice.

## Non-Goals

- Do not make route-decision signing automatic.
- Do not change default `TriageClient.run_task(...)` behavior.
- Do not expand policy enforcement beyond metadata-only signature verification.
- Do not add runtime key rotation behavior.
- Do not add dashboard or TUI work.

## Acceptance Criteria

- [x] `tc audit --signed-route-decision-smoke-test --agent-id <id>` appends one metadata-only signed `route_decision` event.
- [x] The command fails closed if the identity is missing or lacks `route_decision:sign`.
- [x] A reviewer-facing doc shows the unsigned default path, the opt-in signed path, and the verification command.
- [x] The route-decision verification doc includes a metadata-only success example and a safe failure example.
- [x] Focused tests prove the smoke event verifies with `tc audit --verify-signatures --kind route_decision`.
- [x] Backlog and change log wording reflect the new reviewer-facing evidence slice.

## Validation

- `python -m py_compile triage_core/tc_cli.py tests/test_audit_cli.py`
- `python -m pytest tests/test_audit_cli.py -q`
- `git diff --check`
