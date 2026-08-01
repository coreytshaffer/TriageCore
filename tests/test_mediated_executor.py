"""Tests for the CR-OC-001C constrained single-file replacement executor.

Covers the 36 accepted test obligations. Venue tags follow the contract:

- ``[N]`` platform-neutral, runs everywhere including Ubuntu CI, against the
  pure core;
- ``[W]`` requires real Windows/NTFS; marked ``windows`` and skipped
  elsewhere. **A skip on Windows is a failure** -- the CI job asserts a zero
  skip count for the mandatory group, because a broken platform gate must
  turn red rather than silently green;
- the supplemental symbolic-link probe carries ``windows_optional``, sits
  outside the 36 obligations and outside the zero-skip calculation, and is
  never acceptance evidence.

Windows obligations run against real files on a real NTFS volume. A closed,
enumerated set of injection seams covers only the branches Windows will not
produce on demand (a chosen ``ReplaceFileW`` error code, a post-verification
divergence, a foreign owner, a forced probe failure, a malformed capture);
those are labelled ``seam-injected`` in their docstrings and are classifier
evidence, not genuine-filesystem evidence.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import subprocess
import sys
import threading
import uuid

import pytest

from triage_core.mediated_effect import (
    DeclaredInvocationContext,
    MediatedFileDescriptor,
    build_authorized_effect,
)
from triage_core.privacy_invariants import assert_persistent_privacy_safe

import triage_core.mediated_executor as executor
from triage_core.mediated_executor import (
    OUTCOME_MAY_HAVE_OCCURRED,
    OUTCOME_NOT_ATTEMPTED,
    OUTCOME_TARGET_UNCHANGED,
    OUTCOME_VERIFIED,
    REASON_CODES,
    REASON_TO_OUTCOME,
    MediatedExecutorContractError,
    ReplacementResult,
    SecuritySnapshot,
    TrustedTargetEntry,
    build_target_registry,
    classify_replace_result,
    compare_security_snapshots,
    execute_replacement,
    snapshot_from_capture,
)

WINDOWS = sys.platform == "win32"
windows_only = pytest.mark.skipif(not WINDOWS, reason="Windows/NTFS obligation")

# --- Obligation ledger (CR sections 19 and 25.5) ------------------------------
# Every contractual obligation maps to at least one designated test here. Test
# names carry their obligation number as ``test_t<NN>...``; the ``n``/``w``
# suffix marks which venue half a test satisfies. OBLIGATIONS below is checked
# against the file itself by test_ledger_every_obligation_has_a_test, so this
# table cannot drift away from the suite.
#
#  T   venue  designated coverage
#  --  -----  ------------------------------------------------------------
#   1  W      only target_file_id selects the target
#   2  W      canonical_relpath cannot redirect execution
#   3  U+W    duplicate ids raise (U); unknown id fails closed (W)
#   4  U      no path parameter; relpath grammar; path-like id rejection
#   5  W      anchor no longer resolving to the captured root
#   6  W      junction as the target (genuine reparse point)
#   7  W      junction ancestor redirecting outside
#   8  W      directory target
#   9  W      missing target, nothing created
#  10  W      pre-digest mismatch
#  11  W      proposed-content mismatch
#  12  W      proposed size mismatch
#  13  W      oversized existing and oversized proposed content
#  14  W      exact bytes across CRLF, BOM, and normal form
#  15  W      artifact exclusivity, collision check, unpredictability
#  16  W      partial temp write never alters the target
#  17  W      flush precedes the single replacement call
#  18  W      temp and backup in the target directory (same volume)
#  19  W      verified success writes exact bytes; backup deleted
#  20  W      owner gate refuses a foreign principal; control for the real one
#  21  U+W    complete ordered ACE comparison (U); real DACL and injected (W)
#  22  W      post-replacement non-regular file
#  23  W      post containment loss (ancestor and final-path observations)
#  24  W      post divergence is ambiguous, one replacement, no restore
#  25  U+W    pure 1175/1176/1177 classifier (U); injected end-to-end (W)
#  26  U+W    degenerate pre==post rejected (U); real sharing conflict (W)
#  27  U      cross-process exclusion excluded, not claimed
#  28  U+W    projection shape (U); real-run canary payload (W)
#  29  W      failures expose no content or absolute paths
#  30  U+W    no network/subprocess/IPC/database/ledger access
#  31  U      import boundary; helper imports no TriageCore module
#  32  U+W    non-Windows gate (U); forced API-probe failure (W)
#  33  W      backup lifecycle: deleted on success, retained otherwise
#  34  W      identity re-probe catches a genuinely swapped target
#  35  U+W    SE_DACL_AUTO_INHERITED monotonic rule (U); NTFS observation (W)
#  36  U      monotonic rule rejects True -> False
#
# The supplemental symlink probe carries ``windows_optional``, is NOT an
# obligation, and is excluded from the mandatory run and the zero-skip count.
OBLIGATIONS = frozenset(range(1, 37))

CONFIG_DIGEST = "sha256:" + "2b" * 32
CANARY = b"CANARY-SENTINEL-e6f1a2b3 confidential payload\n"


def digest_of(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


# --- Builders -----------------------------------------------------------------


def make_effect(
    *,
    relpath="docs/notes.md",
    pre=b"original\n",
    post=b"replacement\n",
    target_id="f-target",
    maximum_size_bytes=4096,
    pre_digest=None,
    post_digest=None,
    content_size_bytes=None,
):
    """Build a CR-OC-001A effect. ``post`` is the proposed byte sequence."""
    descriptor = MediatedFileDescriptor(
        target_file_id=target_id,
        canonical_relpath=relpath,
        maximum_size_bytes=maximum_size_bytes,
    )
    context = DeclaredInvocationContext(
        runtime_id="openclaw",
        runtime_version="1.4.2",
        openclaw_config_digest=CONFIG_DIGEST,
        agent_id="agent-a",
        session_id="session-b",
        tool_name="propose_replacement",
        client_request_id="req-executor",
    )
    effect = build_authorized_effect(
        descriptor,
        context,
        expected_pre_digest=pre_digest or digest_of(pre),
        proposed_bytes=post,
        expected_post_digest=post_digest or digest_of(post),
        broker_connection_id="conn-executor",
        client_request_id="req-executor",
    )
    if content_size_bytes is not None:
        # Rebuild through the canonical mapping so the object stays valid while
        # carrying a deliberately wrong size.
        payload = dict(effect.as_canonical_dict())
        payload["content_size_bytes"] = content_size_bytes
        effect = type(effect).from_mapping(payload)
    return effect


def entry(target_id="f-target", relpath="docs/notes.md", maximum_size_bytes=4096):
    return TrustedTargetEntry(target_id, relpath, maximum_size_bytes)


def workspace(tmp_path, *, relpath="docs/notes.md", content=b"original\n"):
    """Create a workspace root with one target file, return (root, target)."""
    root = tmp_path / "ws"
    target = root / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return str(root), target


def registry_for(root, entries=None):
    return build_target_registry(root, entries or [entry()])


def snapshot(
    *,
    owner=b"S-1-5-21-1-2-3-1001",
    state="present",
    present=True,
    protected=False,
    auto_inherited=False,
    revision=2,
    aces=(b"\x00\x10\x14\x00" + b"\xaa" * 16,),
):
    """Directly constructed core snapshot. No Windows involved."""
    return SecuritySnapshot(
        owner_sid=owner,
        dacl_state=state,
        control_bits=(present, protected, auto_inherited),
        acl_revision=revision,
        ace_count=len(aces),
        aces=tuple(aces),
    )


def ace(size=20, ace_type=0, flags=0x10, body=None):
    """A complete ACE byte sequence whose AceSize header matches its length."""
    payload = body if body is not None else b"\xaa" * (size - 4)
    return bytes([ace_type, flags]) + size.to_bytes(2, "little") + payload


class Capture:
    """Stand-in for the adapter capture. Mirrors its field names only."""

    def __init__(
        self,
        owner_sid=b"S-1-5-21-1-2-3-1001",
        dacl_present=True,
        dacl_is_null=False,
        control_bits=(True, False, False),
        acl_revision=2,
        ace_count=1,
        aces=None,
    ):
        self.owner_sid = owner_sid
        self.dacl_present = dacl_present
        self.dacl_is_null = dacl_is_null
        self.control_bits = control_bits
        self.acl_revision = acl_revision
        self.aces = (ace(),) if aces is None else aces
        self.ace_count = len(self.aces) if aces is not None else ace_count


# =============================================================================
# Obligation 4 [N] -- caller paths cannot enter the API; relpath grammar
# =============================================================================


def test_ledger_every_obligation_has_a_designated_test():
    """The ledger is machine-checked against this file, so 36 obligations
    cannot silently become 30 as tests are renamed or removed."""
    import re

    with open(os.path.abspath(__file__), "r", encoding="utf-8") as handle:
        source = handle.read()
    covered = {int(m) for m in re.findall(r"^def test_t(\d{2})", source, re.M)}
    missing = sorted(OBLIGATIONS - covered)
    assert not missing, "obligations with no designated test: {0}".format(missing)
    stray = sorted(covered - OBLIGATIONS)
    assert not stray, "tests naming an obligation outside 1-36: {0}".format(stray)


def test_ledger_optional_probe_is_not_an_obligation():
    """The supplemental symlink probe must not be numbered as an obligation."""
    import re

    with open(os.path.abspath(__file__), "r", encoding="utf-8") as handle:
        source = handle.read()
    optional = re.findall(r"^def (test_optional_\w+)", source, re.M)
    assert optional, "the supplemental probe must exist"
    for name in optional:
        assert not re.match(r"test_optional_t\d", name), name


def test_t04_entry_point_accepts_no_path_parameter():
    """The API structurally cannot receive a caller-supplied target path."""
    import inspect

    parameters = list(
        inspect.signature(execute_replacement).parameters
    )
    assert parameters == ["registry", "effect", "proposed_bytes"]


@pytest.mark.parametrize(
    "relpath",
    [
        "/absolute",
        "C:/drive",
        "docs\\notes.md",
        "//unc/share",
        "\\\\?\\verbatim",
        "docs/../escape",
        "docs/./here",
        "docs//empty",
        "docs/trailing.",
        "docs/trailing ",
        "CON",
        "docs/NUL.txt",
        "docs/com1",
        "docs/bad\x00nul",
        "docs/bad\x01ctrl",
        "",
    ],
)
def test_t04_relpath_grammar_rejects_unsafe_shapes(relpath):
    with pytest.raises(MediatedExecutorContractError):
        TrustedTargetEntry("f-x", relpath, 4096)


@pytest.mark.parametrize("path_like", ["a/b", "a\\b", "..", "C:x", "~/home"])
def test_t04_target_file_id_cannot_be_path_like(path_like):
    with pytest.raises(MediatedExecutorContractError):
        TrustedTargetEntry(path_like, "docs/notes.md", 4096)


def test_t04_maximum_size_must_be_positive_integer():
    for bad in (0, -1, True, "4096", 4096.0):
        with pytest.raises(MediatedExecutorContractError):
            TrustedTargetEntry("f-x", "docs/notes.md", bad)


# =============================================================================
# Obligation 3 [N half] -- duplicate ids raise at construction
# =============================================================================


def test_t03_duplicate_target_ids_raise_at_registry_construction():
    with pytest.raises(MediatedExecutorContractError):
        build_target_registry(
            "ws", [entry("f-dup", "a/one.md"), entry("f-dup", "b/two.md")]
        )


def test_t03_registry_construction_is_pure_and_rejects_non_entries():
    with pytest.raises(MediatedExecutorContractError):
        build_target_registry("ws", [{"target_file_id": "f-x"}])
    with pytest.raises(MediatedExecutorContractError):
        build_target_registry("", [entry()])


def test_t03_registry_lookup_is_by_id_only_and_has_no_path_lookup():
    registry = _neutral_registry()
    assert registry.lookup("f-target") is not None
    assert registry.lookup("docs/notes.md") is None
    assert registry.lookup(None) is None
    assert not hasattr(registry, "lookup_by_path")


# =============================================================================
# Obligation 25 [N half] -- pure ReplaceFileW result classification
# =============================================================================


def test_t25_success_classifies_ok():
    assert classify_replace_result(True, 0) == "ok"


def test_t25_error_1175_classifies_as_refused():
    """ERROR_UNABLE_TO_REMOVE_REPLACED. Asserted as its own distinct case so
    flattening it into the ambiguous 1177 outcome fails here (kills M27)."""
    assert classify_replace_result(False, 1175) == "replacement_refused"
    assert REASON_TO_OUTCOME["replacement_refused"] == OUTCOME_TARGET_UNCHANGED


def test_t25_error_1176_classifies_as_refused():
    assert classify_replace_result(False, 1176) == "replacement_refused"


def test_t25_error_1177_classifies_as_ambiguous():
    """Documented state can leave the target name absent."""
    assert classify_replace_result(False, 1177) == "replacement_outcome_unknown"
    assert (
        REASON_TO_OUTCOME["replacement_outcome_unknown"] == OUTCOME_MAY_HAVE_OCCURRED
    )


@pytest.mark.parametrize("code", [0, 1, 5, 32, 87, 1178, 999999])
def test_t25_undocumented_errors_are_ambiguous_never_unchanged(code):
    assert classify_replace_result(False, code) == "replacement_outcome_unknown"


# =============================================================================
# Obligation 35 [N] -- SE_DACL_AUTO_INHERITED monotonic rule, deterministic
# =============================================================================


@pytest.mark.parametrize(
    "pre_bit, post_bit",
    [(False, False), (False, True), (True, True)],
)
def test_t35n_accepted_auto_inherited_transitions(pre_bit, post_bit):
    """Directly constructed snapshots. All three accepted transitions pass."""
    pre = snapshot(auto_inherited=pre_bit)
    post = snapshot(auto_inherited=post_bit)
    assert compare_security_snapshots(pre, post) is True


@pytest.mark.parametrize(
    "field, post_kwargs",
    [
        ("owner", {"owner": b"S-1-5-21-9-9-9-1002"}),
        ("dacl_state", {"state": "null", "aces": (), "revision": 0}),
        ("present_bit", {"present": False}),
        ("protected_bit", {"protected": True}),
        ("acl_revision", {"revision": 4}),
        ("ace_count", {"aces": (ace(), ace(size=24))}),
        ("ace_bytes", {"aces": (ace(body=b"\xbb" * 16),)}),
    ],
)
def test_t35n_false_to_true_never_excuses_another_difference(field, post_kwargs):
    """The exception is gated per component: it must not widen to anything."""
    pre = snapshot(auto_inherited=False)
    post = snapshot(auto_inherited=True, **post_kwargs)
    assert compare_security_snapshots(pre, post) is False, field


def test_t35n_false_to_true_never_excuses_ace_reordering():
    first, second = ace(body=b"\x01" * 16), ace(body=b"\x02" * 16)
    pre = snapshot(auto_inherited=False, aces=(first, second))
    post = snapshot(auto_inherited=True, aces=(second, first))
    assert compare_security_snapshots(pre, post) is False


def test_t35n_identical_snapshots_compare_equal():
    """Control: passes under several mutants, counted as a control only."""
    assert compare_security_snapshots(snapshot(), snapshot()) is True


# =============================================================================
# Obligation 36 [N] -- monotonic rule rejects True -> False
# =============================================================================


def test_t36_true_to_false_is_rejected():
    pre = snapshot(auto_inherited=True)
    post = snapshot(auto_inherited=False)
    assert compare_security_snapshots(pre, post) is False


def test_t36_true_to_false_rejected_even_when_all_else_identical():
    """Everything else byte-identical; only the bit clears. Still a failure."""
    shared = ace(body=b"\x77" * 16)
    pre = snapshot(auto_inherited=True, aces=(shared,))
    post = snapshot(auto_inherited=False, aces=(shared,))
    assert pre.owner_sid == post.owner_sid
    assert pre.aces == post.aces
    assert compare_security_snapshots(pre, post) is False


# =============================================================================
# Obligation 21 [N half] -- complete ordered ACE comparison
# =============================================================================


def test_t21n_object_ace_guid_difference_is_detected():
    """A four-field tuple would ignore the GUID region; whole bytes cannot."""
    guid_a = bytes([0x05, 0x10, 0x2C, 0x00]) + b"\x00" * 8 + b"\x11" * 16 + b"\x99" * 16
    guid_b = bytes([0x05, 0x10, 0x2C, 0x00]) + b"\x00" * 8 + b"\x22" * 16 + b"\x99" * 16
    assert len(guid_a) == len(guid_b) == 0x2C
    assert compare_security_snapshots(
        snapshot(aces=(guid_a,)), snapshot(aces=(guid_b,))
    ) is False


def test_t21n_callback_application_data_difference_is_detected():
    body_a = b"\x00" * 12 + b"conditional-A"
    body_b = b"\x00" * 12 + b"conditional-B"
    size = 4 + len(body_a)
    left = bytes([0x09, 0x00]) + size.to_bytes(2, "little") + body_a
    right = bytes([0x09, 0x00]) + size.to_bytes(2, "little") + body_b
    assert compare_security_snapshots(
        snapshot(aces=(left,)), snapshot(aces=(right,))
    ) is False


def test_t21n_ace_flags_only_difference_is_detected():
    assert compare_security_snapshots(
        snapshot(aces=(ace(flags=0x10),)), snapshot(aces=(ace(flags=0x12),))
    ) is False


def test_t21n_unknown_ace_type_compared_as_opaque_whole():
    unknown_left = ace(ace_type=0xFE, body=b"\x33" * 16)
    unknown_right = ace(ace_type=0xFE, body=b"\x33" * 16)
    unknown_other = ace(ace_type=0xFE, body=b"\x34" * 16)
    assert compare_security_snapshots(
        snapshot(aces=(unknown_left,)), snapshot(aces=(unknown_right,))
    ) is True
    assert compare_security_snapshots(
        snapshot(aces=(unknown_left,)), snapshot(aces=(unknown_other,))
    ) is False


def test_t21n_absent_and_null_dacl_states_are_distinct():
    absent = snapshot(state="absent", present=False, aces=(), revision=0)
    null = snapshot(state="null", present=True, aces=(), revision=0)
    present_empty = snapshot(state="present", aces=(), revision=2)
    assert compare_security_snapshots(absent, null) is False
    assert compare_security_snapshots(null, present_empty) is False
    assert compare_security_snapshots(absent, present_empty) is False
    assert compare_security_snapshots(absent, absent) is True


def test_t21n_comparison_requires_snapshots():
    with pytest.raises(MediatedExecutorContractError):
        compare_security_snapshots(snapshot(), Capture())


# --- snapshot_from_capture: conversion, classification, malformed input ------


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({"dacl_present": False, "dacl_is_null": False, "aces": (), "acl_revision": 0},
         "absent"),
        ({"dacl_present": True, "dacl_is_null": True, "aces": (), "acl_revision": 0},
         "null"),
        ({"dacl_present": True, "dacl_is_null": False}, "present"),
    ],
)
def test_t21n_three_valued_classification_is_decided_by_the_core(kwargs, expected):
    """The adapter reports two booleans; the core decides the vocabulary."""
    assert snapshot_from_capture(Capture(**kwargs)).dacl_state == expected


def test_t21n_present_with_zero_aces_is_present_not_null():
    converted = snapshot_from_capture(Capture(aces=()))
    assert converted.dacl_state == "present"
    assert converted.ace_count == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"owner_sid": ""},
        {"owner_sid": b""},
        {"dacl_present": False, "dacl_is_null": True},
        {"control_bits": (True, False)},
        {"control_bits": (1, 0, 0)},
        {"acl_revision": -1},
        {"acl_revision": True},
        {"aces": [ace()]},
        {"dacl_present": False, "dacl_is_null": False, "aces": (ace(),)},
    ],
)
def test_t21n_malformed_capture_raises_rather_than_being_compared(kwargs):
    with pytest.raises(MediatedExecutorContractError):
        snapshot_from_capture(Capture(**kwargs))


@pytest.mark.parametrize(
    "bad_ace",
    [
        b"",
        b"\x00\x10",
        b"\x00\x10\x00\x00",
        b"\x00\x10\xff\x00" + b"\xaa" * 4,
        b"\x00\x10\x08\x00" + b"\xaa" * 16,
    ],
)
def test_t21n_malformed_ace_size_fails_closed(bad_ace):
    """Zero, truncated, or self-inconsistent AceSize is never compared."""
    with pytest.raises(MediatedExecutorContractError):
        snapshot_from_capture(Capture(aces=(bad_ace,)))


def test_t21n_capture_missing_a_field_raises():
    class Partial:
        owner_sid = b"S-1-5-21-1-2-3-1001"

    with pytest.raises(MediatedExecutorContractError):
        snapshot_from_capture(Partial())


def test_t21n_slack_space_cannot_enter_the_decision():
    """The snapshot carries only enumerated ACEs, so buffer slack is absent."""
    converted = snapshot_from_capture(Capture(aces=(ace(),)))
    assert converted.aces == (ace(),)
    assert not hasattr(converted, "acl_bytes_free")
    assert not hasattr(converted, "acl_size")


# =============================================================================
# Obligation 26 [N half] -- degenerate pre == post rejected
# =============================================================================


def test_t26n_equal_pre_and_post_digests_are_rejected_without_opening_a_file(
    tmp_path, monkeypatch
):
    """A scope and API rule, not replay prevention (CR section 7.1 step 6)."""
    same = b"unchanged\n"
    effect = make_effect(pre=same, post=same)
    assert effect.expected_pre_digest == effect.expected_post_digest

    opened = []
    real_open = os.open
    monkeypatch.setattr(os, "open", lambda *a, **k: opened.append(a) or real_open(*a, **k))

    registry = _neutral_registry()
    result = execute_replacement(registry, effect, same)
    assert result.reason_code == "invalid_executor_input"
    assert result.outcome == OUTCOME_NOT_ATTEMPTED
    assert opened == []


def _neutral_registry():
    """A registry usable in neutral tests, anchored only where possible."""
    if WINDOWS:
        return build_target_registry(os.environ.get("TEMP", "."), [entry()])
    return build_target_registry("ws", [entry()])


# =============================================================================
# Obligation 32 [N] -- unsupported platform fails closed, zero opens
# =============================================================================


def test_t32_non_windows_platform_fails_closed_before_any_open(monkeypatch):
    monkeypatch.setattr(executor, "_platform_is_windows", lambda: False)
    opened = []
    real_open = os.open
    monkeypatch.setattr(os, "open", lambda *a, **k: opened.append(a) or real_open(*a, **k))

    result = execute_replacement(_neutral_registry(), make_effect(), b"replacement\n")

    assert result.reason_code == "platform_unsupported"
    assert result.outcome == OUTCOME_NOT_ATTEMPTED
    assert opened == []


@windows_only
@pytest.mark.windows
def test_t32_forced_api_probe_failure_fails_closed(monkeypatch, tmp_path):
    """Seam-injected: a required Win32 entry point reported unavailable."""
    import triage_core.mediated_executor_win32 as win32

    root, _ = workspace(tmp_path)
    registry = registry_for(root)
    monkeypatch.setattr(win32, "windows_support_probe", lambda: False)

    result = execute_replacement(registry, make_effect(), b"replacement\n")
    assert result.reason_code == "platform_unsupported"


# =============================================================================
# Obligation 28 [N half] / 17 -- privacy-safe projection
# =============================================================================


def _result(**kwargs):
    base = dict(
        outcome=OUTCOME_VERIFIED,
        reason_code="ok",
        target_file_id="f-target",
        canonical_relpath="docs/notes.md",
        effect_digest=digest_of(b"effect"),
        expected_pre_digest=digest_of(b"pre"),
        expected_post_digest=digest_of(b"post"),
        content_size_bytes=12,
    )
    base.update(kwargs)
    return ReplacementResult(**base)


def test_t28n_projection_key_set_is_exactly_the_contract_fields():
    assert set(_result().persistent_projection()) == {
        "outcome",
        "reason_code",
        "target_file_id",
        "canonical_relpath",
        "effect_digest",
        "expected_pre_digest",
        "expected_post_digest",
        "content_size_bytes",
        "observed_pre_digest",
        "observed_post_digest",
        "platform_profile",
        "backup_retained",
    }


def test_t28n_projection_passes_the_persistent_privacy_invariant():
    assert_persistent_privacy_safe(
        _result().persistent_projection(), artifact_name="executor result"
    )


def test_t28n_projection_carries_no_bytes_and_no_path_material():
    projection = _result().persistent_projection()
    for key, value in projection.items():
        assert not isinstance(value, (bytes, bytearray)), key
    serialized = json.dumps(projection)
    for forbidden in ("CANARY", ".tcx-tmp-", ".tcx-bak-", "S-1-5-", "C:\\", "\\\\?\\"):
        assert forbidden not in serialized


def test_t28n_result_is_immutable():
    result = _result()
    with pytest.raises(Exception):
        result.reason_code = "ok"


def test_t28n_outcome_is_always_derived_from_the_reason_code():
    """No code path may choose an outcome independently of the condition."""
    for reason, outcome in REASON_TO_OUTCOME.items():
        built = executor._build_result(make_effect(), reason)
        assert built.outcome == outcome
        assert built.reason_code == reason


def test_t28n_unknown_reason_code_raises():
    with pytest.raises(MediatedExecutorContractError):
        executor._build_result(make_effect(), "not_a_reason")


def test_t28n_vocabularies_are_closed_and_consistent():
    assert set(REASON_TO_OUTCOME) == set(REASON_CODES)
    assert set(REASON_TO_OUTCOME.values()) <= {
        OUTCOME_NOT_ATTEMPTED,
        OUTCOME_TARGET_UNCHANGED,
        OUTCOME_MAY_HAVE_OCCURRED,
        OUTCOME_VERIFIED,
    }
    assert len(REASON_CODES) == 27


# =============================================================================
# Obligation 27 [N] -- cross-process exclusion is excluded, not claimed
# =============================================================================


def test_t27_no_cross_process_locking_api_and_no_such_claim():
    """Weak structural control in the style of CR-OC-001A's M9; reviewers are
    the real control."""
    public = [name for name in dir(executor) if not name.startswith("_")]
    for name in public:
        lowered = name.lower()
        assert "cross_process" not in lowered
        assert "file_lock" not in lowered
        assert "flock" not in lowered
    assert not hasattr(executor, "acquire_cross_process_lock")

    # Mentioning cross-process exclusion is *required* -- the contract demands
    # it be denied, and the denial necessarily contains the phrase. What must
    # not exist is an affirmative claim.
    with open(os.path.join(PRODUCTION, "mediated_executor.py"), "r", encoding="utf-8") as handle:
        source = handle.read()
    lowered = source.lower()

    # The denials must be present.
    assert "cross-process or hostile-process exclusion" in lowered
    assert "not cross-process exclusion" in lowered

    # No affirmative claim in any phrasing.
    for affirmative in (
        "provides cross-process",
        "guarantees cross-process",
        "cross-process safe",
        "safe across processes",
        "cross-process exclusion is provided",
        "prevents concurrent processes",
    ):
        assert affirmative not in lowered, affirmative

    assert isinstance(executor._EXECUTION_LOCK, type(threading.Lock()))


# =============================================================================
# Obligation 31 [N] -- import boundary and integration absence
# =============================================================================


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTION = os.path.join(REPO_ROOT, "triage_core")


def test_t31_no_runtime_module_imports_either_executor_module():
    offenders = []
    for name in sorted(os.listdir(PRODUCTION)):
        if not name.endswith(".py") or name.startswith("mediated_executor"):
            continue
        with open(os.path.join(PRODUCTION, name), "r", encoding="utf-8") as handle:
            source = handle.read()
        if "mediated_executor" in source:
            offenders.append(name)
    assert offenders == []


def test_t31_core_has_no_module_scope_ctypes_msvcrt_or_helper_import():
    with open(os.path.join(PRODUCTION, "mediated_executor.py"), "r", encoding="utf-8") as handle:
        source = handle.read()
    for forbidden in ("import ctypes", "import msvcrt", "from ctypes"):
        assert forbidden not in source
    # The helper is reachable only through the dynamic, gated loader.
    assert "import triage_core.mediated_executor_win32" not in source
    assert "_load_win32_adapter" in source


def test_t31_helper_imports_no_triagecore_module():
    """The dependency must stay one-way: mechanism never imports policy."""
    with open(
        os.path.join(PRODUCTION, "mediated_executor_win32.py"), "r", encoding="utf-8"
    ) as handle:
        source = handle.read()
    assert "triage_core" not in source.replace(
        "triage_core.mediated_executor", "<forbidden>"
    ).replace("<forbidden>", "")
    assert "from triage_core" not in source
    assert "import triage_core" not in source


def test_t31_core_imports_cleanly_off_windows_without_touching_the_filesystem():
    """Proven in a subprocess with the adapter import made explosive."""
    script = (
        "import sys, builtins\n"
        "real = builtins.__import__\n"
        "def guard(name, *a, **k):\n"
        "    if name.endswith('mediated_executor_win32'):\n"
        "        raise AssertionError('helper imported at module scope')\n"
        "    return real(name, *a, **k)\n"
        "builtins.__import__ = guard\n"
        "import triage_core.mediated_executor as m\n"
        "assert m.PLATFORM_PROFILE == 'windows'\n"
        "print('OK')\n"
    )
    env = dict(os.environ, PYTHONPATH=REPO_ROOT)
    completed = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, env=env
    )
    assert completed.returncode == 0, completed.stderr
    assert "OK" in completed.stdout


# =============================================================================
# Obligation 30 [N half] -- no network, subprocess, IPC, database, ledger
# =============================================================================


def test_t30n_pure_paths_perform_no_network_subprocess_or_database_access(monkeypatch):
    import socket
    import sqlite3

    def explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("mediated_executor attempted forbidden I/O")

    monkeypatch.setattr(socket, "socket", explode)
    monkeypatch.setattr(socket, "create_connection", explode)
    monkeypatch.setattr(subprocess, "Popen", explode)
    monkeypatch.setattr(subprocess, "run", explode)
    monkeypatch.setattr(sqlite3, "connect", explode)

    outputs = [
        classify_replace_result(False, 1175),
        compare_security_snapshots(snapshot(), snapshot()),
        snapshot_from_capture(Capture()),
        _result().persistent_projection(),
        build_target_registry("ws", [entry()]) if not WINDOWS else None,
    ]
    assert len(outputs) == 5


def test_t30n_executor_imports_no_authority_or_store_module():
    with open(os.path.join(PRODUCTION, "mediated_executor.py"), "r", encoding="utf-8") as handle:
        source = handle.read()
    for forbidden in (
        "triage_core.authz",
        "triage_core.capability_claims",
        "triage_core.task_ledger",
        "triage_core.request_reservation",
        "import socket",
        "import subprocess",
        "import sqlite3",
        "import logging",
    ):
        assert forbidden not in source, forbidden


# =============================================================================
# Windows/NTFS obligations. Real files on a real NTFS volume unless a test's
# docstring says "seam-injected".
# =============================================================================


def _open_target(path):
    import triage_core.mediated_executor_win32 as win32

    return win32.walk_open_target(os.path.dirname(path), (os.path.basename(path),))


def capture_snapshot(path):
    """Core snapshot of a real file, through the adapter."""
    import triage_core.mediated_executor_win32 as win32

    handle = _open_target(str(path))
    try:
        return snapshot_from_capture(win32.capture_security(handle))
    finally:
        win32.close_handle(handle)


def artifacts_in(directory):
    return sorted(n for n in os.listdir(directory) if n.startswith(".tcx-"))


def make_junction(link, target):
    """Junctions need no elevation, which is why they carry T6/T7."""
    completed = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:  # pragma: no cover - environment guard
        pytest.fail("junction creation failed")


def adapter_error():
    import triage_core.mediated_executor_win32 as win32

    return win32.Win32AdapterError


# --- Priority 1: T35[W] genuine NTFS observation -----------------------------


@windows_only
@pytest.mark.windows
def test_t35w_auto_inherited_transition_is_accepted_and_recorded(
    tmp_path, record_property
):
    """Genuine NTFS. Starts from a confirmed pre-state, requires one of the
    three accepted transitions, and records which one occurred.

    Not reproducing False -> True is NOT a failure (CR 10.1a): a runner that
    produces False -> False has exhibited another accepted transition.
    """
    pre_bytes, post_bytes = b"before\n", b"after\n"
    root, target = workspace(tmp_path, content=pre_bytes)

    before = capture_snapshot(target)
    pre_bit = before.control_bits[2]
    record_property("se_dacl_auto_inherited_pre", str(pre_bit))

    result = execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    # The post snapshot is captured BEFORE any outcome assertion, so a
    # metadata_preservation_failed result can still be classified rather than
    # aborting the test with the component difference unknown.
    try:
        after = capture_snapshot(target)
    except Exception:
        after = None

    differences = []
    if after is None:
        differences.append("post_capture_failed")
    else:
        if before.owner_sid != after.owner_sid:
            differences.append("owner")
        if before.dacl_state != after.dacl_state:
            differences.append("dacl_state")
        if before.control_bits[0] != after.control_bits[0]:
            differences.append("dacl_present")
        if before.control_bits[1] != after.control_bits[1]:
            differences.append("dacl_protected")
        if before.control_bits[2] != after.control_bits[2]:
            differences.append("dacl_auto_inherited")
        if before.acl_revision != after.acl_revision:
            differences.append("acl_revision")
        if before.ace_count != after.ace_count:
            differences.append("ace_count")
        if before.aces != after.aces:
            differences.append("ace_bytes_or_order")

    # DIAGNOSTIC: field names only. No SID, ACE, descriptor, path, or
    # control-bit VALUE is emitted -- only which component differed.
    if result.reason_code == "metadata_preservation_failed":
        pytest.fail(
            "hosted_metadata_differences="
            + (",".join(differences) if differences else "unclassified")
        )

    assert result.outcome == OUTCOME_VERIFIED, result.reason_code
    assert after is not None

    post_bit = after.control_bits[2]
    transition = "{0}->{1}".format(pre_bit, post_bit)
    record_property("se_dacl_auto_inherited_transition", transition)

    assert transition in {"False->False", "False->True", "True->True"}, transition
    assert (pre_bit, post_bit) != (True, False)

    # Every other component must be exactly preserved. Computed labels are
    # used so a failure names the component without printing its value.
    assert differences in ([], ["dacl_auto_inherited"]), differences


# --- Priority 2: healthy replacement and backup lifecycle --------------------


@windows_only
@pytest.mark.windows
def test_t19_successful_replacement_writes_exact_bytes_and_deletes_backup(tmp_path):
    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, target = workspace(tmp_path, content=pre_bytes)

    result = execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    assert result.reason_code == "ok"
    assert result.outcome == OUTCOME_VERIFIED
    assert target.read_bytes() == post_bytes
    assert result.observed_post_digest == digest_of(post_bytes)
    assert result.backup_retained is False
    assert artifacts_in(target.parent) == []


@windows_only
@pytest.mark.windows
def test_t14_exact_bytes_survive_crlf_bom_and_normal_form(tmp_path):
    """No normalisation anywhere between the caller and the disk."""
    pre_bytes = b"alpha\r\nbeta\n"
    post_bytes = "﻿gamma\r\ndelta\né\n".encode("utf-8")
    root, target = workspace(tmp_path, content=pre_bytes)

    result = execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    assert result.reason_code == "ok"
    written = target.read_bytes()
    assert written == post_bytes
    assert b"\xef\xbb\xbf" in written
    assert b"\r\n" in written


@windows_only
@pytest.mark.windows
def test_t33_backup_retained_when_deletion_fails_but_outcome_stays_verified(
    tmp_path, monkeypatch
):
    """Seam-injected backup-deletion failure. A hygiene fact, never a
    downgrade of the verified outcome."""
    import triage_core.mediated_executor_win32 as win32

    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, target = workspace(tmp_path, content=pre_bytes)
    real_delete = win32.delete_file

    def fail_backup_delete(path):
        if ".tcx-bak-" in path:
            raise win32.Win32AdapterError("delete_file", 5)
        return real_delete(path)

    monkeypatch.setattr(win32, "delete_file", fail_backup_delete)
    result = execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    assert result.reason_code == "ok"
    assert result.outcome == OUTCOME_VERIFIED
    assert result.backup_retained is True
    assert target.read_bytes() == post_bytes
    assert any(n.startswith(".tcx-bak-") for n in artifacts_in(target.parent))


@windows_only
@pytest.mark.windows
def test_t15_artifact_names_are_collision_checked_and_never_retried(
    tmp_path, monkeypatch
):
    """A pre-seeded artifact name fails closed; no second name is attempted."""
    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, target = workspace(tmp_path, content=pre_bytes)

    fixed = iter([".tcx-tmp-fixed.tmp", ".tcx-bak-fixed.bak"])
    monkeypatch.setattr(executor, "_artifact_name", lambda *a: next(fixed))
    (target.parent / ".tcx-tmp-fixed.tmp").write_bytes(b"squatter\n")

    result = execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    assert result.reason_code == "temp_creation_failed"
    assert result.outcome == OUTCOME_NOT_ATTEMPTED
    assert target.read_bytes() == pre_bytes
    assert (target.parent / ".tcx-tmp-fixed.tmp").read_bytes() == b"squatter\n"


@windows_only
@pytest.mark.windows
def test_t15_artifact_names_are_unpredictable_and_prefixed(tmp_path, monkeypatch):
    names = []
    real_name = executor._artifact_name
    monkeypatch.setattr(
        executor,
        "_artifact_name",
        lambda p, s: names.append(real_name(p, s)) or names[-1],
    )
    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, _ = workspace(tmp_path, content=pre_bytes)
    execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    temp_name, backup_name = names[0], names[1]
    assert temp_name.startswith(".tcx-tmp-") and temp_name.endswith(".tmp")
    assert backup_name.startswith(".tcx-bak-") and backup_name.endswith(".bak")
    assert len(temp_name) == len(".tcx-tmp-") + 32 + len(".tmp")
    assert temp_name != backup_name
    # A second invocation must not reuse either name.
    assert real_name(".tcx-tmp-", ".tmp") != temp_name


@windows_only
@pytest.mark.windows
def test_t18_temp_and_backup_live_in_the_target_directory(tmp_path, monkeypatch):
    """Same directory therefore same volume, by construction."""
    import triage_core.mediated_executor_win32 as win32

    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, _ = workspace(tmp_path, content=pre_bytes)
    seen = {}
    real_replace = win32.replace_file

    def record(replaced, replacement, backup):
        seen.update(
            replaced=replaced, replacement=replacement, backup=backup
        )
        return real_replace(replaced, replacement, backup)

    monkeypatch.setattr(win32, "replace_file", record)
    execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    directory = os.path.dirname(seen["replaced"]).lower()
    assert os.path.dirname(seen["replacement"]).lower() == directory
    assert os.path.dirname(seen["backup"]).lower() == directory


@windows_only
@pytest.mark.windows
def test_t17_temp_is_flushed_before_the_replacement_call(tmp_path, monkeypatch):
    """Call-order recorder. Implementation-shaped by necessity, and labelled."""
    import triage_core.mediated_executor_win32 as win32

    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, _ = workspace(tmp_path, content=pre_bytes)
    order = []
    real_flush, real_replace = win32.flush_and_close, win32.replace_file

    monkeypatch.setattr(
        win32, "flush_and_close", lambda h: order.append("flush") or real_flush(h)
    )
    monkeypatch.setattr(
        win32,
        "replace_file",
        lambda a, b, c: order.append("replace") or real_replace(a, b, c),
    )
    execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    # Membership first, so a missing flush fails on a clean assertion rather
    # than raising ValueError from .index() -- an unclean failure would not be
    # a valid mutant kill.
    assert "flush" in order, order
    assert "replace" in order, order
    assert order.index("flush") < order.index("replace")
    assert order.count("replace") == 1


@windows_only
@pytest.mark.windows
def test_t16_partial_temp_write_never_alters_the_target(tmp_path, monkeypatch):
    """Seam-injected write failure."""
    import triage_core.mediated_executor_win32 as win32

    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, target = workspace(tmp_path, content=pre_bytes)

    def explode(handle, data):
        raise win32.Win32AdapterError("write_all", 5)

    monkeypatch.setattr(win32, "write_all", explode)
    result = execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    assert result.reason_code == "temp_write_failed"
    assert result.outcome == OUTCOME_NOT_ATTEMPTED
    assert target.read_bytes() == pre_bytes
    assert artifacts_in(target.parent) == []


# --- Mechanism call-log instrumentation --------------------------------------


def instrument(monkeypatch, calls, overrides=None):
    """Wrap every adapter entry point so the mechanism call log is observable.

    Used to prove operation cessation: once an ambiguous state is established
    the log must simply end -- no cleanup, probing, retry, or rollback.
    """
    import triage_core.mediated_executor_win32 as win32

    overrides = overrides or {}
    for name in dir(win32):
        if name.startswith("_"):
            continue
        attribute = getattr(win32, name)
        if isinstance(attribute, type) or not callable(attribute):
            continue

        def wrap(call_name, original):
            def recorder(*args, **kwargs):
                calls.append(call_name)
                if call_name in overrides:
                    return overrides[call_name](*args, **kwargs)
                return original(*args, **kwargs)

            return recorder

        monkeypatch.setattr(win32, name, wrap(name, attribute))
    return win32


MUTATING_CALLS = {
    "replace_file",
    "delete_file",
    "create_private_temp",
    "write_all",
    "flush_and_close",
}

# Operations that actually touch the filesystem or the OS. Pure path helpers
# (paths_equal, strip_verbatim_prefix, expected_final_path, parent_directory,
# child_path) are string functions and are deliberately absent -- they observe
# nothing and mutate nothing, so they cannot constitute continued activity.
#
# close_handle is also absent: releasing a handle already held is not an
# operation on filesystem state, and it must happen or the handle leaks. It is
# asserted separately below.
FILESYSTEM_CALLS = {
    "open_anchor",
    "walk_open_target",
    "create_private_temp",
    "final_path",
    "volume_is_ntfs",
    "volume_filesystem_name",
    "file_identity",
    "file_size",
    "file_size_of_path",
    "is_regular_file",
    "path_exists",
    "has_reparse_ancestor",
    "read_exact_bounded",
    "write_all",
    "flush_and_close",
    "process_default_owner_sid",
    "capture_security",
    "replace_file",
    "delete_file",
}


def assert_ceased_at(calls, expected_final_observation, backup_path=None):
    """Prove the contract's strong rule: once ambiguity is established, no
    further filesystem operation occurs -- not merely no further *mutation*.

    The filesystem call log must END at the exact failing observation. Only
    handle release and pure string helpers may appear afterwards.
    """
    operations = [c for c in calls if c in FILESYSTEM_CALLS]
    assert operations, "no filesystem operations were recorded"
    assert operations[-1] == expected_final_observation, operations[-6:]

    # Nothing filesystem-touching after the failing observation.
    last = len(operations) - 1 - operations[::-1].index(expected_final_observation)
    assert last == len(operations) - 1, operations[last:]

    # Explicit prohibitions, stated independently of ordering.
    assert "delete_file" not in calls, "no cleanup may run in an ambiguous state"
    assert calls.count("replace_file") == 1, "exactly one replacement attempt"
    assert calls.count("create_private_temp") <= 1, "no retry of preparation"
    if backup_path is not None:
        assert os.path.exists(backup_path), "the backup must remain for recovery"


def capture_backup_path(monkeypatch, holder):
    """Record the backup name the executor generates, without disclosing it."""
    real_name = executor._artifact_name

    def remember(prefix, suffix):
        name = real_name(prefix, suffix)
        if prefix == executor.BACKUP_PREFIX:
            holder["backup"] = name
        return name

    monkeypatch.setattr(executor, "_artifact_name", remember)


# --- Priority 3: genuine junction containment --------------------------------


@windows_only
@pytest.mark.windows
def test_t06_junction_as_the_target_fails_closed(tmp_path, monkeypatch):
    """Genuine reparse point at the final target.

    Rejection must occur via the reparse check **before** the executor opens a
    handle to the target (CR 7.2 orders reparse rejection ahead of
    CreateFileW). The zero-open assertion is a mechanism-specific mutant
    assertion: it constrains the executor's own target-handle open, not all OS
    activity -- the lstat-style attribute probe is expressly permitted.
    """
    root = tmp_path / "ws"
    (root / "docs").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    real = outside / "real.md"
    real.write_bytes(b"original\n")

    make_junction(root / "docs" / "notes.md", outside)

    calls = []
    instrument(monkeypatch, calls)
    result = execute_replacement(
        registry_for(str(root)), make_effect(), b"replacement\n"
    )

    assert result.reason_code == "containment_violation"
    assert result.outcome == OUTCOME_NOT_ATTEMPTED
    assert real.read_bytes() == b"original\n"
    # MECHANISM ASSERTION: the reparse target never reached a target-handle open.
    assert calls.count("walk_open_target") == 0, calls


@windows_only
@pytest.mark.windows
def test_t07_junction_ancestor_redirecting_outside_fails_closed(
    tmp_path, monkeypatch
):
    """Pre-existing ancestor junction. A lexical prefix check passes this; the
    mandatory ancestor reparse walk must not, and must reject **before** the
    executor opens a handle to the redirected target.

    The zero-open assertion is a mechanism-specific mutant assertion (see T6).
    """
    root = tmp_path / "ws"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    victim = outside / "notes.md"
    victim.write_bytes(b"original\n")

    make_junction(root / "docs", outside)
    # Lexically the constructed path sits beneath the workspace root.
    assert (root / "docs" / "notes.md").read_bytes() == b"original\n"

    calls = []
    instrument(monkeypatch, calls)
    result = execute_replacement(
        registry_for(str(root)), make_effect(), b"replacement\n"
    )

    assert result.reason_code == "containment_violation"
    assert result.outcome == OUTCOME_NOT_ATTEMPTED
    assert victim.read_bytes() == b"original\n"
    # MECHANISM ASSERTION: the ancestor walk rejected before any target open.
    assert calls.count("walk_open_target") == 0, calls


@windows_only
@pytest.mark.windows
def test_t05_anchor_that_no_longer_resolves_to_the_captured_root_fails_closed(
    tmp_path,
):
    """The anchor is re-verified at execution; a swapped root is a violation."""
    root = tmp_path / "ws"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "notes.md").write_bytes(b"original\n")
    registry = registry_for(str(root))

    elsewhere = tmp_path / "elsewhere"
    (elsewhere / "docs").mkdir(parents=True)
    victim = elsewhere / "docs" / "notes.md"
    victim.write_bytes(b"original\n")

    import shutil

    shutil.rmtree(root)
    make_junction(root, elsewhere)

    result = execute_replacement(registry, make_effect(), b"replacement\n")

    assert result.reason_code == "containment_violation"
    assert result.outcome == OUTCOME_NOT_ATTEMPTED
    assert victim.read_bytes() == b"original\n"


@pytest.mark.windows_optional
@windows_only
def test_optional_symlink_probe_reports_pass_or_environment_unavailable(tmp_path):
    """SUPPLEMENTAL. Outside the 36 obligations, outside the zero-skip count,
    non-gating, and never acceptance evidence. Junctions carry T6/T7."""
    root = tmp_path / "ws"
    (root / "docs").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    real = outside / "real.md"
    real.write_bytes(b"original\n")
    try:
        os.symlink(str(real), str(root / "docs" / "notes.md"))
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("symlink creation unavailable: environment lacks the privilege")

    result = execute_replacement(
        registry_for(str(root)), make_effect(), b"replacement\n"
    )
    assert result.outcome == OUTCOME_NOT_ATTEMPTED
    assert real.read_bytes() == b"original\n"


# --- Priority 4: real sharing conflict and identity re-probe -----------------


@windows_only
@pytest.mark.windows
def test_t26w_real_sharing_conflict_never_reports_verified(tmp_path):
    """Genuine conflict: a live handle without delete sharing.

    The observable contract outcome and the on-disk bytes are asserted; the
    specific Win32 error code is deliberately NOT asserted, because it is not
    guaranteed to be identical across supported runners. Exact 1175/1176/1177
    mapping is carried by the pure classifier tests.
    """
    import triage_core.mediated_executor_win32 as win32

    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, target = workspace(tmp_path, content=pre_bytes)

    blocker = win32._create_file(
        str(target),
        win32.GENERIC_READ,
        win32.FILE_SHARE_READ,
        win32.OPEN_EXISTING,
        win32.FILE_ATTRIBUTE_NORMAL,
        "test_blocker",
    )
    try:
        result = execute_replacement(
            registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
        )
    finally:
        win32.close_handle(blocker)

    assert result.outcome != OUTCOME_VERIFIED
    assert result.reason_code in REASON_CODES
    assert target.read_bytes() == pre_bytes


@windows_only
@pytest.mark.windows
def test_t34_identity_reprobe_catches_a_genuinely_swapped_target(
    tmp_path, monkeypatch
):
    """Genuine identity change; the seam controls only *when* it happens."""
    import triage_core.mediated_executor_win32 as win32

    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, target = workspace(tmp_path, content=pre_bytes)
    real_create = win32.create_private_temp

    def swap_then_create(path):
        # Replace the target with a different file object carrying identical
        # bytes: same name, same content, new file identity.
        os.remove(str(target))
        target.write_bytes(pre_bytes)
        return real_create(path)

    monkeypatch.setattr(win32, "create_private_temp", swap_then_create)
    result = execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    assert result.reason_code == "target_observation_unstable"
    assert result.outcome == OUTCOME_NOT_ATTEMPTED
    assert target.read_bytes() == pre_bytes
    assert artifacts_in(target.parent) == []


# --- Priority 5: injected-only states, clearly labelled ----------------------


@windows_only
@pytest.mark.windows
@pytest.mark.parametrize("code", [1175, 1176])
def test_t25w_injected_documented_intact_errors_report_target_unchanged(
    tmp_path, monkeypatch, code
):
    """SEAM-INJECTED ReplaceFileW error. Classifier evidence, not genuine
    filesystem evidence: Windows will not produce a chosen code on demand."""
    import re

    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, target = workspace(tmp_path, content=pre_bytes)
    calls = []
    seen = {}

    def refuse(replaced, replacement, backup):
        seen.update(replaced=replaced, replacement=replacement, backup=backup)
        return (False, code)

    instrument(monkeypatch, calls, {"replace_file": refuse})

    result = execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    assert result.reason_code == "replacement_refused"
    assert result.outcome == OUTCOME_TARGET_UNCHANGED
    assert target.read_bytes() == pre_bytes
    # The documented-intact path removes our own temp; the target is untouched.
    assert artifacts_in(target.parent) == []

    # MECHANISM ASSERTION: the primitive must be invoked WITH a conforming
    # backup name. Without one, the documented state for this error class is a
    # deleted target -- an unacceptable silent-loss mode (CR 11.2).
    assert re.search(
        r"\\\.tcx-bak-[0-9a-f]{32}\.bak$", seen["backup"]
    ), seen["backup"]
    assert re.search(r"\\\.tcx-tmp-[0-9a-f]{32}\.tmp$", seen["replacement"])


@windows_only
@pytest.mark.windows
def test_t25w_injected_1177_is_ambiguous_and_all_operations_cease(
    tmp_path, monkeypatch
):
    """SEAM-INJECTED. Once ambiguity is established the mechanism call log must
    simply END: no backup deletion, temp cleanup, probing, retry, or rollback."""
    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, _ = workspace(tmp_path, content=pre_bytes)
    calls = []
    instrument(monkeypatch, calls, {"replace_file": lambda *a: (False, 1177)})

    result = execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    assert result.reason_code == "replacement_outcome_unknown"
    assert result.outcome == OUTCOME_MAY_HAVE_OCCURRED
    assert result.backup_retained is True
    assert_ceased_at(calls, "replace_file")


@windows_only
@pytest.mark.windows
@pytest.mark.parametrize("code", [0, 5, 32, 87, 1178])
def test_t25w_injected_undocumented_errors_are_ambiguous_and_cease(
    tmp_path, monkeypatch, code
):
    """SEAM-INJECTED. No documented state exists, so nothing is asserted and
    nothing further is touched."""
    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, _ = workspace(tmp_path, content=pre_bytes)
    calls = []
    instrument(monkeypatch, calls, {"replace_file": lambda *a: (False, code)})

    result = execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    assert result.reason_code == "replacement_outcome_unknown"
    assert result.outcome == OUTCOME_MAY_HAVE_OCCURRED
    assert result.backup_retained is True
    assert_ceased_at(calls, "replace_file")


@windows_only
@pytest.mark.windows
def test_t24_injected_post_divergence_is_ambiguous_with_no_second_mutation(
    tmp_path, monkeypatch
):
    """SEAM-INJECTED post-verification divergence. Exactly one replacement, no
    restore, backup retained, and no further mutating call afterwards."""
    import triage_core.mediated_executor_win32 as win32

    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, target = workspace(tmp_path, content=pre_bytes)
    calls = []
    real_read = win32.read_exact_bounded
    state = {"reads": 0}

    def diverge_on_post_read(handle, limit):
        state["reads"] += 1
        if state["reads"] >= 2:
            return b"divergent-content\n"
        return real_read(handle, limit)

    holder = {}
    capture_backup_path(monkeypatch, holder)
    instrument(monkeypatch, calls, {"read_exact_bounded": diverge_on_post_read})
    result = execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    assert result.reason_code in {"post_digest_mismatch", "post_size_mismatch"}
    assert result.outcome == OUTCOME_MAY_HAVE_OCCURRED
    assert result.backup_retained is True
    # All activity stops at the failing content observation.
    assert_ceased_at(
        calls, "read_exact_bounded", os.path.join(target.parent, holder["backup"])
    )


@windows_only
@pytest.mark.windows
def test_t23_injected_post_containment_loss_is_ambiguous_and_ceases(
    tmp_path, monkeypatch
):
    """SEAM-INJECTED post containment failure."""
    import triage_core.mediated_executor_win32 as win32

    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, _ = workspace(tmp_path, content=pre_bytes)
    calls = []
    state = {"checks": 0}

    def lose_containment(anchor, segments):
        state["checks"] += 1
        return state["checks"] >= 2

    holder = {}
    capture_backup_path(monkeypatch, holder)
    instrument(monkeypatch, calls, {"has_reparse_ancestor": lose_containment})
    result = execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    assert result.reason_code == "post_containment_lost"
    assert result.outcome == OUTCOME_MAY_HAVE_OCCURRED
    assert result.backup_retained is True
    assert_ceased_at(
        calls, "has_reparse_ancestor", os.path.join(root, "docs", holder["backup"])
    )


@windows_only
@pytest.mark.windows
def test_t23_injected_post_final_path_divergence_ceases_at_that_observation(
    tmp_path, monkeypatch
):
    """SEAM-INJECTED failing final-path observation after replacement."""
    import triage_core.mediated_executor_win32 as win32

    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, _ = workspace(tmp_path, content=pre_bytes)
    calls = []
    holder = {}
    real_final, real_replace = win32.final_path, win32.replace_file
    state = {"replaced": False}

    def note_replacement(*args):
        state["replaced"] = True
        return real_replace(*args)

    def diverge_only_after_replacement(handle):
        value = real_final(handle)
        # Keyed off the replacement itself, so the divergence lands on the
        # post-verification resolution rather than on the identity re-probe.
        return value + "\\redirected" if state["replaced"] else value

    capture_backup_path(monkeypatch, holder)
    instrument(
        monkeypatch,
        calls,
        {"final_path": diverge_only_after_replacement, "replace_file": note_replacement},
    )
    result = execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    assert result.reason_code == "post_containment_lost"
    assert result.outcome == OUTCOME_MAY_HAVE_OCCURRED
    assert result.backup_retained is True
    assert_ceased_at(
        calls, "final_path", os.path.join(root, "docs", holder["backup"])
    )


@windows_only
@pytest.mark.windows
def test_t22_injected_post_non_regular_file_is_ambiguous(tmp_path, monkeypatch):
    """SEAM-INJECTED."""
    import triage_core.mediated_executor_win32 as win32

    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, _ = workspace(tmp_path, content=pre_bytes)
    calls = []
    state = {"checks": 0}

    def not_regular_after_replacement(handle):
        state["checks"] += 1
        return state["checks"] < 2

    holder = {}
    capture_backup_path(monkeypatch, holder)
    instrument(monkeypatch, calls, {"is_regular_file": not_regular_after_replacement})
    result = execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    assert result.reason_code == "post_not_regular_file"
    assert result.outcome == OUTCOME_MAY_HAVE_OCCURRED
    assert result.backup_retained is True
    assert_ceased_at(
        calls, "is_regular_file", os.path.join(root, "docs", holder["backup"])
    )


@windows_only
@pytest.mark.windows
def test_t21w_injected_metadata_difference_is_ambiguous_not_success(
    tmp_path, monkeypatch
):
    """SEAM-INJECTED post-capture difference in a participating component."""
    import triage_core.mediated_executor_win32 as win32

    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, _ = workspace(tmp_path, content=pre_bytes)
    calls = []
    real_capture = win32.capture_security
    state = {"captures": 0}

    def broaden_on_post_capture(handle):
        captured = real_capture(handle)
        state["captures"] += 1
        if state["captures"] >= 2:
            return win32.Win32SecurityCapture(
                owner_sid=captured.owner_sid,
                dacl_present=captured.dacl_present,
                dacl_is_null=captured.dacl_is_null,
                control_bits=captured.control_bits,
                acl_revision=captured.acl_revision,
                ace_count=captured.ace_count,
                aces=tuple(reversed(captured.aces)),
            )
        return captured

    holder = {}
    capture_backup_path(monkeypatch, holder)
    instrument(monkeypatch, calls, {"capture_security": broaden_on_post_capture})
    result = execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    assert result.reason_code == "metadata_preservation_failed"
    assert result.outcome == OUTCOME_MAY_HAVE_OCCURRED
    assert result.backup_retained is True
    # The final security capture is the last input to the comparison.
    assert_ceased_at(
        calls, "capture_security", os.path.join(root, "docs", holder["backup"])
    )


@windows_only
@pytest.mark.windows
def test_t21w_injected_malformed_post_capture_is_ambiguous(tmp_path, monkeypatch):
    """SEAM-INJECTED malformed capture after replacement."""
    import triage_core.mediated_executor_win32 as win32

    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, _ = workspace(tmp_path, content=pre_bytes)
    calls = []
    real_capture = win32.capture_security
    state = {"captures": 0}

    def malformed_on_post(handle):
        captured = real_capture(handle)
        state["captures"] += 1
        if state["captures"] >= 2:
            raise win32.Win32AdapterError("capture_security", 0)
        return captured

    holder = {}
    capture_backup_path(monkeypatch, holder)
    instrument(monkeypatch, calls, {"capture_security": malformed_on_post})
    result = execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    assert result.reason_code == "metadata_preservation_failed"
    assert result.outcome == OUTCOME_MAY_HAVE_OCCURRED
    assert result.backup_retained is True
    assert_ceased_at(
        calls, "capture_security", os.path.join(root, "docs", holder["backup"])
    )


@windows_only
@pytest.mark.windows
def test_t20_injected_incompatible_default_owner_refuses_before_mutation(
    tmp_path, monkeypatch
):
    """T20 part 1. SEAM-INJECTED incompatible default owner.

    ``ReplaceFileW`` does not preserve the owner, so an unpreservable case is
    refused rather than promised.
    """
    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, target = workspace(tmp_path, content=pre_bytes)
    calls = []
    instrument(
        monkeypatch,
        calls,
        {"process_default_owner_sid": lambda: b"S-1-5-21-9-9-9-4242"},
    )

    result = execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    assert result.reason_code == "metadata_precondition_failed"
    assert result.outcome == OUTCOME_NOT_ATTEMPTED
    assert target.read_bytes() == pre_bytes
    assert not (MUTATING_CALLS & set(calls)), calls
    assert artifacts_in(target.parent) == []


@windows_only
@pytest.mark.windows
def test_t20_created_file_owner_equals_the_token_default_owner(tmp_path):
    """T20 part 2. A file this process creates without an explicit security
    descriptor carries the token's default owner.

    That is the property the gate depends on, and it is why the gate must read
    ``TokenOwner`` rather than ``TokenUser``. Equality-shaped only: neither SID
    value is attached to the assertion or otherwise emitted.
    """
    import triage_core.mediated_executor_win32 as win32

    root, target = workspace(tmp_path)
    created_owner = capture_snapshot(target).owner_sid
    default_owner = win32.process_default_owner_sid()

    assert created_owner == default_owner


@windows_only
@pytest.mark.windows
def test_t20_ordinary_replacement_passes_the_gate_and_preserves_owner(tmp_path):
    """T20 part 3. The gate does not block an ordinary target, and the owner
    is preserved across the replacement."""
    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, target = workspace(tmp_path, content=pre_bytes)
    before = capture_snapshot(target).owner_sid

    result = execute_replacement(
        registry_for(root), make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    assert result.reason_code == "ok"
    assert result.outcome == OUTCOME_VERIFIED
    assert capture_snapshot(target).owner_sid == before


@windows_only
@pytest.mark.windows
def test_t20_adapter_queries_token_owner_information_class(monkeypatch):
    """T20, designated killer for M30. DETERMINISTIC and host-independent.

    Records the information class passed to every ``GetTokenInformation`` call
    and asserts both the sizing probe and the retrieval request ``TokenOwner``.
    A narrowly fake ``_ADV`` is substituted so the assertion does not depend on
    whether ``TokenUser`` and ``TokenOwner`` happen to resolve to the same SID
    on the machine under test -- which is precisely how the original defect
    escaped local evidence.
    """
    import triage_core.mediated_executor_win32 as win32

    requested_classes = []
    sid_blob = b"\x01\x01\x00\x00\x00\x00\x00\x05\x12\x00\x00\x00"

    class _FakeAdv:
        def OpenProcessToken(self, process, access, token_ref):
            token_ref._obj.value = 1234
            return 1

        def GetTokenInformation(self, token, info_class, buffer, length, needed):
            requested_classes.append(int(info_class))
            if buffer is None:
                needed._obj.value = ctypes.sizeof(ctypes.c_void_p)
                return 0
            ctypes.cast(
                buffer, ctypes.POINTER(win32._TOKEN_OWNER)
            ).contents.Owner = ctypes.cast(
                ctypes.create_string_buffer(sid_blob), ctypes.c_void_p
            ).value
            return 1

    monkeypatch.setattr(win32, "_ADV", _FakeAdv())
    monkeypatch.setattr(win32, "_sid_to_canonical_bytes", lambda p: b"S-1-5-18")
    monkeypatch.setattr(win32, "close_handle", lambda h: None)

    assert win32.process_default_owner_sid() == b"S-1-5-18"

    # Two calls are expected: one for buffer sizing, one for retrieval.
    assert requested_classes == [
        win32._TOKEN_OWNER_CLASS,
        win32._TOKEN_OWNER_CLASS,
    ]
    assert set(requested_classes) == {4}


def test_t20_adapter_exposes_no_dormant_token_user_machinery():
    """Leaving TokenUser definitions in place would weaken M30 and confuse
    review, so their absence is asserted rather than assumed."""
    with open(
        os.path.join(PRODUCTION, "mediated_executor_win32.py"), "r", encoding="utf-8"
    ) as handle:
        source = handle.read()
    assert "_TOKEN_USER_CLASS" not in source
    assert "class _TOKEN_USER" not in source
    assert "_TOKEN_OWNER_CLASS = 4" in source


# --- Resolution: only target_file_id selects the target ----------------------


@windows_only
@pytest.mark.windows
def test_t01_only_target_file_id_selects_the_target(tmp_path):
    """Two registered targets; only the addressed one may change."""
    root = tmp_path / "ws"
    (root / "docs").mkdir(parents=True)
    first = root / "docs" / "notes.md"
    second = root / "docs" / "other.md"
    first.write_bytes(b"original\n")
    second.write_bytes(b"original\n")

    registry = build_target_registry(
        str(root),
        [entry("f-target", "docs/notes.md"), entry("f-other", "docs/other.md")],
    )
    result = execute_replacement(registry, make_effect(), b"replacement\n")

    assert result.reason_code == "ok"
    assert first.read_bytes() == b"replacement\n"
    assert second.read_bytes() == b"original\n"


@windows_only
@pytest.mark.windows
def test_t02_canonical_relpath_cannot_redirect_execution(tmp_path):
    """Registry maps the id to A while the effect names B. Both must survive."""
    root = tmp_path / "ws"
    (root / "docs").mkdir(parents=True)
    registered = root / "docs" / "notes.md"
    named = root / "docs" / "other.md"
    registered.write_bytes(b"original\n")
    named.write_bytes(b"original\n")

    registry = build_target_registry(str(root), [entry("f-target", "docs/notes.md")])
    effect = make_effect(relpath="docs/other.md")

    result = execute_replacement(registry, effect, b"replacement\n")

    assert result.reason_code == "effect_registry_mismatch"
    assert result.outcome == OUTCOME_NOT_ATTEMPTED
    assert registered.read_bytes() == b"original\n"
    assert named.read_bytes() == b"original\n"


@windows_only
@pytest.mark.windows
def test_t03w_unknown_target_id_fails_closed(tmp_path):
    root, target = workspace(tmp_path)
    registry = build_target_registry(root, [entry("f-registered", "docs/notes.md")])

    result = execute_replacement(registry, make_effect(), b"replacement\n")

    assert result.reason_code == "target_id_unknown"
    assert result.outcome == OUTCOME_NOT_ATTEMPTED
    assert target.read_bytes() == b"original\n"


# --- File type, existence, preconditions -------------------------------------


@windows_only
@pytest.mark.windows
def test_t08_directory_target_fails_closed(tmp_path):
    root = tmp_path / "ws"
    (root / "docs" / "notes.md").mkdir(parents=True)

    result = execute_replacement(
        registry_for(str(root)), make_effect(), b"replacement\n"
    )

    assert result.reason_code == "target_not_regular_file"
    assert result.outcome == OUTCOME_NOT_ATTEMPTED
    assert (root / "docs" / "notes.md").is_dir()


@windows_only
@pytest.mark.windows
def test_t09_missing_target_fails_closed_and_creates_nothing(tmp_path):
    root = tmp_path / "ws"
    (root / "docs").mkdir(parents=True)

    result = execute_replacement(
        registry_for(str(root)), make_effect(), b"replacement\n"
    )

    assert result.reason_code == "target_missing"
    assert result.outcome == OUTCOME_NOT_ATTEMPTED
    assert not (root / "docs" / "notes.md").exists()
    assert artifacts_in(root / "docs") == []


@windows_only
@pytest.mark.windows
def test_t10_pre_digest_mismatch_leaves_the_target_unchanged(tmp_path):
    on_disk = b"something else entirely\n"
    root, target = workspace(tmp_path, content=on_disk)

    result = execute_replacement(
        registry_for(root), make_effect(pre=b"original\n"), b"replacement\n"
    )

    assert result.reason_code == "pre_digest_mismatch"
    assert result.outcome == OUTCOME_NOT_ATTEMPTED
    assert result.observed_pre_digest == digest_of(on_disk)
    assert result.observed_pre_digest != result.expected_pre_digest
    assert target.read_bytes() == on_disk
    assert artifacts_in(target.parent) == []


@windows_only
@pytest.mark.windows
def test_t11_proposed_content_mismatch_leaves_the_target_unchanged(tmp_path):
    """The bytes handed in do not hash to the authorized post-digest."""
    pre_bytes = b"original\n"
    root, target = workspace(tmp_path, content=pre_bytes)
    effect = make_effect(pre=pre_bytes, post=b"authorized\n")

    result = execute_replacement(registry_for(root), effect, b"NOT authorized\n")

    assert result.reason_code in {
        "proposed_content_mismatch",
        "proposed_size_mismatch",
    }
    assert result.outcome == OUTCOME_NOT_ATTEMPTED
    assert target.read_bytes() == pre_bytes


@windows_only
@pytest.mark.windows
def test_t12_proposed_size_mismatch_is_reported_as_its_own_condition(tmp_path):
    """Same length family, wrong declared content_size_bytes."""
    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, target = workspace(tmp_path, content=pre_bytes)
    effect = make_effect(
        pre=pre_bytes, post=post_bytes, content_size_bytes=len(post_bytes) + 5
    )

    result = execute_replacement(registry_for(root), effect, post_bytes)

    assert result.reason_code == "proposed_size_mismatch"
    assert result.outcome == OUTCOME_NOT_ATTEMPTED
    assert target.read_bytes() == pre_bytes


@windows_only
@pytest.mark.windows
def test_t13_oversized_existing_content_fails_closed(tmp_path):
    big = b"x" * 200
    root, target = workspace(tmp_path, content=big)
    registry = build_target_registry(
        root, [entry("f-target", "docs/notes.md", maximum_size_bytes=64)]
    )

    result = execute_replacement(
        registry, make_effect(pre=big, post=b"small\n"), b"small\n"
    )

    assert result.reason_code == "pre_size_exceeded"
    assert result.outcome == OUTCOME_NOT_ATTEMPTED
    assert target.read_bytes() == big


@windows_only
@pytest.mark.windows
def test_t13_oversized_proposed_content_fails_closed(tmp_path):
    pre_bytes = b"original\n"
    big = b"y" * 200
    root, target = workspace(tmp_path, content=pre_bytes)
    registry = build_target_registry(
        root, [entry("f-target", "docs/notes.md", maximum_size_bytes=64)]
    )

    result = execute_replacement(
        registry, make_effect(pre=pre_bytes, post=big), big
    )

    assert result.reason_code == "proposed_size_exceeded"
    assert result.outcome == OUTCOME_NOT_ATTEMPTED
    assert target.read_bytes() == pre_bytes


# --- Privacy and forbidden I/O on a real run ---------------------------------


@windows_only
@pytest.mark.windows
def test_t28w_real_run_projection_carries_no_content_or_absolute_path(tmp_path):
    """Canary content in a canary-named workspace, real replacement."""
    canary_root = tmp_path / "CANARY-WORKSPACE-9f1c"
    (canary_root / "docs").mkdir(parents=True)
    target = canary_root / "docs" / "notes.md"
    target.write_bytes(CANARY)
    post_bytes = b"CANARY-SENTINEL-replacement payload\n"

    result = execute_replacement(
        registry_for(str(canary_root)),
        make_effect(pre=CANARY, post=post_bytes),
        post_bytes,
    )
    assert result.reason_code == "ok"

    projection = result.persistent_projection()
    assert_persistent_privacy_safe(projection, artifact_name="executor result")
    serialized = json.dumps(projection)
    for forbidden in (
        "CANARY",
        "SENTINEL",
        "confidential",
        "CANARY-WORKSPACE",
        str(tmp_path),
        ".tcx-tmp-",
        ".tcx-bak-",
        "S-1-5-",
        ":\\",
    ):
        assert forbidden not in serialized, forbidden
    assert "CANARY" not in repr(result)


@windows_only
@pytest.mark.windows
@pytest.mark.parametrize(
    "scenario",
    ["pre_digest_mismatch", "target_missing", "temp_creation_failed"],
)
def test_t29_failures_expose_no_content_or_absolute_paths(
    tmp_path, monkeypatch, scenario
):
    canary_root = tmp_path / "CANARY-WORKSPACE-2d7e"
    (canary_root / "docs").mkdir(parents=True)
    target = canary_root / "docs" / "notes.md"

    if scenario == "target_missing":
        pass
    else:
        target.write_bytes(CANARY if scenario == "pre_digest_mismatch" else b"original\n")
    if scenario == "temp_creation_failed":
        fixed = iter([".tcx-tmp-fixed.tmp", ".tcx-bak-fixed.bak"])
        monkeypatch.setattr(executor, "_artifact_name", lambda *a: next(fixed))
        (target.parent / ".tcx-tmp-fixed.tmp").write_bytes(b"squatter\n")

    result = execute_replacement(
        registry_for(str(canary_root)), make_effect(), b"replacement\n"
    )

    assert result.reason_code == scenario
    blob = repr(result) + json.dumps(result.persistent_projection())
    for forbidden in ("CANARY", "SENTINEL", "confidential", str(tmp_path), ":\\", ".tcx-"):
        assert forbidden not in blob, forbidden


@windows_only
@pytest.mark.windows
def test_t30w_real_replacement_performs_no_forbidden_io(tmp_path, monkeypatch):
    """Exploding stubs during a genuine end-to-end replacement. Workspace file
    I/O is expected and permitted; everything else must not be reached."""
    import socket
    import sqlite3

    def explode(*args, **kwargs):  # pragma: no cover - must never run
        raise AssertionError("executor attempted forbidden I/O")

    pre_bytes, post_bytes = b"original\n", b"replacement\n"
    root, target = workspace(tmp_path, content=pre_bytes)
    registry = registry_for(root)

    monkeypatch.setattr(socket, "socket", explode)
    monkeypatch.setattr(socket, "create_connection", explode)
    monkeypatch.setattr(subprocess, "Popen", explode)
    monkeypatch.setattr(subprocess, "run", explode)
    monkeypatch.setattr(sqlite3, "connect", explode)

    result = execute_replacement(
        registry, make_effect(pre=pre_bytes, post=post_bytes), post_bytes
    )

    assert result.reason_code == "ok"
    assert target.read_bytes() == post_bytes
