# CR-DD-018: Structured Specialist-Offload Evidence Contract

## Status

- **Status:** Proposed — design-settlement candidate. The original proposal deliberately
  left the event/payload schema unsettled; this amendment records the settled design
  contract produced by the read-only schema/design review. It remains `Proposed`: the
  settled contract is itself the thing now under review, and no code exists.
- **Type:** Evidence / Observability (Governance-kernel — evidence and reconstruction),
  with a privacy-sensitive schema-design component.
- **Priority:** Design. Downstream of a read-only investigation of the
  `offload_recommended_for_local_only` branch conducted after CR-DD-017's
  implementation merged to `main` (`424bc7a66dc51d73a46dd0980969d8312c553d4e`). Does
  not reopen or amend CR-DD-017, CR-DD-016, CR-DD-013, or any routing/capability-
  resolution CR, and does not rewrite CR-078 or CR-082.
- **Implementation authority:** Not authorized. Explicitly withheld, including after
  this design settlement. Settling the schema removes the original reason implementation
  could not responsibly be authorized; it does not itself authorize implementation. This
  document grants no execution, integration, signing-path, or standing authority.
- **Human approval requirement:** Explicit human review and approval of this Change
  Request is required before any implementation begins. Approval of this CR, if
  granted, records acceptance of the requirements/design contract only and does not
  by itself grant implementation authority. A separate, explicit human
  implementation-authority grant — scoped to bounded files and naming which call
  site(s) it covers — is required before any code change begins, per
  `docs/change/change_management.md` and CR-130's stage-separation rule. Merge of the
  design-settlement amendment PR records the settled design contract only. It does not
  move this CR out of `Proposed`, constitute design acceptance, grant implementation
  authority, or authorize the separately governed signing path described below.

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
offload_recommended_for_local_only` stands in for four structurally distinct causes
(explicit safety handoff, high risk, medium risk while online, oversized context), each
carrying a different `route_decision["reason"]` string that is computed and then
discarded one call site away. The identical loss exists on the *allowed* path: `build_worker_result_payload`'s
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

**The ledger's persistent-privacy invariant is defense in depth, not the primary
guarantee.** `TaskLedger.append_event()` calls `assert_persistent_privacy_safe()`
(`triage_core/privacy_invariants.py`) on every payload, and that check is *both* a
forbidden-key denylist (`prompt`, `data`, `content`, `token`, `secret`, and similar) and
a recursive scan of string *values* for SSN, email, phone, secret-key, precise-location,
and Luhn-valid payment-card patterns. It is therefore stronger than a key-name check.
But it is pattern-limited and not provenance-aware: arbitrary input-derived prose, file
paths that trip no detector, and other free-form reason material pass it cleanly under
any field name not on the denylist. The bounded specialist schema below is consequently
the primary privacy control for this event; the ledger scanner is a secondary net that
must not be relied on to catch a schema mistake.

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

## Settled Design Contract

This section replaces the original provisional "preferred direction." It records the
settled contract produced by the read-only schema/design review. It remains subject to
design acceptance, and it grants no implementation authority.

### Event boundary

- **Event type: `specialist_offload_decision`** — a dedicated event, not a stretch of
  `route_audit` and not a fold into the resilience `route_decision`.
  - `route_audit.reason_code="offload_recommended_for_local_only"` stays exactly as the
    policy-gate explanation on the local-only branch — unchanged, not
    renamed/split/parameterized.
  - The resilience `route_decision` event is **not** overloaded with specialist-router
    fields — that would blur two independent decision systems into one schema.
- **The event is policy-outcome-agnostic.** It records what `SpecialistRouter`
  concluded and why. It never records whether privacy policy subsequently blocked the
  task or handed it off; that outcome already lives in the neighboring `route_audit`
  and `worker_result` events, correlated by `task_id` and event order.
- **`TaskLedger.append_event()` remains the transport.** The ledger does not restrict
  event-type names, so no ledger schema migration is required.
- **Because generic append enforces no closed payload, the eventual implementation MUST
  use a dedicated builder/validator** that rejects unknown fields, invalid enum values,
  and noncanonical category lists before calling the ledger — the same discipline
  `triage_core/route_worker_ledger.py` already demonstrates with its closed
  payload-field sets. Exact module placement is deliberately **not** settled here.

### Closed payload (discriminated by `offload_reason_code`)

Common fields, always present:

- `offload_reason_code` — exactly one of:
  `high_risk | safety_handoff | medium_risk_online | context_limit_online`
- `risk_level` — exactly one of `low | medium | high`. Always present: `route_task()`
  evaluates `DangerDetector.analyze()` before every offload branch, so risk is assessed
  for every decision this event can describe. Reaching the context-size branch means
  the high and medium branches did not return, i.e. `risk_level="low"`.
- `risk_categories` — always present; **sorted and deduplicated**, restricted to
  `destructive_ops | system_modifications | secrets_and_auth | package_management |
  deployment_config`. An empty list is valid. Canonical ordering is required because
  `DangerDetector` accumulates categories in a `set` before converting to a list, so raw
  ordering is not a stable evidence property — and would become a correctness problem if
  this event is signed later.

Variant-required fields:

| `offload_reason_code` | `internet_available` | `context_limit_exceeded` |
|---|---|---|
| `high_risk` | absent | absent |
| `safety_handoff` | absent | absent |
| `medium_risk_online` | required, `true` | absent |
| `context_limit_online` | required, `true` | required, `true` |

Fields not permitted by a variant MUST be **absent, never `null`**. A `null` placeholder
would reintroduce exactly the "absent means what?" ambiguity this discriminated shape
exists to remove.

### Discriminant normalization (`safety_handoff` / `high_risk` overlap)

`route_task()`'s first branch is `risk_level == "high" OR category == "safety_handoff"`,
so both conditions can hold simultaneously and a single discriminant needs an explicit
rule:

> If `category == "safety_handoff"`, record `offload_reason_code="safety_handoff"`.
> Otherwise normalize in order: `high_risk`, then `medium_risk_online`, then
> `context_limit_online`.

This does not erase coincident high risk — `risk_level="high"` and the bounded
`risk_categories` still preserve it. What it prevents is the explicit safety-handoff
trigger vanishing from evidence whenever both conditions are true.

`safety_handoff` is included now, though it is **not presently reachable through
`TriageClient`**: `TaskClassifier.CATEGORIES` contains eight values and
`safety_handoff` is not among them (the nearest is `blocked_or_high_risk`). The
`SpecialistRouter.route_task()` API nonetheless accepts it explicitly, and
`triage_core/context_budget.py` already carries a `safety_handoff` task-class budget
entry. Recording it now avoids designing an event whose vocabulary needs extending the
moment that trigger becomes reachable.

### Deliberately excluded from the payload

- **No raw task category.** `route_task()` accepts a plain string, so persisting it to
  explain `safety_handoff` would quietly convert a bounded schema back into an unbounded
  string surface. The bounded reason code carries that meaning instead.
- **No prompt text, no `data` text, no raw matched substrings, no secrets, no
  `target_files` paths, and no free-form `DangerInfo.reasons` strings** — unconditionally,
  and not contingent on what today's call sites happen to pass to
  `DangerDetector.analyze` or `route_task`.

### Event ordering

Sharing a payload schema across both call sites does not imply a shared event sequence.
Exact placement per call site:

- **Local-only blocked path:**
  `route_audit(blocked)` → `specialist_offload_decision` → raise
  `LocalRouteUnavailableError`
- **Allowed specialist-offload path:**
  `route_audit(allowed)` → `route_decision` → `specialist_offload_decision` →
  `worker_result(handoff_required)`

This preserves the distinction between specialist cause, resilience cause, and eventual
policy/execution outcome.

### Integrity invariant

> A required specialist-evidence persistence failure MUST propagate before worker
> execution, fallthrough, `LocalRouteUnavailableError`, or a successfully recorded
> `handoff_required` outcome is emitted. A future explicitly requested signing failure
> follows the same rule.

On the local-only blocked path this failure must not be masked as
`LocalRouteUnavailableError`; on the allowed path it must not proceed to emit
`worker_result` as though the causal evidence chain completed. One rule for both sites:
an evidence-integrity failure cannot turn into execution, fallthrough, or a
successfully recorded routing outcome.

### Signing decision

Recorded in the CR-078 coverage-table style. **CR-078 and CR-082 are historical records
and are not rewritten by this CR.**

| Event type | Signing status | Capability | Reason |
|---|---|---|---|
| `specialist_offload_decision` | Intentionally unsigned for the first implementation slice | Not assigned to that slice | Dedicated signing endpoint is `specialist_offload_decision:sign`. `route_decision:sign` MUST NOT be borrowed — a signature under that capability would misattribute one subsystem's evidence to another subsystem's authority. Signing implementation requires a separately governed verification/readiness path, following the CR-078 → CR-082 precedent in which a signed event type arrives together with its dedicated helper, capability, and operator-facing verification rather than silently widening an existing signature's meaning. |

**Unenabled/unprovisioned signing is not a failure.** Before specialist signing exists
or has been enabled, `specialist_offload_decision` is intentionally unsigned: no signing
capability is required, and there is no runtime error merely because
`specialist_offload_decision:sign` has not been provisioned. A future signing
implementation should include a readiness/preflight path capable of surfacing an
unprovisioned signer *before* task execution.

**A failure of explicitly requested signing is an integrity failure.** Once signing is
explicitly requested, a missing `specialist_offload_decision:sign` capability, a revoked
identity, a cryptographic failure, or any other signing failure is an
integrity/authorization failure. It MUST propagate under the integrity invariant above.
The system MUST NOT silently downgrade an explicitly requested signed event to unsigned.

## Scope of the Design (this CR's deliverable)

This CR is a design/requirements contract. Its deliverable is the settled schema — not
code. The Settled Design Contract above now discharges that deliverable:

1. The exact field set and bounded vocabulary for every enum-like field is defined.
2. Both `client.py` call sites the schema covers — local-only-blocked and
   allowed/offload — are named, with per-site event ordering settled, so a schema
   implemented at one site does not need replacing when later extended to the other.
3. **The local-only-blocked branch is nominated, without authorization, as the first
   candidate implementation slice**, consistent with CR-DD-017's sequencing. Design
   coverage of both call sites is not implementation authorization for both: approval
   of this CR's schema does not itself authorize implementing coverage for either
   call site, and does not bundle the two into one implementation grant. Any future
   implementation-authority grant must independently name and bound which call
   site(s) it covers; a grant scoped to the local-only-blocked branch does not extend
   to the allowed/offload path merely because both are described here, and the
   reverse holds equally. Describing the allowed path and its ordering above
   authorizes nothing.
4. The acceptance-test scenarios needed to prove the design closes the gap are defined
   below.

**Future implementation surface is wider than one slice.** The first implementation
slice is expected to touch `triage_core/client.py`, `triage_core/routers.py`, and
tests. The separately governed signing path described above would additionally reach
`triage_core/task_ledger.py` (dedicated helper, capability constant, signature-payload
wrapper), operator-facing verification, and operator identity provisioning. That
breadth is recorded here so it is visible before any implementation allowlist is
proposed — it is not an allowlist and authorizes nothing.

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

- [x] The proposal defines a complete, closed field set for the specialist-offload
      evidence contract, with an explicit bounded vocabulary for every enum-like
      field (`offload_reason_code`, `risk_level`, `risk_categories`). *Satisfied by the
      Settled Design Contract: a discriminated payload keyed by `offload_reason_code`,
      with per-variant required/absent fields and no `null` placeholders.*
- [x] The proposal explicitly and unconditionally excludes prompt text, raw matched
      substrings, secrets, file paths, and free-form `DangerInfo.reasons` from every
      durable field it defines, and states this exclusion does not rest on any
      assumption that today's call sites (e.g. `route_task()` not passing
      `target_files`) will remain unchanged. *Satisfied, and extended to exclude the raw
      task category string; the ledger's persistent-privacy check is recorded as
      pattern-limited defense in depth rather than the primary guarantee.*
- [x] The proposal states which `client.py` call sites the schema is intended to
      cover (local-only-blocked and allowed/offload), confirms the schema shape does
      not depend on which call site emits it first, and states explicitly that
      describing both call sites here does not authorize implementing either — any
      future implementation-authority grant must independently name and bound which
      call site(s) it covers. *Satisfied, with per-site event ordering settled
      separately from the shared payload shape.*
- [x] The signing posture is explicitly settled rather than left accidental: a
      dedicated `specialist_offload_decision:sign` endpoint is named, borrowing
      `route_decision:sign` is prohibited, the first slice is recorded as intentionally
      unsigned in CR-078 coverage-table style, and unenabled/unprovisioned signing is
      distinguished from failure of an explicitly requested signing operation.
- [x] A single integrity invariant covers both call sites: a required
      specialist-evidence persistence failure — and any explicitly requested signing
      failure — propagates before worker execution, fallthrough,
      `LocalRouteUnavailableError`, or a successfully recorded `handoff_required`
      outcome.
- [x] The proposal defines four acceptance-test scenarios that exercise the real
      `SpecialistRouter.route_task` / `DangerDetector` decision logic rather than
      mocking the specialist decision result. External connectivity may be
      deterministically controlled at the `is_internet_available()` boundary; tests
      MUST NOT depend on ambient network availability.
      1. **High-risk case:** a prompt matching a high-risk category (e.g.
         `destructive_ops`) resolves to specialist-offload evidence identifying the
         bounded risk cause (`offload_reason_code=high_risk`, correct
         `risk_categories`, asserted in canonical sorted/deduplicated order).
      2. **Medium-risk + internet-available case:** a prompt matching a medium-risk
         category, with `is_internet_available()` deterministically controlled true at
         the external boundary, distinguishes the connectivity-dependent offload
         (`offload_reason_code=medium_risk_online`, `internet_available=true`) from the
         medium-risk *offline fallback* branch (which does not offload today and is
         out of this CR's scope to change).
      3. **Large-context + internet-available case:** data exceeding the context
         threshold, with `is_internet_available()` deterministically controlled true at
         the external boundary, distinguishes context-pressure offload
         (`offload_reason_code=context_limit_online`, `context_limit_exceeded=true`)
         from the risk-driven cases.
      4. **Privacy case:** uses unique sentinel content in the prompt and `data` and
         proves that no input-derived free-form sentinel content, no raw matched
         content, and no raw `DangerInfo.reasons` text appears anywhere in persisted
         evidence for any of the above scenarios. Bounded contract vocabulary is not
         treated as leakage merely because the same literal token happens to occur in
         an input.

      **Coverage note for `safety_handoff`:** that variant is not reachable end-to-end
      through `TriageClient`, because `TaskClassifier` cannot emit the category. How to
      cover it — a direct `SpecialistRouter.route_task()` unit test, or accepting it as
      designed-but-uncovered until the trigger becomes reachable — is left to the
      implementation CR and is not settled here.
- [x] No implementation authority is granted by this CR. A separate, explicit,
      scoped implementation-authority grant — naming exact files and which call
      site(s) it covers — is required before any code change begins, per
      `docs/change/change_management.md` and CR-130. The signing path is separately
      governed and is likewise not authorized here.

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
