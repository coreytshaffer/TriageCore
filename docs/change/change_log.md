# Change Log

This file provides a chronological, human-readable record of applied codebase and architecture changes to TriageCore.

*Note: For operational task and run history, consult `.triagecore/ledger.jsonl`.*

## [Unreleased]
- Implemented CR-028 (Signed Smoke-Path Evidence): Add `tc audit --signed-smoke-test --agent-id <id>` to append one metadata-only signed `route_audit` event using an existing authorized identity.
- Implemented CR-027 (Identity Key Hardening and Consistency Check): Add restrictive private-key permissions where supported, transactional identity creation cleanup, and `tc identity check` for registry/key consistency.
- Implemented CR-026 (Post-Identity Privacy and Security Audit): Add a focused audit of CR-020 identity initialization, local key storage, signed `route_audit` verification, privacy boundaries, and remaining key-lifecycle risks.
- Partially Implemented CR-020 (Persistent Cryptographic Agent Identities): Add identity foundation, Ed25519 signing helpers, signed `route_audit`, verification CLI, identity init/list/check, and signed smoke-path evidence while keeping revocation, rotation, and broader signing out of scope.
- Proposed CR-025 (Backlog Documentation Alignment Pass): Align backlog, README proof markers, release metadata, and current project status after CR-021 through CR-024.
- Implemented CR-023 (Offline Demo Dry-Run Evidence): Add deterministic offline demo evidence with metadata-only `demo_dry_run` ledger events and reviewer-path documentation.
- Implemented CR-024 (Persistent Artifact Audit Command): Add `tc audit --privacy-invariants` to scan existing ledger records for forbidden raw-content fields using the CR-021 invariant.
- Implemented CR-022 (Context Facet Pruning Plan): Add deterministic facet metadata and explicit facet exclusion to context budgeting while keeping context-pack event payloads metadata-only.
- Implemented CR-021 (Persistent Artifact Privacy Invariant): Add a central recursive validator for persistent ledger events and fail closed before writing prohibited raw-content keys.

- Implemented CR-019 (Mobile API Access Boundary): Require bearer authentication, default to loopback, restrict network binding, return privacy-safe task projections, disable logs, and validate review decisions.
- Implemented CR-018 (CI and Release Hygiene): Add a GitHub Actions pytest workflow and public CI trust marker for the alpha release.
- Implemented CR-017 (Public Legibility Pass): Compress the README opening, add a 5-minute reviewer path, and add a canonical privacy-safe public evidence example for first-time reviewers.
- Implemented CR-016 (Hackathon Submission Bundle): Add a judge-facing submission bundle with overview, quickstart, track mapping, and claim boundaries using existing commands only.
- Implemented CR-015 (Hackathon Demo Scenario): Add a documentation-first hackathon walkthrough using existing commands, route audit inspection, and TriageCore/Qwen framing without requiring live cloud credentials.
- Implemented CR-014 (Qwen Cloud Backend Adapter): Add a mocked-testable Qwen Cloud backend, config accessors, and an external-safe-only cloud execution path that preserves local-only fail-closed routing.
- Implemented CR-013 (Audit Smoke Event): Add `tc audit --self-test` to append one privacy-safe `route_audit` event with no raw payload fields.
- Implemented CR-012 (Environment Doctor Cli):
- Implemented CR-011 (Change Request Scaffold CLI): Add `tc propose` command to automate CR boilerplate generation.
- Implemented CR-010 (Audit CLI Test Hardening): Add regression tests for the `tc audit` subcommand.
- Implemented CR-009 (Audit Inspection CLI): Add `audit` subcommand to inspect ledger events safely.
- Implemented CR-008 (Route Decision Audit Trail): Introduce a deterministic, append-only audit trail for all routing decisions.
- Implemented CR-004B (Local-Only Privacy Routing Enforcement): Enforce safety boundaries to ensure sensitive tasks never leave local execution.
- Implemented CR-003 (Safe TaskPacket): Added `VerifiedTaskPacket`, `ExternalSafeTaskPacket`, and pre-routing boundary enforcement.
- Implemented CR-002 (Deterministic Privacy Scan): Added `privacy_scanner.py` and strict pre-routing intake enforcement.
- Implemented CR-007 (Operator Bootstrap and First-Run Setup): Created `docs/workflows/operator_bootstrap.md`.
- Implemented CR-006 (Seamless Operator Workflow Integration): Added `tc` alias and workflow commands.
- Implemented CR-005 (Local Preflight Context Compression): Created `ContextBundle` and `triage_core.compression` module.
- Implemented CR-001 (TaskPacket Privacy Metadata): Added `TaskPacket` and `PrivacyMetadata` schemas and integrated them backward-compatibly into `TriageClient.run_task()`.
- Initial creation of the change management documentation layer.
- Added CR-004 (Local LLM Provenance and Smoke Tests) as proposed documentation only.

