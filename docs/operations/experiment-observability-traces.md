# Experiment Observability Traces

## Purpose

An experiment trace record is the durable join point between a synthetic
experiment result and a future evidence corpus. It keeps every efficiency claim
observable, traceable, and data-driven by linking the task fixture, agent
group, backend profile, runtime efficiency record, quality gate, and claim
validity in one fail-closed artifact.

This slice does not add live model calls, benchmark runners, or runtime
migration. It defines the contract that later capture paths must satisfy.

## Required Trace Fields

Every trace record must include:

- `experiment_id`
- `run_id`
- `task_fixture_digest`
- `agent_group_id`
- `runtime_backend_profile_id`
- `runtime_efficiency_record_id`
- `quality_gate_id`
- `quality_gate_result`
- `claim_validity`
- `lineage`

The embedded runtime efficiency record keeps the trace self-describing even when
the broader evidence store is exported or filtered.

## Fail-Closed Rules

The contract rejects:

- traces without `experiment_id`
- traces without `run_id`
- traces without `task_fixture_digest`
- traces without `agent_group_id`
- traces without `runtime_backend_profile_id`
- traces without `runtime_efficiency_record_id`
- efficiency claims when the quality gate result failed
- energy-valid claims when the measurement tier is only `token_proxy` or
  `runtime_proxy`
- failed quality gates without an explicit `failure_reason`
- lineage mismatches where the candidate group does not match the trace group

These checks prevent orphan claims such as "llama.cpp was more efficient" when
the record cannot prove which task, which group, which baseline, and which
quality gate produced that assertion.

## Minimal Example

```json
{
  "schema_version": "experiment_trace_record.v1",
  "trace_id": "trace-route-review-001",
  "created_at": "2026-06-30T00:00:00Z",
  "experiment_id": "exp-route-review-001",
  "run_id": "run-candidate-001",
  "task_fixture_digest": "sha256:fixture-001",
  "agent_group_id": "small_first_escalation",
  "runtime_backend_profile_id": "llama_cpp_qwen_7b_q4",
  "runtime_efficiency_record_id": "eff-run-candidate-001",
  "quality_gate_id": "route_decision_review_v0",
  "claim_validity": {
    "efficiency_claim_valid": true,
    "energy_claim_valid": false,
    "reason": "token_proxy_only"
  },
  "lineage": {
    "baseline_group_id": "single_large_model",
    "candidate_group_id": "small_first_escalation"
  }
}
```

## Claim Boundary

Token and latency improvements can be marked valid only after the candidate
passes the required quality gate. Energy claims need more: the measurement tier
must be `software_energy_estimate` or `wall_power_measured`, and the underlying
runtime efficiency record must carry a measured baseline-versus-candidate energy
comparison.

That keeps the evidence boundary explicit:

- token proxy claims are allowed as token proxy claims
- energy claims are blocked until the measurement tier supports them
- baseline comparison language must stay anchored to lineage fields
