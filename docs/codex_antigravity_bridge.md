# Codex And Antigravity Bridge Protocol

## Purpose

This protocol lets TriageCore play to the strengths of both Codex and Antigravity while preserving local-first evidence.

- Local backends draft, classify, benchmark, or attempt bounded work first.
- Antigravity can act as the IDE-native supervisor for implementation flow and local pipeline coordination.
- Codex can act as the repo-grounded supervisor for code review, patching, verification, and documentation.
- TriageCore records the decision trail instead of silently treating any supervisor as magic.

## Recommended Division Of Labor

| Lane | Best At | TriageCore Evidence |
| --- | --- | --- |
| Local LLM | fast first drafts, small benchmark tasks, low-risk parsing and repair | backend, model, tokens, duration, energy, validator result |
| Worker Council | parallel local specialist review | worker role, aggregate tokens, duration, escalation decision |
| Antigravity | IDE-native orchestration, visual implementation flow, Gemini supervisor coordination | `supervisor_tool=antigravity`, model/profile, artifact path, decision |
| Codex | repo-grounded review, patching, tests, methodology/docs, Git hygiene | `supervisor_tool=codex`, notes, tests/artifacts, decision |

## Credibility And Throughput Separation

TriageCore intentionally separates high-throughput implementation from
publication-facing credibility work.

Antigravity is the preferred lane for moving quickly inside the IDE: exploring
larger implementation slices, coordinating local model pipelines, sketching UI
or workflow changes, and producing enough concrete code for later review.
Antigravity outputs should be treated as productive drafts until they are
reconciled against the ledger, tests, documentation, and evidence boundaries.

Codex is the preferred lane for credibility review: checking claims against the
repo state, tightening methodology language, preserving APA7-ready citation
habits, reconciling docs with implementation, running stability checks, and
making sure paper-facing language stays cautious, reproducible, and falsifiable.
Codex review does not make a result scientifically valid by itself; it helps
label what is verified, what is estimated, and what still needs evidence.

This separation is an operating protocol, not a ranking of tools. The goal is
to use Antigravity for momentum and Codex for stabilization, documentation
credibility, and evidence-bound interpretation.

## Workflow

1. Run a local draft, worker council, benchmark, or auto pipeline task.
2. Review the task in the ledger.
3. If Antigravity or Codex supervises the result, record that review:

   ```powershell
   triagecore record-supervisor-review <task_id> --tool codex --decision needs_revision --notes "Local draft was close but missed tests." --model gpt-5 --profile high --artifact-path triage_tasks\codex_task_example.md
   ```

   ```powershell
   triagecore record-supervisor-review <task_id> --tool antigravity --decision accepted --notes "Gemini supervisor accepted the local draft after IDE review." --model gemini-3.1-pro-high --profile supervisor --artifact-path .agent_tasks\example\TASK.md
   ```

4. Use `accepted`, `rejected`, `needs_revision`, or `escalated` consistently.
5. Treat estimated supervisor token fields as estimates unless exact tool usage is available.
6. When exact tool usage is available as JSON or JSONL, import it instead of retyping values:

   ```powershell
   triagecore scan-supervisor-usage supervisor_logs\
   triagecore import-supervisor-usage supervisor_usage.jsonl --tool codex --token-source imported_exact --dry-run
   triagecore import-supervisor-usage supervisor_usage.jsonl --tool codex --token-source imported_exact
   ```

## Interpretation Rule

Do not compare local-only runs against supervised runs without labeling the supervision lane. A Codex-reviewed patch and an Antigravity-supervised IDE implementation are different workflows, even if they start from the same local draft.

## Next Improvements

- Capture exact supervisor token usage when an API or tool surface exposes it.
- Import supervisor usage from tool logs when exact values can be verified.
