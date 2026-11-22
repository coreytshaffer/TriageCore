# CR-139 — Action timeline for saved checklist-review runs

## Status

**Proposed.** Proposal and design acceptance are recorded separately below.

| Decision | State |
| --- | --- |
| Proposal acceptance | Accepted at `62e328d`. [Decision record](#proposal-acceptance-record) |
| Design acceptance | Accepted at `62e328d`. [Decision record](#design-acceptance-record) |
| Operator guide and timeline design amendment | Accepted on 2026-11-22. [Design amendment](#design-amendment-for-the-operator-guide-and-timeline) |
| Implementation authority | **Approved for Claude.** One local candidate on `49e3ad4` and two local launcher files. [Current grant](#implementation-grant-for-the-operator-guide-and-timeline) · [Preceding corrective grant](#corrective-grant-for-malformed-and-interrupted-runs) · [First corrective grant](#local-corrective-implementation-grant) · [Original grant](#implementation-authority-record) |
| Implementation acceptance | Pending |
| Merge authority | Pending |
| Release authority | Pending |
| Closeout | Pending |

Human approval requirement: each stage above needs its own explicit operator
decision, recorded in this document and scoped to the named change and the
exact file, system, and action bounds below. A grant for one stage does not
imply the next unless the operator deliberately names and bundles stages.

Type, per the
[backlog scope taxonomy](https://github.com/coreytshaffer/TriageCore/blob/10af245c18095346d7d60b55b2e105bb819f4828/docs/current_backlog.md#backlog-scope-taxonomy):
**adjacent application**. It extends the CR-138 document-revision review
workflow with read-only inspection. It must preserve the kernel properties
that CR-138 named: review and human control, evidence and reconstruction, and
privacy and provenance.

Tracking: milestone 2 of
[CHE-89](https://linear.app/cherryvox/issue/CHE-89/navigate-from-the-review-decision-to-a-saved-action-and-its-evidence).
CHE-89 stays open. CR-138 delivered the first-delivery checks, including the
CLI evidence drill-down.
[CR-138 closeout](https://github.com/coreytshaffer/TriageCore/blob/10af245c18095346d7d60b55b2e105bb819f4828/docs/change/requests/CR-138-checklist-review-first-delivery.md#closeout).
Replay and linked resume (CHE-90) and rollback and file restoration (CHE-91)
are out of scope. So is the solo acceptance trial (CHE-92), which CR-138
also excluded.

### Identifier census

CR-139 is the next numeric identifier in the observed namespace. On
2026-11-21 (Pacific):

- `git fetch origin` placed `origin/main` at
  `10af245c18095346d7d60b55b2e105bb819f4828` (`docs: close out CR-138
  (#204)`). Its `docs/change/requests/` ends the numeric series at CR-138.
- `git grep CR-139` over `docs/` in all 173 local branches, remote-tracking
  branches, and tags found nothing. `git log --all --grep=CR-139` returned
  nothing. No branch name contained `139`, `che-89`, or `timeline` before
  the draft branch named under [Evidence base](#evidence-base) was created.
- The highest pull request ref on `origin` is `refs/pull/204/head`, the
  CR-138 closeout.
- A search of all refs for `CHE-89`, `action timeline`, and
  `checklist_review_timeline` matched only the CR-138 record and the change
  log. No existing milestone-2 proposal exists under another identifier.
- During proposal review, GitHub issue and pull request title searches in
  `coreytshaffer/TriageCore` for `CR-139`, `CHE-89`, and "action timeline"
  returned no matches. The searches found no identifier conflict.

## Proposal acceptance record

On 2026-11-21 (Pacific), Corey Shaffer accepted the CR-139 proposal at
`62e328d` in draft PR #205. The decision covers the problem and the bounded
read-only timeline delivery for CHE-89 milestone 2, with the DC-02
correction and DC-03 preflight stop as acceptance cases.
[Reviewed proposal](https://github.com/coreytshaffer/TriageCore/blob/62e328d1f0f9546c409643f9df203efd86b91166/docs/change/requests/CR-139-checklist-review-action-timeline.md)

## Problem

Corey cannot start at a saved review decision, step through the actions
behind it in order, open one action's evidence, and return to the same place.

CR-138's `show` and `show --evidence` print a whole run at once from a
read-only store. They are the right evidence base but the wrong navigation
surface:

- `render_run` lists only events whose item ID is `revision-approval`
  ([checklist_review_cli.py:305–307](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/checklist_review_cli.py#L305-L307)).
  The attempt start, model preflight, model request, and attempt end events
  carry no item ID
  ([checklist_review_local.py:468–524](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/checklist_review_local.py#L468-L524)).
  For the saved DC-03 stop, `show` reports the preflight outcome in the run
  header, but neither view prints the preflight event ID `fb285f67-…`.
- The policy result records `rule_event_id` and `model_event_id`
  ([checklist_review_local.py:593–598](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/checklist_review_local.py#L593-L598)),
  but neither view shows them. Human `target` and `supersedes` IDs are
  printed as text, and no view lets you follow them.
- Terminal output has no hover, focus, or click, so it cannot preview an
  action, keep details open, or restore a position.

TriageDesk's existing review surface does not read this store. See the
[surface evaluation](#surface-evaluation).

## Proposed scope

Add one read-only window that opens a CR-138 review store. From a saved
review or stopped run, Corey can open the checklist item and inspect all
saved events of that run in order. Run-level actions such as model preflight
have their own selectable rows and details with stable event IDs. Corey
opens the window with a new `timeline` subcommand of the existing
`tc checklist-review` group. A Tk-free view model handles store reading and
labelling. A thin `tkinter.ttk` shell handles pointer, touch, and keyboard input.

### Surface evaluation

| Option | Pointer, touch, and keyboard checks | Local and read-only | Size | Verdict |
| --- | --- | --- | --- | --- |
| **A.** New tab in TriageDesk (`triage_core/ui/app.py`, 4,362 lines) | Possible, but not with existing patterns. Ledger cards bind only `<Button-1>`, with no keyboard activation ([app.py:2012–2068](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/ui/app.py#L2012-L2068)). The inspector destroys and rebuilds its widgets on every render, which drops focus and scroll position ([app.py:1850–1868](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/ui/app.py#L1850-L1868), [1993–2073](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/ui/app.py#L1993-L2073)). | **No.** Start-up probes Ollama and LM Studio in a thread ([app.py:1091](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/ui/app.py#L1091), [3490–3491](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/ui/app.py#L3490-L3491)). The Ollama probe uses `requests` against `TRIAGE_OLLAMA_BASE_URL` ([app.py:3421–3452](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/ui/app.py#L3421-L3452)). Start-up also writes `triagecore.log`, opens the standard `TaskLedger`, and polls an IPC inbox that deletes its file and can auto-dispatch a model task ([app.py:4254–4292](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/ui/app.py#L4254-L4292)). | Large edit to `app.py`. Requires the `[ui]` extra (`customtkinter`). | Not recommended for this milestone |
| **B.** Standalone `ttk` window opened by `tc checklist-review timeline` | **Yes.** `ttk.Treeview` provides native keyboard focus and selection, `focus()`, `see()`, and `yview_moveto()` for restoration. | **Yes.** It opens only `ReviewStore.open_readonly()`, starts no model, and writes nothing. | Two new modules, one additive CLI edit, and tests | **Recommended** |
| **C.** Text-only `show --timeline` | No hover, focus, click, or scroll restoration | Yes | Small | Insufficient alone. A metadata-only `--list` mode is included in B for restart checks and handbacks. |
| **D.** Local web page or loopback server | Yes, in a browser | **No.** It adds a listener, or an HTML export copies case text and notes out of the store. | Larger | Rejected |

**What B reuses from TriageDesk.** B reuses the inspector layout, a list pane
beside a detail pane ([app.py:1788–1839](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/ui/app.py#L1788-L1839)),
and the visible focus-ring convention
([app.py:1000–1018](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/ui/app.py#L1000-L1018)).
It imports no TriageDesk code, so none of TriageDesk's start-up side effects
run. TriageDesk's own Timeline tab
([app.py:1928–1939](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/ui/app.py#L1928-L1939))
renders `.triagecore/ledger.jsonl` events, which CR-138's decision D2 keeps
out of this workflow.

**What B reuses from CR-138, unchanged.**

| Source | Reused |
| --- | --- |
| [`ReviewStore`](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/checklist_review_store.py#L310-L323) | `open_readonly()`, which opens SQLite in `mode=ro` and sets `PRAGMA query_only = ON` ([L325–L338](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/checklist_review_store.py#L325-L338)). Also `list_runs()` and `list_events()`, which orders by `seq` ([L745–L755](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/checklist_review_store.py#L745-L755)); `project_run()` ([L875–L939](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/checklist_review_store.py#L875-L939)); `read_artifact()`, which reports `verified`, `evidence_missing`, or `evidence_digest_mismatch` ([L409–L419](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/checklist_review_store.py#L409-L419)); and `load_definition()`. |
| [`checklist_review_cli.py`](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/checklist_review_cli.py#L235-L251) | The evidence checks behind `show --evidence`: `_load_case` (`verified`, `not_stored`, an artifact status, or `verified, unparsed (<code>)`) and `_artifact_status`. Also the reason-text and uncited-row logic in `render_evidence` ([L352–L444](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/checklist_review_cli.py#L352-L444)). See D3. |
| [`checklist_review.py`](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/triage_core/checklist_review.py#L443-L460) | `parse_case`, `ReviewCase.line`, `evidence_outline` (`target_lines`, `register_lines`, `register_rows`, `matching_rows`, `document_id`, `controlling_file`), `parse_model_result` (`reason_text`, `unresolved_citations`), `ITEM_ID`, `RULE_ID`, and `POLICY_ID`. |

**Event fields read.** The view model reads the `Event` columns `event_id`,
`run_id`, `seq`, `item_id`, `step`, `kind`, `status`, `reason_code`,
`target_event_id`, `supersedes_event_id`, and `recorded_at`. It also reads
the artifact roles `case`, `request`, `output`, and `note`, and these record
fields:

| Event (`step`/`kind`) | Record fields shown |
| --- | --- |
| `attempt`/`started` | `origin`, `origin_label`, `refers_to`, `definition_ref`, `definition_digest`, `runtime_confirmation`, `case.sha256`, `case.stored` |
| `rule`/`result` | `finding`, `reason_code`, `deciding_step`, `cited_labels`, `gaps`, `target_lines`, `kept_rows` |
| `model`/`preflight` | `identity_source`, `expected_tag`, `expected_digest`, `observed_tag`, `observed_digest` |
| `model`/`request` | `settings_sent`, `message_count`, `case_sha256`, `request_sha256`, `request_bytes` |
| `model`/`result` | `finding`, `reason_code`, `cited_labels`, `citation_resolution`, `unresolved_citation_count`, `measurements` |
| `policy`/`result` | `finding`, `agreement`, `evidence_status`, `rule_finding`, `model_finding`, `rule_event_id`, `model_event_id` |
| `attempt`/`finished` | `stage`, `stages_reached` |
| `human`/`assessment` | `finding`, `disposition`, `revision_of`, `label_assessment`, `evidence_assessment`, `cited_labels`, `reason_code`, `record_kind`, `target_step`, `target_finding`, `note.stored`, `measurements` |

### Exact file scope

The following scope applies to the original timeline candidate. The
[operator guide and timeline grant](#implementation-grant-for-the-operator-guide-and-timeline)
defines the writable paths for the candidate based on `49e3ad4`.

The base is `origin/main` at `10af245c18095346d7d60b55b2e105bb819f4828`. The
first-delivery release `022b4a1227b68b899bf1df2aa83d154e9f4855f4` is the
code baseline. `git diff 022b4a1 10af245` changes only
`docs/change/change_log.md` and the CR-138 record, so `triage_core/` and
`tests/` are identical at both commits. Build in an isolated worktree pinned
to the base. Recheck these paths against it before editing.

| Path | Change |
| --- | --- |
| `triage_core/checklist_review_timeline.py` | New. A Tk-free view model: run summaries, ordered timeline rows, text labels, link resolution, per-event details and evidence, and the navigation state for focus, scroll, and the back stack. It is read-only and imports no network module. |
| `triage_core/checklist_review_timeline_tk.py` | New. The `tkinter.ttk` window: run list, run view, timeline, preview strip, and details pane. It contains only input bindings and rendering. |
| `triage_core/checklist_review_cli.py` | Add the `timeline` subparser and include `timeline` in the parent command's usage list in `configure_parser`. Add its dispatch branch in `run`. Import the timeline modules lazily. Preserve help and output for the existing `save`, `run`, `show`, and `review` subcommands. |
| `tests/test_checklist_review_timeline.py` | New. Headless tests: fixtures, ordering, labels, links, evidence and gaps, navigation state, `--list`, the read-only snapshot, zero connection attempts, and restart in a new process. |
| `tests/test_checklist_review_timeline_tk.py` | New. Tk interaction tests for preview, pinned details, Escape, focus, scroll restoration, back to item, and the private-evidence clipboard boundary. They skip with a recorded reason when `tkinter` or a display is unavailable. |
| `docs/operations/checklist-review-timeline.md` | New. Operator steps, the Windows `python -m triage_core.tc_cli` form, the store integrity comparison, and the operator checks below. |

No change to `triage_core/tc_cli.py`, because `checklist-review` already
dispatches to `checklist_review_cli.run`. No change to
`checklist_review.py`, `checklist_review_store.py`,
`checklist_review_local.py`, the CR-138 tests, or
`tests/fixtures/checklist_review/`, which are read as inputs only. Also no
change to `triage_core/ui/app.py`, `triagedesk_adapter.py`,
`pyproject.toml` (`tkinter` is in the standard library), CI, the README, or
the standard ledger. Updates to `docs/current_backlog.md` and
`docs/change/change_log.md` are lifecycle records made at later stages, not
part of an implementation grant.

### System and action scope

- **Reads:** one operator-named store, opened read-only. Fixture stores live
  in test temporary directories.
- **Writes:** none. The viewer creates no settings, cache, recent-runs list,
  log, export, or ledger entry. It displays private case text, model output,
  and rationale notes in the details pane. Viewer controls keep that content
  off the system clipboard. The `--list` flag emits metadata only.
- **Network:** none. The timeline modules never construct `ReviewModel` or
  any HTTP client. Inspection works with Ollama stopped.
- **Decisions:** none. The viewer has no review action. Decisions are still
  recorded only by `tc checklist-review review`.

### Out of scope

Replay and linked resume (CHE-90), rollback and file restoration (CHE-91),
and the solo acceptance trial (CHE-92). Also out of scope: recording or
editing decisions from the viewer, schema or event changes, a reviewer
identity field, TriageDesk integration (including a launcher button), live
refresh while another process appends, exports, remote or web access,
screen-reader support, and any claim about real documents or model quality.

## Design

### Entry points and navigation

```text
tc checklist-review --store <dir> timeline [--run <run-id>] [--item <item-id>] [--event <event-id>] [--list]
```

1. **Run list** (no `--run`): every run in `list_runs()` order. Each row
   shows the run ID, creation time, origin (with any label), case ID, the
   attempt status, reason, and stage, and the saved decision's source and
   finding. Live runs, recorded runs, and repeat attempts on the same case
   are separate rows.
2. **Run view** (`--run <run-id>`). Read the saved decision from
   `project_run().overall`. Show the human decision (finding, disposition,
   revision, assessments, and event ID), the policy result with review
   available, or "none" with the attempt status, reason, and stage. On a
   human decision, **Based on** opens the target event's details in the
   timeline. A policy result links to its own row, whose details link to the
   rule and model results. The item list currently contains `revision-approval`.
3. **Timeline** opens when Corey selects an item or passes
   `--run <run-id> --item <item-id>`. It shows the run's full event sequence.
   Focus starts on the effective human event, the policy result if there is
   no human decision, or the last event before the attempt ended. For the
   DC-03 stop, that is the preflight event. With `--run` and `--item`,
   `--event` focuses and previews the named row. Click, tap, or Enter opens
   its details. An event outside the selected run returns
   `timeline_event_unknown`.
4. **Back** (button or `Alt+Left`) returns from the timeline to the run
   view with the same item focused, then to the run list with the same run
   focused. Direct entry through `--item` or `--event` and opening **Based on**
   establish the same back path as selecting the item in the run view.

`--list` prints the timeline rows as metadata only and opens no window. The
output contains sequence numbers, event IDs, scopes, labels, closed codes,
cited labels, and link IDs, with no case text, model text, or notes. It
supports the restart comparison and handback transcripts without a display.

### Timeline rows

Rows are every event of the run in `seq` order, which is the store's
per-run sequence (see D2). Each row shows its sequence number, time, scope,
category, stage, actor, and outcome as text, plus the full event ID.
Colour is never the only signal.

| Event | Scope | Category | Stage | Actor | Outcome |
| --- | --- | --- | --- | --- | --- |
| `attempt`/`started` | Run | Run step | Attempt start | TriageCore runner | `started`; origin; runtime confirmation |
| `rule`/`result` | Item | Component result (advisory) | Rule result | Rule `R-DOCREV v0.1` | finding; reason code; cited labels |
| `model`/`preflight` | Run | Run step | Model preflight | Model runtime (`identity_source`) | `ok` or `stopped` with reason |
| `model`/`request` | Run | Run step | Model request prepared | TriageCore runner | `prepared`; request artifact status |
| `model`/`result` | Item | Component result (advisory) | Model result | Model `<tag from definition>` | status; finding; citation resolution |
| `policy`/`result` | Item | Policy result (advisory) | Policy result | Policy `C-AGREE v0.1` | finding; agreement; evidence status |
| `attempt`/`finished` | Run | Run step | Attempt end | TriageCore runner | status; reason; stage |
| `human`/`assessment` | Item | Human decision | Human assessment | Human reviewer | finding; disposition (revision of); label and evidence assessments; `current` or `superseded`; record kind |

The categories keep component results (rule and model) apart from the
policy result and from human decisions. Rule, model, and policy rows are
labelled advisory. The store records no reviewer identity, so the actor
reads "Human reviewer". An unrecognized `kind` renders as a generic row with
its raw closed values instead of failing.

### Details and evidence

Click, tap, or Enter opens a details pane for the row. The pane stays open
until Corey closes it with the Close button or Escape, or opens another row.
Every pane shows the run ID, event ID, sequence number, and time. It also
shows the command that opens the timeline focused on this row. The command
uses the `<store>` placeholder.
`tc checklist-review --store <store> timeline --run <run> --item <item> --event <event>`.

| Event | Evidence shown | Gaps shown explicitly |
| --- | --- | --- |
| Attempt start | Origin, label, `refers_to`, definition digest, runtime confirmation, case digest, case status | `not_stored`, `evidence_missing`, `evidence_digest_mismatch`, `verified, unparsed (<code>)` |
| Rule result | Work-product header lines (`target_lines`), the whole controlling register, rows matching the Document ID, and the cited lines resolved against the recorded case | Rule `gaps`; "Controlling register: not supplied"; case status |
| Model preflight | Separately labelled expected and observed model tags and digests, identity source, status, and saved reason | Show "none observed" when the observed identity fields are absent |
| Model request | Settings sent, message count, request and case digests | Request artifact status |
| Model result | Work-product header and whole controlling register in source order, derived from the verified case independently of model citations. Show matching Document ID rows and resolve the model's citations, marking cited lines in the source context. Label the model's reason as model text. | Unresolved citations, case and output artifact status, and reason unavailable |
| Policy result | Rule and model findings, agreement, evidence status, and links to the rule and model rows | — |
| Attempt end | Status, reason, stage, and stages reached. Stages not reached read "not reached". | — |
| Human assessment | Finding, disposition, revision, assessments, reason code, record kind, cited lines, and the private note. Links go to the target event and to any superseded event. Any later events that supersede this one are listed. | Note artifact status; case status |

Links are buttons in the details pane. Following one focuses the linked row,
scrolls it into view, and shows its details. **Back** inside the pane
returns to the previous details. **Close** ends the whole chain and returns
to the row where the chain started.

### Preview, focus, and scroll

| Input | Preview | Open details | Close details |
| --- | --- | --- | --- |
| Pointer | Hovering over a row (`<Motion>`) shows its stage, actor, outcome, and short ID in a fixed preview strip without moving focus. Leaving the list returns the preview to the focused row. | Click (`<ButtonRelease-1>`) | Close button |
| Keyboard | Entering the list with Tab previews the focused row. Up, Down, Home, End, and the Page keys move focus and update the preview. | Enter or keypad Enter | Escape |
| Touch | The focused row's preview is shown. | Tap through the proposed Windows click binding, with device verification under D5 | Tap Close |

Hover and keyboard focus update the preview strip while the details pane
keeps showing the event Corey opened. The pane changes when Corey opens a
different row or follows a detail link. When details open, the view model
saves the row's event ID and `yview()[0]` as the return position. Closing
details calls `focus(row)`, `selection_set(row)`, and `focus_set()` on the
list, then `yview_moveto(anchor)`. The list keeps its
geometry while the details pane is open, so restoring the position cannot
depend on reflow. The tab order is run list, then run view controls,
timeline list, preview, and details links. The focus highlight stays
visible.

### Read-only and offline boundary

- The store is opened only through `ReviewStore.open_readonly()`. The
  timeline modules never call `create`, `open`, `save_definition`,
  `append_event`, `record_human_assessment`, or `run_review`.
- No persisted UI state. Restart behaviour comes entirely from the store,
  so closing and reopening the app shows the same ordered history.
- Errors use closed reason codes and never print case text, model text,
  notes, or paths. The codes are `store_missing`, `store_unreadable`,
  `store_schema_unsupported`, `run_unknown`, `item_unknown`,
  `timeline_event_unknown`, and `timeline_display_unavailable`. The last one
  covers `tkinter` not being importable or no display.
- The window title shows the run ID only. Case text, model text, and notes
  appear only inside the window.

### Compatibility with CR-138 stores

The viewer reads schema version `1` and store kind
`triagecore.checklist_review`. `ReviewStore._configure` already rejects
anything else with `store_schema_unsupported`. This CR adds no table,
column, step, kind, migration, or write. The store module has not changed
since the first candidate `efe28d7`, because the later corrections touched
only `checklist_review_local.py` and its tests. Runs saved by `efe28d7`,
`b1c4596`, and `697f8e1` in Corey's private store therefore open unchanged.
Missing record keys display as `unknown`.

## Acceptance criteria

Each named test file runs and fails before its implementation, then passes.

**View model (headless, runs in CI):**

- [ ] TL-02 shows eight rows in `seq` order: attempt start, rule result,
  model preflight, model request, model result, policy result, attempt end,
  and human assessment. Rule, model, and policy all show `insufficient
  evidence`. The human row shows `insufficient evidence`, `revised
  (explanation)`, label `correct`, evidence `unsupported`, `current`, and a
  target link to the model row.
- [ ] TL-02 model details show WP.L02 and WP.L03 and the full controlling
  register in source order. No register row has Document ID EQ-INV-07.
  The model explanation is labelled as model text, and S1.L05 is visible as
  an uncited row. A synthetic TL-02 variant that cites only register lines
  still shows both work-product header lines and the full register. Policy
  details link to the rule and model rows by event ID.
- [ ] The original model event and the human event are distinct rows with
  distinct IDs. The model event's record and output digest are unchanged
  after the human event.
- [ ] TL-03S shows four rows in order: attempt start, the inspectable rule
  result of `match` citing WP.L02, WP.L03, and S1.L04, model preflight
  `stopped` with `tags_invalid_response`, and attempt end `stopped` at stage
  `preflight`. The run-level preflight row has its own event ID and is
  focused by default. Its details show the expected model tag and digest
  and "none observed" for the observed identity. The attempt end states
  that model request, model result, and policy were unreached. The saved
  decision reads "none" with the stop, and no human assessment is present.
- [ ] TL-03OK appears in the same fixture store as a separate run, and none
  of its rows appear in the TL-03S timeline.
- [ ] TL-02G (disposable) shows `evidence_missing` for the removed case,
  `evidence_digest_mismatch` for the altered model output, and
  `evidence_missing` for the removed note. IDs, statuses, links, and the
  saved decision stay visible. A parity test confirms that these statuses
  match what `render_evidence` prints for the same store.
- [ ] Navigation state: open row *k* at scroll fraction *f*, follow two
  links, go back, and close. Focus returns to *k* at *f*. Back to item
  focuses the same item, and back to runs focuses the same run.
- [ ] `--run` alone opens the saved decision and item list. **Based on** for
  TL-02 opens the original model event linked by the human review. Entry
  with `--run` and `--item` opens the timeline, and adding `--event` focuses
  the named row. Back from either route focuses the same item and then the
  same run. An event from another run returns `timeline_event_unknown`.
  Sentinel text from case, model, and note artifacts stays out of
  `--list` output.

**Window (Tk; skipped with a recorded reason when unavailable):**

- [ ] Hover previews a row without changing focus, and click opens its
  details. While those details are open, hover another row and verify
  that only the preview changes. Close restores the opened row and its
  scroll position in a timeline long enough to scroll (TL-02S).
- [ ] Tab to the timeline list and verify the focused row previews. Move
  with the arrows and press Enter to open details. Move focus to another
  row and confirm that the opened event stays in the details pane. Tab
  reaches detail links. Follow a link and press Escape to close the pane.
  Focus and scroll return to the row where it opened. `Alt+Left` returns
  to the same item.
- [ ] Selecting private evidence and using the platform's copy gesture in
  its details pane leaves the clipboard contents unchanged. Use fixture
  text for this check.

**Read-only, offline, and restart:**

- [ ] Before invoking the CLI, instrument `HTTPConnection.connect`,
  `socket.create_connection`, `socket.socket.connect`, and
  `socket.socket.connect_ex`. Each hook records a call before raising.
  Open the fixtures in window and `--list` modes. Assert zero calls
  after each launch so a caught connection error still fails the check.
- [ ] A snapshot of the fixture store (relative path, size, `mtime_ns`,
  SHA-256) is identical before opening and after closing, with no new files
  such as `-journal`, `-wal`, or `-shm`. No `.triagecore/` directory, and
  therefore no `ledger.jsonl` or `triagecore.log`, is created in the
  working directory.
- [ ] A new Python process returns the same ordered
  `(seq, event_id, step, kind, status, target, supersedes)` tuples for TL-02
  and TL-03S.
- [ ] `timeline` is registered under `checklist-review` only and appears in
  the parent usage printed by `tc checklist-review --help`. Existing
  subcommand help and output are preserved. The four CR-138 test files
  pass unchanged, and `tc_cli.py` is unchanged.

**Integration:**

- [ ] Run the two new test files, then the four CR-138 files, then
  `python -m pytest -q`. Report exact counts, and compare any failures with
  the baseline at `10af245` (CR-138 recorded pre-existing failures and the
  FastAPI collection stop).
- [ ] The scope diff against the base contains only the paths above, and
  `git diff --check` is clean.
- [ ] Corey completes the [operator checks](#operator-checks-on-the-saved-runs).

## Offline fixtures

Builders in `tests/test_checklist_review_timeline.py` create each fixture
in a temporary store. They use the real `run_review` runner and the real
`ReviewStore`, the pinned CR-138 case and reply fixtures, and a stubbed
model boundary that makes no I/O. No new fixture files are added, and
nothing is copied from the private store. Each fixture run carries a label
in `origin_label` and the saved run ID in `refers_to`, so the timeline shows
its provenance.

| Fixture | Equivalent saved record | How it is built | Known differences |
| --- | --- | --- | --- |
| **TL-02** — `offline fixture TL-02` | DC-02 run `62866263-2842-4e85-acd2-2e681fadb0fa` on `697f8e1`, model event `9f6d72ff-…`, human review `59430e1f-…` | `cases/DC-02.txt` and the sealed reply `recorded/R01_DC-02_slm.txt`, using a stub with live origin and a confirmed runtime. The fixture then records a human review targeting the model result: `insufficient evidence`, `revised`, `correct`, `unsupported`, citing WP.L02, WP.L03, and S1.L03 to S1.L05, with reason `no_matching_document` and a private note. | IDs and times differ. CR-138 matched the sealed reply to the `efe28d7` live reply, but no public record shows the `697f8e1` reply digest. The public record also omits review `59430e1f`'s reason code, so the fixture uses the CR-138 recorded check's `no_matching_document`. |
| TL-02 variant without header citations | Same source context as TL-02 | Use an inline synthetic model reply that keeps `insufficient evidence` and cites only S1.L03 and S1.L04. Keep the case and linked human assessment from the TL-02 recipe. | The reply is synthetic. The sealed reply fixture is untouched. |
| **TL-02S** | Same as TL-02 | TL-02 plus twelve superseding human reviews, which make the list long enough to scroll and exercise `supersedes` links | Synthetic reviews |
| **TL-02G** — disposable | Missing-source variant | A copy of TL-02 with the case artifact removed, the model output altered by one byte, and the note removed | Deliberately damaged |
| **TL-03S** — `offline fixture TL-03S` | DC-03 stop: run `a64e0a30-08ba-43e6-acc1-658575f309c9` on `b1c4596`, preflight event `fb285f67-…` | `cases/DC-03.txt`. The stub's preflight returns `stopped` with `tags_invalid_response` and identity source `observed`, with the observed tag and digest absent as in an invalid tags reply. | IDs and times differ |
| **TL-03OK** — `offline fixture TL-03OK` | The later successful DC-03 run `4d16a147-b49b-4ce4-b3ff-fd2f620f8618` on `697f8e1`, as a separate run | `cases/DC-03.txt`, in the TL-03S store, with an inline synthetic reply: `match`, citing WP.L02, WP.L03, and S1.L04 | The reply is synthetic, not the live output |

The existing CR-138 recorded R01/DC-02 path (`RecordedReply`) gets one
labelling check: its origin reads "recorded (replayed)" and its human row
reads `demonstration`.

## Operator checks on the saved runs

Corey runs these checks against the private store Corey selected, on the
candidate build. No agent receives the store path or opens the store. The handback
records run and event IDs, pass or fail for each step, and the integrity
comparison result only. It never includes paths, case text, model text, or
notes. See D6.

**Before each check.** Stop Ollama, and confirm that nothing is listening on
`127.0.0.1:11434`. Then record a listing of the store:

```powershell
$store = "<private-dir>"
$before = Get-ChildItem -LiteralPath $store -Recurse -File | Sort-Object FullName | ForEach-Object { "{0}|{1}|{2}|{3}" -f $_.FullName.Substring($store.Length), $_.Length, $_.LastWriteTimeUtc.Ticks, (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
```

**DC-02: original result and correction.**

```powershell
python -m triage_core.tc_cli checklist-review --store $store timeline --run 62866263-2842-4e85-acd2-2e681fadb0fa
```

1. In the run view, verify the saved human decision from
   `59430e1f-50e2-4c8f-8d5f-54c9088d73ff`. The finding is
   `insufficient evidence`, the explanation was revised, the label is
   `correct`, and the evidence assessment is `unsupported`.
2. Follow **Based on** and verify the original model event
   `9f6d72ff-c281-40ee-9e33-2e5e4dcf3a79`. Close the pane and go Back to
   the run view. Confirm focus on `revision-approval`, then open that item.
3. Preview the model row by hovering and by keyboard focus. Open details
   by click and by Enter. The pane shows the work-product header at
   WP.L02 and WP.L03, the whole controlling register with no EQ-INV-07
   row in S1.L03–S1.L05, and the original explanation labelled as model
   text. Rule, model, and policy each show `insufficient evidence`.
4. While model details are open, preview the human row. The pane stays on
   the model event. Close by pointer and by Escape in separate passes.
   Each time, focus and scroll return to the model row where details opened.
5. Open human review `59430e1f-…`. Verify that it keeps the finding, marks
   the explanation unsupported, links to `9f6d72ff-…`, and shows the note.
   Close the details and go Back. Confirm focus on `revision-approval`.
6. Close the app and rerun the command. Open the item and verify the same
   rows, IDs, and human-to-model link.
7. On Windows touch hardware, repeat open and Close with taps and verify
   focus and scroll restoration. Record the result under D5.

**DC-03: preflight stop.**

```powershell
python -m triage_core.tc_cli checklist-review --store $store timeline --run a64e0a30-08ba-43e6-acc1-658575f309c9
```

1. The saved decision reads "none". The attempt stopped at `preflight` with
   `tags_invalid_response`, and no human review was saved.
2. Open `revision-approval`. The timeline shows attempt start, rule result,
   model preflight `fb285f67-2399-496c-8784-351a742292e5`, and attempt end.
   Inspect the rule's `match` and its WP.L02, WP.L03, and S1.L04 evidence.
3. Open the preflight row. Verify its saved reason `tags_invalid_response`,
   the expected model tag and digest, and "none observed" for the observed
   identity. The attempt-end details mark model request, model result, and
   policy as "not reached".
4. Restart and reopen. Verify the same saved event sequence and stop.
5. If the selected store contains `4d16a147-b49b-4ce4-b3ff-fd2f620f8618`,
   verify that the later successful DC-03 appears as a separate run.

**After each check.** Recompute the listing as `$after`. Then run
`Compare-Object $before $after`, which should print nothing. Record only
"no differences".

## Control-plane invariants

Per the
[control-plane invariant checklist](https://github.com/coreytshaffer/TriageCore/blob/10af245c18095346d7d60b55b2e105bb819f4828/docs/operations/control-plane-invariant-checklist.md):

- **Row 2:** the standard ledger is untouched, and the viewer persists
  nothing.
- **Rows 7 and 9:** the viewer is read-only, with no write path and no
  export. Failures use closed reason codes.
- **Row 10:** the viewer shows advisory results and human decisions. It
  cannot record a decision.
- No row is weakened.

## Design acceptance record

On 2026-11-21 (Pacific), Corey Shaffer separately accepted CR-139's
recommended design at `62e328d` in draft PR #205. The decision includes
D1–D6, the planned acceptance checks, and the clarification that the parent
command's usage lists `timeline`.
[Reviewed design](https://github.com/coreytshaffer/TriageCore/blob/62e328d1f0f9546c409643f9df203efd86b91166/docs/change/requests/CR-139-checklist-review-action-timeline.md#L518) ·
[Exact file scope](#exact-file-scope)

- **D1 — Surface.** Use the standalone `ttk` window opened by
  `tc checklist-review timeline`.
- **D2 — Timeline scope.** The timeline includes every saved event in the
  selected run, with run-level rows labelled "Run". DC-03's preflight is
  selectable by its saved event ID and opens its own outcome and reason.
- **D3 — Evidence-check reuse.** Call `_load_case` and `_artifact_status`
  in place from `checklist_review_cli.py` and check parity against
  `render_evidence`.
- **D4 — Details presentation.** Use the docked, non-modal details pane.
  Keep the opened details visible during hover and keyboard previews of
  other rows, with the close and return behaviour defined above.
- **D5 — Touch verification.** Record step 7 on Windows touch hardware
  against the candidate. If hardware is unavailable, keep the check
  unverified until a device test or an explicit waiver from Corey. Record
  any waiver separately from the passed checks.
- **D6 — Timing of the operator checks.** Corey runs the planned read-only
  checks on the saved cases against the candidate before the separate
  implementation acceptance decision.

## Implementation authority record

On 2026-11-21 (Pacific), Corey Shaffer explicitly approved the draft
`CR-139-implementation-grant-draft.md` for Claude, pinned to design
`62e328d1f0f9546c409643f9df203efd86b91166`. The approved grant has SHA-256
`94264302be0daa30efcc6c16c1ea4980dd6a6f53efbf4e51df6cc818d2ca4338`.
[Accepted design](https://github.com/coreytshaffer/TriageCore/blob/62e328d1f0f9546c409643f9df203efd86b91166/docs/change/requests/CR-139-checklist-review-action-timeline.md) ·
[Design decision and CLI clarification](https://github.com/coreytshaffer/TriageCore/blob/0b605723c8e5b64c40e317394863296018e661da/docs/change/requests/CR-139-checklist-review-action-timeline.md#design-acceptance-record)

The grant takes effect when this record is committed and published to
[draft PR #205](https://github.com/coreytshaffer/TriageCore/pull/205), before Claude starts implementation.
Claude verifies the published record, the design pin, and the base before
editing implementation files.

- **Candidate scope.** Claude may build and verify one local candidate
  in an isolated worktree based on `10af245c18095346d7d60b55b2e105bb819f4828`.
  Repository writes are limited to the six paths in the accepted file
  scope. The CLI change covers registration, lazy dispatch, and inclusion
  of `timeline` in the parent usage. Preserve help and output for the
  existing subcommands. [Accepted file scope](https://github.com/coreytshaffer/TriageCore/blob/0b605723c8e5b64c40e317394863296018e661da/docs/change/requests/CR-139-checklist-review-action-timeline.md#exact-file-scope)
- **Verification scope.** Claude may use disposable offline fixture stores
  and test directories and create one local candidate commit. Timeline
  inspection opens the selected store read-only, makes zero network calls
  including loopback, and keeps private evidence in the details pane.
  [Accepted system and action scope](https://github.com/coreytshaffer/TriageCore/blob/0b605723c8e5b64c40e317394863296018e661da/docs/change/requests/CR-139-checklist-review-action-timeline.md#system-and-action-scope)
- **Operator checks.** Corey runs the planned read-only DC-02 and DC-03
  checks on the candidate before implementation acceptance. Corey retains
  the private store and returns run and event IDs, check results, and the
  store integrity comparison. The D5 touch check requires device evidence
  or a separately recorded waiver. [Operator procedure](#operator-checks-on-the-saved-runs)
- **End of authority.** This grant ends at local candidate handback.
  Implementation acceptance, remote publication of the candidate, merge,
  release, and closeout require separate decisions. Replay and linked
  resume (CHE-90), rollback and file restoration (CHE-91), and the solo
  trial (CHE-92) are out of scope.

## Local corrective implementation grant

On 2026-11-21 (Pacific), Corey Shaffer authorized Claude to address all four
review findings in **one local corrective commit**. The original grant at
`8a0ab44` ended when Claude handed back `36a6a4c`. The corrective commit
must have `36a6a4c0fff9da6a0577288e2729e4c29dce5b7f` as its sole parent
on `claude/cr-139-che-89-action-timeline-impl`. The accepted design is `62e328d`.

**Files Claude may change in the corrective commit**

- `triage_core/checklist_review_timeline.py`
- `triage_core/checklist_review_timeline_tk.py`
- `tests/test_checklist_review_timeline.py`
- `tests/test_checklist_review_timeline_tk.py`
- `docs/operations/checklist-review-timeline.md`

**Required corrections and offline checks**

1. **Missing policy assessment.** In a seven-event schema-1 fixture, omit
   `evidence_status` from the effective policy result. Verify that the run
   opens, all seven events and their links can be inspected, and the missing
   assessment reads `unknown`.
2. **Missing stage history.** In a four-event preflight stop, omit
   `stages_reached`. Show `unknown` for the missing history and preserve the
   saved rule and preflight rows. Verify that an explicit stage list still
   supports `not reached` for later stages in the intact stop fixture.
3. **Clipboard isolation.** Use an isolated, test-owned clipboard for setup,
   gestures, assertions, and teardown. Verify that an ordinary Tk text widget
   copies fixture text and that the viewer's copy and cut gestures preserve
   the sentinel. Keep the operator's system clipboard outside the test and
   update the runbook to describe the isolated check.
4. **Tk callback errors.** Use only the seven [approved reason codes](#read-only-and-offline-boundary).
   Verify that a recognized error keeps its code and an unexpected `ValueError`
   emits a single diagnostic with an approved code. Exception class names,
   messages, paths, and tracebacks are outside the diagnostic.

Claude may verify the correction with disposable offline fixtures. At local
handback, report the commit and parent, the changed paths, `git diff --check`
against `36a6a4c`, and the test results for the four corrections, including
any failures or skips. This grant ends at that handback.

Corey alone runs the read-only saved DC-02 correction check
(`62866263-2842-4e85-acd2-2e681fadb0fa`) and DC-03 preflight-stop check
(`a64e0a30-08ba-43e6-acc1-658575f309c9`) on the corrected candidate.
Both checks are planned. Corey retains the private store. D5 requires a
Windows touch-device result or Corey's separately recorded waiver.
[Saved-run procedure](#operator-checks-on-the-saved-runs)

Implementation acceptance, remote publication, merge, release, and closeout
each require a separate decision from Corey. The [scope exclusions](#out-of-scope)
include replay, linked resume, rollback, and file restoration.

## Corrective grant for malformed and interrupted runs

On 2026-11-21 (Pacific), Corey Shaffer authorized Claude to address the two
findings below in **one local corrective commit** on
`claude/cr-139-che-89-action-timeline-impl`. Its sole parent must be
`89b0c79ca00b9a06940bb2c0c02077e525bb29d7`. The [first corrective grant](#local-corrective-implementation-grant)
ended when Claude handed back that parent. At that handback the local CR-139
file containing the first corrective grant had SHA-256
`00be452b89bccc5599188688125a23f8209d7844f375eb427a6891e1e15e816e`.

**Files Claude may change in this commit**

- `triage_core/checklist_review_timeline.py`
- `tests/test_checklist_review_timeline.py`
- `tests/test_checklist_review_timeline_tk.py`
- `docs/operations/checklist-review-timeline.md`

**Required corrections and offline checks**

1. **Malformed run.** Use a disposable schema-1 store containing one run
   whose first event is `rule/result` and one intact run. Translate the
   internal `run_incomplete` error to `store_unreadable` in the timeline
   model. The window's run list and `timeline --list` must identify only
   the affected run as unreadable. The list command exits `0` and the intact
   run can still be opened. `timeline --run <bad-id> --list` exits `1`
   with empty stdout and one stderr line,
   `tc: error: checklist-review timeline: store_unreadable`. The window's
   **Open run** action stays on the list and shows `Cannot open: store_unreadable`.
2. **Interrupted run.** Save attempt start, rule result, and model preflight
   in a disposable store, then close it before an `attempt/finished` event.
   The run view and `--list` must show the attempt as `incomplete` and
   `Stages reached: unknown`. Verify that all three saved events keep their
   IDs and order and can be inspected. Use the intact four-event preflight
   stop as a control. Its explicit stage history reads `attempt rule preflight`,
   and its attempt-end details mark model request, model result, and policy
   as `not reached`.

Update the runbook to describe the inline **Open run** error, the one-line
CLI diagnostic, and the interrupted-run summary. Use the existing offline
fixtures and store-integrity checks. At handback, report the commit and its
parent, the changed paths, `git diff --check 89b0c79 HEAD`, and results for
both cases and the timeline, Tk, and CR-138 tests, including failures or skips.
This grant ends at that local handback.

Corey alone runs the [saved-run checks](#operator-checks-on-the-saved-runs)
on the corrected candidate with Ollama stopped. The DC-02 correction
(`62866263-2842-4e85-acd2-2e681fadb0fa`) and DC-03 preflight stop
(`a64e0a30-08ba-43e6-acc1-658575f309c9`) are both planned. Corey retains
the private store. D5 requires a Windows touch-device result or Corey's
separate waiver. Implementation acceptance, remote publication, merge,
release, and closeout each require a separate decision from Corey.
Replay and rollback remain [outside the scope of CR-139](#out-of-scope).

## Design amendment for the operator guide and timeline

On 2026-11-22 (Pacific), Corey Shaffer accepted the design amendment in
`CR-139-accessible-operator-ui-grant-draft.md` as drafted. It extends the
design accepted at `62e328d1f0f9546c409643f9df203efd86b91166`. Corey chose
**Larger** and confirmed the mockup's timeline buttons were easy to select.
The reviewed mockup has SHA-256
`e9ae074a0ff451cd7695127d0345e977c8601ce70c9945a6c73d15705ba8361b`.
[Original design decision](#design-acceptance-record)

- **Entry and navigation.** Double-click **Open TriageCore Review** to start
  the pinned Windows GUI and choose a review folder. Ordinary use has one Tk
  root, event loop, visible window, and size control. **Back to guide** restores
  the case, instruction, observations, and initiating control. Preserve the
  standalone timeline, docked details, and Tk-free `timeline --list`.
- **Text and targets.** Start each independent guide or timeline session at
  **Larger**. **Large / Larger / Largest** correspond to 22 / 26 / 30 logical
  pixels at 100% display scale. Share the setting in memory across both views.
  Full actionable rows and primary buttons have a minimum logical height of
  `max(56, 2.7 × body size)`, allowing native rounding. Use DPI-aware sizing,
  visible focus and full-word controls. At 900 × 560, evidence and controls
  remain reachable at Largest.
- **Inspection.** Guide steps, the chooser, rows, evidence links, and Close
  are keyboard-operable. A stationary pointer does not override a keyboard
  preview after scrolling, resizing, or changing text size. Other previews
  leave opened evidence pinned. Close or Escape restores the opening row and
  scroll position. **Based on** and **Back** preserve the evidence trail.
- **Restart and observations.** Only **Reopen in a fresh process** performs
  the restart check. It opens a fresh viewer process, carries the guided
  session's size, keeps one workflow window visible, then returns to the
  pending step. Retain the seven DC-02 and five DC-03 observations in
  memory. A failed launch stays unverified. **Verified absent** requires
  opening the separate run list. Case outcomes are explicit operator choices.

D5 touch and D6 operator ownership carry forward. Corey alone performs the
saved-run checks. The separate implementation decision follows.

## Implementation grant for the operator guide and timeline

On 2026-11-22 (Pacific), Corey Shaffer separately approved Claude's single-use
implementation grant in `CR-139-accessible-operator-ui-grant-draft.md` as
drafted, SHA-256
`5c7703386fb53958f12febec17dae6350fcb0a1ef765603c04ac1e9445dd05f4`.
This grant takes effect with this local record. Claude may make **one local
candidate commit**, with sole parent
`49e3ad4d414561434713a762e488cbcc6e2cf5b1`, on
`claude/cr-139-che-89-action-timeline-impl`, and prepare the two named
local launcher files. The preceding corrective grant ended at handback of
`49e3ad4`. [Preceding grant](#corrective-grant-for-malformed-and-interrupted-runs)

| Repository path | Authorized change |
| --- | --- |
| `triage_core/checklist_review_guide_tk.py` | New native guide and shared window host. |
| `triage_core/checklist_review_timeline_tk.py` | Mount the existing views in the host and preserve standalone `launch(snapshot, navigator)`. |
| `triage_core/checklist_review_ui_scale.py` | New shared text sizes, DPI-aware targets, and focus styling. |
| `tests/test_checklist_review_guide_tk.py` | New disposable-fixture checks for guide startup, transitions, observations, sizing, and process restart. |
| `tests/test_checklist_review_timeline_tk.py` | Extend native keyboard, pointer, layout, and focus tests. |
| `docs/operations/checklist-review-timeline.md` | Update startup, controls, sizing, restart, and handback instructions. |

**Outside Git.** In the single operator staging directory specified in the
approved grant, Claude may update `CR-139-read-only-checks.py` (input SHA-256
`03f4724c916b6d442aeb58fb83f0f70a610639783d9a1233a0e9e428bd83b0a2`) and create
`Open TriageCore Review.lnk`. After creating the commit, pin the guide to the
new full candidate SHA. The shortcut targets the staging directory's
`CR-138-merge-review/venv/Scripts/pythonw.exe` by absolute path with
`-E -s -B` and the quoted absolute guide path. Its **Start in** directory is
the implementation worktree. Keep the store path, run IDs, and credentials
out of the shortcut. Installation, Desktop or Start menu changes, and
PowerShell policy changes are outside the grant.

**Verification and end of authority.** Claude uses disposable offline fixtures
only. Verify the candidate pin, clean tree, and passive port-11434 check
before each case and new viewer or run-list opening. Keep the read-only
loader, fixed error codes, isolated clipboard test, and per-case before/after
file and SHA-256 comparison, including on pause or close. Test navigation in both directions,
all three text sizes, keyboard and
pointer operation, a fresh viewer PID, intact fixture stores, and startup
failures. Exercise the final shortcut only through its first screen and
Cancel. Report Windows display settings, commands, results, failures, skips,
parent and candidate SHAs, changed paths, launcher hash, and shortcut
target, arguments, and local launch link. This grant ends at local handback.

The **saved DC-02 correction** (`62866263-2842-4e85-acd2-2e681fadb0fa`)
and **saved DC-03 preflight stop** (`a64e0a30-08ba-43e6-acc1-658575f309c9`)
are **planned for Corey alone** on the new candidate with Ollama stopped.
Corey retains the private store, supplies the observations, and verifies
integrity. D5 requires Corey's device check or explicit waiver.
Implementation acceptance, remote publication, merge, release, and closeout
require separate decisions. Replay, linked resume, rollback, file
restoration, and new model runs are outside this grant.
[Saved-run procedure](#operator-checks-on-the-saved-runs)

## Limitations

- The store records no reviewer identity, so human rows read "Human
  reviewer".
- Tk exposes limited UI Automation on Windows, so screen-reader support is
  not claimed. Touch activation and closing details remain unverified
  pending D5. Touch scrolling is also unverified. The scrollbar and Page
  keys are the planned scrolling controls.
- CI's Ubuntu job has no display, so the Tk tests skip there. The Windows
  job runs only a CR-OC-001C subset
  ([tests.yml:165–170](https://github.com/coreytshaffer/TriageCore/blob/10af245c18095346d7d60b55b2e105bb819f4828/.github/workflows/tests.yml#L165-L170)).
  Evidence for the window comes from a local Windows run and Corey's checks.
  The headless view-model tests run in CI.
- The window shows the store as it was when opened. Reopen it to see events
  appended later.
- `tkinter` is an optional, default-on component of the Windows CPython
  installer. Without it, the viewer fails closed with
  `timeline_display_unavailable`, and `--list` still works.
- The fixtures are equivalent in structure and findings, not byte-identical
  to the private store. See the differences column above.

## Evidence base

Observed on 2026-11-21 (Pacific) in `<recovered TriageCore checkout>`:

- The primary worktree is on branch `test/field-notebook-provenance-unknown-check`
  at `eaa05d949949c1454efcf0a32b8587c39ef17d61`, with a clean status and no
  stash. Three CR-138 worktrees also exist, and one has an untracked
  `.serena/` directory. None was modified.
- After `git fetch origin --prune`, `origin/main` is at `10af245`. Both
  `10af245` and `022b4a1` resolve to commits, and the release tag
  `cr-138-checklist-review-first-delivery-2026-11-21` resolves to `022b4a1`.
- Code and documents were read from a `git archive` export of `10af245`.
  Every code link above is pinned to `022b4a1`, whose `triage_core/` and
  `tests/` trees are identical.
- Claude prepared the initial uncommitted draft in a new worktree on
  `claude/cr-139-che-89-action-timeline-proposal` at `10af245`. The revised
  proposal entered [draft PR #205](https://github.com/coreytshaffer/TriageCore/pull/205)
  at `62e328d`, the revision reviewed for both decisions above.

Recorded evidence used, with no private store access:
[DC-02 fresh live verification on `697f8e1`](https://github.com/coreytshaffer/TriageCore/blob/10af245c18095346d7d60b55b2e105bb819f4828/docs/change/requests/CR-138-checklist-review-first-delivery.md#fresh-live-verification-record-for-697f8e1) ·
[DC-03 stop on `b1c4596`](https://github.com/coreytshaffer/TriageCore/blob/10af245c18095346d7d60b55b2e105bb819f4828/docs/change/requests/CR-138-checklist-review-first-delivery.md#corrected-build-dc-03-stop) ·
[Fixture provenance](https://github.com/coreytshaffer/TriageCore/blob/10af245c18095346d7d60b55b2e105bb819f4828/docs/change/requests/CR-138-checklist-review-first-delivery.md#fixture-provenance) ·
[First-delivery operator guide](https://github.com/coreytshaffer/TriageCore/blob/022b4a1227b68b899bf1df2aa83d154e9f4855f4/docs/operations/checklist-review-first-delivery.md) ·
[Verification guide](https://github.com/coreytshaffer/TriageCore/blob/10af245c18095346d7d60b55b2e105bb819f4828/docs/verification_guide.md) ·
[Change management](https://github.com/coreytshaffer/TriageCore/blob/10af245c18095346d7d60b55b2e105bb819f4828/docs/change/change_management.md)
