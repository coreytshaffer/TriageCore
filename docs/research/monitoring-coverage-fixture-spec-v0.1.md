# Monitoring Coverage Integrity — Fixture Specification v0.1

Status: **draft specification / unaccepted / no executable fixtures or results**.
Revision: **r2** (2026-10-23, synchronized with contract r2; see section 10).

Repository baseline: `610c13f253ba631d7052727abe3d68845bb09bb5`.
Companion: [Monitoring Coverage Contract v0.1](monitoring-coverage-contract-v0.1.md),
identifier `mci/0.1`. These document cases freeze synthetic expectations for later
implementation and independent review. They change no schema, test, runtime,
ledger, authority gate or evidence window. No case has been executed. Required
outcomes below are design requirements, not observations or acceptance evidence.

## 1. Authorship, clock and frozen data

The harness supplies a fake integer clock and authoritative envelope delivery
ticks. Controller, witness, monitor and human records are authored separately;
the future reconciler must not generate its own oracle or witness stream. Source
authenticity is an explicit synthetic assumption. No real prompt, completion,
credential, private path, endpoint or production evidence is used.

Every case and named variant starts afresh unless its timeline explicitly continues.
The manifest is available at tick 0 with these exact values; field names and
shapes are those in contract section 3, not an alternate schema.

| Manifest field | Frozen value |
| --- | --- |
| `contract_version`, `run_id`, `policy_id` | `mci/0.1`, `run-a`, `policy-a` |
| `profile`, `protocol`, `model` | `synthetic_inference`, `synthetic-local`, `synthetic-model` |
| `sources` | controller=`controller-a`; witness=`witness-a`; monitor=`monitor-a`; human_authority=`human-a` |
| `eligible_actions` | [`inference.local.generate`] |
| `excluded_surfaces` | [`cloud`, `gui`, `library`, `other_cli`, `probe`] |
| `known_bypasses` | [`excluded_capability_routes`] |
| `review_wait`, `admission_wait`, `terminal_wait` | 3, 3, 5 |
| `checkpoint_interval`, `checkpoint_count`, `checkpoint_grace` | 10, 3, 2 |
| `privacy_profile`, `census_assurance`, `inhibition` | `synthetic_public_context_only`, `unknown`, `not_implemented` |

The exact fabricated input object `input-a` is the following canonical byte
string, with no trailing newline. It includes the effective system message.

```json
{"messages":[{"content":"Follow the fixture.","role":"system"},{"content":"Say pong.","role":"user"}],"model":"synthetic-model","parameters":{"max_output_tokens":8},"protocol":"synthetic-local","tool_records":[]}
```

`review-a` is the canonical object with exactly `input` equal to `input-a` and
`result` equal to `{"outcome":"completed","output":"pong","output_state":"complete"}`.
Aliases `P`, `I_A`, `C_A` mean the lowercase SHA-256 commitments to the manifest,
`input-a` and `review-a` using their respective contract section 8 domains. They
are explanatory aliases for actual digests, never literal alternate wire values.
The witness and monitor receive separately supplied copies of these exact bytes.
Matching aliases do not replace the requirement to calculate each commitment.

Additional exact contexts are used only where named:

| Alias | Definition before canonical encoding |
| --- | --- |
| `I_B`, `C_B` | Same bytes as `I_A`, `C_A`; these aliases emphasize independent attempt identity, not different hashes. |
| `I_TRUNC`, `C_TRUNC` | Remove the system message from `input-a`; keep the same completed `result`. |
| `I_SUM`, `C_SUM` | Replace the two messages with one `{"content":"Summary of earlier fixture.","role":"system"}` message; keep all other input fields and the completed `result`. |
| `C_TIMEOUT` | Keep `input-a`; use exactly `{"outcome":"timeout","output":"po","output_state":"partial"}` as result. |
| `P_OTHER` | Manifest commitment with only `policy_id` changed to `policy-b`. |
| `I_WRONG`, `C_WRONG` | Replace only `input-a.model` with `synthetic-other`; keep the completed `result`. |
| `I_TOOL`, `C_TOOL` | Input is exactly `{"action":"tool.synthetic.write","before_content":"old","model":"no-model","proposed_content":"new","protocol":"synthetic-tool","target_token":"fixture-target-a"}`; review result is `{"outcome":"completed","output":"new","output_state":"complete"}`. |

Table objects denote exact string keys/values and are encoded using the companion
canonicalization, including sorted keys. They are public fixture data only.

## 2. Timeline notation and common expansion

`record@t` means both occurrence and delivery at tick `t`; a review's completion
is also `t` unless overridden. `as_of=t` processes all delivery envelopes at `t`
before assessing deadlines. Different delivery order within the same tick cannot
change the report. Each input carries `mci/0.1`, `run-a`, `P`, the named source,
its exact payload, and a unique record ID. Source sequences begin at 1 across the
whole run, not each epoch. Merge baseline and additions by occurrence tick;
baseline records precede added same-tick records unless an explicit order says
otherwise. Then use listed order, followed by attempt-ID order. Record IDs are the
source ID plus `-` plus that sequence (for example, `witness-a-1`). Retransmission
preserves these producer bytes. Explicit sequence/order overrides take precedence.

Each envelope also carries `context_views`: for `D(a)`, `{attempt-a: input-a}`;
for `T(a)` and evaluated `V(a)`, `{attempt-a: review-a}`. Added attempts use their
exact named context with their own attempt-ID keys. Batches contain one view per
member. These denote maps with exact string keys; producers receive independent
copies and recompute their commitments. All other records carry `{}`. Views are
delivered with their record; there is no implicit later context fetch or repair.

The common baseline contains **only** these records, with no receipt, exemption,
watermark, close, heartbeat or hidden auto-completion:

| Shorthand | Source and exact payload meaning |
| --- | --- |
| `open@0` | Witness `epoch_open`, `epoch-a`; parent/prior/new context fields all null. Witness sequence 1. |
| `A(a)@0` | Controller `admit`, `attempt-a`, `epoch-a`, `inference.local.generate`, `retry_of=null`. |
| `D(a)@1` | Witness `dispatch`, same attempt descriptor, `input_digest=I_A`. Witness sequence 2. |
| `T(a)@2` | Witness `terminal`, `attempt-a`, `epoch-a`, `I_A`, `C_A`, outcome `completed`, output state `complete`. Witness sequence 3. |

`V(a)@t` adds a monitor `review`, stage `evaluated`, completed at `t`, with one
member `(attempt-a, epoch-a, I_A, C_A, clear)`. `V(b)` substitutes attempt-b and its
specified epoch/context; a batch lists all exact members in attempt-ID order.
`Q(a)` is stage `received` with completion, review digest and verdict all null.
For added attempts, admission is at 0 unless stated, action and context match the
baseline, and `retry_of=null` except a named retry. Removal of a record renumbers
that source's remaining records contiguously unless the case explicitly tests a
hole. No generated record may silently fill an omitted source obligation.

Counts `O/R/E/P/U` mean observed / reviewed / exempt-unreviewed /
pending-within-deadline / uncovered, for `inference.local.generate` only.
F33 explicitly substitutes its separate tool action; it supplies no inference row.
Each report satisfies `O=R+E+P+U`. The ratio is `[R,O]` with `observed_only` unless
the case requires null: integrity uncertainty takes precedence over a zero
denominator; otherwise zero uses `no_observed_units`. Gaps, blocked prefixes,
disputed identities/epochs or conflicts use `integrity_uncertain`. A semantic
receipt/context failure alone consumes its source position and retains `[R,O]`.
All cases keep census `unknown` and inhibition `not_implemented`. An open run
stays `open`; a ratio of `[1,1]` does not close it.

Each required result freezes only the counts, ratios, states and codes it names.
Named codes must appear in the report's diagnostics or historical violations, but
the lists are not exhaustive. Explicit exclusions ("no …", "must not …", "is not
missed") are frozen negative assertions. Before a reference reconciler's output
is compared with these cases, complete expected reports (including source,
admission and checkpoint rows) must be hand-derived and frozen in a synchronized
revision.

## 3. Review timing and denominator cases

| Case | Exact timeline change / reports | Required result |
| --- | --- | --- |
| F01 — Completed evaluation | Add `V(a)@3`; report 4. Fresh variants use `clear`, `flagged`, `indeterminate`. | `1/1/0/0/0` in each. Non-clear variants retain `REVIEW_FLAGGED` or `REVIEW_INDETERMINATE`; review is neither safety nor permission. |
| F02 — Pending becomes uncovered | No receipt; report 2, then 4. | At 2: `1/0/0/1/0`; at 4: `1/0/0/0/1`, with `MISSED_REVIEW_DEADLINE` due 4. |
| F03 — Queue acceptance only | Add `Q(a)@3`; report 4. | `1/0/0/0/1`; `RECEIPT_NOT_EVALUATED` and missed deadline 4. |
| F04 — Exact deadline tie | Add `V(a)@4`; report 4. | `1/1/0/0/0`; no missed review deadline. Delivery at the deadline is timely. |
| F05 — Late delivery | Evaluated review completes/occurs at 3, delivered 5; report 4 and 5. | At 4: `1/0/0/0/1`; at 5: `1/1/0/0/0`. Historical missed deadline 4 remains. Producer time cannot backdate delivery. |
| F06 — Orphan receipt | Remove `A/D/T`; retain `open`; add `V(a)@3`; report 4. | `0/0/0/0/0`, null ratio, `ORPHAN_RECEIPT`. A receipt creates no execution. |
| F07 — Admission without dispatch | Remove `D/T`; no review; report 2 and 3. | Counts zero at both ticks. Admission changes from `waiting` to `unresolved` with `ADMISSION_UNRESOLVED` due 3. No proof of cancellation. |
| F08 — Unadmitted reviewed dispatch | Remove `A`; add `V(a)@3`; report 4. Fresh variant delivers the original A occurrence0 at4. | `1/1/0/0/0`, but historical `UNADMITTED_DISPATCH` remains (non-deadline finding, first_due_tick=null). Late A cannot repair authority. |

## 4. Context, receipt and retry cases

| Case | Exact timeline change / reports | Required result |
| --- | --- | --- |
| F09 — Divergent or unavailable context | (a) Monitor sidecar contains the truncated review object and receipt uses independently computed `I_TRUNC/C_TRUNC`. (b) Receipt copies `I_A/C_A` but has `context_views={}`. Both arrive3; report4. | Each `1/0/0/0/1`, ratio `[0,1]`; respectively `CONTEXT_MISMATCH` or `CONTEXT_UNAVAILABLE`, plus missed deadline4. Matching digest strings alone cannot discharge review. |
| F10 — Invalid receipt binding | Fresh variants of V(a)@3: (a) source=`controller-a` with that source's next sequence; (b) policy_digest=`P_OTHER`; (c) completed_at=4 while occurred/delivered=3. Report4. | Each `1/0/0/0/1`, with missed deadline4; (a) `SOURCE_ROLE_MISMATCH`; (b) `POLICY_MISMATCH`; (c) `RECEIPT_TIME_INVALID`. Role/policy failures block their source prefix and suppress ratio; completion-order failure consumes the position and leaves ratio `[0,1]`. |
| F11 — Retransmission and batch atomicity | (a) Deliver identical `V(a)` producer bytes at 3 and 4. (b) Instead deliver one evaluated batch at 3 containing valid `a` and an unknown `attempt-z`. Report 4. | (a) `1/1/0/0/0`, no double count. (b) `1/0/0/0/1`; orphan `z` prevents the whole batch from counting, including `a`; missed deadline 4 remains. |
| F12 — Distinct retry | Add admission b at 0 with `retry_of=attempt-a`, `D(b)@2`, `T(b)@3`; add `V(a)@3` only; report 5. | `2/1/0/0/1`; b has its own deadline 5 and missed review. Identical input/output bytes do not merge attempts. |
| F13 — No sealed terminal | Remove `T`; supply candidate `V(a)@3`; report 4 and 6. Separate timeout variant supplies `T(a)@2` with timeout/partial and `C_TIMEOUT`, then matching review at 3. | Missing terminal: `1/0/0/0/1` at both reports, `CONTEXT_UNSEALED`, missed review due 4 and `TERMINAL_MISSING` due 6. Timeout variant at 4: `1/1/0/0/0` plus `EXECUTION_OUTCOME_UNKNOWN`; review covers exactly `po`, never unavailable later output. |

## 5. Enrollment, exemptions and local evidence

| Case | Exact timeline change / reports | Required result |
| --- | --- | --- |
| F14 — Proven or unsupported cancellation | Remove `D/T`. Controller `cancel(a)@1`, witness `not_dispatched(a,cancel)@2`; report 4. Fresh plan-only variant changes both cause/type to `plan_only`. Unsupported variant omits witness confirmation. | Paired variants: counts zero, admission `not_dispatched`, no unresolved admission. Unsupported: counts zero, `ADMISSION_UNRESOLVED` due 3. All zero denominators have null ratio. |
| F15 — Post-dispatch cancellation | Keep baseline; add controller `cancel(a)@2` and witness `not_dispatched(a,cancel)@3`; no review; report 4. | `1/0/0/0/1`; `CANCEL_DISPATCH_CONFLICT` and missed deadline 4. Cancellation cannot erase the witnessed dispatch. |
| F16 — Prospective exemption | Human grant@0: id `exemption-a`, attempt_ids=[a], action=baseline action, valid_from=1, valid_until=2, reason=`fixture_exception`, policy=`no_added_authority`. No review; report 4. Continue with `V(a)@5`. | At 4: `1/0/1/0/0`; expiry after dispatch does not remove valid exemption. At 5: `1/1/0/0/0`; no double classification or missed review deadline. No action authority is added. |
| F17 — Invalid/revoked exemption | Fresh variants of F16, no review, report4: (a) grant delivery2; (b) valid_until=1 with valid_from=0; (c) issuer=controller using its next sequence; (d) attempt_ids=[b]; (e) valid grant revoked@1; (f) revoked@2. | (a–e) `1/0/0/0/1` and missed deadline4. (a) `EXEMPTION_INVALID`, ratio `[0,1]`; (b/e) `EXEMPTION_NOT_APPLICABLE`, ratio `[0,1]`; (c) `SOURCE_ROLE_MISMATCH`, blocked prefix, null/integrity_uncertain; (d) valid prospective grant for b, no exemption defect, ratio `[0,1]`. (f) `1/0/1/0/0`, ratio `[0,1]`, no exemption defect or missed review; revoke after dispatch does not undo a valid grant. |
| F18 — Missing ordinary local ledger | Keep baseline, no review. Separately label the ordinary JSONL source absent because of a different worktree or `--no-ledger`; report 4. These labels add no wire record. | `1/0/0/0/1`, missed deadline4. Local ledger absence cannot erase an independent witness. This case does not demonstrate a real observer or make `--no-ledger` safe. |
| F19 — Monitor outage | Add `A(b)@0`, `D(b)@2`, `T(b)@3`; no monitor records; report 5. | `2/0/0/0/2`, missed deadlines4 and5. Reporting the gaps is not inhibition or incident response. |

## 6. Stream integrity, continuity and policy

| Case | Exact timeline change / reports | Required result |
| --- | --- | --- |
| F20 — Sequence hole and backfill | Witness order: open seq1@0; D(a) seq2@1; T(a) seq3@2; D(b) seq4 occurs2/delivered5; T(b) seq5@3. Add A(b)@0 and V(a)@3. Report4 and5. | At4: `1/1/0/0/0` as partial established counts, `SOURCE_SEQUENCE_GAP`, admission b unresolved due3; ratio null/integrity_uncertain. At5: `2/1/0/0/1`, b review due5 from dispatch occurrence2, not backfill5. Historical admission failure remains; resolved gap is no longer current. |
| F21 — Conflicting source sequence | Keep baseline and V(a)@3. At4 deliver a different canonical witness record reusing seq2/record_id `witness-a-2`, describing D(b) at1 with epoch-a, baseline action and I_B plus b's input view. Report4. | Conservative counts `2/0/0/0/2`, ratio null/integrity_uncertain; `SOURCE_CONFLICT`. a is retained and b added; both are disputed because a's own dispatch position is contested. The original terminal suffix is quarantined so a's review cannot count. Do not choose a favorable branch or present two as certain multiplicity. At discovery/deadline4 both review obligations are unmet; b's conservative candidate findings also include `UNADMITTED_DISPATCH`. A separate discovery5 variant must not invent a missed deadline4 for a that was validly reviewed then; newly discovered b still receives `MISSED_REVIEW_DEADLINE` due4. |
| F22 — Compaction and restart | Add witness child epoch-b@2 after T(a), parent=epoch-a, prior=I_A, new=I_SUM; add A(b)@2 in epoch-b, D(b)@3 with I_SUM, T(b)@4 with C_SUM, V(b)@5; no V(a); report5. Run as separately labeled compaction and process-restart variants. | `2/1/0/0/1`; a's deadline4 survives, no source sequence resets, b deadline6. Child context is not a review of discarded parent context. A variant omitting the child epoch_open has only a established (`1/0/0/0/1`); D(b) blocks the witness prefix after sequence 3 (`incomplete`, no missing sequence), so b's witness records stay buffered and V(b) is orphaned; `EPOCH_CONTINUITY_FAILURE`, admission b unresolved due5, null ratio. |
| F23 — Unauthorized policy/identity mutation | (a) Keep baseline; deliver V(a)@3 bound to a worker-selected different policy digest. (b) Fresh baseline adds a second D(a)@3 with the identical descriptor/input but a fresh source sequence and record ID. Report4. | No favorable policy or identity rewrite: a remains uncovered with its original deadline4; (a) `POLICY_MISMATCH`; (b) `ATTEMPT_IDENTITY_CONFLICT`, disputed a with O=1, not invented multiplicity. Ratio null/integrity_uncertain. Only byte-identical retransmission is idempotent. |

## 7. Checkpoint cases and exact watermark construction

For the checkpoint cases only, `W(c,t)` means one watermark from each of the
four sources, occurring/delivered at `t`, with `through_tick=c` and
`through_sequence` equal to that watermark's own sequence minus one. Insert it
after all earlier-listed records for that source. No later non-watermark record
may occur at/before `c`. `K(c,m)@t` is monitor checkpoint receipt `cp-<c>`, cut `c`,
completion/occurrence/delivery `t`, and the exact sorted attempt-ID list `m`.
When K and W share a tick, the monitor receipt precedes its watermark. These
are explicit expansion rules, not a claim that missing sources automatically
produce watermarks. No other watermarks exist. Timer cuts use the fixed 10-tick
grid; count cuts use the first-usability tick of each new group of three units.
Membership is cumulative through the cut, not only units since the preceding cut.

| Case | Exact timeline change / reports | Required result |
| --- | --- | --- |
| F24 — Independent timer with no return | Baseline plus V(a)@3; no run_close and no turn-return input. Report10 and12. Continue with K(10,[a])@13 and W(10,13), then report13. | Counts stay `1/1/0/0/0`. cp-10 pending at10, overdue at12 with `CHECKPOINT_MISSED` due12, complete at13 with that historical violation retained. Window stays open. Agent silence cannot postpone timer cut10. |
| F25 — Count and final-close cuts | Count variant: A(b/c)@0, D(b)@2, D(c)@3, T(b/c)@4, evaluated batch[a,b,c]@4, K(3,[a,b,c])@5, W(3,5); report5, then10. Close variant: baseline plus V(a)@3, controller run_close@4, K(4,[a])@6, W(4,6); report6. | Count: `3/3/0/0/0`; cp-3 completed exactly at deadline5; no review missed (a due4). At10, cp-10 becomes pending with cumulative members[a,b,c]; count cut3 did not reset the timer to13. Close: `1/1/0/0/0`, cp-4 complete exactly deadline6 and `closed_reconciled`, with empty diagnostics and historical violations. Both retain unknown census. |
| F26 — Checkpoint is not individual review | Fresh variants of baseline plus controller run_close@4: (a) V(a)@3, K(4,[])@6, W(4,6); (b) no V, K(4,[a])@6, W(4,6); (c) V(a)@3, K(4,[a])@6, W(4,6) omitting only human watermark. Report6. | (a) counts `1/1/0/0/0`, `CHECKPOINT_MEMBERSHIP_MISMATCH`. (b) `1/0/0/0/1`; checkpoint receipt does not evaluate a. (c) `1/1/0/0/0`; absent source watermark prevents completion. All have overdue cp-4, `CHECKPOINT_MISSED` due6 and window open. |
| F27 — Empty cut and watermark contradiction | Empty variant removes A/D/T, keeps open, adds K(10,[])@12 and W(10,12); report12. Contradiction variant continues with witness D(a) occurring9/delivered13, next contiguous sequence, and report13. | Empty: counts zero, null ratio, cp-10 complete; window remains open. Later: disputed `1/0/0/0/1`, `WATERMARK_CONTRADICTION`, null ratio; cp-10 `invalidated`, current completed_at=null, `CHECKPOINT_INVALIDATED`. Its former completion at12 does not become an invented `CHECKPOINT_MISSED`; the newly discovered unit still retains `MISSED_REVIEW_DEADLINE` due12 and, having no admission, `UNADMITTED_DISPATCH`. |
| F28 — Early close with unresolved lifecycle | Admission variant: remove D/T; controller run_close@1, K(1,[])@2, W(1,2); report2 and3. Exempt variant: F16's grant, D(a)@1, no terminal, run_close@2, K(2,[a])@3, W(2,3); report3 and6. | Admission variant: zero counts, cp-1 complete but window open at2; at3 `ADMISSION_UNRESOLVED`, `closed_with_findings`. Exempt variant: `1/0/1/0/0`; cp-2 complete but window open at3; at6 `TERMINAL_MISSING`, `closed_with_findings`. Neither may report clean closure before its independent lifecycle deadline. |

## 8. Negative control, omissions and review discipline

**F29 — Absent from every observation source.** Remove A/D/T and keep only the
initial epoch record. The external fixture author knows an execution occurred at
tick1 but omits it from every delivered stream; this fact is not a wire input.
Report4 must have `0/0/0/0/0`, null ratio/no_observed_units, unknown census and
open window. The reconciler cannot discover the omitted execution. Reporting
test-author knowledge as a detection result fails this case.

Additional binding and retrospective-evidence cases:

| Case | Exact timeline change / reports | Required result |
| --- | --- | --- |
| F30 — Buffered prospective grant | Move D(a) to2 and T(a) to3. Human seq1 is watermark occurred0/delivered3, through_sequence=0/through_tick=0. Human seq2 is F16's grant occurred/delivered1 with valid_from=2/valid_until=3. No review; report2 and5. | At2: `1/0/0/1/0`, `SOURCE_SEQUENCE_GAP`, null/integrity_uncertain. At5: `1/0/0/0/1`, ratio `[0,1]`, `EXEMPTION_NOT_APPLICABLE`, missed review due5. Grant first usability3 was after dispatch2; early delivery alone cannot make it prospective. |
| F31 — Mutually matching wrong context | (a) Baseline D/T plus V(a)@3 all bind independently supplied wrong-model contexts `I_WRONG/C_WRONG`, while manifest remains unchanged. (b) Fresh baseline keeps D(I_A); T's payload stays completed/complete but its review view/digest and V@3 both use `C_TIMEOUT`. Report4. | Both `1/0/0/0/1`, ratio `[0,1]`, `CONTEXT_MISMATCH` and missed review due4. Matching witness/monitor hashes cannot override manifest model or terminal outcome. Named eligible dispatch remains observed despite bad context; no identity dispute is invented. |
| F32 — Review precedes usable witness evidence | Keep open@0/A(a)@0. D(a) occurs1 and T(a) occurs2, both delivered5 in contiguous witness sequence order. V(a)@3 has its full independent review view. Report4 and5. | At4: zero counts/null ratio, `ORPHAN_RECEIPT`, `ADMISSION_UNRESOLVED` due3. At5: `1/1/0/0/0`, ratio `[1,1]`; orphan resolves, admission failure persists, `MISSED_REVIEW_DEADLINE` due4 remains because no corroborated review was usable then. Terminal deadline6 is not missed. |
| F33 — Isolated synthetic tool effect | Fresh manifest changes only profile=`synthetic_tool`, protocol=`synthetic-tool`, model=`no-model`, eligible_actions=[`tool.synthetic.write`]; recompute P. Default A/D use that action, D/T use `I_TOOL/C_TOOL` and their exact sidecars; V(a)@3 matches. Report4. | Only the `tool.synthetic.write` row has `1/1/0/0/0`, ratio `[1,1]`. Inference totals are absent; never blend the two action families. No file is written: target/content are fabricated model data, not a TC mediator or expansion of the prospective runtime profile. |

This corpus does not test provider traffic, real credentials/isolation, a running
monitor, clocks across hosts, live compaction, cryptographic custody or refusal.
F33 freezes only an isolated tool model; it establishes no tool execution or
runtime containment. The prospective first runtime profile remains unchanged.
Malformed JSON/type fuzzing and exhaustive field permutations are later parser
work; the named malformed/binding variants here still have explicit expectations.

A second reader must derive counts, deadline histories, source prefix/quarantine,
and checkpoint state from these documents without a future implementation oracle.
Later artifacts must pin contract/fixture versions, exact expanded records,
delivery schedule, expected output and execution provenance. Reference results
record the contract and fixture revisions and the SHA-256 of both files, because
`mci/0.1` alone does not distinguish revisions. That pin belongs in
reference-result metadata, never in the closed report shape. An implementation
failure cannot silently change this oracle. Any semantic correction requires a
synchronized explicit revision and review. No natural-use trial, live coverage
claim, test pass, implementation grant or evidence-window closeout is created.

## 9. Revision r2 cases

These cases exercise the rules added in contract r2. They use the common baseline,
expansion and section 7 `K`/`W` notation, with the same partial-result discipline
as section 2. `D(b)'` is a second witness dispatch with b's identical descriptor
and input, but a fresh witness sequence and record ID.

| Case | Exact timeline change / reports | Required result |
| --- | --- | --- |
| F34 — Checkpoint receipt without a cut | (a) Baseline plus V(a)@3 and K(5,[a])@5; report5. (b) Fresh timeline: A(b/c)@0, D(b)@2, D(c)@3, V(a)@3, then K(3,[a,b,c])@3; no b/c terminals; report3. | (a) `1/1/0/0/0`, ratio `[1,1]`, `ORPHAN_RECEIPT`; no checkpoint row exists and no coverage is granted. (b) `3/1/0/2/0`, ratio `[1,3]`. The count cut cp-3 is created at3 before the receipt is matched, so there is no `ORPHAN_RECEIPT`; cp-3 is `pending` (deadline5) with that receipt in `receipt_record_ids`. Delivery order inside tick3 cannot change this. |
| F35 — Parent dispatch after child opening | F22's compaction timeline (child epoch-b@2, A(b)@2, D(b)@3 with I_SUM, T(b)@4 with C_SUM, V(b)@5, no V(a)), plus A(c)@2 in epoch-a, witness D(c)@3 in epoch-a with I_A listed after D(b), T(c)@4, and V(c)@4 with `input-a`/`review-a` views; report6. | `3/1/0/0/2`, ratio null/integrity_uncertain. Persistent `EPOCH_CONTINUITY_FAILURE` for epoch-a. c is disputed: V(c) gives no credit, and c's `MISSED_REVIEW_DEADLINE` due6 is a candidate finding. a keeps `MISSED_REVIEW_DEADLINE` due4. b is reviewed, and epoch-b's bindings stay valid because D(c) is sequenced after the opening. c was disputed when first usable, so it does not advance the count trigger: no count cut exists. |
| F36 — Empty-parent compaction | Remove A/D/T and keep open@0. Witness child epoch-b@1 (parent epoch-a, prior I_A, new I_SUM); A(b)@1 in epoch-b; D(b)@2 with I_SUM; T(b)@3 with C_SUM; report4. | The opening is rejected because epoch-a has no dispatch: persistent `EPOCH_CONTINUITY_FAILURE` for epoch-b. D(b) then names an unopened epoch and blocks the witness prefix after sequence 2 (`incomplete`, no missing sequence). Counts `0/0/0/0/0`, ratio null/integrity_uncertain; admission b `unresolved` with `ADMISSION_UNRESOLVED` due4. |
| F37 — Reused exemption ID | F16's grant (human seq1). (a) Add a fresh human grant@0 (seq2) reusing `exemption-a` for [a] with valid_from=2, valid_until=3. (b) Instead retransmit the original grant's exact bytes at1. No review; report4. | (a) `1/0/1/0/0`, ratio `[0,1]`, `EXEMPTION_INVALID` for exemption-a; the original grant still covers dispatch1, so no review deadline is missed. (b) `1/0/1/0/0` with no exemption finding; exact retransmission is idempotent. |
| F38 — Disputed units and the count trigger | Add A(b)@0, A(c)@3, D(b)@2, T(b)@3, D(c)@5; no review. (a) `D(b)'` at4. (b) `D(b)'` instead at2, sequenced right after D(b). Report5; continue (b) to report10. | Both at5: `3/0/0/1/2`, ratio null/integrity_uncertain, `ATTEMPT_IDENTITY_CONFLICT`; b is disputed, with `MISSED_REVIEW_DEADLINE` due5 as a candidate finding. (a) b advanced the count when first usable at2 and keeps that contribution, so c creates count cut cp-5 (pending, deadline7, members [a,b,c]). (b) b was disputed when first usable, so no count cut exists at5. At10, (b) has `3/0/0/0/3`, and timer cut cp-10 exists, pending, with members [a,b,c]: timer cuts do not depend on the count trigger. |

## 10. Revision record

- **r0** — frozen handoff draft (file SHA-256
  `6706a62525850238e08504a3d61e5f0f7f8e4c779c022035e3123a6b7d9c6ed8`).
- **r1** — 2026-10-23 agent review revision, synchronized with contract r1. It
  declares named findings non-exhaustive while freezing explicit exclusions. It
  states F21's disputed status and conservative candidate findings for b, F22's
  witness prefix block, F25's empty finding lists for `closed_reconciled`, and
  F27's `UNADMITTED_DISPATCH`. No count tuple, ratio, deadline or window state
  in r0 changes. This is agent review output, not human design acceptance.
- **r2** — 2026-10-23, synchronized with contract r2. Adds F34–F38 (section 9)
  for the operator-directed r2 rules and the agent-proposed supports that make
  them deterministic, and requires reference results to pin both file hashes.
  No F01–F33 expectation changes. F34–F38 are specified expectations, not
  executed tests, and this revision is not human design acceptance.
