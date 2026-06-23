# CR-063: Admission Evidence JSON Fixture Validation

## Goal
Add JSON mapping and validation for ExternalRuntimeAdmissionEvidence, enabling external admission evidence to be reproducible from structured JSON data without execution or CLI surface area.

## Scope
* Add `admission_evidence_from_mapping` function to `triage_core/admission.py`.
* Validate required booleans (`admitted`, `execution_performed`, `approval_required`, `approval_used`).
* Validate required non-empty strings (`requested_runtime`, `requested_capability`, `manifest_or_source_evidence`).
* Validate required list (`blocked_reasons`), allowing empty lists but enforcing non-empty string items.
* Validate optional `approval_evidence`.
* Add 7 test cases covering the validation rules.
* No CLI, no ledger, no file reads.
