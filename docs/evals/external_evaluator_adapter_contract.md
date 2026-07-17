# External Evaluator Adapter Contract

Contract identifier: `external_evaluator_adapter_contract.v0`

## Status and Purpose

CR-129 is contract-only. It defines the minimum information and safety
properties required before TriageCore may launch a separately installed
external evaluator. It adds no subprocess implementation and no CLI command.
Scoring, pass/fail judgment, findings, and score interpretation remain owned by
the external evaluator.

Implementation stops here because the authoritative evaluator executable or
package and version, bundle-to-argument mapping, working directory, result
location and ownership, evaluator exit meanings, output sensitivity,
network posture, and portable process-tree timeout behavior are not yet pinned
by a versioned profile. Guessing any of them would turn a file-contract
boundary into an implicit execution and trust boundary.

## Reserved Future CLI

A later, separately approved code-bearing CR may use this exact shape:

```text
tc eval invoke-external \
  --bundle <explicit-root> \
  --evaluator-profile <closed-profile> \
  --timeout-seconds <bounded-value>
```

This command does not exist in CR-129. The future command must not accept an
arbitrary `--executable`, free-form evaluator arguments, generic argv
forwarding, shell snippets, or operator-provided command templates. A closed
profile selects the entire executable and argument contract.

The suggested default timeout is 300 seconds. A future implementation must
accept only whole seconds in the inclusive range 1 through 3600.

## Required Versioned Evaluator Profile

No adapter may be implemented until an authoritative, reviewed profile pins:

- a closed profile identifier and profile schema version
- executable identity and an exact or otherwise closed executable path rule
- evaluator package or module identity and version
- a fixed argv-list template mapping the validated bundle's
  `fixtures/safety_boundaries_v0.jsonl` and `actuals/` paths
- an explicit working directory rather than ambient caller cwd
- the evaluator result/output contract, output path ownership, overwrite
  behavior, cleanup responsibility, and sensitivity classification
- network posture, including whether network is required, prohibited, or
  explicitly unverifiable by the wrapper
- evaluator exit meanings, including which evaluator exits constitute wrapper
  success or failure
- stdout/stderr encoding, per-stream byte caps, and safe diagnostic treatment

The profile must be versioned independently of the bundle manifest. It must not
derive executable identity, argv, cwd, outputs, or network posture from bundle
contents.

## Required Pre-Launch Gate

A future adapter must run CR-128
`tc eval validate-handoff --bundle <bundle-root>`-equivalent validation before
launch. Any validation failure stops before process creation with
`bundle_invalid`. Validation proves internal bundle consistency only; it does
not authenticate the evaluator or authorize execution.

## Future Process Safety Requirements

A future implementation must:

- construct an argv list and launch with `shell=False`
- set stdin to `DEVNULL`
- use an allowlisted minimal environment
- exclude credentials, proxy settings, model configuration, endpoint
  configuration, model/runtime configuration, runtime secrets, and unrelated
  TriageCore configuration by default
- enforce the bounded timeout selected within the 1–3600 second range
- terminate the evaluator's full process tree on timeout or interruption using
  tested Windows and POSIX behavior, then wait for confirmed termination
- treat stdout and stderr as untrusted bytes, enforce independent output caps,
  decode only with the profile-pinned encoding, and never echo unbounded or
  sensitive output

Environment stripping alone does not prove offline execution. Child processes
may still reach the network through operating-system facilities, inherited
machine configuration, or evaluator behavior. A profile must state its network
posture, and `network_posture_unverified` remains a valid stop reason when the
wrapper cannot establish that posture.

## Reserved Wrapper Exit Semantics

The future wrapper reserves:

| Wrapper exit | Meaning |
| --- | --- |
| `0` | The pinned evaluator profile launched and completed according to the profile's success contract. This is not a TriageCore score or approval. |
| `1` | Wrapper validation, launch, timeout, evaluator, output, or interruption failure. |
| `2` | Argparse usage error. |

Raw evaluator exit codes must never be propagated as wrapper exit codes or
interpreted without the pinned profile. Stable future failure reasons may
include:

- `bundle_invalid`
- `evaluator_profile_missing`
- `evaluator_profile_invalid`
- `evaluator_not_found`
- `evaluator_version_mismatch`
- `evaluator_launch_failed`
- `evaluator_timeout`
- `evaluator_nonzero_exit`
- `evaluator_output_invalid_encoding`
- `evaluator_output_limit_exceeded`
- `evaluator_interrupted`
- `network_posture_unverified`

These names reserve a bounded diagnostic vocabulary; CR-129 does not emit them.

## Output and Ownership Boundary

The external evaluator, under its future versioned profile, owns any scored
result artifact. TriageCore does not create evaluator output, parse it, import
it, render it, persist it, write a report, or record it in the ledger. The
profile must define result ownership and sensitivity before launch behavior can
be approved. Captured stdout or stderr is diagnostic process output, not a
scored result contract.

## Stop Conditions

A future adapter must stop before or terminate launch when:

- CR-128 bundle validation fails
- the profile is missing, unknown, malformed, or version-mismatched
- executable identity, package/module version, argv mapping, cwd, result
  ownership, exit meanings, encoding, caps, or network posture is unresolved
- the executable is missing or does not match the profile
- safe cross-platform process-tree termination cannot be established
- timeout, interruption, invalid encoding, output overflow, or an unrecognized
  evaluator exit occurs

No fallback may switch to an arbitrary executable, shell command, free-form
argv, model/backend call, or network service.

## Trust and Uncertainty Limits

A valid bundle plus a pinned profile would establish deterministic wrapper
inputs, not evaluator authenticity, evaluator correctness, scoring validity,
offline execution, sandboxing, approval, safety certification, or provenance.
Process isolation and network containment require controls outside this file
contract. Evaluator output remains untrusted and externally interpreted.

## CR-129 Non-Goals

- no `tc eval invoke-external` implementation
- no subprocess or process-tree execution code
- no CLI parser or runtime adapter module
- no result parsing, importing, rendering, persistence, report creation, or
  ledger write
- no TriageCore filesystem writes of any kind
- no evaluator output creation by TriageCore
- no scoring, pass/fail interpretation, approval, or safety claim
- no network, model, backend, routing, admission, approval, identity, or worker
  integration
- no adversarial fixture expansion or evaluator profile selection
