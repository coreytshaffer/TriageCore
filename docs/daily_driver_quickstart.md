# TriageCore Daily-Driver Quickstart

This document explains how to use TriageCore as a local-first governed task surface. TriageCore helps operators check state, inspect safety posture, preview context and routing, execute an explicitly requested task, render bounded handoff packets, and surface reviewable work without hiding authority inside automation.

**TriageCore is not an autonomous background controller.** `tc run` can execute one explicit operator-requested task through the governed routing path, but it does not bypass approval gates, silently resume work, or run agents in the background.

## Daily Operator Loop

Start your work sessions by inspecting the state of your workspace and routing pending tasks:

1. **Check fast local status**
   ```powershell
   python -m triage_core.tc_cli status
   ```
   Provides a quick summary of repo cleanliness, the last ledger event, pending reviews, and the default policy.

2. **Diagnose environment health**
   ```powershell
   python -m triage_core.tc_cli doctor
   ```
   Provides a deeper diagnostic breakdown of your Git environment, ledger, handoff paths, config/test visibility, and runtime-safety posture.

3. **Check the review queue**
   ```powershell
   python -m triage_core.tc_cli review list
   ```
   Surfaces all pending items in the local records that require operator review or approval. 

4. **Preview a governed run**
   ```powershell
   python -m triage_core.tc_cli run "Summarize the current backlog" --files docs/current_backlog.md --privacy local_only --plan --model generic-32k
   ```
   Shows context size, token-budget posture, privacy and egress state, a deterministic route forecast, specialist and ethical-firewall conditions, and expected verification. It makes no model call, writes no ledger event or artifact, and grants no approval.

5. **Execute after reviewing the preview**
   ```powershell
   python -m triage_core.tc_cli run "Summarize the current backlog" --files docs/current_backlog.md --privacy local_only --print
   ```
   Runs a separate operator-initiated invocation through the governed execution path. The preview is advisory and is not cryptographically or persistently coupled to this execution.

6. **Dry-run one-file context planning**
   ```powershell
   python -m triage_core.tc_cli context plan --input docs/current_backlog.md --model generic-32k
   ```
   Evaluates an input file against a chosen token budget profile to ensure it fits safely before handing it off to an LLM.

7. **Render bounded handoff packets**
   ```powershell
   python -m triage_core.tc_cli packet render --task tests/fixtures/packet_renderer/example-task.md --model generic-32k --include docs/current_backlog.md
   ```
   Gathers tasks and included files into a single structured Markdown packet, enforcing token budget boundaries.

## Meaning of Outputs

- **Repo: dirty/clean**: A "dirty" repo means there are uncommitted changes in your workspace. TriageCore uses Git status to track workspace cleanliness.
- **Pending reviews: X detected**: This indicates how many tasks currently require a human review decision but do not have one yet. It does not auto-approve anything; it simply reflects the honest state of the `TaskLedger`.
- **Context fit vs. over budget**: When planning context, TriageCore evaluates if the file fits within the usable input budget after reserving space for safety margins and model output. If a file is "over budget", it exceeds the `usable_input_budget`.
- **Proposed route vs. execution route**: `tc run --plan` uses deterministic and configured inputs only. Live availability, memory headroom, recent failures, internet state, and cloud credit health are not probed, so execution may choose a different governed outcome.
- **Token Estimation**: TriageCore uses a deterministic, conservative character-based estimate (e.g., `max(1, chars // 4)`) rather than precise tokenizer libraries. This ensures consistent bounds across environments without requiring model-specific tokenizers.

## Safe Handoff Workflow

TriageCore enforces bounded handoffs between the operator and the LLM (or other execution agents):

1. **Prepare**: Use `tc packet render` to compile the task and any required context into a single Markdown file. The renderer will warn you if the packet exceeds the safe context budget.
2. **Review**: As the human operator, you review the rendered packet before taking any further action.
3. **Execute Externally**: You hand the resulting packet to the LLM (via a local model, Antigravity, or other tooling).
4. **No Mutation**: TriageCore's rendering does *not* summarize, execute, approve, or mutate any of the input files. It only produces read-only packets.

## Safety Boundaries

TriageCore enforces strict boundaries to preserve trust:
* **Read-only diagnostics**: Commands like `status`, `doctor`, and `review list` only read state and do not mutate the file system or ledger.
* **Dry-run context planning**: The `context plan` command strictly estimates limits; it does not truncate or rewrite your files.
* **Governed run preview**: `tc run --plan` performs privacy and policy checks but makes no model call, executes nothing, and writes no ledger or artifact.
* **Deterministic packet rendering**: The `packet render` command always produces exactly what is expected from the inputs, with no hidden summarization or LLM calls.
* **Human approval remains external and explicit**: The review queue highlights work to be done, but you must manually resolve it. There is no automated approval bypass.

## Troubleshooting

- **Unknown model profile**: If `tc context plan` or `tc packet render` complain about the model, verify you are using a supported string (e.g., `generic-32k`, `generic-128k`, `generic-8k`).
- **Missing input file**: Double-check file paths. TriageCore requires explicit, accurate paths and will fail closed if a file is missing.
- **Dirty git tree**: If `tc status` reports dirty, run `git status` to see what is uncommitted.
- **Empty review queue**: If `tc review list` shows `Status: empty`, there are no tasks in the ledger currently requiring an explicit human approval.
