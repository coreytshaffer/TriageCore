# Hardware-Bound Human Authorization for AI Agent Actions

## Three-minute demonstration

The lead demonstration is
[`examples/hardware_authorization_evidence.py`](../../examples/hardware_authorization_evidence.py).
It uses the existing authorization and atomic capability-claim APIs to gate one
clearly labeled consequential sample action: publishing a demo release marker.
It uses a synthetic software WebAuthn credential, not a physical YubiKey, and
writes only beneath an operator-selected empty repository-relative directory.

From the repository root, choose an output directory that does not exist or is
empty:

```powershell
python -m pip install -e ".[authz,dev]"
python examples/hardware_authorization_evidence.py --output-dir .triagecore/hardware-authorization-evidence-run
```

The command exits nonzero if any demonstration invariant fails. Its JSON
summary shows:

- `mismatched_claim_allowed` is `false`, and the mismatched attempt does not
  publish the marker;
- two concurrent contenders race for one capability, exactly one has
  `claim_allowed: true`, and exactly one has `action_ran: true`;
- the generated ledger was parsed successfully before the summary is emitted;
- `physical_yubikey_claim` is `false`.

A checked-in
[seven-event sample ledger](hardware-bound-human-authorization/sample-ledger.jsonl)
captures one successful synthetic run and can be parsed independently without
running the demonstration. It contains receipt metadata and digests, but not
the unpublished receipt sidecar or credential-identifying material.

Inspect and independently parse the generated JSONL with PowerShell:

```powershell
Get-Content .triagecore\hardware-authorization-evidence-run\ledger.jsonl | ForEach-Object { $_ | ConvertFrom-Json | ConvertTo-Json -Depth 10 }
```

The harness is demonstration packaging only. It does not create a production
CLI command, authorize ordinary `tc run`, or connect the lane to a worker,
router, backend, or daily-driver execution path.

## What this packet demonstrates

TriageCore has a bounded, local authorization lane that binds one WebAuthn
assertion to one versioned authorization request. The request includes the task,
decision, plan, artifact, scope, risk class, approver identity, relying party,
user-verification policy, nonce, and validity window. Changing a bound field
changes the challenge and invalidates the assertion.

This packet separates three kinds of evidence:

- **Recorded physical evidence:** a primary YubiKey was enrolled and used
  through Windows native WebAuthn on 2026-07-24. PIN-plus-touch and touch-only
  assertions both passed offline verification. The bounded hardware record is
  in [CR-YK-001](../change/requests/CR-YK-001-hardware-authorization-receipts.md#hardware-verification-record).
- **Reproducible automated evidence:** synthetic credentials exercise real
  `python-fido2` WebAuthn structures, offline signature verification, rejection
  paths, metadata-only ledger records, and atomic claim/use behavior in
  [`tests/test_authz.py`](../../tests/test_authz.py) and
  [`tests/test_capability_claims.py`](../../tests/test_capability_claims.py).
  These tests do not prove that a physical YubiKey was present.
- **Deliberately unpublished local artifacts:** credential identifiers, COSE
  public keys, AAGUIDs, and assertion sidecars from the physical smoke run are
  not included in this public packet.

## Six proof points

### 1. A consequential action requires authorization

[`AuthorizationRequest`](../../triage_core/authz.py) binds the exact plan,
artifact, decision, and execution scope into a one-use capability. Capability
issuance requires the caller to complete full receipt verification first.

The demonstration-only harness publishes its demo release marker only after
the existing atomic claim API returns a successful claim bound to the expected
artifact, scope, claimant, and execution-attempt identifiers. A mismatched
claim is passed to the same action boundary and cannot publish the marker.
Two concurrent action attempts then prove that exactly one successful claim
can produce exactly one publication.

Current production boundary: no `tc authz` command, ordinary `tc run` path,
worker, router, or backend consumes this lane. The harness demonstrates the
existing control over one isolated sample action; it is not production
daily-driver or CLI integration. That integration is the next product gap,
not a reason to deepen this feature.

### 2. A valid enrolled hardware credential approves only the bounded claim

[`compute_challenge`](../../triage_core/authz.py) hashes the canonical,
versioned request. [`verify_receipt`](../../triage_core/fido2_adapter.py)
requires an enrolled, non-revoked credential belonging to the named approver
and verifies the relying-party hash, user-presence/user-verification policy,
credential match, origin, and assertion signature offline.

The physical YubiKey result is a dated operator record. The automated positive
path uses a synthetic enrolled credential and real `python-fido2` structures;
it is reproducible cryptographic coverage, not replacement hardware evidence.

### 3. An invalid or mismatched claim fails closed

Structural verification rejects expiry, malformed client data, the wrong
WebAuthn type, challenge mismatch, and origin mismatch. Full verification also
rejects unknown, revoked, wrong-identity, wrong-RP, wrong-key, and invalid-signature
credentials. Capability claiming separately rejects artifact, scope, immutable
binding, expiry, legacy-schema, and store failures with closed reason codes.

### 4. Concurrency prevents duplicate claim/use

[`CapabilityClaimStore`](../../triage_core/capability_claims.py) uses a local
SQLite `BEGIN IMMEDIATE` transaction before reading claim state. Independent
connections racing for one capability produce exactly one committed claim;
later attempts fail closed as already claimed. A failed, abandoned, or crashed
attempt does not restore the capability.

This proves duplicate **claim/use prevention**. It does not claim
issuance-registry protection or globally unique authorization issuance.

### 5. The ledger record is independently reviewable

The receipt remains a sidecar artifact. The JSONL ledger receives privacy-safe
metadata and digests for the receipt, request, plan, artifact, scope, approver,
capability issuance, successful claim/use, terminal state, and denials. A
reviewer can parse the JSONL without proprietary tooling and compare the
recorded receipt digest with the sidecar bytes.

The checked-in
[seven-event snapshot](hardware-bound-human-authorization/sample-ledger.jsonl)
is evidence output from the successful synthetic demonstration. It is
independently parseable and includes the receipt metadata/digest link, while
excluding the receipt sidecar and credential-identifying material.

This makes the record independently inspectable and tamper-evident across the
receipt-to-ledger digest link. These authorization events use the ordinary
unsigned ledger append path: the JSONL record does **not** cryptographically
authenticate the ledger itself, its writer, or its completeness. The checked-in
snapshot is evidence output, not a cryptographically authenticated ledger.

### 6. The human claim stays narrow

A verified assertion is evidence that the enrolled credential participated in
the bounded WebAuthn ceremony, with user verification claimed only when it was
required and verified. It is not non-repudiation, authenticator-model
attestation, or protection against a compromised local host.

**possession proves credential control—not comprehension, voluntariness, or good judgment.**

## Reproduce the software evidence

Run from the repository root:

```powershell
python -m pip install -e ".[authz,dev]"
python -c "from triage_core.fido2_adapter import ceremony_support; print(ceremony_support())"
python -m pytest tests/test_authz.py tests/test_capability_claims.py -q -p no:cacheprovider
```

For reviewer-readable proof names and assertions:

```powershell
python -m pytest tests/test_authz.py -k "challenge or mismatch or concurrent or ledger or full_verification" -vv -p no:cacheprovider
python -m pytest tests/test_capability_claims.py -k "independent_claimers or contention or binding or privacy" -vv -p no:cacheprovider
```

The tests require no network or physical authenticator. Hardware availability
can be inspected by the second command, but a physical ceremony remains an
operator-observed step and must not be inferred from synthetic test success.

## Feature freeze

The hardware-authorization feature boundary is frozen after this evidence
packet: no new authorization architecture, policy depth, credential type,
quorum, attestation, or distributed locking is part of this demonstration.
Daily-driver integration is the next product-level gap.
