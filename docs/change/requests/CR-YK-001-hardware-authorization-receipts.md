# CR-YK-001: FIDO2 Security-Key-Backed Human Authorization Receipts (YubiKey Hackathon Lane)

## Status

Primary-path hardware verification completed 2026-07-24, targeting the
YubiKey hackathon on 2026-08-05.

Primary YubiKey enrollment and assertion ceremonies verified on Windows. A phone passkey was also validated as a secondary cross-device pathway. Redundant backup-YubiKey enrollment remains unverified.

Verification ran on Microsoft Windows 11 Pro 64-bit, version
10.0.26200, build 26200, with `fido2` 2.2.1 through Windows native WebAuthn
on branch `cr-yk-001-hardware-authz` at `0424442`, which is patch-identical
to the previously recorded `295a119`. Separate lane (CR-YK-*) so it cannot
entangle the CR-DD sequence, mirroring how Build Week ran as its own bounded
slice.

Component states (kept honest and separate):

| # | Component | State |
|---|-----------|-------|
| 1 | Deterministic authorization core (`triage_core/authz.py`) | **Implemented and tested** (challenge derivation, receipts, tamper detection, capability lane, credential store with revocation) |
| 2 | WebAuthn adapter (`triage_core/fido2_adapter.py`) | **Implemented and tested against python-fido2 2.2.1**; offline verification exercised with real fido2 data structures, a synthetic software credential, and the physical ceremonies below |
| 3 | Primary physical YubiKey enrollment ceremony | **Verified 2026-07-24** through Windows native WebAuthn with explicit cross-platform authenticator selection |
| 4 | Primary physical YubiKey assertion ceremony | **Verified 2026-07-24** for both PIN-required UV and corrected touch-only operation; offline verification passed |
| 5 | Secondary cross-device phone WebAuthn passkey | **Verified 2026-07-24** as the bounded hackathon-lane secondary credential; it is not a second hardware security key |
| 6 | Redundant backup-YubiKey enrollment | **UNVERIFIED** — a second physical YubiKey was unavailable; the phone passkey is not assurance-equivalent |
| 7 | CR-DD-012B execution integration (`tc run --confirmed-plan`) | **Explicitly out of scope** for this CR and not modified during hardware smoke testing |
| 8 | Atomic capability consumption | **Not implemented**; documented limitation with a strict expected-failure test; required before 012B integration |

## Decision (bounded allowlist)

This CR authorizes, and only authorizes:

1. `triage_core/authz.py`: canonical versioned authorization requests,
   challenge derivation, receipt sidecar artifacts with tamper detection and
   restrictive permissions, structural verification, the one-use
   execution-capability lane with a closed denial vocabulary, and the
   public-credential store with revocation tombstones.
2. `triage_core/fido2_adapter.py`: all python-fido2 and platform-specific
   code — availability probe, enrollment and assertion ceremonies, and full
   offline verification via `Fido2Server`.
3. `tests/test_authz.py`: deterministic-core tests plus fido2-backed
   verification tests using synthetic software credentials.
4. The optional dependency extra `authz = ["fido2>=2.0,<3"]`. Absence of
   the extra must not break import, and non-Windows platforms must receive a
   controlled unavailability result, never an import crash
   (`fido2.client.windows` cannot even be imported off-Windows).
5. Hackathon-day CLI additions listed under "Planned CLI surface".

Not authorized here: any change to `tc run`, the resilience router, cloud
paths, TriageDesk, CR-DD-012B implementation files, or atomic capability
storage.

## Problem

TriageCore separates system recommendation from human decision, but a
recorded human decision is currently a ledger event anyone with file access
could have written. For governed agent actions the missing property is
phishing-resistant evidence that the enrolled human performed a fresh,
deliberate approval ceremony over one exact plan — the standard mitigation
for excessive agency in current OWASP agentic guidance, made cryptographic.

## Design

### Binding chain

```
run-plan artifact (CR-DD-011)          existing: canonical bytes + digests
        │  artifact_byte_digest / plan_body_digest
        ▼
AuthorizationRequest (schema v2)       versioned canonical JSON binding:
        │                              schema id, decision_id, both plan
        │                              digests, scope/policy digest (when
        │                              available), task_id, risk class,
        │                              policy version, approver, RP ID,
        │                              UV-required policy, nonce (UUID),
        │                              issued-at, expiry
        ▼
challenge = SHA-256(canonical_json(request))
        ▼
WebAuthn get-assertion                user presence always; user
(YubiKey or bounded phone secondary) verification required when the request
        │                             says so
        ▼
HumanAuthorizationReceipt (schema v2)  request + standard WebAuthn JSON
        │                              wire-format assertion; sidecar file
        │                              under .triagecore/authz/receipts/
        │                              with owner-only permissions
        ▼
ledger: human_authorization_receipt    digests + privacy-safe metadata only
        ▼
execution capability (one-use, TTL)    issued → consumed | denied
                                       reasons: capability_not_found |
                                       capability_already_consumed |
                                       capability_expired |
                                       artifact_digest_mismatch
```

Versioning and domain separation live in the canonical payload's `schema`
field rather than raw byte concatenation, so what a signature binds is
explicit and auditable in the serialized form. Key-sorted canonical JSON
makes the digest independent of field construction order (tested).

### Identity and normalization

`approver_identity_id` is the stable registered identifier of the approving
human and is the only approver value that is security-bound. Human-facing
display labels are informational, live in the credential store
(`EnrolledCredential.label`), and never enter the challenge. Verification
additionally requires the asserting credential to be enrolled to the same
identity the request names (`credential_approver_mismatch` otherwise), so
one enrolled human's key cannot satisfy another human's request.

The credential store enforces the identical normalization contract:
`EnrolledCredential` normalizes and validates `human_id` at construction,
which covers enrollment, lookup (`find_by_human_id` normalizes its query),
revocation, and serialization uniformly. Cosmetic variants such as
`Operator-A` and `operator-a` therefore resolve to one governed identity —
they cannot enroll as distinct identities, and a request naming
`" operator-a "` verifies against a credential enrolled as `OPERATOR-A`
(both invariants are tested).

Canonical JSON fixes field ordering but not semantics, so construction
normalizes before hashing (tested for equivalence and rejection):

- `risk_class`, `policy_version`, `approver_identity_id`, `rp_id`:
  strip + lowercase, then validated — risk class against the closed
  `{low, medium, high}` vocabulary, the rest against a constrained
  identifier grammar. `"HIGH"`, `"high"`, and `"high "` produce one
  challenge; `"critical"` is rejected.
- `task_id`, `decision_id`: whitespace-stripped and non-empty with no
  embedded whitespace; case is preserved deliberately because ledger task
  lookups are case-exact and operator-supplied IDs (e.g. `CR-017`) must
  keep their linkage.
- digests: must match `sha256:<64 lowercase hex>`; `scope_digest` may be
  empty until a scope artifact exists.
- `nonce`: any accepted UUID form is stored in canonical lowercase form.
- timestamps: round-tripped through ISO-8601 parsing to one canonical
  serialization; unparseable values are rejected at construction.

### Offline verification

Verification layers, in order:

1. **Structural** (dependency-free): request expiry; clientDataJSON parses;
   `type == "webauthn.get"`; challenge equality against the recomputed
   request digest; pinned origin.
2. **Credential policy**: credential is enrolled, not revoked, matches the
   request's RP, and belongs to the request's `approver_identity_id`.
3. **Cryptographic**, via `fido2.server.Fido2Server.authenticate_complete`
   (python-fido2's own server-side primitive, not re-implemented WebAuthn
   parsing): RP-ID hash, user-presence flag, user-verification flag when
   the request required it, credential membership, and the signature over
   `authenticatorData || SHA256(clientDataJSON)`.

Signature counters are deliberately not enforced; zero counters are valid
(common on current keys). Verification is reproducible offline from the
receipt artifact, the enrolled COSE public key, and the ledger — the same
independent-verifiability posture as `tc build-review verify`. Tamper
detection closes the loop: the ledger event stores the receipt digest, and
`read_receipt_artifact(path, expected_digest=...)` rejects drifted bytes.

### Evidence honesty

Primary YubiKey enrollment and assertion ceremonies verified on Windows. A phone passkey was also validated as a secondary cross-device pathway. Redundant backup-YubiKey enrollment remains unverified.

A verified receipt is *WebAuthn-backed authorization*: evidence of
possession and user interaction with an enrolled credential, over exactly
one request digest. A receipt from the primary YubiKey is additionally
security-key-backed. A receipt from the bounded secondary phone credential
is a cross-device passkey receipt and must not be described as coming from a
second hardware security key. "User verification confirmed" is claimed only
when UV was required and the flag was verified.

Not claimed: non-repudiation; cryptographic proof of the YubiKey model or
firmware (attestation was not requested or validated); comprehension of what
was approved (which is why the approval flow must render `render_run_plan`
output, never a bare digest). The operator reports that the tested primary is
a developer early-release firmware 5.8 YubiKey and that only one unit will be
provided. No serial is recorded.

### Threat-model limitations (explicit)

- **Host clock manipulation**: issued-at, expiry, and capability TTLs read
  the local clock. An attacker (or operator) who shifts the host clock can
  extend or revive validity windows. Receipts remain digest-bound, so the
  *content* approved cannot change — only the timing gates weaken.
- **Local-host compromise**: an attacker with code execution on this host
  can present a misleading plan render before the ceremony, request
  approval for content the human did not intend, read sidecar artifacts,
  or append forged non-signed ledger events. The security key defeats
  remote credential phishing and remote approval forgery; it does not
  defend a compromised local machine. Mitigations (out of scope here):
  signed ledger events via the existing identity registry, and reviewing
  plans on a second device.
- **Concurrency**: single-use capability enforcement is sequential-only in
  this slice (see below).

### Capability safety (known gap)

`consume_capability` is read-then-append over a shared JSONL file. Two
concurrent consumers can both observe "unconsumed" before either appends,
so an append-only "consumed" event alone does not prove race-safe single
use, and the sequential unit tests do not claim it. A strict
expected-failure test (`test_concurrent_consume_race_documented`)
deterministically demonstrates the interleaving. **Atomic claiming — e.g. a
SQLite claim table using `BEGIN IMMEDIATE`, or an O_EXCL claim file — is a
requirement for CR-DD-012B integration** and is proposed as its own bounded
slice (CR-YK-002); it is not implemented under this CR.

Agreed CR-YK-002 design sketch (recorded for continuity, not authorized by
this CR): explicit capability states `issued → claimed → completed |
failed`, where a claim is irrevocable for the original capability — a
failed or crashed execution does not silently restore reusability; a new
authorization is required unless a future recovery policy explicitly
permits otherwise. The atomic claim is a SQLite `BEGIN IMMEDIATE`
transaction performing `UPDATE ... SET state='claimed', claimed_at=?,
claimant_id=? WHERE capability_id=? AND state='issued' AND expires_at > ?`
and requiring exactly one changed row. The store binds capability ID,
receipt digest, approved artifact digest, execution-scope digest, expiry,
state, claimant / execution-attempt ID, claimed timestamp, and terminal
outcome timestamp. SQLite becomes the authoritative concurrency-control
mechanism; the ledger remains the durable signed evidence history.

### Sidecar retention

Receipts persist until the operator prunes them. They are inputs to offline
re-verification, so deletion degrades auditability of the runs they
authorized; recommended practice is to retain receipts at least as long as
the ledger covering the same tasks. Credentials use revocation tombstones,
never deletion, so historical receipts stay attributable. Neither artifact
ever contains PINs, private keys, or secrets.

## Planned CLI surface (hackathon day)

- `tc authz enroll --human <id> --label <text>` — make-credential ceremony;
  appends to `.triagecore/authz/credentials.json`. For this bounded hackathon
  lane, enroll the one available developer YubiKey and a separately labeled
  cross-device phone WebAuthn passkey as the secondary credential. The phone
  credential is not a second hardware security key. Google Authenticator TOTP
  is not accepted as a substitute.
- `tc authz approve --plan-artifact <path>` — render plan, build request
  (UV required for high risk), get assertion, record receipt, issue
  capability.
- `tc authz verify --receipt <path>` — offline verification against the
  store and ledger digest.
- `tc authz revoke --credential <id>` — tombstone a lost key.
- `tc authz exec --capability <id> ...` — demo wrapper that consumes the
  capability then invokes the existing governed run path. Demo scope only;
  the durable integration point is CR-DD-012B's `--confirmed-plan`.

## Hardware verification checklist (executed 2026-07-24)

On the Windows verification machine with the physical YubiKey and the
separately labeled phone passkey:

1. `pip install -e ".[authz]"`; confirm `fido2` reports version 2.2.1.
2. `python -c "from triage_core.fido2_adapter import ceremony_support; print(ceremony_support())"`
   → expect `windows_native`, available.
3. Enroll the primary YubiKey and the bounded secondary cross-device phone
   passkey as separately labeled credentials; confirm entries contain
   credential ID, COSE key, AAGUID, and nothing secret. This one-YubiKey-plus-
   phone policy is a bounded amendment for this lane, not a claim that the
   phone is a backup hardware security key.
4. Assertion ceremony over a real run-plan request with UV required (PIN
   plus touch for the YubiKey) and with UV not required (YubiKey touch only,
   with no PIN).
5. `verify_receipt` passes on both; then repeat all failure paths from the
   demo script (tamper, expiry, replay, revoked key, wrong key).
6. Exercise the phone credential with REQUIRED UV through Windows QR/
   cross-device WebAuthn and confirm device unlock, `user_verified == true`,
   and offline verification.

### Hardware verification record

- The first registration selected Windows Hello because the creation options
  did not constrain authenticator attachment. It enrolled AAGUID
  `08987058-cadc-4b81-b6e1-30de50dcbe96`, was quarantined in the isolated
  `.triagecore/hardware-smoke` store, and did not count as YubiKey enrollment.
- Enrollment was corrected to require
  `AuthenticatorAttachment.CROSS_PLATFORM`. Primary YubiKey enrollment then
  succeeded in the isolated `.triagecore/hardware-smoke-yubikey` store.
- The high-risk YubiKey assertion used REQUIRED UV. PIN and touch were
  observed, `user_verified` was true, and offline verification passed.
- The initial non-required assertion used PREFERRED, still prompted for a
  PIN, and did not count as the touch-only result. The false UV policy was
  corrected to DISCOURAGED in both the live assertion request and the
  reconstructed verifier state.
- The corrected touch-only YubiKey assertion presented no PIN prompt. Touch
  was observed, `user_verified` was false, and offline verification passed.
- Because only one developer YubiKey is available, a separately labeled
  cross-device phone WebAuthn passkey is accepted as the secondary credential
  for this bounded hackathon lane. Phone enrollment through the Windows QR/
  cross-device flow succeeded. Its high-risk REQUIRED-UV assertion succeeded
  with device unlock, `user_verified` true, and offline verification passed.
  This is not a second hardware security key; Google Authenticator TOTP is
  not an accepted substitute.
- The offline rejection matrix passed for artifact tamper, request expiry,
  wrong public key, a revoked credential copy, sequential replay denial, and
  capability expiry.
- Focused tests: **64 passed, 1 skipped, 1 xfailed**. Full suite:
  **1151 passed, 5 skipped, 1 xfailed**.
- The main `.triagecore/authz` credential store and execution integration were
  not modified. All smoke artifacts remain isolated.

Pre-hackathon note: audit finding F1 (DangerDetector substring `auth`/
`token`) still blocks demo prompts about authorization from reaching the
approval gate; fix it first.

## Demo script (~3 minutes)

1. `tc run "<task>" --plan --plan-output plan.json` — show digests.
2. `tc authz approve --plan-artifact plan.json` — plan renders, OS WebAuthn
   dialog, touch key; show receipt artifact + metadata-only ledger event.
3. `tc authz exec` — capability consumed once; action runs.
4. Re-run — denied `capability_already_consumed`; denial is evidence.
5. Tamper one byte of the plan — `client_data_challenge_mismatch`.
6. Force expiry — `capability_expired`.
7. Revoke the key, verify again — `credential_revoked`.
8. Close on `tc task show <id>`: propose → approve → capability → execute
   → deny chain.

## Verification path

- Deterministic + synthetic-credential: `python -m pytest tests/test_authz.py -q`
  (challenge determinism, field-order independence, normalization
  equivalence and non-canonical rejection, per-field binding
  including UV policy, approver identity, and scope digest,
  approver-credential mismatch, malformed/typed/challenge/origin
  clientData rejections, expiry, artifact tamper detection and permissions,
  privacy-invariant compliance of all ledger payloads, capability lifecycle
  and denials, strict-xfail concurrency demonstration, dependency-missing
  and platform-unavailable handling, and full fido2-backed verification
  positive/negative matrix: zero counter accepted, missing UP, missing
  required UV, UP-only when UV not required, wrong RP-ID hash, altered
  authenticator data, altered signature, wrong key, unknown credential,
  revoked credential). Latest focused result: **64 passed, 1 skipped,
  1 xfailed**.
- Full suite: **1151 passed, 5 skipped, 1 xfailed**.
- Hardware: the checklist above passed on 2026-07-24 through Windows native
  WebAuthn with the primary YubiKey and bounded secondary cross-device phone
  passkey.

## Non-goals

- No change to routing, privacy gating, cloud enablement, or TriageDesk.
- No CR-DD-012B implementation or `--confirmed-plan` wiring.
- No atomic capability storage in this slice (separate bounded change).
- No attestation-chain validation of authenticator provenance.
- No multi-approver quorum policies.
