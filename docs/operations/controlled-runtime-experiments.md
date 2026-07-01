# Controlled Runtime Experiments

## Purpose

Controlled runtime experiments compare agent, model, and runtime configurations
against the same task fixture. The goal is not to prove that one runtime is
always faster. The goal is to identify the lowest-burden route that still passes
the required quality gate for a specific task class.

A credible experiment keeps these inputs fixed:

- task fixture
- input constraints
- output contract
- token budget
- scoring rubric
- measurement tier
- warm or cold start policy, when live capture is added later

This slice does not make live model calls. It defines the deterministic planning
and result-record layer that later benchmark commands can use.

## Compared Groups

Useful first groups are:

- `single_large_model`: one larger model handles the whole task.
- `small_specialist_agents`: planner, executor, and reviewer are smaller bounded
  agents.
- `large_planner_small_executor`: a stronger planner makes the structural
  decision, then smaller agents execute bounded work.
- `small_first_escalation`: a smaller model attempts the task first and escalates
  only if the quality gate fails.
- `no_agent_direct_call`: one prompt and one response, with no decomposition.

These groups can compare Ollama, llama.cpp, and other OpenAI-compatible local
runtimes by recording backend metadata through the runtime efficiency ledger.

## Quality Gates

Quality gates are mandatory for efficiency claims. Token savings do not matter
when the candidate route produces invalid output.

A failed result can still be useful evidence, but it must mark:

```json
{
  "efficiency_claim_valid": false,
  "reason": "candidate route failed quality gate"
}
```

This prevents fake wins where a small model saves tokens by producing unusable
work.

## Measurement Boundaries

Token savings are proxy evidence. They can support claims about reduced token
load, but they are not measured energy savings.

Energy-saving claims require an energy-capable measurement tier:

- `software_energy_estimate`
- `wall_power_measured`

For `token_proxy` and `runtime_proxy`, measured energy fields may be omitted.

## Route-Decision Review Example

A strong first experiment is `route_decision` review:

- A: `single_large_model`
- B: `single_small_model`
- C: `small_model_plus_reviewer`
- D: `large_planner_small_reviewer`
- E: `small_first_escalation`

The metric is whether the group can produce a valid route-decision review packet
that passes schema and policy checks. The result then records token, latency,
quality, and energy-evidence tier through the runtime efficiency record.
