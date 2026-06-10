# Change Log

This file provides a chronological, human-readable record of applied codebase and architecture changes to TriageCore. 

*Note: For operational task and run history, consult `.triagecore/ledger.jsonl`.*

## [Unreleased]
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
