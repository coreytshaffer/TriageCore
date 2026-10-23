# Monitoring Coverage Integrity — Contract v0.1

Status: **draft design for review; unaccepted; not implemented**.

Recorded: 2026-10-22 PDT / 2026-10-23 UTC. Repository baseline:
`610c13f253ba631d7052727abe3d68845bb09bb5` (remote `main` rechecked).
Contract identifier: `mci/0.1`; this is a document version, not a CR number.
Revision: **r2** (2026-10-23; see section 10). Wire identifiers and digest
domains remain `mci/0.1`, and no revision adds a record field, so `mci/0.1` alone
cannot distinguish r0, r1 and r2. Reference results must record the contract
revision and the SHA-256 of this contract and of the fixture specification.

This document develops the [candidate](candidates/monitoring-coverage-integrity.md)
and [source inventory](../operations/monitoring-coverage-baseline-2026-10-22.md).
The [fixture specification](monitoring-coverage-fixture-spec-v0.1.md) freezes
reviewable synthetic expectations for this draft. “Must” below defines proposed
conformance within this synthetic profile; it does not assert installed controls,
design acceptance, implementation authority, or a change to existing TC schemas.

## 1. Claim and scope

The first claim is **deterministic reconciliation of supplied, independently
authored synthetic evidence**. Runtime census completeness and enforcement are
separate claims and remain `unknown` and `not_implemented`, respectively.

The prospective runtime profile is one explicitly enrolled local-only governed
`tc run`, one backend protocol and fixed model identity. It excludes the cloud
lane, other CLI commands, GUI, direct library/injected-backend calls, metadata
probes and host-wide activity. Exclusion is a disclosure, not prevention of bypass.
Synthetic tool effects may exercise the accounting rules in a separate fixture
profile; they do not imply a TC tool mediator or broaden this runtime profile.

An inference unit is one dispatched backend attempt, including its stream and
terminal outcome. Tokens/chunks do not create additional inference units. A retry
creates a new attempt even if its logical task and content are identical. An
ambiguous timeout remains a dispatched attempt; it is not proven nonexecution.
Each named synthetic tool effect is a separate unit and has separate totals.
`review_wait` includes execution duration. A stream that outlasts that deadline
without a sealed terminal becomes uncovered even if checkpoints occur. This
version detects that condition; it does not claim incremental review of an
unbounded response. Such review would need a separately versioned chunk model.

| Dimension | Permitted conclusion | Not established |
|---|---|---|
| Coverage | Which witnessed units have valid completed review or another explicit state | Behavioral safety, authorization or provider-side completion |
| Reconciliation | Whether supplied source obligations and streams reconcile | That all actual activity reached any source |
| Census assurance | `unknown` for every fixture in this version | Comprehensive or non-bypassable runtime coverage |
| Inhibition | `not_implemented` | That reporting a gap stops an action |

## 2. Trust, identity and time

The manifest names distinct source IDs for `controller`, `witness`, `monitor` and
`human_authority`. The controller records enrollment/admission and lifecycle
intent; the witness records effect boundaries; the monitor evaluates context;
the human source issues exemptions. The reconciler consumes those sources.
Separate fixture authorship is required. A string naming a source proves no
authentication: synthetic fixtures assume role authenticity explicitly. A runtime
profile needs independently enforced source authentication and custody.

Unit key: `(run_id, attempt_id)`. An attempt's `epoch_id`, `action`, parent retry
and policy binding cannot change. IDs are case-sensitive ASCII tokens matching
`[A-Za-z0-9._-]{1,64}`. Attempts are unique across a run, including restarts.
Epochs link through a witness-observed predecessor; they never reset deadlines.
Each source has one sequence across the entire run, starting at 1. New epochs do
not reset it. Source replacement/rekeying during a run is outside v0.1.

Time is a shared synthetic integer clock starting at enrollment tick 0. It is
not wall time. Every input is delivered in a harness envelope
`{visible_at, record, context_views}`; `visible_at` is assigned by the delivery schedule, not the
record producer. Reconciliation at `as_of=t` sees only envelopes with
`visible_at <= t`. Records must have `0 <= occurred_at <= visible_at`.
Evaluation completion, production and delivery remain distinct timestamps.
Runtime clock authority, skew and timestamp attestation are deferred decisions.

`context_views` is a synthetic fixture sidecar, not a sixth governance record.
It maps attempt IDs to the exact context independently supplied to that producer:
input objects for witness dispatches, review objects for witness terminals and
evaluated monitor members (section 8). Other records use `{}`. A required missing
view gives `CONTEXT_UNAVAILABLE`; a mismatching digest gives `CONTEXT_MISMATCH`.
The reconciler recomputes commitments from these fabricated bytes. It cannot
prove an evaluator actually reasoned over them or that the fixture author is
independent. Sidecars arrive with their record, are included in input identity,
and cannot be fetched from a live provider. Later context delivery is outside v0.1.

All deliveries at a tick are processed before deadlines at that tick. Each tick
runs four steps in order: (1) admit the envelopes visible at that tick and extend
source prefixes; (2) resolve dependencies among usable records; (3) create that
tick's timer, count and final cuts, then match usable checkpoint receipts; (4)
assess obligations due at that tick. Delivery order inside a tick never matters.
Evidence delivered exactly at a deadline can satisfy it. An unmet obligation becomes due
when `as_of >= deadline`. Backfill ages an obligation from its occurrence tick,
not delivery. No heartbeat, new attempt, compaction or restart refreshes it.

## 3. Five record families

These are closed conceptual wire shapes for a future test-only implementation,
not additions to the ordinary JSONL ledger. Unknown fields, versions, enum values,
duplicate JSON keys, floats, invalid types and impossible timestamps are invalid.
Required fields cannot be omitted; nullable fields are written explicitly as null.
Lists retain order unless a rule specifies sorted unique membership.

There is a separate ingestion boundary: malformed JSON, duplicate keys, floats or
values outside the ASCII canonicalization domain reject the entire dataset before
reconciliation. An invalid manifest also rejects the dataset. The validation result is exactly
`{status: "input_error", code: "INVALID_RECORD", input_index: <integer>, raw_sha256: <64-hex>}`,
where input_index is -1 for the manifest and otherwise the zero-based envelope
index; the digest covers the exact rejected manifest/envelope bytes. No coverage report or
partial success is returned. If several inputs fail, report the lowest index; the
reordering invariance in section 4 applies only to datasets that pass this boundary.
This validation result is not a governance record.
Canonicalizable but wrong-shaped/typed records remain inspectable report inputs;
they are structurally invalid and block an identifiable source prefix. Thus an
invalid input is never silently normalized merely to obtain an input-set digest.

### 3.1 Scope manifest

One immutable manifest is available at tick 0. Its exact fields are:

| Field | Type / rule |
|---|---|
| `contract_version`, `run_id`, `policy_id` | `mci/0.1`, token, token |
| `profile` | `synthetic_inference` or `synthetic_tool` |
| `protocol`, `model` | Fixed synthetic identifiers, never discovered dynamically |
| `sources` | Exactly four role-to-source-ID bindings; all distinct |
| `eligible_actions` | Sorted unique action tokens; primary profile has `inference.local.generate` only |
| `excluded_surfaces`, `known_bypasses` | Sorted unique descriptive tokens; empty is an explicit declaration, not assurance |
| `review_wait`, `admission_wait`, `terminal_wait` | Positive integer ticks from dispatch, admission, dispatch respectively |
| `checkpoint_interval`, `checkpoint_count`, `checkpoint_grace` | Positive ticks, positive unit count, positive ticks |
| `privacy_profile` | `synthetic_public_context_only` |
| `census_assurance`, `inhibition` | Literal `unknown`, `not_implemented` |

`policy_digest` is the commitment to this complete manifest (section 8). Policy
changes during the run are invalid; a new approved manifest requires a new run.
The synthetic default values are 3, 3, 5, 10, 3 and 2 for the six timing/count
fields above. These are fixture parameters, not production recommendations.

### 3.2 Common input envelope and observations

Observation, receipt and exemption records share these fields:
`contract_version`, `kind`, `record_id`, `run_id`, `policy_digest`, `source_id`,
`sequence`, `occurred_at`, `payload`. `sequence` is a positive integer; all IDs
are tokens. The fixture specification gives aliases, never alternate wire fields.
`record_id` is unique per run. The external delivery envelope is not part of the
producer's canonical record. Exact retransmissions keep all producer fields.

`kind=observation` has `payload.type` and only the fields of the matching row:

| Type / permitted source | Required payload beyond `type` |
|---|---|
| `epoch_open` / witness | `epoch_id`, nullable `parent_epoch_id`, nullable `prior_context_digest`, nullable `new_context_digest`; initial epoch has all three nullable fields null |
| `admit` / controller | `attempt_id`, `epoch_id`, `action`, nullable `retry_of` |
| `dispatch` / witness | `attempt_id`, `epoch_id`, `action`, nullable `retry_of`, `input_digest` |
| `terminal` / witness | `attempt_id`, `epoch_id`, `input_digest`, `review_digest`, `outcome`, `output_state` |
| `cancel` or `plan_only` / controller | `attempt_id`, `epoch_id` |
| `not_dispatched` / witness | `attempt_id`, `epoch_id`, `cause` (`cancel` or `plan_only`) |
| `run_close` / controller | Empty beyond `type`; starts final reconciliation, not proof of completion |
| `watermark` / any named source | `through_sequence`, `through_tick` |

`terminal.outcome` is `completed`, `error`, `timeout` or `unknown`;
`output_state` is `complete`, `partial` or `none`. Timeout/unknown never asserts
provider cancellation. A terminal seals exactly the available observable context;
it may faithfully record partial output and an uncertain execution outcome.
`completed` requires `complete`; `timeout`/`unknown` cannot claim `complete`.

Every dispatch requires a known epoch, eligible action and unique attempt identity.
Witness and controller attempt descriptors must agree when both exist. A missing
admission does not invalidate an otherwise valid witness or erase the execution.
It creates a boundary violation. Initial `epoch_open` occurs at tick 0. A child
epoch requires an earlier known parent and non-null context commitments. It may
have outstanding parent obligations; they remain in the same run.

Epoch lineage is linear in this profile and ordered by witness sequence, not
occurrence tick. `prior_context_digest` must match the input of the parent's
last dispatch sequenced before the opening; `new_context_digest` must match the
child's first dispatch. Child opening ends new dispatches in the parent, but
parent terminals/reviews remain admissible. These links establish byte identity,
not semantic equivalence of a summary.

An opening is accepted only if it is the initial opening (the witness's first
`epoch_open`, at tick 0, all three nullable fields null) or opens a new epoch ID
whose parent is the latest accepted epoch, has at least one dispatch, and is
bound by non-null commitments with a matching `prior_context_digest`. In
particular, an empty parent cannot be compacted. Any other opening is rejected:
it consumes its position, opens and ends nothing, and records persistent
`EPOCH_CONTINUITY_FAILURE`; later records naming its epoch follow the
unopened-epoch rule (section 4). A dispatch naming an epoch after a child of
that epoch has opened is accepted as a disputed unit with persistent
`EPOCH_CONTINUITY_FAILURE`; it receives no review credit, and earlier valid
evidence is unaffected. A child's first dispatch that contradicts
`new_context_digest` is a contradictory binding: it disputes that child's units
and persists `EPOCH_CONTINUITY_FAILURE`. Before that first dispatch, the binding
is pending rather than failed.

Only an exact retransmission of the original producer record is idempotent.
A fresh record ID/sequence cannot repeat `admit`, `dispatch`, `terminal` or
`not_dispatched` for an attempt, even with equal payload: mark
`ATTEMPT_IDENTITY_CONFLICT`. This prevents two sends disguised with one attempt
ID from being treated as one clean execution. Multiplicity then remains unknown.

### 3.3 Monitor receipts

`kind=receipt` requires the monitor source. `payload.type` chooses one closed form:

| Type | Fields |
|---|---|
| `review` | `stage` (`received` or `evaluated`), nullable `completed_at`, `members` |
| `checkpoint` | `checkpoint_id`, `cut_tick`, `completed_at`, `members` |

A review member contains `attempt_id`, `epoch_id`, `input_digest`, `review_digest`
and `verdict`. Members are nonempty, unique and sorted by attempt ID. For
`received`, `completed_at`, each `review_digest` and each `verdict` must be null;
queue acceptance never counts as review. For `evaluated`, all are non-null;
`verdict` is `clear`, `flagged` or `indeterminate`, and
`terminal.occurred_at <= completed_at <= record.occurred_at <= visible_at`.
Any of these verdicts can count as completed review; none is action permission.

Each evaluated member must match both witness commitments and exact identity.
The monitor must independently calculate them from context it actually received.
Input-only inspection cannot mark a whole streaming attempt reviewed. A known
dispatch without a terminal is `CONTEXT_UNSEALED`; retain the receipt as pending
dependency, not successful review. A receipt for an unknown attempt is orphaned;
it does not create an execution. It may resolve when corroborating evidence arrives.

Review batches are atomic: a wrong identity, commitment or unresolved member
prevents the whole batch counting until every member validates. Report every
affected member. Separate valid receipts can still review those events. Two
different valid reviews may disagree behaviorally; count each unit once, retain
both verdicts, and flag behavioral disagreement for human assessment. Conflicting
source sequences/record IDs are integrity failures, not competing opinions.

A checkpoint receipt has sorted unique attempt IDs as `members` (possibly empty),
matching the recomputed cumulative membership exactly. Its `checkpoint_id` must
be `cp-` followed by its decimal `cut_tick`; otherwise it is `INVALID_RECORD`. A
receipt naming a cut that does not exist once that tick's cuts are created
(section 2, step 3) is `ORPHAN_RECEIPT`: it creates no checkpoint and grants no
coverage. Cuts are created only at their own tick, so it can never resolve.
It records completed checkpoint work, not individual evaluation. Individual reviews/exemptions and source watermarks
must also satisfy section 6. `cut_tick <= completed_at <= occurred_at <= visible_at`.

### 3.4 Exemptions

`kind=exemption` requires `human_authority`. Its payload is either:

- `type=grant`: `exemption_id`, sorted unique `attempt_ids`, `action`,
  `valid_from`, `valid_until`, `reason`, `consequential_action_policy`.
- `type=revoke`: `exemption_id`.

Grants are prospective, exact-attempt and single-action. `reason` is a closed token
`fixture_exception`; it must not carry free text. The only consequential policy in
v0.1 is `no_added_authority`. Wildcards and retrospective repair are forbidden.
Require `occurred_at <= visible_at <= valid_from < valid_until`. The interval
is half-open: `[valid_from, valid_until)`. Eligibility is tested at dispatch tick.
The grant's first usable tick after source-prefix validation must precede or
equal dispatch. A human-source gap/blocked prefix at dispatch suspends exemption
eligibility for that dispatch; later backfill cannot retroactively waive it.
A structurally valid human revoke restricts its named grant from delivery, even
if buffered; withholding an earlier sequence cannot defer that restriction.
Revocation at the dispatch tick wins. Later expiry/revocation
does not erase an exemption valid for an already dispatched unit, nor does it
authorize later attempts. Duplicate grants cannot extend validity: the first
accepted grant for an `exemption_id` (human sequence order) is the only one, and
a later fresh grant reusing that ID is `EXEMPTION_INVALID` and leaves the
original unchanged. An exact retransmission stays idempotent.

Exemptions waive only that unit's review obligation. They waive neither independent
witnessing nor authorization, terminal accounting, checkpoint delivery or incident
handling. Revocation/reissue history remains inspectable. An exemption cannot
launder an earlier missed deadline. A reviewed exempt event counts as reviewed;
otherwise a valid grant yields `exempt_unreviewed`.

### 3.5 Reconciliation report

The output family has exactly these top-level fields:
`contract_version`, `run_id`, `policy_digest`, `as_of`, `input_set_digest`,
`window_state`, `source_states`, `unit_states`, `admission_states`,
`checkpoint_states`, `counts_by_action`, `diagnostics`, `historical_violations`,
`census_assurance`, `inhibition`.

- `source_states`: per source, contiguous accepted prefix, highest sequence seen,
  gaps, disputed IDs, latest accepted watermark and state
  (`contiguous`, `incomplete`, `conflicted`).
- `unit_states`: per attempt, immutable identity, observed tick, deadlines,
  partition (`reviewed`, `exempt_unreviewed`, `pending_within_deadline`,
  `uncovered`), current evidence IDs, outcome, and `disputed` boolean.
- `admission_states`: `waiting`, `dispatched`, `not_dispatched` or `unresolved`.
- `checkpoint_states`: cut, due/deadline ticks, exact membership and state
  (`pending`, `complete`, `overdue`, `invalidated`), with historical violations retained.
- `counts_by_action`: `observed`, `reviewed`, `exempt_unreviewed`,
  `pending_within_deadline`, `uncovered`, `coverage_ratio`, `ratio_status`.
  Exactly one row per manifest eligible action, including all-zero rows; no
  other action receives a row.
- Diagnostics/violations are object rows with `code`, `subject_id`, `first_due_tick`;
  the latter is null for non-deadline findings. No raw exception messages.

The exact nested row fields follow. `id-list` means a sorted unique array of
tokens; `tick?` means integer or null; `digest?` means lowercase 64-hex or null.
All fields in a row are required. An absent fact is null, not an omitted key or
a fabricated successful state.

| Array | Exact row fields |
|---|---|
| `source_states` | `source_id`, `state`, `accepted_prefix` (integer >=0), `highest_seen` (integer >=0), `missing_sequences` (sorted positive integers), `disputed_record_ids` (id-list), `watermark_sequence` (integer or null), `watermark_tick` (tick?) |
| `unit_states` | `attempt_id`, `epoch_id`, `action`, `retry_of` (token or null), `dispatch_tick` (integer), `review_deadline` (integer), `terminal_deadline` (integer), `partition`, `disputed` (boolean), `dispatch_record_ids` (id-list), `terminal_record_id` (token or null), `review_record_ids` (id-list), `exemption_ids` (id-list), `input_digest` (digest?), `review_digest` (digest?), `outcome` (terminal enum or null), `output_state` (terminal enum or null), `verdicts` (sorted unique verdict strings) |
| `admission_states` | `attempt_id`, `epoch_id`, `admission_record_ids` (id-list), `admission_tick`, `deadline` (integers), `state`, `resolution_record_ids` (id-list) |
| `checkpoint_states` | `checkpoint_id`, `previous_cut`, `cut_tick`, `deadline` (integers), `members` (id-list), `state`, `receipt_record_ids` (id-list), `completed_at` (tick?) |
| `counts_by_action` | `action`, `observed`, `reviewed`, `exempt_unreviewed`, `pending_within_deadline`, `uncovered` (integers >=0), `coverage_ratio` (two nonnegative integers or null), `ratio_status` |
| `diagnostics`, `historical_violations` | `code`, `subject_id` (token), `first_due_tick` (tick?) |

`accepted_prefix` ends immediately before a structural failure/dispute. Missing
sequences include only absent positions, not invalid records. A disputed unit
retains its earliest accepted descriptor (or earliest delivered variant, with
source-sequence, record-ID, then canonical record-plus-sidecar byte tie breaks);
it is a disputed bookkeeping label, not a
selected true version. Disputed commitments/outcome are null, and no receipt is
credited to it. Admission rows exist only for supplied controller admits;
unadmitted dispatches appear in unit rows/findings instead. Checkpoint `completed_at`
is the first tick all completion conditions were usable, not the producer's
timestamp. `as_of` is a nonnegative integer. Source states are `incomplete` for
a blocked prefix or hole, `conflicted` for quarantine, otherwise `contiguous`.

Evidence fields show only what is currently credited, from accepted records
outside quarantine: `terminal_record_id`, `review_record_ids` and `verdicts`
come from the credited terminal and evaluated reviews; `exemption_ids` lists
grants applicable at dispatch; checkpoint `receipt_record_ids` lists receipts
meeting completion condition 1; and admission `resolution_record_ids` lists the
matching dispatch, or else the controller cancel/plan record and its witness
`not_dispatched`. A matching dispatch, disputed or not, gives state `dispatched`.
`dispatch_record_ids` and `admission_record_ids` list every syntactically valid
dispatch or admit placing the attempt in its row, including conflicting or
quarantined variants. Uncredited evidence appears only as a finding subject, and
verdict codes come only from credited reviews. `disputed_record_ids` lists every
record ID in that source's quarantined suffix, including conflicting variants.

All keyed output arrays are sorted by their identifier. Findings sort by
`(code, subject_id, first_due_tick)`, lexicographically for strings and with null
before integer ticks. Duplicate identical finding rows collapse to one.
`input_set_digest` commits to the manifest and canonical, sorted delivered
envelopes, with exact retransmissions collapsed to the earliest delivery.
The hashed object is exactly `{manifest: <manifest>, delivered: <envelopes>}`.
Sort envelopes by `(visible_at, source_id, sequence, record_id, canonical_bytes)`;
missing/invalid sort fields use empty string for token fields and -1 for sequence.
`canonical_bytes` of the entire envelope breaks remaining ties. Only identical
record **and sidecar** pairs collapse; changing a bound sidecar under the same
record identity is `SOURCE_CONFLICT`. `as_of` selects the delivered set but is
separately recorded, so two report ticks with identical inputs can share a digest.
Do not hash a report into its own input identity. Report generation is a pure
projection of these inputs and `as_of`; prior report files are not required.

## 4. Stream integrity and historical reconstruction

Validate each source's contiguous prefix starting at sequence 1. Out-of-order
suffix records are buffered until the hole is filled; the maximum number seen
is not a watermark. Structurally invalid records (shape, type, role, version,
policy or impossible envelope time) block that prefix. Semantic binding failures
such as mismatched context, orphan receipts or inapplicable exemptions consume
their source position but cannot satisfy the failed obligation. Their evidence
and diagnostics remain visible. Exact retransmission is
idempotent. Reuse of a source sequence or record ID with different canonical
producer bytes is `SOURCE_CONFLICT`, even if its claimed outcome looks favorable.

A watermark at sequence `s` must declare `through_sequence=s-1` and a
nondecreasing `through_tick <= occurred_at`. It promises the source will emit no
later non-watermark record whose occurrence is at or before `through_tick`.
Its prefix must be complete. A later contradictory event creates
`WATERMARK_CONTRADICTION`. A watermark is a source assertion under the synthetic
trust model, not proof that no external event occurred. Watermarks may advance
with no effects, which is essential for detecting idle-source disappearance.

On conflict, mark the source conflicted and quarantine its claims from the first
disputed position onward. Retain all previously established witnessed units as a
conservative candidate set; add distinct syntactically valid witness attempt
IDs in conflicting variants and the quarantined suffix as disputed units. Such units remain
`uncovered` and ratios are null. Do not choose a favorable branch, erase units,
or claim their multiplicity is certain. The candidate count is not a numerical
lower or upper bound on real executions; its ratio remains suppressed. Downstream reviews relying on quarantined
terminals cannot count. Healthy sources remain inspectable. Source conflict is
not auto-repaired in this version; human disposition requires a new profile/run.
A unit whose own dispatch position is contested is disputed even if it was
established earlier. Every unit in `O`, disputed or not, keeps the per-unit
obligations of section 5 (dispatch admission, terminal and review deadlines),
computed from its retained descriptor's dispatch occurrence. Once its dispute
is discovered, its terminal and review obligations cannot be satisfied, and it
gains no credit. Findings about a disputed unit are conservative candidate
findings; they establish neither its existence nor its multiplicity. They stay
identifiable through the subject unit's `unit_states.disputed`; consumers must
not present them as confirmed execution.

Apply the same quarantine rule to a watermark contradiction, starting at the
contradictory watermark. `ATTEMPT_IDENTITY_CONFLICT` disputes that attempt and
its dependent evidence, while unrelated units/source positions remain usable.
An invalid observation/context binding cannot erase an earlier valid dispatch:
retain the unit, invalidate the dependent terminal/review and expose the defect.
A structurally valid eligible witness dispatch remains observed even if its
context bytes violate profile/context binding. Its existence cannot disappear
because its model/context is wrong; it cannot receive review credit until valid
required bindings exist. This is distinct from disputed event identity.
Epoch-binding conflicts dispute affected child units; missing epoch evidence
buffers them and prevents complete accounting. Specifically, a witness dispatch
or terminal naming an epoch not opened earlier in the witness's accepted prefix
blocks that prefix at its position (`incomplete`); because an opening can only
precede it in the same sequence, nothing later repairs that block in v0.1. Controller
admits are not epoch-dependent and remain accepted; receipts naming a blocked
attempt are orphaned. An unknown-source input is retained
as invalid evidence without impersonating or advancing a named source.

First derive all obligations known at `as_of`, including backfilled dispatches.
Compute historical violations by replaying distinct delivery ticks, timer-grid
ticks and those obligation deadlines up to `as_of`. At each tick, run the four
steps of section 2. Reordering a file without changing
delivery ticks must not change results. A record that arrived before a deadline
but was buffered behind a missing prefix was not usable at that deadline.
Late records can resolve current states but cannot erase the historical interval
in which a deadline was missed. This rule avoids using producer timestamps to
backdate apparent compliance. A newly discovered overdue dispatch is evaluated
against what was usable at its original deadline, even if it is reviewed now.
A later-discovered conflict invalidates current evidence from discovery onward;
it does not retroactively invent a missed deadline that was satisfied then.

## 5. Accounting and event lifecycle

Let `O` be distinct eligible witness-dispatched units accepted from healthy
prefixes, augmented by the conservative disputed set above. Admission, monitor
receipts, controller claims and ledger entries cannot independently add to `O`.
Out-of-profile evidence is reported as `OUT_OF_SCOPE_EVENT`; it cannot silently
expand the profile or improve its numerator. Unknown epochs/invalid dispatches
produce invalid-evidence diagnostics and prevent a clean window.

For each nondisputed unit, use this exclusive precedence at the report tick:

1. A valid completed evaluation available and fully corroborated: `reviewed`.
2. Otherwise a valid exemption applicable at dispatch: `exempt_unreviewed`.
3. Otherwise `as_of < dispatch_tick + review_wait`: `pending_within_deadline`.
4. Otherwise: `uncovered`.

For each action separately:

`observed = reviewed + exempt_unreviewed + pending_within_deadline + uncovered`

Coverage ratio is the exact integer pair `[reviewed, observed]`, not a rounded
percentage. It is null with `ratio_status=no_observed_units` when the denominator
is zero, or `ratio_status=integrity_uncertain` when a source gap/blocked prefix,
source conflict, disputed attempt or unresolved epoch prevents reliable accounting.
Integrity uncertainty is run-wide and takes precedence even for zero observed units. An epoch
is unresolved only while witness records are blocked on it or its units are
disputed; a rejected opening with no dependent records, or a child awaiting its
first dispatch, does not by itself suppress the ratio. A semantic
receipt failure alone does not suppress an otherwise known observed-only ratio;
it prevents credit and remains a finding. Otherwise `ratio_status=observed_only`;
the ratio is conditional on observations and must be presented with
`census_assurance=unknown`. Exemptions stay in the denominator. Separate action
totals must not be combined into an inference coverage percentage.

Independent obligations exist even when all of `O` is reviewed:

| Obligation | Deadline / disposition |
|---|---|
| Admission | At admission tick + `admission_wait`, require matching dispatch or a controller cancel/plan outcome paired with witness `not_dispatched`; otherwise `ADMISSION_UNRESOLVED` |
| Dispatch admission | Valid prior/equal admission required; missing/late admission yields `UNADMITTED_DISPATCH` at dispatch and cannot be repaired retrospectively |
| Terminal evidence | At dispatch tick + `terminal_wait`, require a matching witness terminal; otherwise `TERMINAL_MISSING` |
| Review evidence | At dispatch tick + `review_wait`, require review or applicable exemption; otherwise `MISSED_REVIEW_DEADLINE` |
| Outcome consistency | A dispatch conflicting with `not_dispatched` remains counted and yields `CANCEL_DISPATCH_CONFLICT`; cancellation cannot subtract it |
| Epoch continuity | Missing or conflicting predecessor/context linkage yields `EPOCH_CONTINUITY_FAILURE`; earlier obligations persist |

Admission occurrence must precede/equal dispatch. For the synthetic admission
claim to be considered available before dispatch, its first usable tick (after
prefix validation) must also precede/equal dispatch occurrence; mere delivery
into a buffered suffix is insufficient. A backdated admission cannot repair
authority. The
same tick is permitted because deliveries are processed before due assessment.
This is a monitoring boundary rule, not TC's existing authorization mechanism.

Plan/cancel pairs describe no dispatched unit only while uncontested; absence of
a dispatch record alone is insufficient. A waiting admission before its deadline
is legitimate queued work. Terminal outcome and behavioral verdict remain separate
from review coverage. A timed-out attempt can be reviewed while its provider-side
result is unknown. Both `timeout` and `unknown` produce
`EXECUTION_OUTCOME_UNKNOWN` even after review. A reviewed unadmitted attempt remains a boundary violation.

## 6. Independent checkpoints and closure

Checkpoint cuts are derived from the independent synthetic clock and witness
availability, not agent turn completion. Three triggers apply:

- Fixed timer grid: `checkpoint_interval`, twice that interval, and so on.
- Count: every `checkpoint_count` distinct units first becoming usable from the
  witness creates a cut at that usability tick. Count new units in attempt-ID
  order within a tick; a burst creates at most one cut that tick. Backfill can
  trigger a present checkpoint, never postpone original per-unit deadlines. A
  unit that is disputed after step 2 of the tick it first becomes usable never
  advances this count; a unit that advanced it keeps that contribution if it is
  disputed later. Timer cuts do not depend on the count.
- Final: the first usable controller `run_close` creates a cut at its usability
  tick. A further fresh run-close record consumes its source position, creates no
  cut and is retained as `INVALID_RECORD`; an exact retransmission stays idempotent.

IDs are stable `cp-<cut_tick>`, such as `cp-10`. Simultaneous triggers create one
cut; count cuts do not reset the timer grid. `previous_cut` records the prior
created cut (0 initially) but does not scope membership. Every checkpoint covers
the cumulative set of witnessed units with dispatch occurrence at or before its
cut. Overlap does not inflate event totals. Each deadline is `cut + checkpoint_grace`.
With the fixture defaults (`checkpoint_grace` 2 < `review_wait` 3), a unit
dispatched at a cut must be reviewed or exempt by `cut + 2` for that checkpoint
to complete, although its own review deadline is unchanged; a timely per-unit
review can therefore coexist with `CHECKPOINT_MISSED`.
Timer cuts occur with no units. After close becomes usable, no later ordinary
cuts are generated. A dispatch occurring later than that close tick is
`POST_CLOSE_DISPATCH`, remains counted, and prevents clean closure.

Created cuts/counter progress are preserved if later evidence becomes disputed.
Delayed witness evidence can enlarge earlier cumulative membership and invalidate
an old acknowledgment; it never renames that checkpoint or erases its history.
Recompute membership against all known evidence and retain missed obligations.

A checkpoint is complete only when all are true:

1. A valid checkpoint receipt names exactly the cumulative witnessed membership.
2. Every member is reviewed or validly exempt, without changing its own deadline.
3. All four sources have accepted contiguous watermarks through the cut tick.
4. No unresolved source/identity/epoch integrity problem or invalid context in
   the evidence being credited affects that cumulative membership. An older
   rejected receipt remains a finding but does not invalidate a separate valid one.

Before its deadline it is pending; at/after deadline it is overdue if incomplete,
with `CHECKPOINT_MISSED`. A later complete checkpoint retains that violation.
If a previously complete checkpoint is invalidated by later conflicting evidence,
its state is `invalidated` with `CHECKPOINT_INVALIDATED`; retain the former
completion tick as history in the input projection, but current `completed_at`
is null. Do not invent a deadline miss that was satisfied with usable evidence
then. Newly discovered per-unit obligations still receive retrospective deadline
assessment. A distinct valid checkpoint receipt plus repaired dependencies can
restore completion, except an unrepairable source conflict in v0.1.
An empty checkpoint still requires its receipt and all four watermarks. A queue
receipt/heartbeat cannot stand in for this completed checkpoint. Checkpoints
certify a bounded source scan, not census completeness or execution permission.

`window_state` is `open` until `run_close` and the final checkpoint requirements
are satisfied. Once they are, it is `closed_reconciled` only if both `diagnostics`
and `historical_violations` are empty; otherwise it is `closed_with_findings`.
That covers historical violations, orphan/invalid evidence, unresolved admissions,
unknown terminal outcomes, flagged/indeterminate verdicts, verdict disagreement,
out-of-scope disclosures and coverage gaps. Exempt-unreviewed units carry no code
and do not by themselves prevent `closed_reconciled`; they remain unmonitored and
the counts must still show them. A still-waiting admission
or any unit lacking a valid terminal keeps the window open until its deadline;
thereafter an explicit unresolved/missing-terminal finding can close only as
`closed_with_findings` if the final checkpoint conditions are otherwise satisfied.
Thus an exempt unfinished attempt cannot become a clean closed run merely by
waiving review. Source holes/conflicts or an
incomplete final checkpoint keep it `open`; never print “complete” merely because
the observed-only ratio is one. Even `closed_reconciled` retains unknown census
assurance and grants no safety or execution conclusion.

## 7. Findings vocabulary and response boundary

The following closed codes are the v0.1 vocabulary. Report the corresponding
diagnostic while currently applicable; preserve deadline/boundary/integrity codes
in `historical_violations` once established. Resolved dependency diagnostics must not remain current. Specifically, orphan
and unsealed receipt findings clear once those dependencies validate; a queued
receipt's `RECEIPT_NOT_EVALUATED` clears when valid evaluations cover all its
members. Filled sequence gaps and successfully resolved admission/terminal/review
obligations lose their current diagnostics, retaining any historical violations. Invalid evidence is retained for inspection, never silently
dropped to make a window clean. A persisted code appears in both lists while its
condition is currently applicable (for example, an uncovered unit's
`MISSED_REVIEW_DEADLINE` or an unrepairable `UNADMITTED_DISPATCH`), and only in
`historical_violations` after it is resolved.

| Class | Codes |
|---|---|
| Input/integrity | `INVALID_RECORD`, `POLICY_MISMATCH`, `SOURCE_ROLE_MISMATCH`, `SOURCE_SEQUENCE_GAP`, `SOURCE_CONFLICT`, `WATERMARK_CONTRADICTION`, `ATTEMPT_IDENTITY_CONFLICT` |
| Context/receipts | `ORPHAN_RECEIPT`, `CONTEXT_UNAVAILABLE`, `CONTEXT_UNSEALED`, `CONTEXT_MISMATCH`, `RECEIPT_NOT_EVALUATED`, `RECEIPT_TIME_INVALID`, `REVIEW_VERDICT_DISAGREEMENT`, `REVIEW_FLAGGED`, `REVIEW_INDETERMINATE` |
| Lifecycle/boundary | `ADMISSION_UNRESOLVED`, `UNADMITTED_DISPATCH`, `TERMINAL_MISSING`, `EXECUTION_OUTCOME_UNKNOWN`, `CANCEL_DISPATCH_CONFLICT`, `EPOCH_CONTINUITY_FAILURE`, `OUT_OF_SCOPE_EVENT`, `POST_CLOSE_DISPATCH` |
| Exemption | `EXEMPTION_INVALID`, `EXEMPTION_NOT_APPLICABLE` |
| Timing/checkpoint | `MISSED_REVIEW_DEADLINE`, `CHECKPOINT_MEMBERSHIP_MISMATCH`, `CHECKPOINT_MISSED`, `CHECKPOINT_INVALIDATED` |

`SOURCE_SEQUENCE_GAP`, orphan/unsealed/not-evaluated receipts and inapplicable
exemptions are current diagnostics rather than permanent violations by themselves.
Missed deadlines caused by them remain historical. `REVIEW_FLAGGED`,
`REVIEW_INDETERMINATE` and `EXECUTION_OUTCOME_UNKNOWN` require attention but do not
invalidate truthful review. Impossible record shape/time is `INVALID_RECORD`;
receipt-specific completion ordering uses `RECEIPT_TIME_INVALID`. Assign multiple
codes only for distinct failed rules; do not duplicate a count per code.

Finding subjects are deterministic: source sequence/conflict/watermark codes use
`source_id`; lifecycle, attempt identity, behavioral verdict and exemption-not-
applicable codes use `attempt_id`; epoch continuity uses the `epoch_id` named by
the offending record (a dispatch's or terminal's epoch, an opening's own); checkpoint
codes use `checkpoint_id`; exemption-invalid uses `exemption_id`. All remaining
input/context/receipt codes use the offending `record_id`. If that ID is absent
or invalid, use the 64-hex SHA-256 of its canonical envelope as the subject.
Batch failures identify the batch record; its members expose every affected unit.

Persist exactly these codes in `historical_violations` once established:
`INVALID_RECORD`, `POLICY_MISMATCH`, `SOURCE_ROLE_MISMATCH`, `SOURCE_CONFLICT`,
`WATERMARK_CONTRADICTION`, `ATTEMPT_IDENTITY_CONFLICT`, `CONTEXT_UNAVAILABLE`,
`CONTEXT_MISMATCH`, `RECEIPT_TIME_INVALID`, `EXEMPTION_INVALID`,
`ADMISSION_UNRESOLVED`, `UNADMITTED_DISPATCH`, `TERMINAL_MISSING`,
`CANCEL_DISPATCH_CONFLICT`, `POST_CLOSE_DISPATCH`, `MISSED_REVIEW_DEADLINE`,
`CHECKPOINT_MEMBERSHIP_MISMATCH`, `CHECKPOINT_MISSED`, `CHECKPOINT_INVALIDATED`.
A contradictory (rather than missing) epoch binding also persists
`EPOCH_CONTINUITY_FAILURE`. Other codes are current findings, not proof that a
rule was violated. Out-of-scope activity is a disclosure, not automatically an
unauthorized action. Only the four deadline codes use a non-null due tick:
`ADMISSION_UNRESOLVED`, `TERMINAL_MISSING`, `MISSED_REVIEW_DEADLINE`,
`CHECKPOINT_MISSED`; all other first_due_tick values are null.

v0.1 emits findings; it performs no stop, resume, escalation or external action.
A runtime design must assign a human incident owner, acknowledgment deadline,
isolated evidence custody and a recovery procedure before consequential use.
A future gate may refuse work or add constraints under separate authority; a
receipt or exemption may never remove an existing human authorization requirement.

## 8. Context, canonical identity and privacy

Synthetic canonicalization is intentionally narrow: ASCII string values only;
objects with ASCII keys sorted lexicographically; compact JSON separators `,`
and `:`; ordinary JSON escaping of quotes, backslashes and control characters;
no escaped printable ASCII; integers in decimal without leading zeroes; no floats;
arrays preserve order; UTF-8 bytes with no BOM or trailing newline. This is a
specified fixture encoding, not a claim of general cross-language JSON equivalence.

Commitments use lowercase SHA-256 hex over a domain prefix and canonical bytes:
`mci/0.1/manifest\n`, `mci/0.1/input\n`, `mci/0.1/review\n`, or
`mci/0.1/inputs\n`. Here `\n` means one LF byte. Policy digest uses the first;
input and review digests use the next two; report input-set identity uses the last.
Commitments are not signatures or evidence of independent computation.

An inference input context has exactly `protocol`, `model`, `messages`,
`tool_records`, `parameters`. `messages` is the ordered effective invocation
sequence of `{role, content}`, including TC-added system text. `tool_records`
is an ordered synthetic list (empty in the primary profile); `parameters` is an
explicit synthetic object. The review context is exactly
`{input: <complete input context>, result: {outcome, output_state, output}}`.
`output` is the exact observable string, including a partial stream if applicable.
The separate synthetic tool profile uses exactly
`{protocol, model, action, target_token, before_content, proposed_content}` as
its input: protocol `synthetic-tool`, model `no-model`, action
`tool.synthetic.write`, opaque target token and fabricated ASCII content strings.
Its review object has the same `input`/`result` wrapper and terminal enums.
It models a proposed single-target effect without touching any file. A completed
result's output must equal proposed_content. Its manifest action list contains
only `tool.synthetic.write`; it reports tool totals only, never inference totals.
This is a separate synthetic profile, not a TC runtime capability.

Each context's protocol/model must equal its manifest. The inference profile's
`tool_records` must be empty; the tool profile's action must equal its sole
eligible action. Message roles are `system`, `user`, `assistant` or `tool`, with
ASCII content strings. A terminal's review-object input must reproduce the
dispatch input commitment; its result outcome/output_state must equal the terminal
payload. `output_state=none` requires an empty output string. A terminal cannot
occur before dispatch. A monitor's evaluated view must independently match these
same cross-record bindings. Matching hashes over the wrong profile/result fail
with `CONTEXT_MISMATCH`; agreement between two producers is insufficient.

The witness binds its actual supplied input and observable result; the monitor
independently binds what it inspected. A supplied matching digest without access
to those bytes does not satisfy the design. Hidden provider reasoning/internals
are excluded. A summary is not a substitute for original messages. Compaction
requires both the old and new context identities and preserves old review debt.
The monitor may review faithfully bounded partial/unknown output; that must never
be presented as review of unavailable or future content.

Only fabricated public context is permitted in this specification. Future ordinary
governance records may retain bounded metadata/commitments/receipts, not raw prompts,
completions, credentials, endpoint secrets or private paths. A production profile
must decide canonical bytes, access controls, finite retention/deletion and digest
guessing/linkability defenses before handling real data. Hashes alone do not make
private content safe. Runtime evidence storage and signing/key rotation are outside
this design; existing optional TC signatures do not prove observation completeness.

## 9. Review, dependencies and change control

Review acceptance requires a second reader to derive the fixture partitions,
deadline histories, source states and claim limits without using a future
reconciler's output as the oracle. The fixture document is frozen for this draft:
semantic changes require an explicit version/revision and synchronized expectations.
It is not a claim that a test suite was executed or a human accepted the design.

The present docs-only slice may proceed with the existing baseline. Before later
test-only implementation, select a formal CR with exact paths and check whether
any separately governed monitoring study (including TC-AM-001, which this
repository does not contain) applies or would interfere. Neither that study nor
the open daily-use evidence window is a blanket prerequisite for isolated
synthetic work. Before a runtime pilot,
resolve credential/transport custody, source authenticity, clocks, effective-context
capture, checkpoint scheduling independent of workers, incident ownership and
actual refusal behavior. CR-135 integration is conditional on using its transport;
CR-132 is a separate architecture repair. Neither is required to write these specs.

Keep synthetic evidence outside the historical daily-use study. Disposition of
that window is required before changing its natural-use semantics. Export,
external-evaluator and key-lifecycle work are dependencies only when used. The
DD-012B lifecycle-record discrepancy remains unresolved; no grant is reconstructed.
This contract allocates no CR, changes no operational schemas and authorizes no
code, live monitoring, publication, deployment, merge, release or closeout under
[change management](../change/change_management.md).

## 10. Revision record

- **r0** — frozen handoff draft at the baseline above (file SHA-256
  `3eddaeb45669cfe11f14f14b8d5c67b0bac19590ded6f3db19a7f297d04f7e0e`).
- **r1** — 2026-10-23 agent review revision, synchronized with fixture
  specification r1. It pins rules r0 left open: the lowest failing index for
  multiple ingestion failures; one count row per eligible action; per-unit
  obligations for disputed units, and disputed status for a contested own
  dispatch position; the witness prefix block for a dispatch or terminal in an
  unopened epoch; a duplicate run-close that consumes its position; the
  checkpoint-grace interaction; `closed_reconciled` tied to empty finding lists;
  and when a persisted code also appears in `diagnostics`. r1 changes no frozen
  count tuple. It is agent review output, not human design acceptance.

Still unpinned in r1, to be decided before any implementation treats them as an
oracle: the finding for a checkpoint receipt naming a cut that was never created;
codes for a parent dispatch after its child opens and for opening a child of an
empty parent; a reissued grant reusing an existing `exemption_id`; and whether
units first known only as disputed advance the checkpoint count trigger. No
F01–F33 case depends on these choices.

- **r2** — 2026-10-23, synchronized with fixture specification r2, which adds
  F34–F38 for the new rules without changing any F01–F33 expectation.
  - *Operator-directed:* the five items above (orphaned checkpoint receipt after
    same-tick cuts; disputed parent dispatch after a child opens; rejected
    empty-parent opening; rejected reuse of an `exemption_id`; disputed units and
    the count trigger); disputed-unit findings identifiable through
    `unit_states.disputed`; and reference results pinned to the contract revision
    and file hashes. The TC-AM-001 and evidence-window wording in section 9
    follows the operator's correction.
  - *Agent-proposed determinism supports (for review):* the four-step tick order
    and timer-grid replay ticks; the `cp-<cut_tick>` identifier check; lineage
    ordered by witness sequence; rejection of every other invalid opening, and
    pending (not failed) continuity before a child's first dispatch; the epoch
    finding subject; disputed units satisfying no terminal or review obligation
    after discovery, while their dispatch still resolves an admission; when an
    epoch is unresolved for ratio purposes; and evidence-field projection rules,
    with verdict codes only from credited reviews.

No open semantic item is known after r2. Freezing complete expected reports may
expose more; any found requires a synchronized revision before it is frozen.
