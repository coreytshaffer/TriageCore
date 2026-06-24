# Actual Outcome Export

TriageCore exports its evaluation outcomes as static JSON files. This approach ensures a strict architectural boundary between **system behavior** (TriageCore) and **external evaluation** (`agent-control-evals`).

By exporting evidence as files:
- Scoring is performed *only* by the independent eval-suite repository.
- TriageCore does not need to self-score.
- There are no cross-repository Python imports, preventing tight coupling.

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

## Where Files Are Exported

When running evaluation smoke tests or full evaluations, the generated files should be written to a dedicated directory. Examples:
* `.triagecore/eval_actuals/<run_id>/`
* `actuals/triagecore_smoke/`

## How to Score

To score these outcomes, you must use the independent eval-suite repository (`agent-control-evals`). Do not score them within TriageCore.

Run the following command **from the `agent-control-evals` repository**, pointing to the exported actuals directory:

```powershell
python -m evals.runner --actuals ../triagecore/actuals/triagecore_smoke/ --output reports/triagecore_smoke.jsonl
```

The eval kit will consume the static JSON files, score them against expected outcomes, and produce a definitive JSONL evidence report.
