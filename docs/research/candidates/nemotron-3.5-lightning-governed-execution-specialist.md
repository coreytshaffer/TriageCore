# Nemotron 3.5 Lightning Governed Execution Specialist — Research Candidate

Status: **nominated / documentation only / not authorized for installation, execution, or integration**
Recorded: 2026-08-11
Repository checkout consulted: `codex/agents-governance-separation` at
`424bc7a66dc51d73a46dd0980969d8312c553d4e`

## What this document is, and is not

This is a source-bound research nomination and proposed experiment protocol. It
does not authorize a model download, Ollama invocation, local-runtime probe,
benchmark run, backend configuration, route declaration, route binding,
automatic offload, adapter, fixture, telemetry, or code change.

It is deliberately unnumbered and is not entered in the Futures Register or
the implementation backlog. A later decision may promote a bounded experiment
to a Change Request; this document is not that decision.

No claim in this document establishes any of the following:

```text
ModelInstalled ≠ ObservedAvailable ≠ ModelCapable ≠ RouteAuthorizedForTask
```

In particular, a successful future local invocation would be evidence for that
attempt only. It would not authorize a logical route, override privacy or
authority gates, or establish that the model is suitable for a route class.

## Candidate identity and source record

| Field | Record |
| --- | --- |
| Candidate | NVIDIA Nemotron 3.5 Lightning 30B-A3B |
| Intended role under study | Local, bounded execution specialist; never a policy or authorization authority |
| Canonical model source | NVIDIA's [BF16 model card](https://huggingface.co/nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-BF16) |
| Local-distribution source considered | Ollama [library entry](https://ollama.com/library/nemotron-3.5-lightning) |
| Source type and access date | Primary vendor model card and distributor library page, accessed 2026-08-11 |
| Model-card release date | 2026-08-11 |
| Exact model artifact for an experiment | **Not pinned.** The Ollama `latest` / `30b` tag is mutable and must not stand in for an immutable artifact identity. |
| License reported by NVIDIA | OpenMDW 1.1; exact terms and compatibility are not yet reviewed for TriageCore use. |
| Local installation state | **Not observed.** No download or invocation was performed for this nomination. |
| Runtime state | **Not observed.** No local endpoint or inventory was consulted. |

### Relevant claims from the sources

- The NVIDIA model card reports **30B total parameters and 3B active
  parameters**, a hybrid Mamba-2 + MoE + selected-attention architecture,
  configurable reasoning, and vLLM tool-calling guidance. This is direct
  source support, not local performance evidence.
- NVIDIA reports up to 1M-token context support. Its card also describes a
  256K single-H100 reference deployment and a multi-GPU 1M example. Therefore
  1M is a model capability ceiling, not a practical local target for this
  candidate experiment.
- The Ollama page currently lists its `latest` / `30b` package as 25 GB with a
  1M context window. The page does not, by itself, establish the exact
  quantization, provenance of the binary relative to NVIDIA's reference
  weights, local RAM/VRAM requirement, or usable context length on this host.
- NVIDIA's throughput and task-completion-time statements are vendor benchmark
  claims. They are hypotheses for a controlled TriageCore study, not expected
  results and not evidence about this machine.

### Source quality, fit, and limitations

The NVIDIA card is the primary source for the reference model's stated
architecture, intended capabilities, release date, and license. The Ollama
page is the primary source for its currently advertised package size and tag,
but its mutable tag cannot provide reproducible artifact identity. Neither
source reports performance, memory use, tool reliability, failure behavior, or
task-completion time for this checkout, runtime, quantization, hardware, or
TriageCore task mix.

The model card's stated single-GPU reference is an 80 GB H100/A100. The 25 GB
Ollama package makes full 24 GB-VRAM residency unlikely once runtime overhead
is included, but that is a capacity inference rather than an NVIDIA hardware
requirement. CPU, hybrid, offload, and reduced-context operation remain **not
verified**.

## Dependency and supply-chain review

```text
Dependency: NVIDIA Nemotron 3.5 Lightning through a future exact Ollama artifact
Purpose: test a potential local execution specialist against bounded synthetic tasks
Provenance: NVIDIA model card and official Ollama library page observed; exact local
            artifact digest, artifact derivation, and license review not yet verified
Execution and data exposure: a future model runner would execute local inference;
            tool calling creates an additional control boundary and must receive only
            synthetic, local, non-secret fixtures during any initial experiment
Recommendation: defer introduction pending evidence and separately scoped authority
Authorization status: not granted by this review
```

Required controls before an installation or experiment:

1. Record an immutable model artifact identity, its source URL, license decision,
   Ollama/runtime version, and the exact local model name exposed by the runtime.
2. Isolate the first study from credentials, personal prompts, repositories with
   sensitive data, external network tools, and write-capable tools. No automatic
   model pull, update, or cloud fallback.
3. Establish a bounded disk, RAM, VRAM, context, concurrency, and timeout budget
   before downloading. Stop rather than evicting or degrading unrelated work.
4. Treat model-produced tool calls as untrusted proposals. The harness—not the
   model—must enforce schemas, allowlists, denials, timeouts, and termination.
5. Record the remaining uncertainty: model weights and generated content are
   third-party artifacts; this review does not establish their safety, security,
   fitness, or legal suitability.

## TriageCore fit

The candidate is interesting because its advertised role resembles a possible
division of labor: a capable planner may propose an approach while a local
specialist performs bounded repetitive work. TriageCore's research question is
stricter than vendor routing: the control plane must evaluate privacy,
authority, capability evidence, task characteristics, and the permitted
execution envelope before any backend is selected.

The current checkout does not grant that relationship. Current capability work
keeps `Configured`, `ObservedAvailable`, `ObservedUnavailable`, and `Unknown`
separate; a reachable runtime alone does not prove a local route class, and
class-to-model binding remains deferred. A model result can inform a future
human decision, but cannot act as planner approval, route authorization, or
evidence of authority.

### Terminology boundary with CR-DD-018

"Execution specialist" in this nomination is descriptive of a proposed
experiment role only. It does **not** mean `SpecialistRouter`, invoke
`SpecialistRouter.route_task()`, decide whether to offload or hand off work, or
alter the independent resilience-routing/capability-resolution decision.
The nomination neither produces nor depends on CR-DD-018's proposed
`specialist_offload_decision` evidence event. Any future experiment that needs
that event, specialist-router behavior, or route integration requires its own
explicitly authorized implementation scope.

## Research question and hypothesis

**Research question:** Under fixed local conditions and bounded synthetic
fixtures, does the exact Lightning artifact improve governed execution outcomes
over an already observed baseline without increasing invalid structured output,
unsafe tool proposals, unexplained handoffs, recovery failures, or human review
burden?

**Hypothesis:** Lightning may improve end-to-end completion time for bounded
structured transformations and tool-mediated tasks while preserving validator
success and conservative stopping behavior. This is an inference from the
vendor's stated intended use and must be tested, not assumed.

The study is not designed to establish general intelligence, broad safety,
frontier-model equivalence, practical 1M local context, or a production routing
policy.

## Proposed experiment protocol

### Preconditions for a separately authorized study

- A human grants a bounded installation and experiment authorization that names
  the artifact, download destination, storage budget, runtime, host, and
  permitted actions.
- The exact artifact identity and all runtime settings are captured before the
  first invocation; mutable aliases are supplementary labels only.
- An already installed baseline is selected and its exact identity recorded.
  The baseline must use the same fixture corpus, tool contract, context cap,
  timeout policy, and review process.
- A new fixture/harness change, if required, receives its own Change Request,
  allowlist, and implementation authority. Existing Study 002 fixtures may be
  reused only where their task and validator definitions match; they do not by
  themselves define a tool-recovery experiment.
- The first tool surface is a deterministic in-process fake tool. It has no
  network, credentials, filesystem writes, subprocesses, or access to project
  contents beyond the minimal synthetic fixture.

### Fixed conditions

For every run, record:

- TriageCore checkout, study ID, unique run ID, fixture version and fixture
  digest;
- model artifact identity and source, runtime/backend version, quantization,
  model identifier, sampling parameters, reasoning mode, tool parser, context
  cap, output cap, timeout, concurrency, warm/cold state, and retry policy;
- host operating system, CPU, RAM, accelerator and VRAM, free disk before and
  after, and measured peak memory where safely available;
- validator version, fake-tool response variant, failure category, and whether
  any human review occurred.

No result may compare different fixture sets or timeout/context policies as if
it were a model-only comparison.

### Task families and negative controls

Use synthetic, privacy-safe prompts with deterministic expected results:

| Family | Primary measure | Required negative control |
| --- | --- | --- |
| Structured transformation | schema-valid **and** semantically valid output | malformed-but-parseable output rejected by validator |
| Tool selection | correct tool, or correct no-tool decision | irrelevant tool offered; no-tool-needed task |
| Instruction persistence | constraints retained across bounded steps | conflicting late instruction must not override fixed policy |
| Unavailable capability | no fabricated success after denial | tool absent or explicitly denied |
| Tool-error recovery | safe terminal/retry behavior after an error | malformed result and timeout response |
| Escalation calibration | correct `handoff_required` / terminal outcome | task beyond the local envelope or authority boundary |

"Fail closed" is a harness and TriageCore property. The model-specific outcome
is whether it proposes a permitted next step, preserves the failure evidence,
and refrains from claiming a nonexistent tool result.

### Sample and measures

Start with **100 independent attempts per model-condition/task-family**, using
the same randomized order and a pre-recorded seed where sampling applies.
Increase to 500 only after reviewing the first 100 for fixture ambiguity,
validator defects, runtime instability, and cost. Do not pool distinct task
families into a single quality rate.

For each family report both numerator and denominator, plus a 95% binomial
interval for binary rates:

- valid structured-output rate;
- semantic-validator pass rate;
- correct tool/no-tool/denial behavior rate;
- fabricated-success rate after unavailable or failed tools;
- recovery outcome distribution and unexpected-handoff rate;
- wall-clock task-completion time (median, p95), elapsed seconds, input/output
  tokens when reported, and tokens per second;
- peak memory or an explicit `not observed` marker;
- human-review minutes and workload for reviewed attempts.

Record every timeout, parser failure, unavailable backend, and invalid result.
Do not silently retry away failures or average them into a performance claim.

### Review and promotion criteria

An initial study is interpretable only when the model and baseline have complete
runs under the same conditions, failures are categorized, and a human has
reviewed all unexpected safety/authority outcomes plus a documented sample of
ordinary completions. A faster result is insufficient if it raises invalid
output, fabricated success, unexpected handoff, or review burden.

Promotion to a route-binding or integration proposal requires separate human
review of the evidence and a new Change Request. That proposal must state the
exact model identity, scope, capability evidence, route-class rule, privacy
envelope, fallback behavior, enforcement point, and stop conditions. Benchmark
success alone never supplies those elements.

## Stop conditions

Stop the candidate study and seek direction if any of these occurs:

- artifact identity, license basis, storage/RAM/VRAM budget, or experiment
  authority is missing or ambiguous;
- any fixture carries private repository content, credentials, personal data, or
  a real external tool/action;
- the model runner needs a new dependency, privileged environment change,
  automatic cloud fallback, or unreviewed executable behavior;
- the harness cannot deterministically validate the claimed task outcome;
- an observed result is being used to alter routing, configuration, authority,
  or implementation without separately scoped approval.

## Disposition

Nominated. The next action, if desired, is a separately authorized, pinned,
isolated experiment—not installation or routing integration.
