# Workspace Dashboard

> **CR-WU-004** — Static HTML orientation view for TriageCore work items.

## Purpose

The Workspace Dashboard provides a visually pleasing, browser-based "launchpad" view of the workspace. It translates the information from the terminal `now` command into a highly readable, side-by-side card layout designed specifically for agent handoffs.

## Features

- **Static HTML output:** Zero dependencies (no external CSS, JS, React, or Tailwind).
- **Copyable affordances:** Focus cards prioritize the next action, the reason it matters, and the stop rule. Buttons for copying handoff packets are present (currently disabled as placeholders until CR-WU-006).
- **Security:** All dynamic YAML fields are aggressively HTML-escaped to prevent script injection.
- **Read-only execution:** The CLI command never mutates the repo, executes commands, or calls models. The *only* write effect is creating the explicitly requested output file.

## Schema Additions

To support a friendly UX and agent handoffs, two new optional objects were added to the `work_items.yaml` schema:

### `ux`
- `short_label`: An abbreviated title for the dashboard header.
- `why_it_matters`: A one-line explanation of the item's value to help with motivation.
- `friendly_status`: A human-readable status (e.g., "Ready to start" instead of "ready").

### `handoff`
- `preferred_tool`: The agent/tool to use for implementation (e.g., "codex").
- `reviewer_tool`: The agent/tool to use for code review (e.g., "chatgpt").
- `prompt_style`: The desired framing style for the handoff.
- `stop_rule`: A clear boundary condition to prevent scope creep (e.g., "Stop after static HTML export works; do not add live GitHub import in this CR.").
- `return_format`: Expected output structures (e.g., `["changed_files", "tests_run", "unresolved_risks"]`).

## CLI Usage

Generate the static HTML dashboard by combining the master work items list and today's focus list:

```bash
tc workspace dashboard --items path/to/work_items.yaml --today path/to/today.yaml --output path/to/dashboard.html
```

Open `dashboard.html` in your browser to view the launchpad.
