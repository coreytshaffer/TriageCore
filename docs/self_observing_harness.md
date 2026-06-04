# The Self-Observing Harness Doctrine

TriageCore functions as a **Self-Observing Harness** for local and cloud models. It does not exist merely to execute tasks; it exists to observe *how* tasks are executed, evaluate the success of those executions, and propose systemic improvements over time.

## The Evidence Loop

The system operates on a continuous, transparent evidence loop that moves from initial observation to verified adaptation.

### 1. Sense (Task Classification)
The harness observes a new user prompt and context. Using a local LLM or heuristics, it estimates complexity, targets the necessary files, and evaluates the risk level to determine the optimal safety bounds.

### 2. Act (Delegated Execution)
Work is dispatched. Small or repetitive tasks go to the **Local Worker Council** (RepoMapper, TestStubber, CodeRepair, Validator). The harness manages boundaries (file limits, token limits) to prevent system runaway.

### 3. Record (Ledger Events)
Every action is recorded in an immutable local ledger (`.triagecore/ledger.jsonl`). This includes routing decisions, model latency, token consumption, energy estimates, errors, and validation results. 

### 4. Compare (Supervisor Review)
The generated artifact is not assumed to be correct. TriageCore compares the local output against acceptance criteria. If it fails validation or if a human flags it, the task escalates to a **Cloud Supervisor** (e.g., Codex or Antigravity) for targeted review and correction.

### 5. Propose (Learning Candidates)
Using the ledger history, the harness periodically analyzes past failures, escalating patterns, and successful overrides to generate "Learning Proposals". 

### 6. Verify (Human-in-the-Loop)
**Crucially, TriageCore does not rewrite its own rules automatically.** Every Learning Proposal is held in a queue. A human operator must review the evidence and explicitly accept or reject the proposed adaptation.

### 7. Adapt (System Evolution)
Once verified by a human, the proposal is integrated into the routing logic, system prompts, or boundary configurations, improving the harness's future performance.

## Boundaries and Constraints

To ensure the safety and predictability of the harness, the following invariants are strictly enforced:

- **No Automatic Self-Modification:** The system cannot alter its core logic, routing thresholds, or agent prompts without explicit human verification (Step 6).
- **Persistent Visibility:** All state, including intermediate model outputs and telemetry, must be stored transparently in text formats (JSONL/Markdown).
- **Escalation is Supervision, Not Replacement:** High-capability cloud models are treated as supervisors that review and correct local outputs. They do not replace the local workers.
- **Fail Closed:** If a security validator fails, or if token/energy budgets are exceeded, the task immediately halts and escalates. It does not loop endlessly or proceed with partial results.
