# CR-125: Preflight Privacy Before Ledger Persistence

## Status

Implemented

## Summary

Preflight the complete `tc run` `TaskPacket` before constructing or writing to
the ledger. Privacy-blocked input now exits with code 2 before a ledger event is
created. Successful runs store a fixed content-withheld task marker and input
lengths instead of raw prompt or data text.

## Scope

- Verify the `tc run` packet before ledger construction and task-event writes.
- Replace persisted `tc run` prompt/data text with fixed metadata and lengths.
- Extend the persistent-artifact invariant with high-confidence PII, credential,
  and precise-location value patterns from the privacy scanner.
- Make `tc audit --privacy-invariants` report those value-pattern findings
  without echoing content.
- Add offline tests for prompt/data absence and blocked-run no-residue behavior.

## Non-Goals

- No historical ledger rewrite or migration.
- No full DLP engine or arbitrary free-text safety classifier.
- No hash or content fingerprint of prompt/data input.
- No routing, approval, signature, or external-runtime behavior change.

## Validation

- `python -m pytest -q tests/test_tc_run_cli.py tests/test_privacy_invariants.py tests/test_audit_cli.py`
- `python -m pytest -q`
- `git diff --check`
