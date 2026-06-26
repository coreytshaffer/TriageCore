# TriageDesk GUI Plan (TD-001)

## Purpose
TriageDesk is designed to be a **calm, read-only operator console** layered over the stable daily-driver baseline capabilities of TriageCore. It provides a safer and more visual way to inspect system state, estimate context budgets, and prepare bounded handoff packets without expanding execution authority or hiding operations from the operator.

## Current Inventory
- **Existing Surface**: An initial GUI exists at `triage_core/ui/app.py`.
- **Current Structure**: It is a monolithic ~3,700-line `customtkinter` application containing multiple internal backup artifacts. It directly manages state, renders gauges, tracks sustainability/ledger logs, and serves as a highly coupled `TriageDeskApp`.
- **Improvement Path**: Do not rewrite or modify `app.py` directly yet. The safest approach is to build an **adapter layer** underneath it (making TriageDesk consume stable Python interfaces rather than scraping strings or reimplementing logic). Once the adapter layer exists, the GUI can be refactored or replaced to wrap the daily-driver CLI logic seamlessly.

## Read-only / Default-Safe Boundaries
1. **No autonomous execution**: TriageDesk will not execute workflows or external tools independently.
2. **No hidden approvals**: The GUI will not approve packets; it only prepares and visualizes them.
3. **No background task mutation**: Operations are deterministic and read-only.
4. **No network/tool execution**: The GUI strictly interacts with the local ledger and environment.
5. **Honestly surface uncertainty**: If a field is unavailable or dry-run estimates are uncertain, the GUI must display that clearly.

## Proposed Views and Data Sources
TriageDesk will present five core views, mapped directly to the existing CLI baseline:

1. **Status View**: 
   - **Wraps**: `tc status`
   - **Data Source**: Core ledger and config state.
2. **Doctor View**: 
   - **Wraps**: `tc doctor`
   - **Data Source**: `diagnostics.py` environment checks.
3. **Review Queue View**: 
   - **Wraps**: `tc review list`
   - **Data Source**: `review_queue.py` (read-only listing of pending packets).
4. **Context Planner View**: 
   - **Wraps**: `tc context plan`
   - **Data Source**: `token_budget.py` and `context_planner.py` (dry-run estimating fit against selected model profiles).
5. **Packet Renderer View**: 
   - **Wraps**: `tc packet render`
   - **Data Source**: `packet_renderer.py` (combining a task file, includes, and context planner budget bounds).

## What the GUI Must NOT Do
- It must not execute models or agents.
- It must not act as a live workflow controller.
- It must not bypass human-in-the-loop (HITL) gates.
- It must not overwrite local configurations or ledgers directly; it only reads them and outputs bounded artifacts (like rendering a packet).

## Implementation Backlog
1. **[x] TD-002: Add GUI adapter layer with no UI dependency**
   - Create a pure-Python adapter layer that bridges `TriageDesk` with `diagnostics.py`, `review_queue.py`, `context_planner.py`, `packet_renderer.py`, and `token_budget.py`. Ensure TriageDesk calls these stable functions instead of re-implementing logic. (Completed)
2. **[x] TD-003: Read-only status panel wiring**
   - Added an Operator Status panel to the TriageDesk dashboard powered by the adapter layer. Displays repo status, ledger state, last event, pending reviews, and adapter connectivity. (Completed)
4. **[x] TD-004: TriageDesk review queue panel**
   - Added a read-only review queue panel to the TriageDesk dashboard powered by the adapter layer. (Completed)
5. **[x] TD-005: Read-only Context Planner panel**
   - Added a dedicated sidebar tab for Context Planner dry-runs. Evaluates token budgets, estimates inputs, and provides recommendations without writing packets. (Completed)
6. **[x] TD-006: Packet Preview UI integration**
   - Wired up the UI for `packet render` dry-runs within the Context Planner tab, producing safely bounded deterministic outputs visually in a read-only textbox without executing or mutating. (Completed)
