"""Demonstrate bounded human authorization without adding a runtime surface.

This harness uses a synthetic software WebAuthn credential and real
``python-fido2`` verification structures. It does not require, exercise, or
imply a physical YubiKey ceremony. The recorded physical YubiKey evidence
remains the separate dated operator record in CR-YK-001.

The consequential sample action changes a demo release marker from absent to
published. The action function refuses to run without a successful atomic
capability claim. Two simultaneous action attempts race for one capability;
exactly one may claim it and publish the marker.

The emitted JSONL is independently parseable and privacy-checked, but its
ordinary authorization events are unsigned. It does not cryptographically
authenticate the ledger, its writer, or its completeness. Possession proves
credential control—not comprehension, voluntariness, or good judgment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from fido2 import cbor as fido2_cbor
from fido2.cose import ES256
from fido2.webauthn import (
    AuthenticationResponse,
    AuthenticatorAssertionResponse,
    AuthenticatorData,
    CollectedClientData,
)

from triage_core.authz import (
    ORIGIN,
    AuthorizationRequest,
    CapabilityClaim,
    CredentialStore,
    EnrolledCredential,
    HumanAuthorizationReceipt,
    b64url_encode,
    claim_capability,
    compute_challenge,
    finalize_capability,
    issue_capability,
    record_receipt,
)
from triage_core.capability_claims import CLAIM_OK, STATE_COMPLETED
from triage_core.fido2_adapter import verify_receipt
from triage_core.task_ledger import TaskLedger

DEMO_NAME = "hardware-bound-human-authorization"
ACTION_NAME = "publish-demo-release-marker"
ACTION_BYTES = b'{"release":"synthetic-authorization-demo","state":"published"}\n'
ACTION_PLAN = b"Publish the bounded synthetic authorization demo release marker."
ACTION_SCOPE = b"demo-only:publish-one-release-marker"
TASK_ID = "hardware-authz-evidence-demo"
DECISION_ID = "gd-hardware-authz-evidence"
APPROVER_ID = "human-demo"
POLICY_VERSION = "cr-yk-evidence-v1"
SYNTHETIC_CREDENTIAL_ID = b"synthetic-demo-credential"
DEFAULT_OUTPUT_DIR = ".triagecore/hardware-authorization-evidence"
ACTION_FILE_NAME = "consequential-action.json"
LEDGER_FILE_NAME = "ledger.jsonl"


def _digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _build_request(now: datetime) -> AuthorizationRequest:
    return AuthorizationRequest(
        decision_id=DECISION_ID,
        artifact_byte_digest=_digest(ACTION_BYTES),
        plan_body_digest=_digest(ACTION_PLAN),
        task_id=TASK_ID,
        risk_class="high",
        policy_version=POLICY_VERSION,
        approver_identity_id=APPROVER_ID,
        user_verification_required=True,
        scope_digest=_digest(ACTION_SCOPE),
        nonce=str(uuid.uuid4()),
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=10)).isoformat(),
    )


def _make_synthetic_receipt(
    request: AuthorizationRequest,
    now: datetime,
) -> tuple[HumanAuthorizationReceipt, EnrolledCredential]:
    """Create valid software evidence; this is explicitly not hardware evidence."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = ES256.from_cryptography_key(private_key.public_key())
    enrolled = EnrolledCredential(
        human_id=APPROVER_ID,
        label="synthetic software credential for public evidence",
        credential_id=b64url_encode(SYNTHETIC_CREDENTIAL_ID),
        public_key_cose=b64url_encode(fido2_cbor.encode(public_key)),
    )

    client_data = CollectedClientData.create(
        type="webauthn.get",
        challenge=compute_challenge(request),
        origin=ORIGIN,
    )
    rp_hash = hashlib.sha256(request.rp_id.encode("utf-8")).digest()
    flags = 0x01 | 0x04  # user presence and user verification
    authenticator_data = AuthenticatorData(
        rp_hash + bytes([flags]) + struct.pack(">I", 0)
    )
    signature = private_key.sign(
        bytes(authenticator_data) + client_data.hash,
        ec.ECDSA(hashes.SHA256()),
    )
    wire_response = dict(
        AuthenticationResponse(
            raw_id=SYNTHETIC_CREDENTIAL_ID,
            response=AuthenticatorAssertionResponse(
                client_data=client_data,
                authenticator_data=authenticator_data,
                signature=signature,
            ),
        )
    )
    receipt = HumanAuthorizationReceipt(
        request=request,
        credential_id=b64url_encode(SYNTHETIC_CREDENTIAL_ID),
        assertion_response=json.loads(json.dumps(wire_response)),
        user_verified=True,
        recorded_at=now.isoformat(),
    )
    return receipt, enrolled


def _perform_consequential_action(
    claim: CapabilityClaim,
    action_path: Path,
    ledger: TaskLedger,
    *,
    expected_claimant_id: str,
    expected_attempt_id: str,
) -> bool:
    """Publish the marker only after the expected successful atomic claim."""
    if (
        not claim.allowed
        or claim.reason_code != CLAIM_OK
        or claim.claimant_id != expected_claimant_id
        or claim.execution_attempt_id != expected_attempt_id
    ):
        return False

    try:
        with action_path.open("xb") as handle:
            handle.write(ACTION_BYTES)
    except FileExistsError:
        return False

    ledger.append_event(
        TASK_ID,
        "consequential_demo_action_executed",
        {
            "action_name": ACTION_NAME,
            "artifact_byte_digest": _digest(ACTION_BYTES),
            "scope_digest": _digest(ACTION_SCOPE),
            "claimant_id": expected_claimant_id,
            "execution_attempt_id": expected_attempt_id,
            "result": "published",
        },
    )
    return True


def _prepare_output_dir(raw_path: str) -> tuple[Path, str]:
    requested = Path(raw_path)
    if requested.is_absolute() or ".." in requested.parts:
        raise ValueError("output directory must be a safe repository-relative path")
    if requested.exists() and any(requested.iterdir()):
        raise ValueError(f"output directory is not empty: {requested}")
    requested.mkdir(parents=True, exist_ok=True)
    return requested, str(requested)


def _validate_jsonl(path: Path) -> list[dict]:
    events = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TypeError(f"ledger line {line_number} is not an object")
            events.append(value)
    if not events:
        raise RuntimeError("ledger contains no events")
    return events


def run_demo(output_dir: str) -> dict:
    run_dir, portable_ledger_dir = _prepare_output_dir(output_dir)
    action_path = run_dir / ACTION_FILE_NAME
    ledger = TaskLedger(ledger_dir=portable_ledger_dir)
    now = datetime.now(timezone.utc)

    request = _build_request(now)
    receipt, synthetic_enrollment = _make_synthetic_receipt(request, now)
    store = CredentialStore(ledger_dir=portable_ledger_dir)
    store.add(synthetic_enrollment)

    verified = verify_receipt(receipt, store, now=now)
    if verified.human_id != request.approver_identity_id:
        raise RuntimeError("synthetic enrolled identity did not match bounded request")

    record_receipt(ledger, receipt, ledger_dir=portable_ledger_dir)
    capability_id = issue_capability(ledger, receipt, now=now)

    mismatch = claim_capability(
        ledger,
        TASK_ID,
        capability_id,
        _digest(b"mismatched-action-bytes"),
        request.scope_digest,
        claimant_id="demo-mismatch-attempt",
        execution_attempt_id="mismatch-attempt",
        now=now,
    )
    if mismatch.allowed:
        raise RuntimeError("mismatched claim unexpectedly succeeded")
    if _perform_consequential_action(
        mismatch,
        action_path,
        ledger,
        expected_claimant_id="demo-mismatch-attempt",
        expected_attempt_id="mismatch-attempt",
    ):
        raise RuntimeError("consequential action ran without a valid claim")
    if action_path.exists():
        raise RuntimeError("mismatched claim changed consequential action state")

    barrier = threading.Barrier(2)
    result_lock = threading.Lock()
    attempts: list[dict] = []

    def action_attempt(index: int) -> None:
        claimant_id = f"demo-action-agent-{index}"
        attempt_id = f"concurrent-action-attempt-{index}"
        own_ledger = TaskLedger(ledger_dir=portable_ledger_dir)
        barrier.wait()
        claim = claim_capability(
            own_ledger,
            TASK_ID,
            capability_id,
            request.artifact_byte_digest,
            request.scope_digest,
            claimant_id=claimant_id,
            execution_attempt_id=attempt_id,
            now=now,
        )
        action_ran = _perform_consequential_action(
            claim,
            action_path,
            own_ledger,
            expected_claimant_id=claimant_id,
            expected_attempt_id=attempt_id,
        )
        terminal_recorded = False
        if action_ran:
            terminal = finalize_capability(
                own_ledger,
                TASK_ID,
                capability_id,
                STATE_COMPLETED,
                claimant_id=claimant_id,
                execution_attempt_id=attempt_id,
                now=now,
            )
            terminal_recorded = terminal.allowed
        with result_lock:
            attempts.append(
                {
                    "claimant_id": claimant_id,
                    "execution_attempt_id": attempt_id,
                    "claim_allowed": claim.allowed,
                    "claim_reason": claim.reason_code,
                    "action_ran": action_ran,
                    "terminal_recorded": terminal_recorded,
                }
            )

    threads = [
        threading.Thread(target=action_attempt, args=(index,))
        for index in range(2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    if sum(bool(item["claim_allowed"]) for item in attempts) != 1:
        raise RuntimeError("concurrent claims did not produce exactly one winner")
    if sum(bool(item["action_ran"]) for item in attempts) != 1:
        raise RuntimeError("concurrent action attempts did not execute exactly once")
    if sum(bool(item["terminal_recorded"]) for item in attempts) != 1:
        raise RuntimeError("winning action did not record exactly one terminal state")
    if not action_path.exists() or action_path.read_bytes() != ACTION_BYTES:
        raise RuntimeError("bounded consequential action output is invalid")

    ledger_path = run_dir / LEDGER_FILE_NAME
    events = _validate_jsonl(ledger_path)
    event_types = [event.get("event_type") for event in events]
    required_types = {
        "human_authorization_receipt",
        "execution_capability_issued",
        "execution_capability_denied",
        "execution_capability_claimed",
        "execution_capability_terminal",
        "consequential_demo_action_executed",
    }
    if not required_types.issubset(event_types):
        raise RuntimeError("ledger is missing required demonstration evidence")

    return {
        "demo": DEMO_NAME,
        "evidence_kind": "synthetic_software_webauthn_only",
        "physical_yubikey_claim": False,
        "bounded_action": ACTION_NAME,
        "mismatched_claim_allowed": mismatch.allowed,
        "concurrent_attempts": sorted(
            attempts, key=lambda item: item["execution_attempt_id"]
        ),
        "action_executions": sum(bool(item["action_ran"]) for item in attempts),
        "ledger_event_count": len(events),
        "ledger_path": str(ledger_path),
        "ledger_authenticity": "unsigned_jsonl_not_cryptographically_authenticated",
        "human_intent_limitation": (
            "possession proves credential control—not comprehension, "
            "voluntariness, or good judgment"
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run a synthetic, demonstration-only hardware-authorization "
            "evidence path. This does not exercise a physical YubiKey."
        )
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=(
            "empty repository-relative evidence directory "
            f"(default: {DEFAULT_OUTPUT_DIR})"
        ),
    )
    args = parser.parse_args()
    try:
        summary = run_demo(args.output_dir)
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        parser.exit(1, f"hardware authorization evidence demo failed: {exc}\n")
    print(json.dumps(summary, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
