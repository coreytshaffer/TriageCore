# TriageCore

[![tests](https://github.com/coreytshaffer/TriageCore/actions/workflows/tests.yml/badge.svg)](https://github.com/coreytshaffer/TriageCore/actions/workflows/tests.yml)

**Observable, Traceable, Data-Driven**

TriageCore is an observable, traceable, data-driven control-plane harness for evaluating local AI routing decisions. It records structured evidence about model and runtime choices, agent-group behavior, token use, latency, quality gates, and energy-measurement tier before making stronger orchestration claims. The project remains an early research workbench for AI-assisted software work that keeps local control, reviewable artifacts, and privacy boundaries visible to the operator. It can generate preflight and handoff packets, inspect privacy-safe route audit events, run local benchmark/report workflows, and support a bounded Qwen Cloud path for external-safe packets.

> **Status**
> TriageCore is active as a local-first prototype/workbench. Current capabilities, supporting docs, tests, and demo paths are in-repo now. Broader governance, release polish, and long-term environmental-edge integrations should be treated as ongoing work, not completed product claims.

## What It Does Today

- Verifies operator environment and local repo state with `tc doctor`.
- Generates reviewable preflight and handoff artifacts with `tc preflight` and `tc handoff`.
- Records and inspects privacy-safe route audit events with `tc audit`.
- Validates and renders offline Task Envelope and Admission Evidence contracts via the `tc task-envelope` and `tc admission` CLI tools.
- Validates static agent authority manifests with `tc authority check` without granting execution authority.
- Supports local benchmark fixtures and benchmark reports without hiding the evidence trail.
- Enforces local-only privacy boundaries before any optional external-safe Qwen Cloud path is considered.

## Evidence-Bound Build Review

Build Review turns a development request and Git comparison into a local,
reviewable evidence packet. It compares declared scope with actual changed
files, runs trusted operator-supplied validations, flags missing or failed
evidence, and keeps the system recommendation separate from the named human
decision.

Create a packet:

```powershell
tc build-review create `
  --request-file docs/change/requests/CR-BW-001-evidence-bound-build-review.md `
  --base main `
  --head HEAD `
  --validate "python -m pytest -q"
```

Record one non-overwriting decision:

```powershell
tc build-review decide `
  .triagecore/build-reviews/<review-id> `
  approved `
  --reviewer "Your name" `
  --note "Scope and validation evidence reviewed."
```

Independently verify the packet and optional decision:

```powershell
tc build-review verify .triagecore/build-reviews/<review-id>
```

Verification exits `0` only for an internally intact packet, `1` with a
specific integrity or operation diagnostic, and `2` for malformed command use.
It rejects missing or symlinked artifacts, malformed or duplicate-key JSON,
hash drift, derived-view drift, and decisions referencing different evidence.
Packet and decision content also pass the persistent privacy invariant before
write.

Two portable packets demonstrate the distinction between integrity and
acceptability:

```powershell
tc build-review verify examples/build-week/clean-self-review
tc build-review verify examples/build-week/adversarial-scope-drift
```

The clean packet recommends approval while its human decision remains pending.
The adversarial packet is internally intact but documents undeclared scope,
missing validation, a rejection recommendation, and a `needs_revision`
decision.

SHA-256 establishes internal consistency here, not authorship or protection
against an actor able to replace every artifact and recompute every digest.
See [the artifact contract](docs/build-review-contract.md) and
[Build Week scope](BUILD_WEEK_SCOPE.md).

## Why It Matters

- It makes local vs cloud execution explicit instead of burying that decision inside an agent loop.
- It preserves human review, permission boundaries, and fail-closed local-only handling as core workflow rules.
- It produces inspectable artifacts and route evidence instead of relying on vague autonomy claims.
- It is useful today as safer AI-assisted SDLC framing and useful later as a control pattern for environmental edge workflows.

## Workspace Unifier

TriageCore includes a local-first Workspace Unifier for orientation, focus selection, review artifacts, and bounded handoffs. It works from local YAML files, keeps previews reviewable, and does not turn agent coordination into an approval surface.

### Quick Start

**1. Create your private configuration:**
```bash
mkdir ~/.triagecore
# Create ~/.triagecore/work_items.yaml (your full registry)
# Create ~/.triagecore/today.yaml (your daily focus list)
```

**2. Generate the dashboard:**
```bash
tc workspace dashboard --items ~/.triagecore/work_items.yaml --today ~/.triagecore/today.yaml --output ~/.triagecore/dashboard.html
```

**3. Open it (Windows/PowerShell):**
```powershell
Invoke-Item ~/.triagecore/dashboard.html
# Or just: ii ~/.triagecore/dashboard.html
```

### Command Surface

| Command | Purpose |
|---|---|
| `tc workspace board --items <path>` | Read-only board view grouped by status. |
| `tc workspace wbs --items <path>` | Read-only work breakdown view by area, project, and component. |
| `tc workspace now --items <path> --today <path>` | Read-only daily focus view combining the registry and today list. |
| `tc workspace dashboard --items <path> --today <path> --output <path>` | Writes a static HTML dashboard with no external dependencies. |
| `tc workspace handoff --items <path> --id <id> --tool <tool>` | Exports a bounded handoff packet for a selected item. |
| `tc workspace import-github --repo <owner/repo> --output <path>` | Imports open GitHub issues into a preview file for review. |
| `tc workspace review-import --preview <path>` | Reviews imported preview items before promotion. |
| `tc workspace promote --items <path> --preview <path> --id <id> --output <path>` | Explicitly promotes selected preview items into a live board file. |
| `tc workspace close --items <path> --id <id>` | Generates a closing packet and can persist closure metadata only when explicitly directed. |
| `tc workspace review --items <path>` | Shows a weekly review view of stale, active, and blocked work. |
| `tc workspace touch --items <path> --id <id>` | Updates review metadata for an item with explicit write intent. |
| `tc workspace export-eval --items <path> --id <id> --output <path>` | Writes a static evaluator-input packet for a selected work item without scoring it. |

> **Note on GitHub imports:**
> You can import open GitHub issues via `tc workspace import-github --repo owner/repo --output preview.yaml`.
> **Generated previews are review artifacts, not the live board.** Use `tc workspace promote` to select which items to pull into your real `work_items.yaml`.

### Architecture Boundary

- **TriageCore** = policy, contracts, state, and CLI engine.
- **TriageDesk** = human control cockpit.
- **Meta-harness** = agent coordination layer.
- **Independent evaluator** = external assessment layer.
- See [Workspace Evaluator Preview](docs/evals/workspace_evaluator_preview.md) for the file-contract-based workspace export that feeds external assessment without importing or invoking the evaluator.
- See [Fluidic Signal Paths](docs/architecture/fluidic_signal_paths.md) for the architecture note on how context, handoffs, approvals, evaluator outputs, and evidence should flow between these layers.

### Safety Invariants

- Local-first.
- Read-only by default.
- Explicit mutation only.
- Backup support for in-place writes.
- Generated previews are review artifacts, not the live board.
- Dashboard has no external dependencies.
- Handoffs omit private notes by default.
- Evaluator must not become approval authority.

### Daily Workflow

Capture → Clarify → Promote → Focus → Handoff → Execute → Close → Weekly Review

### What This Does Not Do

- Does not replace TriageDesk.
- Does not approve actions automatically.
- Does not execute agent work.
- Does not mutate GitHub.
- Does not import everything into the live board.
- Does not make the meta-harness the source of truth.

### Next Architecture Direction

TriageDesk should become the human-facing cockpit for approvals, evidence, review, and dashboard operation. Meta-harness should coordinate agents and sessions. Independent evaluator should assess whether observed behavior matched expected control boundaries. TriageCore remains the stable contract/evidence substrate.

## Current, Planned, And Research Framing

**Current capabilities**
- local-first operator workflow
- route audit inspection
- benchmark scaffolding and reports
- bounded Qwen Cloud escalation for external-safe packets only

**Planned / future-facing**
- public release polish such as release metadata upkeep and GitHub metadata
- deeper environmental-edge packaging around Clear Lake Watch style workflows

**Research framing**
- methodology, evidence schema, and benchmark comparison docs remain first-class because the project is also an evaluation workbench, not only a tool wrapper

## 5-Minute Reviewer Path

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
tc authority check --manifest docs\security\examples\agent_authority_manifest_reviewer.json
```

Expected outputs:

- `tc doctor` confirms repo root, Python, CLI path, ledger path, and pytest visibility.
- `tc demo --dry-run` shows the offline safety-control loop from packet summary through human review and writes one metadata-only demo event.
- `tc preflight CR-017` writes a handoff artifact under `.triagecore/handoffs/`.
- `tc handoff latest --print` prints a reviewable handoff packet.
- `tc audit --self-test` writes one privacy-safe `route_audit` event.
- `tc audit --kind route_audit --last 10` shows routing metadata without raw prompt/data leakage.
- `tc audit --kind demo_dry_run --last 5` shows the deterministic demo evidence without raw request or proposed-output content.
- `tc audit --privacy-invariants` scans the persistent ledger for forbidden raw-content keys and high-confidence PII, credential, and precise-location value patterns; it does not classify arbitrary free text.
- `triagecore benchmark --list-only` shows the benchmark fixture set without contacting a backend.
- `tc model check` validates the documented manifest example locally.
- `tc model warn` provides warning-only route/manifest comparison visibility and
  remains non-blocking when mismatches exist.
- `tc authority check` validates the static authority-manifest example without writing ledger or identity state.

For a hop-by-hop walkthrough of how a task's route decision, evidence record, review state, and verification evidence link together, see [Reviewer Traceability](docs/operations/reviewer-traceability.md).

Sample audit transcript:

```text
> tc audit --self-test
Success: Wrote privacy-safe route_audit self-test event to ...\.triagecore\ledger.jsonl.

> tc audit --kind route_audit --last 10
[2026-06-11T03:39:17.292773+00:00] Task: audit-self-test | Type: route_audit
  Decision: allowed | Reason: audit_self_test
  Privacy: public (Scan Passed: True)
  Local Only: False | Route: self_test | Backend: self_test
```

The deterministic demo runs offline, calls no model backend, and changes no
source files. It demonstrates the current workflow structure and review gates;
it is not evidence of production safety certification.

The manifest warning commands are optional deeper verification only. They
demonstrate route/manifest comparison visibility, not runtime enforcement,
backend probing, or production certification.

Start here if you want the shortest guided path:

- [Daily-Driver Quickstart](docs/daily_driver_quickstart.md)
- [Hackathon Demo](docs/workflows/hackathon_demo.md)
- [Judge Submission Bundle](docs/submission/README.md)
- [Verification Guide](docs/verification_guide.md)
- [Evidence Schema](docs/evidence_schema.md)
- [Agent Identity Provenance Boundary](docs/security/agent_identity_provenance.md)
- [External Runtime Admission Governance](docs/operations/external-runtime-admission.md)
- [Benchmark Fixtures](benchmarks/tasks.jsonl)
- [Public Evidence Example](docs/submission/public_evidence_example.md)

## External Runtime Admission Governance

TriageCore models external agent actions using a tri-part governance model:
1. **Task Envelope** (The Contract)
2. **Admission Evidence** (The Proof)
3. **Execution Sidecar** (The Enforcer)

The execution sidecar is the future/runtime integration boundary; the current CLI tools provide deterministic preflight governance evidence.

These commands validate and render operator-facing governance artifacts. They do not execute external runtimes, write to the ledger, or mutate approval state.

```bash
# Draft or preview envelopes
tc task-envelope wizard
tc task-envelope draft --from-json docs/examples/task-envelope.example.json

# Validate strict schemas
tc task-envelope validate --from-json docs/examples/task-envelope.example.json
tc admission validate --from-json docs/examples/admission-evidence.example.json

# Render for operator review
tc admission render --from-json docs/examples/admission-evidence.example.json
```

For more details, refer to:
- [Operator Admission Workflow](docs/operations/external-runtime-admission.md)
- [Task Envelope CLI](docs/operations/task-envelope-cli.md)
- [Admission Evidence CLI](docs/operations/admission-cli.md)

## Proof Markers

Current in-repo proof markers:

- a runnable reviewer path using existing commands
- a judge-facing submission bundle under [`docs/submission/`](docs/submission/README.md)
- a privacy-safe route audit self-test and public evidence example
- persistent artifact privacy invariant audit via `tc audit --privacy-invariants`
- benchmark fixtures and benchmark-report scaffolding
- a full offline-oriented test suite runnable with `python -m pytest -q`
- a public README test badge backed by the GitHub Actions workflow

Proof markers that still depend on GitHub/release state rather than repository files:

- release metadata upkeep
- GitHub About description
- GitHub topics

## Installation

You can install TriageCore locally for CLI access:

```bash
git clone https://github.com/coreytshaffer/TriageCore
cd TriageCore
pip install -e .
```

## Features

## Hackathon Demo

For a bounded operator walkthrough that works with existing commands, see [docs/workflows/hackathon_demo.md](docs/workflows/hackathon_demo.md).

For the judge-facing submission bundle, start with [docs/submission/README.md](docs/submission/README.md).

That demo is designed to support:

- TriageCore local-first plus optional Qwen Cloud escalation as the primary story
- safer AI-assisted SDLC as the secondary framing
- Clear Lake Watch or other environmental edge workflows as a future extension

### 1. The TriageDesk GUI
Launch the local control plane GUI to actively review tasks, monitor telemetry, and perform context planning:
```bash
triagecore desk
```
- **Read-Only Operator Console (Baseline Tag: `triagedesk-daily-driver-baseline-2026-06-25`):** The GUI acts strictly as a read-only telemetry and context-planning tool. To ensure the UI does not become a hidden execution surface, it relies exclusively on `triagedesk_adapter.py` and performs zero LLM calls, file writes, or ledger mutations directly.
- **Energy-Aware Routing:** `psutil` integration actively monitors your battery life. If your battery dips below 20% while unplugged, TriageCore refuses to run heavy LLM tasks and prompts you to plug in (Permacomputing in action).
- **Telemetry & Resource Accounting:** Tracks measured or heuristic resource estimates for energy consumption (kWh/Joules) and carbon emissions (gCO2e) in a local append-only ledger (`.triagecore/ledger.jsonl`).
- **Local-First Benefit Signals:** The dashboard foregrounds accepted yield, local-first routing share, accepted local work, and review-light tasks so the bench encourages continued evidence collection while formal reports remain baseline-bound.

### 2. Post-Execution Safety Validators
Audit the files your agents modify to ensure they didn't bypass the initial risk assessment:
```bash
triagecore audit <task_id> --files src/main.py
```
- **Scope Verification:** Flags modified files that were not in the original target list.
- **Profile Adherence:** Blocks changes if the task was rated `read-only`.
- **Escalation Detection:** Static analysis checks for `requests`, `socket`, `subprocess`, etc., if the task was classified as low-risk.

## Pluggable Local Backends

TriageCore supports pluggable backends so you can process tasks against any local runner without manually wrangling URLs. All local generations route through a unified `OpenAICompatibleBackend` adapter, and the Qwen Cloud path stays bounded behind explicit external-safe routing.

You can configure your `TriageClient` with the following presets:

### 1. Ollama (Default: `http://localhost:11434/v1`)
```python
from triage_core import TriageClient

client = TriageClient(backend_type="ollama", model="qwen2.5-coder:7b")
```

### 2. vLLM (Default: `http://localhost:8000/v1`)
```python
client = TriageClient(backend_type="vllm", model="Qwen/Qwen2.5-Coder-7B-Instruct")
```

### 3. llama.cpp (Default: `http://localhost:8080/v1`)
```python
client = TriageClient(backend_type="llama.cpp", model="local-model")
```

### 4. Custom Backend (e.g. LM Studio)
```python
from triage_core.backends import OpenAICompatibleBackend
from triage_core import TriageClient

backend = OpenAICompatibleBackend(
    name="lmstudio",
    base_url="http://localhost:1234/v1",
    model="local-model"
)
client = TriageClient(backend=backend)
```

## Scientific Methodology

TriageCore is also being developed as a scientific model evaluation and token-balancing workbench. Each task attempt can be treated as an experimental observation that records routing decisions, backend behavior, token use, validation outcomes, energy estimates, and human review results.

The project methodology is documented in [`docs/methodology.md`](docs/methodology.md). Supporting literature is collected in [`docs/references.md`](docs/references.md). Together, these describe the evidence loop for model evaluation, safety routing, mistake logging, and human-reviewed learning.

The shared evidence schema is documented in [`docs/evidence_schema.md`](docs/evidence_schema.md). The first repeatable study plan is [`docs/study_001_local_model_baseline.md`](docs/study_001_local_model_baseline.md), model/backend comparison is planned in [`docs/study_002_model_backend_comparison.md`](docs/study_002_model_backend_comparison.md), and Codex/Antigravity supervision is described in [`docs/codex_antigravity_bridge.md`](docs/codex_antigravity_bridge.md).

Use [`docs/verification_guide.md`](docs/verification_guide.md) for practical code, UI, study-evidence, and human-review verification checks.

## Permacomputing Orientation

TriageCore is inspired by sustainable and permacomputing practices that emphasize sufficiency, repairability, visible infrastructure, and graceful operation under constraints.

Rather than optimizing for maximum automation, TriageCore optimizes for bounded, reviewable, locally controlled developer-agent work.

**Design commitments:**
- Prefer local files over remote services.
- Prefer Markdown, JSON, and TOML over opaque state.
- Prefer small task packets over broad autonomous sessions.
- Prefer explicit permission recommendations over silent execution.
- Prefer deferral or refusal when a task is too broad, risky, or wasteful.
- Preserve human review as a first-class part of the workflow.
- Treat compute, attention, battery, trust, and hardware lifespan as scarce resources.

## Benchmark Tasks

TriageCore includes repeatable benchmark fixtures in [`benchmarks/tasks.jsonl`](benchmarks/tasks.jsonl). List them without contacting a backend:

```bash
triagecore benchmark --list-only
```

Run them against a local backend and append model-evaluation evidence to `.triagecore/ledger.jsonl`:

```bash
triagecore benchmark --backend-type ollama --model qwen2.5-coder:7b
```

Tag formal study runs so reports can exclude exploratory ledger history:

```bash
triagecore benchmark --study-id study_001 --run-id trial_001
```

Summarize benchmark evidence:

```bash
triagecore benchmark-report
triagecore benchmark-report --output reports/benchmark-report.md
triagecore benchmark-report --study-id study_001 --run-id trial_001 --output reports/study_001_benchmark_report.md
```

Compare backend/model pairs by giving each run a unique `run_id` under one study:

```bash
triagecore benchmark --study-id study_002 --run-id ollama_qwen25_coder_7b_trial_001 --backend-type ollama --model qwen2.5-coder:7b-triagecore
triagecore benchmark --study-id study_002 --run-id lmstudio_loaded_model_trial_001 --backend-type custom --base-url http://localhost:1234/v1 --model <loaded-model-name>
triagecore benchmark-report --study-id study_002 --output reports/study_002_model_backend_comparison.md
```

Comparison reports include `By Supervision`, `By Backend`, `By Model`, and `By Category` sections. When supervised benchmark records exist, reports also include a `Supervisor Reviews` table with decision counts and estimated supervisor token totals under the same study/run filter.

## Human-Reviewed Learning

TriageCore can generate pending learning proposals from ledger evidence, but it does not automatically change routing behavior:

```bash
triagecore propose-lessons
```

Record an explicit human decision:

```bash
triagecore review-lesson <proposal_id> --decision accepted --notes "Evidence supports this routing change."
```

Record a Codex or Antigravity supervisor decision for a task:

```bash
triagecore record-supervisor-review <task_id> --tool codex --decision needs_revision --notes "Local draft missed tests." --model gpt-5 --profile high
triagecore record-supervisor-review <task_id> --tool antigravity --decision accepted --notes "IDE supervisor accepted the local draft." --model gemini-3.1-pro-high --profile supervisor
```

Import supervisor usage from a verified JSON or JSONL artifact:

```bash
triagecore scan-supervisor-usage supervisor_logs\
triagecore import-supervisor-usage supervisor_usage.jsonl --tool codex --token-source imported_exact --dry-run
triagecore import-supervisor-usage supervisor_usage.jsonl --tool codex --token-source imported_exact
```

## CLI Handoff Generation

TriageCore provides a convenient CLI for generating agent task bundles offline:

### 1. Initialize Agent Configs
Generate a default `AGENTS.md` file in your repository:
```bash
triagecore init-agents
```

### 2. Generate a Codex Task
Create a standalone markdown task file (`triage_tasks/codex_task_low.md`) for Codex:
```bash
triagecore codex-task --prompt "Refactor the database connection string logic" --files src/db.py
```

### 3. Generate an Antigravity Bundle
Create a robust multi-file bundle (`.agent_tasks/my-slug/TASK.md`, `ACCEPTANCE_CRITERIA.md`):
```bash
triagecore antigravity-task --prompt "Add pytest coverage for handoff.py" --files tests/test_handoff.py --slug add-tests
```

## Development & Testing

TriageCore uses `pytest` to ensure all routing and safety logic operates completely offline without network calls. Tests actively mock the backend `requests` module to verify payload structures across Ollama, vLLM, and llama.cpp presets.

## Safety and Compliance Scope

TriageCore is a research-stage orchestration and workflow-control project. It is designed to support privacy-aware routing, local-first execution, human approval gates, and auditable task records.

TriageCore is not a certified safety system, compliance system, medical device, legal decision system, emergency dispatch system, or critical infrastructure control system. It does not guarantee safe, lawful, complete, accurate, or compliant outcomes.

Operators are responsible for validating outputs, configuring policies, reviewing logs, and ensuring that any deployment satisfies applicable legal, security, privacy, safety, and sector-specific requirements.

```bash
pip install pytest
pytest tests/
```

## License
MIT
