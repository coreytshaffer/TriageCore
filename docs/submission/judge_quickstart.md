# Judge Quickstart

This is the fastest judge path for verifying the current TriageCore submission with existing commands only.

## Purpose

Show the implemented local-first workflow, reviewable artifacts, and privacy-safe route audit evidence without requiring live Qwen Cloud credentials.

## Prerequisites

- Run from the repository root.
- The `tc` CLI should already be available.
- No live Qwen credentials are required.

Recommended shell:

```powershell
cd TriageCore
```

## Fastest Path

Run:

```powershell
tc doctor
tc preflight CR-017
tc handoff latest --print
tc audit --self-test
tc audit --kind route_audit --last 10
```

## What Each Command Proves

### `tc doctor`

Shows:

- repo root
- Python and `tc` executable paths
- ledger path
- handoff path
- pytest config visibility

### `tc preflight CR-017`

Shows:

- TriageCore can generate a reviewable handoff artifact
- the workflow is operator-bounded and artifact-based

### `tc handoff latest --print`

Shows:

- the generated handoff is readable
- task scope and forbidden scope are explicit
- artifact references are visible

### `tc audit --self-test`

Shows:

- TriageCore can append a privacy-safe audit event without running a real task

### `tc audit --kind route_audit --last 10`

Shows:

- route audit records are inspectable
- metadata is visible
- raw task payload fields are not displayed

## Expected Outputs

You should see:

- a valid doctor report
- a successful preflight message writing to `.triagecore/handoffs/`
- a printed handoff packet
- a successful audit self-test confirmation
- recent `route_audit` records with fields such as decision, reason, privacy, route, and backend

## Optional Deeper Verification

If more time is available:

```powershell
python -m pytest -q
git status
```

## Troubleshooting

### `tc` not found

Use the Python module fallback:

```powershell
python -m triage_core.tc_cli --help
```

### Preflight fails

Check:

- you are in repo root
- `docs/change/requests/CR-017-public-legibility-pass.md` exists

### Handoff print fails

Re-run:

```powershell
tc preflight CR-017
tc handoff latest --print
```

### Audit view is empty

Run:

```powershell
tc audit --self-test
tc audit --kind route_audit --last 10
```

## Related Docs

- [hackathon_submission_overview.md](hackathon_submission_overview.md)
- [track_mapping.md](track_mapping.md)
- [claim_boundaries.md](claim_boundaries.md)
- [public_evidence_example.md](public_evidence_example.md)
- [hackathon_demo.md](../workflows/hackathon_demo.md)



