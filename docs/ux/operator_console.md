# Operator Console

This note defines the operator UX target for TriageCore as a daily governance sidecar. The goal is not to make the system feel powerful. The goal is to make safe behavior the easiest behavior while keeping scope, risk, and evidence visible.

## UX North Star

At a glance, the operator should be able to answer:

1. What am I working on?
2. What tools or agents are involved?
3. What is allowed?
4. What still needs human approval?
5. What evidence exists if I need to reconstruct this later?

If the interface hides one of those answers, it is not ready.

## Design Principles

### Calm, Not Casual

The interface should reduce burden without making risky actions feel trivial. TriageCore should feel legible, steady, and hard to misuse.

### Safety Must Stay Visible

Approval gates, forbidden paths, route boundaries, and validation status should stay on the main surface instead of being buried in secondary views.

### Evidence Before Automation

A task should accumulate inspectable artifacts before it accumulates more autonomy. Reports, preflight records, and review notes come before launch controls.

### Agent Lanes, Not Magical Agents

Codex, Antigravity, and the human operator should appear as separate lanes with explicit responsibilities. This keeps handoffs teachable and auditable.

### Fail Closed, Explain Clearly

Failure messages should say what was blocked, why, and which next steps are allowed.

## Recommended Surface Order

### 1. CLI Polish First

TriageCore already has a command-oriented workflow. The first UX priority is to make the CLI easier to operate without requiring the user to remember every governance field.

Current commands already in the repo include:

- `tc preflight`
- `tc status`
- `tc audit`
- `tc propose`
- `tc doctor`

Future CLI grouping can unify these into a more task-centered surface after a separate implementation CR. A likely direction is a `tc task ...` family that wraps the existing workflow without removing explicit review.

### 2. Markdown Operator Reports Second

The next surface should be a clean Markdown summary that can be read in the repo, pasted into a handoff, or attached to review material.

Target shape:

```text
Task: CR-050 Operator UX And Task Envelope Console
Repo: TriageCore
Risk: Low
Route: Local / Docs-only
Allowed files: docs/ux, docs/operations, docs/change
Blocked files: secrets, .triagecore, runtime adapters
Approval gates: commit, push, PR, merge
Status: Ready for human review
```

### 3. Textual TUI Third

A Textual-based terminal UI is a strong fit once the CLI fields and report shape are stable. The first TUI should be read-only or near-read-only so it acts as a control panel rather than a hidden execution layer.

Illustrative layout:

```text
+-- TriageCore Operator Console ----------------------------+
| Active Task: CR-050 Operator UX And Task Envelope Console |
| Risk: LOW        Route: LOCAL / DOCS-ONLY                 |
| Status: PREFLIGHT PASSED                                  |
+-----------------------+-----------------------------------+
| Allowed Files         | Approval Gates                    |
| docs/ux/              | [ ] Commit                        |
| docs/operations/      | [ ] Push                          |
| docs/change/          | [ ] PR                            |
|                       | [ ] Merge                         |
+-----------------------+-----------------------------------+
| Agent Lanes                                                |
| Codex: implementation worker                               |
| Antigravity: docs and review worker                        |
| Human: merge authority                                     |
+------------------------------------------------------------+
| Recent Evidence                                            |
| [x] docs-only scope                                        |
| [x] explicit approval gates                                |
| [x] task-envelope template added                           |
+------------------------------------------------------------+
```

## UX Elements To Prioritize

### Task Envelope Wizard

Future CLI or TUI flows should guide the operator through:

- repo
- CR number
- task title
- allowed files
- forbidden files
- risk level
- Codex role
- Antigravity role
- approval gates

The wizard should produce a reusable artifact, not just ephemeral prompts.

### Risk Badges

Use consistent bounded labels:

- `LOW`: docs-only, no runtime behavior
- `MEDIUM`: tests or bounded implementation
- `HIGH`: runtime routing, identity, secrets, external systems
- `BLOCKED`: policy violation or missing approval

### Agent Lane Cards

Represent responsibilities as explicit lanes:

- Codex lane: bounded implementation, tests, branch hygiene
- Antigravity lane: docs review, stability analysis, backlog shaping
- Human lane: scope judgment, commit approval, merge authority, risk acceptance

### Evidence Drawer

Every task surface should make it easy to inspect:

- preflight result
- route or policy checks
- changed files
- validation performed
- handoff artifacts
- PR link when one exists

## Failure Message Pattern

Avoid vague blocking messages such as:

```text
ERROR: policy violation
```

Prefer messages that preserve control:

```text
Blocked: this task touches runtime adapter files, but the task envelope is docs-only.

Allowed next steps:
1. revise the task envelope
2. move the runtime change to a new CR
3. discard the runtime file change
```

## What To Avoid Early

Do not start the UX path with:

- full web dashboard
- multi-agent auto-routing launch surface
- auto-merge controls
- secret-management UI
- background daemons

These add surface area faster than they add trustworthy operator control.

## Follow-On CR Sequence

Keep UX changes narrow and reviewable:

1. `CR-050`: operator UX and task-envelope console docs
2. `CR-051`: CLI task-envelope wizard MVP
3. `CR-052`: Markdown task report export
4. `CR-053`: Textual read-only operator dashboard

That sequence keeps interface work subordinate to the governance model instead of racing ahead of it.

