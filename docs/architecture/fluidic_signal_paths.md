# Fluidic Signal Paths

This note captures the "Fluidic" architecture metaphor for the Workspace Unifier while the current control boundaries are still fresh. It is a framing document only. It adds no runtime behavior, no new command surface, and no schema changes.

## The Fluidic Metaphor

The Workspace Unifier can be understood as a small local-first lab-on-chip for work control. Instead of imagining work as an unbounded stream of chat context, the Fluidic model treats it as routed flow through explicit control surfaces.

- **Channels** = typed handoff paths.
- **Valves** = approval gates and policy checks.
- **Reservoirs** = `work_items.yaml`, preview files, and evidence stores.
- **Sensors** = tests, evaluators, review views, and stale checks.
- **Backpressure** = blocked, stale, or high-risk warnings that deliberately slow flow.
- **Cross-contamination** = leakage of private notes, local paths, sensitive context, or scope drift.
- **Lab-on-chip** = the local-first workspace control plane as a compact, bounded system.

This metaphor matters because the Workspace Unifier is not trying to be a general-purpose orchestration engine. It is trying to keep flow visible, bounded, and reviewable.

## Component Roles

- **TriageCore** = contracts, schemas, CLI engine, gates, packets, and evidence.
- **TriageDesk** = human cockpit for approvals, review, evidence, and dashboard operation.
- **Meta-harness** = agent and session coordination layer.
- **Agents** = bounded execution or analysis workers.
- **Independent evaluator** = external assessment of whether observed behavior matched expected control boundaries.

In this model, TriageCore provides the typed channels and persistence rules. TriageDesk is where human judgment remains visible. The meta-harness can route work between sessions or agents, but it does not become an approval authority. Agents perform bounded work against the handoff they receive, not against an unlimited context pool. The independent evaluator measures observed behavior against the intended boundary model, but it also does not approve.

## Signal Flow

```text
Idea / GitHub issue / user request
  -> intake / preview
  -> clarify / promote
  -> focus
  -> handoff
  -> agent work
  -> evidence packet
  -> evaluator result
  -> human approval
  -> close / review
```

A slightly expanded reading of that flow:

- Intake and preview collect candidate work without immediately polluting the live board.
- Clarify and promote move selected work through an explicit valve into active tracking.
- Focus narrows the working set so the operator and agents are not flooded.
- Handoff converts selected work into a typed packet with purpose, constraints, stop rules, and checks.
- Agent work happens outside the control plane but within those bounds.
- Evidence packets and evaluator results flow back for inspection.
- Human approval remains distinct from both orchestration and evaluation.
- Close and review drain completed work, refresh the board, and expose stale or blocked items.

## Design Principles

- Context should flow through channels, not flood the workspace.
- Narrow typed handoffs beat broad context dumps.
- Valves before consequence.
- Reservoirs separate raw intake from active work.
- Sensors watch the flow.
- Backpressure is a feature.
- No cross-contamination.
- The meta-harness coordinates but does not approve.
- The evaluator assesses but does not approve.
- TriageDesk presents decisions; TriageCore preserves contracts and evidence.

## Why This Matters

The Fluidic model reduces cognitive load because it keeps the operator from rebuilding the same context from scratch every time work resumes. It protects private context by separating raw intake, active work, and outbound handoffs instead of letting everything mix together. It makes handoffs repeatable because packets and review artifacts are typed rather than improvised. It also preserves the difference between agent orchestration and human approval, which is easy to blur once multiple tools, sessions, and evaluators are involved.

## Non-Goals

- Not a public product rename.
- Not a trademark or branding claim.
- Not a new command surface.
- Not a replacement for TriageDesk.
- Not a replacement for the independent evaluator.
- Not a runtime orchestration engine.

## Boundary Notes

A few failure modes are worth naming explicitly:

- Cross-contamination happens when private notes, local filesystem paths, sensitive context, or adjacent-scope material leak into a handoff that should have remained narrower.
- Missing valves create silent mutation risk by allowing promotion, closure, or approval-like behavior to happen without an explicit control point.
- Missing backpressure leads to overloaded boards, stale focus lists, and agents acting on work that should have been paused for clarification.
- Sensors only help if their outputs remain reviewable and subordinate to human judgment.

The intended result is a workspace that behaves less like an overflowing inbox and more like an inspectable signal path: bounded inputs, typed transfers, clear gates, visible evidence, and human decisions at the consequential steps.
