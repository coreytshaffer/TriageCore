# Current Backlog

## Status

This document summarizes the active TriageCore backlog after CR-021 through CR-024.

## Active GitHub Backlog

- Issue #4: Persistent cryptographic agent identities
  - Status: open
  - Related CR: CR-020
  - Purpose: add persistent local agent identities, signed ledger-event metadata, revocation, capability checks, and crypto-agile algorithm metadata.
  - Current phase: identity foundation, signing helpers, signed `route_audit`, verification CLI, identity init/list/check/revoke, CR-027 key hardening, CR-028 signed smoke-path evidence, and CR-030 rotation/recovery policy complete
  - Next gate: runtime rotation design and any decision about expanding signing beyond `route_audit`

## Candidate Future Work

- Runtime integrity and model provenance enforcement
  - Source: CR-031 policy baseline
  - Status: candidate future CR, not yet active GitHub backlog
  - Purpose: add operator-facing model or route integrity checks so convenience
    wrappers, aliases, and mutable tags do not become implicit trust
    boundaries.

- Circuit breakers and degraded mode states
  - Source: older Drive performance backlog
  - Status: candidate future CR, not yet active GitHub backlog
  - Purpose: allow unstable routes to cool down instead of retrying immediately.

## Completed Safety Spine

- CR-021: Persistent Artifact Privacy Invariant
- CR-022: Context Facet Pruning Plan
- CR-023: Offline Demo Dry-Run Evidence
- CR-024: Persistent Artifact Audit Command
- CR-026: Post-Identity Privacy and Security Audit
- CR-027: Identity Key Hardening and Consistency Check
- CR-028: Signed Smoke-Path Evidence
- CR-029: Identity Revocation CLI
- CR-030: Identity Rotation and Recovery Policy
- CR-031: Runtime Integrity and Model Provenance Policy
- CR-032: Model Route Manifest Schema
- CR-033: Model Manifest Check CLI

## Current Recommendation

Keep Issue #4 open and pause signing expansion beyond `route_audit`.
Private-key permission and consistency checks plus metadata-only signed smoke
evidence plus identity revocation are now implemented, and rotation/recovery
policy is now documented. Runtime rotation behavior still needs a separate
implementation slice before adding signed event types.

Treat CR-031 as the policy baseline for any future `tc model check`, route
manifest, or backend provenance work. Runtime integrity enforcement should stay
separate from convenience-adapter support.

Treat CR-032 as the artifact contract for future runtime validation. `CR-033`
should validate manifests against this schema instead of inventing provenance
rules ad hoc in code.

Future runtime-integrity work should build on CR-033 by adding richer
manifests, route discovery, or backend-aware checks without collapsing policy,
artifact shape, and live enforcement into one step.
