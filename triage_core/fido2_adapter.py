"""python-fido2 (2.x) adapter for CR-YK-001 authorization receipts.

All optional-dependency and platform-specific code for the authorization lane
lives here, behind narrow functions that callers and tests can replace:

- ``ceremony_support()``    -> availability probe, never raises on import
- ``enroll_credential()``   -> make-credential ceremony (hardware)
- ``get_assertion_receipt()`` -> get-assertion ceremony (hardware)
- ``verify_receipt()``      -> offline verification via Fido2Server

Import rules enforced here:

- ``import triage_core`` must succeed without python-fido2 installed; this
  module imports fido2 only inside functions via the ``_import_fido2`` seam.
- ``fido2.client.windows`` crashes at import time on non-Windows platforms
  (its ctypes bindings require HRESULT), so it is imported only when
  ``sys.platform == "win32"``.
- Non-Windows systems without a CTAP HID device get a controlled
  ``CeremonySupport(available=False, ...)`` result, never an import crash.

Written against python-fido2 2.2.x. The 1.x style ``WindowsClient(origin)``
constructor no longer exists; 2.x clients take a ``ClientDataCollector``.

Verification note: ``Fido2Server.authenticate_complete`` checks clientData
type, challenge equality (constant-time), pinned origin, RP-ID hash, the
user-presence flag, user-verification when required, credential membership,
and the signature over ``authenticatorData || SHA256(clientDataJSON)``. It
does not enforce signature counters; zero counters (common on current keys)
are therefore accepted, deliberately.

Hardware status: the ceremony functions follow the verified 2.x API surface
but remain UNVERIFIED against a physical YubiKey until the CR-YK-001 manual
checklist is executed on Windows hardware.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from triage_core.authz import (
    ORIGIN,
    RP_ID,
    RP_NAME,
    AuthorizationRequest,
    AuthzError,
    AuthzHardwareUnavailable,
    AuthzVerificationError,
    CredentialStore,
    EnrolledCredential,
    HumanAuthorizationReceipt,
    b64url_decode,
    b64url_encode,
    compute_challenge,
    normalize_identity,
    verify_receipt_structure,
)

VERIFY_FAIL_UNKNOWN_CREDENTIAL = "credential_not_enrolled"
VERIFY_FAIL_REVOKED_CREDENTIAL = "credential_revoked"
VERIFY_FAIL_RP_MISMATCH = "credential_rp_mismatch"
VERIFY_FAIL_APPROVER_MISMATCH = "credential_approver_mismatch"


def _import_fido2():
    """Import seam for the optional dependency; tests may monkeypatch this."""
    try:
        import fido2.cbor
        import fido2.cose
        import fido2.server
        import fido2.utils
        import fido2.webauthn
    except ImportError as exc:
        raise AuthzHardwareUnavailable(
            "python-fido2 >= 2.0 is required for this operation. "
            'Install the optional extra: pip install -e ".[authz]"'
        ) from exc
    import fido2 as _fido2

    return _fido2


def _list_ctap_devices():
    """Enumerate CTAP HID devices; seam for tests. Requires fido2 installed."""
    from fido2.hid import CtapHidDevice

    return list(CtapHidDevice.list_devices())


# --- Availability -------------------------------------------------------------

@dataclass(frozen=True)
class CeremonySupport:
    available: bool
    mechanism: str      # "windows_native" | "ctap_hid" | "none"
    detail: str = ""


def ceremony_support() -> CeremonySupport:
    """Report how a live ceremony could run on this host. Never raises."""
    try:
        _import_fido2()
    except AuthzHardwareUnavailable as exc:
        return CeremonySupport(False, "none", str(exc))

    if sys.platform == "win32":
        try:
            from fido2.client.windows import WindowsClient  # guarded import

            if WindowsClient.is_available():
                return CeremonySupport(True, "windows_native")
            return CeremonySupport(
                False, "none", "Windows WebAuthn API not available on this build"
            )
        except Exception as exc:  # pragma: no cover - windows only
            return CeremonySupport(False, "none", f"windows client error: {exc}")

    try:
        devices = _list_ctap_devices()
    except Exception as exc:
        return CeremonySupport(False, "none", f"CTAP HID enumeration failed: {exc}")
    if devices:
        return CeremonySupport(True, "ctap_hid", f"{len(devices)} device(s)")
    return CeremonySupport(False, "none", "no FIDO2 authenticator found")


def _make_client():  # pragma: no cover - requires hardware or Windows API
    """Build a 2.x WebAuthn client for the current platform."""
    _import_fido2()
    from fido2.client import DefaultClientDataCollector, Fido2Client

    collector = DefaultClientDataCollector(ORIGIN)

    if sys.platform == "win32":
        from fido2.client.windows import WindowsClient  # guarded import

        if WindowsClient.is_available():
            return WindowsClient(client_data_collector=collector)

    devices = _list_ctap_devices()
    if not devices:
        raise AuthzHardwareUnavailable("no FIDO2 authenticator found")
    return Fido2Client(devices[0], client_data_collector=collector)


# --- Ceremonies (HARDWARE-UNVERIFIED until the manual checklist runs) ---------

def enroll_credential(
    human_id: str,
    label: str,
    rp_id: Optional[str] = None,
) -> EnrolledCredential:  # pragma: no cover - requires hardware
    """Run a make-credential ceremony; return public material for the store.

    Stores credential ID, COSE public key, and AAGUID only — never PINs,
    private keys, or secrets (those never leave the authenticator).
    """
    import os as _os

    fido2 = _import_fido2()
    from fido2.webauthn import (
        PublicKeyCredentialCreationOptions,
        PublicKeyCredentialParameters,
        PublicKeyCredentialRpEntity,
        PublicKeyCredentialType,
        PublicKeyCredentialUserEntity,
    )

    resolved_rp = rp_id or RP_ID
    human_id = normalize_identity(human_id)
    if not human_id:
        raise AuthzError("human_id must be a non-empty stable identifier")
    client = _make_client()
    options = PublicKeyCredentialCreationOptions(
        rp=PublicKeyCredentialRpEntity(id=resolved_rp, name=RP_NAME),
        user=PublicKeyCredentialUserEntity(
            id=human_id.encode("utf-8"), name=human_id, display_name=label
        ),
        challenge=_os.urandom(32),
        pub_key_cred_params=[
            PublicKeyCredentialParameters(
                type=PublicKeyCredentialType.PUBLIC_KEY, alg=-7  # ES256
            )
        ],
    )
    registration = client.make_credential(options)
    credential_data = registration.response.attestation_object.auth_data.credential_data
    if credential_data is None:
        raise AuthzVerificationError("registration returned no credential data")
    return EnrolledCredential(
        human_id=human_id,
        label=label,
        credential_id=b64url_encode(credential_data.credential_id),
        public_key_cose=b64url_encode(fido2.cbor.encode(credential_data.public_key)),
        aaguid=bytes(credential_data.aaguid).hex(),
        rp_id=resolved_rp,
    )


def get_assertion_receipt(
    request: AuthorizationRequest,
    credential: EnrolledCredential,
) -> HumanAuthorizationReceipt:  # pragma: no cover - requires hardware
    """Run a get-assertion ceremony over ``compute_challenge(request)``.

    UV policy comes from the request: ``user_verification_required=True``
    demands a PIN/biometric ceremony; otherwise user presence suffices.
    """
    _import_fido2()
    from fido2.webauthn import (
        PublicKeyCredentialDescriptor,
        PublicKeyCredentialRequestOptions,
        PublicKeyCredentialType,
        UserVerificationRequirement,
    )

    client = _make_client()
    options = PublicKeyCredentialRequestOptions(
        challenge=compute_challenge(request),
        rp_id=request.rp_id,
        allow_credentials=[
            PublicKeyCredentialDescriptor(
                type=PublicKeyCredentialType.PUBLIC_KEY,
                id=b64url_decode(credential.credential_id),
            )
        ],
        user_verification=(
            UserVerificationRequirement.REQUIRED
            if request.user_verification_required
            else UserVerificationRequirement.PREFERRED
        ),
    )
    selection = client.get_assertion(options)
    response = selection.get_response(0)
    return HumanAuthorizationReceipt(
        request=request,
        credential_id=b64url_encode(response.raw_id),
        assertion_response=dict(response),
        user_verified=response.response.authenticator_data.is_user_verified(),
    )


# --- Offline verification -----------------------------------------------------

def verify_receipt(
    receipt: HumanAuthorizationReceipt,
    store: CredentialStore,
    now: Optional[datetime] = None,
) -> EnrolledCredential:
    """Full offline verification of a receipt against enrolled credentials.

    Order:
      1. Structural checks (expiry, clientData type/challenge/origin) — no
         dependency required, fails fast with a stable reason code.
      2. Credential policy: enrolled, not revoked, RP matches the request.
      3. ``Fido2Server.authenticate_complete``: RP-ID hash, user presence,
         user verification when the request required it, credential match,
         and the assertion signature. Counters are not enforced.

    Returns the enrolled credential on success; raises
    AuthzVerificationError otherwise.
    """
    structural = verify_receipt_structure(receipt, now)
    if not structural.passed:
        raise AuthzVerificationError(structural.failure_reason)

    enrolled = store.find_by_credential_id(receipt.credential_id)
    if enrolled is None:
        raise AuthzVerificationError(VERIFY_FAIL_UNKNOWN_CREDENTIAL)
    if enrolled.revoked:
        raise AuthzVerificationError(VERIFY_FAIL_REVOKED_CREDENTIAL)
    if enrolled.rp_id != receipt.request.rp_id:
        raise AuthzVerificationError(VERIFY_FAIL_RP_MISMATCH)
    if normalize_identity(enrolled.human_id) != receipt.request.approver_identity_id:
        # The asserting credential must belong to the identity the request
        # names; otherwise any enrolled human's key could satisfy it.
        raise AuthzVerificationError(VERIFY_FAIL_APPROVER_MISMATCH)

    fido2 = _import_fido2()
    from fido2.server import Fido2Server
    from fido2.utils import websafe_encode
    from fido2.webauthn import (
        AttestedCredentialData,
        PublicKeyCredentialRpEntity,
        UserVerificationRequirement,
    )

    server = Fido2Server(
        PublicKeyCredentialRpEntity(id=receipt.request.rp_id, name=RP_NAME),
        verify_origin=lambda origin: origin == ORIGIN,
    )
    state = {
        "challenge": websafe_encode(compute_challenge(receipt.request)),
        "user_verification": (
            UserVerificationRequirement.REQUIRED
            if receipt.request.user_verification_required
            else UserVerificationRequirement.PREFERRED
        ),
    }
    registered = AttestedCredentialData.create(
        bytes.fromhex(enrolled.aaguid),
        b64url_decode(enrolled.credential_id),
        fido2.cose.CoseKey.parse(
            fido2.cbor.decode(b64url_decode(enrolled.public_key_cose))
        ),
    )
    try:
        server.authenticate_complete(
            state, [registered], receipt.assertion_response
        )
    except ValueError as exc:
        raise AuthzVerificationError(str(exc)) from exc
    except Exception as exc:
        raise AuthzVerificationError(
            f"assertion verification failed: {exc}"
        ) from exc
    return enrolled
