# Workspace Handoff Packets

> **CR-WU-005** — Read-only CLI export for extracting agent handoff text from work items.

## Purpose

The `handoff` command bridges the gap between the static TriageCore registry and actual execution. Rather than manually typing out context for an LLM session, the `handoff` command emits formatted, tool-specific packets combining the objective, constraints, bounds, and criteria into a single copyable block.

## Tool Profiles

- `codex`: Implementation handoff with strict boundaries, checks, and stop rules.
- `chatgpt`: Review/architecture handoff focusing on scope creep and design decisions.
- `status`: Minimal progress summary.
- `closing`: A checklist packet containing verified criteria and checks for final evidence gathering.

## Formats

- `text`: Plain text (default).
- `markdown`: Bold headings (`**`) for markdown renderers.
- `json`: Structured raw data for scripting or further automation.

## Usage

```bash
tc workspace handoff --items ~/.triagecore/work_items.yaml --id CR-WU-005 --tool codex --format text
```

## Privacy & Security Guardrails

By default, the handoff generator actively omits private metadata such as the `notes` block to prevent accidental leakage of sensitive local context or personal information when pasting into third-party cloud models. Output is stable and deterministic.
