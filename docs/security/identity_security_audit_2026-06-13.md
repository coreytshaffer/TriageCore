# Identity Security Audit - 2026-06-13

## Scope

This audit reviews the CR-020 identity and signing work through Phase 5:

- identity metadata model
- local Ed25519 key generation
- private key storage boundary
- public identity registry
- opt-in `route_audit` signing
- `route_audit` verification CLI
- identity initialization and listing CLI

This audit does not expand signing coverage or modify runtime behavior.

## Conclusion

CR-020 is usable as a local identity and signed-`route_audit` foundation, but
it should remain open. Event signing should not expand beyond `route_audit`
until key revocation, rotation, recovery, and filesystem-permission policy are
defined.

The implemented controls passed their focused and full-suite tests. The live
ledger also passed the persistent privacy audit and default signature audit.
However, the live ledger currently contains no signed `route_audit` records, so
the production workspace has not yet demonstrated a successful signed-event
verification outside the test suite.

## Current Controls

- Private keys are stored under `.triagecore/identity/keys/`.
- `.triagecore/identity/keys/` is gitignored.
- Public identity metadata is stored in `.triagecore/identity/agents.json`.
- Signing is opt-in and exposed programmatically through `TaskLedger`.
- Signed ledger support is limited to `route_audit`.
- Persistent privacy validation runs before a `route_audit` payload is signed
  and written.
- `tc audit --verify-signatures` verifies signed `route_audit` records.
- `tc audit --verify-signatures --strict` rejects unsigned legacy
  `route_audit` records.
- `tc audit --privacy-invariants` scans persistent records for forbidden raw
  content fields.
- `tc identity list` prints selected public metadata and does not print private
  key contents.

## Privacy Review

- [x] No private key material is printed by `tc identity list`.
- [x] No private key material is written to ledger payloads.
- [x] Raw `prompt`, `data`, and `content` fields are rejected before signing.
- [x] Signature verification prints aggregate counts rather than payload data.
- [x] The live privacy invariant audit passed.
- [x] Signature verification output is counts-only.

Evidence:

- `TaskLedger.append_signed_route_audit_event()` calls the persistent privacy
  invariant before constructing or signing the ledger event.
- Public identity metadata and error tests assert that private key material is
  not serialized or echoed.
- CLI tests assert that signed and unsigned route reasons are not printed by
  signature verification.

## Security Review

- [x] Duplicate identity creation fails.
- [x] Unknown agents fail verification.
- [x] Revoked or inactive agents fail authorization and verification.
- [x] Unauthorized capabilities fail before signing and during verification.
- [x] Tampered signed `route_audit` payloads fail verification.
- [x] Unsupported algorithms fail clearly.
- [x] Unsigned legacy `route_audit` records remain allowed by default.
- [x] Strict mode fails on unsigned legacy `route_audit` records.

## Findings

### Medium: private key protection relies on default filesystem behavior

Private keys are unencrypted PKCS8 files. The implementation creates the key
directory and writes the key, but it does not set or validate restrictive file
permissions. No live identity directory existed during this audit, so a live
Windows ACL could not be verified.

Recommendation: define a Windows and POSIX permission policy, apply it during
key creation, and add a deterministic permission check where the platform
supports one.

### Medium: identity creation is not transactional

`AgentIdentityRegistry.generate_identity()` saves public registry metadata
before writing the private key file. An interrupted or failed key write can
leave an identity registered without usable private key material.

Recommendation: write the key to a protected temporary file first, then update
the public registry, and define cleanup or recovery behavior for partial
initialization.

### Medium: key lifecycle controls are not implemented

There is no operator CLI for revocation, rotation, backup, recovery, or
deletion. Revocation is enforced by the model and verification code, but an
operator cannot yet perform the lifecycle action through supported commands.

Recommendation: implement revocation before expanding signed event types, then
document rotation and recovery semantics.

### Low: the public identity registry is not gitignored

The private key directory is ignored, but
`.triagecore/identity/agents.json` is not. The registry contains public
material, not secrets, but it is local operational metadata and could be
committed unintentionally.

Recommendation: decide explicitly whether identity registries are portable
project artifacts or local runtime state. If local, add the registry path to
`.gitignore`.

### Low: identity initialization prints the private key path

`tc identity init` does not print key contents, but it prints the full local
private key path. This can expose the operator username and workspace layout in
shared terminal captures.

Recommendation: print a repository-relative path or a general confirmation
instead of the full path.

### Evidence gap: no signed event exists in the live ledger

The live signature audit found six unsigned legacy `route_audit` records and
zero signed records. Signed-event success is covered by automated tests, but
the current workspace has no operator-visible signed-event proof.

Recommendation: add a separate, explicit signed self-test only after key
lifecycle policy is settled. It must remain metadata-only and opt-in.

## Known Limitations

- Private keys are unencrypted local files.
- No explicit private-key permission hardening is implemented.
- No key rotation CLI exists.
- No revocation CLI exists.
- No deletion, backup, or recovery flow exists.
- No full ledger signing chain or previous-event hash exists.
- Only `route_audit` supports signed ledger metadata.
- `tc identity init` prints the private key path, but not key contents.
- Route-audit signing is currently a programmatic opt-in path, not a dedicated
  operator signing command.

## Validation Evidence

Run on June 13, 2026:

```text
python -m pytest -q
294 passed, 2 skipped

tc audit --privacy-invariants
Privacy invariant audit passed: 690 record(s) checked.

tc audit --verify-signatures
passed: valid_signed=0 invalid_signed=0 unsigned=6 malformed=0

tc audit --verify-signatures --strict
failed as expected: valid_signed=0 invalid_signed=0 unsigned=6 malformed=0
```

The strict-mode failure is expected policy behavior for legacy unsigned
records, not a failure of default compatibility or signature validation.

## Recommendation

Pause signing expansion after CR-020 Phase 5. Keep Issue #4 open and complete
the following lifecycle work before signing additional event types:

1. Add an operator revocation command.
2. Define key rotation and partial-initialization recovery behavior.
3. Add backup and recovery warnings.
4. Define and enforce private-key filesystem permissions.
5. Reduce private-key path exposure in CLI output.
6. Add one explicit metadata-only signed-event smoke path.

CR-020 should continue through these lifecycle controls, then receive a final
closure audit before Issue #4 is closed.
