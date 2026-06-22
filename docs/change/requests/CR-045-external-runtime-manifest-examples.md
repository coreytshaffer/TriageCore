# CR-045: External Runtime Manifest Examples

## Status

Implemented

## Scope

- add vendor-neutral external runtime manifest examples
- show what safe read-only and draft-only manifests look like under the CR-044
  schema
- add one intentionally invalid authority-incomplete example for future
  validation and review work
- update backlog framing so interoperability remains example-first,
  adapter-later

## Non-Scope

- do not add manifest validation code
- do not add adapter or driver code
- do not add OpenClaw-specific runtime admission yet
- do not add shell, browser, plugin, skill, or network execution
- do not grant mutation authority
- do not add cloud escalation
- do not change runtime behavior

## Implementation Authority

Documentation-only repo slice.

## Description

This change adds vendor-neutral examples for the external runtime manifest
schema introduced in CR-044. The examples are deliberately narrow: a read-only
summary runtime, a draft-only runtime, and an intentionally invalid manifest
that demonstrates fields future authority-sensitive validation should reject.
The goal is to make the contract concrete before any adapter stub or runtime
admission work exists.

## Acceptance Criteria

- [x] `docs/integrations/examples/external_runtime_manifest_read_only.yaml`
  exists and represents a read-only external runtime.
- [x] `docs/integrations/examples/external_runtime_manifest_draft_only.yaml`
  exists and represents draft-only behavior without mutation authority.
- [x] `docs/integrations/examples/external_runtime_manifest_invalid_unknowns.yaml`
  exists and represents an intentionally invalid authority-incomplete manifest.
- [x] `docs/current_backlog.md` reflects the example slice and keeps adapter and
  execution work out of scope.
- [x] No runtime code changes.

## Validation

```powershell
git diff --stat
git diff --check
git status --short
```