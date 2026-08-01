# Workspace Unifier Promotion, Handoff, and Review Flow

## Status and Verification Basis

**Level 3 — current subsystem flow plus disconnected external steps.** Verified against
local `main` at `6d585268` on 2026-08-01. Re-pinned after CR-DD-013's documentation-only
closeout; no production, test, workflow, schema, or architecture file changed between the
two pins.

## Claim Supported

The Workspace Unifier keeps candidate imports separate from live work state, requires an
explicit human promotion to cross that boundary, exports bounded handoff and evaluator
packets without delivering or executing them, and keeps evaluator signals separate from the
human decision and explicit closure path.

```mermaid
sequenceDiagram
    actor Human as Human operator
    participant TC as TriageCore Workspace Unifier
    participant Preview as Preview artifact
    participant State as work_items.yaml / today.yaml
    participant Handoff as Static handoff packet
    participant Agent as External bounded agent (disconnected)
    participant Evidence as External work evidence
    participant EvalInput as Static evaluator-input JSON
    participant Evaluator as Independent evaluator (external)
    participant Desk as TriageDesk review / evaluator display

    Human->>TC: Candidate idea or explicit GitHub import
    TC->>Preview: Validate and write candidate preview
    TC->>Human: review-import output
    Note over Human,State: Promotion valve: preview is not live state
    Human->>TC: Explicitly select item(s) to promote
    TC->>State: Validated promotion into live work registry
    Human->>State: Author today.yaml focus intent
    Human->>TC: Select focused item and request handoff
    TC->>Handoff: Render bounded packet; omit private notes by default
    Handoff->>Human: Static export only
    Human-->>Agent: Separate delivery outside Workspace Unifier
    Agent-->>Evidence: Work artifacts + checks + unresolved risks
    Human->>TC: Export evaluator input for selected item
    TC->>EvalInput: Selective static JSON; omit notes/local paths
    Human-->>Evaluator: Separate external evaluator workflow
    Evaluator-->>Desk: Static result JSON; observation only
    Evidence-->>Desk: Reviewable work evidence
    Desk->>Human: Present evidence and evaluator signals
    Note over Human,Desk: Approval valve: only the operator decides
    Human->>TC: Explicit close/touch/write intent
    TC->>State: Validate and persist allowed state change
```

Solid arrows are current Workspace Unifier operations. Dashed arrows cross a disconnected
delivery, execution, or evaluator boundary.

## Promotion Gate

`workspace_github_import` writes a preview artifact. `workspace_review_import` renders that
candidate state. `workspace_promote` requires an explicit selection and produces validated
live registry state. The preview does not become `work_items.yaml` by observation, import,
or agent action alone.

## Handoff Gate

`workspace_handoff` selects one work item and renders a tool-specific text, Markdown, or
JSON packet with objective, constraints, checks, stop rule, and return format. Private notes
are omitted by default. The module does not deliver the packet, invoke a meta-harness, or
run an agent.

## Evaluation Gate

`workspace_eval_packet` exports selective static evaluator input. It does not invoke the
evaluator, import evaluator code, score the packet, or produce a result. Evaluator execution
and result production remain external. TriageDesk's evaluator result handling is
observation-only and rejects approval- or execution-claiming results as unsafe/invalid.

## Human Decision and Closure

Agent reports, checks, and evaluator outputs remain evidence. Only the human operator makes
the approval decision. `workspace_close` and `workspace_touch` require explicit write intent;
orientation views do not silently mutate state.

## Authoritative Sources Verified

- `triage_core/workspace_github_import.py`
- `triage_core/workspace_review_import.py`
- `triage_core/workspace_promote.py`
- `triage_core/workspace_board.py`, `workspace_now.py`, `workspace_review.py`, and
  `workspace_dashboard.py`
- `triage_core/workspace_handoff.py`
- `triage_core/workspace_eval_packet.py`
- `triage_core/workspace_close.py` and `workspace_touch.py`
- `triage_core/evaluator_result.py` and `evaluator_result_history.py`
- `triage_core/triagedesk_adapter.py`
- `schemas/workspace_work_items.schema.json` and `schemas/workspace_today.schema.json`
- Focused tests in `tests/test_workspace_*.py`, `tests/test_evaluator_result.py`,
  `tests/test_evaluator_result_history.py`, and `tests/test_triagedesk_adapter.py`

## Non-Claims

- No claim that Workspace Unifier delivers handoffs or executes agents.
- No claim that TriageCore invokes an evaluator or produces evaluator results.
- No claim that TriageDesk has a current action/executor bridge.
- No claim that a passing check or evaluator result grants approval.
- No claim that imports automatically enter the live registry.
- No claim that the meta-harness or an agent is a source of truth.

## Related Pages

- [Workspace Unifier Architecture](workspace_unifier_architecture.md)
- [Fluidic Signal Paths](fluidic_signal_paths.md)
- [Current System Architecture](current_system_architecture.md)
