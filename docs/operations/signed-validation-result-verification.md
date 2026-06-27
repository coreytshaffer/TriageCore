# Signed Validation Result Verification

## Purpose
This document shows the reviewer-facing path for inspecting signed `validation_result` ledger evidence after CR-078 and CR-079.

## Command
Use the existing audit verification entrypoint with the `validation_result` kind selector:

```powershell
tc audit --verify-signatures --kind validation_result
```

## Success Example
A successful verification run stays metadata-only and reports the event type, task id, and signing identity:

```text
Validation result signature verification passed: event_type=validation_result valid_signed=1 invalid_signed=0 unsigned=0 malformed=0 skipped_non_target=3 strict=off
PASS event_type=validation_result task_id=validation-task agent_id=validator-tools
```

## Failure Examples
Verification failures also stay metadata-only and report a safe failure reason without echoing raw prompt or payload content:

```text
Validation result signature verification failed: event_type=validation_result valid_signed=0 invalid_signed=1 unsigned=0 malformed=0 skipped_non_target=0 strict=off
FAIL event_type=validation_result task_id=validation-task agent_id=validator-tools reason=signature_mismatch
```

```text
Validation result signature verification failed: event_type=validation_result valid_signed=0 invalid_signed=1 unsigned=0 malformed=0 skipped_non_target=0 strict=off
FAIL event_type=validation_result task_id=validation-task agent_id=missing-validator reason=unknown_agent
```

```text
Validation result signature verification failed: event_type=validation_result valid_signed=0 invalid_signed=1 unsigned=0 malformed=0 skipped_non_target=0 strict=off
FAIL event_type=validation_result task_id=validation-task agent_id=revoked-validator reason=revoked_agent
```

## Boundary
A valid signature proves provenance and tamper evidence only.

It does not prove:
- approval
- safety
- correctness
- authority escalation

This keeps cryptographic identity separate from human review, admission decisions, and other safety controls.
