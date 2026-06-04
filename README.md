# TriageCore

**A Local-First Developer-Agent Control Harness**

TriageCore provides safety rails, task classification, and structured handoff packets for AI coding agents. Instead of giving agents unbounded access or treating expensive cloud models as an automatic fallback, TriageCore evaluates tasks locally using a TaskClassifier and a Local Worker Council. It assigns permission profiles and generates `.md` packets (Handoff Packets) so that cloud models act as supervisors (like Codex and Antigravity) rather than primary executors.

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

## Installation

You can install TriageCore locally for CLI access:

```bash
git clone https://github.com/coreytshaffer/TriageCore
cd TriageCore
pip install -e .
```

## Pluggable Local Backends

TriageCore supports pluggable backends so you can process tasks against any local runner without manually wrangling URLs. All local generations route through a unified `OpenAICompatibleBackend` adapter.

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

### 4. Custom Backend (e.g., LM Studio)
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

## Features

### 1. The TriageDesk GUI
Launch the local control plane GUI to actively manage tasks, monitor telemetry, and interact with the local LLM engine:
```bash
triagecore desk
```
- **Live Local Engine:** Hooks directly into Ollama or LM Studio to stream generated code right into the UI.
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

## Scientific Methodology

TriageCore is also being developed as a scientific model evaluation and token-balancing workbench. Each task attempt can be treated as an experimental observation that records routing decisions, backend behavior, token use, validation outcomes, energy estimates, and human review results.

The project methodology is documented in [`docs/methodology.md`](docs/methodology.md). Supporting literature is collected in [`docs/references.md`](docs/references.md). Together, these describe the evidence loop for model evaluation, safety routing, mistake logging, and human-reviewed learning.

The shared evidence schema is documented in [`docs/evidence_schema.md`](docs/evidence_schema.md). The first repeatable study plan is [`docs/study_001_local_model_baseline.md`](docs/study_001_local_model_baseline.md), model/backend comparison is planned in [`docs/study_002_model_backend_comparison.md`](docs/study_002_model_backend_comparison.md), and Codex/Antigravity supervision is described in [`docs/codex_antigravity_bridge.md`](docs/codex_antigravity_bridge.md).

Use [`docs/verification_guide.md`](docs/verification_guide.md) for practical code, UI, study-evidence, and human-review verification checks.

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

```bash
pip install pytest
pytest tests/
```

## License
MIT
