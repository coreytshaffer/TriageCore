# Experiment Trace Smoke

## Purpose

CR-093 adds a reviewer-facing dry-run export path for the experiment trace
contract introduced in CR-092. It writes one deterministic synthetic trace
artifact to an explicit output directory without calling a model, changing
routing behavior, writing to the main ledger, or claiming measured energy
savings.

## What It Proves

This smoke path proves:

- the observable trace contract can produce a concrete JSON artifact
- the trace stays linked to run, fixture, group, backend, quality gate, and
  claim-validity lineage
- reviewer-visible evidence can be exported without live runtime benchmarking

This smoke path does not prove:

- llama.cpp or Ollama benchmark performance
- measured energy savings
- autonomous orchestration quality
- production runtime behavior

## Artifact Shape

The exporter writes:

- `experiment_trace_record.json`
- `experiment_trace_summary.md`

The JSON artifact uses synthetic `token_proxy` evidence only. That means the
artifact may claim token or latency efficiency under a passing quality gate, but
it must not claim measured energy savings.

## Fail-Closed Rules

The exporter rejects:

- missing `output_dir`
- `output_dir` values that point to a file
- synthetic traces that fail CR-092 validation
- quality-gate violations for efficiency claims
- energy claims that exceed the measurement tier
- missing quality-gate methods

## Suggested Usage

Use the pure Python seam directly for now:

```python
from triage_core.experiment_trace_smoke import export_experiment_trace_smoke

result = export_experiment_trace_smoke(".triagecore/smoke/experiment-trace")
print(result.trace_path)
```

The explicit output directory keeps reviewer evidence local and reviewable
without turning the export path into ledger mutation or benchmark execution.
