# CR-DD-011: Governed Plan Artifact And Exact Confirmation Linkage

## Status

Implemented locally after explicit human approval. Pending external review and
merge. This CR grants no execution authority.

## Implementation Incident Record

During validation, an intermediate ledger-root selection defect unintentionally
appended five privacy-safe `audit-self-test` events to the pre-existing
user-level ledger. No prompt, context, secret, or sensitive task content was
written. The root-selection defect was fixed before release validation, and
the events were preserved unchanged to respect the ledger's append-only
integrity semantics.

## Decision

CR-DD-011 is intentionally smaller than confirmed-plan execution.

CR-DD-010 previews through deterministic classification and a no-network
specialist forecast. The existing execution path may instead use
`TaskClassifier.classify()` with a configured model and
`SpecialistRouter.route_task()` with a live socket-dependent branch. There is
currently no supported way to inject the reviewed route into
`TriageClient.run_task` or prove that execution will use the same decision
inputs without a larger shared-decision-path refactor.

Therefore this CR implements only:

1. a deterministic, privacy-safe, operator-named plan artifact;
2. explicit confirmation of the exact reviewed artifact digest;
3. metadata-only task-ledger linkage and read-only inspection.

Execution of a confirmed plan is blocked and remains a future CR. This CR
does not add `--confirmed-plan`, execute after confirmation, route injection,
approval-and-resume, or any model/backend call.

## Implementation Authority

The operator approved implementation after the required branch-state preflight.
Authority remains limited to artifact creation, exact-digest confirmation, and
read-only linkage display.

Confirmation means only: “the operator reviewed this exact plan artifact.” It
is not general approval, execution authority, cloud authorization, admission,
acceptance, an authority grant, or satisfaction of a human-review gate.

## Implemented Interface

### 1. Write The Reviewed Plan

```text
tc run "<prompt>" --plan --model <profile> --task-id <id> \
  --plan-output <operator-path> [existing --files/--data/--privacy/--allow-cloud]
```

- `--plan-output` is valid only with `--plan`, `--model`, and an explicit
  `--task-id`.
- The existing stdout-only CR-DD-010 preview remains unchanged when
  `--plan-output` is absent.
- Stdout and the artifact derive from the same in-memory plan.
- The path is explicit. Its resolved target must not already exist; its
  resolved parent must already exist; every existing parent path component is
  checked for symlink/reparse behavior where the platform exposes it; and the
  target must not resolve inside the configured ledger, identity/key storage,
  or any other protected TriageCore state directory. Violations fail closed.
- Publication writes and fsyncs an exclusive same-directory staging file, then
  atomically creates the absent destination with a hard link. It never
  overwrites. Publication failure removes staging residue and leaves no
  destination artifact.
- No default plan directory is added.
- The artifact is deterministic canonical JSON with no timestamp or random ID.
- The command prints the complete `plan_body_digest` and
  `artifact_byte_digest`.
- No ledger is read or written during plan creation.

### 2. Confirm The Exact Artifact

```text
tc run-plan confirm --plan <path> --artifact-digest <sha256:64hex> \
  [--ledger-dir <dir>]
```

- The operator must repeat the complete lower-case `artifact_byte_digest`
  printed during plan creation, binding the confirmation act to the exact
  reviewed file bytes.
- The command validates the closed artifact contract, canonical serialization,
  embedded `plan_body_digest`, current full-file `artifact_byte_digest`, task
  ID, and persistent-privacy invariant before ledger access.
- Wrong, shortened, case-altered, stale, malformed, noncanonical, mutated, or
  privacy-unsafe artifacts fail closed and write nothing.
- A valid confirmation appends a metadata-only
  `run_plan_review_confirmed` event under the artifact task ID. If needed, it
  first writes minimal privacy-safe task scaffolding with no raw task content.
- Repeating the same confirmation is idempotent. A conflicting plan digest for
  the same task ID fails closed.
- Confirmation is never inferred from a default, prompt, environment variable,
  plan-file presence, `review_completed` event, admission artifact, authority
  manifest, signature, or evaluator result.

The confirmation event contains only:

- contract version;
- task ID;
- `plan_body_digest`;
- exact artifact-byte digest;
- decision `exact_plan_reviewed`;
- route posture and bounded ethical-firewall status;
- `execution_authority=false`;
- `general_approval=false`;
- `cloud_authorization=false`;
- `human_review_gate_satisfied=false`; and
- `artifact_accepted=false`.

It does not create `review_completed`, accepted, admission, authority, or
execution events.

### 3. Inspect The Linkage

`tc task show <task-id> [--ledger-dir <dir>]` gains a bounded `Run plan review
linkage` section. The optional read-only ledger override uses the same ledger
selection and validation rules as confirmation, so confirmations written to an
isolated/custom ledger remain inspectable.

- `plan_body_digest`;
- exact artifact-byte digest;
- exact-plan review confirmation present/absent;
- route and ethical-firewall posture;
- `execution_authority: false`;
- `execution_linkage: not_implemented`; and
- the existing event timeline.

No raw prompt, data, context path/content, matched firewall term, secret,
credential, or precise location is displayed.

## Plan Artifact Contract

The artifact is a closed `governed_run_plan.v1` object serialized as canonical
JSON. Unknown or missing fields fail closed.

The two digest values are distinct lower-case strings matching exactly
`sha256:[0-9a-f]{64}`:

- `plan_body_digest` is embedded in the artifact and is SHA-256 over the
  canonical UTF-8 JSON bytes of the closed `plan_body` object only. The
  `plan_body` object contains no digest field, so the hash input excludes every
  digest value.
- `artifact_byte_digest` is SHA-256 over the complete final artifact bytes,
  including the embedded `plan_body_digest`. It is printed and recorded in the
  confirmation event but is not embedded in the artifact, avoiding a
  self-referential hash.

Canonical JSON uses a TriageCore standard-library profile. Values are limited
to objects, arrays, strings, integers, booleans, and null; floats (including
non-finite values) are prohibited. Parsing rejects duplicate object keys.
Serialization recursively sorts object keys, uses compact `,` and `:`
separators with no insignificant whitespace, and uses `ensure_ascii=True`.
The resulting ASCII-compatible JSON text is encoded as UTF-8/ASCII bytes with
no BOM and no trailing newline. A parsed artifact must be byte-for-byte equal
to its reserialization before either digest is accepted. `plan_body_digest`
hashes the exact bytes produced by applying this same profile to the closed
`plan_body` object alone.

It contains:

- task ID and planner contract version;
- closed `plan_body` and its embedded `plan_body_digest`;
- declared model profile, privacy class, and cloud-intent flag;
- ordered source bindings using locator digests, content SHA-256, and byte
  lengths, not raw source paths;
- digests and lengths for the task instruction, assembled input, and inline
  input, not raw values;
- token estimate and usable budget;
- deterministic classification and risk/profile forecast;
- bounded ethical-firewall status and escalation label, never the matched term
  or raw reason;
- logical route, reason code, fallback depth, human-review posture, and
  forecast backend/model binding;
- bounded verification posture;
- non-secret configuration bindings used by the preview; and
- explicit `execution_authority=false` and `execution_evidence=false`.

It must not contain:

- prompt, inline data, or context-file content;
- raw context paths;
- matched privacy/firewall terms or raw reasons;
- secrets, credentials, tokens, environment variables, or credential-bearing
  URLs;
- model output or backend response;
- approval evidence;
- timestamps; or
- generated IDs.

Content digests provide linkage, not authenticity, identity, secrecy, safety,
or correctness. Low-entropy inputs may be guessable from unsalted digests, so
artifacts remain operator-controlled and are not public redaction artifacts.

## Confirmed Execution Blocker

Confirmed execution is explicitly out of scope because preview and execution
do not yet share one enforceable decision path.

A future CR must first choose and review one of these approaches:

- extract a pure shared decision builder used identically by preview and
  execution; or
- add a validated immutable execution-plan input to `run_task` while still
  rerunning current privacy and ethical-firewall checks.

That future CR must address current model-assisted classification,
socket-dependent specialist behavior, configuration drift, input-file TOCTOU,
one-shot consumption, cloud reauthorization, terminal handoff behavior, and
pre-backend ledger linkage. CR-DD-011 makes no claim that its confirmed
artifact can yet be executed faithfully.

## Security Invariants

- Confirmation binds the canonical semantics and exact reviewed file bytes.
- Confirmation is review evidence only.
- Raw task content enters neither artifact nor ledger.
- Human-only and ethical-firewall policy remain non-executable.
- Cloud intent in a plan is not cloud authorization.
- Plan mutation after confirmation requires a new artifact and confirmation.
- No execution code consumes confirmation in this slice.

## Non-Goals

- No `--confirmed-plan` or execution-after-confirmation.
- No route injection, `run_task` refactor, or decision-path unification.
- No auto-confirm, interactive default, general approval, or policy waiver.
- No execution of local, cloud, human-only, or handoff plans.
- No background execution, queue, daemon, polling, scheduler, resume, retry,
  checkpoint, or approval-and-resume.
- No raw prompt/data/context persistence.
- No TriageDesk or mobile changes.
- No backend, provider, probe, capability discovery, circuit breaker, degraded
  mode, routing policy, or cloud-path change.
- No budget enforcement, compaction, truncation, or context rewriting.
- No admission/authority/signature binding or new cryptography.
- No evaluator invocation, result verification, artifact acceptance, scoring,
  efficiency reporting, or improvement claim.

## Risks And Mitigations

- **Confirmation mistaken for approval:** event and display use
  `execution_authority=false` and `artifact_accepted=false`.
- **Digest mistaken for authenticity:** documentation and output state the
  linkage-only limitation.
- **Sensitive persistence:** closed schema, raw-path omission, bounded firewall
  codes, and the existing persistent-privacy invariant apply before writing.
- **Artifact mutation:** confirmation requires the exact full-file
  `artifact_byte_digest` and independently verifies the embedded
  `plan_body_digest`.
- **Semantic collision with review:** use `run_plan_review_confirmed`, never
  `review_completed`.
- **Future execution overclaim:** task show reports
  `execution_linkage: not_implemented`.
- **Hash disclosure:** artifact remains operator-controlled and carries the
  low-entropy limitation.
- **Ledger tampering:** current ledger evidence is inspectable, not
  automatically authentic; no signing claim is added.

## Acceptance Criteria

- [x] `--plan-output` requires `--plan`, `--model`, and explicit `--task-id`.
- [x] Existing stdout-only CR-DD-010 output remains unchanged without
  `--plan-output`.
- [x] Artifact creation refuses an existing target, missing parent, a
  symlink/reparse in any existing parent path component where detectable, and
  targets inside configured ledger, identity/key, or other protected
  TriageCore state directories.
- [x] Publication uses an exclusive same-directory staging file, fsyncs where
  supported, atomically creates the absent destination, never overwrites, and
  cleans staging residue on failure.
- [x] The artifact is deterministic canonical JSON, closed-contract,
  metadata-only, and persistent-privacy-safe.
- [x] No raw task/context content or raw source path appears in the artifact.
- [x] Repeated creation from identical inputs/configuration is byte-identical.
- [x] Plan creation prints distinct lower-case `plan_body_digest` and
  `artifact_byte_digest` values matching `sha256:[0-9a-f]{64}`.
- [x] `plan_body_digest` hashes only canonical `plan_body` bytes; the
  non-embedded `artifact_byte_digest` hashes the complete final artifact bytes.
- [x] Confirmation requires the exact full `artifact_byte_digest` repeated by
  the operator and independently verifies the embedded `plan_body_digest`.
- [x] Invalid or mutated artifacts fail before ledger mutation.
- [x] Confirmation writes only minimal task scaffolding when needed and one
  metadata-only `run_plan_review_confirmed` event.
- [x] Identical confirmation is idempotent; conflicting confirmation for the
  same task ID fails closed.
- [x] Confirmation creates no review, acceptance, approval, admission,
  authority, execution, route, or worker-result evidence.
- [x] Ethical-firewall/human-only posture is preserved as bounded metadata and
  never becomes executable.
- [x] `tc task show`, including its matching read-only `--ledger-dir`
  override, displays exact-plan review linkage and explicitly reports that
  execution linkage is not implemented.
- [x] Prompt/data/context values, raw paths, and matched sensitive terms never
  appear in artifact, ledger event, or task-show output.
- [x] No model/backend/network/subprocess call occurs during plan writing,
  confirmation, or inspection.
- [x] Existing `tc run`, stdout-only `--plan`, review, admission, authority,
  signature, privacy, and ledger behavior remains unchanged.

## Required Tests

- deterministic artifact bytes, canonical `plan_body_digest`, and complete
  final-file `artifact_byte_digest`;
- explicit-path, exclusive-create/no-overwrite, missing-parent,
  symlink/reparse-in-parent-chain, and protected-state-directory failures;
- simulated partial/crash files are invalid and unconfirmable;
- closed schema, unknown field, missing field, and canonical serialization;
- raw-content and persistent-privacy rejection;
- correct full `artifact_byte_digest` confirmation plus independent embedded
  `plan_body_digest` verification;
- wrong, shortened, case-altered, stale, and mutated artifact/body digest
  rejection;
- confirmation idempotence and conflicting-confirmation rejection;
- no `review_completed`, accepted, approval, admission, authority, execution,
  route, or worker-result event;
- ethical-firewall/human-only bounded metadata without term disclosure;
- task-show linkage, custom-ledger inspection through read-only `--ledger-dir`,
  default-ledger non-regression, and explicit
  `execution_linkage: not_implemented`;
- malformed ledger and ledger-write failures fail closed;
- traps for model, backend, socket/network, subprocess, and artifact overwrite;
- existing CR-DD-010 and `tc run` regressions.

## Approved Implementation Files

- `docs/change/requests/CR-DD-011-plan-confirmation-linkage.md`
- `triage_core/tc_cli.py`
- `triage_core/run_plan.py`
- `triage_core/run_plan_artifact.py` — new closed artifact/confirmation module
- `tests/test_tc_run_plan_artifact_cli.py`
- `tests/test_tc_run_plan_cli.py` — regression only
- `tests/test_tc_run_cli.py` — regression only
- `tests/test_cr_098_task_show.py` — linkage display only
- `docs/architecture/daily_driver_orchestrator_spec.md`
- `docs/daily_driver_quickstart.md`
- `docs/current_backlog.md`
- `docs/change/change_log.md`

`triage_core/client.py`, `triage_core/routers.py`, execution routing, and
`triage_core/task_ledger.py` reducer changes are not authorized by this CR.
Changes outside the list require a separately approved scope amendment.

## Verification

- `python -m pytest -q tests/test_tc_run_plan_artifact_cli.py tests/test_tc_run_plan_cli.py tests/test_tc_run_cli.py tests/test_cr_098_task_show.py`
- `python -m py_compile triage_core/run_plan_artifact.py triage_core/run_plan.py triage_core/tc_cli.py`
- `python -m pytest`
- `python -m triage_core.tc_cli audit --privacy-invariants`
- `git diff --check`

## Dependencies And Sequencing

- Depends on CR-DD-009 and CR-DD-010.
- Reuses append-only ledger events and `tc task show` without redefining
  `review_completed`.
- Preserves CR-095 and admission-evidence boundaries: inspectable evidence is
  not permission.
- A separately approved shared-decision-path CR is required before any
  confirmed execution.
- Durable sessions, resume, TriageDesk action, live probes, circuit breakers,
  budget enforcement, provider expansion, signing, evaluator integration, and
  efficiency reporting remain separate future work.
