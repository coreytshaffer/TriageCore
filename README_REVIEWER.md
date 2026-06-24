# TriageCore Reviewer README

**For AI safety / security reviewers**
**Purpose:** five-minute reviewer path for the Anthropic Fellows application packet.
**Repository:** `coreytshaffer/TriageCore`
**Project status:** active local-first prototype / research workbench, not a production safety framework.

## Reviewer thesis

TriageCore is a local-first control-plane prototype for safer AI-assisted workflows. It focuses on the safety layer around tool-using or agentic AI systems: admission checks, external runtime boundaries, privacy-safe audit events, runtime provenance, evidence requirements, and explicit human review gates.

The core research question is:

> Can external control-plane mechanisms measurably reduce unsafe or unauthorized behavior in tool-using AI agents, especially under prompt injection, ambiguity, missing evidence, privacy-sensitive requests, and adversarial task conditions?

TriageCore does **not** claim to solve alignment, sandboxing, or agent security. Its value is as an inspectable research harness for evaluating where external controls create safety margins, where they fail, and which mechanisms deserve deeper empirical study.

## Why this matters

Tool-using AI systems can affect files, code, APIs, private context, cloud resources, and local devices. That changes the safety problem: the dangerous step may not be the model's text output; it may be whether the surrounding system admits an action.

Prompt instructions alone are weak control boundaries. TriageCore explores a complementary approach: keep authority, evidence, privacy metadata, provenance, and review gates outside the model, in a system that can be tested and audited.

## What TriageCore does today

Current reviewer-relevant capabilities:

- verifies local operator environment and repository state with `tc doctor`
- generates reviewable preflight and handoff artifacts with `tc preflight` and `tc handoff`
- records and inspects privacy-safe route-audit events with `tc audit`
- validates and renders offline Task Envelope and Admission Evidence contracts
- enforces local-only privacy boundaries before optional external-safe cloud routing is considered
- supports benchmark fixtures and benchmark reports without hiding the evidence trail

## Safety mechanisms under evaluation

| Mechanism | Purpose | Reviewer signal |
|---|---|---|
| Admission checks | Decide whether a task/action has enough structure and evidence to proceed | Task Envelope and Admission Evidence validation |
| External runtime boundaries | Prevent external runtimes from receiving authority by default | External runtime admission governance docs and CLI flows |
| Privacy invariants | Keep persistent artifacts from storing raw sensitive prompt/data content | `tc audit --privacy-invariants` |
| Audit payload shaping | Log useful routing/evidence metadata without raw-content leakage | route-audit self-test and ledger inspection |
| Runtime/model provenance | Make local/cloud/backend/model identity explicit | model manifest examples and route warning checks |
| Human review gates | Preserve operator control over higher-risk actions | preflight/handoff packets and demo dry-run |

## Five-minute reviewer path

Install locally:

```bash
git clone https://github.com/coreytshaffer/TriageCore
cd TriageCore
pip install -e .
```

Then run:

```powershell
tc doctor
tc demo --dry-run
tc preflight CR-017
tc handoff latest --print
tc audit --self-test
tc audit --kind route_audit --last 10
tc audit --kind demo_dry_run --last 5
tc audit --privacy-invariants
triagecore benchmark --list-only
```

Optional deeper verification:

```powershell
tc model check --manifest docs\security\examples\model_route_manifest_local_ollama.json
tc model warn --manifest docs\security\examples\model_route_manifest_local_ollama.json --route docs\security\examples\route_payload_local_ollama.json
tc model warn --manifest docs\security\examples\model_route_manifest_cloud_qwen.json --route docs\security\examples\route_payload_local_ollama.json
```

Expected reviewer takeaways:

- `tc doctor` confirms the local environment and ledger path.
- `tc demo --dry-run` demonstrates an offline safety-control loop without calling a model backend or modifying source files.
- `tc preflight` and `tc handoff` produce reviewable operator artifacts.
- `tc audit --self-test` writes a privacy-safe route-audit event.
- `tc audit --privacy-invariants` checks persistent ledger artifacts for forbidden raw-content keys.
- benchmark commands expose fixtures without requiring backend contact.
- model manifest commands show local/cloud route comparison visibility.

## Two links for a busy reviewer

Use these as the primary proof path in an application or portfolio page:

1. **Guided demo / reviewer path:** `docs/workflows/hackathon_demo.md`
2. **Governance and evidence path:** `docs/operations/external-runtime-admission.md`

Useful supporting links:

- `docs/submission/README.md` - judge-facing submission bundle
- `docs/verification_guide.md` - verification workflow
- `docs/evidence_schema.md` - evidence schema
- `docs/submission/public_evidence_example.md` - public evidence example
- `benchmarks/tasks.jsonl` - benchmark fixtures

## Current proof markers

- runnable CLI reviewer path
- public test badge in repository README
- offline dry-run demo evidence
- privacy-safe route-audit self-test
- persistent-artifact privacy invariant check
- strict Task Envelope / Admission Evidence validation and rendering
- external runtime admission governance model
- benchmark fixtures and report scaffolding
- documented limits on local/cloud routing claims

## Limitations and non-claims

TriageCore is intentionally modest about its claims.

It is **not**:

- a complete sandbox
- a formal security boundary
- a proof of model alignment
- a replacement for secure runtime isolation
- a production governance framework
- a claim that cloud or local models are inherently safe
- a system that grants untrusted external agents authority by default

The current claim is narrower:

> External control-plane mechanisms can be made explicit, inspectable, and testable; TriageCore is a prototype for studying those mechanisms around AI-assisted workflows.

## Fellowship extension
