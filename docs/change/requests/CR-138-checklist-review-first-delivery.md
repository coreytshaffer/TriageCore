# CR-138 — Saved document-revision review with a recorded human assessment

## Status

**Proposed. Ready for proposal and design review.** Nothing in this document is
accepted or authorized.

| Decision | State |
| --- | --- |
| Proposal acceptance | Pending |
| Design acceptance | Pending |
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

CR-138 is the next numeric identifier in the observed namespace. Observed on
2026-11-20:

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

Recheck the census before recording proposal acceptance.

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
- **Writes:** only inside the operator-named `--store` directory. There is no
  default store location. Tests use temporary directories only.
- **Standard ledger:** not written by this slice (see Decision D2).
- **Live verification:** two operator-run `run` commands against the local
  Ollama runtime, after implementation authority is granted, as part of the
  implementation evidence.

### Out of scope

Hover or focus timeline UI (milestone 2), offline checkpoint replay, rollback
of managed files, and the solo acceptance trial (CHE-90 to CHE-92); external or
cloud providers; integration with `tc run`, routing, TriageDesk, or the
destination-policy slice 2; signing; scoring or ranking models; any claim
about real documents.

## Design

### Workflow definition (frozen)

A definition is saved once under an opaque workflow reference, such as
`docrev-v1`. It contains:

- the system text and user template from the R01 candidate pack, byte for
  byte;
- rule `R-DOCREV v0.1` and policy `C-AGREE v0.1` identifiers;
- the model profile: Ollama tag, expected digest, and request settings. The
  default settings are R01's explicit options: `temperature 0`, `top_p 1`,
  `seed 7`, `num_predict 256`, `num_ctx 4096`, `think false`, `stream false`;
- bounds: maximum case bytes, maximum response bytes, connect and read
  timeouts.

The definition digest is the SHA-256 of its canonical JSON form. Saving a
reference that already exists with different content fails with
`definition_conflict`. A changed definition gets a new reference. Saved rows
are never updated.

### Case parsing

`parse_case(raw: bytes) -> ReviewCase` accepts UTF-8 bytes up to the definition
bound, the `BEGIN CASE` / `END CASE` envelope, `FILE:` sections, and lines of the
form `<LABEL>  <text>`. It rejects duplicate labels, a missing or unnamed
controlling source, unknown files, and oversize input with closed reason codes.
The case object maps each unique visible label to its exact line and records
the case digest. Each run binds the exact case bytes.

### Rule R-DOCREV v0.1

`apply_rule(case) -> ComponentResult` reads the Document ID and Revision only
from the work-product header lines, and the controlling source only from the
request. It keeps register rows whose Document ID cell matches exactly,
character for character, then tests in order:

1. a required header field or the controlling source is missing →
   `insufficient evidence`;
2. no row counts → `insufficient evidence`, citing every entry row;
3. an exact revision with Decision `Approved` → `match`;
4. any counting row with an empty Revision or Decision → `insufficient
   evidence`;
5. an exact revision with any other Decision → `insufficient evidence`;
6. otherwise → `mismatch`.

Blank cells and a lone em dash are empty. The rule cites the two header lines
it read and the relevant register rows. The rule ignores Remarks by design, so
an automatic result is always provisional and review stays available.

Expected results: DC-03 → `match` citing S1.L04. DC-02 → `insufficient
evidence` citing S1.L03, S1.L04, and S1.L05. A row with the same revision and
date but a different Document ID never counts.

### Model output and policy C-AGREE v0.1

`parse_model_result(case, raw) -> ComponentResult` accepts exactly one JSON
object with `case_id`, `finding`, `cited_lines`, and `reason`. It rejects extra
text, a wrong `case_id`, a finding outside the three values, and a cited label
that is absent from the case. Rejection yields a `returned_invalid` component
with a closed reason code. The raw text is kept either way.

`combine(rule, model) -> PolicyResult`: if both components are valid and their
findings agree, the policy finding is that finding. A disagreement or an
invalid model result yields `insufficient evidence` with `review_needed`. Both
components and their reasons are retained. Agreement does not mark the
evidence as assessed. The projection shows `agreed`, `evidence unassessed`
until a human assessment exists.

### Store

`ReviewStore(root)` owns a SQLite database and an `artifacts/` directory under
the explicit root.

- **Artifacts:** case bytes, raw model output, request bodies sent, and any
  free-text note. Each is written once with exclusive creation, named by its
  SHA-256, and referenced by an opaque artifact ID. A model-supplied citation
  can select only a label in the recorded case, never a path.
- **Events:** append-only rows keyed by run ID and a per-run increasing
  sequence, with item ID (initially `revision-approval`), step (`attempt`,
  `rule`, `model`, `policy`, `human`), and an event ID. A human event also
  references the target result event and any earlier human event it revises.
  The artifact is written before its event row. The event row and its artifact
  references commit in one transaction. The command acknowledges a write only
  after reading the complete record back. An unreferenced artifact left by a
  failed transaction is inert.
- **Immutability:** schema triggers reject `UPDATE` and `DELETE` on
  definitions and events. The current result is a projection over ordered
  events.
- **Metadata privacy:** every metadata row and summary passes
  `privacy_invariants.assert_persistent_privacy_safe` before insertion. Summaries
  carry identifiers, digests, closed codes, statuses, and measurements only.
  Free text lives only in private artifacts.

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

`ReviewModel` resolves the configured tag and expected digest through `GET
/api/tags` before it accepts candidate messages. Outcomes:

| Condition | Attempt status | Reason code |
| --- | --- | --- |
| Connection refused or tags timeout | `stopped` | `runtime_unavailable` |
| Tag absent | `stopped` | `model_not_installed` |
| Tag present with a different digest | `stopped` | `model_digest_mismatch` |
| Redirect, lost connection, non-200 status, or oversize response on chat | `failed` | `transport_refused`, `completion_failed`, or `response_too_large` |
| Chat timeout | `failed` | `timeout` |
| Completed, output rejected by the parser | `returned_invalid` | parser reason code |
| Completed, output accepted | `returned_valid` | none |

A stop skips generation and is persisted as a durable record. The attempt
start is persisted before any model call. Each request is a fresh two-message
exchange: the definition's system text and the user template with one case.
The evaluator key, the R01 recorded answer, and any correction never enter
model input. Runtime metadata and the exact settings sent are recorded. A
repeat run gets a new run ID and may reference the earlier run.

**Transport (Decision D1):** use standard-library `http.client` with the host
`127.0.0.1` and port `11434` as module constants. `http.client` consults no
proxy environment variables and never follows redirects. Any 3xx response is a
refusal. Responses are read up to the configured byte bound and the time
bound. The transport is injectable so tests use no network.

### Command group

```text
tc checklist-review --store <dir> save --workflow docrev-v1 --model qwen3.5:4b --model-digest <sha256>
tc checklist-review --store <dir> run  --workflow docrev-v1 --case <DC-03.txt>
tc checklist-review --store <dir> run  --workflow docrev-v1 --case <DC-02.txt>
tc checklist-review --store <dir> show --run <run-id>
tc checklist-review --store <dir> show --run <run-id> --item revision-approval --evidence
tc checklist-review --store <dir> review --run <run-id> --item revision-approval \
    --target <model-event-id> --finding "insufficient evidence" --disposition revised \
    --label-assessment correct --evidence-assessment unsupported \
    --cite S1.L03 --cite S1.L04 --cite S1.L05 --reason-code no_matching_document \
    [--supersedes <human-event-id>] [--note-file <path>] [--active-seconds <n>]
```

- `show` is read-only. It makes no model call, writes no event, and fails
  closed on a missing store or unknown run. It walks from the overall decision
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
- [ ] Duplicate labels, a missing controlling source, and malformed model JSON
  each give a distinct closed reason code.
- [ ] Agreement, disagreement, and an invalid model result give the C-AGREE
  results above, with both components retained.
- [ ] `python -m pytest tests/test_checklist_review.py -q` passes without a
  runtime.

**Store and feedback (CHE-88):**

- [ ] A new store instance reopens the same run with strict chronology,
  byte-identical original model output, an unchanged original definition, and
  a later linked human event.
- [ ] A simulated failed event write reports failure to the operator and leaves
  the earlier state readable.
- [ ] Sentinel source and model text never appear in summaries, error messages,
  or SQLite metadata columns, and the standard ledger is not created or
  modified.
- [ ] Mixed measured and unknown values give correct known counts, coverage,
  and missing counts.
- [ ] `python -m pytest tests/test_checklist_review_store.py -q` passes.

**Local attempt (CHE-87 with CHE-88 records):**

- [ ] With an injected transport, the tests verify the exact tag and digest
  check, the fixed loopback host and paths, bounded time and size, two-message
  isolation, and the seven outcomes in the boundary table.
- [ ] A selected-model stop skips generation, persists, and reopens.
- [ ] `python -m pytest tests/test_checklist_review_local.py -q` passes without
  a model service.

**Recorded DC-02 inspection and correction (CHE-89 first-delivery checks):**

- [ ] A new test run, labelled origin `recorded R01/DC-02` and linked to the
  historical attempt, is produced through the same runner and store with the
  recorded response injected. Rule, model, and policy all show `insufficient
  evidence`. No human decision exists yet, and review remains available.
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
  the later review in order, returns to the same item, makes no model call, and
  writes no event. A removed or altered artifact shows a gap while keeping the
  result IDs and decision.
- [ ] `python -m pytest tests/test_checklist_review_cli.py -q` passes without a
  model service.

**Integration and live check:**

- [ ] `python -m pytest tests/test_checklist_review.py
  tests/test_checklist_review_store.py tests/test_checklist_review_local.py
  tests/test_checklist_review_cli.py -q`, then `python -m pytest -q`, with
  exact counts and any failures reported.
- [ ] The scope diff against the base contains only the paths above.
  `git diff --check` is clean.
- [ ] In the real CLI, two new runs of the same saved definition on DC-03 and
  DC-02 have distinct case digests and explicit human decisions with
  citations. The actual model output is recorded as observed, with its status,
  and the runtime's observed model identity and settings are reported. If
  Ollama is unavailable, the observed stop is reported and the live check stays
  pending.
- [ ] Two short CLI transcripts are returned: (1) reopening the recorded DC-02
  run and inspecting the unsupported reason before and after the correction;
  (2) two live reviews reusing the saved procedure, with model identity and any
  stops. Unmeasured human time is labelled `unknown`.

## Fixture provenance

The candidate-visible text (system text, user template, DC-02 and DC-03) and
the recorded DC-02 response come from the R01 development run:

- source packet `10_candidate_pack.md`, SHA-256
  `7a8ce3c3bb9e185a18f743607ae8dddc410d71ff5be5594e045742a96a36cf60`;
- sealed model text `slm_raw_R01_DC-02.txt`, SHA-256
  `7fca096c058a6998ae18699a3ae271447a230403721092502141db76db76d6c8`;
- R01 settings: `qwen3.5:4b`, digest
  `d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04`, Ollama
  0.40.16, with the options listed under the workflow definition. The installed
  model also supplied `top_k 20` and `presence_penalty 1.5`. Repeat penalty was
  unreported.

If the sealed originals are available to the implementer, copy their exact
bytes and verify these digests in a test. Otherwise, label each fixture
*transcribed from the first-delivery handoff, not seal-verified* and make no
seal claim. R01's aggregate scores (rule 5/6 evidence-credited, model 4/6
correct and 3/6 evidence-credited, policy 6/6 correct, human review time
unknown) are development evidence over six synthetic cases. They are not
acceptance evidence for this CR.

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

- **D1 — transport seam.** Recommended: a self-contained `http.client`
  transport with constant loopback host and port, as described above.
  Alternative: reuse `destination_policy.GuardedTransport` and its
  `device_local_loopback.v1` profile. That transport already enforces
  `trust_env=False`, zero redirects, and an exact Ollama call allowlist, but
  its module docstring and the architecture page state that nothing imports
  it. Using it would make this the first consumer of CR-135's slice-1 module
  and would need those records updated, which is outside this file scope.
- **D2 — standard ledger.** Recommended: no standard-ledger writes in this
  slice. The tests check that it is untouched. Alternative: append one
  screened metadata event per run through `TaskLedger.append_event`, adding a
  new event kind to the ledger's consumers.
- **D3 — identifier.** CR-138 in the numeric series, as censused above. A
  separate lane prefix, as used for CR-DD and CR-BW, is the operator's choice.

## Limitations

- The rule handles one controlling register table and the R01 case format
  only. It ignores Remarks.
- `127.0.0.1` covers IPv4 loopback only. An Ollama instance bound only to
  `::1` reports `runtime_unavailable`.
- A tag and digest check confirms which model the runtime reports. It does not
  prove the weights served or the sampling actually applied.
- The private store has ordinary file permissions. It is not encrypted, and
  this CR does not stop an operator from choosing a store inside a synced or
  shared folder. The operator guide recommends a path outside version
  control, such as the ignored `.triagecore/` directory.
- Two synthetic cases show the workflow runs. They say nothing about model
  quality or real documents.

## Evidence base

Observed on 2026-11-20 in `<recovered TriageCore checkout>`:
a single worktree on branch `test/field-notebook-provenance-unknown-check` at
`eaa05d949949c1454efcf0a32b8587c39ef17d61` with a clean status and no stash.
Local `main` was `ffb47b1a`, behind `origin/main` (`d634f5a`) by 11 commits. The
first-delivery handoff described a different inspection (local `main` at
`a435b62`, an untracked `.serena/` directory, and a stale CR-DD-019 worktree);
none of those was present in this checkout. The seams cited above were read at
`eaa05d9`, whose `triage_core/` tree matches `origin/main`.

## Implementation authority record

*Pending. To be completed only by an explicit operator grant naming this CR,
its file scope, its network scope, and the live verification action.*
