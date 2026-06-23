# CR-073: Admission Evidence Fixture Drift Check

## Status
Implemented

## Scope

- Add a small guardrail test that checks drift between the admission validator, public valid fixture, and admission evidence contract documentation.
- Reuse the current public fixture at `docs/examples/admission-evidence.example.json`.
- Assert that the contract doc references the fixture path, the current required top-level fields, and the recognized optional `approval_evidence` field.
- Update backlog and changelog entries for this slice.

## Non-Goals

- No validator changes
- No renderer changes
- No CLI behavior changes
- No schema expansion
- No live runtime execution
- No network behavior
- No full-document snapshot testing
- No README churn

## Description

This slice adds a narrow drift-check guardrail around the governance artifacts built in CR-069 through CR-072. The test keeps the public valid fixture, the current validator contract, and the admission evidence contract documentation from silently diverging. It intentionally checks stable field-name tokens and fixture-path references rather than brittle prose snapshots.

## Acceptance Criteria

- [x] Public valid fixture still validates.
- [x] Contract doc references the public valid fixture.
- [x] Contract doc mentions all currently required top-level fields.
- [x] Contract doc mentions `approval_evidence` as the recognized optional field.
- [x] Full suite passes.
- [x] `tc doctor` remains clean.
- [x] `git diff --check` is clean.
