# Task Envelope Template

Use this template before non-trivial TriageCore work so the operator, Codex, Antigravity, and later reviewers can answer the same bounded questions from one document.

## Copyable Template

```markdown
# Task Envelope

## Identity

- Task: `CR-XXX Short Title`
- Repo: `TriageCore`
- Operator: `name or agent`
- Date: `YYYY-MM-DD`
- Status: `draft | ready for preflight | in progress | blocked | ready for review | closed`

## Objective

State the smallest useful outcome for this slice in 1-3 sentences.

## Route And Risk

- Route: `local/docs-only | local/code | bounded external-safe review | human-only`
- Risk: `LOW | MEDIUM | HIGH | BLOCKED`
- Why this risk level applies:

Risk language:
- `LOW`: docs-only, no runtime behavior
- `MEDIUM`: tests or bounded implementation
- `HIGH`: runtime routing, identity, secrets, or external systems
- `BLOCKED`: policy violation or missing approval

## Allowed And Forbidden Scope

### Allowed Files

- `path/to/file`
- `path/to/file`

### Forbidden Files Or Areas

- `secrets`
- `.triagecore`
- `runtime adapters`

### Explicit Non-Scope

- item
- item

## Agent Lanes

### Codex Lane

- bounded implementation or drafting work
- targeted tests or validation
- branch hygiene

### Antigravity Lane

- docs review
- stability analysis
- backlog shaping

### Human Lane

- scope judgment
- commit approval
- merge authority
- risk acceptance

## Approval Gates

- [ ] preflight
- [ ] commit
- [ ] push
- [ ] PR
- [ ] merge

## Preflight Checks

- [ ] allowed files reviewed
- [ ] forbidden areas confirmed untouched
- [ ] privacy boundary checked
- [ ] source files verified before editing
- [ ] validation plan written

## Evidence

### Existing Evidence

- `CR reference`
- `relevant tests`
- `prior docs`

### Evidence To Produce

- `diff`
- `validation output`
- `handoff note`

## Failure Modes And Allowed Next Steps

Example format:

Blocked: this task touches runtime adapter files, but the task envelope is docs-only.

Allowed next steps:
1. revise the task envelope
2. move the runtime change to a new CR
3. discard the runtime file change

## Operator Summary

Task: `CR-XXX Short Title`
Repo: `TriageCore`
Risk: `LOW`
Route: `LOCAL / DOCS-ONLY`
Allowed files: `docs/...`
Blocked files: `secrets`, `.triagecore`, `runtime adapters`
Approval gates: `commit`, `push`, `PR`, `merge`
Status: `Ready for human review`
```

## Notes

- Prefer one envelope per bounded slice.
- Keep the allowed-file list narrow enough that a reviewer can audit it quickly.
- If the route or risk changes materially, update the envelope before continuing.
- If validation cannot be run, state the exact blocker in the Evidence section.
