# CR-072: Admission Evidence Contract Linkage

## Status
Implemented

## Scope

- Add one discoverability link from the normal operator admission workflow path to `docs/admission/admission_evidence_contract.md`.
- Keep the linkage change minimal by using the existing `docs/operations/external-runtime-admission.md` reviewer/operator path instead of broad README churn.
- Update backlog and changelog entries for this slice.

## Non-Goals

- No code changes
- No validator changes
- No renderer changes
- No CLI behavior changes
- No schema changes
- No runtime behavior changes
- No broad docs reorganization

## Description

CR-071 defined the admission evidence contract, but the contract was not yet reachable from the normal operator workflow path. This slice adds the smallest useful linkage so operators and reviewers can discover the contract from the existing admission workflow documentation without changing behavior or widening scope.

## Acceptance Criteria

- [x] `docs/admission/admission_evidence_contract.md` is reachable from a normal reviewer/operator path.
- [x] Link text accurately describes the contract doc.
- [x] CR-072 change request note exists.
- [x] Backlog and change log are updated.
- [x] Full test suite remains green.
