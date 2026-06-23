# Task Envelope CLI Reference

The `tc task-envelope` command provides operators with the ability to preview and draft deterministic Markdown representations of Task Envelopes without triggering runtime execution or ledger interactions.

## Command Overview

The CLI provides three deterministic commands:
- `tc task-envelope preview`: Prints a hardcoded example Task Envelope.
- `tc task-envelope draft`: Builds a Task Envelope purely from explicit CLI flags.
- `tc task-envelope wizard`: Interactively prompts the user for all required envelope fields.

None of these commands read from or write to the ledger (`.triagecore/ledger.jsonl`), nor do they execute any side-effects. They are strictly local Markdown rendering utilities.

---

## `tc task-envelope wizard`

An interactive command that guides the operator through creating a Task Envelope. It prompts for each required field sequentially and ensures that contract requirements (like having at least one allowed file) are met before rendering.

**Usage:**
```bash
tc task-envelope wizard
```

It will prompt for all the required fields listed in the `draft` command below, then output the final Markdown.

---

## `tc task-envelope preview`

Outputs a sample Task Envelope to `stdout`. Use this command to verify the structure and formatting of the Task Envelope template (CR-052) and its Markdown renderer (CR-053).

**Usage:**
```bash
tc task-envelope preview
```

---

## `tc task-envelope draft`

Drafts a new Task Envelope from CLI flags or a JSON fixture. This command enforces the required boundaries of the Task Envelope contract. All list-based flags (`--allowed-file`, `--forbidden-area`, `--non-scope`, `--evidence`) must be provided explicitly to prevent accidental scope bleed.

If a required field is missing, the command will fail and exit nonzero.

**Using a JSON Fixture:**
You can provide a local JSON file using `--from-json <path>`. This is mutually exclusive with explicit field flags.
```bash
tc task-envelope draft --from-json docs/examples/task-envelope.example.json
```
*(Note: `.triagecore/ledger.jsonl` is not an allowed fixture source).*

**Required Flags (if not using `--from-json`):**
- `--task-id`: Unique identifier (e.g., `CR-010`)
- `--title`: Title of the task
- `--objective`: Detailed goal of the task
- `--repo`: Target repository name
- `--operator-agent-lane`: Which lane is executing (e.g., `cli-operator`, `agent`)
- `--route`: The execution route
- `--risk-level`: The assessed risk (e.g., `Low`, `High`)
- `--requested-capability`: Capabilities needed (e.g., `read_only`)
- `--allowed-file`: (Repeatable) Explicitly allowed files or paths
- `--forbidden-area`: (Repeatable) Explicitly forbidden paths or patterns
- `--non-scope`: (Repeatable) Items explicitly excluded from the task
- `--approval-gates`: Human or automated approval requirements
- `--validation-plan`: How the task's success will be verified
- `--evidence`: (Repeatable) Evidence that must be produced
- `--current-status`: Current envelope status (e.g., `proposed`, `approval_required`)
- `--operator-decision`: Operator's decision state (e.g., `Pending`)
- `--next-allowed-action`: The next valid step in the workflow

**Optional Flags:**
- `--blocked-reason`: Reason the envelope is blocked or failed
- `--approval-evidence`: Identifier or summary of approval
- `--admission-evidence`: Identifier or summary of admission

**Full Example:**
```bash
tc task-envelope draft \
  --task-id "CR-056" \
  --title "CLI Task Envelope Draft Example" \
  --objective "Demonstrate drafting an envelope from CLI flags." \
  --repo "TriageCore" \
  --operator-agent-lane "cli-operator" \
  --route "local-cli" \
  --risk-level "Low" \
  --requested-capability "read_only" \
  --allowed-file "docs/operations/task-envelope-cli.md" \
  --forbidden-area ".triagecore/ledger.jsonl" \
  --non-scope "Runtime execution" \
  --approval-gates "human review" \
  --validation-plan "pytest and git diff" \
  --evidence "stdout markdown" \
  --current-status "proposed" \
  --operator-decision "Pending" \
  --next-allowed-action "review markdown"
```

> [!NOTE]
> Future updates will introduce an interactive CLI wizard that automates the collection of these flags. For now, `draft` serves as the underlying backbone for automated assembly and explicit testing.
