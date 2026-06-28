# Workspace Evaluator Preview

## Purpose

`tc workspace export-eval` exports a static evaluator-input packet from Workspace Unifier state. The packet is meant for external assessment workflows that need structured workspace observations without importing TriageCore internals or letting TriageCore score itself.

## Boundary

- TriageCore exports evaluator-ready packets.
- The independent evaluator assesses them.
- TriageCore does not import, invoke, or depend on the evaluator.
- The evaluator does not approve actions.
- Human approval remains outside this packet export.

## Command

```powershell
python -m triage_core.tc_cli workspace export-eval --items docs/examples/workspace_work_items.example.yaml --today docs/examples/workspace_today.example.yaml --id DEMO-001 --output actuals/workspace_demo-001.json
```

## Packet Shape

Example shape:

```json
{
  "schema_version": "workspace_evaluator_input_v1",
  "packet_kind": "workspace_evaluator_input",
  "case_id": "workspace_demo-001",
  "source": {
    "system": "TriageCore",
    "subsystem": "Workspace Unifier",
    "export_command": "tc workspace export-eval"
  },
  "boundary": {
    "triagecore_scores_packet": false,
    "external_evaluator_required": true,
    "evaluator_can_approve": false,
    "approval_authority": "human"
  },
  "work_item": {
    "id": "DEMO-001",
    "project": "example-control-plane",
    "title": "Implement workspace registry schema",
    "status": "active",
    "priority": "high"
  },
  "focus_context": {
    "today_file_present": true,
    "in_today_focus": true,
    "focus_rank": 1
  },
  "evidence_summary": {
    "required_checks": ["python -m pytest tests/test_workspace_board.py"],
    "external_reference": {
      "source": null
    }
  },
  "observations": [
    {"code": "kanban_status", "value": "active"},
    {"code": "in_today_focus", "value": true}
  ]
}
```

## Privacy And Omission Rules

The export is intentionally selective.

- Raw `work_item.notes` are omitted.
- Raw `today.notes` are omitted.
- Local filesystem paths are not embedded in the packet.
- The packet records omissions so an evaluator can tell what was intentionally excluded.

## What This Does Not Do

- It does not score outcomes.
- It does not import fixtures or code from `agent-control-evals`.
- It does not approve actions.
- It does not mutate workspace items.
- It does not claim the evaluator result inside TriageCore.
