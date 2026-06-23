# Current Backlog

## Status

This document summarizes the active TriageCore backlog after CR-074.

## Active GitHub Backlog

- Issue #4: Persistent cryptographic agent identities
  - Status: open
  - Related CR: CR-020
  - Purpose: add persistent local agent identities, signed ledger-event metadata, revocation, capability checks, and crypto-agile algorithm metadata.
  - Current phase: identity foundation, signing helpers, signed `route_audit`, verification CLI, identity init/list/check/revoke, CR-027 key hardening, CR-028 signed smoke-path evidence, and CR-030 rotation/recovery policy complete
  - Next gate: runtime rotation design and any decision about expanding signing beyond `route_audit`

## Candidate Future Work

- Operator UX implementation path
  - Source: CR-051, CR-052, CR-053, CR-054, CR-055, CR-056, CR-057, CR-058, CR-059, CR-060, CR-061, CR-062, CR-063, CR-064, CR-065, CR-066, CR-067, CR-068, CR-069, CR-070, CR-071, CR-072, CR-073, and CR-074
  - Status: design, template, markdown renderer, CLI preview/draft/wizard commands, CLI documentation, admission CLI smoke coverage, no-mutation invariant coverage, contract documentation, contract linkage, fixture drift coverage, and review bundle dry-run support complete; TUI and dashboard work remain future slices
  - Purpose: keep operator UX calm, legible, and evidence-first without jumping straight to a web dashboard or hidden automation surface.

- External runtime execution admission evidence
  - Source: CR-050 admission evidence record
  - Status: evidence structure complete; ledger integration remains future work
  - Purpose: audit the admission of proposals separately from their execution.

- CLI task-envelope wizard MVP
  - Source: CR-051 follow-on sequence
  - Status: candidate future CR, not yet active GitHub backlog
  - Purpose: guide the operator through task scope, allowed files, risk, agent lanes, and approval gates without requiring memorized fields.



- Textual read-only operator dashboard
  - Source: CR-051 follow-on sequence
  - Status: candidate future CR, not yet active GitHub backlog
  - Purpose: provide a calm terminal control panel for status, approvals, scope, and evidence after CLI/report fields stabilize.

- External runtime execution boundary stub
  - Source: CR-049 execution-path boundary stub
  - Status: stub caller complete; routing policy and admission tokens remain future work
  - Purpose: enforce structural and policy boundaries by ensuring proposals must pass `admit_external_runtime` before proceeding.

- External runtime manifest examples
  - Source: CR-045 docs-only example slice
  - Status: documentation-only slice complete; adapter and execution work remain
    gated
  - Purpose: show what safe read-only, draft-only, and intentionally invalid
    external runtime manifests look like under the CR-044 contract.

- External runtime manifest schema
  - Source: CR-044 docs-only contract slice
  - Status: documentation-only slice complete; example and adapter work remain
    gated
  - Purpose: define the vendor-neutral manifest contract external runtimes must
    provide before TriageCore can classify authority, approval, provenance, and
    revocation expectations.

- External runtime integration doctrine
  - Source: CR-043 docs-only baseline
  - Status: documentation-only slice complete; runtime integration work remains gated
  - Purpose: define vendor-neutral integration rules for external runtimes without granting new authority or adding dependencies.

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
- CR-034: Repository Consistency and Secrets Hygiene

## Current Recommendation

Keep three work lanes distinct:

- Identity lifecycle work remains under Issue #4. Pause signing expansion beyond
  `route_audit`; runtime rotation behavior still needs a separate
  implementation slice before adding signed event types.
- Model and runtime integrity work should build on CR-031 through CR-033. Keep
  policy baseline, route-manifest artifact shape, manifest validation, and live
  enforcement as separate reviewable slices.
- Repository consistency and secrets hygiene from CR-034 is complete. Future
  hygiene work should be limited to stale documented claims or a separately
  proposed repo-consistency checker.

The next feature-sized slice can be a runtime model-manifest enforcement
preview, but it should not collapse policy, artifact shape, manifest validation,
and backend probing into one change.

For external runtime interoperability, the next approved slice should be policy tests or execution-path validation for the bounded adapter path.

For operator UX, keep the next slices boring and sequential: task-envelope wizard first, Markdown report export second, and any Textual dashboard only after the artifact shape is stable.
