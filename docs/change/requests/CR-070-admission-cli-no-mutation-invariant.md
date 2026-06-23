# CR-070: Admission CLI No-Mutation Invariant

## Status
Implemented

## Scope

- Reuse the public admission evidence JSON fixture from `docs/examples/admission-evidence.example.json`.
- Add a focused invariant test for both:
  - `tc admission validate --from-json`
  - `tc admission render --from-json`
- Run both commands from an isolated temporary working directory with explicitly controlled `.triagecore/` state.
- Assert that no ledger file is created or modified and no unexpected local runtime files appear.
- Update backlog and changelog entries for this slice.

## Non-Goals

- No admission policy changes
- No live runtime execution
- No network calls
- No ledger writes
- No CLI refactor
- No README churn

## Description

This slice hardens the admission JSON CLI path by proving it stays read-only. CR-069 already showed that a public fixture can be validated and rendered through the operator-facing CLI path. CR-070 adds the next governance guardrail: the same commands must not create ledger records, modify existing `.triagecore/` state, or leave behind runtime artifacts in the working directory.

## Acceptance Criteria

- [x] Existing admission CLI smoke tests still pass.
- [x] New no-mutation invariant test passes.
- [x] Full suite passes.
- [x] `tc doctor` remains clean.
- [x] `git diff --check` is clean.
- [x] CR-070 documentation explains the invariant and non-goals.
