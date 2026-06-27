# CR-081: Signed Validation Result Verification Example

## Status
Implemented

## Scope

- Add a reviewer-facing example for verifying signed `validation_result` ledger events.
- Show the exact verification command: `tc audit --verify-signatures --kind validation_result`.
- Show safe metadata-only example output for both pass and fail cases.
- Re-state the boundary that signatures provide provenance, not approval, safety, or correctness.
- Update backlog and change log wording so the signed-event lane reflects the new documentation layer.

## Non-Goals

- No code changes.
- No new signed event types.
- No runtime key rotation.
- No private key exposure.
- No raw prompt or sensitive payload examples.

## Acceptance Criteria

- [x] A reviewer-facing doc shows how to verify signed `validation_result` ledger events.
- [x] The doc includes a metadata-only success example.
- [x] The doc includes safe failure examples for `signature_mismatch`, `unknown_agent`, and `revoked_agent`.
- [x] The doc explicitly states that signature validity proves provenance, not approval, safety, or correctness.
- [x] Backlog and change log wording reflect the documentation slice.

## Validation

- `git diff --check`
- `python -m pytest tests -q`
