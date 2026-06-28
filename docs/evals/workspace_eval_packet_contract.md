# Workspace Eval Packet Contract

## Purpose

This note freezes one canonical `workspace export-eval` packet example and defines how an independent evaluator should treat it. The packet is an observation and evidence input, not a decision record and not an approval artifact.

## Canonical Example

The canonical fixture lives at [`docs/examples/workspace_eval_packet.example.json`](../examples/workspace_eval_packet.example.json).

It is generated from:

- `docs/examples/workspace_work_items.example.yaml`
- `docs/examples/workspace_today.example.yaml`
- work item `DEMO-001`

with a fixed timestamp so the packet remains deterministic in-repo.

## Evaluator Interpretation

An independent evaluator may interpret the packet and return one of these statuses:

- `pass`
- `fail`
- `ambiguous`
- `not_evaluated`

Those statuses belong to the evaluator, not to TriageCore.

## Required Boundary Assumptions

- The packet is observation and evidence input only.
- The evaluator must not treat the packet as approval.
- The evaluator must not mutate source workspace files.
- The evaluator must not require TriageCore imports.
- TriageCore does not score this packet and does not claim an evaluator result inside the export.

## What The Packet Omits

- Raw `work_item.notes`
- Raw `today.notes`
- Local filesystem paths

Those omissions are intentional and are recorded in the packet's `omissions` block.

## Non-Goals

- No evaluator scoring logic in TriageCore
- No bidirectional sync with an evaluator
- No mutation of workspace state during export
- No import from `agent-control-evals`
