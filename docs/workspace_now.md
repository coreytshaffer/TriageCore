# Workspace Now Focus View

> **CR-WU-003** — Read-only focus surface for TriageCore work items.

## Purpose

The Workspace Now view provides a tightly focused summary of what matters **today**.
While the board and WBS views show the entire orientation substrate of all projects,
the `now` view filters down to only:
1. The intentional items you chose to focus on.
2. Any items currently blocked (requiring unblocking).
3. Any items waiting for your review.

This is **not** a task scheduler or a reminder system. It is simply an answer to:
> "What did I intentionally choose to focus on today?"

## `today.yaml` Schema

The `today.yaml` file defines the focus list and optional daily limits.

| Field | Purpose | Required? |
|---|---|---|
| `date` | Optional ISO 8601 string for intent tracking | No |
| `focus` | List of work item IDs to focus on | ✅ Yes |
| `limits.max_active_items` | Threshold before issuing a warning on item count | No |
| `limits.max_high_risk_items` | Threshold before issuing a warning on risk | No |
| `notes` | General notes or reminders for the day | No |

### Example

```yaml
date: 2026-06-27

focus:
  - CR-WU-003
  - CC-RECALL-001
  - CLW-FRESHNESS-001

limits:
  max_active_items: 3
  max_high_risk_items: 1

notes:
  - "Close one slice before opening another."
```

## CLI Usage

```bash
tc workspace now --items path/to/work_items.yaml --today path/to/today.yaml
```

**Output:**

```text
Workspace Now
=============

Focus:
1. CR-WU-003 | triagecore | Workspace Now Focus View
   Next: implement today.yaml loader and focus renderer
   Tool: codex
   Risk: medium

2. CC-RECALL-001 | cyber-commons-lab | Right of recall with encryption
   Next: draft recall state machine
   Tool: chatgpt
   Risk: medium

Warnings:
- Focus list contains 2 medium/high risk items; limit is 1.

Blocked:
- ST-VMS-001 | safetask-ai | Real camera/VMS integration boundary
  Blocker: Privacy/NAS boundary plan not ready

Review:
- ACE-REVIEW-001 | agent-control-evals | Human approval boundary reviewer polish
  Next: Polish README and status packet language for reviewer clarity
```

## Design Invariants

1. **Read-only.** Never writes files or changes state.
2. **Fail-closed.** If a focus ID does not exist in the main `work_items.yaml`, the command fails loudly.
3. **No magic.** It does not auto-populate the focus list or auto-schedule anything. You must manually construct `today.yaml`.
