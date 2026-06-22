# CR-043: External Runtime Integration Doctrine

## Status

Implemented

## Scope

- add a vendor-neutral integration doctrine for external runtimes
- document the compatibility-without-capture rule
- define the authority invariant for external tools
- document OpenClaw as the first bounded example
- update backlog framing so this work stays docs-only and behind the current
  security gate

## Non-Scope

- do not install or run OpenClaw
- do not add adapter or driver code
- do not add shell execution pathways
- do not add plugin or skill loading
- do not add network exposure
- do not add any new authority surface

## Implementation Authority

Documentation-only repo slice.

## Description

This change adds a small doctrine-first integration slice for external runtimes.
 It defines the line between interoperability and capture, states that external
 runtimes may request capability but only TriageCore grants authority, and uses
 OpenClaw as the first documented boundary example. The slice is intentionally
 docs-only so it does not widen the current attack surface or jump ahead of the
 security gate.

## Acceptance Criteria

- [x] `docs/integrations/integration_doctrine.md` exists and defines the
  authority and replaceability invariants.
- [x] `docs/integrations/openclaw_boundary.md` exists and defines OpenClaw as a
  subordinate external runtime.
- [x] `docs/current_backlog.md` reflects this doctrine work as docs-only and
  security-gated.
- [x] No runtime code changes.
- [x] No OpenClaw dependency added.

## Validation

```powershell
git diff --stat
git diff --check
git status --short
```
