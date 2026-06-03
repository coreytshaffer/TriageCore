# TriageCore

**A Local-First Developer-Agent Control Harness**

TriageCore provides safety rails, task classification, and structured handoff packets for AI coding agents. Instead of giving agents unbounded access or automatically falling back to expensive cloud models when things fail, TriageCore evaluates tasks locally, assigns permission profiles, and generates `.md` packets (Handoff Packets) for tools like Codex and Antigravity.

## Core Philosophy

1. **Local Executes, Cloud Stays Out:** We've removed automatic cloud fallbacks. If an operation fails locally or hits a safety constraint, it doesn't quietly burn cloud tokens. It generates a structured `HandoffPacket` for a developer or specialized agent to review.
2. **Safety by Default:** Tasks are classified by the `DangerDetector`. Requests to edit `.env` files, run `sudo`, or execute risky deletes (`rm -rf`) are flagged and restricted to `read-only` or `blocked` permission profiles.
3. **Agent-Agnostic Packets:** TriageCore compiles instructions into standardized Markdown bundles. These bundles guide your agents (e.g., Antigravity or Codex) exactly on what to do, what files to touch, and how to verify their work.

## Installation

You can install TriageCore locally for CLI access:

```bash
git clone https://github.com/coreytshaffer/TriageCore
cd TriageCore
pip install -e .
```

## CLI Usage

TriageCore provides a convenient CLI for generating agent task bundles:

### 1. Initialize Agent Configs
Generate a default `AGENTS.md` file in your repository:
```bash
triagecore init-agents
```

### 2. Generate a Codex Task
Create a standalone markdown task file (`triage_tasks/codex_task_low.md`) for Codex:
```bash
triagecore codex-task --prompt "Refactor the database connection string logic" --files src/db.py
```

### 3. Generate an Antigravity Bundle
Create a robust multi-file bundle (`.agent_tasks/my-slug/TASK.md`, `ACCEPTANCE_CRITERIA.md`):
```bash
triagecore antigravity-task --prompt "Add pytest coverage for handoff.py" --files tests/test_handoff.py --slug add-tests
```

## Architecture

TriageCore consists of several tightly integrated local components:

- **TriageClient & TriageEngine**: Execute local parsing/generation tasks with strict temporal budgets (e.g., via LM Studio / Ollama).
- **TriageRouter**: Inspects prompts to decide if they should be executed immediately or wrapped into a handoff packet.
- **TaskClassifier & DangerDetector**: Categorize tasks (`bugfix`, `docs_update`) and enforce safety constraints (`read-only`, `workspace-write`, `blocked`).
- **HandoffPacket**: A dataclass that standardizes tasks into readable Markdown.

## Development & Testing

TriageCore uses `pytest` to ensure all routing and safety logic operates completely offline without network calls.

```bash
pip install pytest
pytest tests/
```

## License
MIT
