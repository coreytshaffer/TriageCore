"""Mediated single-file effect contract (CR-OC-001A).

A pure representation and validation layer for exactly one file-content
replacement. It reads no file, writes no file, opens no connection, launches no
subprocess, and touches no database.

What this module establishes:

- a single-file content replacement can be represented deterministically;
- it can be bound to an exact pre-content digest and an exact post-content
  digest over exact bytes;
- it can be bound to a unique client request, a client-declared invocation
  context, and a distinct broker-connection identifier field;
- a privacy-safe metadata projection can be produced from it.

What this module does **not** establish, and must never be cited for:

- that OpenClaw is contained;
- that the invocation context is authenticated;
- that ``broker_connection_id`` was broker-generated or bound to a connection;
- that ``target_file_id`` came from a trusted allowlist;
- that replay is prevented in practice;
- that paths are safe;
- that a capability was claimed;
- that any file was actually changed;
- that OS privilege separation exists.

Provenance is asserted, never established. Three fields are validated
*syntactically* and cannot be validated *substantively* here:
``broker_connection_id``, every member of the declared invocation context, and
``target_file_id``. Digesting a value makes it tamper-evident after the fact; it
does not make it true when first supplied. A pure module cannot tell a
broker-minted identifier from a forged one. The terms *broker-generated* and
*broker-authenticated* belong to CR-OC-001D, not here.

The content claim is a content claim only:

    the exact authorized pre-content digest became the exact authorized
    post-content digest

That is not a claim about exact filesystem state. Atomic replacement may change
timestamps and file identity. Owner, DACL, regular-file status, and workspace
containment are CR-OC-001C's responsibility, with their own tests.

``canonical_relpath`` is integrity-bound into the effect digest so evidence
stays consistent, but it is never a resolution channel. Resolution is
exclusively through ``target_file_id``. This module never joins it onto a root,
resolves it, opens it, or infers allowlist membership from it.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional, Tuple

# --- Schemas ------------------------------------------------------------------
# The discriminator lives inside the canonical input rather than being applied
# as a byte prefix, matching the established house pattern for domain-separated
# identity envelopes, so two objects with otherwise identical fields cannot
# collide.

SCHEMA_FILE_DESCRIPTOR = "triagecore.mediated_file_descriptor.v1"
SCHEMA_DECLARED_CONTEXT = "triagecore.mediated_declared_context.v1"
SCHEMA_FILE_EFFECT = "triagecore.mediated_file_effect.v1"
SCHEMA_CLIENT_REQUEST = "triagecore.mediated_client_request.v1"
SCHEMA_PLAN_LINKAGE = "triagecore.mediated_plan_linkage.v1"

OPERATION_REPLACE = "replace"
ENCODING_UTF8 = "utf-8"

# --- Closed validation vocabulary ---------------------------------------------
# House style: no free-text reason ever enters evidence. Conditions this module
# cannot observe -- path traversal, symlinks, broker availability, capability
# lifecycle, store conditions, execution results -- are deliberately absent. A
# code for an undetectable condition would be a false capability claim in
# vocabulary form.

VALIDATION_OK = "ok"
INVALID_OPERATION = "invalid_operation"
INVALID_TARGET_FILE_ID = "invalid_target_file_id"
INVALID_CLIENT_REQUEST_ID = "invalid_client_request_id"
INVALID_DIGEST = "invalid_digest"
INVALID_DECLARED_CONTEXT = "invalid_declared_context"
INVALID_BROKER_BINDING = "invalid_broker_binding"
CONTENT_NOT_UTF8 = "content_not_utf8"
CONTENT_SIZE_EXCEEDED = "content_size_exceeded"
POST_DIGEST_MISMATCH = "post_digest_mismatch"
REQUEST_ID_REUSE_MISMATCH = "request_id_reuse_mismatch"

VALIDATION_REASONS = frozenset(
    {
        VALIDATION_OK,
        INVALID_OPERATION,
        INVALID_TARGET_FILE_ID,
        INVALID_CLIENT_REQUEST_ID,
        INVALID_DIGEST,
        INVALID_DECLARED_CONTEXT,
        INVALID_BROKER_BINDING,
        CONTENT_NOT_UTF8,
        CONTENT_SIZE_EXCEEDED,
        POST_DIGEST_MISMATCH,
        REQUEST_ID_REUSE_MISMATCH,
    }
)

# --- Replay classification vocabulary -----------------------------------------

REPLAY_NEW_REQUEST = "new_request"
REPLAY_IDEMPOTENT = "idempotent_replay"
REPLAY_REUSE_MISMATCH = REQUEST_ID_REUSE_MISMATCH

REPLAY_CLASSIFICATIONS = frozenset(
    {REPLAY_NEW_REQUEST, REPLAY_IDEMPOTENT, REPLAY_REUSE_MISMATCH}
)

_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

# A file ID is an opaque token, never a path. Rejecting these separators is not
# a path-safety check -- it is a type check that keeps the two vocabularies from
# being confused at the boundary.
_PATH_LIKE = ("/", "\\", "..", ":", "~")

_MAX_IDENTIFIER_LENGTH = 512
_MAX_RELPATH_LENGTH = 4096


class MediatedEffectError(Exception):
    """Base error for the mediated effect contract."""


class MediatedValidationError(MediatedEffectError):
    """A proposal or object failed closed. Carries a closed reason code."""

    def __init__(self, reason_code: str) -> None:
        if reason_code not in VALIDATION_REASONS:
            raise MediatedContractError(
                f"reason_code must be one of {sorted(VALIDATION_REASONS)}"
            )
        super().__init__(reason_code)
        self.reason_code = reason_code


class MediatedContractError(MediatedEffectError):
    """A caller violated this module's contract.

    Distinct from ``MediatedValidationError`` on purpose: a caller defect is not
    a validation outcome and must never be reported through the closed
    vocabulary, which would misdescribe a bug as a decision about the input.
    """


# --- Canonicalization ---------------------------------------------------------


def _canonical_json_bytes(value: Any) -> bytes:
    """Canonical JSON per the approved contract.

    Implemented locally rather than imported from any existing module: this
    module reuses the canonicalization *contract*, not another module's private
    helper or dependency graph.
    """
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _digest_of(mapping: Mapping[str, Any]) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json_bytes(dict(mapping))).hexdigest()


# --- Field validation ---------------------------------------------------------
# Security-bound identifiers are validated or rejected, never silently
# normalized. Nothing here strips, folds case, or rewrites a value: task_id and
# decision_id stay case-exact, and a value that would need normalizing to be
# acceptable is rejected instead.


def _check_identifier(value: Any, reason_code: str) -> str:
    if not isinstance(value, str):
        raise MediatedValidationError(reason_code)
    if not value or len(value) > _MAX_IDENTIFIER_LENGTH:
        raise MediatedValidationError(reason_code)
    if value != value.strip():
        raise MediatedValidationError(reason_code)
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise MediatedValidationError(reason_code)
    return value


def _check_digest(value: Any) -> str:
    if not isinstance(value, str) or not _DIGEST_PATTERN.match(value):
        raise MediatedValidationError(INVALID_DIGEST)
    return value


def _check_target_file_id(value: Any) -> str:
    identifier = _check_identifier(value, INVALID_TARGET_FILE_ID)
    if any(marker in identifier for marker in _PATH_LIKE):
        raise MediatedValidationError(INVALID_TARGET_FILE_ID)
    return identifier


def _check_canonical_relpath(value: Any) -> str:
    """Type and shape only.

    Deliberately not a safety check. This module does not resolve, join, open,
    or existence-check the value, and must not imply that it is safe.
    """
    if not isinstance(value, str):
        raise MediatedValidationError(INVALID_TARGET_FILE_ID)
    if not value or len(value) > _MAX_RELPATH_LENGTH:
        raise MediatedValidationError(INVALID_TARGET_FILE_ID)
    if "\x00" in value:
        raise MediatedValidationError(INVALID_TARGET_FILE_ID)
    return value


def _check_size(value: Any, reason_code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MediatedValidationError(reason_code)
    return value


def _require_exact_fields(
    mapping: Any,
    expected: Tuple[str, ...],
    reason_code: str,
) -> Dict[str, Any]:
    """Closed field set: unknown, missing, and null values all fail closed.

    Optional values are forbidden rather than omitted, so an omitted-key form
    cannot exist and two payloads cannot differ by key presence alone.
    """
    if not isinstance(mapping, Mapping):
        raise MediatedValidationError(reason_code)
    keys = set(mapping.keys())
    if keys != set(expected):
        raise MediatedValidationError(reason_code)
    for key in expected:
        if mapping[key] is None:
            raise MediatedValidationError(reason_code)
    return {key: mapping[key] for key in expected}


# --- Canonical objects --------------------------------------------------------


@dataclass(frozen=True)
class MediatedFileDescriptor:
    """An allowlisted file descriptor.

    Produced by a later trusted allowlist-enumeration phase. This slice defines
    and validates only its canonical representation; it does not enumerate,
    resolve, or establish that ``target_file_id`` came from the allowlist.
    """

    target_file_id: str
    canonical_relpath: str
    maximum_size_bytes: int
    encoding: str = ENCODING_UTF8

    FIELDS = (
        "schema",
        "target_file_id",
        "canonical_relpath",
        "encoding",
        "maximum_size_bytes",
    )

    def __post_init__(self) -> None:
        _check_target_file_id(self.target_file_id)
        _check_canonical_relpath(self.canonical_relpath)
        if self.encoding != ENCODING_UTF8:
            raise MediatedValidationError(INVALID_OPERATION)
        size = _check_size(self.maximum_size_bytes, CONTENT_SIZE_EXCEEDED)
        if size <= 0:
            raise MediatedValidationError(CONTENT_SIZE_EXCEEDED)

    def as_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema": SCHEMA_FILE_DESCRIPTOR,
            "target_file_id": self.target_file_id,
            "canonical_relpath": self.canonical_relpath,
            "encoding": self.encoding,
            "maximum_size_bytes": self.maximum_size_bytes,
        }

    def digest(self) -> str:
        return _digest_of(self.as_canonical_dict())

    @classmethod
    def from_mapping(cls, mapping: Any) -> "MediatedFileDescriptor":
        fields = _require_exact_fields(mapping, cls.FIELDS, INVALID_TARGET_FILE_ID)
        if fields["schema"] != SCHEMA_FILE_DESCRIPTOR:
            raise MediatedValidationError(INVALID_OPERATION)
        return cls(
            target_file_id=fields["target_file_id"],
            canonical_relpath=fields["canonical_relpath"],
            maximum_size_bytes=fields["maximum_size_bytes"],
            encoding=fields["encoding"],
        )


@dataclass(frozen=True)
class DeclaredInvocationContext:
    """Client-declared facts. Not authenticated identity.

    Every field arrives from the untrusted side. The digest makes them
    tamper-evident after the fact; it does not make them true. Nothing in this
    module authenticates the runtime, the agent, or the session, and no accessor
    presents these values as authenticated identity.
    """

    runtime_id: str
    runtime_version: str
    openclaw_config_digest: str
    agent_id: str
    session_id: str
    tool_name: str
    client_request_id: str

    FIELDS = (
        "schema",
        "runtime_id",
        "runtime_version",
        "openclaw_config_digest",
        "agent_id",
        "session_id",
        "tool_name",
        "client_request_id",
    )

    def __post_init__(self) -> None:
        for name in (
            "runtime_id",
            "runtime_version",
            "agent_id",
            "session_id",
            "tool_name",
        ):
            _check_identifier(getattr(self, name), INVALID_DECLARED_CONTEXT)
        _check_digest(self.openclaw_config_digest)
        _check_identifier(self.client_request_id, INVALID_CLIENT_REQUEST_ID)

    def as_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema": SCHEMA_DECLARED_CONTEXT,
            "runtime_id": self.runtime_id,
            "runtime_version": self.runtime_version,
            "openclaw_config_digest": self.openclaw_config_digest,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "client_request_id": self.client_request_id,
        }

    def declared_context_digest(self) -> str:
        """Digest of client-declared context. Tamper-evidence, not authenticity."""
        return _digest_of(self.as_canonical_dict())

    @classmethod
    def from_mapping(cls, mapping: Any) -> "DeclaredInvocationContext":
        fields = _require_exact_fields(mapping, cls.FIELDS, INVALID_DECLARED_CONTEXT)
        if fields["schema"] != SCHEMA_DECLARED_CONTEXT:
            raise MediatedValidationError(INVALID_DECLARED_CONTEXT)
        return cls(
            runtime_id=fields["runtime_id"],
            runtime_version=fields["runtime_version"],
            openclaw_config_digest=fields["openclaw_config_digest"],
            agent_id=fields["agent_id"],
            session_id=fields["session_id"],
            tool_name=fields["tool_name"],
            client_request_id=fields["client_request_id"],
        )


@dataclass(frozen=True)
class AuthorizedContentEffect:
    """One exact single-file content transition.

    The bound claim is content state only: the exact authorized pre-content
    digest became the exact authorized post-content digest. Timestamps, file
    identity, ownership, DACLs, and workspace containment are outside it.
    """

    target_file_id: str
    canonical_relpath: str
    expected_pre_digest: str
    expected_post_digest: str
    content_size_bytes: int
    declared_context_digest: str
    broker_connection_id: str
    client_request_id: str
    operation: str = OPERATION_REPLACE

    FIELDS = (
        "schema",
        "operation",
        "target_file_id",
        "canonical_relpath",
        "expected_pre_digest",
        "expected_post_digest",
        "content_size_bytes",
        "declared_context_digest",
        "broker_connection_id",
        "client_request_id",
    )

    def __post_init__(self) -> None:
        if self.operation != OPERATION_REPLACE:
            raise MediatedValidationError(INVALID_OPERATION)
        _check_target_file_id(self.target_file_id)
        _check_canonical_relpath(self.canonical_relpath)
        _check_digest(self.expected_pre_digest)
        _check_digest(self.expected_post_digest)
        _check_digest(self.declared_context_digest)
        _check_size(self.content_size_bytes, CONTENT_SIZE_EXCEEDED)
        _check_identifier(self.broker_connection_id, INVALID_BROKER_BINDING)
        _check_identifier(self.client_request_id, INVALID_CLIENT_REQUEST_ID)

    def as_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema": SCHEMA_FILE_EFFECT,
            "operation": self.operation,
            "target_file_id": self.target_file_id,
            "canonical_relpath": self.canonical_relpath,
            "expected_pre_digest": self.expected_pre_digest,
            "expected_post_digest": self.expected_post_digest,
            "content_size_bytes": self.content_size_bytes,
            "declared_context_digest": self.declared_context_digest,
            "broker_connection_id": self.broker_connection_id,
            "client_request_id": self.client_request_id,
        }

    def effect_digest(self) -> str:
        """Canonical effect digest; used as ``scope_digest`` by CR-YK-002."""
        return _digest_of(self.as_canonical_dict())

    def persistent_projection(self) -> Dict[str, Any]:
        """Evidence-safe metadata only.

        Never carries ``proposed_bytes`` in whole or in part, prompt text, model
        messages, tool arguments, credentials, or filesystem contents. The raw
        bytes are not reachable from this object at all -- they were dropped
        after verification and were never stored on it.
        """
        return {
            "target_file_id": self.target_file_id,
            "canonical_relpath": self.canonical_relpath,
            "expected_pre_digest": self.expected_pre_digest,
            "expected_post_digest": self.expected_post_digest,
            "content_size_bytes": self.content_size_bytes,
            "client_request_id": self.client_request_id,
            "declared_context_digest": self.declared_context_digest,
            "broker_connection_id": self.broker_connection_id,
            "effect_digest": self.effect_digest(),
        }

    @classmethod
    def from_mapping(cls, mapping: Any) -> "AuthorizedContentEffect":
        fields = _require_exact_fields(mapping, cls.FIELDS, INVALID_OPERATION)
        if fields["schema"] != SCHEMA_FILE_EFFECT:
            raise MediatedValidationError(INVALID_OPERATION)
        return cls(
            operation=fields["operation"],
            target_file_id=fields["target_file_id"],
            canonical_relpath=fields["canonical_relpath"],
            expected_pre_digest=fields["expected_pre_digest"],
            expected_post_digest=fields["expected_post_digest"],
            content_size_bytes=fields["content_size_bytes"],
            declared_context_digest=fields["declared_context_digest"],
            broker_connection_id=fields["broker_connection_id"],
            client_request_id=fields["client_request_id"],
        )


@dataclass(frozen=True)
class MediatedClientRequest:
    """Request identity: every proposal field except the raw bytes.

    ``broker_connection_id`` is included deliberately. Without it, the same
    ``client_request_id`` and ``request_digest`` could recur unchanged after a
    reconnect while the authorized effect had changed, and a reservation store
    would report an idempotent replay for authority issued against a connection
    that no longer exists.
    """

    task_id: str
    client_request_id: str
    broker_connection_id: str
    target_file_id: str
    canonical_relpath: str
    expected_pre_digest: str
    expected_post_digest: str
    content_size_bytes: int
    declared_context_digest: str

    FIELDS = (
        "schema",
        "task_id",
        "client_request_id",
        "broker_connection_id",
        "target_file_id",
        "canonical_relpath",
        "expected_pre_digest",
        "expected_post_digest",
        "content_size_bytes",
        "declared_context_digest",
    )

    def __post_init__(self) -> None:
        _check_identifier(self.task_id, INVALID_CLIENT_REQUEST_ID)
        _check_identifier(self.client_request_id, INVALID_CLIENT_REQUEST_ID)
        _check_identifier(self.broker_connection_id, INVALID_BROKER_BINDING)
        _check_target_file_id(self.target_file_id)
        _check_canonical_relpath(self.canonical_relpath)
        _check_digest(self.expected_pre_digest)
        _check_digest(self.expected_post_digest)
        _check_digest(self.declared_context_digest)
        _check_size(self.content_size_bytes, CONTENT_SIZE_EXCEEDED)

    def as_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema": SCHEMA_CLIENT_REQUEST,
            "task_id": self.task_id,
            "client_request_id": self.client_request_id,
            "broker_connection_id": self.broker_connection_id,
            "target_file_id": self.target_file_id,
            "canonical_relpath": self.canonical_relpath,
            "expected_pre_digest": self.expected_pre_digest,
            "expected_post_digest": self.expected_post_digest,
            "content_size_bytes": self.content_size_bytes,
            "declared_context_digest": self.declared_context_digest,
        }

    def request_digest(self) -> str:
        return _digest_of(self.as_canonical_dict())

    def binding(self) -> "RequestBinding":
        return RequestBinding(
            client_request_id=self.client_request_id,
            request_digest=self.request_digest(),
        )

    @classmethod
    def from_mapping(cls, mapping: Any) -> "MediatedClientRequest":
        fields = _require_exact_fields(mapping, cls.FIELDS, INVALID_CLIENT_REQUEST_ID)
        if fields["schema"] != SCHEMA_CLIENT_REQUEST:
            raise MediatedValidationError(INVALID_CLIENT_REQUEST_ID)
        return cls(
            task_id=fields["task_id"],
            client_request_id=fields["client_request_id"],
            broker_connection_id=fields["broker_connection_id"],
            target_file_id=fields["target_file_id"],
            canonical_relpath=fields["canonical_relpath"],
            expected_pre_digest=fields["expected_pre_digest"],
            expected_post_digest=fields["expected_post_digest"],
            content_size_bytes=fields["content_size_bytes"],
            declared_context_digest=fields["declared_context_digest"],
        )


@dataclass(frozen=True)
class MediatedPlanLinkage:
    """Binds a governed decision to the exact effect, request, and connection.

    Digested as ``plan_body_digest``, so an authorization cannot be transplanted
    onto a different effect, request, or connection while keeping its decision
    identity.
    """

    task_id: str
    decision_id: str
    client_request_id: str
    broker_connection_id: str
    effect_digest: str
    request_digest: str

    FIELDS = (
        "schema",
        "task_id",
        "decision_id",
        "client_request_id",
        "broker_connection_id",
        "effect_digest",
        "request_digest",
    )

    def __post_init__(self) -> None:
        _check_identifier(self.task_id, INVALID_CLIENT_REQUEST_ID)
        _check_identifier(self.decision_id, INVALID_CLIENT_REQUEST_ID)
        _check_identifier(self.client_request_id, INVALID_CLIENT_REQUEST_ID)
        _check_identifier(self.broker_connection_id, INVALID_BROKER_BINDING)
        _check_digest(self.effect_digest)
        _check_digest(self.request_digest)

    def as_canonical_dict(self) -> Dict[str, Any]:
        return {
            "schema": SCHEMA_PLAN_LINKAGE,
            "task_id": self.task_id,
            "decision_id": self.decision_id,
            "client_request_id": self.client_request_id,
            "broker_connection_id": self.broker_connection_id,
            "effect_digest": self.effect_digest,
            "request_digest": self.request_digest,
        }

    def plan_body_digest(self) -> str:
        return _digest_of(self.as_canonical_dict())

    @classmethod
    def from_mapping(cls, mapping: Any) -> "MediatedPlanLinkage":
        fields = _require_exact_fields(mapping, cls.FIELDS, INVALID_CLIENT_REQUEST_ID)
        if fields["schema"] != SCHEMA_PLAN_LINKAGE:
            raise MediatedValidationError(INVALID_CLIENT_REQUEST_ID)
        return cls(
            task_id=fields["task_id"],
            decision_id=fields["decision_id"],
            client_request_id=fields["client_request_id"],
            broker_connection_id=fields["broker_connection_id"],
            effect_digest=fields["effect_digest"],
            request_digest=fields["request_digest"],
        )


# --- Exact-byte content verification ------------------------------------------


def verify_proposed_bytes(
    proposed_bytes: bytes,
    expected_post_digest: str,
    maximum_size_bytes: int,
) -> int:
    """Hash the exact bytes, verify the post-digest, return the exact length.

    The bytes are hashed transiently. They are never embedded in canonical JSON,
    any digest input, a returned object, or the persistent projection -- only
    their length and their digest survive this call.

    Exact-byte treatment is binding. UTF-8 validity is a **gate, not a
    normalization step**: invalid input is rejected and valid input passes
    through untouched. There is no Unicode normalization, no newline conversion,
    no BOM insertion or removal, and the size is measured on the original byte
    sequence rather than any decoded or re-encoded form. Without this, two
    conforming implementations could hash different post-content from identical
    input and both claim compliance.
    """
    if not isinstance(proposed_bytes, (bytes, bytearray)):
        raise MediatedValidationError(CONTENT_NOT_UTF8)
    raw = bytes(proposed_bytes)
    size = len(raw)
    limit = _check_size(maximum_size_bytes, CONTENT_SIZE_EXCEEDED)
    if size > limit:
        raise MediatedValidationError(CONTENT_SIZE_EXCEEDED)
    try:
        raw.decode("utf-8")  # gate only; the decoded text is deliberately unused
    except UnicodeDecodeError:
        raise MediatedValidationError(CONTENT_NOT_UTF8) from None
    expected = _check_digest(expected_post_digest)
    actual = "sha256:" + hashlib.sha256(raw).hexdigest()
    if actual != expected:
        raise MediatedValidationError(POST_DIGEST_MISMATCH)
    return size


# --- Proposal -> effect -------------------------------------------------------


def build_authorized_effect(
    descriptor: MediatedFileDescriptor,
    declared_context: DeclaredInvocationContext,
    *,
    expected_pre_digest: str,
    proposed_bytes: bytes,
    expected_post_digest: str,
    broker_connection_id: str,
    client_request_id: str,
) -> AuthorizedContentEffect:
    """Validate a replacement proposal and build the authorized effect.

    Construction is all-or-nothing: any failure raises and no partially valid
    effect is produced. ``proposed_bytes`` are consumed here and are not
    retained on the returned object.
    """
    if not isinstance(descriptor, MediatedFileDescriptor):
        raise MediatedValidationError(INVALID_TARGET_FILE_ID)
    if not isinstance(declared_context, DeclaredInvocationContext):
        raise MediatedValidationError(INVALID_DECLARED_CONTEXT)
    _check_identifier(client_request_id, INVALID_CLIENT_REQUEST_ID)
    if declared_context.client_request_id != client_request_id:
        raise MediatedValidationError(INVALID_CLIENT_REQUEST_ID)
    _check_digest(expected_pre_digest)
    size = verify_proposed_bytes(
        proposed_bytes, expected_post_digest, descriptor.maximum_size_bytes
    )
    return AuthorizedContentEffect(
        target_file_id=descriptor.target_file_id,
        canonical_relpath=descriptor.canonical_relpath,
        expected_pre_digest=expected_pre_digest,
        expected_post_digest=expected_post_digest,
        content_size_bytes=size,
        declared_context_digest=declared_context.declared_context_digest(),
        broker_connection_id=broker_connection_id,
        client_request_id=client_request_id,
    )


def validate_replacement_proposal(
    descriptor: MediatedFileDescriptor,
    declared_context: DeclaredInvocationContext,
    *,
    expected_pre_digest: str,
    proposed_bytes: bytes,
    expected_post_digest: str,
    broker_connection_id: str,
    client_request_id: str,
) -> str:
    """Non-raising validation returning a closed reason code."""
    try:
        build_authorized_effect(
            descriptor,
            declared_context,
            expected_pre_digest=expected_pre_digest,
            proposed_bytes=proposed_bytes,
            expected_post_digest=expected_post_digest,
            broker_connection_id=broker_connection_id,
            client_request_id=client_request_id,
        )
    except MediatedValidationError as error:
        return error.reason_code
    return VALIDATION_OK


def build_client_request(
    effect: AuthorizedContentEffect,
    *,
    task_id: str,
) -> MediatedClientRequest:
    """Request identity for ``effect``, carrying its connection binding."""
    if not isinstance(effect, AuthorizedContentEffect):
        raise MediatedValidationError(INVALID_OPERATION)
    return MediatedClientRequest(
        task_id=task_id,
        client_request_id=effect.client_request_id,
        broker_connection_id=effect.broker_connection_id,
        target_file_id=effect.target_file_id,
        canonical_relpath=effect.canonical_relpath,
        expected_pre_digest=effect.expected_pre_digest,
        expected_post_digest=effect.expected_post_digest,
        content_size_bytes=effect.content_size_bytes,
        declared_context_digest=effect.declared_context_digest,
    )


def build_plan_linkage(
    effect: AuthorizedContentEffect,
    request: MediatedClientRequest,
    *,
    task_id: str,
    decision_id: str,
) -> MediatedPlanLinkage:
    if not isinstance(effect, AuthorizedContentEffect):
        raise MediatedValidationError(INVALID_OPERATION)
    if not isinstance(request, MediatedClientRequest):
        raise MediatedValidationError(INVALID_CLIENT_REQUEST_ID)
    return MediatedPlanLinkage(
        task_id=task_id,
        decision_id=decision_id,
        client_request_id=effect.client_request_id,
        broker_connection_id=effect.broker_connection_id,
        effect_digest=effect.effect_digest(),
        request_digest=request.request_digest(),
    )


def capability_binding_fields(
    effect: AuthorizedContentEffect,
    linkage: MediatedPlanLinkage,
) -> Dict[str, str]:
    """Map the effect onto the merged CR-YK-002 capability fields.

    Adds no capability schema and changes no CR-YK-002 behavior; this is a
    read-only projection of already-computed digests.
    """
    return {
        "artifact_byte_digest": effect.expected_post_digest,
        "scope_digest": effect.effect_digest(),
        "plan_body_digest": linkage.plan_body_digest(),
    }


# --- Replay classification ----------------------------------------------------


@dataclass(frozen=True)
class RequestBinding:
    """A comparison input, **not** a sixth canonical digest object.

    Never canonicalized, digested, or persisted by this module. The
    "optional values are forbidden, not omitted" rule governs the five canonical
    digest objects; it does not reach here, because absence is a real state the
    caller must be able to express -- through ``None`` for the whole binding,
    never through a null field inside one.
    """

    client_request_id: str
    request_digest: str

    def __post_init__(self) -> None:
        _check_identifier(self.client_request_id, INVALID_CLIENT_REQUEST_ID)
        _check_digest(self.request_digest)


def classify_request_replay(
    existing: Optional[RequestBinding],
    incoming: RequestBinding,
) -> str:
    """Classify a client request against an already-recorded binding.

    Pure: no lookup, no persistence, no I/O. CR-OC-001B supplies the stored
    binding atomically and owns every decision about what to do with the result.
    Nothing here prevents replay; it only classifies what the caller was handed.

    Because ``request_digest`` covers ``broker_connection_id``, a repeat of the
    same client request on a different connection classifies as
    ``request_id_reuse_mismatch`` rather than an idempotent replay.

    A non-null ``existing`` whose ``client_request_id`` differs from ``incoming``
    cannot arise from a correct caller, since CR-OC-001B looks up *by* the
    incoming id. That input raises rather than returning a classification:
    ``new_request`` would let a lookup bug hand back mismatched state and obtain
    fresh authority, and ``request_id_reuse_mismatch`` would report a conflict
    that never happened. Raising surfaces the defect where it can be fixed.
    """
    if not isinstance(incoming, RequestBinding):
        raise MediatedContractError("incoming must be a RequestBinding")
    if existing is None:
        return REPLAY_NEW_REQUEST
    if not isinstance(existing, RequestBinding):
        raise MediatedContractError("existing must be a RequestBinding or None")
    if existing.client_request_id != incoming.client_request_id:
        raise MediatedContractError(
            "existing binding must carry the incoming client_request_id"
        )
    if existing.request_digest == incoming.request_digest:
        return REPLAY_IDEMPOTENT
    return REPLAY_REUSE_MISMATCH
