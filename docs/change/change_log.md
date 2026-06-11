# Change Log

This file provides a chronological, human-readable record of applied codebase and architecture changes to TriageCore.

*Note: For operational task and run history, consult `.triagecore/ledger.jsonl`.*

## [Unreleased]

- Implemented CR-020 (Persistent Artifact Privacy Invariant): Add a central validator for persistent ledger events and fail closed before writing prohibited raw-content keys.
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
