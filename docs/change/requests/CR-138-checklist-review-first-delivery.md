# CR-138 — Saved document-revision review with a recorded human assessment

## Status

**Proposal and design accepted at `eb431f4`. Implementation authority pending.**

| Decision | State |
| --- | --- |
| Proposal acceptance | Accepted at `eb431f4`. [Decision record](#proposal-acceptance-record) |
| Design acceptance | Accepted at `eb431f4`. [Decision record](#design-acceptance-record) |
| Implementation authority | **Pending.** No grant is recorded for this CR. No code, test, fixture, or operator-documentation change may be made under it. |
| Implementation acceptance | Pending |
| Merge authority | Pending |
| Release authority | Pending |
| Closeout | Pending |

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
- [ ] Two live runs on synthetic DC-03 and DC-02 use the same saved definition,
  the selected local model, and the explicit private store. Each records the
  operator's cloud-disabled runtime confirmation, observed model identity,
  settings sent, distinct case digest, model outcome, and human decision with
  citations. An unavailable runtime or unverified locality leaves live
  acceptance pending and preserves the stop.
- [ ] Two short CLI transcripts are returned: (1) reopening the recorded DC-02
  run and inspecting the unsupported reason before and after the correction;
  (2) two live reviews reusing the saved procedure, with model identity and any
  stops. Unmeasured human time is labelled `unknown`.

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
- The planned two-case synthetic trial will check whether the workflow runs
  end to end. Model quality and performance on real documents are outside
  that trial's scope.

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

*Pending. To be completed only by an explicit operator grant naming this CR,
its file scope, its network scope, and the live verification action.*
