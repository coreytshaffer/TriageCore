# Privacy Propagation Investigation (CR-DD-016 Track C) — 2026-08-29

## Headline — this record revises Track C's original suspicion

CR-DD-016 recorded the Track C question as whether `privacy_level="local_ok"` is
"intentional normalization, legacy dead code, or a genuine propagation defect."

**It is none of those three in the sense the question implied. The hardcoded
`privacy_level="local_ok"` is not itself a propagation defect in the CLI path.** It is a
constructor default that both callers override wherever the value is load-bearing, and the
operator's `--privacy` declaration *is* enforced end to end. No privacy-attributable
routing defect was demonstrated.

Track C instead identifies three different concerns — **evidence fidelity**, **vocabulary**,
and **library surface** — plus one enforcement-shape observation. Those are findings 1
through 4 below.

## What this document is, and is not

**This is a read-only investigation record for Track C of CR-DD-016's Sequencing section.
It is not a Change Request, not an amendment to CR-DD-016, not a runtime, schema, or test
change, and it grants no implementation authority of any kind.**

CR-DD-016 required that Tracks B and C stay "read-only until its own findings warrant a
separately scoped CR." This is that read-only output for Track C, and it is deliberately
recorded **before** any decision about change structure. Whether these findings warrant one
CR, two CRs, or no implementation change at all is left open on purpose: fixing the
evidence first and the remedy later keeps evidence collection separate from change
authority.

**Method.** Static source inspection at `main`
`c0545a7f7d4e08edaa31a3f5acd63d1e454328b9`, plus probes that call the **real**
`privacy_metadata_for_run`, `verify_packet`, `make_external_safe_packet`,
`TriageClient._build_resilience_route_input`, `choose_resilience_route`, and
`build_route_decision_payload` rather than re-implementing any of them, plus a read-only
census of `route_decision` events in the repository's existing ledgers. No `tc run` was
invoked, no ledger was written, no synthetic execution was created, and no repository
source, schema, test, or fixture was modified. Probe module provenance was asserted at
runtime (`triage_core.__file__` pinned to the working checkout) so results could not be
silently taken from a different checkout.

Unlike the Track B investigation, **no live model calls were made**. Every result here comes
from pure functions over constructed inputs.

This document does not modify, and should not be read as modifying:

- CR-DD-016, its Corrective Amendment, or its closeout;
- CR-DD-013's capability-resolution precedence, or CR-DD-012B's shared preview/execution
  design, both of which this record cites but leaves intact;
- Track B's record (`classifier-terminal-fallback-2026-08-29.md`), which is independent;
- any `triage_core/` source, schema, test, or fixture.

## The chain, as traced

    --privacy
      -> privacy_metadata_for_run                  (run_plan.py:121-127)
      -> PrivacyMetadata.external_model_allowed
      -> make_external_safe_packet                 (safe_task_packet.py:53)
      -> is_local_only                             (client.py:171-177)
      -> route_input.privacy_level                 (client.py:224 override; :822 default)
      -> local_only = privacy_level in LOCAL_ONLY_VALUES   (resilience_router.py:102)
      -> persisted as task_privacy_level           (route_events.py:242)

The full declaration envelope, produced by executing that chain rather than reasoning about
it:

| `--privacy` | `--allow-cloud` | `external_model_allowed` | `is_local_only` | `route_input.privacy_level` | router treats as local-only? |
| --- | --- | --- | --- | --- | --- |
| `local_only` | no | False | True | `local_only` | yes |
| `external_safe` | no | False | True | `local_only` | yes |
| `external_safe` | yes | True | False | `local_ok` | no |
| `public` | no | False | True | `local_only` | yes |
| `public` | yes | True | False | `local_ok` | no |

`--privacy local_only --allow-cloud` is rejected at the CLI (`tc_cli.py:1133`) and is
therefore absent. The enforcement is real: `local_only` yields
`external_model_allowed=False` (`run_plan.py:123`), which makes `make_external_safe_packet`
raise, which sets `is_local_only`, which sets `privacy_level="local_only"`, which puts the
router in its local-only branch. Nothing about the `local_ok` default weakens that.

## Finding 1 — Evidence collapse: the declaration is not recoverable from route evidence

The router consumes `privacy_level` for exactly one purpose — the binary test at
`resilience_router.py:102`, used at `:111` and `:124`. Every value outside
`LOCAL_ONLY_VALUES` (`resilience_router.py:12`) is therefore equivalent to every other.
That is fine for routing and lossy for evidence.

`build_route_decision_payload` persists the field verbatim as `task_privacy_level`
(`route_events.py:242`). Mapping the envelope above onto what is actually recorded:

| persisted `task_privacy_level` | operator declarations that produce it | recoverable? |
| --- | --- | --- |
| `local_only` | `local_only`; `external_safe` without cloud; `public` without cloud | **no — 3-way ambiguous** |
| `local_ok` | `external_safe` with cloud; `public` with cloud | **no — 2-way ambiguous** |

**The operator's declared privacy class cannot be reconstructed from persisted route
evidence.** This is structurally the same defect Track B found in the classifier lane, where
`bugfix` and `refactor` collapse onto one `task_class` before anything is written. Two
independent lanes, the same failure shape: the routing input is recorded, the governed
declaration that produced it is not.

One important qualification. The declaration **is** preserved faithfully elsewhere:
`GovernedRunSnapshot.declared_privacy` validates and carries exactly
`{local_only, external_safe, public}` (`governed_run_snapshot.py:433`). The information
exists in the system. Whether the snapshot's `declared_privacy` is reliably linked to the
corresponding `route_decision` event in persisted evidence **was not traced** and is not
asserted here. That linkage question is the natural first thing any follow-up should settle,
because it determines whether this finding is a recording gap or merely a
join-that-nobody-documented.

## Finding 2 — Vocabulary mismatch: `local_ok` is outside the declared privacy vocabulary

Three vocabularies are in play, and one has a member the others do not:

| surface | values |
| --- | --- |
| `--privacy` CLI choices (`tc_cli.py:2437`) | `local_only`, `external_safe`, `public` |
| `GovernedRunSnapshot.declared_privacy` (`governed_run_snapshot.py:433`) | `local_only`, `external_safe`, `public` |
| `ResilienceRouteInput.privacy_level` default (`resilience_router.py:56`, `client.py:822`) | **`local_ok`** |

`local_ok` appears in no declared-value schema and cannot be typed by an operator. It can
nevertheless reach persisted route evidence, where a reader would encounter a fourth term
with no definition in the declaration vocabulary and no obvious mapping back to one.

The plan path does not use it — `run_plan.py:381` assigns `local_only` or `external_safe`
explicitly. So the same invocation can be described by two different words depending on
which path recorded it. That divergence is examined, and largely defused, under the negative
finding below; it is noted here only because it is what makes `local_ok`'s vocabulary status
visible rather than academic.

## Finding 3 — Enforcement concentration: execution never independently consumes `allow_cloud`

`triage_core/client.py` does not read `allow_cloud` anywhere — verified by direct search of
the module. Execution's `internet_ok` and `cloud_primary_available` are taken from
configuration alone (`client.py:822` and the lines following), so on the execution path
cloud availability is a function of whether the cloud backend is enabled, **not** of whether
the operator asked for cloud on this invocation.

`--allow-cloud` is honored on the execution path, but **entirely indirectly**: it reaches
routing only through `privacy_metadata_for_run` (`tc_cli.py:1214`, `run_plan.py:126`) ->
`external_model_allowed` -> `make_external_safe_packet` -> `is_local_only` ->
`privacy_level`. Because `external_model_allowed` is `privacy in {...} and allow_cloud`,
`--allow-cloud=False` always produces `False`, so the packet is never external-safe and the
local-only branch always engages. The behavior is correct.

The observation is about **shape, not a demonstrated defect**: cloud exclusion on the
execution path rests on a single derived boolean. Any future change that let `is_local_only`
be `False` while the operator had not asked for cloud would silently re-open cloud routing,
with no second, independent check to catch it. Nothing in this record shows that happening
today.

## Finding 4 — Library default: direct `run_task` permits external-model eligibility with no declaration

`PrivacyMetadata`'s dataclass defaults are `data_class="public"` (`task_packet.py:6`) and
`external_model_allowed=True` (`task_packet.py:10`). A caller who constructs a `TaskPacket`
directly and invokes `run_task` — bypassing the CLI, which always supplies metadata via
`privacy_metadata_for_run` — therefore gets a packet that **passes** every
`make_external_safe_packet` check. Probed end to end:

    defaults: data_class='public'  external_model_allowed=True
      -> is_local_only=False   privacy_level='local_ok'   route=local_fast

So the default posture for a direct library caller is external-model-eligible, with no
operator privacy declaration having been made at all. This parallels CR-DD-013's
`capability is None` branch, where the absence of supplied evidence yields the permissive
literal rather than the conservative one.

**This is recorded as behavior, not as a defect.** It may well be deliberate API policy —
`run_task` is a library entry point, its callers are in-process code rather than operators,
and CR-DD-013 set an explicit precedent for treating "no evidence supplied" differently from
"evidence supplied and negative." Establishing which it is requires reading this default
against its own authorities, which this record does not do.

## Negative finding — the plan/execution route divergence is capability-attributable, not privacy-attributable

This is recorded at length because the intermediate results were misleading, and a reader
who re-derives them without the controls will reach the wrong conclusion.

**The apparent signal.** Plan and execution assign *different* `privacy_level` values for
four of the five reachable invocations:

| invocation | plan records | execution records |
| --- | --- | --- |
| `local_only` | `local_only` | `local_only` |
| `external_safe`, no cloud | `external_safe` | `local_only` |
| `external_safe`, cloud | `external_safe` | `local_ok` |
| `public`, no cloud | `external_safe` | `local_only` |
| `public`, cloud | `external_safe` | `local_ok` |

**Two probes that pointed the wrong way, and why they were wrong.** Isolating the
`privacy_level` field and asking the router directly produced dramatic divergences —
`external_safe` selecting `cloud_primary` where `local_only` selected `human_handoff`, in
six of eight categories. Both probes forced cloud availability on **both** sides. That does
not model the plan path, which sets `internet_ok`, `cloud_primary_available`, and
`cloud_credit_state` from `allow_cloud` itself (`run_plan.py:382-388`). A field-level
sensitivity analysis is not a reachability claim, and it was being read as one.

**The controlled comparison.** Rebuilding each path's route input the way its own source
builds it:

- **Local routes available:** all five invocations select the **same** route on both paths,
  despite `privacy_level` differing in four of them. The recorded-value divergence does not
  become a routing divergence.
- **Local routes unavailable:** all five diverge — **including `--privacy local_only`, where
  both paths record the identical `privacy_level`.**

That last row is the control that settles it. A divergence that persists when the variable
under test is held constant is not caused by that variable. The cause is capability: the
plan path passes `capability=None` unconditionally (`run_plan.py:378-380`), by explicit
CR-DD-012B design, so the plan always believes local routes are available while execution
knows whether they are.

**Conclusion: no privacy-attributable routing defect was demonstrated.** The residual
plan/execution divergence is a known, documented consequence of CR-DD-012B's decision to
keep capability out of the decision ID, and is out of Track C's scope.

## Historical evidence — `local_ok` has never been recorded

A census of every `route_decision` event in the repository's ledgers found six events
carrying `task_privacy_level`, and **all six record `local_only`**. Two further
`route_decision` events (root `ledger.jsonl` smoke tests) carry `None`. **No persisted trial
has ever recorded `local_ok`.**

This is consistent with the envelope rather than in tension with it: `local_ok` requires
`--allow-cloud` together with a non-`local_only` declaration, and every recorded trial was
local-only. The finding-1 ambiguity is therefore, to date, **latent in the recorded corpus**
— real in the code, not yet realized in evidence. That distinction matters for judging
severity and should not be collapsed in either direction.

## Classification

**EVIDENCE-FIDELITY AND VOCABULARY GAP, WITH TWO UNADJUDICATED BOUNDARY OBSERVATIONS — and
an explicit negative result on enforcement.**

Not a routing defect: the declaration is enforced across the whole reachable envelope, and
the one apparent counter-example is attributable to capability, proven by control. Not a
pure documentation gap either: no prose makes a collapsed evidence field recoverable, and no
prose removes a term from a vocabulary it was never meant to join.

**Three distinct assurance levels, deliberately not conflated.** Making the declaration
recoverable in evidence (finding 1) is a recording question. Removing or defining `local_ok`
(finding 2) is a vocabulary question. Whether execution should independently consume
`allow_cloud`, and whether the library default should be permissive (findings 3 and 4), are
**policy** questions that may be answered "no change" once read against their own
authorities. Nothing here establishes that findings 3 or 4 require any change.

## Recorded result

> Track C's original suspicion is revised: `privacy_level="local_ok"` is a constructor
> default that both callers override where it matters, and the `--privacy` declaration is
> enforced end to end through `external_model_allowed` -> `make_external_safe_packet` ->
> `is_local_only`. No privacy-attributable routing defect was demonstrated; the apparent
> plan/execution divergence is capability-attributable, proven by the control case where
> `privacy_level` is identical on both paths and the routes still diverge. What Track C does
> establish is that the operator's declaration is not recoverable from persisted route
> evidence (three declarations collapse onto `local_only`, two onto `local_ok`), that
> `local_ok` belongs to no declared privacy vocabulary, that execution never independently
> consumes `allow_cloud` so cloud exclusion rests on one derived boolean, and that the
> direct-library default is external-model-eligible absent any declaration. No recorded trial
> has ever carried `local_ok`, so the evidence ambiguity is latent rather than realized.

## Deferred follow-up — two candidate lanes, MARKED not decided

This record fixes the evidence. It deliberately does **not** decide the change structure. No
CR identifier is minted, no implementation is proposed, and no claim is made that either
lane must result in a change.

- **Candidate A — privacy evidence fidelity and vocabulary.** Findings 1 and 2. Would have
  to settle first whether `GovernedRunSnapshot.declared_privacy` is already reliably joined
  to the corresponding `route_decision` event, since that determines whether anything is
  actually missing from evidence or merely undocumented. Any recording change would need
  reconciling with CR-DD-018's evidence contract.
- **Candidate B — privacy enforcement boundary and library default.** Findings 3 and 4.
  **This lane may correctly conclude in no change.** The direct-library default may be
  intentional API policy, and the single-mechanism enforcement shape is a robustness
  observation rather than a demonstrated defect. Examining it against CR-DD-013's precedent
  for absent-evidence defaults is prerequisite to proposing anything.

Whether these are one CR, two CRs, or none is an open question this record does not answer
and should not be read as answering.

**Track B is complete and independent of this record. Nothing here reopens it.**
