# Current Backlog

## Status

This document summarizes the active TriageCore backlog after CR-021 through CR-024.

## Active GitHub Backlog

- Issue #4: Persistent cryptographic agent identities
  - Status: open
  - Related CR: CR-020
  - Purpose: add persistent local agent identities, signed ledger-event metadata, revocation, capability checks, and crypto-agile algorithm metadata.
  - Current phase: Phase 5 identity initialization CLI in progress

## Candidate Future Work

- Circuit breakers and degraded mode states
  - Source: older Drive performance backlog
  - Status: candidate future CR, not yet active GitHub backlog
  - Purpose: allow unstable routes to cool down instead of retrying immediately.

## Completed Safety Spine

- CR-021: Persistent Artifact Privacy Invariant
- CR-022: Context Facet Pruning Plan
- CR-023: Offline Demo Dry-Run Evidence
- CR-024: Persistent Artifact Audit Command

## Current Recommendation

Continue CR-020 in small phases. Phase 5 should remain limited to operator
identity initialization and safe public metadata inspection before any broader
TaskLedger signing expansion.
