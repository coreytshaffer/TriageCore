# TriageDesk Evaluator Panel

The **Evaluator Panel** in TriageDesk is a display-only UI module designed to visualize external evaluation results of TriageCore workspace packets. 

> [!WARNING]
> **Observation-Only Safety Boundary**
> TriageDesk does **NOT** run evaluators, nor does it interpret evaluation results as authorizations. The evaluator panel acts strictly as an observational lens. The human operator remains the sole approval authority.

## Architectural Context

This module implements the TriageDesk portion of the **Decoupled Workspace Evaluator Bridge**:
1. `TriageCore` exports an immutable workspace packet.
2. `agent-control-evals` (or another external evaluator) assesses the packet structurally.
3. The evaluator produces a static JSON result.
4. **`TriageDesk` (Evaluator Panel) loads and displays that result.**

For more details on the fluidic boundary and observation-only constraints, see the [Workspace Unifier Architecture](./workspace_unifier_architecture.md) (or corresponding architecture notes).

## Strict Display-Only Rules

To maintain the safety boundary, the TriageDesk Evaluator Panel explicitly enforces the following:

- **No Execution:** TriageDesk does not spawn subprocesses, invoke models, or make network calls to run evaluators. It only reads static JSON files from disk.
- **No Inferred Approval:** Any evaluator result that attempts to claim approval authority (e.g., `approval_status != "not_approval"`, or a decision like `"approve"`) is instantly classified as **INVALID**. 
- **No Target Invocation:** Any evaluator result that claims execution capability (e.g., `target_invocation != "not_invoked"`) is instantly classified as **INVALID**.

## Expected JSON Shape

The panel requires a static JSON file matching the observation-only schema. 

Below is an example of a valid evaluator result:

```json
{
  "result_type": "workspace_packet_evaluation_result",
  "item_id": "DEMO-001",
  "packet_id": "workspace_eval_packet_contract_001",
  "decision": "observe",
  "approval_status": "not_approval",
  "target_invocation": "not_invoked",
  "score": "pass",
  "reasons": [
    "Required workspace packet fields are present.",
    "Private fields were not included.",
    "Evaluator result is observation-only."
  ],
  "warnings": [],
  "generated_at": "2026-06-27T00:00:00Z"
}
```

If the loaded JSON violates the observation-only constraints, the UI will display a red **INVALID** status and provide the specific validation error explaining why the result was rejected.
