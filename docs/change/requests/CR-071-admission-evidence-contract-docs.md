# CR-071: Admission Evidence Contract Documentation

## Status
Implemented

## Scope

- Add a docs-first contract for admission evidence JSON at `docs/admission/admission_evidence_contract.md`.
- Document the current required and optional fields supported by `triage_core.admission.admission_evidence_from_mapping`.
- Make forbidden assumptions and trust boundaries explicit.
- Document the relationship between the contract and the `tc admission validate --from-json` and `tc admission render --from-json` CLI paths.
- Update backlog and changelog entries for this slice.

## Non-Goals

- No validator changes
- No renderer changes
- No CLI behavior changes
- No schema expansion
- No live runtime execution
- No network behavior
- No README churn unless a very small existing docs link is clearly needed

## Description

This slice turns the recent admission evidence work into a stable, reviewable contract document. The goal is to make the admission evidence JSON layer legible to future operators, contributors, and tests without adding new code pressure. The document explains what the current implementation accepts, what it does not prove, and how validation and rendering remain subordinate to separate admission and execution authority.

## Acceptance Criteria

- [x] Admission evidence contract doc exists.
- [x] Required and optional fields match current implementation.
- [x] Forbidden assumptions are explicit.
- [x] Trust boundaries are explicit.
- [x] CLI relationship is documented.
- [x] CR-071 note added.
- [x] Backlog and change log updated.
- [x] Full test suite still passes.
