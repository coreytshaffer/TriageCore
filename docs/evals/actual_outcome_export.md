# Actual Outcome Export

TriageCore exports its evaluation outcomes as static JSON files. This approach ensures a strict architectural boundary between **system behavior** (TriageCore) and **external evaluation** (`agent-control-evals`).

By exporting evidence as files:
- Scoring is performed *only* by the independent eval-suite repository.
- TriageCore does not need to self-score.
- There are no cross-repository Python imports, preventing tight coupling.

> **Reviewer Note:** For the conceptual explanation of how these actual outcome exports can be scored by an independent harness without importing TriageCore, see [Eval Integration Bridge](file:///c:/Users/corey/Documents/Science/AI/triagecore/docs/evals/eval_integration_bridge.md).

## JSON Contract Shape

TriageCore generates one JSON file per evaluation scenario. The exported file must match the following shape:

```json
{
  "case_id": "privacy_leak_attempt_001",
  "decision": "block",
  "boundary_family": "privacy",
  "reasons": ["persistent_artifact_contains_sensitive_content"],
  "audit_required": true,
  "human_approval_required": false
}
```

Required fields:
* `case_id`: The string identifier matching the corresponding test fixture.
* `decision`: A string indicating the agent decision (e.g., "block", "allow").
* `boundary_family`: A string classifying the boundary policy (e.g., "privacy").
* `reasons`: A list of strings justifying the decision.
* `audit_required`: Boolean.
* `human_approval_required`: Boolean.

Extra fields may be present for diagnostics but are not required for scoring.

## Diagnostic details

* `reasons` are stable eval-facing reason codes.
* `diagnostic_details` are optional raw explanatory details.
* diagnostic details are not scored as primary oracle reasons.
* scoring remains external to TriageCore.

Note: Privacy reason normalization now prefers structured finding codes exposed directly by the `PrivacyReport`. These codes are centralized in TriageCore's internal constants (`triage_core.privacy_findings`) to prevent drift, but the exported values remain stable contract strings. The raw diagnostic messages are preserved under `diagnostic_details`. Raw-string normalization remains only as a backward-compatible fallback for older reports.
## Where Files Are Exported

When running evaluation smoke tests or full evaluations, the generated files should be written to a dedicated directory. Examples:
* `.triagecore/eval_actuals/<run_id>/`
* `actuals/triagecore_smoke/`

## Smoke export command

You can write a dummy contract-shaped actual outcome file to verify the pipeline by running:

```powershell
python -m triage_core.tc_cli eval export-smoke --output-dir .triagecore/eval_actuals/smoke
```

## Real decision export path

`TC-EVAL-001` added the pure contract writer, and `TC-EVAL-002` added the smoke export.
`TC-EVAL-003` maps one real internal TriageCore decision path (`triage_core.privacy_scanner.PrivacyReport`) to the actual-outcome contract. Scoring still happens only in the independent eval-suite repo.

When privacy checks fail, they are projected as `audit_required=True`. This does not define a new runtime policy; it only maps the existing `PrivacyReport` result into the external actual-outcome contract.

## Privacy scanner actual export

This path runs TriageCore’s privacy scanner on a deterministic smoke input and exports actual behavior evidence. It does not score the result. Scoring is performed externally from the eval-suite repo.

```powershell
python -m triage_core.tc_cli eval export-privacy-smoke --output-dir .triagecore/eval_actuals/privacy_smoke
```

## How to Score

To score these outcomes, you must use the independent eval-suite repository (`agent-control-evals`). Do not score them within TriageCore.

Run the following command **from the `agent-control-evals` repository**, pointing to the exported actuals directory:

```powershell
# For the mock smoke export
python -m evals.runner --actuals <path-to-triagecore-actuals> --output reports/triagecore_smoke.jsonl

# For the privacy scanner actual export
python -m evals.runner --actuals <path-to-triagecore-privacy-actuals> --output reports/triagecore_privacy_smoke.jsonl
```

The eval kit will consume the static JSON files, score them against expected outcomes, and produce a definitive JSONL evidence report.
