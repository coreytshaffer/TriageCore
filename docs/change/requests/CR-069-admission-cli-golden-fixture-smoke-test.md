# CR-069: Admission CLI Golden Fixture Smoke Test

## Status
Implemented

## Scope

- Reuse the public admission evidence JSON fixture under `docs/examples/admission-evidence.example.json`.
- Add a focused CLI smoke test covering both:
  - `tc admission validate --from-json`
  - `tc admission render --from-json`
- Assert stable operator-facing headings and fields in the rendered Markdown without snapshotting the entire output.
- Add one fail-closed negative CLI test using the existing invalid-fixture pattern.
- Update backlog and changelog entries for this slice.

## Non-Goals

- No live runtime execution
- No network calls
- No ledger writes
- No admission policy changes
- No README churn unless a broken command path is found

## Description

This slice adds a narrow regression layer around the new admission JSON CLI path. The goal is to prove that the same public fixture can still pass strict JSON validation and render a stable operator-facing Markdown readout through the CLI surface. Keeping the smoke test fixture-based and CLI-level helps protect the reviewable operator workflow without widening scope into runtime execution, persistence, or broader refactors.

## Acceptance Criteria

- [x] Valid admission evidence fixture passes `tc admission validate --from-json`.
- [x] Valid admission evidence fixture passes `tc admission render --from-json`.
- [x] Render smoke test checks meaningful operator-facing headings and fields.
- [x] Negative CLI fixture case fails closed.
- [x] No live external runtime execution occurs.
- [x] No ledger write occurs.
- [x] Focused admission tests pass.
