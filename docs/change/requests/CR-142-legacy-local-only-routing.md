# CR-142 legacy local-only destination enforcement

## Status

Implementation authorized on November 26, 2026. The base is TriageCore `main` at
`31e6bd3a5c730f55c1e6f56e7bfb43f9217be571`.

## Finding

Legacy `TriageClient.run_task` calls a configurable model classifier
and a connectivity probe during routing. The local route check then
accepts a route label without binding the backend that receives the task.
The headless `triagecore run-pipeline` command builds and calls a
configured backend directly. Task packets also default to external
eligibility. The fresh Daybreak scan confirmed the legacy exposure on
the reviewed revision. CR-135 already binds governed `tc run` routes.

[Fresh Daybreak finding](https://chatgpt.com/mcp-app/connector_openai_defense_factory/open_defense_factory#/findings/raw/rf_wfr_b6b48f4496e07160632af031a7eb0a11c6229d17e679ed31fda7040f6e76864b%3Awfo_04354d3590dac0cc33074fd0b486a1d3e52d6cb773f8c830bba185c56c9addde%3Aocc_91833e6ca37f075b8ad76416) · [Original finding](https://chatgpt.com/mcp-app/connector_openai_defense_factory/open_defense_factory#/findings/acf_ccd0718399f72804a01b382587492f1d) · [Legacy client](https://github.com/coreytshaffer/TriageCore/blob/31e6bd3a5c730f55c1e6f56e7bfb43f9217be571/triage_core/client.py#L365-L393) · [Headless pipeline](https://github.com/coreytshaffer/TriageCore/blob/31e6bd3a5c730f55c1e6f56e7bfb43f9217be571/triage_core/cli.py#L921-L971)

## Proposed behavior

- Default implicit task privacy to `restricted` with external models
  disabled. External eligibility requires explicit public metadata and
  external-model permission. The existing packet scanner and cloud
  opt-in remain required for the explicit cloud route.
- Use the existing deterministic classifier for a local-only legacy
  task. Its specialist route evaluation skips the connectivity probe and
  retains handoffs for medium-risk, high-risk, and oversized input. The
  policy records external routing as unavailable for this task.
- Require a CR-135 literal loopback binding for generation on either
  legacy local route. Resolve supported built-in backend settings once
  and use a fresh guarded transport for discovery and generation.
  Refuse remote or ambiguous destinations, Qwen on a local route, and
  injected backends whose implementation the guard cannot verify. The
  trust decision uses the bound transport and its owner.
- Make `run-pipeline` local-only, with the same destination check before
  reading source files or running a backend. Keep loopback streaming,
  successful output files, and ledger summaries. A policy refusal
  returns a nonzero status and a bounded reason without an output
  artifact or an automatic escalation.

Literal loopback addresses are the supported local configuration.
Installations using hostname aliases or externally hosted models will
need to update their configuration or use the explicit cloud route where
eligible. A third-party injected backend that lacks the verified
transport returns a safety handoff or the existing local-route refusal.

An alternative is to retire legacy local execution and require governed
`tc run` everywhere. That would bring execution under the governed
decision contract in one move and would also require migrating the
legacy pipeline and library callers. Reusing the existing transport
guard at the two affected entry points keeps this change focused on
destination enforcement.

## Authorized writable paths

| Path | Purpose |
| --- | --- |
| `triage_core/task_packet.py` | Privacy defaults for implicit tasks. |
| `triage_core/client.py` | Select local-only classification and verified local dispatch. |
| `triage_core/routers.py` | Evaluate the local-only specialist route without a connectivity probe. |
| `triage_core/destination_policy.py` | Reuse the literal loopback profile for legacy local binding. |
| `triage_core/backends.py` | Construct supported legacy backends with the sealed transport. |
| `triage_core/cli.py` | Protect the `run-pipeline` entry point and map policy refusals to CLI status. |
| `triage_core/public_export.py` | Preserve CR-134's public classification basis and existing approval checks. |
| `tests/test_capability_binding.py` | Preserve the capability and audit checks through guarded transport. |
| `tests/test_compression.py` | Mark two synthetic compression fixtures explicitly public. |
| `tests/test_task_packet.py` | Verify privacy defaults and explicit metadata. |
| `tests/test_safe_taskpacket.py` | Verify packet and classification boundaries. |
| `tests/test_client.py` | Exercise normal dispatch and engine outcomes with recording adapters. |
| `tests/test_local_only_routing.py` | Cover pre-dispatch checks and destination enforcement. |
| `tests/test_route_decision_audit.py` | Cover the privacy and refusal evidence on the affected routes. |
| `tests/test_legacy_pipeline_local_only.py` | New tests through the public pipeline command. |
| `docs/change/requests/CR-142-legacy-local-only-routing.md` | Record the approved scope, authority, and verification evidence. |

## Acceptance criteria

- Implicit tasks and explicit local-only packets make no classifier or
  connectivity calls. A remote, unverified, or changed destination
  creates zero unauthorized sends and records a bounded refusal.
- An approved loopback backend handles discovery, ordinary generation,
  and streaming using the shared transport. Redirects and ambient
  proxy, authentication, and CA overrides cannot reroute the request.
- The pipeline refuses an unapproved backend before reading file
  contents and leaves the requested output absent. An approved loopback
  run preserves the output, streaming, and ledger contracts.
- Regression checks cover explicit external-safe Qwen, governed
  `tc run`, privacy and route audit, and approved local execution. Use
  synthetic input and recording adapters, followed by the full suite
  and the hosted matrix. Reassess the High finding on the merged
  revision after the candidate is accepted.

## Authority

On November 26, 2026, Corey Shaffer approved the design and the original
thirteen paths, synthetic testing, and publication in a separate draft
pull request. Corey separately approved `tests/test_capability_binding.py`,
`tests/test_compression.py`, and `triage_core/public_export.py`. The grant
covers the sixteen listed paths and the two affected legacy entry points. Implementation
acceptance, merge, release, and closeout are separate decisions.
