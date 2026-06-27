# Key Rotation Lifecycle

This document provides operational guidance for managing agent identity keys in TriageCore, expanding on the `identity_rotation_recovery_policy.md` trust boundaries. It defines the mechanics of rotation, historical validation, and compromise handling.

## Rotation Metadata and Linkage

When a key is rotated, the old key is superseded by a new key. In TriageCore, this linkage is maintained simply by keeping the `agent_id` identical.
The registry (`agents.json`) allows multiple `AgentIdentity` entries for the same `agent_id`, distinguishing them by `public_key_fingerprint` and enforcing that only one key per `agent_id` can be active at a time.

For historical integrity, every rotated key must define a `rotated_at` timestamp. This explicit boundary ensures that any payload claiming to have been signed by the rotated key was signed *before* the key was removed from active duty.

## Historical Verification

Verification logic in TriageCore is designed to honor history without extending trust:

1. A signature is evaluated against all known keys for the given `agent_id`.
2. If a key cryptographically verifies the signature:
   * **Active**: Returns `True`. The signature is valid.
   * **Rotated**: Returns `True` **only if** `signed_at <= rotated_at`. Rotated keys are untrusted for signatures dated after their rotation.
   * **Revoked**: Returns `False`. The key is treated as having its trust fully rescinded.
   * **Compromised**: Raises `CompromisedKeyError`.

Signatures from rotated keys lacking a valid `signed_at` timestamp fail closed (returning `False`).

## Compromise vs Ordinary Rotation

A compromised key implies that the private key material may have been exposed. Unlike an ordinary rotation where the old key's history is still trusted, a compromised key is fundamentally untrusted.

If TriageCore verifies a signature cryptographically, but the corresponding key's status is `compromised`, it explicitly raises a `CompromisedKeyError` rather than returning `False`. This allows upstream evaluators, logs, and interfaces to differentiate between a random verification failure and a valid signature from a known-tainted identity.

A compromised key does not block verification for the entire `agent_id`. If another active or rotated key for that same `agent_id` successfully verifies the signature, the verification succeeds. The `CompromisedKeyError` is only raised if the signature specifically matches the compromised key.

## Exceptions for Compromised History

Future tooling will support explicit operator overrides (e.g., `--allow-compromised-history`) to permit historical analysis of compromised ledgers, but the default behavior is strictly fail-closed.

## Backup and Recovery Warnings

TriageCore does not support automated or implied recovery of lost keys.
Local private keys are high-value trust material. Loss of a private key means permanent loss of signing ability for that key. Public registry metadata alone does not restore signing authority.

If a key is lost, the only supported path is to rotate to a new key.

## CLI Usage

The `tc identity rotate` command is designed to manage key rotation. Currently (as of CR-084), only a dry-run preview is supported. Real rotation is not yet implemented.

To preview rotation changes:
```powershell
tc identity rotate <agent-id> --dry-run
```

This command will output the intended registry and key updates without actually modifying `agents.json` or any `.key` files on disk. The dry-run enforces constraints, such as verifying the identity is `active`, before outputting the preview.
