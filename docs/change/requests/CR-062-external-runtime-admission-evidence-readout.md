# CR-062: External Runtime Admission Evidence Readout

## Goal
Add a read-only operator-facing report for external runtime admission decisions. This allows TriageCore to show why an external runtime proposal is admitted, blocked, or approval-gated without executing it.

## Scope
* Add `ExternalRuntimeAdmissionEvidence` dataclass to `triage_core/admission.py`.
* Add `render_admission_evidence_markdown` function.
* Add unit tests for 4 distinct admission states.
* Add example JSON fixture.
* No CLI command, no runtime execution, no ledger writes, no side effects.
