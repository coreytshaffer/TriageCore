# TriageCore

A lightweight, local-compute-first orchestration harness. It uses flagship cloud models strictly for cognitive routing and oversight, aggressively offloading code generation and formatting to local workers (like Nemotron 30B) to minimize API burn and maximize token efficiency.

## Overview

In modern agentic loops, developers often pass the entirety of a workspace or large data chunks directly to expensive cloud models (Claude Sonnet 3.5, GPT-4o, Gemini 1.5 Pro). While these models possess incredible reasoning, executing mundane text-parsing, code-formatting, and boilerplate generation wastes expensive cloud execution tokens.

**TriageCore** formalizes a "Supervisor-Worker Loop":
1. **The Cloud Supervisor** plans the task and establishes strict formatting constraints.
2. **The Local Worker** executes the repetitive code generation and raw parsing. 
3. **The Triage Engine** watches the local generation budget (timeouts) and automatically escalates back to the Cloud Supervisor if the local model fails or gets stuck in a loop.

## Installation

```bash
pip install -r requirements.txt
python setup.py install
```

## Quick Start

You can configure TriageCore to talk to any LiteLLM-compatible cloud model, and any OpenAI-compatible local model (e.g. LM Studio, Ollama).

```python
from triage_core import TriageClient
from triage_core.validators import PythonSyntaxValidator

client = TriageClient(
    local_url="http://127.0.0.1:1234", 
    cloud_model="gemini/gemini-1.5-pro", # Uses LiteLLM standard model naming
    timeout_seconds=45
)

result = client.run_task(
    prompt="Generate a Python function that adds two numbers. Output raw code only.",
    data="Context: no math functions exist yet.",
    validator=PythonSyntaxValidator.validate
)

print(f"Executed via: {result['source']}")
print(result['output'])
```

## Architecture Notes & Failure Taxonomy

If you are building your own Hybrid orchestration workflows, you need to be aware of the exact failure modes local models run into when acting as execution grunts.

1. **The Generation Ceiling:** Local model failure is rarely a reasoning issue; it is a raw output length issue. A 90-second timeout on a local GPU generally supports <150 tokens depending on hardware. Any task requiring more than ~100 tokens of generation must either be aggressively minimized or routed to the cloud orchestrator.
2. **The Regex Bottleneck:** Complex string patterns or regular expressions dramatically slow down tokenization. Be prepared to pre-escape strings before sending them to the local worker.
3. **Idempotent Retries:** If a local generation hits the timeout wall, the TriageEngine will gracefully intercept the error and route the payload to your flagship model instead. The process is completely transparent to your broader application loop.

## Quality Gates

TriageCore comes with `PythonSyntaxValidator`, which uses native `py_compile` to statically evaluate generated Python code without executing it. If a local model generates code that is syntactically invalid (e.g. missing colons or bad indentation), TriageCore catches it instantly and escalates the failure back to the Cloud model for a successful fallback generation. 
