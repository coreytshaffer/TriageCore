# Workspace Board + WBS Views

> **CR-WU-002** — Read-only orientation surfaces for TriageCore work items.

## Purpose

The workspace board reduces **orientation cost** when switching between projects.
Instead of manually reconstructing "what is active, what is blocked, and what
comes next," you run one command and get a current-state view.

This is an **orientation system**, not a project management system:

| Orientation system | Project management system |
|---|---|
| Shows what matters now | Tracks everything |
| Optimized for starting | Optimized for reporting |
| Reduces restart cost | Can become maintenance burden |
| Lightweight | Often heavy |
| Answers "what do I do next?" | Asks "what is the status?" |

## Schema

Work items combine five layers:

| Layer | Purpose | Required? |
|---|---|---|
| **Kanban** | Flow state (status + priority) | ✅ Yes |
| **PMI** | Governance (process group, deliverable, acceptance criteria) | Optional |
| **GTD** | Next-action discipline (next action, context, energy) | Optional (but `next_action` required if section present) |
| **WBS** | Hierarchy (area, package, component) | Optional |
| **Risk** | Risk register (probability, impact, response strategy) | Optional |

### Required fields (per item)

- `id` — Unique identifier (e.g., `CR-WU-002`)
- `project` — Project slug (e.g., `triagecore`)
- `title` — Human-readable title
- `type` — Work item type (e.g., `feature`, `bug`, `documentation`)
- `kanban.status` — Current flow state
- `kanban.priority` — Current priority

### Allowed values

| Field | Values |
|---|---|
| `kanban.status` | `backlog`, `ready`, `active`, `review`, `blocked`, `done`, `parked` |
| `kanban.priority` | `critical`, `high`, `medium`, `low`, `someday` |
| `pmi.process_group` | `initiating`, `planning`, `executing`, `monitoring-controlling`, `closing` |
| `pmi.lifecycle_model` | `predictive`, `agile`, `hybrid`, `research`, `operational` |
| `gtd.list` | `inbox`, `next-actions`, `waiting-for`, `someday-maybe`, `reference` |
| `gtd.energy` | `low`, `medium`, `high` |
| `risk.level` | `low`, `medium`, `high` |
| `risk.register[].probability` | `low`, `medium`, `high` |
| `risk.register[].impact` | `low`, `medium`, `high` |
| `risk.register[].response_strategy` | `avoid`, `mitigate`, `transfer`, `accept`, `escalate` |
| `data_sensitivity` | `low`, `medium`, `high` |

### JSON Schema

The full JSON Schema is at [`schemas/workspace_work_items.schema.json`](../schemas/workspace_work_items.schema.json).
This schema is a documentation and interoperability artifact. Runtime validation
is done in Python via dataclass + enum parsing.

## CLI Usage

### Board view

```bash
# Show all statuses
tc workspace board --items path/to/work_items.yaml

# Filter to active workflow
tc workspace board --items path/to/work_items.yaml --status active,ready,review,blocked
```

**Output:**

```
# Workspace Board

## Active

| Priority | Project | ID | PMI Phase | Work Item | Risk | Next Action |
|---|---|---|---|---|---|---|
| high | example-control-plane | DEMO-001 | executing | Implement workspace registry schema | medium | Implement schema loader and brief renderer |

## Review

| Priority | Project | ID | PMI Phase | Work Item | Risk | Next Action |
|---|---|---|---|---|---|---|
| medium | example-monitoring | DEMO-003 | monitoring-controlling | Clarify resource freshness vs observation freshness | low | Review public claims language for accuracy |
```

### WBS view

```bash
tc workspace wbs --items path/to/work_items.yaml
```

**Output:**

```
# Work Breakdown Structure

## Ai Control Plane

### example-control-plane

**registry**

- `DEMO-001` Implement workspace registry schema [active] [high]

**rotation**

- `DEMO-005` Agent identity rotation smoke tests [done] [high]
```

## Private/Public Separation

- **Public** (in the repo): Schema, loader, renderer, CLI, example file, tests, docs.
- **Private** (outside the repo): Your real `work_items.yaml` with actual project data.

Keep real work-item files in `~/.triagecore/` or similar. The example file at
[`docs/examples/workspace_work_items.example.yaml`](examples/workspace_work_items.example.yaml)
uses fictional projects only.

## Fail-Closed Behavior

| Condition | Result |
|---|---|
| Missing file | `FileNotFoundError` with clear path |
| Malformed YAML/JSON | `ValueError` with parser error details |
| Unknown status/priority/risk value | `ValueError` naming the field, item ID, and allowed values |
| Missing required field | `ValueError` naming the field and item index/ID |
| Unsupported file extension | `ValueError` listing supported extensions |
| Unsupported schema version | `ValueError` with version number |
| Empty items list | Valid — prints "No work items found." |

## Design Invariants

1. **Read-only.** Never writes files, executes commands, calls APIs, or invokes models.
2. **Fail-closed.** All validation errors are loud and specific.
3. **No private data.** Example files use fictional data only.
4. **Deterministic output.** Same input → same output, every time.
