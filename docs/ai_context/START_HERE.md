# AI Agent Context: START HERE

Welcome. If you are an AI agent or a new contributor working on TriageCore, you must understand the documentation layout and change rules before proposing or implementing changes.

## Guiding Principles
TriageCore operates as a **Self-Observing Harness**. It does not exist merely to execute tasks; it exists to observe how tasks are executed.
- **No Automatic Self-Modification**: You cannot alter core logic, routing thresholds, or agent prompts without explicit human verification.
- **Human-in-the-Loop**: All systemic adaptations require explicit human acceptance.

## Where to Look
Depending on your goal, consult the following documents:
- **Active Work & Phases**: `docs/backlog.md` (What is currently planned or deferred).
- **Architecture & Codebase Changes**: `docs/change/change_management.md` (How to propose a change).
- **Aspirational Ideas**: `docs/futures/futures_register.md` (Ideas that are not yet approved for implementation).
- **Core Doctrine**: `docs/self_observing_harness.md` (Rules for observation and adaptation).
- **Verification Standards**: `docs/verification_guide.md` (How to verify your work).
- **First-Run Setup**: `docs/workflows/operator_bootstrap.md` (How to set up the operator CLI).

## Change Rules
1. Do not modify existing architecture without an approved Architectural Decision Record (ADR).
2. Do not implement new features without an approved Change Request (CR).
3. Do not treat Futures Register items as approved work; they must be promoted to a CR first.
4. Separate operational telemetry (`.triagecore/ledger.jsonl`) from architecture history (`docs/change/change_log.md`).
5. If a requested change appears useful but exceeds the active CR, do not implement it. Record it as a proposed follow-up CR or Futures Register item.
