# CR-044: External Runtime Manifest Schema

## Status

Implemented

## Scope

- define a vendor-neutral manifest shape for external runtimes
- document the minimum identity, authority, and revocation fields required
  before any external runtime can participate in TriageCore workflows
- keep the contract separate from any one runtime example or adapter
- update backlog framing so the next slices remain example-first and
  adapter-later

## Non-Scope

- do not add OpenClaw-specific manifest data yet
- do not add an adapter, driver, or execution pathway
- do not implement manifest validation code
- do not add plugin, skill, browser, shell, or network execution
- do not widen the current approval or authority surface

## Implementation Authority

Documentation-only repo slice.

## Description

This change defines the canonical manifest contract an external runtime must
present before TriageCore can reason about it safely. The manifest is
vendor-neutral and authority-focused: it identifies the runtime, records the
capability and tool-policy boundary it claims, states whether approval and
provenance are mandatory, and makes revocation support explicit. This keeps the
contract ahead of any OpenClaw example or adapter implementation so a later
runtime cannot define the schema by accident.

## Acceptance Criteria

- [x] `docs/integrations/external_runtime_manifest_schema.md` exists and defines
  the canonical external runtime manifest shape.
- [x] The schema includes explicit fields for runtime identity, authority
  boundary, model identity, approval expectation, provenance expectation, and
  revocation support.
- [x] `docs/current_backlog.md` sequences this work ahead of any runtime example
  or adapter slice.
- [x] No runtime code changes.
- [x] No external runtime dependency added.

## Validation

```powershell
git diff --stat
git diff --check
git status --short
```
