# Declared-Privacy Evidence Join Trace (Track C Finding 1 dependency) — 2026-08-29

## Status and scope

**This is a read-only falsification trace. It is not a Change Request, not an
implementation, not an amendment to the Track C record, and it grants no implementation
authority.** No CR identifier is minted here, and Candidate A is not converted into an
accepted change request.

It answers exactly one inherited question and stops. It does not touch Candidate B, which
is outside this record entirely.

**Baseline.** All source facts below were verified by direct inspection at `main`
`5003761b37e9293d4f8c207b5922047d9dc18270`, and every file:line citation in this document
resolves at that commit. Nineteen source locations were checked before writing and all
nineteen resolved; every file:line reference appearing in this document is one of them.
Nothing checked was found missing, and nothing cited went unchecked.

**Method.** Static source inspection, plus a read-only census of the repository's existing
ledgers under `.triagecore/`. No `tc run` was invoked, no ledger was written, no synthetic
execution was created, no model was called, and no repository source, schema, test, or
fixture was modified.

## The question inherited from Track C

The Track C record (`privacy-propagation-2026-08-29.md`, Finding 1) established that the
operator's declared privacy class is not recoverable from the `route_decision` payload
itself, and then deliberately declined to resolve one dependency:

> Whether the snapshot's `declared_privacy` is reliably linked to the corresponding
> `route_decision` event in persisted evidence **was not traced** and is not asserted here.
> That linkage question is the natural first thing any follow-up should settle, because it
> determines whether this finding is a recording gap or merely a
> join-that-nobody-documented.

This trace settles that dependency and nothing else.

## Determination

**The uncertainty is resolved: on the ordinary execution path there is no persisted
evidence join from `route_decision` to the operator's declared privacy class. This is a
recording/provenance gap, not merely an undocumented existing join.**

The basis for that conclusion is the static trace in the next section. The empirical census
that follows is corroborating evidence, not the basis.

## Static evidence — the basis for the join-absence conclusion

**1. The governed decision body is never ledger-appended.** `serialize_governed_decision`
(`governed_decision.py:310`) is imported in `client.py:555` and called at exactly one site,
`client.py:573`, where its output is used for an in-memory serialize/reparse verification
of the decision id. That value is not passed to any ledger append. The route-decision
append site is `client.py:686`, and it writes the route payload only. The decision body —
which is where `operator_intent.declared_privacy` lives — therefore never reaches persisted
evidence through this path.

**2. `run_plan_review_confirmed` has an exact-key payload that excludes the declared privacy
value.** `confirmation_payload` (`run_plan_artifact.py:678`) returns a fixed dictionary, and
its keys are constrained to the twelve-member `_CONFIRMATION_KEYS` frozenset
(`run_plan_artifact.py:87`). `declared_privacy_class` is not a member. The payload carries
`plan_body_digest` and `artifact_byte_digest`, but not the privacy value itself — a
distinction developed in its own section below.

**3. The optional plan artifact is the only identified persisted carrier of
`declared_privacy_class`.** It appears in the artifact body at `run_plan_artifact.py:279`,
and in the artifact's declared key set at `run_plan_artifact.py:42`. This is a file on
disk, not a ledger event.

**4. The plan artifact contains no `decision_id`.** A search of `run_plan_artifact.py`
returns zero occurrences of `decision_id`. Correlation between an artifact and a
`route_decision` event could therefore only be attempted by `task_id`, never by the
decision linkage that `route_decision` itself carries
(`route_events.py:236`, `:275`).

**5. `--plan-output` defaults to absent and is conditioned on a plan-specific invocation.**
The flag is declared with `default=None` (`tc_cli.py:2474`) and its help text states it
requires `--plan`, `--model`, and `--task-id` (`tc_cli.py:2475`). Those conditions are
enforced at `tc_cli.py:1084` (`--plan-output` requires `--plan`) and `tc_cli.py:1104`
(`--task-id` is required with `--plan-output`). The artifact is therefore produced only on
explicit operator opt-in under three co-required conditions.

**Therefore: an ordinary `tc run` does not persist a recoverable declared privacy value,
and does not persist any join to one.** The best join available even in the favourable case
is `route_decision.task_id` correlated against an operator-retained artifact file that
lives outside the ledger — and that case requires the operator to have opted into
`--plan-output` and retained the file.

For completeness, the declaration is validated and carried faithfully in memory:
`GovernedRunSnapshot.declared_privacy` admits exactly
`{local_only, external_safe, public}` (`governed_run_snapshot.py:433`). The gap is in
persistence and linkage, not in the in-memory model.

## Empirical census and controls

Corroborating only. The determination above rests on the static trace; this section shows
the recorded corpus is consistent with it, and shows the method well enough that a later
reader can falsify it.

Corpus: every `*.jsonl` under `.triagecore/`, 814 rows parsed, 8 `route_decision` events.

| probe | result | role |
| --- | --- | --- |
| `task_privacy_level` present in `route_decision` | 6/8 | **positive control** — method finds keys that exist |
| `selected_route` present in `route_decision` | 8/8 | **positive control** — method finds keys that exist |
| `zzz_not_a_real_key` present in `route_decision` | 0/8 | **negative control** — method reports absence correctly |
| `declared_privacy` present in `route_decision` | 0/8 | the question |
| `declared_privacy_class` present in `route_decision` | 0/8 | the question |
| `operator_intent` present in `route_decision` | 0/8 | the question |
| `run_plan_review_confirmed` events in corpus | 0 | carrier-search context |
| `governed_decision` events in corpus | 0 | carrier-search context |
| `zzz_fake_event` events in corpus | 0 | **negative control** for the carrier search |

A deliberately broader check was also run: a raw substring scan for `declared_privacy`
across all 814 rows, which would catch the value at any nesting depth rather than only as a
top-level payload key. It returns **0**.

The controls are load-bearing. Without them a table of zeros is indistinguishable from a
census that silently fails to read anything, which is the failure mode this repository has
recorded before. The positive controls establish that the same code path does find keys
that are present in the same events.

## Authentication is not recovery

`run_plan_review_confirmed` carries `plan_body_digest` and `artifact_byte_digest`. Those
permit a holder of a plan artifact to **authenticate** it against the ledger — to confirm
that the bytes they possess are the bytes that were reviewed.

They do not permit **recovery**. A digest is not a preimage: ledger evidence alone cannot
reconstruct `declared_privacy_class` from them. A reader who encounters those digests could
reasonably mistake them for privacy provenance; they are integrity anchors for an
externally held artifact, and the declared privacy class is recoverable only if that
external artifact is itself still held.

This distinction sharpens the determination rather than softening it: the ledger can prove
an artifact was not altered, while remaining unable to say what privacy class the operator
declared.

## Historical-corpus limitation

`decision_id` is present in **0 of 8** recorded `route_decision` events.

**This result must not be read as evidence that current governed execution fails to emit
`decision_id`.** The recorded corpus predates CR-DD-012B, which introduced the governed
decision linkage (`route_events.py:236`, `:275`; set on the execution path at
`client.py:183` and `client.py:194`). Absence in a corpus that predates the feature is
expected and carries no information about present-day behavior.

The result is recorded here as **historical/corpus context only**. It is not part of the
basis for the determination, and the determination does not depend on it: the static trace
establishes that even a present `decision_id` would not reach a persisted record of the
declared privacy class, because no such persisted record exists on the ordinary path.

## Effect on Candidate A

Track C listed two candidate lanes and marked both undecided. This trace bears on one of
them.

**Candidate A — privacy evidence fidelity and vocabulary — may now be described as
evidence-supported, or eligible for CR consideration.** Its stated prerequisite was
settling whether the join already existed; that prerequisite is discharged, and the answer
supports rather than dissolves the finding.

**Candidate A remains undecided and unminted.** No CR identifier is created, no
implementation is proposed, no scope is drafted, and nothing here obliges any change. The
question of whether Candidate A becomes one CR, part of a CR, or no change at all is
untouched by this record.

**Candidate B is outside this record entirely** and is neither supported, weakened, nor
modified by anything above.

## Explicit non-findings and unresolved questions

Recorded as open rather than resolved by inference:

- **Possible non-ledger persistence outside the traced scope.** This trace covered the
  ledger and the plan artifact. Whether any other store — outside `.triagecore/`, or in a
  surface not reached from the paths above — retains decisions or declarations was not
  established.
- **Plan-artifact retention convention.** Whether operators are expected to retain
  `--plan-output` artifacts, where, and for how long, was not traced. The favourable join
  case depends on that convention, which is currently unknown to this record.
- **Present-day empirical `decision_id` emission on a governed path.** Not exercised here.
  The static trace shows where it is set and emitted; no current-day run was performed to
  observe it, and none is claimed.
- **Whether the absence is intentional.** Nothing in this trace establishes whether the
  non-persistence of the declared privacy class is a deliberate minimisation choice — for
  example, to keep operator declarations out of a ledger that withholds prompt content — or
  an oversight. That question is prerequisite to any remedy and is not answered here.

## No-change boundary

This record changes no code, test, schema, fixture, workflow, configuration, or runtime
behavior. It mints no CR identifier. It does not amend the Track C record, whose Finding 1
stands as written; this document resolves the dependency Finding 1 named, and should be
read alongside it rather than as a replacement for it. It grants no implementation
authority of any kind, and creates no standing authority.
