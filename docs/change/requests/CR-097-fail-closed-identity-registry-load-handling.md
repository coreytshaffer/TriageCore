# CR-097: Fail-Closed Identity Registry Load Handling

## Summary
Implements a narrow, fail-closed mechanism for handling identity registry (`agents.json`) load failures in reviewer-facing CLI call sites.

## Context
When an identity registry is malformed, truncated, or unreadable, the system must not leak raw exception stack traces or secret-like material to stdout/stderr. Instead, the failure should produce a bounded, safe, metadata-only output and exit with status 1.

## Changes
- **Typed Exceptions:** Added specific exceptions (`IdentityRegistryUnreadableError`, `IdentityRegistryMalformedError`, `InvalidIdentityRecordError`) to `AgentIdentityError` in `agent_identity.py`.
- **Registry Loader:** Updated `AgentIdentityRegistry.load()` to map JSON decode errors, IO errors, and validation errors to these explicit typed errors without leaking raw exception context.
- **CLI Helper:** Added `_handle_registry_load_failure` to `tc_cli.py` to intercept load failures and emit bounded output containing:
  - `reason=registry_load_failed`
  - `registry=<path>`
  - `category=<category>`
- **Guarded Call Sites:** Wrapped `tc identity list`, `tc audit --verify-signatures`, `tc audit --signed-smoke-test`, and `tc audit --signed-route-decision-smoke-test` to use the helper.

## Explicit Disclosures
- Missing registry file (`FileNotFoundError` before opening) remains empty-registry behavior; it does NOT trigger `registry_load_failed`.
- This is strictly load-error handling, not cryptographic tamper detection.
- This does not validate all key correctness.
- This does not change signing, routing, authority, or execution behavior.
- Historical ledger entries are not rewritten.
