"""Constrained single-file replacement executor (CR-OC-001C) -- policy core.

Performs at most one constrained single-file content replacement, given an
already constructed CR-OC-001A ``AuthorizedContentEffect``, an independently
supplied exact proposed byte sequence, and a frozen trusted mapping from
``target_file_id`` to one repository target.

This module owns **policy**. Every Win32 structure walk lives in the private
``triage_core.mediated_executor_win32`` adapter, which this module imports
**dynamically and only after the Windows platform gate has passed**. The
dependency is one-way: the adapter imports no TriageCore module, and no
adapter-owned type is used as policy input -- the adapter's capture is
converted here, by ``snapshot_from_capture``, into the core-owned
``SecuritySnapshot``.

What a completed execution may support, and nothing more:

    On Windows with an NTFS workspace, given a frozen trusted registry, an
    already constructed and internally consistent CR-OC-001A effect,
    immutable exact proposed bytes, and **no concurrent writer to the target
    or its ancestor directories**, the executor can select one target
    exclusively through ``target_file_id``, verify the exact authorized
    pre-content, privately prepare the exact authorized replacement bytes,
    issue at most one ``ReplaceFileW`` call with a same-directory backup,
    freshly resolve and verify the observed post-state, and report honestly
    whether no mutation was attempted, the target is documented unchanged,
    replacement may have occurred, or replacement was verified.

**The no-concurrent-writer assumption is load-bearing.** A validation handle
proves facts about the original object only; ``ReplaceFileW`` resolves the
target name independently of any handle this module holds, so the identity
re-probe performed immediately before the call narrows the swap window but
cannot close it. Across that residual interval correctness rests on the
assumption and on nothing else. No wording here may describe the re-probe as
preventing a hostile race.

This module must never be cited for any of:

- OpenClaw containment;
- an authenticated caller, broker, connection, or declared context;
- capability validity, successful claiming, or reservation ownership;
- exactly-once execution across crashes;
- cross-process or hostile-process exclusion;
- indefinite persistence of the postcondition after the verification instant;
- exact preservation of timestamps or file identity;
- transactionality with any SQLite or JSONL store;
- safe mutation of more than one target;
- file creation, deletion, append, patch, rename, directory mutation, or
  command execution as an exposed operation;
- that observing a postcondition proves this invocation caused it.

``target_file_id`` is the sole resolution key. ``canonical_relpath`` is
integrity-bound evidence, compared once for consistency and carried in the
result; it is never used to select, join, resolve, or open anything.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple

from triage_core.mediated_effect import (
    CONTENT_NOT_UTF8,
    CONTENT_SIZE_EXCEEDED,
    POST_DIGEST_MISMATCH,
    AuthorizedContentEffect,
    MediatedValidationError,
    verify_proposed_bytes as _a_verify_proposed_bytes,
)
from triage_core.privacy_invariants import assert_persistent_privacy_safe

# --- Platform profile ---------------------------------------------------------

PLATFORM_PROFILE = "windows"

_WIN32_HELPER_MODULE = "triage_core.mediated_executor_win32"

# --- Closed outcome vocabulary (CR section 13.2) ------------------------------

OUTCOME_NOT_ATTEMPTED = "not_attempted"
OUTCOME_TARGET_UNCHANGED = "target_unchanged"
OUTCOME_MAY_HAVE_OCCURRED = "replacement_may_have_occurred"
OUTCOME_VERIFIED = "replacement_verified"

OUTCOMES = frozenset(
    {
        OUTCOME_NOT_ATTEMPTED,
        OUTCOME_TARGET_UNCHANGED,
        OUTCOME_MAY_HAVE_OCCURRED,
        OUTCOME_VERIFIED,
    }
)

# --- Closed reason vocabulary (CR section 16) ---------------------------------
# Each code is reserved narrowly for the condition it names. A containment
# problem must not surface as a registry problem; an ambiguous replacement must
# never surface as replacement_refused. Conditions this module cannot observe --
# crash detection, reservation or capability lifecycle, broker authenticity,
# ledger conditions -- are deliberately absent, because a code for an
# unobservable condition is a false capability claim in vocabulary form.

REASON_OK = "ok"
REASON_INVALID_EXECUTOR_INPUT = "invalid_executor_input"
REASON_EFFECT_REGISTRY_MISMATCH = "effect_registry_mismatch"
REASON_PLATFORM_UNSUPPORTED = "platform_unsupported"
REASON_TARGET_ID_UNKNOWN = "target_id_unknown"
REASON_TARGET_MISSING = "target_missing"
REASON_CONTAINMENT_VIOLATION = "containment_violation"
REASON_TARGET_NOT_REGULAR_FILE = "target_not_regular_file"
REASON_TARGET_READ_FAILED = "target_read_failed"
REASON_TARGET_OBSERVATION_UNSTABLE = "target_observation_unstable"
REASON_PRE_SIZE_EXCEEDED = "pre_size_exceeded"
REASON_PRE_DIGEST_MISMATCH = "pre_digest_mismatch"
REASON_METADATA_PRECONDITION_FAILED = "metadata_precondition_failed"
REASON_PROPOSED_CONTENT_MISMATCH = "proposed_content_mismatch"
REASON_PROPOSED_SIZE_MISMATCH = "proposed_size_mismatch"
REASON_PROPOSED_SIZE_EXCEEDED = "proposed_size_exceeded"
REASON_TEMP_CREATION_FAILED = "temp_creation_failed"
REASON_TEMP_WRITE_FAILED = "temp_write_failed"
REASON_TEMP_FILE_FAILURE = "temp_file_failure"
REASON_REPLACEMENT_REFUSED = "replacement_refused"
REASON_REPLACEMENT_OUTCOME_UNKNOWN = "replacement_outcome_unknown"
REASON_POST_CONTAINMENT_LOST = "post_containment_lost"
REASON_POST_NOT_REGULAR_FILE = "post_not_regular_file"
REASON_POST_DIGEST_MISMATCH = "post_digest_mismatch"
REASON_POST_SIZE_MISMATCH = "post_size_mismatch"
REASON_POST_VERIFICATION_FAILED = "post_verification_failed"
REASON_METADATA_PRESERVATION_FAILED = "metadata_preservation_failed"

# The reason -> outcome mapping is the single source of truth. Outcomes are
# never chosen independently of the reason, so an implementation cannot report
# a reason under an outcome the contract does not assign it.
REASON_TO_OUTCOME: Mapping[str, str] = {
    REASON_OK: OUTCOME_VERIFIED,
    REASON_INVALID_EXECUTOR_INPUT: OUTCOME_NOT_ATTEMPTED,
    REASON_EFFECT_REGISTRY_MISMATCH: OUTCOME_NOT_ATTEMPTED,
    REASON_PLATFORM_UNSUPPORTED: OUTCOME_NOT_ATTEMPTED,
    REASON_TARGET_ID_UNKNOWN: OUTCOME_NOT_ATTEMPTED,
    REASON_TARGET_MISSING: OUTCOME_NOT_ATTEMPTED,
    REASON_CONTAINMENT_VIOLATION: OUTCOME_NOT_ATTEMPTED,
    REASON_TARGET_NOT_REGULAR_FILE: OUTCOME_NOT_ATTEMPTED,
    REASON_TARGET_READ_FAILED: OUTCOME_NOT_ATTEMPTED,
    REASON_TARGET_OBSERVATION_UNSTABLE: OUTCOME_NOT_ATTEMPTED,
    REASON_PRE_SIZE_EXCEEDED: OUTCOME_NOT_ATTEMPTED,
    REASON_PRE_DIGEST_MISMATCH: OUTCOME_NOT_ATTEMPTED,
    REASON_METADATA_PRECONDITION_FAILED: OUTCOME_NOT_ATTEMPTED,
    REASON_PROPOSED_CONTENT_MISMATCH: OUTCOME_NOT_ATTEMPTED,
    REASON_PROPOSED_SIZE_MISMATCH: OUTCOME_NOT_ATTEMPTED,
    REASON_PROPOSED_SIZE_EXCEEDED: OUTCOME_NOT_ATTEMPTED,
    REASON_TEMP_CREATION_FAILED: OUTCOME_NOT_ATTEMPTED,
    REASON_TEMP_WRITE_FAILED: OUTCOME_NOT_ATTEMPTED,
    REASON_TEMP_FILE_FAILURE: OUTCOME_NOT_ATTEMPTED,
    REASON_REPLACEMENT_REFUSED: OUTCOME_TARGET_UNCHANGED,
    REASON_REPLACEMENT_OUTCOME_UNKNOWN: OUTCOME_MAY_HAVE_OCCURRED,
    REASON_POST_CONTAINMENT_LOST: OUTCOME_MAY_HAVE_OCCURRED,
    REASON_POST_NOT_REGULAR_FILE: OUTCOME_MAY_HAVE_OCCURRED,
    REASON_POST_DIGEST_MISMATCH: OUTCOME_MAY_HAVE_OCCURRED,
    REASON_POST_SIZE_MISMATCH: OUTCOME_MAY_HAVE_OCCURRED,
    REASON_POST_VERIFICATION_FAILED: OUTCOME_MAY_HAVE_OCCURRED,
    REASON_METADATA_PRESERVATION_FAILED: OUTCOME_MAY_HAVE_OCCURRED,
}

REASON_CODES = frozenset(REASON_TO_OUTCOME)

# --- Documented ReplaceFileW special errors (CR section 11.2) -----------------
# Only these three carry a documented post-failure name/backup state. Every
# other failure is ambiguous by construction.

ERROR_UNABLE_TO_REMOVE_REPLACED = 1175
ERROR_UNABLE_TO_MOVE_REPLACEMENT = 1176
ERROR_UNABLE_TO_MOVE_REPLACEMENT_2 = 1177

# --- Private artifact naming (CR section 11.1, 11.3) --------------------------
# The documented prefixes exist so a human can recognise an abandoned artifact.
# The random suffix is what makes the name unpredictable; a later invocation
# never scans for, reports, or deletes these.

TEMP_PREFIX = ".tcx-tmp-"
TEMP_SUFFIX = ".tmp"
BACKUP_PREFIX = ".tcx-bak-"
BACKUP_SUFFIX = ".bak"
_ARTIFACT_RANDOM_BYTES = 16

# --- Grammar and identifier bounds --------------------------------------------

_MAX_RELPATH_LENGTH = 4096
_RESERVED_DEVICE_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)
_DEVICE_OR_VERBATIM_PREFIXES = ("\\\\.\\", "\\\\?\\")
_DACL_STATE_ABSENT = "absent"
_DACL_STATE_NULL = "null"
_DACL_STATE_PRESENT = "present"
DACL_STATES = frozenset({_DACL_STATE_ABSENT, _DACL_STATE_NULL, _DACL_STATE_PRESENT})

# A Windows ACE_HEADER is AceType (1) + AceFlags (1) + AceSize (2).
_ACE_HEADER_SIZE = 4


class MediatedExecutorError(Exception):
    """Base error for the constrained replacement executor."""


class MediatedExecutorContractError(MediatedExecutorError):
    """A trusted-side or caller defect.

    Distinct from a reason code on purpose: a defect in trusted-side
    construction is not a decision about untrusted input and must never enter
    the closed vocabulary, which would misdescribe a bug as an outcome.
    """


# --- Immutable contract types -------------------------------------------------


@dataclass(frozen=True)
class TrustedTargetEntry:
    """One trusted target. Constructed only by the operator-side caller.

    Nothing reaching this type may originate from ``proposed_bytes``, a
    declared context, or any client-supplied field.
    """

    target_file_id: str
    workspace_relpath: str
    maximum_size_bytes: int

    def __post_init__(self) -> None:
        _validate_target_file_id(self.target_file_id)
        _validate_workspace_relpath(self.workspace_relpath)
        if (
            isinstance(self.maximum_size_bytes, bool)
            or not isinstance(self.maximum_size_bytes, int)
            or self.maximum_size_bytes <= 0
        ):
            raise MediatedExecutorContractError(
                "maximum_size_bytes must be a positive integer"
            )


@dataclass(frozen=True)
class MediatedTargetRegistry:
    """A frozen trusted mapping, immutable for its entire lifetime.

    ``workspace_root_final_path`` is captured at construction on Windows and is
    the containment anchor for every later check. On a platform where execution
    is impossible it stays empty; the platform gate refuses execution long
    before the anchor would be consulted, so an unanchored registry can never
    be used to mutate anything.
    """

    workspace_root: str
    workspace_root_final_path: str
    _entries: Mapping[str, TrustedTargetEntry] = field(repr=False)

    def lookup(self, target_file_id: str) -> Optional[TrustedTargetEntry]:
        """Resolve by ``target_file_id`` only. There is no path-based lookup."""
        if not isinstance(target_file_id, str):
            return None
        return self._entries.get(target_file_id)

    def target_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(self._entries))


@dataclass(frozen=True)
class SecuritySnapshot:
    """Core-owned security facts, in core vocabulary.

    Built only by :func:`snapshot_from_capture` from an adapter capture. The
    adapter never constructs this type, and this type never carries a Win32
    structure -- ``aces`` holds complete, already bounds-validated ACE byte
    sequences, so ACL slack space cannot enter any comparison.

    SACL, primary group, and provenance-only control bits deliberately do not
    participate (CR section 10.1).
    """

    owner_sid: bytes
    dacl_state: str
    control_bits: Tuple[bool, bool, bool]
    acl_revision: int
    ace_count: int
    aces: Tuple[bytes, ...]


@dataclass(frozen=True)
class ReplacementResult:
    """Immutable, metadata-only outcome record.

    Carries no proposed content, no previous content, no absolute path, no
    temporary or backup name, and no security-descriptor material. ``outcome``
    is always derived from ``reason_code`` through :data:`REASON_TO_OUTCOME`,
    so an outcome can never be chosen independently of the condition observed.
    """

    outcome: str
    reason_code: str
    target_file_id: str
    canonical_relpath: str
    effect_digest: str
    expected_pre_digest: str
    expected_post_digest: str
    content_size_bytes: int
    observed_pre_digest: str = ""
    observed_post_digest: str = ""
    platform_profile: str = PLATFORM_PROFILE
    backup_retained: bool = False

    def persistent_projection(self) -> Dict[str, Any]:
        """Evidence-safe metadata only, gated before it is handed back.

        The privacy invariant runs over the exact payload intended for
        durable use, not over a later copy of it.
        """
        payload: Dict[str, Any] = {
            "outcome": self.outcome,
            "reason_code": self.reason_code,
            "target_file_id": self.target_file_id,
            "canonical_relpath": self.canonical_relpath,
            "effect_digest": self.effect_digest,
            "expected_pre_digest": self.expected_pre_digest,
            "expected_post_digest": self.expected_post_digest,
            "content_size_bytes": self.content_size_bytes,
            "observed_pre_digest": self.observed_pre_digest,
            "observed_post_digest": self.observed_post_digest,
            "platform_profile": self.platform_profile,
            "backup_retained": self.backup_retained,
        }
        assert_persistent_privacy_safe(
            payload, artifact_name="mediated executor result"
        )
        return payload


# --- Registry construction and validation -------------------------------------


def _validate_target_file_id(value: Any) -> str:
    """Opaque identifier, never a path. A type check, not a safety check."""
    if not isinstance(value, str) or not value or value != value.strip():
        raise MediatedExecutorContractError(
            "target_file_id must be a non-empty stripped string"
        )
    if any(marker in value for marker in ("/", "\\", "..", ":", "~")):
        raise MediatedExecutorContractError("target_file_id must not be path-like")
    return value


def _validate_workspace_relpath(value: Any) -> str:
    """The CR section 6.2 grammar. Platform-neutral string validation only."""
    if not isinstance(value, str) or not value:
        raise MediatedExecutorContractError(
            "workspace_relpath must be a non-empty string"
        )
    if len(value.encode("utf-8", "surrogatepass")) > _MAX_RELPATH_LENGTH:
        raise MediatedExecutorContractError("workspace_relpath is too long")
    if "\\" in value:
        raise MediatedExecutorContractError(
            "workspace_relpath separator must be '/' only"
        )
    if ":" in value:
        raise MediatedExecutorContractError(
            "workspace_relpath must carry no drive designator"
        )
    if value.startswith("/"):
        raise MediatedExecutorContractError("workspace_relpath must not be absolute")
    if value.startswith("//") or any(
        value.startswith(prefix) for prefix in _DEVICE_OR_VERBATIM_PREFIXES
    ):
        raise MediatedExecutorContractError(
            "workspace_relpath must carry no UNC, device, or verbatim prefix"
        )
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise MediatedExecutorContractError(
            "workspace_relpath must carry no control characters"
        )
    for segment in value.split("/"):
        if not segment:
            raise MediatedExecutorContractError(
                "workspace_relpath must carry no empty segment"
            )
        if segment in (".", ".."):
            raise MediatedExecutorContractError(
                "workspace_relpath must carry no '.' or '..' segment"
            )
        if segment.endswith(".") or segment.endswith(" "):
            # Windows silently strips these, which would make two spellings
            # name one file.
            raise MediatedExecutorContractError(
                "workspace_relpath segment must not end in '.' or a space"
            )
        base = segment.split(".", 1)[0].upper()
        if base in _RESERVED_DEVICE_NAMES:
            raise MediatedExecutorContractError(
                "workspace_relpath must not use a reserved device name"
            )
    return value


def _reject_duplicate_ids(entries: Tuple[TrustedTargetEntry, ...]) -> None:
    seen = set()
    for entry in entries:
        if entry.target_file_id in seen:
            raise MediatedExecutorContractError(
                "duplicate target_file_id in trusted registry"
            )
        seen.add(entry.target_file_id)


def build_target_registry(
    workspace_root: str,
    entries: Iterable[TrustedTargetEntry],
) -> MediatedTargetRegistry:
    """Build the frozen trusted registry.

    Validation is pure and runs first, so a malformed descriptor or a duplicate
    identifier is rejected on any platform without touching the filesystem. The
    containment anchor is captured afterwards, and only where execution is
    possible at all.
    """
    if not isinstance(workspace_root, str) or not workspace_root:
        raise MediatedExecutorContractError(
            "workspace_root must be a non-empty string"
        )
    materialised = tuple(entries)
    for entry in materialised:
        if not isinstance(entry, TrustedTargetEntry):
            raise MediatedExecutorContractError(
                "registry entries must be TrustedTargetEntry instances"
            )
    _reject_duplicate_ids(materialised)

    anchor = ""
    if _platform_is_windows():
        win32 = _load_win32_adapter()
        handle = win32.open_anchor(workspace_root)
        try:
            anchor = win32.final_path(handle)
        finally:
            win32.close_handle(handle)

    return MediatedTargetRegistry(
        workspace_root=workspace_root,
        workspace_root_final_path=anchor,
        _entries={entry.target_file_id: entry for entry in materialised},
    )


# --- Pure validation of the effect against the trusted entry ------------------


def _validate_effect_against_entry(
    effect: AuthorizedContentEffect,
    entry: TrustedTargetEntry,
) -> Optional[str]:
    """CR section 7.1 steps 4-5. Returns a reason code, or None when clean."""
    if effect.canonical_relpath != entry.workspace_relpath:
        # Byte-for-byte: no case folding, no separator normalisation. This is
        # an evidence-consistency check, never a resolution channel.
        return REASON_EFFECT_REGISTRY_MISMATCH
    if effect.content_size_bytes > entry.maximum_size_bytes:
        return REASON_PROPOSED_SIZE_EXCEEDED
    return None


def _verify_proposed_bytes(
    effect: AuthorizedContentEffect,
    entry: TrustedTargetEntry,
    proposed_bytes: bytes,
) -> Optional[str]:
    """Independently verify the exact proposed bytes (CR section 15.2).

    A typed effect object is not proof that CR-OC-001A validation ran on these
    bytes, so every check is repeated here. The length check runs before the
    delegated digest/UTF-8 gate so each failure reports the condition that
    actually occurred rather than whichever check happened to run first.
    """
    if len(proposed_bytes) != effect.content_size_bytes:
        return REASON_PROPOSED_SIZE_MISMATCH
    try:
        # Reuses the merged CR-OC-001A helper for the size limit, the UTF-8
        # gate, and the exact-byte post-digest comparison rather than
        # re-deriving them. No normalisation occurs in either module.
        _a_verify_proposed_bytes(
            proposed_bytes,
            effect.expected_post_digest,
            entry.maximum_size_bytes,
        )
    except MediatedValidationError as error:
        if error.reason_code == CONTENT_SIZE_EXCEEDED:
            return REASON_PROPOSED_SIZE_EXCEEDED
        if error.reason_code == CONTENT_NOT_UTF8:
            return REASON_INVALID_EXECUTOR_INPUT
        if error.reason_code == POST_DIGEST_MISMATCH:
            return REASON_PROPOSED_CONTENT_MISMATCH
        raise MediatedExecutorContractError(
            "trusted registry entry carries an unusable size limit"
        ) from None
    return None


# --- Pure ReplaceFileW result classification (CR section 11.2) ----------------


def classify_replace_result(succeeded: bool, last_error: int) -> str:
    """Map a primitive mechanism result to a closed reason code.

    Pure, so the classification table is unit-testable without Windows. The
    two ``target_unchanged`` classifications rest strictly on Microsoft's
    documented name-retention statements for those error codes; every
    undocumented failure stays ambiguous, because the target's condition
    cannot be established.
    """
    if succeeded:
        return REASON_OK
    if last_error == ERROR_UNABLE_TO_REMOVE_REPLACED:
        # Documented: the replaced file could not be deleted, and the replaced
        # and replacement files retain their original file names.
        return REASON_REPLACEMENT_REFUSED
    if last_error == ERROR_UNABLE_TO_MOVE_REPLACEMENT:
        # Documented: with a backup name supplied, the replaced and replacement
        # files retain their original file names.
        return REASON_REPLACEMENT_REFUSED
    if last_error == ERROR_UNABLE_TO_MOVE_REPLACEMENT_2:
        # Documented: the replacement file still exists under its original
        # name and the replaced file exists under the backup name -- the target
        # name may be absent. Nothing may be asserted about the target.
        return REASON_REPLACEMENT_OUTCOME_UNKNOWN
    return REASON_REPLACEMENT_OUTCOME_UNKNOWN


# --- Capture -> snapshot conversion and comparison (CR section 10.1) ----------


def snapshot_from_capture(capture: Any) -> SecuritySnapshot:
    """Convert an adapter capture into core vocabulary.

    This is where mechanism facts stop being mechanism facts. The three-valued
    DACL classification is decided **here**, in the core -- the adapter reports
    ``dacl_present`` and ``dacl_is_null`` and reaches no conclusion.

    Raises ``MediatedExecutorContractError`` on a malformed or internally
    inconsistent capture; the caller converts that into the fail-closed reason
    appropriate to when it was observed.
    """
    try:
        owner_sid = capture.owner_sid
        dacl_present = capture.dacl_present
        dacl_is_null = capture.dacl_is_null
        control_bits = capture.control_bits
        acl_revision = capture.acl_revision
        ace_count = capture.ace_count
        aces = capture.aces
    except AttributeError as error:
        raise MediatedExecutorContractError(
            "security capture is missing a required field"
        ) from None

    if not isinstance(owner_sid, bytes) or not owner_sid:
        raise MediatedExecutorContractError("capture owner_sid must be non-empty bytes")
    if not isinstance(dacl_present, bool) or not isinstance(dacl_is_null, bool):
        raise MediatedExecutorContractError("capture DACL facts must be booleans")
    if (
        not isinstance(control_bits, tuple)
        or len(control_bits) != 3
        or not all(isinstance(bit, bool) for bit in control_bits)
    ):
        raise MediatedExecutorContractError(
            "capture control_bits must be three booleans"
        )
    for name, number in (("acl_revision", acl_revision), ("ace_count", ace_count)):
        if isinstance(number, bool) or not isinstance(number, int) or number < 0:
            raise MediatedExecutorContractError(
                f"capture {name} must be a non-negative integer"
            )
    if not isinstance(aces, tuple) or not all(
        isinstance(ace, bytes) for ace in aces
    ):
        raise MediatedExecutorContractError("capture aces must be a tuple of bytes")

    if dacl_is_null and not dacl_present:
        raise MediatedExecutorContractError(
            "capture cannot report a NULL DACL that is not present"
        )

    if not dacl_present:
        state = _DACL_STATE_ABSENT
    elif dacl_is_null:
        state = _DACL_STATE_NULL
    else:
        state = _DACL_STATE_PRESENT

    if state != _DACL_STATE_PRESENT and (aces or ace_count):
        raise MediatedExecutorContractError(
            "capture reports ACEs without a present non-NULL DACL"
        )
    if state == _DACL_STATE_PRESENT and len(aces) != ace_count:
        raise MediatedExecutorContractError(
            "capture ace_count disagrees with the enumerated ACEs"
        )
    for ace in aces:
        # The adapter bounds-validates while walking; this is the core's own
        # independent floor, so a defective adapter cannot smuggle a truncated
        # ACE into a comparison.
        if len(ace) < _ACE_HEADER_SIZE:
            raise MediatedExecutorContractError("capture carries a truncated ACE")
        declared = int.from_bytes(ace[2:4], "little")
        if declared != len(ace):
            raise MediatedExecutorContractError(
                "capture ACE length disagrees with its AceSize header"
            )

    return SecuritySnapshot(
        owner_sid=owner_sid,
        dacl_state=state,
        control_bits=tuple(control_bits),
        acl_revision=acl_revision,
        ace_count=ace_count,
        aces=tuple(aces),
    )


def compare_security_snapshots(pre: SecuritySnapshot, post: SecuritySnapshot) -> bool:
    """Structural equality of the participating components (CR section 10.1).

    Order: owner SID identity; three-valued DACL state; ``SE_DACL_PRESENT``
    and ``SE_DACL_PROTECTED`` equality; the ``SE_DACL_AUTO_INHERITED``
    monotonic rule; ACL revision and ACE count; then ordered per-index
    equality of the complete ACE byte sequences.

    Complete per-ACE byte comparison is the rule because Windows ACE forms
    carry access-relevant data beyond any small field tuple -- object-ACE
    GUIDs, callback and conditional application data, inheritance fields. An
    unknown ACE type is compared as an opaque complete byte sequence and is
    never partially parsed, partially compared, or skipped. Raw SDDL text is
    not the invariant and never substitutes for this comparison.

    **The ``SE_DACL_AUTO_INHERITED`` monotonic rule (CR section 10.1a).**
    A successful ``ReplaceFileW`` was observed to set that bit on a file whose
    descriptor lacked it, while preserving every access-bearing component
    exactly, so strict equality would fail a correct replacement::

        False -> False    accepted
        False -> True     accepted as Windows normalization
        True  -> True     accepted
        True  -> False    rejected

    The exception applies to that one bit and to nothing else. Every other
    component is compared independently and fails on its own terms, so the
    exception can never mask an owner, state, presence, protection, revision,
    count, ordering, or ACE-byte difference. ``True -> False`` stays a failure
    because it was never observed and is not a documented normalization --
    narrowing the claim rather than widening the exception.
    """
    if not isinstance(pre, SecuritySnapshot) or not isinstance(post, SecuritySnapshot):
        raise MediatedExecutorContractError(
            "security comparison requires two SecuritySnapshot values"
        )
    if pre.owner_sid != post.owner_sid:
        return False
    if pre.dacl_state != post.dacl_state:
        return False
    pre_present, pre_protected, pre_auto_inherited = pre.control_bits
    post_present, post_protected, post_auto_inherited = post.control_bits
    if pre_present != post_present:
        return False
    if pre_protected != post_protected:
        return False
    if pre_auto_inherited and not post_auto_inherited:
        return False
    if pre.dacl_state != _DACL_STATE_PRESENT:
        # Absent and NULL states carry no ACL to compare structurally.
        return True
    if pre.acl_revision != post.acl_revision:
        return False
    if pre.ace_count != post.ace_count:
        return False
    if len(pre.aces) != len(post.aces):
        return False
    for pre_ace, post_ace in zip(pre.aces, post.aces):
        if pre_ace != post_ace:
            return False
    return True


# --- Platform gate ------------------------------------------------------------


def _platform_is_windows() -> bool:
    """Pure platform check. Indirected so a test can force the gate closed."""
    return sys.platform == "win32"


def _load_win32_adapter():
    """Import the Windows adapter dynamically.

    Never imported at module scope: ``ctypes.windll`` does not exist off
    Windows, so a module-scope import would break this module's import safety
    on every non-Windows platform.
    """
    import importlib

    return importlib.import_module(_WIN32_HELPER_MODULE)


# --- Result construction ------------------------------------------------------


def _build_result(
    effect: AuthorizedContentEffect,
    reason_code: str,
    *,
    observed_pre_digest: str = "",
    observed_post_digest: str = "",
    backup_retained: bool = False,
) -> ReplacementResult:
    if reason_code not in REASON_CODES:
        raise MediatedExecutorContractError(f"unknown reason code: {reason_code!r}")
    return ReplacementResult(
        outcome=REASON_TO_OUTCOME[reason_code],
        reason_code=reason_code,
        target_file_id=effect.target_file_id,
        canonical_relpath=effect.canonical_relpath,
        effect_digest=effect.effect_digest(),
        expected_pre_digest=effect.expected_pre_digest,
        expected_post_digest=effect.expected_post_digest,
        content_size_bytes=effect.content_size_bytes,
        observed_pre_digest=observed_pre_digest,
        observed_post_digest=observed_post_digest,
        backup_retained=backup_retained,
    )


def _sha256_digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _artifact_name(prefix: str, suffix: str) -> str:
    """Unpredictable private artifact name with a documented recognisable prefix."""
    return prefix + os.urandom(_ARTIFACT_RANDOM_BYTES).hex() + suffix


# --- Orchestration ------------------------------------------------------------

# Process-local only. This is NOT cross-process exclusion, and nothing in this
# module may be read as providing it (CR section 14).
_EXECUTION_LOCK = threading.Lock()


def execute_replacement(
    registry: MediatedTargetRegistry,
    effect: AuthorizedContentEffect,
    proposed_bytes: bytes,
) -> ReplacementResult:
    """Perform at most one constrained single-file replacement.

    The accepted sixteen-step sequence is preserved exactly. Step 11 issues at
    most one ``ReplaceFileW`` call; there is no retry loop and no code path
    reaches it twice. There is no automatic rollback, no path-based fallback,
    no best-effort ACL parsing, and no cleanup mutation once the state is
    ambiguous.
    """
    with _EXECUTION_LOCK:
        return _execute_locked(registry, effect, proposed_bytes)


def _execute_locked(
    registry: MediatedTargetRegistry,
    effect: AuthorizedContentEffect,
    proposed_bytes: bytes,
) -> ReplacementResult:
    # -- 1 validate immutable inputs ------------------------------------------
    if not isinstance(registry, MediatedTargetRegistry):
        raise MediatedExecutorContractError(
            "registry must be a MediatedTargetRegistry"
        )
    if not isinstance(effect, AuthorizedContentEffect):
        # A typed effect can only be produced by CR-OC-001A's validating
        # constructors, so anything else here is a caller defect.
        raise MediatedExecutorContractError(
            "effect must be an AuthorizedContentEffect"
        )
    if type(proposed_bytes) is not bytes:
        # Strictly built-in bytes. A mutable buffer could change between the
        # digest check and the write, making "the bytes verified are the bytes
        # written" unprovable.
        return _build_result(effect, REASON_INVALID_EXECUTOR_INPUT)
    if effect.expected_pre_digest == effect.expected_post_digest:
        # A scope and API rule, not replay prevention: this executor performs
        # an actual content transition, and equal digests describe none.
        # Duplicate-request authority belongs to CR-OC-001B alone.
        return _build_result(effect, REASON_INVALID_EXECUTOR_INPUT)

    # -- 2 freeze and validate trusted registry --------------------------------
    entry = registry.lookup(effect.target_file_id)
    if entry is None:
        return _build_result(effect, REASON_TARGET_ID_UNKNOWN)
    mismatch = _validate_effect_against_entry(effect, entry)
    if mismatch is not None:
        return _build_result(effect, mismatch)

    # -- 3 verify Windows and NTFS ---------------------------------------------
    if not _platform_is_windows():
        return _build_result(effect, REASON_PLATFORM_UNSUPPORTED)
    win32 = _load_win32_adapter()
    if not win32.windows_support_probe():
        return _build_result(effect, REASON_PLATFORM_UNSUPPORTED)

    return _execute_on_windows(win32, registry, effect, entry, proposed_bytes)


def _execute_on_windows(
    win32: Any,
    registry: MediatedTargetRegistry,
    effect: AuthorizedContentEffect,
    entry: TrustedTargetEntry,
    proposed_bytes: bytes,
) -> ReplacementResult:
    """Steps 3 (NTFS) through 16. Every filesystem action goes through win32."""
    adapter_error = win32.Win32AdapterError
    segments = tuple(entry.workspace_relpath.split("/"))
    anchor = registry.workspace_root_final_path

    # -- 3 (continued) NTFS verification ---------------------------------------
    try:
        anchor_handle = win32.open_anchor(registry.workspace_root)
    except adapter_error:
        return _build_result(effect, REASON_CONTAINMENT_VIOLATION)
    try:
        try:
            if not win32.volume_is_ntfs(anchor_handle):
                return _build_result(effect, REASON_PLATFORM_UNSUPPORTED)
            if not win32.paths_equal(win32.final_path(anchor_handle), anchor):
                # The anchor captured at construction no longer resolves to the
                # same location; containment cannot be established.
                return _build_result(effect, REASON_CONTAINMENT_VIOLATION)
        except adapter_error:
            return _build_result(effect, REASON_CONTAINMENT_VIOLATION)
    finally:
        win32.close_handle(anchor_handle)

    # -- 4 resolve target only from target_file_id -----------------------------
    # Resolution runs exclusively through entry.workspace_relpath under the
    # anchored root. effect.canonical_relpath is never joined or opened.
    # Reparse rejection covers the target AND every ancestor, and happens
    # BEFORE any handle to the target is opened. The two halves are separate
    # calls so each is independently verifiable.
    try:
        if win32.has_reparse_ancestor(anchor, segments):
            return _build_result(effect, REASON_CONTAINMENT_VIOLATION)
    except adapter_error:
        return _build_result(effect, REASON_CONTAINMENT_VIOLATION)

    try:
        if win32.has_reparse_target(anchor, segments):
            return _build_result(effect, REASON_CONTAINMENT_VIOLATION)
    except adapter_error:
        return _build_result(effect, REASON_CONTAINMENT_VIOLATION)

    try:
        target_handle = win32.walk_open_target(anchor, segments)
    except FileNotFoundError:
        # The target must already exist; creation is out of scope and no
        # creating disposition ever reaches the target name.
        return _build_result(effect, REASON_TARGET_MISSING)
    except adapter_error as error:
        if getattr(error, "not_found", False):
            return _build_result(effect, REASON_TARGET_MISSING)
        return _build_result(effect, REASON_CONTAINMENT_VIOLATION)

    pre_snapshot: Optional[SecuritySnapshot] = None
    pre_identity: Optional[Tuple[int, int, int]] = None
    observed_pre_digest = ""
    try:
        # -- 5 validate original object and containment ------------------------
        try:
            if not win32.paths_equal(
                win32.final_path(target_handle),
                win32.expected_final_path(anchor, segments),
            ):
                return _build_result(effect, REASON_CONTAINMENT_VIOLATION)
            if not win32.is_regular_file(target_handle):
                return _build_result(effect, REASON_TARGET_NOT_REGULAR_FILE)
        except adapter_error:
            return _build_result(effect, REASON_CONTAINMENT_VIOLATION)

        # -- 6 capture pre-identity and owner/DACL state -----------------------
        try:
            pre_identity = win32.file_identity(target_handle)
        except adapter_error:
            return _build_result(effect, REASON_TARGET_OBSERVATION_UNSTABLE)
        try:
            pre_capture = win32.capture_security(target_handle)
        except adapter_error:
            return _build_result(effect, REASON_METADATA_PRECONDITION_FAILED)
        try:
            pre_snapshot = snapshot_from_capture(pre_capture)
        except MediatedExecutorContractError:
            # Malformed pre-state metadata fails before any mutation.
            return _build_result(effect, REASON_METADATA_PRECONDITION_FAILED)

        # Pre-mutation ownership gate: ReplaceFileW does not preserve the
        # owner, so an unpreservable case is refused rather than promised.
        # The comparison is against the token's DEFAULT OWNER -- the owner the
        # temporary file about to be created will actually receive -- and not
        # against the token's user account (CR section 10.2a).
        try:
            if pre_snapshot.owner_sid != win32.process_default_owner_sid():
                return _build_result(effect, REASON_METADATA_PRECONDITION_FAILED)
        except adapter_error:
            return _build_result(effect, REASON_METADATA_PRECONDITION_FAILED)

        # -- 7 read and verify exact pre-content -------------------------------
        try:
            size = win32.file_size(target_handle)
        except adapter_error:
            return _build_result(effect, REASON_TARGET_READ_FAILED)
        if size > entry.maximum_size_bytes:
            return _build_result(effect, REASON_PRE_SIZE_EXCEEDED)
        try:
            existing = win32.read_exact_bounded(
                target_handle, entry.maximum_size_bytes + 1
            )
        except adapter_error:
            return _build_result(effect, REASON_TARGET_READ_FAILED)
        if len(existing) > entry.maximum_size_bytes:
            return _build_result(effect, REASON_PRE_SIZE_EXCEEDED)
        if len(existing) != size:
            return _build_result(effect, REASON_TARGET_OBSERVATION_UNSTABLE)
        # Exact bytes: no normalisation of any kind between disk and hash.
        observed_pre_digest = _sha256_digest(existing)
        del existing
        if observed_pre_digest != effect.expected_pre_digest:
            return _build_result(
                effect,
                REASON_PRE_DIGEST_MISMATCH,
                observed_pre_digest=observed_pre_digest,
            )
    finally:
        # The validation handle proves facts about the ORIGINAL object only. It
        # does not bind the target name, and ReplaceFileW resolves that name
        # independently of any handle held here, so holding it open across the
        # call would close no race. It is closed as the contract specifies.
        win32.close_handle(target_handle)

    # -- 8 independently verify exact proposed bytes ---------------------------
    proposed_reason = _verify_proposed_bytes(effect, entry, proposed_bytes)
    if proposed_reason is not None:
        return _build_result(
            effect, proposed_reason, observed_pre_digest=observed_pre_digest
        )

    return _mutate(
        win32,
        effect,
        entry,
        proposed_bytes,
        anchor=anchor,
        segments=segments,
        pre_identity=pre_identity,
        pre_snapshot=pre_snapshot,
        observed_pre_digest=observed_pre_digest,
    )


def _mutate(
    win32: Any,
    effect: AuthorizedContentEffect,
    entry: TrustedTargetEntry,
    proposed_bytes: bytes,
    *,
    anchor: str,
    segments: Tuple[str, ...],
    pre_identity: Tuple[int, int, int],
    pre_snapshot: SecuritySnapshot,
    observed_pre_digest: str,
) -> ReplacementResult:
    """Steps 9 through 16. Reached only after every precondition has passed."""
    adapter_error = win32.Win32AdapterError
    directory = win32.parent_directory(anchor, segments)
    target_path = win32.expected_final_path(anchor, segments)

    def failed(reason: str, *, backup_retained: bool = False) -> ReplacementResult:
        return _build_result(
            effect,
            reason,
            observed_pre_digest=observed_pre_digest,
            backup_retained=backup_retained,
        )

    # -- 9 prepare and verify private temporary file ---------------------------
    temp_name = _artifact_name(TEMP_PREFIX, TEMP_SUFFIX)
    backup_name = _artifact_name(BACKUP_PREFIX, BACKUP_SUFFIX)
    temp_path = win32.child_path(directory, temp_name)
    backup_path = win32.child_path(directory, backup_name)

    try:
        if win32.path_exists(temp_path) or win32.path_exists(backup_path):
            # Collision-checked; never retried with a fresh name in the same
            # invocation. "At most one attempt" includes preparation.
            return failed(REASON_TEMP_CREATION_FAILED)
    except adapter_error:
        return failed(REASON_TEMP_CREATION_FAILED)

    try:
        temp_handle = win32.create_private_temp(temp_path)
    except adapter_error:
        return failed(REASON_TEMP_CREATION_FAILED)

    temp_written = False
    try:
        try:
            win32.write_all(temp_handle, proposed_bytes)
        except adapter_error:
            return failed(REASON_TEMP_WRITE_FAILED)
        try:
            # Flushed to the device before the replacement call.
            win32.flush_and_close(temp_handle)
            temp_handle = None
        except adapter_error:
            return failed(REASON_TEMP_WRITE_FAILED)
        try:
            if win32.file_size_of_path(temp_path) != effect.content_size_bytes:
                return failed(REASON_TEMP_FILE_FAILURE)
        except adapter_error:
            return failed(REASON_TEMP_FILE_FAILURE)
        temp_written = True
    finally:
        if temp_handle is not None:
            try:
                win32.close_handle(temp_handle)
            except adapter_error:
                pass
        if not temp_written:
            # Every pre-replacement failure removes the temporary file. If the
            # removal itself fails the ORIGINAL reason is preserved; the
            # leftover is simply an abandoned artifact.
            try:
                win32.delete_file(temp_path)
            except adapter_error:
                pass

    # -- 10 immediate identity re-probe ----------------------------------------
    # Narrows the window in which a name swap goes unnoticed. It cannot close
    # it: ReplaceFileW resolves the target name itself, after this probe.
    try:
        probe_handle = win32.walk_open_target(anchor, segments)
    except (FileNotFoundError, adapter_error):
        win32.delete_file(temp_path)
        return failed(REASON_TARGET_OBSERVATION_UNSTABLE)
    try:
        try:
            stable = (
                win32.paths_equal(win32.final_path(probe_handle), target_path)
                and win32.file_identity(probe_handle) == pre_identity
            )
        except adapter_error:
            stable = False
    finally:
        win32.close_handle(probe_handle)
    if not stable:
        win32.delete_file(temp_path)
        return failed(REASON_TARGET_OBSERVATION_UNSTABLE)

    # -- 11 issue at most ONE ReplaceFileW call --------------------------------
    try:
        succeeded, last_error = win32.replace_file(
            target_path, temp_path, backup_path
        )
    except adapter_error:
        succeeded, last_error = False, 0

    # -- 12 classify the primitive result --------------------------------------
    classified = classify_replace_result(succeeded, last_error)

    if classified == REASON_REPLACEMENT_REFUSED:
        # Documented: both files retain their original names. Remove our own
        # temporary file. If, contrary to the documented state, a file exists
        # at this invocation's backup name, retain it (safe direction).
        backup_retained = False
        try:
            backup_retained = win32.path_exists(backup_path)
        except adapter_error:
            backup_retained = True
        try:
            win32.delete_file(temp_path)
        except adapter_error:
            pass
        return failed(REASON_REPLACEMENT_REFUSED, backup_retained=backup_retained)

    if classified != REASON_OK:
        # Ambiguous. Perform NO further filesystem operations: any additional
        # mutation in an unknown state can only make the state harder to reason
        # about. Both artifacts are retained for human recovery.
        return failed(REASON_REPLACEMENT_OUTCOME_UNKNOWN, backup_retained=True)

    return _verify_post_state(
        win32,
        effect,
        anchor=anchor,
        segments=segments,
        backup_path=backup_path,
        pre_snapshot=pre_snapshot,
        observed_pre_digest=observed_pre_digest,
    )


def _verify_post_state(
    win32: Any,
    effect: AuthorizedContentEffect,
    *,
    anchor: str,
    segments: Tuple[str, ...],
    backup_path: str,
    pre_snapshot: SecuritySnapshot,
    observed_pre_digest: str,
) -> ReplacementResult:
    """Steps 13 through 16.

    Post-verification uses a **fresh** resolution through the frozen trusted
    registry -- never a cached path, a pre-replacement handle, or a cached
    identity, because the object now at the target name is the replacement
    file's object and legitimately carries a new identity.

    Every failure here is ``replacement_may_have_occurred``: the mutation
    already happened or may have happened, and nothing may claim otherwise.
    The backup is retained in every such state.
    """
    adapter_error = win32.Win32AdapterError

    def ambiguous(reason: str, observed_post: str = "") -> ReplacementResult:
        return _build_result(
            effect,
            reason,
            observed_pre_digest=observed_pre_digest,
            observed_post_digest=observed_post,
            backup_retained=True,
        )

    # -- 13 freshly resolve the post-state through the registry ----------------
    try:
        if win32.has_reparse_ancestor(anchor, segments):
            return ambiguous(REASON_POST_CONTAINMENT_LOST)
    except adapter_error:
        return ambiguous(REASON_POST_CONTAINMENT_LOST)

    try:
        handle = win32.walk_open_target(anchor, segments)
    except (FileNotFoundError, adapter_error):
        return ambiguous(REASON_POST_CONTAINMENT_LOST)

    observed_post_digest = ""
    try:
        # -- 14 verify content, size, type, containment, owner, and DACL -------
        try:
            if not win32.paths_equal(
                win32.final_path(handle),
                win32.expected_final_path(anchor, segments),
            ):
                return ambiguous(REASON_POST_CONTAINMENT_LOST)
        except adapter_error:
            return ambiguous(REASON_POST_CONTAINMENT_LOST)
        try:
            if not win32.is_regular_file(handle):
                return ambiguous(REASON_POST_NOT_REGULAR_FILE)
        except adapter_error:
            return ambiguous(REASON_POST_VERIFICATION_FAILED)
        try:
            observed = win32.read_exact_bounded(handle, effect.content_size_bytes + 1)
        except adapter_error:
            return ambiguous(REASON_POST_VERIFICATION_FAILED)
        if len(observed) != effect.content_size_bytes:
            return ambiguous(REASON_POST_SIZE_MISMATCH)
        observed_post_digest = _sha256_digest(observed)
        del observed
        if observed_post_digest != effect.expected_post_digest:
            return ambiguous(REASON_POST_DIGEST_MISMATCH, observed_post_digest)
        try:
            post_capture = win32.capture_security(handle)
            post_snapshot = snapshot_from_capture(post_capture)
        except (adapter_error, MediatedExecutorContractError):
            # Malformed or non-comparable post-state metadata is ambiguous, not
            # a pre-mutation failure.
            return ambiguous(REASON_METADATA_PRESERVATION_FAILED, observed_post_digest)
        if not compare_security_snapshots(pre_snapshot, post_snapshot):
            return ambiguous(REASON_METADATA_PRESERVATION_FAILED, observed_post_digest)
    finally:
        win32.close_handle(handle)

    # -- 15 delete backup ONLY after complete verified success -----------------
    backup_retained = False
    try:
        win32.delete_file(backup_path)
    except adapter_error:
        # A hygiene fact, never a downgrade of the verified outcome. The backup
        # holds the authorized previous content, which was already on disk.
        backup_retained = True

    # -- 16 produce the privacy-safe result ------------------------------------
    # This asserts the conjunction of "the single primitive call succeeded" and
    # "the postcondition was observed afterwards". It does NOT assert that the
    # observation alone proves this invocation caused the state.
    return _build_result(
        effect,
        REASON_OK,
        observed_pre_digest=observed_pre_digest,
        observed_post_digest=observed_post_digest,
        backup_retained=backup_retained,
    )
