# CR-141 legacy Qwen credential destination binding

## Status

Implementation authorized on November 26, 2026. The base revision is 114faf951470525e92d698c84eeffe841cbfd67f.

## Problem

The accepted CR-135 implementation protects governed `tc run`. A legacy
cloud invocation and callers of the Qwen factory or class can still
construct a Qwen backend whose request transport uses the configured
destination without the approved destination check. The fix belongs at
the shared Qwen request boundary so all supported Qwen construction
paths enforce the same credential-release rule.

[CR-135 closeout](https://github.com/coreytshaffer/TriageCore/blob/114faf951470525e92d698c84eeffe841cbfd67f/docs/change/requests/CR-135-governed-backend-destination-policy.md#L719) ·
[Qwen backend construction](https://github.com/coreytshaffer/TriageCore/blob/114faf951470525e92d698c84eeffe841cbfd67f/triage_core/backends.py#L487) ·
[Legacy cloud invocation](https://github.com/coreytshaffer/TriageCore/blob/114faf951470525e92d698c84eeffe841cbfd67f/triage_core/client.py#L897)

## Accepted design

Reuse CR-135’s canonical DashScope HTTPS origin, port, and base path.
Bind legacy and direct Qwen generation to the existing guarded request
transport. The allowed request is an exact generation POST. Require
the prepared request to match the binding before the bearer credential
can leave the process. Keep redirect following disabled and prevent
ambient proxy, netrc, or CA settings from changing the approved transport
policy.

Use configured explicit model IDs and the existing default model.
Refuse a model that still requires discovery before sending any
credential. Make a configuration refusal return a bounded reason without
printing the supplied URL, API key, or response body. The legacy client
keeps its existing cloud opt-in, packet checks, and graceful handoff.

The design reuses the approved origin and transport rules.
Additional providers, regional origins, direct local-backend restrictions,
configuration migrations, and deployed or live provider tests require
their own review. The existing governed destination contract and local
backend behavior are regression checks.

## Authorized writable paths

| Path | Purpose |
| --- | --- |
| `triage_core/backends.py` | Install and enforce the binding for legacy and direct Qwen instances. |
| `triage_core/destination_policy.py` | Reuse the canonical Qwen request policy and construct the legacy transport binding. |
| `triage_core/client.py` | Map destination and setup refusals to the existing legacy cloud handoff. |
| `tests/test_qwen_backend.py` | Cover direct and factory use with dummy credentials and a recording transport. |
| `tests/test_qwen_cloud_routing.py` | Cover legacy cloud routing, refusal, packet eligibility, and graceful handoff. |
| `tests/test_destination_policy.py` | Verify that configuration precedence agrees with the guarded Qwen factory. |
| `docs/change/requests/CR-141-legacy-qwen-credential-destination.md` | Record authority, scope, and verified results. |

## Implementation authority

On November 26, 2026, Corey Shaffer accepted the proposal and design and granted implementation authority with the response “Approve CR-141 and draft PR.” The original grant covered six paths, local synthetic tests, and publication of the tested candidate as a draft pull request. Implementation acceptance, merge, release, and closeout remain separate decisions.

Corey added `tests/test_destination_policy.py` with the response “Authorize this test file.” The expanded grant covers the seven listed paths.

## Acceptance criteria

- [x] Direct Qwen construction, the Qwen factory, and the legacy cloud
  client reject destinations outside the approved identity before any send.
- [x] Approved generation reaches the canonical URL once using a
  synthetic bearer credential. Credentialed discovery, destination
  mutation, redirects, and ambient transport settings fail closed.
- [x] Legacy configuration failures preserve bounded handoff and
  the application’s packet and cloud-authorization rules.
- [ ] Governed Qwen and non-Qwen backend focused regression tests pass.
  Run the full project suite and record results against the tested revision.
- [ ] Tests run locally with fixtures and recording transports. The draft
  includes the exact approved path list and observed verification results.

## Verification

The focused Windows Python 3.12 run passed 579 tests with five symlink
tests skipped because this Windows session cannot create symlinks.
The run includes the Qwen backend and legacy routing tests, destination
policy and guarded transport, workspace operations, and reviewer
traceability and integration. Qwen tests used synthetic credentials
and recording adapters. They also verified that a direct worker can
generate after an unsupported probe and that an invalid model setting
produces a bounded legacy handoff with route evidence enabled. The
draft pull request records full-suite results against the candidate
revision.

[Change management policy](https://github.com/coreytshaffer/TriageCore/blob/114faf951470525e92d698c84eeffe841cbfd67f/docs/change/change_management.md)
