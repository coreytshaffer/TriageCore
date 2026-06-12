# Hackathon Demo Workflow

For the judge-facing submission packet, start with [docs/submission/README.md](C:/Users/corey/Documents/Science/AI/triagecore/docs/submission/README.md).

This workflow is the operator-facing demo path for TriageCore in hackathon settings.

It is designed to cover three presentation needs with one bounded walkthrough:

- Primary demo: TriageCore local-first orchestration with optional Qwen Cloud escalation.
- Secondary framing: safer AI-assisted SDLC with explicit review and audit trails.
- Future extension: Clear Lake Watch and other environmental edge workflows that need local resilience before optional cloud help.

## Purpose

Use this walkthrough to show that TriageCore is not "an agent that just calls the cloud."

Instead, it is a local-first control layer that:

- verifies operator environment state
- creates reviewable preflight handoff artifacts
- preserves privacy and local-only boundaries
- records route audit evidence
- allows optional cloud escalation only when a task is external-safe and explicitly configured

The main demo should stay centered on TriageCore and the Qwen Cloud integration from CR-014. The environmental framing is a future extension, not the main runtime claim.

## Prerequisites

- Run from the repository root.
- The editable CLI install should already work.
- No live Qwen Cloud credential is required for this walkthrough.
- The deterministic dry run calls no model backend and requires no credentials.

Recommended shell:

```powershell
cd C:\Users\corey\Documents\Science\AI\triagecore
```

## Exact Commands

Run these commands in order:

```powershell
tc doctor
tc demo --dry-run
tc preflight CR-014
tc handoff latest --print
tc audit --self-test
tc audit --kind route_audit --last 10
tc audit --kind demo_dry_run --last 5
```

Optional evidence command if you want to show the existing seed examples:

```powershell
python -m triage_core.cli import-learning-seeds --source-dir docs\learning\examples --ledger-dir .triagecore
```

Use that last command only when you want to explain the learning/example layer. It is not required for the core 3-minute demo.

## Expected Outputs

### 1. `tc doctor`

Expected themes:

- confirms repo root
- confirms Python executable and `tc` path
- confirms ledger path
- confirms handoff path
- confirms pytest config visibility

What to point out:

- TriageCore is operating from the local repo.
- The operator can inspect the local ledger and artifact paths directly.

### 2. `tc demo --dry-run`

Expected themes:

- shows the messy-request fixture and a bounded `TaskPacket` summary
- runs the existing privacy scan
- selects a deterministic offline route with a visible rationale
- shows a scoped context summary with `raw_context_included: False`
- produces a proposed output marked `pending_review`
- runs a deterministic validator
- leaves the human decision pending by default
- writes one metadata-only `demo_dry_run` event
- prints the ledger path

What to point out:

- this is a deterministic dry run, not a model-generated result
- it runs offline and does not call Qwen, Ollama, LM Studio, or another backend
- it does not mutate source files
- the messy request and proposed output are visible in the terminal but are not
  persisted to the ledger
- it demonstrates workflow structure and control gates, not production AI
  safety or certification

Optional human-decision simulations:

```powershell
tc demo --dry-run --decision approve
tc demo --dry-run --decision reject
```

### 3. `tc preflight CR-014`

Expected themes:

- writes `.triagecore/handoffs/CR-014-preflight.md`
- updates `.triagecore/handoffs/latest.md`
- does not edit source code

What to point out:

- the system creates a reviewable handoff artifact before implementation work
- this is a bounded operator workflow, not silent autonomous execution

### 4. `tc handoff latest --print`

Expected themes:

- prints the generated handoff markdown
- includes task scope and forbidden scope
- includes file references and token metadata comments
- may include a deterministic fallback warning if local compression is unavailable

What to point out:

- the handoff is readable and auditable
- the artifact is designed for human review or supervised continuation

### 5. `tc audit --self-test`

Expected themes:

- appends one privacy-safe `route_audit` event to `.triagecore/ledger.jsonl`
- prints a confirmation message

What to point out:

- TriageCore can demonstrate its audit trail without executing a real user task
- the event contains metadata only

### 6. `tc audit --kind route_audit --last 10`

Expected themes:

- displays recent `route_audit` events
- shows decision, reason, privacy level, route, and backend
- does not display prompt/data/content/raw payload fields

What to point out:

- operators can inspect routing evidence directly
- the audit view is privacy-safe by design

### 7. `tc audit --kind demo_dry_run --last 5`

Expected themes:

- displays the deterministic route and review metadata
- confirms `raw_context_included: False`
- displays validation and decision state
- does not display the messy request, raw packet data, full context, or proposed
  output

## Privacy And Local-First Explanation

Say this plainly:

- TriageCore starts from local control, not cloud delegation.
- Privacy scanning and packet verification happen before any eligible cloud path.
- Local-only packets stay local and fail closed if the route is ambiguous.
- Cloud use is optional and bounded. It is not the default behavior for every task.

If someone asks what "local-first" means here:

- local files, local ledger, local preflight, local inspection, and explicit operator review happen before any optional escalation story

## Optional Qwen Cloud Escalation Explanation

This walkthrough does not require live Qwen credentials.

What you can say:

- CR-014 added a narrow Qwen Cloud adapter behind the existing backend interface.
- The Qwen execution path only exists for already external-safe packets.
- Missing credentials fail safely into handoff behavior.
- Local-only packets never invoke the Qwen adapter.

What you should not do in this demo:

- do not imply that the walkthrough is making a live Qwen call
- do not imply that every cloud-shaped route automatically executes remotely

## Route Audit Inspection

The key audit command is:

```powershell
tc audit --kind route_audit --last 10
```

During the demo, point out these fields:

- `Decision`
- `Reason`
- `Privacy`
- `Local Only`
- `Route`
- `Backend`

Point out what is missing:

- no raw prompt
- no raw data
- no copied task content

That is the evidence trail story: useful metadata without leaking payload contents.

## What To Say In A 3-Minute Demo

Suggested talk track:

1. "TriageCore is a local-first control harness for AI-assisted software work, not a blind cloud agent."
2. "First I verify the local operator environment with `tc doctor` so the demo starts from inspectable local state."
3. "Then I run one deterministic offline command that makes the packet, privacy, route, context, validation, and human-review checkpoints visible."
4. "Next I generate and print a preflight handoff for CR-014. This creates a review artifact before code work."
5. "Now I inspect both route-audit and deterministic-demo ledger evidence."
6. "The ledger contains useful metadata without storing the raw request, context, or proposed output."
7. "This shows the core value: local-first workflow, bounded artifacts, privacy-safe auditability, and optional cloud escalation only when a task is external-safe and explicitly configured."
8. "For future environmental and edge workflows like Clear Lake Watch, the same pattern supports offline-resilient local operation before optional cloud help."

## What Not To Claim

Do not claim:

- that the deterministic dry run executed an AI model
- that the deterministic dry run proves production safety or certification
- that the demo proves live production cloud execution
- that TriageCore automatically solves SDLC governance
- that local-first means zero human review
- that audit records contain full task history or raw prompts
- that Clear Lake Watch integration already exists as a finished runtime workflow
- that this demo validates environmental outcomes beyond the software-control pattern

## Troubleshooting Notes

### `tc` command not found

Use the module fallback:

```powershell
python -m triage_core.tc_cli --help
python -m triage_core.tc_cli preflight CR-014
```

See [operator_bootstrap.md](C:/Users/corey/Documents/Science/AI/triagecore/docs/workflows/operator_bootstrap.md) for the longer setup notes.

### `tc preflight CR-014` fails

Check:

- you are running from the repo root
- the CR file exists under `docs/change/requests/`
- Python and the editable install are available

### `tc handoff latest --print` fails

Usually this means the preflight step did not complete first. Re-run:

```powershell
tc preflight CR-014
tc handoff latest --print
```

### `tc audit --kind route_audit --last 10` shows nothing

Run the self-test first:

```powershell
tc audit --self-test
tc audit --kind route_audit --last 10
```

### `tc audit --kind demo_dry_run --last 5` shows nothing

Run the dry run first:

```powershell
tc demo --dry-run
tc audit --kind demo_dry_run --last 5
```

### Qwen Cloud questions come up during judging

Clarify:

- the integration exists
- it is privacy-gated
- this walkthrough does not depend on live credentials
- mocked tests verify the adapter path without requiring external connectivity

## Demo Boundaries

This workflow is intentionally bounded.

It demonstrates:

- a deterministic offline acceptance-chain proof
- local-first operator workflow
- reviewable handoff generation
- privacy-safe route auditing
- optional cloud escalation framing

It does not demonstrate:

- AI-generated output in the deterministic dry run
- live production cloud calls
- autonomous end-to-end delivery
- domain-complete environmental deployment
