# Eval Integration Bridge

## Purpose
This document provides a reviewer-facing explanation of how TriageCore interfaces with the independent `agent-control-evals` repository. It clarifies how actual outcome exports produced by TriageCore can be deterministically scored by an external harness without importing or coupling the repositories.

## Integration Boundary
The integration between TriageCore and the evaluation harness is strictly **file-contract-based**.
There are no shared runtime dependencies, no cross-repository Python imports, and no hidden coupling. The boundary is entirely maintained by writing static JSON files to disk, which are then independently read and scored.

## What TriageCore Produces
TriageCore acts as a compatible producer of static actual outcome JSON records. When its control-plane scanner intercepts an action (for example, a privacy check or a forbidden tool call), it can map the resulting internal decision into a standardized external contract shape and write it to disk.

## What the External Harness Consumes
`agent-control-evals` acts as the independent evaluation suite. It consumes the static JSON records produced by TriageCore, validates them against its own expected-outcome fixtures, and produces a scored JSONL report showing where the system passed or failed.

## Example Handshake Commands
To execute the file-contract integration manually, you only need the built-in CLI commands from both repositories.

1. **In TriageCore**: Export the actual outcome to a shared or temporary directory.
   ```powershell
   python -m triage_core.tc_cli eval export-privacy-smoke --output-dir actuals/privacy_smoke
   ```

2. **In `agent-control-evals`**: Score the actuals against the independent fixtures.
   ```powershell
   python -m evals.runner --actuals <path-to-triagecore>/actuals/privacy_smoke --output reports/privacy_smoke_results.jsonl
   ```

## What This Demonstrates
This integration demonstrates a decoupled, inspectable control-plane evaluation pattern. It proves that a system's adherence to external boundaries (privacy, authorization, human approval) can be rigorously audited and scored by a completely independent test suite using a stable file contract.

## Non-Claims
To remain strictly within the bounds of this evaluation architecture, we explicitly note what this integration does **not** claim:

*   **This does not certify TriageCore**: The eval kit proves architectural capability but is not a substitute for production-grade certification.
*   **This does not prove model alignment**: The safety mechanisms evaluated here reside in the control plane's boundary enforcement, not the generative model itself.
*   **This does not provide sandboxing**: This pattern evaluates policy and decision compliance, not OS-level process isolation.
*   **This does not claim comprehensive safety coverage**: The fixtures test specific, bounded families of failure, not every conceivable adversarial attack.
*   **This only demonstrates a narrow file-contract pattern** for scoring static control-plane outcomes.

## Future Work
*   Expanding the JSON contract schema to handle multi-step interactions and conversational audits.
*   Adding standardized export endpoints in TriageCore to produce actuals for the new Escalation Channel boundary family.
