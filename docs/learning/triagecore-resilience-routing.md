# TriageCore Resilience Routing

## Purpose

This document defines the first design slice for a TriageCore resilience router.

The resilience router decides which model, tool, or handoff path should receive a task when cloud services, API credits, internet connectivity, LM Studio, local memory, or deterministic tools change availability.

This is TriageCore work. SafeTask AI can provide examples, but SafeTask AI should not own this router.

## Candidate Ranking

| Field | Value |
| --- | --- |
| Candidate ID | `TCP-007` |
| Title | Resilience and capability-aware routing |
| Proposal type | assignment policy |
| Expected gain | high |
| Evidence quality | medium |
| Local LLM fit | high |
| Verification readiness | high |
| Implementation effort | medium |
| Risk level | medium |
| Confidence score | `0.84` |
| Priority bucket | `active_candidate` |

Ranking note:

This candidate is high ROI because it directly improves local autonomy when internet, credits, or cloud agents are unavailable. Risk stays medium because routing must not silently approve sensitive tasks or hide provider failures.

## Design Rule

TriageCore should not merely call a model.

It should route work through an explicit capability policy that considers:

- internet availability
- cloud/API credit availability
- LM Studio availability
- local model availability
- memory headroom
- task class
- complexity
- privacy or sensitivity
- deterministic tool availability
- recent failure history
- validation requirements

## Route Modes

| Route mode | Use when | Example worker |
| --- | --- | --- |
| `cloud_primary` | Internet and credits are available; task is high-complexity or final review. | Codex/Jules/cloud coding agent |
| `cloud_secondary` | Cloud is available and task is normal complexity. | General cloud assistant |
| `local_heavy` | Cloud is degraded or task is local/private/high-complexity. | LM Studio Qwen3.6-27B Q4/Q5 class |
| `local_fast` | Task is small, repetitive, or helper-shaped. | Qwen2.5-Coder 7B class |
| `deterministic` | A tool can answer more reliably than a model. | tests, parsers, search, linters |
| `human_handoff` | No reliable route exists or human approval is required. | Corey review packet |

## Initial Fallback Chain

```text
cloud_primary
  -> cloud_secondary
  -> local_heavy
  -> local_fast
  -> deterministic
  -> human_handoff
```

Privacy or local-only tasks should skip cloud routes:

```text
local_heavy
  -> local_fast
  -> deterministic
  -> human_handoff
```

## System State

TriageCore should maintain a compact system state before assignment:

```json
{
  "internet_ok": true,
  "cloud_credits_ok": false,
  "lm_studio_ok": true,
  "local_heavy_available": true,
  "local_fast_available": true,
  "memory_headroom_mb": 8192,
  "local_tools_ok": true,
  "current_mode": "degraded_cloud"
}
```

## Task Profile

The router should combine system state with a task profile:

```json
{
  "task_id": "task-2026-06-05-001",
  "task_class": "ui_api_slice",
  "complexity": "medium",
  "privacy_level": "local_ok",
  "requires_repo_context": true,
  "requires_tool_use": true,
  "human_review_required": true,
  "max_latency_seconds": null
}
```

## Route Decision Event

Each route decision should be logged:

```json
{
  "event_type": "route_decision",
  "task_id": "task-2026-06-05-001",
  "selected_route": "local_heavy",
  "selected_model": "Qwen3.6-27B-Q4_K_M",
  "reason": "cloud_credits_unavailable",
  "internet_ok": true,
  "cloud_credits_ok": false,
  "lm_studio_ok": true,
  "task_class": "ui_api_slice",
  "task_complexity": "medium",
  "privacy_level": "local_ok",
  "fallback_depth": 2
}
```

## Worker Result Event

Each result should also be logged:

```json
{
  "event_type": "worker_result",
  "task_id": "task-2026-06-05-001",
  "route": "local_heavy",
  "status": "completed",
  "validation_status": "passed",
  "duration_ms": 84231,
  "tokens_in": 9211,
  "tokens_out": 2144,
  "failure_type": null
}
```

## Circuit Breakers

TriageCore should stop sending repeated work to failing providers.

| Backend | Failure threshold | Cooldown |
| --- | --- | --- |
| `cloud_primary` | 3 failures | 300 seconds |
| `cloud_secondary` | 3 failures | 300 seconds |
| `local_heavy` | 2 failures | 120 seconds |
| `local_fast` | 5 failures | 60 seconds |

Failure examples:

- provider unavailable
- credit failure
- model load failure
- timeout
- repeated validation failure
- context window failure

## Mode States

Use stable mode states to avoid flapping:

| Mode | Meaning |
| --- | --- |
| `normal` | Cloud, local models, and deterministic tools are available. |
| `degraded_cloud` | Internet or credits are unreliable; local heavy is preferred for substantial tasks. |
| `offline_local` | Cloud is unavailable; local models and tools are primary. |
| `local_minimal` | Heavy local model is unavailable; use local fast and deterministic tools. |
| `deterministic_only` | LLMs are unavailable; produce tool output and handoff packets. |
| `human_handoff` | No reliable automated route exists. |

Require stable successes before returning to a higher mode. For example, after cloud recovery, require three successful cloud checks or two minutes of stable availability before returning from `offline_local` to `normal`.

## MVP Policy

1. If privacy is `local_only`, skip cloud.
2. If cloud is healthy and credits are available, use cloud for high-complexity planning/review.
3. If cloud is degraded or credits are unavailable, use `local_heavy` for medium/high complexity.
4. Use `local_fast` for low-complexity helper tasks.
5. Use deterministic tools first for parsing, syntax, search, tests, and schema checks.
6. If no route is reliable, produce a human handoff packet.

## Verification Plan

First tests should cover:

- cloud healthy routes high-complexity work to `cloud_primary`
- cloud credits unavailable routes high-complexity work to `local_heavy`
- local-only privacy skips cloud
- local heavy unavailable routes small work to `local_fast`
- deterministic task routes to `deterministic`
- repeated provider failures open a circuit breaker
- recovered provider does not immediately flap back to normal mode

## Relationship To Existing TriageCore Learning Artifacts

- Assignment preflight should include system state and preferred route mode.
- Context packs should include route constraints, such as local-only or degraded-cloud mode.
- Outcome records should log selected route, validation result, fallback depth, and failure type.
- Waste controls should treat repeated provider failures as route-level waste.
- Ranking system should keep speculative autonomous reassignment below threshold until the resilience router has enough outcome data.

## First Implementation Slice

Status: implemented as a static policy slice in `triage_core/routing/resilience_router.py` with focused tests in `tests/test_resilience_router.py`.

Initial TriageCore-owned files now exist outside SafeTask AI:

```text
triage_core/routing/
  resilience_router.py

tests/
  test_resilience_router.py
```

Future slices can add model profiles, health checks, circuit breakers, route/result ledger events, and a project-level routing doc. Keep the implementation boring and explicit: static policy first, then clear route/result telemetry, then deterministic tests around each behavior.
