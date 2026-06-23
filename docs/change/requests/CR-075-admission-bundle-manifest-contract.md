# CR-075: Admission Bundle Manifest Contract

## Status
Implemented

## Scope

- Add a small manifest contract doc for `bundle_manifest.json` at `docs/admission/admission_bundle_manifest_contract.md`.
- Add focused bundle-manifest contract coverage in `tests/test_admission_cli.py`.
- Assert the generated manifest preserves review-only semantics and keeps `execution_authority` set to `false`.
- Update backlog and changelog entries for this slice.

## Non-Goals

- No live runtime execution
- No network calls
- No ledger writes
- No admission approval semantics
- No validator changes
- No renderer changes
- No broad CLI behavior changes
- No broad docs reorganization

## Description

CR-074 introduced a review bundle path that looks official enough to become risky if its manifest drifts toward approval or execution semantics. This slice makes the current manifest contract explicit and adds a narrow test to keep the generated manifest and its documentation aligned around the review-only boundary.

## Acceptance Criteria

- [x] Manifest contract doc exists.
- [x] Tests assert the generated manifest preserves review-only semantics.
- [x] Tests assert `execution_authority` remains `false`.
- [x] Tests assert no approval/execution-granting manifest fields are introduced.
- [x] Contract doc is consistent with generated manifest.
- [x] Full suite passes.
- [x] `tc doctor` remains clean.
- [x] `git diff --check` is clean.
