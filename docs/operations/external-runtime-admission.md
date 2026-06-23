# Operator Admission Workflow

TriageCore relies on deterministic operator governance before allowing an autonomous agent to execute an external runtime payload. 

The Operator Admission Workflow strictly separates proposal inspection from execution. Operators use pure offline CLI tools to validate and read out payloads as Markdown. Execution sidecars can then independently enforce these verified states.

## The Tri-Part Governance Model

The full lifecycle of runtime admission involves three distinct components:

1. **Task Envelope (The Contract)**
   - Defines the task objective, boundaries, risk level, and required capabilities.
   - Represents the "what" and the "why".
2. **Admission Evidence (The Proof)**
   - Details why a specific runtime proposal aligns with the task envelope.
   - Represents the exact evaluation of requested vs. allowed capabilities.
3. **Execution Sidecar (The Enforcer)**
   - An isolated environment (e.g., container, sandbox) that consumes the task envelope and admission evidence to execute code, restricting access strictly to approved bounds.

## Operator Workflow

### Step 1: Draft and Validate the Task Envelope

Before doing any work, the operator (or an agent under operator supervision) constructs a Task Envelope mapping.

You can preview the shape or use the wizard to build one interactively:
```bash
tc task-envelope preview
tc task-envelope wizard
```

When a Task Envelope JSON fixture is proposed, the operator validates it to ensure structural integrity and strict typing, and then renders it to Markdown for human review:

```bash
# Verify it conforms to the Task Envelope schema
tc task-envelope validate --from-json envelope.json

# Read the human-legible contract
tc task-envelope draft --from-json envelope.json
```

### Step 2: Evaluate Admission Evidence

When an agent proposes executing an external runtime (e.g., executing Python in a Docker container), it must provide a structured payload of Admission Evidence mapping exactly what runtime is requested and why.

The operator validates and renders this payload without ever running the code or writing to the global ledger. This ensures the proposal can be fully understood offline.

```bash
# Verify it conforms to the Admission Evidence schema
tc admission validate --from-json admission.json

# Read the human-legible trust anchors
tc admission render --from-json admission.json
```

The rendered output provides trust anchors (such as `**Execution Performed:** false`), highlighting whether the payload requires manual approval or is blocked by policy violations.

### Step 3: External Runtime Sidecar Execution

If the admission is `admitted: true` (or manually approved if gated), the payload can be passed to the external runtime sidecar.

TriageCore does not execute arbitrary code directly in the host OS. Instead, it expects operators to provide standard runtime adapters that honor the validated Envelope and Admission Evidence.

*(Note: Execution adapter tooling is handled by your specific runtime integration.)*

## Key Security Properties

- **No Implicit Execution:** Neither `tc task-envelope` nor `tc admission` execute runtimes. They only perform schema mapping and pure-Markdown rendering.
- **No Implicit Ledger Writes:** The CLI tools intentionally reject reading from or writing to `.triagecore/ledger.jsonl` via `--from-json` to prevent state corruption.
- **Stateless Validation:** All validation is isolated, making it safe to integrate into CI pipelines, offline terminals, or external agent feedback loops.
