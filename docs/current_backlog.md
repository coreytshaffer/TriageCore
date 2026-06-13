# Current Backlog

## Status

This document summarizes the active TriageCore backlog after CR-021 through CR-024.

## Active GitHub Backlog

- Issue #4: Persistent cryptographic agent identities
  - Status: open
  - Related CR: CR-020
  - Purpose: add persistent local agent identities, signed ledger-event metadata, revocation, capability checks, and crypto-agile algorithm metadata.
  - Current phase: Phase 2 signing foundation in progress

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

Continue CR-020 in small phases. Phase 2 should remain limited to local key
generation, public identity registration, signing and verification helpers,
tamper-failure checks, and authorization gating before any live TaskLedger
integration work.
