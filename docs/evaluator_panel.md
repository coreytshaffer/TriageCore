# TriageDesk Evaluator Panel

The **Evaluator Panel** in TriageDesk is a display-only UI module designed to visualize external evaluation results of TriageCore evaluator-input packets.

> [!WARNING]
> **Observation-Only Safety Boundary**
> TriageDesk does **NOT** run evaluators, nor does it interpret evaluation results as authorizations. The evaluator panel acts strictly as an observational lens. The human operator remains the sole approval authority.

## Architectural Context

This module implements the TriageDesk portion of the **Decoupled Workspace Evaluator Bridge**:
1. `TriageCore` exports a **selective, static evaluator-input packet** — a deliberately narrowed artifact assembled for evaluation, not a complete or authoritative copy of workspace state.
2. `agent-control-evals` (or another external evaluator) assesses the packet structurally.
3. The evaluator produces a static JSON result.
4. **`TriageDesk` (Evaluator Panel) loads and displays that result.**

The boundary at step 1 is one-way. **TriageCore does not invoke the evaluator and does not produce evaluator results.** It writes the input artifact and stops there; evaluator execution and result production are external to TriageCore, and nothing in this bridge gives TriageCore a way to run an evaluator or synthesize a result on its behalf.

> "The evaluator is a signal classifier, not an approval authority."

For more details on the fluidic boundary and observation-only constraints, see the [Workspace Unifier Architecture](architecture/workspace_unifier_architecture.md).

## Strict Display-Only Rules

To maintain the safety boundary, the TriageDesk Evaluator Panel explicitly enforces the following:

- **No Execution:** TriageDesk does not spawn subprocesses, invoke models, or make network calls to run evaluators. It only reads static JSON files from disk.
- **No Inferred Approval:** Any evaluator result that attempts to claim approval authority (e.g., `approval_status != "not_approval"`, or a decision like `"approve"`) is instantly classified as **INVALID** or **UNSAFE**.
- **No Target Invocation:** Any evaluator result that claims execution capability (e.g., `target_invocation != "not_invoked"`) is instantly classified as **INVALID** or **UNSAFE**.

## History List and Loading Results

The UI provides two ways to load results into the history table:

1. **Load Result JSON:** Loads a single static evaluator result file.
2. **Load Result Folder:** Loads all `.json` files within a specified directory.
   - *Note:* Folder loading is **non-recursive** and strictly **display-only**. It does not watch the folder or auto-refresh.

### File Outcomes

The history list represents **file outcomes**, rather than only valid evaluator results. This ensures that unsafe or broken results are flagged visibly for review instead of being normalized. Each loaded file receives one of the following statuses:

- **PASS**: The evaluator structurally passed the packet (decision `pass` or `observe`).
- **FAIL**: The evaluator explicitly failed the packet (decision `fail`).
- **AMBIG**: The evaluator lacked sufficient evidence to pass or fail (decision `ambiguous`).
- **UNSAFE**: The JSON parsed successfully, but the result violates the observation-only boundary (e.g. attempting to claim approval or execution authority).
- **INVALID**: Valid JSON, but missing or misconfigured expected evaluator-result fields.
- **MALFORMED**: The file is not valid JSON or could not be parsed.

These statuses describe **what a file said**, not what may now happen.

`PASS`, `FAIL`, `AMBIG`, and any numeric or categorical score are observational
results only. None grants, withholds, or implies execution authority. A `PASS`
result is neither human approval nor a required precondition for execution.

A human operator remains the sole approval authority.

Selecting any row in the history table updates the detail pane. For `UNSAFE`, `INVALID`, or `MALFORMED` files, the details pane displays the specific validation error to aid in debugging.

## Expected JSON Shape

The panel expects a static JSON file matching the observation-only schema.

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
