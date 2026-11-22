# CR-138 — Saved document-revision review with a recorded human assessment

## Status

**Closed out on 2026-11-21 (Pacific).** [Closeout record](#closeout).

**Proposal and design accepted at `eb431f4`. Implementation accepted
through `64bb94c`.**

Both live checks are complete for `efe28d7`.
[Live verification record](#live-verification-record).
[Local transport correction](#transport-correction-authority).
The corrective candidate `cfdef2c` is accepted for implementation.
[Correction handback](#transport-correction-handback) ·
[Corrective acceptance and draft publication](#corrective-candidate-acceptance-record).
[Corrected build live-check authority](#corrected-build-live-check-authority).
[Saved DC-03 stop](#corrected-build-dc-03-stop).
[Response-completion correction handback](#response-completion-correction-handback) ·
[Response-completion acceptance and draft publication](#response-completion-correction-acceptance-record).
Both fresh live checks and informed reviews are complete on `697f8e1`.
[Fresh live-check authority](#fresh-live-check-authority-for-697f8e1) ·
[Fresh live verification record](#fresh-live-verification-record-for-697f8e1).
The CR-138 GitHub source release is published from `022b4a1`.
[Source release verification](#source-release-verification).

| Decision | State |
| --- | --- |
| Proposal acceptance | Accepted at `eb431f4`. [Decision record](#proposal-acceptance-record) |
| Design acceptance | Accepted at `eb431f4`. [Decision record](#design-acceptance-record) |
| Implementation authority | **Chat approval recorded after handback.** The original grant required this record before it became effective. No open Claude implementation grant. [Approval and sequence](#implementation-authority-record) |
| Implementation acceptance | **Accepted at `efe28d7`, `cfdef2c`, and `64bb94c`.** [Original decision](#implementation-acceptance-record) · [Transport correction](#corrective-candidate-acceptance-record) · [Response-completion correction](#response-completion-correction-acceptance-record) |
| Merge authority | **Authorized for PR #203.** Merged to `main` as `022b4a1`. [Decision record](#merge-authority-record) · [Merge verification](#merge-verification) |
| Release authority | **Authorized for the CR-138 GitHub source release.** [Decision record](#release-authority-record) · [Source release verification](#source-release-verification) |
| Closeout | **Authorized and closed out on 2026-11-21.** [Closeout record](#closeout) |

Human approval requirement: each stage above needs its own explicit operator
decision, recorded in this document, scoped to the named change and the exact
file, system, and action bounds below. A grant for one stage does not imply the
next unless the operator deliberately names and bundles stages.

Type, per the [backlog scope taxonomy](../../current_backlog.md#backlog-scope-taxonomy):
**adjacent application** (a document-revision review workflow). It does not
claim to strengthen the governance kernel. It must preserve these kernel
properties: review and human control (a model or rule finding is never the
decision), evidence and reconstruction (originals stay byte-identical and
later assessments are linked events), and privacy and provenance (raw evidence
stays in an explicit private store).

Tracking: first-delivery milestone of *TriageCore MVP — repeatable local
workflows* ·
[CHE-87](https://linear.app/cherryvox/issue/CHE-87) (versioned review and
local attempt) ·
[CHE-88](https://linear.app/cherryvox/issue/CHE-88) (durable run and feedback
records) ·
[CHE-89](https://linear.app/cherryvox/issue/CHE-89) (first-delivery checks
only). CHE-90 to CHE-92 (offline checkpoint replay, rollback of managed files,
and the solo acceptance trial) are outside this CR.

### Identifier census

CR-138 is the next numeric identifier in the observed namespace. At the
initial census on 2026-11-20:

- `docs/change/requests/` at local `HEAD` `eaa05d9` and at `origin/main`
  `d634f5a` both end the numeric series at CR-137. `git ls-remote origin
  refs/heads/main` returned `d634f5aa4923b451ca348e01feca2cfb2b0734fc`.
- No local or remote branch or tag name contains `cr-138`, and
  `git log --all --grep=CR-138` returned nothing.
- GitHub pull request and issue searches for `CR-138` in
  `coreytshaffer/TriageCore` returned no results.
- A repository-wide search for `checklist_review`, `checklist-review`,
  `R-DOCREV`, `C-AGREE`, `CHE-87`, `CHE-88`, and `CHE-89` found no existing
  file or record.

Rechecked for proposal acceptance on 2026-11-20. `main` at `d634f5a` still
ended at CR-137. The GitHub searches found draft PR #203 and its branch as
the only CR-138 matches, with no matching issue.

## Problem

The operator cannot yet run one saved document-revision review procedure on
several inputs with a local model, inspect the evidence behind a result, and
record a human decision that survives reopening the review.

The R01 development run showed why the human decision has to be separate and
inspectable. On synthetic case DC-02, the local model (`qwen3.5:4b`) returned
the correct finding, `insufficient evidence`, for an unsupported reason. It
stated that the controlling register "contains an entry for Document ID
EQ-INV-07 but only for Revision 2". The register has no EQ-INV-07 entry. Its
revision-2 row is for FC-214 and its revision-4 row is for EQ-INV-12. The cited
labels all exist, yet none supports the reason, and the citations omit S1.L05.
An agreeing rule and policy produced the same finding. A workflow that showed
only the finding would hide the defect.

Existing surfaces do not cover this:

- `tc build-review` (CR-BW-001) records one exclusive human decision on a
  software change packet. It has no model attempt, no document case, and no
  linked revision of an earlier assessment.
- The standard ledger (`.triagecore/ledger.jsonl`) is metadata-only by
  invariant ([checklist row 2](../../operations/control-plane-invariant-checklist.md)).
  It cannot hold the case text and raw model output needed for later
  inspection.
- `triage_core/backends.py:OllamaBackend` selects a model automatically when
  none is set, uses `requests` with environment proxies and redirects at their
  defaults, and does not check a model digest. It is a payload and timing
  reference only.

## Proposed scope

Add one operator flow to the existing `tc` CLI: a `checklist-review` command
group backed by one versioned workflow definition, a durable local review store
(SQLite metadata plus content-addressed private artifacts), a single
loopback-only local-model boundary, and read-only evidence inspection.

### Exact file scope

The base is `origin/main` at `d634f5aa4923b451ca348e01feca2cfb2b0734fc`. The
current local branch `test/field-notebook-provenance-unknown-check`
(`eaa05d9`) adds only `tests/fixtures/field_notebook/evidence_cases_v0.json`
and is not part of this CR. Build in an isolated worktree pinned to the agreed
base. Recheck these paths against that base before editing.

| Path | Change |
| --- | --- |
| `triage_core/checklist_review.py` | New. Frozen workflow definition (ID, version, digest), bounded case parser, R-DOCREV v0.1 rule, model output parser, C-AGREE v0.1 policy, closed vocabularies, and opaque evidence references. Pure: no I/O. |
| `triage_core/checklist_review_store.py` | New. `ReviewStore`: SQLite schema, immutable definitions, original artifacts, append-only run and review events, projections, and metadata summaries. |
| `triage_core/checklist_review_local.py` | New. The single loopback model boundary (`ReviewModel`) and `run_review` orchestration. |
| `triage_core/checklist_review_cli.py` | New. `configure_parser(parser)` and `run(args) -> int`, following `triage_core/build_review_cli.py`. |
| `triage_core/tc_cli.py` | Parser registration and dispatch for `checklist-review` only, mirroring the `build-review` blocks at lines 3028–3034 and 3374–3378 at the base. No other edit. |
| `tests/test_checklist_review.py` | New. Rule, parser, and policy checks. |
| `tests/test_checklist_review_store.py` | New. Persistence, chronology, immutability, failure, privacy, and denominator checks. |
| `tests/test_checklist_review_local.py` | New. Model boundary and attempt-state checks with an injected transport. |
| `tests/test_checklist_review_cli.py` | New. Recorded DC-02 inspection and review through the real command group. |
| `tests/fixtures/checklist_review/` | New. `workflow_docrev_v1/` (system text and user template), `cases/DC-02.txt`, `cases/DC-03.txt`, and `recorded/R01_DC-02_slm.txt` plus a provenance note. The recorded response is used only by the test harness. |
| `docs/operations/checklist-review-first-delivery.md` | New. Operator steps, Windows `python -m triage_core.tc_cli` equivalents, and the exact recorded and live verification commands. |

No change to `pyproject.toml` (standard-library `sqlite3` and `http.client`
only), `backends.py`, `destination_policy.py`, `task_ledger.py`,
`privacy_invariants.py`, routing, `tc run`, TriageDesk, CI, or the README.
Updates to `docs/current_backlog.md` and `docs/change/change_log.md` are
lifecycle records made at the relevant later stages, not part of the
implementation grant.

### System and action scope

- **Network:** the live path may send exactly two request kinds, `GET
  /api/tags` and `POST /api/chat`, to the fixed loopback endpoint
  `127.0.0.1:11434`. No host name, environment variable, configuration value,
  or command-line option can change the host, port, or path. Any other
  provider or destination requires a separate grant.
- **Model:** the one tag and expected digest saved in the workflow definition.
  No automatic selection, no pull, no load or unload request.
- **Local execution:** the client enforces its loopback destination. The
  Ollama local API can invoke cloud models, so before each live attempt the
  operator verifies that the installed pinned model is local and confirms
  that the running Ollama instance has cloud features disabled. Ollama's
  startup log can witness the setting. Record the operator's confirmation
  separately from the observed model tag and digest.
  [Ollama Cloud](https://docs.ollama.com/cloud) ·
  [Local-only configuration](https://docs.ollama.com/faq#how-do-i-disable-ollamas-cloud-features)
- **Writes:** the operator names a private local `--store` outside shared,
  synced, and version-controlled folders. The review store and its private
  artifacts are the only write destination. Tests use temporary directories.
- **Live verification:** two operator-run commands using the synthetic DC-03
  and DC-02 cases, one saved workflow, and the installed pinned local model.
  This evidence uses the cloud-disabled runtime and private store described
  above, after explicit implementation authority for the live check.

### Out of scope

Hover or focus timeline UI (milestone 2), offline checkpoint replay, rollback
of managed files, and the solo acceptance trial (CHE-90 to CHE-92); external or
cloud providers; integration with `tc run`, routing, TriageDesk, or the
destination-policy slice 2; signing; scoring or ranking models; any claim
about real documents.

## Design

### Workflow definition (frozen)

A definition is saved once under an opaque workflow reference, such as
`docrev-v1`. `save` takes the fixed system text and user template from
`triage_core/checklist_review.py`, which is part of the installed package.
It freezes both byte strings as private artifacts. The fixture files test
their identity and are independent of the runtime lookup. The definition
metadata contains:

- the artifact IDs and SHA-256 digests of the exact R01 system text and user
  template from the run card;
- rule `R-DOCREV v0.1`, R01 response parsing, and policy `C-AGREE v0.1`
  identifiers;
- the model profile: Ollama tag, expected digest, and request settings. The
  defaults use R01's `options` (`temperature 0`, `top_p 1`, `seed 7`,
  `num_predict 256`, `num_ctx 4096`) and the top-level `think false` and
  `stream false` fields;
- a case limit of 8 KiB, a serialized chat request limit of 32 KiB, and the
  endpoint limits specified under the local model boundary.

The definition digest covers the canonical JSON metadata, including both
template digests. Saving a reference that already exists with different
content fails with `definition_conflict`. A changed definition gets a new
reference. Reopening a definition verifies the referenced template bytes
before rendering any model input. Missing or changed template bytes stop the
attempt with an evidence gap.

### Case parsing

`parse_case(raw: bytes) -> ReviewCase` accepts bounded UTF-8, a matching
`BEGIN CASE` and `END CASE` envelope, labelled `FILE:` sections for the
request and work product plus any supplied source excerpts, and lines of the
form `<LABEL>  <text>`. Malformed framing, duplicate labels, unsupported file
sections, invalid UTF-8, and oversize input stop with distinct input
reason codes before inference. A structurally valid case can omit the
controlling-source designation or the named excerpt. That produces an
explicit evidence gap and the rule finding `insufficient evidence` without
substituting a context source. The case object binds its exact bytes by digest
and maps each unique label to the supplied line.

### Rule R-DOCREV v0.1

`apply_rule(case) -> ComponentResult` reads the Document ID and Revision only
from the work-product header lines, and the controlling source only from the
request. It keeps register rows whose Document ID cell matches exactly,
character for character, then tests in order:

1. a required header field is missing → `insufficient evidence`, with
   `R1_target_field_missing`; a missing source designation or excerpt yields
   the same finding with `R2_controlling_source_absent`;
2. no row counts → `insufficient evidence`, citing every entry row;
3. an exact revision with Decision `Approved` → `match`;
4. any counting row with an empty Revision or Decision → `insufficient
   evidence`;
5. an exact revision with any other Decision → `insufficient evidence`;
6. otherwise → `mismatch`.

Blank cells and a lone em dash are empty. The rule cites each supplied header
line it read and the relevant register rows. It shows missing fields as gaps.
The rule ignores Remarks by design, so an automatic result is always
provisional and review stays available.

Expected results: DC-03 → `match` citing S1.L04. DC-02 → `insufficient
evidence` citing S1.L03, S1.L04, and S1.L05. A row with the same revision and
date but a different Document ID never counts.

### Model output and policy C-AGREE v0.1

`parse_model_result(case, raw) -> ComponentResult` uses the R01 run card's
parsing rule. Trim surrounding whitespace, remove one outer Markdown fence
with optional `json` designation, and parse one strict JSON object. Require the
exact `case_id`, a string `finding` in the three allowed values after trimming
and lowercasing, a list of strings in `cited_lines`, and a string `reason`.
Ignore extra keys. Shape or syntax failure yields `returned_invalid` with a
closed reason code. The raw text is preserved for every completed reply.

Resolve single labels and same-source ranges such as `S1.L03-S1.L05` only
against the recorded case. Record resolution separately as `all`,
`some_unresolvable`, or `none_cited`. A parsed answer with an unresolved
citation is still a completed, parsed answer. Expose the unresolved reference
as an evidence gap. The operator assesses whether the source supports the
explanation, even if all labels resolve. Changes to parsing or policy behavior
require a new workflow version.

`combine(rule, model) -> PolicyResult`: if both components are valid and their
findings agree, the policy finding is that finding. A disagreement or an
invalid model result yields `insufficient evidence` with `review_needed`. Both
components and their reasons are retained. Agreement does not mark the
evidence as assessed. The projection shows `agreed`, `evidence unassessed`
until a human assessment exists. A stopped or failed attempt exposes the
stages reached and its reason code. A model call that never completed has no
parsed finding or C-AGREE result.

### Store

`ReviewStore(root)` owns a SQLite database and an `artifacts/` directory under
the explicit root.

- **Artifacts:** frozen templates, case bytes, raw model output, exact
  serialized chat request bodies, and optional notes. The store stages bytes
  in a temporary file inside its artifact directory, flushes the complete
  file to storage, verifies its digest, and publishes it atomically without
  overwriting a digest path. Reuse an existing artifact only after verifying
  its complete bytes against the expected digest. A partial or corrupt file
  never qualifies as committed evidence. Metadata uses opaque artifact IDs.
  Model citations resolve only against labels in the recorded case.
- **Events:** append-only rows keyed by run ID and a per-run increasing
  sequence, with item ID (initially `revision-approval`), step (`attempt`,
  `rule`, `model`, `policy`, `human`), and an event ID. A human event also
  references the target result event and any earlier human event it revises.
  Validate that the target is an earlier rule, model, or policy result of this
  run and item and that `--supersedes`, if given, names an earlier human event
  of the same run and item. Reject an invalid link before appending. The event
  and its artifact references commit in one transaction after the complete
  artifacts verify. Acknowledge after reading back the record. A complete
  unreferenced file from an interrupted transaction is inert.
- **Immutability:** schema triggers reject `UPDATE` and `DELETE` on
  definitions and events. The current result is a projection over ordered
  events.
- **Metadata privacy:** use explicit fields for identifiers and artifact
  references, digests, closed codes, statuses, and measurements. Check every
  metadata record and summary with
  `privacy_invariants.assert_persistent_privacy_safe`. Store free text and
  template bytes in private artifacts. The standard ledger has no role in
  this workflow.

Separate recorded values: finding correctness (`correct`, `incorrect`,
`unknown`), evidence support (`supported`, `unsupported`, `unknown`),
completion status, and human disposition (`accepted`, `revised`). A valid
completed model result that the operator later revises stays completed.

### Measurements

- Model generation seconds come from the runtime's reported `eval_duration`,
  with `total_duration` and `load_duration` kept separately.
- Active operator seconds come only from an explicit `--active-seconds` on the
  review action.
- End-to-end elapsed seconds have a declared scope: attempt start to policy
  result, and attempt start to saved human decision.
- `unknown` means a required measurement was unavailable. `inapplicable`
  applies only to a stage that does not occur, such as model generation in a
  human event.
- Summaries report each value over known observations, coverage over eligible
  observations, and the missing count. A missing optional reason does not
  remove an otherwise complete row from a metric.

### Local model boundary

Record the attempt start before network I/O. For a live run,
`--confirm-local-runtime` records that the operator verified the cloud-disabled
runtime and installed model for that attempt. Without confirmation, record a
stop before either request. Save the case and rule result before model
preflight so the run can show the available evidence after a stop.
`ReviewModel` resolves the exact configured tag and digest with a single
`GET /api/tags`. Chat requires both a matching tag in a well-formed response
and a verified private artifact for the prepared request.

| Stage and condition | Attempt status | Reason code |
| --- | --- | --- |
| Live runtime confirmation absent | `stopped` | `runtime_locality_unconfirmed` |
| Tags connection fails before a response, or non-200 status other than redirect | `stopped` | `runtime_unavailable` |
| Tags deadline exceeded | `stopped` | `tags_timeout` |
| Tags redirect | `stopped` | `transport_refused` |
| Tags response exceeds cap | `stopped` | `tags_response_too_large` |
| Malformed or truncated tags envelope, missing required identity fields, or duplicate matching tag | `stopped` | `tags_invalid_response` |
| Tag absent from a valid list | `stopped` | `model_not_installed` |
| Matching tag reports a different digest | `stopped` | `model_digest_mismatch` |
| Serialized chat request exceeds cap before sending | `stopped` | `request_too_large` |
| Chat redirect | `failed` | `transport_refused` |
| Chat connection fails before a response, or non-200 status other than redirect | `failed` | `completion_failed` |
| Chat deadline exceeded or response exceeds cap | `failed` | `timeout` or `response_too_large` |
| Chat reply is truncated or has an invalid or incomplete Ollama envelope | `failed` | `chat_invalid_response` |
| Completed chat reply, model text rejected by the parser | `returned_invalid` | parser reason code |
| Completed chat reply, model text accepted by the parser | `returned_valid` | none |

Persist the stop or failure with its reason. A stopped preflight sends zero
chat requests. Accept a bounded chat envelope with `done: true` and a string
`message.content` as a completed model reply, with parser status and the
runtime's termination reason recorded independently. Each chat request has
exactly two messages, the frozen system text and the frozen user template
rendered with one candidate case. Evaluator material, the recorded response,
and later corrections are outside those inputs. Record the settings sent and
runtime metadata observed, and leave unavailable metadata unknown. A repeat
gets a new run ID and may refer to the earlier run.

**Transport (D1).** Use standard-library `http.client` with the constant
destination `127.0.0.1:11434`, the two fixed method/path pairs, and no proxy,
redirect, fallback or retry. Tags has a 5-second deadline and 256 KiB response
body cap. Chat has a 240-second deadline and 64 KiB body cap. Each deadline is
absolute and monotonic, from before connection through request send, status,
headers, and body. A socket inactivity timeout is an additional bound. Abort
the owned connection at the deadline even if bytes keep arriving. Enforce
each size cap during reads rather than relying solely on declared length.
Use an injected connection and clock to exercise this production control
flow without network access in tests.

### Command group

```text
tc checklist-review --store <dir> save --workflow docrev-v1 --model qwen3.5:4b --model-digest <sha256>
tc checklist-review --store <dir> run  --workflow docrev-v1 --case <DC-03.txt> --confirm-local-runtime
tc checklist-review --store <dir> run  --workflow docrev-v1 --case <DC-02.txt> --confirm-local-runtime
tc checklist-review --store <dir> show --run <run-id>
tc checklist-review --store <dir> show --run <run-id> --item revision-approval --evidence
tc checklist-review --store <dir> review --run <run-id> --item revision-approval \
    --target <model-event-id> --finding "insufficient evidence" --disposition revised \
    --label-assessment correct --evidence-assessment unsupported \
    --cite S1.L03 --cite S1.L04 --cite S1.L05 --reason-code no_matching_document \
    [--supersedes <human-event-id>] [--note-file <path>] [--active-seconds <n>]
```

- `show` opens the existing store read-only and fails closed on a missing
  store or unknown run. It walks from the overall decision
  to the item, each component's finding and citations, then the cited lines
  resolved against the recorded case only. It includes both work-product header
  lines and the whole controlling register. A missing or altered artifact
  appears as a visible gap (`evidence_missing` or `evidence_digest_mismatch`)
  while the result IDs and human decisions stay visible. The detail view prints
  the same run and item IDs and the command that returns to the run view.
- `save`, `run`, and `review` are explicit mutations into the named store.
  Errors print closed reason codes and never echo case or model text.
- `--cite` accepts only labels present in the recorded case.

## Acceptance criteria

Each named test file runs and fails before its implementation, then passes, so
the handback can show which missing behaviour each test catches.

**Rule, parser, and policy (CHE-87):**

- [ ] DC-03's rule result is `match` citing S1.L04. DC-02's is `insufficient
  evidence` citing S1.L03–S1.L05.
- [ ] A row with the same revision and date but a different Document ID does
  not count.
- [ ] A well-formed case with a missing controlling source is saved and yields
  `insufficient evidence` with a visible gap. A malformed envelope or duplicate
  label stops input processing with a distinct closed reason code.
- [ ] R01-compatible parsing accepts a single JSON fence, normalized findings,
  extra keys, and a same-source citation range. Malformed model JSON stays
  `returned_invalid`. A parsed answer with an unresolved citation keeps its
  finding and shows the separate citation gap.
- [ ] Agreement, disagreement, and an invalid model result give the C-AGREE
  results above, with both components retained.
- [ ] `python -m pytest tests/test_checklist_review.py -q` passes without a
  runtime.

**Store and feedback (CHE-88):**

- [ ] A new store instance reopens the same run with strict chronology,
  byte-identical original model output, an unchanged original definition, and
  a later linked human event.
- [ ] Simulate interruption during artifact publication and a failed event
  write. Prior records reopen intact. A partial or corrupt artifact is never
  linked by a successful event, and a complete existing artifact is reused
  only after digest verification.
- [ ] A `review` using a target or superseded event from another run or item
  fails before an event is appended. Valid corrections keep the original and
  later events readable in order.
- [ ] Sentinel source and model text never appear in summaries, error messages,
  or SQLite metadata columns. Frozen templates live in verified private
  artifacts, with their references and digests in metadata. The standard
  ledger is neither created nor modified.
- [ ] Mixed measured and unknown values give correct known counts, coverage,
  and missing counts.
- [ ] `python -m pytest tests/test_checklist_review_store.py -q` passes.

**Local attempt (CHE-87 with CHE-88 records):**

- [ ] With an injected connection and clock, test the actual adapter's fixed
  method/path pairs, exact tag and digest check, two-message payload, response
  caps, and deadline and failure outcomes for both endpoints. Include a
  response that keeps delivering bytes until the absolute deadline and a
  redirect at each endpoint.
- [ ] Missing operator confirmation makes no request. A malformed, oversized,
  redirected, or timed-out tags reply stops before chat. Both types of stop
  persist and reopen with the appropriate reason.
- [ ] `python -m pytest tests/test_checklist_review_local.py -q` passes without
  a model service.

**Recorded DC-02 inspection and correction (CHE-89 first-delivery checks):**

- [ ] A new test run, labelled origin `recorded R01/DC-02` and linked to the
  historical attempt, is produced through the same runner and store with the
  recorded response injected. Rule, model, and policy all show `insufficient
  evidence`. No human decision exists yet, and review remains available. The
  recorded run makes no network calls and the live runtime confirmation is
  inapplicable.
- [ ] `show --evidence` displays WP.L02, WP.L03, and S1.L01–S1.L05, showing the
  absent EQ-INV-07 entry and the unsupported model reason.
- [ ] The `review` command records `insufficient evidence`,
  `label_assessment=correct`, `evidence_assessment=unsupported`, the three
  register rows, and the rationale *The supplied register contains no
  EQ-INV-07 entry. Its revision-4 row belongs to EQ-INV-12.* in a private note.
  The original model reason and policy finding are unchanged. The human event is
  marked as a revision of the explanation and as a demonstration record, since
  the historical DC-02 had no human disposition.
- [ ] A new process with the model unavailable shows the original results and
  the later review in order, returns to the same item, and opens the store
  read-only with no model call, store initialization, or new event. A removed
  or altered artifact shows a gap while keeping the result IDs and decision.
- [ ] `python -m pytest tests/test_checklist_review_cli.py -q` passes without a
  model service.

**Integration and live check:**

- [ ] `python -m pytest tests/test_checklist_review.py
  tests/test_checklist_review_store.py tests/test_checklist_review_local.py
  tests/test_checklist_review_cli.py -q`, then `python -m pytest -q`, with
  exact counts and any failures reported.
- [ ] The scope diff against the base contains only the paths above.
  `git diff --check` is clean.
- [ ] In an installed `tc` environment without the repo's test directory,
  `save` freezes the packaged template bytes with the fixture digests below.
  Reopen that definition and run it with separately supplied case files.
- [x] Two live runs on synthetic DC-03 and DC-02 use the same saved definition,
  the selected local model, and the explicit private store. Each records the
  operator's cloud-disabled runtime confirmation, observed model identity,
  settings sent, distinct case digest, model outcome, and human decision with
  citations. An unavailable runtime or unverified locality leaves live
  acceptance pending and preserves the stop.
  [Live verification record](#live-verification-record).
- [ ] Two short CLI transcripts are returned: (1) reopening the recorded DC-02
  run and inspecting the unsupported reason before and after the correction;
  (2) two live reviews reusing the saved procedure, with model identity and any
  stops. Unmeasured human time is labelled `unknown`.
  [Live CLI summary](#live-cli-summary).

## Fixture provenance

The R01 v0.2-draft packet manifest identifies the complete source files.
Their SHA-256 digests were checked in design review.

| Complete source | SHA-256 |
| --- | --- |
| `30_run_card.md` (prompt wrapper and parsing rule) | `4acb630d54271dc28f44331d935c9b630764f1986eb0d1af788f479aa88de4a2` |
| `10_candidate_pack.md` (case blocks) | `7a8ce3c3bb9e185a18f743607ae8dddc410d71ff5be5594e045742a96a36cf60` |

For each text excerpt, normalize line endings to LF, encode UTF-8 without
a BOM, and exclude the newline after the last extracted line. Treat those
as the canonical fixture bytes on every platform. Copy the raw DC-02 reply
byte for byte and verify its original seal without newline normalization.

| Fixture under `tests/fixtures/checklist_review/` | Extraction or source | SHA-256 |
| --- | --- | --- |
| `workflow_docrev_v1/system.txt` | Run card's exact system-text fenced block, excluding fences | `69d17c5d1de85bddf0ddd321af7d1471ece6abb9ca60f04dbeb7dd03676df316` |
| `workflow_docrev_v1/user_template.txt` | Run card's exact user-text fenced block with placeholders intact | `4038f3e9de8bb33f58f1da1803951b510176b9f3caa8e3d6dd99f8ee30475176` |
| `cases/DC-02.txt` | Candidate pack from `BEGIN CASE DC-02` through `END CASE DC-02` inclusive | `bd28ba046465e68390a13200de61f3e46168d232ea51834cda0f7f74bb96ed79` |
| `cases/DC-03.txt` | Candidate pack from `BEGIN CASE DC-03` through `END CASE DC-03` inclusive | `ff0d555e3ce5845c20ee746aea44f1922dec4c883375373ad379e7a9772a861f` |
| `recorded/R01_DC-02_slm.txt` | Sealed R01 file `slm_raw_R01_DC-02.txt` | `7fca096c058a6998ae18699a3ae271447a230403721092502141db76db76d6c8` |

Substituting each case and its ID into the template reproduces both messages
in the corresponding sealed R01 request. Verify the installed template and
each fixture against its individual digest in tests. A handoff transcription
can qualify by matching the pinned bytes. Label a divergent copy as
transcribed and leave the exact recorded-fixture check pending.

R01 used `qwen3.5:4b` at digest
`d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04` with
Ollama 0.40.16 and the request settings under the workflow definition. The
installed model supplied `top_k 20` and `presence_penalty 1.5`. Repeat
penalty was unreported. The rule earned evidence credit on 5/6 cases. Qwen
was correct on 4/6 and earned evidence credit on 3/6. The policy was correct
on 6/6. Human review time was unknown. These are development results for six
synthetic cases. This CR has separate recorded and live acceptance checks.

## Control-plane invariants

Per the [control-plane invariant checklist](../../operations/control-plane-invariant-checklist.md):

- Row 2: the standard ledger is untouched. Review-store metadata is screened by
  the persistent privacy invariant. Raw evidence stays in the private artifact
  store by design and is not a ledger record.
- Rows 7 and 9: `show` is read-only. Mutating subcommands need an explicit
  store and fail closed. Failures use closed reason codes, never raw text.
- Row 10: rule, model, and policy outputs are advisory. Only the explicit
  `review` action records a human decision, and it confers no authority outside
  this review store.
- No row is weakened.

## Decisions for design review

These choices are part of the design accepted at `eb431f4`. See the
[design acceptance record](#design-acceptance-record).

- **D1 — transport seam.** Use the self-contained `http.client` adapter with
  the fixed loopback endpoint and two allowed calls. CR-135's
  `GuardedTransport` is deliberately disconnected at the pinned base. Its
  first runtime integration would be a separate scope decision.
- **D2 — standard ledger.** Use the explicit private review store as the sole
  workflow history for this slice. The run, rule, model, policy, and human
  assessment records link within that store. The standard ledger is outside
  the write scope.
- **D3 — identifier.** Keep numeric CR-138, as confirmed in the census recheck.

## Limitations

- The rule handles one controlling register table and the R01 case format
  only. It ignores Remarks.
- `127.0.0.1` covers IPv4 loopback only. An Ollama instance bound only to
  `::1` reports `runtime_unavailable`.
- A tag and digest check confirms which model the runtime reports. It does not
  prove the weights served or the sampling actually applied.
- The store relies on ordinary local file permissions and the operator's
  choice of an unsynced, unshared directory outside the checkout. Record
  that choice in the live handback without including the private path. The
  client records the operator's runtime confirmation. Its HTTP boundary
  covers client requests to loopback.
- The two-case synthetic trial exercised the workflow end to end. Model
  quality and performance on real documents are outside that trial's scope.

## Evidence base

Observed on 2026-11-20 in `<recovered TriageCore checkout>`:
a single worktree on branch `test/field-notebook-provenance-unknown-check` at
`eaa05d949949c1454efcf0a32b8587c39ef17d61` with a clean status and no stash.
Local `main` was `ffb47b1a`, behind `origin/main` (`d634f5a`) by 11 commits. The
first-delivery handoff described a different inspection (local `main` at
`a435b62`, an untracked `.serena/` directory, and a stale CR-DD-019 worktree);
none of those was present in this checkout. The seams cited above were read at
`eaa05d9`, whose `triage_core/` tree matches `origin/main`.

## Proposal acceptance record

On 2026-11-20 (Pacific), Corey Shaffer accepted CR-138's proposal at
[`eb431f4b5a05e2db51104937da4a648d2cf57bf1`](https://github.com/coreytshaffer/TriageCore/blob/eb431f4b5a05e2db51104937da4a648d2cf57bf1/docs/change/requests/CR-138-checklist-review-first-delivery.md).
This accepts the problem, objective, and bounded first delivery for CHE-87,
CHE-88, and the first-delivery checks in CHE-89 as recorded at that revision.

## Design acceptance record

On 2026-11-20 (Pacific), Corey Shaffer separately accepted CR-138's design at
[`eb431f4b5a05e2db51104937da4a648d2cf57bf1`](https://github.com/coreytshaffer/TriageCore/blob/eb431f4b5a05e2db51104937da4a648d2cf57bf1/docs/change/requests/CR-138-checklist-review-first-delivery.md).
This accepts the design, D1–D3, and the planned acceptance checks at that
revision. The trial wording in this record clarifies the timing of the
planned check. Any substantive design change requires its own acceptance.

## Implementation authority record

### Operator approval and sequence

At 22:12 PST on 2026-11-20, Corey Shaffer referenced the named
*CR-138 implementation grant for Claude* draft in the Claude conversation
and wrote “Implementation granted.” The referenced draft has SHA-256
`07da5ab4258aa14fd61fe7180d6c2b3303871d25fe679ab406ee2b4f124dfae3`.
The referenced draft pins design `eb431f4b5a05e2db51104937da4a648d2cf57bf1`
and code base `d634f5aa4923b451ca348e01feca2cfb2b0734fc`.

The draft requires both explicit approval and recording in CR-138 before
the grant takes effect, and limits Claude's scope to one candidate through
handback. Claude created local candidate `efe28d75b8f0a5673636f7a2bc714b165ddfc22f`
at 22:52 PST on 2026-11-20. PR #203 was still at `1e7753b` with authority
pending at handback. This entry records the earlier chat approval after the
fact. It preserves the missing pre-implementation record as a timing
deviation. [Implementation acceptance](#implementation-acceptance-record)
is recorded separately.

### Scope of the approved draft

Claude's bounded scope was one first-delivery candidate for CHE-87, CHE-88,
and basic CHE-89, in an isolated checkout at the pinned base. It covered
local edits and a local candidate commit for the exact files below, plus
offline tests and package verification in disposable directories. Remote
publication and later lifecycle stages require separate decisions.

```text
triage_core/checklist_review.py
triage_core/checklist_review_store.py
triage_core/checklist_review_local.py
triage_core/checklist_review_cli.py
triage_core/tc_cli.py
tests/test_checklist_review.py
tests/test_checklist_review_store.py
tests/test_checklist_review_local.py
tests/test_checklist_review_cli.py
tests/fixtures/checklist_review/workflow_docrev_v1/system.txt
tests/fixtures/checklist_review/workflow_docrev_v1/user_template.txt
tests/fixtures/checklist_review/cases/DC-02.txt
tests/fixtures/checklist_review/cases/DC-03.txt
tests/fixtures/checklist_review/recorded/R01_DC-02_slm.txt
tests/fixtures/checklist_review/PROVENANCE.md
docs/operations/checklist-review-first-delivery.md
```

The `tc_cli.py` edit was limited to parser registration and dispatch for
`checklist-review`. The private review store is the sole workflow history.

The draft reserved the two planned live checks for Corey as operator, one
attempt on DC-03 and one on DC-02 using the same saved definition. The
operator verifies a cloud-disabled local Ollama runtime and an installed
`qwen3.5:4b` matching digest
`d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`, then
records that confirmation on each run. The store is private, local, and
outside synced, shared, and version-controlled folders. Each attempt has
at most one of each of these two requests:

- `GET http://127.0.0.1:11434/api/tags` with a 5-second absolute deadline
  and 256 KiB body cap.
- `POST http://127.0.0.1:11434/api/chat` with a 240-second absolute deadline,
  32 KiB request cap, and 64 KiB body cap. It requires a valid tag and digest
  match and a verified private artifact for the prepared request.

These are the only permitted endpoints. The draft excludes proxies,
redirects, retries, fallback, model pulls, and separate load or unload
requests.

### Handback observations

The candidate's diff and five fixture digests were checked against the
approved scope and accepted design. The handback reports 156 focused tests
passing, two remaining baseline failures in the broader run, and the mobile
test excluded. The two live Ollama checks were pending at handback.

The reported scratch socket test used an injected connection factory. The
adapter requested `127.0.0.1:11434`, but the factory connected to a fake
server on an ephemeral loopback port. This is a separate deviation from the
approved no-network test scope. It did not contact Ollama and counts as
neither operator-run live check. This record documents the deviations for
review and does not ratify them.

## Implementation acceptance record

On 2026-11-20 (Pacific), Corey Shaffer wrote “Implementation acceptance
granted.” in response to the CR-138 handback. This accepts the local candidate
`efe28d75b8f0a5673636f7a2bc714b165ddfc22f` on `claude/cr-138-first-delivery-impl`,
based on `d634f5aa4923b451ca348e01feca2cfb2b0734fc` and the design accepted
at `eb431f4b5a05e2db51104937da4a648d2cf57bf1`. Acceptance is pinned to that
candidate commit.

The two operator-run Ollama checks were pending at implementation acceptance.
The subsequent checks and informed decisions are in the
[live verification record](#live-verification-record).
The test results, limitations, and two deviations remain recorded in
[Handback observations](#handback-observations) and
[Operator approval and sequence](#operator-approval-and-sequence).
Implementation acceptance is a separate decision. Merge authority, release
authority, and closeout remain pending.

## Live verification record

On 2026-11-20 (Pacific), Corey Shaffer ran DC-03 and then DC-02 using the
installed CLI built from the accepted candidate
`efe28d75b8f0a5673636f7a2bc714b165ddfc22f`. Both attempts used the private
local store Corey selected and reused `docrev-v1` at definition digest
`2253ccf998f3325cddf9e6e752a6010d40f5fbb02f3a6b1cb236e3d9e9b92811`.

Each attempt recorded Corey's cloud-disabled runtime confirmation. The
Ollama startup log corroborated that setting. Ollama reported `qwen3.5:4b`
with the pinned digest
`d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`
on both attempts. The server log shows one `GET /api/tags` and one
`POST /api/chat` for each case on `127.0.0.1:11434`.

Each stored request contained the frozen system message and one user message
rendered for that case. Both requests set `num_ctx=4096`, `num_predict=256`,
`seed=7`, `temperature=0`, `top_p=1.0`, `think=false`, and `stream=false`.
The saved case digests matched the pins in [Fixture provenance](#fixture-provenance).
The launcher initially paused on lowercase `run` before issuing a request
or creating a run. The corrected prompt recorded one attempt per case, both
`returned_valid`.

### Live CLI summary

| Case | Run ID | Model result event | Human review event |
| --- | --- | --- | --- |
| DC-03 | `cfd2836c-31e6-4032-9cce-28224c2a8198` | `65ba02dd-ef6a-4057-b1bc-e75bbe314c83` | `f9abb594-a457-46e4-b69d-33fa6a7581ec` |
| DC-02 | `852e8e58-476d-4070-ba8a-53e9c44a550a` | `2749848a-9631-47e8-ac81-cc15885d745d` | `373680fc-76a3-4a3e-82cc-5e92a4dbce12` |

Corey confirmed both informed reviews in Codex by selecting “Record both
reviews.” Each decision was appended to the live run and linked to its
original model result. Both reviews recorded the finding as `correct`.

- **DC-03.** Rule, model, and policy agreed on `match`. Corey accepted the
  finding and marked the explanation `supported`. `WP.L02` and `WP.L03`
  identify FC-233 revision E, and `S1.L04` records approval for that revision.
- **DC-02.** Rule, model, and policy agreed on `insufficient evidence`.
  Corey kept the finding, marked the model's explanation `unsupported`, and
  revised the explanation using `WP.L02`, `WP.L03`, and `S1.L03`–`S1.L05`.
  The register contains no EQ-INV-07 entry. The revision-2 row belongs to
  FC-214, and the revision-4 row belongs to EQ-INV-12. The live response's
  SHA-256 matches the sealed R01 DC-02 response in Fixture provenance.

The CLI reopened both decisions read-only. The original event IDs matched
those recorded before review. The stored cases, requests, model replies, and
review notes passed digest checks.

| Case | Model generation (s) | Elapsed to policy (s) | Elapsed to saved decision (s) | Active operator time |
| --- | ---: | ---: | ---: | --- |
| DC-03 | 0.523802 | 6.343 | 241.808 | `unknown` |
| DC-02 | 0.711365 | 1.234 | 223.453 | `unknown` |

Elapsed times are measured from the start of each attempt.

## Transport correction authority

On 2026-11-21 (Pacific), Corey Shaffer directed “Continue along the landing
path” in response to the CR-138 merge-readiness review. This authorizes the
first step in that review, a local corrective candidate based on
`efe28d75b8f0a5673636f7a2bc714b165ddfc22f`. The scope covers the three
findings on response deadlines, HTTP body completeness, and termination
codes in persisted metadata.

The corrective commit is limited to the following two files.

- `triage_core/checklist_review_local.py`
- `tests/test_checklist_review_local.py`

Verification uses the injected transport, clock, and timer in offline
tests and disposable build and test directories. The scope covers one
local corrective commit and the CR-138 authority and evidence records
through handback. Acceptance of the corrective candidate, publication to
the draft PR, merge, release, and closeout require separate decisions.

## Transport correction handback

The local corrective candidate is `cfdef2c90c31294dcf385845bf990b2cfe9944d4`
on `codex/cr-138-transport-correction`. Its parent is the accepted candidate
`efe28d75b8f0a5673636f7a2bc714b165ddfc22f`. The local authority record
`c9a5a9479a61643ed2d95895d56ddfca9ed5f0ed` preceded the test and code edits.
The two changed paths match the corrective scope.

The watchdog retains the active socket through response-body reads. The
adapter checks a declared body length before accepting JSON and records the
existing endpoint-specific invalid-response status for incomplete bodies.
Termination reasons in metadata use `stop` or `length`. Absent values remain
`unknown`, and unrecognized values become `other`.

Offline verification used Windows, CPython 3.12.16, and pytest 9.2.0.

- Four regression cases failed on the parent and passed after the
  correction. The four checklist-review test files passed **162 tests**.
  Selected Ruff checks and `git diff --check` passed.
- The installed-wheel smoke check matched the corrective adapter to its
  commit and saved both pinned template digests in a disposable store.
- The unfiltered suite stopped during collection because the offline
  environment lacked FastAPI for `tests/test_mobile_web.py`. The initial
  core run with that module excluded reported 2,724 passed, 27 skipped,
  61 failed, and 13 setup errors. The setup errors occurred in
  `tests/test_build_review_cli.py` during editable installation.
- Matched reruns of the seven affected files with shorter temporary paths
  reported **268 passed, 2 skipped, and the same 56 failing test IDs** on
  `efe28d7` and `cfdef2c`. The legacy build-review CLI tests completed
  with the shorter paths. The matched failures were in
  `test_agent_identity.py`, `test_doctor_cli.py`,
  `test_governed_consumption_parity.py`, `test_identity_cli.py`,
  `test_mediated_executor.py`, and `test_tc_run_plan_artifact_cli.py`.

The corrective grant ended at this handback. The prior DC-03 and DC-02 live
checks and informed reviews remain evidence for `efe28d7`. The corrective
candidate has offline verification.
[Subsequent acceptance and draft publication decisions](#corrective-candidate-acceptance-record).

## Corrective candidate acceptance record

On 2026-11-21 (Pacific), Corey Shaffer selected “Accept and authorize draft
update” in Codex after reviewing the offline results for the corrective
candidate. This records implementation acceptance for
`cfdef2c90c31294dcf385845bf990b2cfe9944d4`.

The same decision separately authorizes publishing the accepted implementation
and this CR record to the existing branch of [draft PR #203](https://github.com/coreytshaffer/TriageCore/pull/203)
for hosted CI. The publication preserves `efe28d7` and `cfdef2c` in the
branch history. Merge authority, release authority, and closeout remain pending.

## Corrected build live-check authority

On 2026-11-21 (Pacific), Corey Shaffer wrote “I authorize one fresh live
check each for DC-03 and DC-02 on `b1c4596`.” This authorizes Corey as
operator to run synthetic DC-03 and then DC-02 once each on
`b1c4596c3dec363f201b5f60477988a382b9be6b`, which contains the accepted
transport correction `cfdef2c`.

Reuse the existing operator-selected private store and its saved `docrev-v1`
definition at digest
`2253ccf998f3325cddf9e6e752a6010d40f5fbb02f3a6b1cb236e3d9e9b92811`.
Both attempts use the pinned local `qwen3.5:4b` model at digest
`d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`,
with the [saved workflow settings](#workflow-definition-frozen) and a fresh
two-message context for each case.

Before each attempt, Corey confirms that the installed model is local and
that cloud features are disabled in the running Ollama instance. The
attempt may make one `GET /api/tags` and, after the pinned identity
matches, one `POST /api/chat` on `127.0.0.1:11434`. A saved stop consumes
the attempt for that case and leaves the live review pending.

Record the fresh run IDs and later informed reviews against `b1c4596`.
The original live runs and reviews remain evidence for `efe28d7`.
Merge authority, release authority, and closeout remain pending.

## Corrected build DC-03 stop

On 2026-11-21 at 01:00:29 PST, Corey Shaffer ran DC-03 on `b1c4596`.
Run `a64e0a30-08ba-43e6-acc1-658575f309c9` saved the verified case,
the local-runtime confirmation, and rule result `match` citing `WP.L02`,
`WP.L03`, and `S1.L04`. Saved preflight event
`fb285f67-2399-496c-8784-351a742292e5` stopped with
`tags_invalid_response`. The Ollama log shows HTTP 200 for `GET /api/tags`
at that time. The run ended at preflight, with chat, policy, and human
review stages unreached.

DC-03 consumed its authorized attempt. DC-02 is unused under the
`b1c4596` authorization. Live verification of that build is incomplete.
The earlier two completed live runs remain evidence for `efe28d7`.

An offline comparison passed an identical, complete fixed-length reply
through the Python HTTP response path on each build. `efe28d7` accepted
the model pin. `b1c4596` returned `tags_invalid_response` after trying to
set a timeout on the socket after the response stream had closed. This
confirmed a response-completion defect. The saved live evidence records
the HTTP status and stop reason. Exact live response framing is unknown.

## Response-completion correction authority

On 2026-11-21 (Pacific), Corey Shaffer selected “Record the stop and fix
locally” in Codex. This authorizes one local corrective commit on
`b1c4596c3dec363f201b5f60477988a382b9be6b` to finish reading a complete
response before reapplying its socket timeout. The correction is limited
to `triage_core/checklist_review_local.py` and
`tests/test_checklist_review_local.py`, with offline verification.

The scope ends with the local candidate and verification record.
Implementation acceptance and draft publication for the new candidate
are separate decisions. Merge authority, release authority, and closeout
remain pending.

## Response-completion correction handback

The local corrective candidate is `64bb94c34450643c6d7b4e93e55519fa342ffaed`
on `codex/cr-138-response-completion`, based on
`b1c4596c3dec363f201b5f60477988a382b9be6b`. The local authority record
`87301efd09eb38c66c22788a0034545568581c36` preceded the test and code edits.
The commit contains the two authorized paths.

The adapter checks whether Python's HTTP response stream has closed before
setting another socket timeout. The time and response-size limits and the
declared-length check continue to apply to body reads.

Offline verification on Windows with CPython 3.12.16:

- Two regression cases for a response that releases its socket after its
  final bytes failed on `b1c4596`. The corrected checkout passed all
  **164 checklist-review tests**, including both regression cases.
- The same complete fixed-length reply that stopped preflight on `b1c4596`
  passed the model digest check on the corrective candidate using Python's
  HTTP client with an in-memory socket.
- Selected Ruff checks and `git diff --check` passed. The unfiltered suite
  stopped at collection because the offline environment lacked FastAPI
  for `tests/test_mobile_web.py`.

The correction grant ended at this local handback. At handback,
implementation acceptance, publication to draft PR #203, hosted CI, and
live checks on `64bb94c` were pending. The unused DC-02 attempt on
`b1c4596` was held. Fresh operator authorization tied to the new candidate
is required for DC-03 and DC-02.
[Subsequent acceptance and draft publication decision](#response-completion-correction-acceptance-record).

## Response-completion correction acceptance record

On 2026-11-21 (Pacific), Corey Shaffer wrote “I accept `64bb94c`.”
This records implementation acceptance for
`64bb94c34450643c6d7b4e93e55519fa342ffaed`.

Corey separately authorized publishing the accepted fix and this CR record
to the existing draft branch for hosted CI.
[Draft PR #203](https://github.com/coreytshaffer/TriageCore/pull/203).

At acceptance, fresh live checks were on hold. The unused DC-02 attempt on
`b1c4596` remains on hold.
[Subsequent live-check authorization](#fresh-live-check-authority-for-697f8e1).

## Fresh live-check authority for 697f8e1

On 2026-11-21 (Pacific), Corey Shaffer wrote “I authorize one fresh live
check each for DC-03 and DC-02 on `697f8e1`.” This authorizes Corey as
operator to start synthetic DC-03 and DC-02 separately on
`697f8e14892ee3061f632b4984fdd11d4816a2ad`, the draft PR #203 head
that contains the accepted response-completion fix `64bb94c`.

Each case has one attempt, including any saved stop. Start with DC-03.
The recorded DC-03 stop and unused DC-02 attempt on `b1c4596` remain
scoped to that build. Retain the earlier runs and informed reviews in
the existing private store.

Use the saved `docrev-v1` definition at digest
`2253ccf998f3325cddf9e6e752a6010d40f5fbb02f3a6b1cb236e3d9e9b92811`
and the pinned local `qwen3.5:4b` digest
`d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`.
Use the sealed DC-03 and DC-02 inputs and a fresh two-message context
for each case.

Before each attempt, Corey confirms the current Ollama instance is
cloud-disabled and listening on `127.0.0.1:11434`. Each attempt may
make one `GET /api/tags` and, after the exact model identity matches,
one `POST /api/chat` to that loopback instance.

Record the run ID, outcome, and later informed review for each attempt
against `697f8e1`. Merge authority, release authority, and closeout
remain pending.

## Fresh live verification record for 697f8e1

On 2026-11-21 (Pacific), Corey Shaffer ran DC-03 and then DC-02 on
`697f8e14892ee3061f632b4984fdd11d4816a2ad`. Each case used its one authorized
attempt. The launcher verified the staged build, both case seals, and
the saved `docrev-v1` definition before starting the checks.
[Fresh live-check authority](#fresh-live-check-authority-for-697f8e1).

Corey confirmed cloud-disabled Ollama on `127.0.0.1:11434` for each
attempt. The launcher checked the startup log for the running instance.
Both `GET /api/tags` preflights returned the authorized `qwen3.5:4b`
digest. Each `POST /api/chat` used a fresh two-message context built
from the frozen workflow and that case's sealed input. Both attempts
reached policy with status `returned_valid`.

| Case | Run ID | Model result event | Human review event |
| --- | --- | --- | --- |
| DC-03 | `4d16a147-b49b-4ce4-b3ff-fd2f620f8618` | `23300b38-e6ff-4a65-8cc7-27f0108dbdff` | `b2df3a92-32f6-4f77-afdd-871aaa9f16b8` |
| DC-02 | `62866263-2842-4e85-acd2-2e681fadb0fa` | `9f6d72ff-c281-40ee-9e33-2e5e4dcf3a79` | `59430e1f-50e2-4c8f-8d5f-54c9088d73ff` |

Corey selected “Record both reviews” in Codex. Each informed review
was appended as an operational assessment linked to its original
model result. Both findings were assessed as `correct`.

- **DC-03.** Rule, model, and policy agreed on `match`. Corey accepted
  the finding and marked the explanation `supported`. `WP.L02` and
  `WP.L03` identify FC-233 revision E. `S1.L04` approves that revision
  and supersedes the prior approval.
- **DC-02.** Rule, model, and policy agreed on `insufficient evidence`.
  Corey kept the finding, marked the model explanation `unsupported`,
  and revised the explanation using `WP.L02`, `WP.L03`, and
  `S1.L03`–`S1.L05`. The register contains no EQ-INV-07 entry. Its
  revision-2 row belongs to FC-214 and its revision-4 row belongs to
  EQ-INV-12.

Read-only verification reopened the reviews and verified the sealed
case inputs, two-message requests, model replies, and private rationale
notes. The prior events matched their pre-review fingerprints.

| Case | Model generation (s) | Model load (s) | Elapsed to policy (s) | Elapsed to saved decision (s) | Active operator time |
| --- | ---: | ---: | ---: | ---: | --- |
| DC-03 | 0.513357 | 10.158423 | 11.141 | 343.524738 | `unknown` |
| DC-02 | 0.671519 | 0.005807 | 1.219 | 296.606439 | `unknown` |

Elapsed times are measured from the start of each attempt.

At live handback, merge authority, release authority, and closeout were pending.
[Subsequent merge authorization](#merge-authority-record).

## Merge authority record

On 2026-11-21 (Pacific), Corey Shaffer wrote “I acknowledge both
documented deviations and authorize merging PR #203 at `e860cf8` into
`main`.” Corey acknowledged the late recording of the original
implementation authority and the scratch fake-loopback test outside the
original offline verification scope.
[Operator approval and sequence](#operator-approval-and-sequence) ·
[Handback observations](#handback-observations).

The merge is authorized for the reviewed PR head
`e860cf8b39e70da0841b694ff4e75a8dc10dca2d` and this CR-only decision record,
targeting `main`. The merge will preserve the accepted implementation
commits and the live evidence bound to `697f8e1`.
[Reviewed draft PR #203](https://github.com/coreytshaffer/TriageCore/pull/203) ·
[CI on e860cf8](https://github.com/coreytshaffer/TriageCore/actions/runs/44954440054).

At merge, release authority and closeout were pending.
[Subsequent release authority](#release-authority-record).

## Merge verification

On 2026-11-21 at 14:24:04 PST, GitHub merged PR #203 into `main`
as `022b4a1227b68b899bf1df2aa83d154e9f4855f4`. The merge preserved the
accepted implementation commits and included `ba19739`, the CR-138
merge authorization recorded on top of the reviewed `e860cf8`.
[Merged PR #203](https://github.com/coreytshaffer/TriageCore/pull/203) ·
[Merge commit](https://github.com/coreytshaffer/TriageCore/commit/022b4a1227b68b899bf1df2aa83d154e9f4855f4).

All four jobs passed in post-merge CI run `44956558375` on `main`
at that commit. The implementation matches the build used for both
fresh live checks and informed reviews.
[Post-merge CI](https://github.com/coreytshaffer/TriageCore/actions/runs/44956558375) ·
[Fresh live verification](#fresh-live-verification-record-for-697f8e1).

## Release authority record

On 2026-11-21 (Pacific), Corey Shaffer authorized the CR-138 GitHub
source release from `022b4a1227b68b899bf1df2aa83d154e9f4855f4`
under `cr-138-checklist-review-first-delivery-2026-11-21`. The
authorized source is the `main` merge commit for PR #203.
[Merged PR #203](https://github.com/coreytshaffer/TriageCore/pull/203) ·
[Post-merge CI](https://github.com/coreytshaffer/TriageCore/actions/runs/44956558375).

The authorization covers publishing the named GitHub source release
and verifying its tag and GitHub-generated ZIP and tar.gz archives
against the pinned source. At release authorization, closeout authority
was pending.

## Source release verification

GitHub published the CR-138 source release on 2026-11-21 at 15:32:09 PST.
The tag `cr-138-checklist-review-first-delivery-2026-11-21` resolves to
`022b4a1227b68b899bf1df2aa83d154e9f4855f4`.
[Published release](https://github.com/coreytshaffer/TriageCore/releases/tag/cr-138-checklist-review-first-delivery-2026-11-21).

Both GitHub-generated downloads declared the pinned commit. The file paths
and contents in each matched the exported Git tree for all 800 files,
including the 17 CR-138 changed paths. The closeout review downloaded
both archives again and matched their recorded SHA-256 checksums.

| Archive | Files verified | SHA-256 of download |
| --- | ---: | --- |
| ZIP | 800 | `2cdccafb73a3a0feed56b61d3033696995a19b0c68f4ee3bf6c8a471238e51a7` |
| tar.gz | 800 | `f7b2cae2dcab7759ae596f130a924cc0054d722e1719788f5ca24b306f01d00e` |

[Verified ZIP download](https://api.github.com/repos/coreytshaffer/TriageCore/zipball/cr-138-checklist-review-first-delivery-2026-11-21) ·
[Verified tar.gz download](https://api.github.com/repos/coreytshaffer/TriageCore/tarball/cr-138-checklist-review-first-delivery-2026-11-21).

[Subsequent closeout decision](#closeout).

## Closeout

On 2026-11-21 (Pacific), Corey Shaffer authorized CR-138 closeout.
The grant covers recording the merge, source release verification, and
closeout decision in this CR, updating the change log, and landing
the two documentation changes on `main`.
[Change log](../change_log.md#cr-138-checklist-review-first-delivery---2026-11-21).

The release tag `cr-138-checklist-review-first-delivery-2026-11-21` is pinned to
`022b4a1227b68b899bf1df2aa83d154e9f4855f4`.
[Merge verification](#merge-verification) ·
[Source release verification](#source-release-verification).
