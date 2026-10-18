# CR-134: Public Export Admission Contract (`public_export_v0`)

## Status

- **Status:** Proposed. Proposal-only documentation.
- **Type:** Governance kernel — privacy and provenance; identity and authority;
  capability and effect bounds; review and human control. Classified under the
  [Backlog Scope Taxonomy](../../current_backlog.md) by the invariant it strengthens:
  *no content leaves the local boundary for an external model recipient except the exact
  bytes an operator was shown and confirmed, under a deterministic eligibility decision
  recomputed at release.*
- **Evidence baseline:** `main` at `ede8ef154d916389dd140345b256b46fd7b19eaa`. Every
  repository fact below was observed at that commit. Re-verify when the pin changes.
- **Proposal drafting authority:** Granted by the human operator on 2026-10-18 for this
  single document. Recorded verbatim in Authority Record below.
- **Owner decisions:** Two recorded on 2026-10-18; see Owner Decisions. They settle two
  design questions. They do not constitute design acceptance.
- **Proposal acceptance:** Pending review of this completed document.
- **Design acceptance:** Pending. Explicitly withheld until the completed proposal is
  reviewed.
- **Implementation authority:** Not granted.
- **Implementation acceptance / merge / release / closeout:** Not granted.

### Lifecycle state

| Stage | State |
|---|---|
| identifier allocation | CR-134, allocated by the operator after a census of `docs/change/requests/` at `ede8ef1` (highest numeric CR-133; no existing delegation or export CR) |
| proposal drafting | granted, single document |
| owner decisions | two recorded (see Owner Decisions) |
| proposal acceptance | pending |
| design acceptance | pending |
| implementation authority | not granted |
| implementation acceptance | not granted |
| merge authority | not granted |
| release authority | not granted |
| closeout | not granted |

## Scope

Exactly one file: this document.

No backlog entry, change-log entry, architecture page, code, test, fixture file, schema,
CLI surface, configuration, ledger, credential, or workflow change is made or authorized.
Backlog and change-log linkage for this CR, if wanted, requires its own grant.

## Human Approval Requirement

No implementation, test, fixture-file, or CLI work may proceed on the strength of this
document. Proposal acceptance, design acceptance, implementation authority,
implementation acceptance, merge, release, and closeout are separate human decisions under
[change management](../change_management.md). The two owner decisions recorded below
settle design questions only; neither carries any later stage.

## Authority Record

The operator's grant of 2026-10-18, recorded verbatim:

> **Authorized now:** Draft the single proposal document under CR-134, incorporating these
> corrections and preserving the v0.4 fixtures, non-claims, unresolved implementation
> questions and evidence requirements.
>
> **Not authorized:** Implementation, tests or fixture-file changes, CLI changes,
> credential operations, ledger mutations, PR merge, release or deployment.
>
> Record the two approved owner decisions in the CR, but leave overall design acceptance
> pending review of the completed proposal. Preserve the existing NIST/ISO assessment and
> the separate PR #179 reconciliation requirement.

The grant names the file path
`docs/change/requests/CR-134-public-export-admission-contract.md`. It does not name
publication (push or pull request); in this repository publication has been treated as a
separately granted action (see the CR-DD-012B publication record), so this document is
committed locally only until publication is separately granted.

## Owner Decisions

Recorded 2026-10-18. Each settles one design question for this profile.

1. **Proposer-only `denied_actions`.** A parent manifest's `denied_actions` bound the
   proposing agent and the work it may *request*. They are not read as enforced bounds on
   what an external recipient does. Exception: a parent that denies `network_access` or
   `external_api_call` makes every export `ineligible` (an agent forbidden from egress does
   not get its material sent out through the operator). No downstream enforcement is
   claimed anywhere in this profile.
2. **File-by-default staging.** The only default staging kind is a file written to an
   explicitly selected, trusted local destination. Clipboard staging is an explicit
   opt-in.

The operator also allocated identifier CR-134 and confirmed, independently, the two CR-095
validator observations recorded under Established Facts.

## Problem Statement

A workflow in which one external assistant (a coordinator) proposes work and another (a
specialist) performs it is, from TriageCore's side, a sequence of **exports**: each
external party is a recipient of whatever it is shown. A gate placed between the
coordinator and the specialist cannot govern what the coordinator already received, and a
specialist's returned analysis does not inherit permission to be passed onward.

TriageCore has mechanisms adjacent to this — external-safe packets, admission evidence,
task envelopes, and authority manifests — but none of them is an export gate, and several
cannot be promoted into one as they stand (Established Facts). Provider-side access
programs (Anthropic's Cyber Verification Program, OpenAI's Daybreak) further mean that a
recipient surface's effective safeguard mode is an account- or request-level property that
TriageCore cannot observe on a chat surface and must not assume.

### Evidence anchor

All facts observed read-only on `main@ede8ef1` in a clean worktree. Commands are given so
a reviewer can reproduce them rather than trust this record.

### Established facts

1. `triage_core/admission.py::admission_evidence_from_mapping` validates presence and type
   only. It accepts `admitted: true` together with `approval_required: true`,
   `approval_used: false`, a non-empty `blocked_reasons`, and an unknown `access_tier`
   field. This is consistent with its documented structure-only contract, but it means the
   parser cannot serve as an admission gate.
2. `ExternalRuntimeAdmissionEvidence` is defined twice with different shapes, in
   `triage_core/admission.py` and `triage_core/external_runtime_adapter.py`. This CR
   extends neither; the duplication is a separate finding.
3. `triage_core/task_envelope.py::task_envelope_from_mapping` reads known fields and
   silently ignores unknown ones.
4. `TaskPacket`, `VerifiedTaskPacket`, and `ExternalSafeTaskPacket` are plain, mutable
   `@dataclass`es (`task_packet.py:14`, `safe_task_packet.py:13,21`). Holding an
   `ExternalSafeTaskPacket` is not a binding between a scan result and unchanged content.
5. `make_external_safe_packet` already rejects any packet whose `data_class` is not
   `public`, or that carries PII, sensitive content, precise location, a redaction
   requirement, or `external_model_allowed = false`. These are reusable criteria, not an
   export binding.
6. `triage_core/agent_authority.py::validate_authority_manifest` (CR-095):
   - accepts unknown top-level fields silently (the reviewer example manifest with
     `allowed_recipients`, `max_turns`, and `tool_prohibitions` added validates with zero
     issues);
   - treats `allowed_actions` as an open vocabulary (any non-empty string; only a literal
     `"*"` is rejected);
   - has no recipient, destination, data-class, task-risk, or numeric-limit dimension;
   - accepts an injectable `now`, so expiry can be evaluated at a chosen time.
7. The CR-DD-012B construction seam already provides the binding pattern this CR needs:
   `GovernedRunInputSnapshot` and its components are `@dataclass(frozen=True, slots=True)`
   with `sha256:` digests, and `GovernedDecision` carries a domain-separated, verifiable
   `decision_id` (`governed_decision.py:287–379`). Source locations are recorded as
   domain-separated locator digests (`governed_run_snapshot.py:106`), not raw paths.
8. The identity registry loader returns an empty registry when the registry file is
   absent (`agent_identity.py:290–293`). CR-097's fail-closed categories cover unreadable
   or malformed registry data, not absence.

Reproduction (read-only):

```bash
git rev-parse HEAD            # ede8ef154d916389dd140345b256b46fd7b19eaa
git status --short            # empty
python -I -c "import sys; sys.path.insert(0,'.'); \
from triage_core.admission import admission_evidence_from_mapping as m; \
print(m({'admitted':True,'execution_performed':False,'approval_required':True, \
'approval_used':False,'requested_runtime':'r','requested_capability':'c', \
'blocked_reasons':['x'],'manifest_or_source_evidence':'y','access_tier':'z'}))"
```

## Objective

Define one manual-staging export profile, `public_export_v0`, in which TriageCore:

- decides whether exact public content may be **staged locally** for an operator to
  transfer by hand to one named external chat surface;
- binds that decision to the content, recipient, scope, operations, classification, risk,
  outcome, reasons, policy, and time inputs;
- shows the operator the exact bytes and the decision before confirmation;
- recomputes the decision and re-checks time at release; and
- records what it observed locally, and only that.

TriageCore decides what may be exported and under what bounds. Models propose work and
analyze admitted material. The operator retains approval authority. TriageCore does not
rank models.

## Design Principles

1. **Every external party is a recipient.** Each leg — including returning one
   recipient's output to another — is a separate export with its own eligibility record.
2. **Requests may only tighten.** No proposal field can loosen a policy ceiling, a parent
   bound, or a classification.
3. **Attested is not observed.** Operator statements are recorded as attested; provider
   behaviour is never inferred from them.
4. **No downstream enforcement claims.** Restrictions on what a recipient does are
   instructions, not controls.
5. **Release repeats the decision.** Staging never relies on an earlier eligibility result
   alone.
6. **Fail closed, and say what happened.** Uncertain staging is reported as uncertain,
   never as "not staged".

## Relationship to Existing Contracts

| Existing mechanism | Treatment under this CR |
|---|---|
| CR-DD-012B snapshot / decision pattern | **Reused as the pattern** for freezing inputs and deriving a domain-separated identifier. No change to those modules. |
| `make_external_safe_packet` criteria | **Reused as criteria** for the public data-class floor. Not used as the binding. |
| `ProjectSteward` and `policies/cybernetic_ecology_boundary.yaml` | **Reused** to produce review triggers on payload text, with its documented fallback semantics. A match is a review trigger, not a confidentiality finding. |
| Privacy scanner (`scan_task_packet`) | **Reused** over the payload text. A non-match is recorded as `no_configured_finding`. |
| CR-095 authority manifest | **Consumed as the parent format**, with export-specific strict closure and normalization (Parent Normalization). The validator is not modified. |
| CR-044 external runtime manifest | Not used in v0; recipient surfaces are described by policy profiles. |
| `admission_evidence_from_mapping` / `ExternalRuntimeAdmissionEvidence` | **Not extended.** Structure-only parsing is not an admission gate. |
| CR-YK-001 / CR-YK-002 | Not integrated. A WebAuthn assertion over the eligibility identifier is the deferred authenticated-approval upgrade. |
| CR-AR-001 (Proposed, unauthorized) | Aligned in spirit with its R3 "staged external" tier (preparation, then human approval at the release boundary). No dependency is taken. |
| NIST/ISO assessment M04 (trusted endpoint policy) | The recipient allowlist here and M04's endpoint trust policy should be **one** trusted destination policy, designed once (see Relationship to the NIST/ISO Assessment). |

## Profile Scope

`public_export_v0` covers exactly: one payload file, one recipient chat surface, manual
transfer by the operator after local staging. It makes no network call, invokes no
provider API, and starts no MCP server.

### Surfaces

| Surface | v0 treatment |
|---|---|
| `claude_ai_web` (Claude consumer chat) with operator-attested grant state `none` for every relevant program | Eligible |
| ChatGPT chat (web or Android) with operator-attested grant state `none` | Eligible |
| Either surface with grant state `granted` or `unknown` | `ineligible` — no documented per-request standard-mode mechanism on these surfaces |
| Claude Console / API workspace | `excluded_from_v0` |
| OpenAI Responses API | `excluded_from_v0` |
| Codex CLI or app | `excluded_from_v0` |
| Desktop local STDIO MCP plugins | `excluded_from_v0` |

Exclusion is a scope statement for v0. Whether an excluded surface is available, or could
satisfy a later profile, is a separate question recorded under Deferred Work.

## Trust Boundary and Input Origins

| Input | Origin | Basis assigned |
|---|---|---|
| Payload bytes | One file read once into an immutable buffer | `observed_local` |
| Proposal | Untrusted file | `proposal_declared` |
| Parent manifest | File bytes read once and frozen; parsed from those bytes | `parent_declared` |
| Policy | Local operator-maintained file, read once and frozen; digest displayed at confirmation | `operator_policy` |
| Access attestations | Interactive prompts in the exporter only, stamped by the trusted clock at collection | `operator_attested` |
| Clock | Local wall clock (injectable in tests), cross-checked against a monotonic clock within one invocation | `observed_local` |

Basis vocabulary (closed): `observed_local`, `operator_attested`, `operator_policy`,
`parent_declared`, `proposal_declared`, `provider_documented`, `provider_reported`,
`unknown`. The exporter assigns basis internally. No input can set or raise a basis.

Untrusted means untrusted regardless of form: no eligibility record, approval record,
attestation, or decision presented as a file is ever accepted as authoritative, however
well-formed or correctly hashed.

Stated limits: the operator controls the wall clock; the policy file and payload are local
files that any process with write access to them could alter before freezing. The display
of the policy digest and payload at confirmation is the control for that window.

### Strict schema closure

Every structured input — proposal, parent manifest (for this profile), and policy — is
validated against a closed field allowlist **at every nesting level**. Any field not in the
allowlist, at any depth, makes the export `ineligible` with `unknown_field`. A secondary
list of forbidden names (`basis`, `attestation`, `attestations`, `approval`,
`operator_decision`, `admitted`, `outcome`, `eligibility`, `eligibility_id`,
`review_resolution`) produces the more specific `forbidden_field`; it is a diagnostic aid,
not the control. Closure is the control.

Proposal shape (closed; all fields required unless marked optional):

```json
{
  "schema": "triagecore.export_proposal.v0",
  "proposal_id": "<uuid>",
  "payload_path": "<repo-relative path>",
  "recipient": {"provider": "anthropic", "surface": "claude_ai_web"},
  "model_selection": "<string, optional>",
  "requested_operations": ["read_provided_text", "write_critique"],
  "recipient_instructions": ["<text>", "..."],
  "declared_data_class": "public",
  "declared_task_risk": "low",
  "requested_expiry": "<RFC 3339 timestamp>",
  "parent_manifest_path": "<repo-relative path>"
}
```

The payload must decode as strict UTF-8; otherwise `payload_not_utf8`.

## Records

| Record | Producer | Persisted | Ever accepted as an input |
|---|---|---|---|
| `ExportProposal` | Model or operator | By its author | Yes — and only this, as untrusted data |
| `ExportEligibility` | TriageCore, computed | As metadata-only evidence | **Never**; recomputed at release |
| `OperatorExportApproval` | Operator channel, within one invocation | As metadata-only evidence | **Never** |
| `ExportIntent` | Exporter, before staging | Yes (fsynced) | Only by audit, never by release |
| `ExportRelease` | Exporter, after staging | Yes | Only by audit, never by release |

**Persisted approval records are never consumed.** No input path reads one back.

Intent and release records are new persisted record kinds. They route through strict
mapping validation and the privacy invariant (control-plane checklist rows 2, 8, 9), carry
no payload text, record paths only as locator digests, and are written only to an
explicitly named evidence directory with no default location (row 7).

## Operator Workflow (normative order)

1. **Freeze inputs.** Read the payload, proposal, parent manifest, and policy each once
   into immutable buffers and compute their digests.
2. **Collect attestations.** Through the operator channel, ask which account is open on the
   named surface and its grant state for each relevant program (`none` / `granted` /
   `unknown`). Stamp each answer with `observed_at` from the trusted clock.
   - An implementation may refuse before this step when a structural check already makes
     the export `ineligible`; that record marks attestations `not_collected`.
3. **Evaluate.** Capture `evaluation_time`, compute the eligibility body and its
   identifier. This order guarantees `observed_at ≤ evaluation_time` without weakening the
   future-dated-attestation guard.
4. **Stop if ineligible.** Display the eligibility record and its reasons. Offer no
   confirmation prompt.
5. **Display.** Show the complete payload, losslessly escaped (Payload Display), its byte
   length and SHA-256, the final eligibility record, and the policy digest.
6. **Confirm.** For `review_required`, the operator acknowledges exactly the set of review
   triggers. Capture `confirmed_at`.
7. **Release checks.** Perform every check in Release-Time Checks.
8. **Write intent.** Write and fsync `ExportIntent`. If this fails, refuse with no payload
   staged.
9. **Stage** (Staging and Destination Security).
10. **Record.** Write `ExportRelease` with the outcome.

## Eligibility Record

Body (closed; identifier derived from it):

```json
{
  "schema": "triagecore.export_eligibility.v0",
  "profile": "public_export_v0",
  "evaluation_time": "<RFC 3339>",
  "proposal_digest": "sha256:…",
  "payload": {"digest": "sha256:…", "length": 0, "locator_digest": "sha256:…"},
  "recipient": {"provider": "anthropic", "surface": "claude_ai_web",
                "model_selection": {"value": "…", "basis": "proposal_declared"}},
  "access": {
    "credential_scope": {"value": "account:ordinary-1", "basis": "operator_attested",
                         "observed_at": "…"},
    "mode_mechanism": "none_documented",
    "grants": [{"program": "anthropic_cvp", "value": "none",
                "basis": "operator_attested", "observed_at": "…"}]
  },
  "operations": [{"name": "write_critique", "parent": "allowed",
                  "approval_gate": "none"}],
  "restrictions": [{"text_digest": "sha256:…", "class": "recipient_instruction"}],
  "data_class": {"declared": "public", "computed": "public", "effective": "public",
                 "scanner": "no_configured_finding"},
  "task_risk": {"declared": "low", "computed": "low", "effective": "low"},
  "parent": {"bytes_digest": "sha256:…", "agent_id": "…", "expires_at": "…",
             "revocation_status": "active", "basis": "parent_declared"},
  "outcome": "eligible_for_operator_reviewed_export",
  "reason_codes": [],
  "review_triggers": [],
  "policy": {"version": "…", "digest": "sha256:…"},
  "triagecore_commit": "…",
  "valid_until": "<RFC 3339>"
}
```

- `eligibility_id = "sha256:" + SHA-256(domain_tag ‖ canonical(body))`, with a
  profile-specific domain tag, following the `GovernedDecision` identifier pattern.
- `valid_until` = the earliest of: `requested_expiry`; the earliest attestation
  `observed_at` plus the policy freshness ceiling; the parent's `expires_at`; and
  `evaluation_time` plus the policy's maximum eligibility duration.
- Changing any bound input — recipient, surface, scope, operations, restrictions,
  classification, risk, outcome, reasons, policy, payload, parent, or attestations —
  changes the identifier. An approval for one recipient therefore cannot release to
  another.

## Decision Rules and Precedence

Effective data class and task risk are the stricter of declared and computed. A
classification can be raised, never lowered.

1. **`ineligible`** — not overridable by review; no confirmation is offered. Triggers
   include:
   - `nonpublic_content` (effective class is not `public`);
   - `unknown_field`, `forbidden_field`, `payload_not_utf8`, `payload_too_large`;
   - `credential_pattern`;
   - `operation_not_permitted` / `operation_denied` / `operation_outside_vocabulary`;
   - `unsupported_constraint` (Restriction Enforceability; Approval Gates);
   - `egress_denied_by_parent`;
   - `parent_invalid` / `parent_inactive` / `parent_expired`;
   - `source_outside_allowed_resources`;
   - `recipient_not_allowlisted`, `surface_excluded_from_v0`, `model_not_allowlisted`;
   - `grant_not_none` (grant state `granted` or `unknown` where the mechanism is
     `none_documented`);
   - `attestation_missing`, `attestation_stale`, `future_dated_attestation`;
   - `consequential_task_risk` (security testing, credentials, deployment, privileged
     programs);
   - `expiry_passed`.
2. **`review_required`** — arises only for public content. Triggers:
   - `steward_match`;
   - `elevated_task_risk`;
   - `recipient_review_always` (policy-flagged, e.g. first use of a recipient profile).
3. **`eligible_for_operator_reviewed_export`** — everything else. Operator confirmation is
   still required for every export in v0.

A scanner non-match is recorded as `no_configured_finding`, never as safe. A steward match
is a review trigger, not a confidentiality classification: public discussion of tribal or
water-policy topics is not thereby confidential.

### Review transitions

| From | Operator action | Result | Payload staged |
|---|---|---|---|
| `eligible_for_operator_reviewed_export` | Confirm | Approval record | Yes, if release checks pass |
| `review_required` | Confirm, acknowledging exactly the set of `review_triggers` | Approval with `acknowledged_triggers` | Yes, if release checks pass |
| `review_required` | Acknowledge a strict subset | Refused | No |
| either | Decline | Declination record | No |
| `ineligible` | — (no prompt offered) | Record | No |
| any | Edit any input | New proposal; new evaluation and identifier | Only via a new cycle |

## Parent Normalization

The parent is a CR-095 v1.0.0 manifest. For this profile the export path enforces closure:
any top-level field outside CR-095 v1.0.0 makes the export `ineligible` with
`unsupported_constraint`. The frozen manifest is validated with
`validate_authority_manifest(now=evaluation_time)` and again at release with
`now=release_time`.

Dimensions are owned by exactly one source. The omission rule applies only to
parent-owned dimensions.

| Dimension | Owner | Rule | If the owner omits it |
|---|---|---|---|
| Recipient and surface allowlist | **Policy** | Recipient must be on the policy allowlist; never read from the parent | n/a — any parent field claiming it is `unsupported_constraint` |
| Data-class ceiling (`public`) | **Policy** | Effective class must be `public` | n/a |
| Freshness, eligibility-duration, and approval-TTL ceilings | **Policy** | Proposal may tighten; parent cannot loosen | n/a |
| Payload size cap | **Policy** | `locally_enforced` | n/a |
| Export-operation vocabulary | **Policy** | Requested operations must be in it | n/a |
| Act of proposing an export | **Parent** | `propose_external_export` ∈ `allowed_actions` and ∉ `denied_actions` | Missing from allowed → `operation_not_permitted` |
| Requested recipient work | **Parent** (as *requests*) | Each requested operation ∈ `allowed_actions` ∩ policy vocabulary, and ∉ `denied_actions` | Not allowed → `operation_not_permitted` |
| Egress denial | **Parent** | `network_access` or `external_api_call` ∈ `denied_actions` → `egress_denied_by_parent` | — |
| Content source | **Parent** | The payload file's normalized repository-relative path falls under an `allowed_resources` prefix | Missing → `source_outside_allowed_resources` |
| Expiry | **Parent** | `valid_until` ≤ `expires_at` | Required by CR-095 |
| Approval gates | **Parent** | See Approval Gates | Never waived |

Owner decision 1 applies: other `denied_actions` (for example `execute_shell`) bound the
proposer and its requests, not the recipient. The record states: *in this profile
TriageCore releases public content; it delegates no action authority and makes no claim
about what the recipient does.*

Content provenance limit: the source rule establishes where the payload file sits, not
where its contents came from.

### Approval gates

| Gate in `requires_human_approval_for` | Treatment |
|---|---|
| `propose_external_export` | Satisfied by the local operator confirmation (`locally_enforced`) |
| `network_access`, `external_api_call` | Defined as applicable to the export act and satisfied by the same local confirmation, because in v0 the only egress the export enables is the operator's own manual transfer after a confirmation that displays the exact payload and recipient. *Explicit design point for review.* |
| Any requested operation (e.g. `write_critique`) | `unsupported_constraint` (code `approval_gate_unsupported`) in v0. The gate cannot silently disappear because recipient execution is outside the profile; a later revision may define how local confirmation satisfies it. |
| An action neither requested nor the export act | No effect on this export |

## Restriction Enforceability

Every restriction is classed:

- **`locally_enforced`** — governs local staging: confirmation before staging, expiry and
  freshness, class ceiling, recipient allowlist at staging, size cap, source prefix,
  destination rules.
- **`recipient_instruction`** — text the proposal asks to include for the recipient (for
  example "do not browse", "answer within three turns"). Recorded by digest and labelled.
  It never satisfies any requirement.
- **`unsupported_constraint`** — makes the export `ineligible`. Arises from any requirement
  that a downstream restriction be *enforced* (turn limit, tool prohibition, a
  recipient-side approval gate), whether requested by the proposal or present as an
  unknown parent field, and from any constraint key the profile does not define.

No v0 recipient surface has a documented, evidenced enforcement mechanism, so no
restriction is ever classed as `surface_enforced` in v0.

## Operator Channel and Confirmation

### Payload display

- The full frozen payload is displayed from the same buffer that will be staged, paged if
  long, with byte length and SHA-256.
- Escaping is **lossless and injective**: zero-width characters, bidirectional controls,
  other control characters, non-ASCII whitespace, and the escape character itself are
  rendered as visible escape sequences, so two different payloads never render
  identically. `unescape(render(payload)) == payload` is a required property.
- The eligibility record and policy digest are displayed alongside.

### Confirmation

- The operator types a short code derived from `eligibility_id`. The code binds the
  confirmation to the screen shown. **It does not establish human identity**; any process
  controlling the terminal could type it. The exporter must not be run by an agent.
- **One staging attempt per confirmation.** Any failure after confirmation consumes it; a
  retry requires a new evaluation, display, and confirmation.
- The supported claim is: *the operator was shown the complete payload and the
  eligibility record, and confirmed in this process.* Not that the operator read or
  understood it, and not that an authenticated human approved it.

## Time and Determinism

- **Conditional determinism.** The eligibility body is a deterministic function of the
  frozen payload, proposal, parent bytes, policy bytes, operator attestations, and
  `evaluation_time`. Identical inputs yield an identical body and identifier.
- **Release recomputation** uses the in-memory `evaluation_time` with freshly re-read
  files; the identifier must match. Time-dependent checks are then applied separately
  against `release_time`. **An approved, unchanged binding can still be refused at
  release.**
- `approval_expires_at` = min(`confirmed_at` + policy approval TTL, `valid_until`) —
  anchored to confirmation time.
- Attestation freshness is re-checked at release: `release_time − observed_at` ≤ policy
  ceiling.
- `observed_at > evaluation_time` → `future_dated_attestation` (`ineligible`).
- Ordering `observed_at ≤ evaluation_time ≤ confirmed_at ≤ release_time` is checked on the
  wall clock, and intra-invocation durations are cross-checked against a monotonic clock;
  disagreement → `clock_inconsistent`.

## Release-Time Checks

Immediately before writing the intent record, in order:

1. Re-read the payload; digest must match (`bytes_changed`).
2. Re-read proposal, parent, and policy; digests must match (`proposal_changed`,
   `parent_changed`, `policy_changed`).
3. Recompute the eligibility body; identifier must equal the confirmed one
   (`eligibility_id_mismatch`).
4. Revalidate the parent at `release_time` (`parent_expired`, `parent_inactive`).
5. Time checks (`valid_until_passed`, `approval_expired`, `attestation_stale_at_release`,
   `clock_inconsistent`).
6. The confirmation was produced by this invocation's operator channel and has not been
   consumed (`confirmation_consumed`).
7. Destination checks (Staging and Destination Security).

Any failure → `refused_pre_staging` with no payload staged.

## Staging and Destination Security

### File staging (default)

- The destination directory must be **explicitly selected** for each invocation and lie
  under a staging root listed in policy. The file name is generated by the exporter.
- **Symlink protection:** resolve the real path; refuse if any component of the
  destination path is a symbolic link or junction, or if the resolved path leaves the
  staging root. The final file is created with exclusive-create and no-follow semantics,
  and refused if it exists.
- **Permissions:** created owner-read/write only (POSIX mode `0600`). The equivalent
  Windows ACL is an open implementation question (Deferred Work). A staging root that is
  group- or world-writable is refused.
- **Repository exclusion:** a staging root inside any version-controlled working tree is
  refused, so staged content cannot be committed or pushed by accident.
- **Synchronized and watched directories:** the exporter does not control external
  synchronization and must never imply that it does. Policy may list known sync roots to
  refuse; the operator attests at selection that the staging root is not synchronized.
  Stated hazard: on Windows, OneDrive Known Folder Move may redirect Documents and Desktop
  into a synchronized location, so a staged file there may be copied off-host before the
  operator transfers it.
- **Verification:** write, fsync, then read back and compare the digest with the displayed
  buffer.
- **Retention:** staged files remain until the operator removes them. Cleanup tooling is
  out of scope.

### Clipboard staging (explicit opt-in)

Write, then read back where the platform permits. Residual risk: clipboard history and
cross-device clipboard sync (including Windows clipboard history and sync) may retain or
copy the content beyond the operator's intent.

### Outcomes

| Outcome | Meaning | "No payload staged" may be claimed |
|---|---|---|
| `refused_pre_staging` | A release check failed, or the intent write failed | **Yes — only here.** The intent record, if written, is itself a persistent effect. |
| `staging_failed_partial` | Error during the write; cleanup recorded as `removed`, `failed`, or `unknown` | No |
| `staging_uncertain` | Ambiguous I/O or clipboard result | No |
| `staged_verified` | Read-back digest matches the displayed buffer | No |
| `staged_unverified` | Write reported success; no read-back possible | No |
| `staged_mismatch` | Read-back differs from the displayed buffer; opens an incident | No |
| `outcome_unknown` | An intent exists with no release record (for example a crash after staging); found by a later audit | No — never reported as "not staged" |

If the release record cannot be written after staging, the exporter prints a prominent
`STAGED — evidence record failed` notice and exits with a distinct exit code.

## Evidence and Coverage

Every outcome records **local staging only**. Delivery to the provider is never recorded
or claimed.

Outside TriageCore's visibility, and listed in every release record and report:

- whether and when the operator transferred the content, and whether the transferred
  bytes matched the staged bytes;
- provider retention, logging, and training use;
- which model actually served the request, and the effective safeguard mode;
- tool use or browsing inside the provider session;
- uploads the operator made directly in the browser without the exporter.

Evidence claims are reported against observed coverage, for example: *"N exports were
staged through the exporter; each had a matching recomputed eligibility identifier and an
in-process confirmation."* A claim such as "no unadmitted exports occurred" is not
supported.

Real-use records retain digests, reason codes, and outcomes only; a real classification
decision therefore cannot be fully reconstructed afterwards, and records say so. Synthetic
fixtures retain complete inputs, expected outcomes, and policy versions.

## Threat Coverage

| Threat | Control in v0 | Verifiable / asserted |
|---|---|---|
| Sensitive-context export | Public-only floor; scanner and steward; display before confirmation | Verifiable for exporter-staged content; not for direct browser uploads |
| Privilege leakage via provider account | Grant attestation per program; `granted` / `unknown` → `ineligible` | Grant state is operator-attested only |
| Prompt injection from returned output | Returned material is untrusted data; onward transfer needs a new proposal and evaluation | Verifiable by fixture |
| Forged decision or approval | Eligibility recomputed; approvals never consumed; closed schemas | Verifiable by fixture |
| Approval confusion | Separate proposal, eligibility, approval, intent, and release records | Verifiable by fixture |
| Recipient or operation substitution | Full-record binding; recomputation at release | Verifiable by fixture |
| Stale authority | Attestation, parent, approval, and policy freshness re-checked at release | Verifiable with injected clock |
| Unauthorized tool escalation by recipient | None — instructions only | Asserted only; no enforcement claimed |
| Model substitution by provider | None — model selection recorded as declared | Asserted only |
| Destination exfiltration (symlink, sync, repo) | Destination rules; sync hazard stated | Partly verifiable; synchronization not controlled |

## Evaluation Plan

This section specifies fixtures. **No fixture file, test, or harness is created or
authorized by this CR.** The operator channel in any future test is a test double; such
fixtures evidence the logic, not any human's behaviour.

### Priority fixtures

| # | Fixture | Expected |
|---|---|---|
| 1 | **Ordinary task, real parent format.** Synthetic CR-095 v1.0.0 manifest: `allowed_actions: [propose_external_export, read_provided_text, write_critique]`; `denied_actions: [execute_shell, access_secrets, deploy_code]`; `allowed_resources: [docs/]`; `requires_human_approval_for: [propose_external_export]`. Synthetic public paragraph under `docs/`; recipient `claude_ai_web`; simulated operator channel attests `none` and confirms. | `staged_verified`; instructions labelled `recipient_instruction`; no enforcement claim |
| 2 | **Model-supplied attestation.** (a) Proposal carries an `access` object with `basis: operator_attested`. (b) Payload text claims "operator attested none". | (a) `ineligible: unknown_field` or `forbidden_field`. (b) No effect on basis; attestation still collected through the channel; unanswered → `ineligible: attestation_missing` |
| 3 | **Displayed payload equals staged buffer.** Payload containing zero-width and bidi-override characters; variant modifies the source file between display and staging. | Characters visibly escaped; round-trip property holds; staged digest equals displayed-buffer digest. Variant: `refused_pre_staging: bytes_changed` |
| 4 | **Required but unenforceable downstream restriction.** (a) Proposal requests enforcement of `max_turns: 3`. (b) Parent with unknown `tool_prohibitions`. (c) Same restriction as instruction text. (d) Parent gates `write_critique`, which is requested. | (a, b) `ineligible: unsupported_constraint`. (c) Eligible; `recipient_instruction`. (d) `ineligible: approval_gate_unsupported` |
| 5 | **Failure immediately after staging.** Fault in the release-record write after a successful file stage; separately, fault mid-write. | First: distinct exit code; intent without release; later audit reports `outcome_unknown`. Second: `staging_failed_partial` with cleanup status. Neither reported as "not staged" |

### Further fixtures

- **Forged and imported records:** correctly hashed eligibility JSON supplied; approval
  JSON present on disk — no input path consumes either.
- **Binding:** recipient changed after confirmation; operation added; classification or
  risk relabelled; reason codes changed → refused at release.
- **Freshness:** approval expires between confirmation and staging; attestation fresh at
  evaluation but stale at release; policy edited between evaluation and release;
  future-dated attestation; wall/monotonic disagreement.
- **Review transitions:** every row of the Review Transitions table.
- **Attenuation:** each parent-owned dimension exceeded; unknown parent field; parent
  denies `network_access` → `egress_denied_by_parent`; parent revoked or expired; gate on
  an unrequested action → no effect.
- **Schema closure:** unknown field at each nesting level of the proposal.
- **Destination:** symlinked component; existing file; staging root inside a git working
  tree; world-writable staging root; policy-listed sync root.
- **One attempt per confirmation:** second staging attempt after a failure is refused.
- **After the fact:** synthetic provider-reported mode differing from expectation opens an
  incident record; claim wording never says "prevented".
- **Coverage honesty:** every successful release says "staged", never "delivered", and
  carries the out-of-visibility list.
- **Usefulness corpus:** 10–15 representative public tasks (document critique,
  architecture review of public documents, literature summary, test-plan brainstorming).

### Metrics

- **Containment:** every hard-stop fixture ends `ineligible` or `refused_pre_staging`; no
  such case stages a payload.
- **Usefulness:** on the benign corpus, the rate of false `ineligible` results and the rate
  of `review_required`, plus prompts per export as a review-burden measure. Thresholds are
  set by the owner **before** the first run.
- Record counts and denominators, not a global safety rate.

### Retained results

A future implementation slice must retain, for the evidence index: test output in a
machine-readable form, the fixture-corpus digest, the policy digest, and the commit. The
87 focused component tests observed during the design review are not evidence for this
gate.

## Non-Claims

This CR, and any future implementation of it, does not claim that:

- an export was delivered, or that delivered bytes matched staged bytes;
- a recipient obeyed any instruction or used no tools;
- a provider applied standard safeguards, or that an account holds no program grant (grant
  state is operator-attested);
- the confirming operator is authenticated, read the payload, or understood it;
- a scanner non-match means content is safe, or a steward match means content is
  confidential;
- manual mediation is permitted under every provider grant; it avoids several
  automation-specific uncertainties but does not itself establish permission;
- synchronized or watched directories are controlled;
- replay or denial history is enforced across invocations;
- the parent manifest's identity or revocation status is authenticated;
- this profile composes with authorization receipts, capability claims, or mediated
  execution.

## Deferred Work and Open Questions

- **Identity-registry revocation check (CR-029).** Deferred design candidate. A future
  check must distinguish an absent registry (currently loaded as empty) from an unreadable
  or malformed one (CR-097 fail-closed), and must state that registry membership does not
  authenticate the manifest's claimed identity.
- **Authenticated approval.** A CR-YK-001 assertion over `eligibility_id`; separate CR.
- **Persistent replay and denial history.** Requires a store (candidate patterns:
  CR-OC-001B reservation, CR-YK-002 claims); separate CR.
- **Windows staging permissions.** Owner-only ACL equivalent of `0600` on NTFS.
- **Sync-directory detection.** Whether any reliable detection exists beyond policy lists
  and operator attestation.
- **Manifest binding and signing.** CR-095 recorded these as future slices; unchanged here.
- **Admission evidence duplication.** Two `ExternalRuntimeAdmissionEvidence` classes; a
  separate finding.
- **Excluded surfaces.** Console workspaces, the Responses API, Codex, and desktop MCP
  remain `excluded_from_v0`; their availability and governing terms are separate questions.
- **Provider questions** (open; written answers wanted before any later profile relies on
  them):
  - A1. Is there a supported standard-safeguard context inside an individual consumer
    organization enrolled in the Cyber Verification Program?
  - A2. Is a `claude setup-token` token a prohibited "long-lived credential" under an
    individual grant after 2026-12-15?
  - A3. Can a Console workspace reliably remain outside Cyber Verification Program
    coverage, given that the program "appl[ies] automatically to every workspace that meets
    their requirements"?
  - A4. Is a personal export tool with manual transfer "ordinary, individual usage", and
    outside the individual grant's prohibition on "proxy tools that expose the session to
    others"?
  - O1. Is the effective cyber access mode always reported in Responses API responses?
  - O2. Is individual Daybreak enrollment bound to the whole ChatGPT account, and is there
    a standard-mode control in ChatGPT chat or on Android?
  - O3. Is `standard` an accepted `--cyber-access-program` value in Codex CLI, and how is
    Daybreak disabled in 0.163.0?

### Readiness gates for any later live integration

None of these is satisfied, and none is authorized by this CR:

1. A supported standard-access context, documented for the chosen surface.
2. Written provider answers to the applicable questions above.
3. A frozen-bytes exporter implemented and mutation-tested.
4. Containment and usefulness metrics met on the fixture corpus.

## Provider Evidence (dated)

Retrieved 2026-10-18. "Read" means retrieved by the drafting agent; "operator-reported"
means checked independently by the operator and not retrieved by the drafting agent,
because the drafting environment's network policy blocked the OpenAI documentation hosts.

| Source | Basis | Relevant content |
|---|---|---|
| [Cyber Verification Program](https://support.claude.com/en/articles/14604842-cyber-verification-program) | Read | For Claude Team, Max, and Pro, "the Program attaches at the Organization level"; individuals eligible for Defense Access only |
| [CVP Security Requirements](https://support.claude.com/en/articles/17202708) | Read | Individual grants: phishing-resistant MFA and no static or long-lived credentials by 2026-12-15; no "proxy tools that expose the session to others"; all traffic retained |
| [Assign a program to workspaces](https://support.claude.com/en/articles/16764810-assign-a-program-to-workspaces-in-claude-console) | Read | Programs apply to assigned workspaces, but some, including CVP, "apply automatically to every workspace that meets their requirements"; no separate organization needed |
| [Use the Claude Agent SDK with your Claude plan](https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan) | Read | 2026-10-07 update: Agent SDK, `claude -p`, and third-party apps can still use subscription limits |
| [Claude Code legal and compliance](https://code.claude.com/docs/en/legal-and-compliance) | Read | Developers may not intermediate Claude.ai credentials or route requests through consumer plan credentials on behalf of users |
| [Codex CLI 0.161.0](https://github.com/openai/codex/releases/tag/rust-v0.161.0) | Read | Daybreak opt-in; per-turn `--cyber-access-program` |
| [Codex CLI 0.163.0](https://github.com/openai/codex/releases/tag/rust-v0.163.0) | Read | "Daybreak is enabled by default for eligible accounts" |
| [Use Daybreak in the Responses API](https://developers.openai.com/api/docs/guides/daybreak) | Operator-reported | `access_programs.cyber = "standard"` selects behaviour within approved access; response-side mode reported when available; omitted selection can receive Daybreak treatment for eligible projects |
| OpenAI desktop plugin documentation | Operator-reported | Local STDIO MCP for desktop-only plugins; publishing requires approved-partner access |

## Relationship to the NIST/ISO Assessment

The operator's TriageCore assessment and remediation plan (2026-10-17 PDT, evidence
baseline v1.0, pinned to `ede8ef1`) is preserved unchanged by this CR.

- **Scores are unchanged.** This CR is design evidence only.
- **Alignment:** R06 / K02 (separate proposal, eligibility, approval, and release records);
  gate G2 (exact binding, expiry, and freshness at release; refusals stage no payload); K03
  (forged-record fixtures); R08 / K04 (data class bound per export); R13 (dated, versioned
  surface evidence); R10 / G4 (containment plus usefulness metrics).
- **De-duplication:** the recipient allowlist should be the same trusted destination
  policy that M04 defines for endpoint locality (K01 / G1), and declared-class binding
  should reuse M05's privacy-join design rather than run in parallel.
- **Candidate risk-register entry** (identifier to be assigned by the owner): *content or
  authority exported to an external model recipient beyond the approved class, recipient,
  or operation scope.* Treatment: this contract. Residual: activity outside the exporter's
  visibility. Review trigger: any change to a provider's program or default.
- **Sequencing:** this CR should not be implemented before M04 settles the destination
  policy; whether it becomes a later increment is an M09a decision.
- **PR #179:** the separate *authorization-record reconciliation required* finding stands.
  It is not addressed by this CR and belongs to M03.

## Explicit Exclusions

- Any code, test, fixture file, schema file, CLI surface, configuration, or ledger change.
- Any network call, provider API use, MCP server, browser automation, session cookie,
  extracted token, or credential operation.
- Any change to `admission.py`, `external_runtime_adapter.py`, `task_envelope.py`,
  `agent_authority.py`, `safe_task_packet.py`, the governed run path, or the identity
  registry.
- Any surface marked `excluded_from_v0`.
- Any delegation of action authority to an external recipient.
- Backlog, change-log, architecture, and README updates.
- Publication of this document, merge, release, deployment, and closeout.

## Stop Point

This document is the stop point. It proposes a contract and records two owner decisions.
Proposal acceptance and design acceptance are pending review of this completed document.
No implementation, test, fixture, CLI, credential, ledger, publication, merge, release, or
deployment action is authorized by it.
