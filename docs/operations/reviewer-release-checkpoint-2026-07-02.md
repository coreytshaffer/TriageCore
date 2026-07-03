# Reviewer Release Checkpoint — 2026-07-02

## Purpose
This document preserves a point-in-time reviewer-readiness evidence record for TriageCore, taken on 2026-07-02. It aggregates change request summaries, validation results, security disclosures, and next-step backlog recommendations after the completion of the reviewer-facing features up to PR #82.

This is an evidence record of one repository state and one local runtime state on one date. It is not a release certification, and it does not prove production readiness, safety, legal compliance, or correctness of model outputs.

## Commit Baseline
- **Branch:** `main`
- **HEAD Commit:** `355c521` (Merge pull request #82 from coreytshaffer/cr-098-task-evidence-show-command)
- **Working Tree:** clean

## What Changed (PR Arc Summary)
We have completed a sequential, focused stabilization arc to harden TriageCore for reviewer inspection:

1. **PR #80 (Reviewer Stabilization & TriageDesk Evidence Integrity):**
   - Fixed the TriageDesk GUI to correctly emit `review_decision` instead of `decision`, ensuring "needs revision" outcomes survive end-to-end.
   - Removed fabricated GUI default values for `human_review_minutes` and `review_workload` to avoid writing unmeasured effort to the ledger as factual evidence.
   - Hardened agent authority manifests with explicit boundary checks, ensuring denied actions always take precedence and omissions never waive review gates.

2. **PR #81 (CR-097: Fail-Closed Identity Registry Load Handling):**
   - Normalizes all identity registry (`agents.json`) IO, JSON decode, and validation failures into distinct typed exceptions.
   - Adds a bounded CLI handler that outputs safe static categories (`unreadable_registry`, `malformed_registry`, `invalid_identity_record`) and exits 1 immediately without leaking Python tracebacks or secret key material to stdout/stderr.
   - Intercepts crashes on `tc identity list`, `tc audit --verify-signatures`, and signed smoke tests.

3. **PR #82 (CR-098: Read-Only Task Evidence Show Command):**
   - Implements `tc task show <task_id>` to easily display a task's ledger-derived history, status, and event timeline from the CLI.
   - Strictly read-only: does not load the identity registry or perform signature verification inline, preventing registry-dependent crashes in the primary display path.
   - Explicitly directs users to `tc audit --verify-signatures` for signature checking.

---

## Verification Evidence

### Local Full Regression Results
- **Pytest Output:** `715 passed, 2 skipped in 69.71s (0:01:09)`
- **Targeted CLI Tests (`test_cr_097` and `test_cr_098`):** All passed.
- **`tc doctor` Status:** `Overall: OK` (working tree clean, ledger readable/writable).

### GitHub CI Actions (PR #82)
The latest remote CI checks passed successfully:
- `pytest (3.10)`: pass
- `pytest (3.11)`: pass
- `pytest (3.12)`: pass

---

## Reviewer Guide

### What is safe to trust?
- **Append-only ledger history:** Every classification, routing, and review state transition is captured sequentially in `.triagecore/ledger.jsonl`.
- **Metadata-only privacy bounds:** Prompts, secrets, and raw code modifications are kept in task fixtures or local workspace paths and never written to the public ledger.
- **Fail-closed posture:** If the identity registry is malformed or unreadable during signing operations, the CLI immediately halts with a structured `registry_load_failed` output.

### What is explicitly NOT claimed?
- A valid cryptographic signature proves **provenance and tamper evidence only**; it does not constitute approval, safety certification, or correctness proof.
- `tc task show` is read-only; it does not execute code, mutate files, or verify signatures inline.

### How do I inspect a task evidence chain?
Run the newly added CLI command:
```powershell
tc task show <task_id>
```
*Note: This command prints an explicit line warning that signature verification is not checked.*

### How do I verify signatures separately?
To verify the provenance of signed events in the ledger, run:
```powershell
tc audit --verify-signatures --kind route_decision
```

---

## What Should Be Reviewed Next?
Future stabilization work should proceed in the following order:
1. **Identity doctor orphaned-key warning:** Update `tc identity doctor` to warn when private key files (e.g. `*.key`) exist in the keys directory without a matching registered entry in `.triagecore/identity/agents.json`.
2. **Task show signature verification flag:** Add a safe opt-in flag `tc task show <task_id> --verify-signatures` that lazily loads the registry and runs verification for any signed events on the timeline, failing closed if the registry is corrupt.

## Recommended Tag Name
`v0.1.0-reviewer-checkpoint-2026-07-02`
