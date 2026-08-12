# CR-DD-018: Structured Specialist-Offload Evidence Contract

## Status

- **Status:** Proposed.
- **Type:** Evidence / Observability (Governance-kernel — evidence and reconstruction),
  with a privacy-sensitive schema-design component.
- **Priority:** Design. Downstream of a read-only investigation of the
  `offload_recommended_for_local_only` branch conducted after CR-DD-017's
  implementation merged to `main` (`424bc7a66dc51d73a46dd0980969d8312c553d4e`). Does
  not reopen or amend CR-DD-017, CR-DD-016, CR-DD-013, or any routing/capability-
  resolution CR.
- **Implementation authority:** Not authorized. Explicitly withheld. Unlike CR-DD-017,
  this CR does not yet have a sufficiently settled payload/event contract to
  responsibly authorize code — the schema itself is the thing under review. This
  document grants no execution, integration, or standing authority.
- **Human approval requirement:** Explicit human review and approval of this Change
  Request is required before any implementation begins. Approval of this CR, if
  granted, records acceptance of the requirements/design contract only and does not
  by itself grant implementation authority. A separate, explicit human
  implementation-authority grant — scoped to a settled payload/event schema and
  bounded files — is required before any code change begins, per
  `docs/change/change_management.md` and CR-130's stage-separation rule.

## Scope

The evidence contract for `SpecialistRouter.route_task()`'s offload/handoff decision
(`triage_core/routers.py`) — the decision driven by `DangerDetector` risk level,
connectivity (`is_internet_available()`), or context size — as consumed by
`TriageClient.run_task` (`triage_core/client.py`) on:

1. the local-only blocked path (`offload_recommended_for_local_only`), and
2. the allowed/non-local-only offload path (the `route_decision.get("offload_recommended")`
   check later in the same method, whose "Router bypass" reason is also not durably
   persisted today — see Motivating Evidence).

This CR is about *what structured, privacy-safe fields should be durably recorded*
for this decision. It is not about the resilience-router/capability-resolution
decision (CR-DD-013/016/017's territory), and not about privacy enforcement or
routing behavior.

## Problem Statement

`TriageClient.run_task` contains two independent decision systems:

- **Resilience routing** (`choose_resilience_route`) decides *where* execution can
  safely/reliably run, given task class, sensitivity, and capability evidence.
- **`SpecialistRouter.route_task`** decides *whether* the task should be
  offloaded/handed off at all, based on risk keywords, connectivity, or context size —
  a judgment entirely independent of resilience routing or capability.

Today, the second decision can veto an otherwise-valid local-safe route chosen by the
first, but only the generic policy-gate outcome survives in the ledger. On the
local-only blocked path, a single `route_audit.reason_code=
offload_recommended_for_local_only` stands in for three structurally distinct causes
(high risk, medium risk while online, oversized context), each carrying a different
`route_decision["reason"]` string that is computed and then discarded one call site
away. The identical loss exists on the *allowed* path: `build_worker_result_payload`'s
persisted `"reason"` field is populated from the resilience router's reason, not from
`result["reason"]` (the specialist/danger string) — so even where the task *does* get
offloaded rather than blocked, the specialist's causal reason never reaches durable
evidence.

This is a genuine reconstruction gap, structurally similar in kind to what CR-DD-017
fixed, but not the same fix: the causal data lives in a different subsystem
(`SpecialistRouter`/`DangerDetector`, not `choose_resilience_route`), no existing
payload-builder or ledger-event shape already fits it, and part of the causal chain
(`internet_up`, the structured `DangerInfo` object) is not even returned to the caller
today.

There is also a privacy dimension CR-DD-017 did not have to consider. `SpecialistRouter`
builds its `"reason"` string from `DangerInfo.reasons`, and `DangerDetector.analyze`
accepts an optional `target_files` parameter whose matches are interpolated directly
into `reasons` (e.g. `"Target file is sensitive (...): {f}"`). The current call site
(`routers.py:43`) passes only the prompt, so today's strings contain bounded
pattern/category descriptions, not matched secret text or file paths — but that is an
**incidental fact about today's one call site, not a structural guarantee of the
`DangerDetector.analyze` API.** Nothing prevents a future caller from passing
`target_files`, at which point the same free-form `reasons` string would carry matched
file paths. This CR's design must not assume today's formatted reason string will
remain safe merely because `target_files` happens not to be passed today; persisting
`reasons` verbatim, under any field name, would create exactly the kind of schema that
both leaks under a future caller and needs replacing immediately after being added.

## Motivating Evidence

From the read-only investigation (main at `424bc7a`):

- **Reachable from real `tc run` today**, no test-only wiring required: a healthy
  local backend (resilience router picks `local_heavy`/`local_fast`/`deterministic`)
  plus a `--privacy local_only` prompt containing a flagged keyword (e.g. "sudo",
  "password", "rm -rf") or oversized data reaches this exact branch in production.
- **Discarded evidence:** `route_decision.get("reason")` is fetched at
  `client.py:118` and never read again on the local-only blocked branch
  (`client.py:160-163`). No `route_decision`-shaped event exists for this branch at
  all.
- **No reusable payload builder exists.** DD-017's fix called
  `build_route_decision_payload()` — already written, already used elsewhere. No
  analogous function exists for the specialist router's reason; a fix here requires
  new schema design, not a one-line reuse.
- **Cross-branch confirmation:** even the *allowed* offload path
  (`client.py:238-258`) does not persist the specialist's reason durably — only the
  resilience router's reason reaches `build_worker_result_payload`'s `"reason"` field.
  The specialist string only reaches the transient in-memory return value via
  `_merge_route_fields`.
- **Test coverage:** exactly one test exercises the local-only blocked branch
  (`tests/test_local_only_routing.py::test_local_only_packet_offload_recommended_fails_closed`).
  It mocks `route_task` to `return_value={"offload_recommended": True}` — no
  `"reason"` key at all — and passes no `ledger=` argument, so it makes zero
  assertions about ledger content. The blind spot is total absence of coverage, not a
  stale assertion.

## Design Question

**What is the smallest structured, privacy-safe, durable representation of a
`SpecialistRouter` offload decision?**

## Preferred Direction (design lean, not an implementation contract)

**This section is a preferred design direction, not a settled implementation
contract.** It nominates a shape and bounded candidate fields to argue against the
alternatives (stretching `route_audit`, overloading resilience `route_decision`), but
final event/payload naming, the exact field set, and the exact schema shape remain
subject to proposal review and may change materially before any implementation
authority is considered. Nothing below is final wording.

- A **separate specialist-decision evidence object/event**, rather than stretching
  either existing structure:
  - `route_audit.reason_code="offload_recommended_for_local_only"` stays exactly as
    the policy-gate explanation on the local-only branch — unchanged, not
    renamed/split/parameterized.
  - The resilience `route_decision` event is **not** overloaded with specialist-router
    fields — that would blur two independent decision systems into one schema.
- `SpecialistRouter` would expose bounded, structured cause fields instead of (or in
  addition to, pending review) its current free-form `"reason"` string. Candidate
  fields, offered to anchor review discussion rather than as final names:
  - `offload_reason_code`: a closed enum, e.g. `high_risk`, `medium_risk_online`,
    `context_limit_online`.
  - `risk_level`: `DangerDetector`'s existing `high`/`medium`/`low` vocabulary.
  - `risk_categories`: the existing bounded category set (`destructive_ops`,
    `system_modifications`, `secrets_and_auth`, `package_management`,
    `deployment_config`) — no free-form category text.
  - `internet_available`: boolean, where causally relevant (medium-risk and
    context-size triggers only).
  - `context_limit_exceeded`: boolean, not raw data length or content.
- **Explicit privacy exclusions, unconditionally and not contingent on today's call
  sites:** no prompt text, no `data` text, no raw matched substrings, no secrets, no
  `target_files` paths, and no free-form `DangerInfo.reasons` strings ever enter
  durable evidence under this contract — regardless of what future callers of
  `DangerDetector.analyze` or `route_task` pass in.

## Scope of the Design (this CR's deliverable)

This CR is a design/requirements contract. Its deliverable, if approved, is the
settled schema — not code. It must:

1. Define the exact field set and bounded vocabulary for each enum-like field above
   (or a reviewed alternative).
2. Define which `client.py` call sites the schema is intended to eventually cover —
   both the local-only-blocked path and the allowed/offload path — so that a schema
   designed for one call site does not need replacing when later extended to the
   other.
3. **Nominate, without authorizing, the local-only-blocked branch as a first
   candidate implementation slice**, consistent with CR-DD-017's sequencing. Design
   coverage of both call sites is not implementation authorization for both: approval
   of this CR's schema does not itself authorize implementing coverage for either
   call site, and does not bundle the two into one implementation grant. Any future
   implementation-authority grant must independently name and bound which call
   site(s) it covers; a grant scoped to the local-only-blocked branch does not extend
   to the allowed/offload path merely because both are described here, and the
   reverse holds equally.
4. Define the acceptance-test scenarios needed to prove the design closes the gap
   (below).

## Explicitly Out of Scope

- **Any code change.** `triage_core/client.py`, `triage_core/routers.py`,
  `triage_core/classifier.py`, and any test file are all out of scope for this CR.
  This document grants no implementation authority of any kind.
- **Any change to `choose_resilience_route`, capability resolution, or privacy
  enforcement.**
- **Any change to `DangerDetector`'s detection logic** (patterns, categories,
  thresholds) — this CR is about what is *persisted* from an existing decision, not
  how the decision is made.
- **Persisting `DangerInfo.reasons`, prompt text, `target_files` paths, or any other
  free-form/raw content verbatim**, under any field name.
- **CR-DD-015A/B, CR-130, or any other independent evidence-fidelity or governance
  lane** — not reopened, not depended upon.
- **Extending this design to any branch or subsystem not named in Scope above.**

## Acceptance Criteria (design-review level — no code exists to test yet)

- [ ] The proposal defines a complete, closed field set for the specialist-offload
      evidence contract, with an explicit bounded vocabulary for every enum-like
      field (`offload_reason_code`, `risk_level`, `risk_categories`).
- [ ] The proposal explicitly and unconditionally excludes prompt text, raw matched
      substrings, secrets, file paths, and free-form `DangerInfo.reasons` from every
      durable field it defines, and states this exclusion does not rest on any
      assumption that today's call sites (e.g. `route_task()` not passing
      `target_files`) will remain unchanged.
- [ ] The proposal states which `client.py` call sites the schema is intended to
      cover (local-only-blocked and allowed/offload), confirms the schema shape does
      not depend on which call site emits it first, and states explicitly that
      describing both call sites here does not authorize implementing either — any
      future implementation-authority grant must independently name and bound which
      call site(s) it covers.
- [ ] The proposal defines four acceptance-test scenarios, each specifying real
      (non-mocked) inputs sufficient to prove the causal families are distinguishable
      in durable evidence once implemented:
      1. **High-risk case:** a prompt matching a high-risk category (e.g.
         `destructive_ops`) resolves to specialist-offload evidence identifying the
         bounded risk cause (`offload_reason_code=high_risk`, correct
         `risk_categories`).
      2. **Medium-risk + internet-available case:** a prompt matching a medium-risk
         category with `is_internet_available()` true distinguishes the
         connectivity-dependent offload (`offload_reason_code=medium_risk_online`,
         `internet_available=true`) from the medium-risk *offline fallback* branch
         (which does not offload today and is out of this CR's scope to change).
      3. **Large-context + internet-available case:** data exceeding the context
         threshold with internet available distinguishes context-pressure offload
         (`offload_reason_code=context_limit_online`, `context_limit_exceeded=true`)
         from the risk-driven cases.
      4. **Privacy case:** proves no prompt substring, no `data` substring, and no
         raw `DangerInfo.reasons` text appears anywhere in the persisted evidence for
         any of the above three scenarios.
- [ ] No implementation authority is granted by this CR. A separate, explicit,
      scoped implementation-authority grant — naming exact files — is required before
      any code change begins, per `docs/change/change_management.md` and CR-130.

## Non-Goals

- Implementing the schema now.
- Changing `DangerDetector`'s detection logic, patterns, or thresholds.
- Changing any routing, capability-resolution, or privacy-enforcement behavior.
- Resolving CR-DD-015A/B, CR-130, or any other independent evidence-fidelity or
  governance lane.
- Persisting the current free-form `route_decision["reason"]` string verbatim, as a
  fix — explicitly rejected in favor of the bounded structured fields above.

## Sequencing

Downstream of a read-only investigation of `offload_recommended_for_local_only`
conducted after CR-DD-017's implementation merged to `main`
(`424bc7a66dc51d73a46dd0980969d8312c553d4e`). Independent of CR-DD-015A/B (not
authorized, not reopened here), CR-130 (governance/authority semantics, not evidence
schema), and CR-DD-016. Does not reopen or amend CR-DD-017 — DD-017's own branch and
tests remain untouched by this proposal.

## Namespace Census

Verified via `git rev-parse --branches --remotes` and `git ls-tree` across every
local and remote branch/tag immediately before drafting: the highest existing
`CR-DD-0NN` identifiers anywhere in the repository are `CR-DD-016` and `CR-DD-017`.
`CR-DD-015`/`015A`/`015B` do not exist as records anywhere (consistent with
`docs/operations/daily-use-evidence-window-2026-08-02.md`). This CR takes
`CR-DD-018`.
