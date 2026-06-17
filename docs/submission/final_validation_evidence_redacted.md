# Final Validation Evidence (Redacted)

> Note: This file contains redacted validation excerpts from a local final
> packaging run.
> Local paths, usernames, machine names, and exact run identifiers have been
> removed or normalized.
> The excerpts preserve the verification-relevant fields: test result, command
> success, privacy-safe audit behavior, deterministic demo status, manifest
> validation, and non-blocking warning behavior.

This file is a submission-safe excerpt set from the final validation run on
clean `main` at merge commit `e58af68`.

Local machine names, user names, absolute filesystem paths, and full handoff
contents are intentionally omitted or replaced with placeholders.

## Scope Note

These excerpts are intended as compact proof markers, not as a full raw
terminal transcript. The private local transcript should be reviewed manually
before any public sharing.

## 1. Full Test Suite

Command:

```powershell
python -m pytest -q
```

Excerpt:

```text
346 passed, 2 skipped in 61.61s
```

What this proves:

- the repository test suite passed on the final validation run

## 2. Environment Check

Command:

```powershell
tc doctor
```

Excerpt:

```text
TriageCore Doctor
------------------------------
Git Repo Root: <repo-root>
Python Version: 3.14.5
Git Branch: main
Git Status: dirty
Ledger Path: <repo-root>\.triagecore\ledger.jsonl
Handoff Latest: <repo-root>\.triagecore\handoffs\latest.md
Scratch Excluded: yes
```

What this proves:

- the CLI resolved the repo, ledger, and handoff paths correctly
- the operator environment was visible before the demo path ran

Note:

- `Git Status: dirty` during this step reflected runtime-generated evidence
  artifacts from the validation session, not source-code edits

## 3. Deterministic Offline Dry Run

Command:

```powershell
tc demo --dry-run
```

Excerpt:

```text
TaskPacket Summary
  task_id=demo-dry-run-REDACTED | prompt_length=151 | data_length=165 | data_class=public | external_model_allowed=False
Privacy Check
  privacy_level=local_only | passed=True | detections=0 | violations=0
Route Decision
  selected_route=deterministic | backend_invoked=False | reason=offline_demo_fixture_requires_no_model_execution
Scoped Context
  context_strategy=deterministic_summary | raw_context_included=False | privacy_level=local_only
Proposed Output
  status=pending_review
Validation
  validator=deterministic_demo_validator | status=passed | passed=True
Human Decision
  requested=pending | decision_state=pending_review | finalized=False
Ledger Event
  event_type=demo_dry_run | selected_route=deterministic | validation_status=passed | raw_context_included=False
```

What this proves:

- the dry run used a deterministic offline route
- privacy classification and review state remained visible
- raw context was not persisted in the demo evidence path

## 4. Preflight And Handoff

Commands:

```powershell
tc preflight CR-014
tc handoff latest --print
```

Excerpt:

```text
Success: Wrote preflight handoff to .triagecore\handoffs\CR-014-preflight.md and updated .triagecore\handoffs\latest.md
```

Handoff excerpt:

```text
# Handoff for CR-014

> [!WARNING]
> [DETERMINISTIC FALLBACK USED] Local LLM compression unavailable.

## Task Scope
Use the scope described in this CR for orientation. Do not edit source code unless the operator explicitly approves implementation.

## Forbidden Scope
Do not implement unspecified CRs. Do not modify source code autonomously outside the approved scope.
```

What this proves:

- the system generated a reviewable preflight artifact
- scope and forbidden-scope boundaries were made explicit

## 5. Privacy-Safe Route Audit Evidence

Commands:

```powershell
tc audit --self-test
tc audit --kind route_audit --last 10
```

Excerpt:

```text
Success: Wrote privacy-safe route_audit self-test event to <repo-root>\.triagecore\ledger.jsonl.
```

Audit excerpt:

```text
Task: audit-self-test-REDACTED | Type: route_audit
  Decision: allowed | Reason: audit_self_test
  Privacy: public (Scan Passed: True)
  Local Only: False | Route: self_test | Backend: self_test
```

What this proves:

- route audit records can be written and inspected without exposing raw payloads
- the public evidence path is metadata-only

## 6. Deterministic Demo Evidence Inspection

Command:

```powershell
tc audit --kind demo_dry_run --last 5
```

Excerpt:

```text
Task: demo-dry-run-REDACTED | Type: demo_dry_run
  demo_mode: dry_run
  selected_route: deterministic
  route_reason: offline_demo_fixture_requires_no_model_execution
  privacy_level: local_only
  privacy_passed: True
  scoped_context_created: True
  raw_context_included: False
  proposed_output_status: pending_review
  validation_status: passed
  decision_state: pending_review
  finalized: False
```

What this proves:

- the demo evidence can be re-inspected from the ledger
- the persistent record remains metadata-only and review-aware

## 7. Manifest Validation

Command:

```powershell
tc model check --manifest docs\security\examples\model_route_manifest_local_ollama.json
```

Excerpt:

```text
Model manifest check passed
manifest=docs\security\examples\model_route_manifest_local_ollama.json
execution_class=local
backend_type=ollama
exact_model_id=qwen2.5:7b-instruct-q4_K_M
integrity_status=complete
```

What this proves:

- the documented manifest can be validated locally without backend probing

## 8. Manifest Warning Check, Matching Case

Command:

```powershell
tc model warn --manifest docs\security\examples\model_route_manifest_local_ollama.json --route docs\security\examples\route_payload_local_ollama.json
```

Excerpt:

```text
Model route warning check passed
manifest=docs\security\examples\model_route_manifest_local_ollama.json
route=docs\security\examples\route_payload_local_ollama.json
warnings=0
```

What this proves:

- matching manifest and route metadata produce no warnings

## 9. Manifest Warning Check, Deliberate Warning Case

Command:

```powershell
tc model warn --manifest docs\security\examples\model_route_manifest_cloud_qwen.json --route docs\security\examples\route_payload_local_ollama.json
```

Excerpt:

```text
Model route warning check warned
manifest=docs\security\examples\model_route_manifest_cloud_qwen.json
route=docs\security\examples\route_payload_local_ollama.json
warnings=3
warning=backend_mismatch path=$.backend.backend_type
warning=model_mismatch path=$.model.exact_model_id
warning=route_mismatch path=$.route_id
```

What this proves:

- route/manifest mismatches are visible
- the warning path is non-blocking and informational rather than enforcement

## 10. Final Repo State

Command:

```powershell
git status
```

Excerpt:

```text
On branch main
Your branch is up to date with 'origin/main'.

Untracked files:
  .triagecore/hackathon-final-<timestamp>.txt
```

What this proves:

- validation ran on `main`
- the only post-run artifact shown here was the private transcript file itself

## Environment Note

One initial dry-run attempt hit a local filesystem write-permission issue when
appending to `.triagecore\ledger.jsonl`. Rerunning in the permitted shell
completed successfully. This was an environment permission issue, not a
repository regression.
