# CR-YK-001: FIDO2 Security-Key-Backed Human Authorization Receipts (YubiKey Hackathon Lane)

## Status

Hardened scaffold, 2026-07-18, targeting the YubiKey hackathon on 2026-08-05.
Separate lane (CR-YK-*) so it cannot entangle the CR-DD sequence, mirroring
how Build Week ran as its own bounded slice.

Component states (kept honest and separate):

| # | Component | State |
|---|-----------|-------|
| 1 | Deterministic authorization core (`triage_core/authz.py`) | **Implemented and tested** (challenge derivation, receipts, tamper detection, capability lane, credential store with revocation) |
| 2 | WebAuthn adapter (`triage_core/fido2_adapter.py`) | **Implemented against python-fido2 2.2.x**; offline verification exercised with real fido2 data structures and a synthetic software credential |
| 3 | Physical YubiKey enrollment ceremony | **UNVERIFIED** — code follows the inspected 2.x API; no physical-key test has run |
| 4 | Physical YubiKey assertion ceremony | **UNVERIFIED** — same condition; see manual checklist |
| 5 | CR-DD-012B execution integration (`tc run --confirmed-plan`) | **Explicitly out of scope** for this CR |
| 6 | Atomic capability consumption | **Not implemented**; documented limitation with a strict expected-failure test; required before 012B integration |

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
WebAuthn get-assertion (security key)  user presence always; user
        │                              verification (PIN) required when the
        │                              request says so
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

A verified receipt is *FIDO2 security-key-backed authorization*:
hardware-backed evidence of possession and user interaction with an
enrolled credential, over exactly one request digest. "User verification
confirmed" is claimed only when UV was required and the flag was verified.

Not claimed: non-repudiation; proof of a specific YubiKey model
(attestation is not validated); comprehension of what was approved (which
is why the approval flow must render `render_run_plan` output, never a bare
digest); any hardware ceremony success prior to the physical-key checklist
passing.

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
  appends to `.triagecore/authz/credentials.json`. Enroll at least two keys
  (backup is part of the architecture).
- `tc authz approve --plan-artifact <path>` — render plan, build request
  (UV required for high risk), get assertion, record receipt, issue
  capability.
- `tc authz verify --receipt <path>` — offline verification against the
  store and ledger digest.
- `tc authz revoke --credential <id>` — tombstone a lost key.
- `tc authz exec --capability <id> ...` — demo wrapper that consumes the
  capability then invokes the existing governed run path. Demo scope only;
  the durable integration point is CR-DD-012B's `--confirmed-plan`.

## Manual hardware verification checklist (required before any "verified" claim)

On the Windows hackathon machine with a physical YubiKey:

1. `pip install -e ".[authz]"`; confirm `fido2` reports a 2.x version.
2. `python -c "from triage_core.fido2_adapter import ceremony_support; print(ceremony_support())"`
   → expect `windows_native`, available.
3. Enrollment ceremony for two keys; confirm both entries in
   `credentials.json` contain credential ID, COSE key, AAGUID — and nothing
   secret.
4. Assertion ceremony over a real run-plan request with UV required (PIN
   prompt must appear) and with UV not required (touch only).
5. `verify_receipt` passes on both; then repeat all failure paths from the
   demo script (tamper, expiry, replay, revoked key, wrong key).
6. Only after 1–5 pass may states 3 and 4 in the Status table be flipped to
   "verified", with the date and machine noted here.

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
  revoked credential).
- Hardware: the manual checklist above; unverified until executed.

## Non-goals

- No change to routing, privacy gating, cloud enablement, or TriageDesk.
- No CR-DD-012B implementation or `--confirmed-plan` wiring.
- No atomic capability storage in this slice (separate bounded change).
- No attestation-chain validation of authenticator provenance.
- No multi-approver quorum policies.
