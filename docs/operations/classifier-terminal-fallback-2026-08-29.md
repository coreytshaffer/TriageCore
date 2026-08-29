# Classifier Terminal-Fallback Investigation (CR-DD-016 Track B) — 2026-08-29

## What this document is, and is not

**This is a read-only investigation record for Track B of CR-DD-016's Sequencing section.
It is not a Change Request, not an amendment to CR-DD-016, not a runtime, schema, or test
change, and it grants no implementation authority of any kind.**

CR-DD-016 named three tracks and required that Tracks B and C stay "read-only until its
own findings warrant a separately scoped CR." This document is the output of that
read-only stage for Track B. It records what was established, what was not, and what a
later CR would have to decide. Minting a CR identifier, proposing a fix, or changing any
`triage_core/` source remains unauthorized and is not done here.

**Method.** Static source inspection at `main` `fa66c644c95dcdd68c879313225822d696568643`,
plus read-only probes that call the real `TriageClient._build_resilience_route_input` and
`choose_resilience_route` rather than re-implementing their logic, plus read-only
inspection of the existing untracked evidence ledgers under `.triagecore/`. No `tc run`
was invoked, no ledger was written, no synthetic execution was created, and no repository
source, schema, test, or fixture was modified.

One qualification stated plainly: measuring the classifier's timeout behavior required
**five live local Ollama classification calls** (`POST /api/chat` on `localhost:11434`).
These wrote nothing and touched no ledger, route, capability, privacy, or authority
surface, but they are live model calls rather than pure static analysis, and findings 5
and 6 below depend on them.

This document does not modify, and should not be read as modifying:

- CR-DD-016, its Corrective Amendment, or its closeout;
- CR-DD-013's resolution precedence or any routing/capability semantics;
- Track C (the `privacy_level` propagation question), which stays separate per
  CR-DD-016's Sequencing rule and CR-DD-017's restatement of it;
- any `triage_core/` source, schema, test, or fixture.

## Reconciliation against `main` at `96eb3d3` — added 2026-08-29

The findings below were established at `fa66c64`. While this record was being drafted,
`main` advanced three times. This section reconciles the record against the current tip
rather than leaving it to read as current when part of it no longer is.

| merge | PR | what it changed | affects this record? |
| --- | --- | --- | --- |
| `c798e0e` | #179 — CR-DD-012B, shared preview/execution consumption | `run_plan.py`, `client.py`, `route_events.py`, `tc_cli.py`, new `runtime_observation.py` | **Yes** — overlaps Finding 3; see below |
| `da96b66` | #180 — CR-DD-016 closeout | `docs/` only | No |
| `96eb3d3` | #166 — CR-132 CLI architecture accounting | `docs/` only (one new CR document) | No |

Only PR #179 touched `triage_core/`. Verified directly: `git diff c798e0e 96eb3d3 --
triage_core/ tests/ schemas/` is empty, so every source fact below that held at `c798e0e`
holds unchanged at `96eb3d3`. All citations in this section were re-verified against
`96eb3d3`, including the two negative controls named under Citation drift.

**What PR #179 added.** `governed_decision.py` now enumerates a closed
`CLASSIFICATION_REASON_CODES` vocabulary including `deterministic_classifier_match` and
`deterministic_classifier_default` (`governed_decision.py:65-72`). `run_plan.py` sets it
via `_classification_reason_code` (`run_plan.py:221-235`, applied at `run_plan.py:468`),
which distinguishes a genuine keyword match from the terminal default by reproducing that
last branch's condition — and its docstring states the same fact this record establishes
independently: `classify_deterministic` "returns `refactor` both for an explicit refactor
request and as its terminal default, and it exposes no provenance."

**Effect on Finding 3.** The governed-decision path now *can* distinguish the terminal
fallback from a real `refactor` classification. That is exactly the provenance Finding 3
reports as absent, so **Finding 3 is partially superseded for that path.** Two limits keep
it from being fully resolved:

- The new reason code is derived from `classify_deterministic` only. The ordinary `tc run`
  execution path still calls `TaskClassifier.classify` with no provenance capture
  (`client.py:215`), and `task_class_map`/`sensitivity_map` still collapse `bugfix` and
  `refactor` onto `code_repair` with `sensitivity="low"` before any route evidence is
  written (`client.py:774-821`).
- `client.py` does consume a `GovernedDecision` (`client.py:551-574`), so on the
  governed-plan path the reason can reach execution. **Whether it reaches persisted route
  evidence was not traced**, and is not asserted here.

**Effect on the other findings — none.** `classifier.py`, `resilience_router.py`, and
`backends.py` are byte-identical between `fa66c64` and `96eb3d3`, and the `client.py` maps
moved without changing content. Findings 1, 2, and 4 through 7 stand unchanged. The
`--plan`-versus-execution seam in Finding 7 arguably *widens*: the plan path gained
classification provenance that the execution path still lacks.

**Citation drift.** Line references to `classifier.py`, `routing/resilience_router.py`, and
`backends.py` resolve at every commit named here. References to `client.py`, `run_plan.py`,
and `routing/route_events.py` were verified at `fa66c64` and **do not resolve at `c798e0e`
or `96eb3d3`** — `run_plan.py:59` is now an import (`classify_deterministic` moved to line
360) and `route_events.py:217` is now a docstring (`task_sensitivity` moved to line 241).
Both were re-checked at `96eb3d3` as negative controls and still point at the wrong
content, confirming the drift is real rather than an artifact of how it was measured. The
findings' substance is unaffected; only the line anchors moved.

## Why this was investigated

CR-DD-016 recorded the observation as an unconnected adjacent finding: `TaskClassifier`'s
regex fallback has a "terminal, no-match fallback [of] `"refactor"` — a specific,
semantically wrong category rather than an `"unknown"` or neutral result," and explicitly
noted that "the sunscreen run did not establish that the classifier reached the
`"refactor"` fallback."

Track B was scoped to settle three questions: whether `"refactor"` is genuinely the
universal terminal fallback, what downstream routing decisions depend on it, and whether
any specific trial actually traversed that path.

## Findings

### 1. `"refactor"` is the universal terminal fallback — confirmed

`classify_deterministic`'s terminal no-match return is `"refactor"` (`classifier.py:78`),
and `classify` falls through to `classify_deterministic` on every failure path
(`classifier.py:58`) — no backend, backend construction failure, any exception, a timeout,
an empty response, or a response that is not an exact member of `CATEGORIES`
(`classifier.py:51-56`). Both entry points therefore terminate at `"refactor"`. Confirmed
empirically: the empty string classifies as `"refactor"`.

### 2. The fallback resolves *permissively*, which sharpens CR-DD-016's characterization

CR-DD-016 described the fallback as "semantically wrong." That is accurate but understates
the consequence. Probing the real router shows where `"refactor"` actually lands:

| category | sensitivity | task_class | selected route | router reason |
| --- | --- | --- | --- | --- |
| `docs_update` | low | `docs_update` | `local_fast` | `local_fast_available_for_small_or_repetitive_task` |
| `bugfix` | low | `code_repair` | `local_heavy` | `local_heavy_available_for_medium_or_complex_task` |
| `test_addition` | low | `code_generation` | `local_heavy` | `local_heavy_available_for_medium_or_complex_task` |
| **`refactor`** | **low** | **`code_repair`** | **`local_heavy`** | `local_heavy_available_for_medium_or_complex_task` |
| `packaging` | medium | `configuration_review` | `local_heavy` | `local_heavy_available_for_medium_or_complex_task` |
| `security_review` | high | `security_review` | `human_handoff` | `sensitivity_requires_human_review` |
| `architecture_planning` | medium | `architecture_planning` | `local_heavy` | `local_heavy_available_for_medium_or_complex_task` |
| `blocked_or_high_risk` | high | `security_review` | `human_handoff` | `sensitivity_requires_human_review` |

*(Enumerated against the capability state the Aug-8 trial actually recorded — `configured`,
both local routes declared and bound — with `privacy_level="local_only"`.)*

`"refactor"` maps to `sensitivity="low"` (`client.py:488`), which is below the
`{"medium", "high"}` threshold that sets `review_required` (`resilience_router.py:101`)
and below `HIGH_SENSITIVITY_VALUES` (`resilience_router.py:11`) that would route to
`human_handoff` (`resilience_router.py:106-107`). The probe confirms
`human_review_required=False` for the fallback.

**The terminal fallback therefore assigns an unclassifiable prompt the least restrictive
sensitivity tier available, and routes it to autonomous local execution with no human
review.** A neutral `"unknown"` could have been mapped conservatively in either direction;
`"refactor"` specifically resolves toward permission. This is the substantive finding of
Track B, and it is a property of the *composition* of `classifier.py` and `client.py`'s
maps — neither file states it.

### 3. Whether any trial traversed the path — one case settled, the general case unanswerable

**The Aug-8 trial motivating CR-DD-016 did not traverse it — settled.** Its `route_audit`
records `recommended_route: human_handoff`. The envelope above shows that at that trial's
recorded capability state, the terminal `no_reliable_automated_route_available` handoff
(`resilience_router.py:131`, `:170`) is unreachable — every non-sensitive category resolves
to `local_fast` or `local_heavy`. Only `security_review` and `blocked_or_high_risk` produce
`human_handoff`, and `"refactor"` produces `local_heavy`. **CR-DD-016's Corrective
Amendment claim is confirmed by probe rather than merely inferred.**

**The general question cannot be answered from recorded evidence, by construction.**
`task_class_map` collapses both `"bugfix"` and `"refactor"` onto `"code_repair"`
(`client.py:466`, `client.py:468`), and the ledger's `route_decision` payload records the
mapped `task_class` and `task_sensitivity` (`route_events.py:217`), never the classifier's
own category. A census of every `route_audit`/`route_decision` pair in the repository's
ledgers found:

- `daily-use-window/2026-08-01-corrected`: **two trials at `task_class=code_repair`,
  `sensitivity=low`, routed `local_heavy`.** These are equally consistent with a genuine
  `bugfix` classification and with the `"refactor"` terminal fallback. Nothing recorded
  distinguishes them.
- `daily-use-window/2026-08-01`: one `docs_update`; two `human_handoff` blocks with no
  `route_decision` event.
- `daily-use-window/2026-08-06`: one `docs_update`.
- `daily-use-window/2026-08-08`: the Aug-8 trial — `route_audit` only.
- `local-heavy-diagnostic/2026-08-07`: one `architecture_planning`.
- root `ledger.jsonl`: self-test and smoke records only, `task_class=None`.

So the honest answer to Track B's third question is: **no recorded trial can be shown to
have traversed the fallback, and no recorded trial can be shown not to have, except where
the selected route itself excludes it.** Closing this gap would require recording the
classifier's category — a schema question, and therefore a CR question.

A second-order note: the Aug-8 ledger carries no `route_decision` event at all, only the
`route_audit` whose `reason_code` (`ambiguous_or_remote_route`) is `client.py`'s own
blocked-path code, not the router's `reason`. That trial predates CR-DD-017's blocked-route
evidence parity, which is precisely the gap CR-DD-017 closed.

### 4. The two classifiers disagree on a documented category

The model system prompt states that `refactor` covers "Restructure, rewrite, clean, format
code" (`classifier.py:33`). `classify_deterministic` checks `"format"` in its destructive
keyword list (`classifier.py:64`), before any other rule. For the prompt
`"format the code"`:

| path taken | category | sensitivity | route |
| --- | --- | --- | --- |
| model answers within budget | `refactor` | low | `local_heavy`, no review |
| model does not answer | `blocked_or_high_risk` | high | `human_handoff`, blocked for `local_only` |

The same input yields opposite governance outcomes, decided by whether a network call
returns in time. This is not a fallback being merely coarse; it is two classifiers in one
function disagreeing on a category the system prompt defines explicitly.

### 5. On this host, the model path never won — 0/5

Five live `TaskClassifier.classify("format the code")` calls all returned
`blocked_or_high_risk`, identical to the deterministic result. The model path did not win
once.

**Scope of this claim:** one host, one cold model (`qwen2.5-coder:7b-triagecore`), one
moment. The daemon's own `/api/tags` took 2113 ms to answer. This does **not** establish
that the model path never wins anywhere; on a host with a warm model it may well win, which
is exactly what makes finding 4 a race rather than a constant.

### 6. The stated 1.5-second guard costs about 3.0 seconds

`classifier.py:49` passes `timeout=1.5` with the comment "short timeout to prevent UI
freezes." Measured wall-clock per `classify` call was ~3015-3025 ms across every trial.

**A hypothesis that proved wrong, recorded rather than dropped:** the first explanation
tried was that `generate` spends a second full budget on a `resolve_model` preflight
(`backends.py:296` passes `min(float(timeout), 2.0)` into a method that issues its own
`GET /api/tags`). Direct measurement refuted this — `resolve_model` returns in **0 ms**
because it short-circuits whenever an explicit model is set (`backends.py:261-262`), and
`create_backend` in `classify` always sets one (`classifier.py:19-20`). An isolated
`requests.post(..., timeout=1.5)` to `/api/chat` was then measured at ~3015 ms on its own
before raising `ReadTimeout`, which locates the doubling inside the single HTTP call.

The effect is measured and reproducible; **the cause inside `requests`/`urllib3` was not
isolated** and is not asserted here. A later CR that wants to change the timeout should
establish the cause first, because the fix differs depending on it.

### 7. Two adjacent observations, recorded but not investigated

- **`--plan` and execution use different classifiers.** `run_plan.py:59` calls
  `classify_deterministic` (never a model); `client.py:119` calls `classify`
  (model-assisted). Preview and execution can therefore classify the same prompt
  differently even when the model path does win — a provenance seam distinct from the race
  in finding 4.
- **The routing tests mock a category the classifier cannot emit.** Several suites patch
  `TaskClassifier.classify` with `return_value="general"`, which is not a member of
  `CATEGORIES` (`classifier.py:7-10`). The `.get(category, ...)` defaults at
  `client.py:509-511` are consequently exercised only by mocks, never by the real
  classifier.

Neither was traced further; both are stated as observations, not findings.

## Classification

**COMPOSITION DEFECT WITH A PERMISSIVE FAILURE DIRECTION — plus an evidence gap that
prevents measuring its incidence.**

Not a pure documentation gap: no prose change makes an unclassifiable prompt stop routing
to unreviewed autonomous execution. Not a straightforward runtime defect either — every
individual component behaves as written, `classifier.py` never claims `"refactor"` is a
neutral default, and `client.py`'s maps never claim to handle an unknown category. The
defect lives in their composition, which is why neither file reads as wrong in isolation.

**Two distinct assurance levels, not to be conflated.** Changing the terminal fallback to
a neutral category with a conservative mapping would address the *permissive direction*.
It would not, by itself, make the fallback *observable* — that requires recording the
classifier's category in the route evidence, which is a separate schema decision under
CR-DD-018's evidence contract. Finding 2 and finding 3 are therefore not one fix.

## Recorded result

> `"refactor"` is confirmed as the universal terminal fallback of both `classify` and
> `classify_deterministic`. It resolves to `sensitivity=low` and routes to `local_heavy`
> with `human_review_required=False`, so an unclassifiable prompt fails toward permission
> rather than toward review. The Aug-8 trial motivating CR-DD-016 provably did not traverse
> it, confirming that CR's Corrective Amendment. Whether any other trial traversed it is
> unanswerable from recorded evidence, because `bugfix` and `refactor` are collapsed onto
> one `task_class` before anything is written. Separately, the model and regex classifiers
> disagree on `"format"`, giving the same prompt opposite governance outcomes depending on
> a race the model lost 5/5 times on the measured host.

## Deferred follow-up — candidate CRs, none authorized, none minted

This investigation's findings appear to warrant Change Requests, which is the condition
CR-DD-016 set for leaving read-only status. No identifier is minted and no authority is
requested by this document. Two candidates are recorded, deliberately **not** combined:

1. **Terminal-fallback semantics, and the execution path's missing provenance.** Whether
   `"refactor"` should become a neutral `"unknown"` with a conservative mapping, and
   whether the classifier's category should be recorded in the *execution* path's route
   evidence so the fallback's incidence becomes measurable there.

   **Narrowed by PR #179 — see the Reconciliation section.** The governed-decision path
   already gained this provenance through `CLASSIFICATION_REASON_CODES`, so a CR here must
   not re-scope that work. What remains is the ordinary `tc run` path
   (`client.py:215`) and the `bugfix`/`refactor` collapse in `client.py`'s maps. Any
   evidence half would still need reconciling with CR-DD-018's contract, and should first
   establish whether the existing governed-decision reason already reaches persisted route
   evidence — a question this record leaves open rather than answers.
2. **Classifier provenance and divergence.** The `"format"` disagreement between the model
   system prompt and the regex cascade, the `--plan`-versus-execution seam, and the
   timeout's measured 2× cost. Touches `classifier.py` and `run_plan.py`, and needs the
   `requests`/`urllib3` cause established before any timeout change.

Splitting them follows the standing correction-lane sequencing rule restated in CR-DD-017:
do not bundle unrelated evidence-fidelity fixes into one CR merely because they share a
category. They concern different properties — routing conservatism versus classification
provenance — and either could be accepted or rejected without the other.

**Track C remains untouched and unaddressed by this document.**
