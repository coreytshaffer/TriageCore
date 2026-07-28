"""Tests for the CR-YK-002 atomic capability claim registry.

Covers the atomicity, lifecycle, binding, failure, and privacy contracts of
``triage_core.capability_claims`` plus the authorized compatibility boundary in
``triage_core.authz``. No network, subprocess, sleep, randomness, or model
call; concurrency is exercised with threads and a barrier over genuinely
independent SQLite connections.
"""

import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

import pytest

from triage_core.authz import (
    CAPABILITY_SCHEMA,
    EVENT_CAPABILITY_CLAIMED,
    EVENT_CAPABILITY_ISSUED,
    EVENT_CAPABILITY_TERMINAL,
    claim_capability,
    finalize_capability,
)
from triage_core.capability_claims import (
    CLAIM_ALREADY_CLAIMED,
    CLAIM_ARTIFACT_DIGEST_MISMATCH,
    CLAIM_BINDING_MISMATCH,
    CLAIM_EVIDENCE_WRITE_FAILED,
    CLAIM_EXPIRED,
    CLAIM_LEGACY_UNCLAIMABLE,
    CLAIM_NOT_FOUND,
    CLAIM_OK,
    CLAIM_SCOPE_DIGEST_MISMATCH,
    CLAIM_STORE_BUSY,
    CLAIM_STORE_UNAVAILABLE,
    STATE_CLAIMED,
    STATE_COMPLETED,
    STATE_FAILED,
    STATE_ISSUED,
    TERMINAL_ALREADY_TERMINAL,
    TERMINAL_ATTEMPT_MISMATCH,
    TERMINAL_CLAIMANT_MISMATCH,
    TERMINAL_NOT_CLAIMED,
    TERMINAL_NOT_FOUND,
    TERMINAL_OK,
    CapabilityBinding,
    CapabilityClaimStore,
    CapabilityStoreError,
    default_db_path,
)
from triage_core.privacy_invariants import assert_persistent_privacy_safe
from triage_core.task_ledger import TaskLedger

NOW = datetime(2026, 8, 5, 15, 5, 0, tzinfo=timezone.utc)
EXPIRES = NOW + timedelta(minutes=10)
WELL_AFTER_EXPIRY = NOW + timedelta(hours=2)

TASK_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
CAPABILITY_ID = "7c9e6679-7425-40de-944b-e07fc1f90ae7"
ARTIFACT_DIGEST = "sha256:" + "ab" * 32
SCOPE_DIGEST = "sha256:" + "ee" * 32
PLAN_DIGEST = "sha256:" + "cd" * 32
RECEIPT_DIGEST = "sha256:" + "11" * 32
OTHER_DIGEST = "sha256:" + "00" * 32


def _binding(**overrides) -> CapabilityBinding:
    base = dict(
        capability_id=CAPABILITY_ID,
        task_id=TASK_ID,
        decision_id="gd-1234567890abcdef",
        receipt_digest=RECEIPT_DIGEST,
        artifact_byte_digest=ARTIFACT_DIGEST,
        plan_body_digest=PLAN_DIGEST,
        scope_digest=SCOPE_DIGEST,
        approver_identity_id="human-corey",
        expires_at=EXPIRES.isoformat(),
    )
    base.update(overrides)
    return CapabilityBinding(**base)


def _store(tmp_path, **kwargs) -> CapabilityClaimStore:
    return CapabilityClaimStore(default_db_path(str(tmp_path)), **kwargs)


def _claim(store, binding=None, *, claimant="agent-a", attempt="attempt-1", now=NOW):
    return store.claim(
        binding or _binding(),
        claimant_id=claimant,
        execution_attempt_id=attempt,
        now=now,
    )


def _issue(ledger, capability_id=CAPABILITY_ID, task_id=TASK_ID, **payload_overrides):
    """Append a CR-YK-002 issuance event without building a full receipt.

    ``task_id`` is passed to ``append_event``, so it lands in the ledger event
    envelope and never in the payload — the authoritative task binding.
    """
    payload = {
        "schema": CAPABILITY_SCHEMA,
        "capability_id": capability_id,
        "receipt_digest": RECEIPT_DIGEST,
        "decision_id": "gd-1234567890abcdef",
        "artifact_byte_digest": ARTIFACT_DIGEST,
        "plan_body_digest": PLAN_DIGEST,
        "scope_digest": SCOPE_DIGEST,
        "approver_identity_id": "human-corey",
        "issued_at": NOW.isoformat(),
        "expires_at": EXPIRES.isoformat(),
        "single_use": True,
    }
    payload.update(payload_overrides)
    ledger.append_event(task_id, EVENT_CAPABILITY_ISSUED, payload)
    return capability_id


# --- Atomicity ----------------------------------------------------------------

def _race(store, worker_count, binding=None):
    barrier = threading.Barrier(worker_count)
    results = []

    def worker(index):
        barrier.wait()
        results.append(
            store.claim(
                binding or _binding(),
                claimant_id=f"agent-{index}",
                execution_attempt_id=f"attempt-{index}",
                now=NOW,
            )
        )

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(worker_count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def test_two_independent_claimers_produce_exactly_one_success(tmp_path):
    results = _race(_store(tmp_path), 2)

    assert sum(1 for result in results if result.allowed) == 1
    assert sorted(r.reason_code for r in results) == sorted(
        [CLAIM_OK, CLAIM_ALREADY_CLAIMED]
    )


def test_higher_contention_still_produces_exactly_one_success(tmp_path):
    results = _race(_store(tmp_path), 12)

    assert len(results) == 12
    assert sum(1 for result in results if result.allowed) == 1
    assert all(
        result.reason_code == CLAIM_ALREADY_CLAIMED
        for result in results
        if not result.allowed
    )


def test_separate_capabilities_remain_independently_claimable(tmp_path):
    store = _store(tmp_path)
    other_id = "1b4e28ba-2fa1-4d3b-a3f5-cc0c1f2a1a11"

    first = _claim(store)
    second = _claim(
        store, _binding(capability_id=other_id), claimant="agent-b", attempt="attempt-2"
    )

    assert first.allowed and second.allowed
    assert store.get_row(CAPABILITY_ID)["state"] == STATE_CLAIMED
    assert store.get_row(other_id)["state"] == STATE_CLAIMED


def test_duplicate_execution_attempt_id_is_a_binding_conflict(tmp_path):
    store = _store(tmp_path)
    other_id = "1b4e28ba-2fa1-4d3b-a3f5-cc0c1f2a1a11"

    assert _claim(store, attempt="shared-attempt").allowed
    conflict = _claim(
        store, _binding(capability_id=other_id), attempt="shared-attempt"
    )

    assert not conflict.allowed and conflict.reason_code == CLAIM_BINDING_MISMATCH


# --- Lifecycle ----------------------------------------------------------------

def test_claimed_and_terminal_capabilities_are_denied(tmp_path):
    store = _store(tmp_path)
    assert _claim(store).allowed

    assert _claim(store, claimant="agent-b", attempt="attempt-2").reason_code == (
        CLAIM_ALREADY_CLAIMED
    )

    store.finalize(
        CAPABILITY_ID,
        claimant_id="agent-a",
        execution_attempt_id="attempt-1",
        outcome=STATE_COMPLETED,
        now=NOW,
    )
    assert _claim(store, claimant="agent-c", attempt="attempt-3").reason_code == (
        CLAIM_ALREADY_CLAIMED
    )


def test_failed_or_crashed_execution_never_restores_the_capability(tmp_path):
    store = _store(tmp_path)
    assert _claim(store).allowed

    # Terminal failure is still terminal: it does not release the capability.
    assert store.finalize(
        CAPABILITY_ID,
        claimant_id="agent-a",
        execution_attempt_id="attempt-1",
        outcome=STATE_FAILED,
        now=NOW,
    ).applied
    assert store.get_row(CAPABILITY_ID)["state"] == STATE_FAILED
    assert not _claim(store, claimant="agent-b", attempt="attempt-9").allowed

    # An abandoned claim (no terminal transition at all) is equally burnt.
    abandoned = "9f1c8e2d-3a4b-4c5d-8e6f-0a1b2c3d4e5f"
    assert _claim(store, _binding(capability_id=abandoned), attempt="attempt-x").allowed
    retry = _claim(store, _binding(capability_id=abandoned), attempt="attempt-y")
    assert not retry.allowed and retry.reason_code == CLAIM_ALREADY_CLAIMED


def test_expired_capabilities_cannot_be_claimed(tmp_path):
    result = _claim(_store(tmp_path), now=WELL_AFTER_EXPIRY)

    assert not result.allowed and result.reason_code == CLAIM_EXPIRED


def test_claim_committed_before_expiry_may_finalize_after_expiry(tmp_path):
    store = _store(tmp_path)
    assert _claim(store).allowed

    terminal = store.finalize(
        CAPABILITY_ID,
        claimant_id="agent-a",
        execution_attempt_id="attempt-1",
        outcome=STATE_COMPLETED,
        now=WELL_AFTER_EXPIRY,
    )
    assert terminal.applied and terminal.reason_code == TERMINAL_OK


# --- Terminal contract --------------------------------------------------------

def test_only_matching_claimant_and_attempt_can_finalize(tmp_path):
    store = _store(tmp_path)
    assert _claim(store).allowed

    wrong_claimant = store.finalize(
        CAPABILITY_ID,
        claimant_id="agent-b",
        execution_attempt_id="attempt-1",
        outcome=STATE_COMPLETED,
        now=NOW,
    )
    assert wrong_claimant.reason_code == TERMINAL_CLAIMANT_MISMATCH

    wrong_attempt = store.finalize(
        CAPABILITY_ID,
        claimant_id="agent-a",
        execution_attempt_id="attempt-2",
        outcome=STATE_COMPLETED,
        now=NOW,
    )
    assert wrong_attempt.reason_code == TERMINAL_ATTEMPT_MISMATCH
    assert store.get_row(CAPABILITY_ID)["state"] == STATE_CLAIMED


def test_terminal_states_cannot_transition_again(tmp_path):
    store = _store(tmp_path)
    assert _claim(store).allowed
    kwargs = dict(
        claimant_id="agent-a", execution_attempt_id="attempt-1", now=NOW
    )

    assert store.finalize(CAPABILITY_ID, outcome=STATE_COMPLETED, **kwargs).applied
    second = store.finalize(CAPABILITY_ID, outcome=STATE_FAILED, **kwargs)

    assert not second.applied and second.reason_code == TERMINAL_ALREADY_TERMINAL
    assert store.get_row(CAPABILITY_ID)["state"] == STATE_COMPLETED


def test_denied_claim_leaves_no_row_behind(tmp_path):
    """A denied attempt rolls back its insert, so bindings cannot be poisoned.

    If a denied attempt committed its row, an attacker could materialize a
    capability with bogus bindings and permanently lock out the legitimate
    claimer via a binding mismatch.
    """
    store = _store(tmp_path)

    assert _claim(store, now=WELL_AFTER_EXPIRY).reason_code == CLAIM_EXPIRED
    assert store.get_row(CAPABILITY_ID) is None

    assert _claim(store).allowed


def test_unclaimed_and_unknown_capabilities_cannot_finalize(tmp_path):
    store = _store(tmp_path)
    kwargs = dict(
        claimant_id="agent-a", execution_attempt_id="attempt-1",
        outcome=STATE_COMPLETED, now=NOW,
    )

    assert store.finalize("no-such-capability", **kwargs).reason_code == (
        TERMINAL_NOT_FOUND
    )

    # Defensive guard: an ``issued`` row is not reachable through the public
    # API (denied claims roll back), so insert one directly to prove finalize
    # still refuses anything that is not currently claimed.
    binding = _binding()
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "INSERT INTO capability_claims "
            "(capability_id, task_id, decision_id, receipt_digest, "
            " artifact_byte_digest, plan_body_digest, scope_digest, "
            " approver_identity_id, expires_at, state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'issued')",
            binding.as_row_values(),
        )

    assert store.finalize(CAPABILITY_ID, **kwargs).reason_code == TERMINAL_NOT_CLAIMED


def test_rejects_unknown_terminal_outcome(tmp_path):
    with pytest.raises(CapabilityStoreError):
        _store(tmp_path).finalize(
            CAPABILITY_ID,
            claimant_id="agent-a",
            execution_attempt_id="attempt-1",
            outcome="cancelled",
            now=NOW,
        )


# --- Immutable bindings -------------------------------------------------------

def test_conflicting_bindings_cannot_replace_the_stored_row(tmp_path):
    store = _store(tmp_path)
    assert _claim(store).allowed

    for override in (
        {"decision_id": "gd-attacker"},
        {"receipt_digest": OTHER_DIGEST},
        {"plan_body_digest": OTHER_DIGEST},
        {"approver_identity_id": "human-attacker"},
    ):
        conflicting = _claim(store, _binding(**override), attempt="attempt-conflict")
        assert not conflicting.allowed
        assert conflicting.reason_code == CLAIM_BINDING_MISMATCH

    row = store.get_row(CAPABILITY_ID)
    assert row["decision_id"] == "gd-1234567890abcdef"
    assert row["receipt_digest"] == RECEIPT_DIGEST
    assert row["approver_identity_id"] == "human-corey"


def test_database_triggers_block_binding_mutation_and_row_deletion(tmp_path):
    store = _store(tmp_path)
    assert _claim(store).allowed

    with sqlite3.connect(store.db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE capability_claims SET artifact_byte_digest = ? "
                "WHERE capability_id = ?",
                (OTHER_DIGEST, CAPABILITY_ID),
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "DELETE FROM capability_claims WHERE capability_id = ?",
                (CAPABILITY_ID,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE capability_claims SET state = 'issued' "
                "WHERE capability_id = ?",
                (CAPABILITY_ID,),
            )


# --- Schema-enforced lifecycle (direct SQL) -----------------------------------
#
# The module documents SQLite as authoritative for lifecycle state, claim
# ownership, and terminal transitions. These tests hold the schema to that claim
# by bypassing the Python API entirely: every write below goes straight to the
# database, which is the only way to prove the enforcement lives in the schema
# rather than in the caller.

_RAW_COLUMNS = (
    "capability_id, task_id, decision_id, receipt_digest, artifact_byte_digest, "
    "plan_body_digest, scope_digest, approver_identity_id, expires_at, state"
)
_OTHER_CAPABILITY_ID = "9b2c4f18-6d0a-4e57-8c31-2f7a5b6d8e40"


def _raw_row_values(capability_id=_OTHER_CAPABILITY_ID, state=STATE_ISSUED):
    return (
        capability_id,
        TASK_ID,
        "gd-1234567890abcdef",
        RECEIPT_DIGEST,
        ARTIFACT_DIGEST,
        PLAN_DIGEST,
        SCOPE_DIGEST,
        "human-corey",
        EXPIRES.isoformat(),
        state,
    )


def _seeded_store(tmp_path, state=STATE_ISSUED):
    """Store carrying one directly inserted row in ``state``."""
    store = _store(tmp_path)
    store.get_row(CAPABILITY_ID)  # materializes the schema
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            f"INSERT INTO capability_claims ({_RAW_COLUMNS}) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _raw_row_values(state=state),
        )
    return store


@pytest.mark.parametrize("target", [STATE_COMPLETED, STATE_FAILED])
def test_database_rejects_forward_skip_past_claimed(tmp_path, target):
    """``issued`` may only become ``claimed``; a terminal row was never claimed."""
    store = _seeded_store(tmp_path)

    with sqlite3.connect(store.db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE capability_claims SET state = ? WHERE capability_id = ?",
                (target, _OTHER_CAPABILITY_ID),
            )

    assert store.get_row(_OTHER_CAPABILITY_ID)["state"] == STATE_ISSUED


def test_database_rejects_claimed_row_without_an_owner(tmp_path):
    """A ``claimed`` row must name its claimant and execution attempt."""
    store = _store(tmp_path)
    store.get_row(CAPABILITY_ID)

    with sqlite3.connect(store.db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                f"INSERT INTO capability_claims ({_RAW_COLUMNS}) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                _raw_row_values(state=STATE_CLAIMED),
            )

    assert store.get_row(_OTHER_CAPABILITY_ID) is None


def test_database_rejects_terminal_row_that_was_never_claimed(tmp_path):
    store = _store(tmp_path)
    store.get_row(CAPABILITY_ID)

    with sqlite3.connect(store.db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                f"INSERT INTO capability_claims ({_RAW_COLUMNS}, terminal_outcome) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (*_raw_row_values(state=STATE_COMPLETED), STATE_COMPLETED),
            )

    assert store.get_row(_OTHER_CAPABILITY_ID) is None


def test_database_rejects_issued_row_carrying_claim_metadata(tmp_path):
    """An ``issued`` row must be empty of lifecycle metadata."""
    store = _store(tmp_path)
    store.get_row(CAPABILITY_ID)

    with sqlite3.connect(store.db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                f"INSERT INTO capability_claims ({_RAW_COLUMNS}, claimant_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (*_raw_row_values(), "agent-a"),
            )

    assert store.get_row(_OTHER_CAPABILITY_ID) is None


@pytest.mark.parametrize(
    "column, value",
    [
        ("claimant_id", "agent-impostor"),
        ("execution_attempt_id", "attempt-forged"),
        ("claimed_at", "1999-01-01T00:00:00+00:00"),
    ],
)
def test_database_blocks_claim_ownership_mutation(tmp_path, column, value):
    """Claim ownership is immutable once the row leaves ``issued``."""
    store = _store(tmp_path)
    assert _claim(store).allowed
    before = store.get_row(CAPABILITY_ID)

    with sqlite3.connect(store.db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                f"UPDATE capability_claims SET {column} = ? WHERE capability_id = ?",
                (value, CAPABILITY_ID),
            )

    assert store.get_row(CAPABILITY_ID)[column] == before[column]


@pytest.mark.parametrize(
    "column, value",
    [
        ("terminal_outcome", STATE_FAILED),
        ("terminal_at", "1999-01-01T00:00:00+00:00"),
    ],
)
def test_database_blocks_terminal_metadata_mutation(tmp_path, column, value):
    store = _store(tmp_path)
    assert _claim(store).allowed
    assert store.finalize(
        CAPABILITY_ID,
        claimant_id="agent-a",
        execution_attempt_id="attempt-1",
        outcome=STATE_COMPLETED,
        now=NOW,
    ).applied
    before = store.get_row(CAPABILITY_ID)

    with sqlite3.connect(store.db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                f"UPDATE capability_claims SET {column} = ? WHERE capability_id = ?",
                (value, CAPABILITY_ID),
            )

    assert store.get_row(CAPABILITY_ID)[column] == before[column]


def test_hardened_schema_leaves_the_ordinary_lifecycle_working(tmp_path):
    """The constraints must not narrow the legitimate claim/finalize path."""
    store = _store(tmp_path)

    assert _claim(store).allowed
    claimed = store.get_row(CAPABILITY_ID)
    assert claimed["state"] == STATE_CLAIMED
    assert claimed["terminal_at"] is None and claimed["terminal_outcome"] is None

    for outcome in (STATE_COMPLETED, STATE_FAILED):
        fresh = _store(tmp_path / outcome)
        assert _claim(fresh).allowed
        assert fresh.finalize(
            CAPABILITY_ID,
            claimant_id="agent-a",
            execution_attempt_id="attempt-1",
            outcome=outcome,
            now=NOW,
        ).applied
        row = fresh.get_row(CAPABILITY_ID)
        assert row["state"] == outcome and row["terminal_outcome"] == outcome
        assert row["claimant_id"] == "agent-a"


def test_v1_schema_database_fails_closed(tmp_path):
    """A pre-hardening v1 file is unsupported, not silently reused.

    ``CREATE TABLE IF NOT EXISTS`` cannot retrofit the v2 row-shape CHECK, so a
    v1 file would otherwise keep the weak schema while reporting success.
    """
    store = _store(tmp_path)
    assert _claim(store).allowed
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE schema_meta SET value = ? WHERE key = 'schema_version'",
            ("triagecore.capability_claims.v1",),
        )

    result = _claim(
        CapabilityClaimStore(store.db_path),
        _binding(capability_id=_OTHER_CAPABILITY_ID),
    )

    assert not result.allowed and result.reason_code == CLAIM_STORE_UNAVAILABLE


def test_empty_scope_digest_is_bound_literally_not_treated_as_wildcard(tmp_path):
    store = _store(tmp_path)
    assert _claim(store, _binding(scope_digest="")).allowed

    row = store.get_row(CAPABILITY_ID)
    assert row["scope_digest"] == ""

    # A later attempt presenting a real scope digest is a binding conflict.
    conflict = _claim(store, _binding(scope_digest=SCOPE_DIGEST), attempt="attempt-2")
    assert conflict.reason_code == CLAIM_BINDING_MISMATCH


def test_binding_validation_rejects_malformed_digests():
    with pytest.raises(CapabilityStoreError):
        _binding(artifact_byte_digest="not-a-digest")
    with pytest.raises(CapabilityStoreError):
        _binding(scope_digest="sha256:zz")
    with pytest.raises(CapabilityStoreError):
        _binding(capability_id="  ")


# --- Store failure modes ------------------------------------------------------

def test_busy_store_fails_closed(tmp_path):
    store = _store(tmp_path, busy_timeout_ms=1)
    assert _claim(store).allowed

    blocker = sqlite3.connect(store.db_path, isolation_level=None)
    try:
        blocker.execute("BEGIN IMMEDIATE")
        blocked = _claim(
            store,
            _binding(capability_id="0e2f1a3b-4c5d-4e6f-8a9b-0c1d2e3f4a5b"),
            attempt="attempt-blocked",
        )
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()

    assert not blocked.allowed and blocked.reason_code == CLAIM_STORE_BUSY


def test_corrupt_database_fails_closed(tmp_path):
    store = _store(tmp_path)
    assert _claim(store).allowed
    with open(store.db_path, "wb") as handle:
        handle.write(b"this is not a sqlite database" * 40)

    result = _claim(
        CapabilityClaimStore(store.db_path),
        _binding(capability_id="5d41402a-bc4b-4a76-b971-9d911017c592"),
    )

    assert not result.allowed and result.reason_code == CLAIM_STORE_UNAVAILABLE
    assert CapabilityClaimStore(store.db_path).check_integrity() is False


def test_unsupported_schema_version_fails_closed(tmp_path):
    store = _store(tmp_path)
    assert _claim(store).allowed
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE schema_meta SET value = ? WHERE key = 'schema_version'",
            ("triagecore.capability_claims.v999",),
        )

    result = _claim(
        CapabilityClaimStore(store.db_path),
        _binding(capability_id="5d41402a-bc4b-4a76-b971-9d911017c592"),
    )

    assert not result.allowed and result.reason_code == CLAIM_STORE_UNAVAILABLE


def test_malformed_existing_table_fails_closed(tmp_path):
    db_path = default_db_path(str(tmp_path))
    import os

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE capability_claims (unexpected_column TEXT)")

    result = _claim(CapabilityClaimStore(db_path))

    assert not result.allowed and result.reason_code == CLAIM_STORE_UNAVAILABLE


# --- Compatibility boundary (triage_core.authz) -------------------------------

def test_claim_capability_reports_precise_binding_reasons(tmp_path):
    ledger = TaskLedger(ledger_dir=str(tmp_path))
    _issue(ledger)
    common = dict(claimant_id="agent-a", now=NOW)

    missing = claim_capability(
        ledger, TASK_ID, "unknown-capability", ARTIFACT_DIGEST, SCOPE_DIGEST, **common
    )
    assert missing.reason_code == CLAIM_NOT_FOUND

    artifact = claim_capability(
        ledger, TASK_ID, CAPABILITY_ID, OTHER_DIGEST, SCOPE_DIGEST, **common
    )
    assert artifact.reason_code == CLAIM_ARTIFACT_DIGEST_MISMATCH

    scope = claim_capability(
        ledger, TASK_ID, CAPABILITY_ID, ARTIFACT_DIGEST, OTHER_DIGEST, **common
    )
    assert scope.reason_code == CLAIM_SCOPE_DIGEST_MISMATCH

    ok = claim_capability(
        ledger, TASK_ID, CAPABILITY_ID, ARTIFACT_DIGEST, SCOPE_DIGEST, **common
    )
    assert ok.allowed and ok.reason_code == CLAIM_OK


def test_legacy_capability_events_are_permanently_unclaimable(tmp_path):
    ledger = TaskLedger(ledger_dir=str(tmp_path))
    # A pre-CR-YK-002 payload: no schema, no plan/scope bindings.
    ledger.append_event(
        TASK_ID,
        EVENT_CAPABILITY_ISSUED,
        {
            "capability_id": CAPABILITY_ID,
            "receipt_digest": RECEIPT_DIGEST,
            "decision_id": "gd-1234567890abcdef",
            "artifact_byte_digest": ARTIFACT_DIGEST,
            "approver_identity_id": "human-corey",
            "expires_at": EXPIRES.isoformat(),
            "single_use": True,
        },
    )

    result = claim_capability(
        ledger, TASK_ID, CAPABILITY_ID, ARTIFACT_DIGEST, SCOPE_DIGEST,
        claimant_id="agent-a", now=NOW,
    )

    assert not result.allowed
    assert result.reason_code == CLAIM_LEGACY_UNCLAIMABLE
    assert CapabilityClaimStore(default_db_path(str(tmp_path))).get_row(
        CAPABILITY_ID
    ) is None


class _EvidenceFailureLedger(TaskLedger):
    """Ledger whose success-event append fails after SQLite has committed."""

    def append_event(self, task_id, event_type, payload):
        if event_type == EVENT_CAPABILITY_CLAIMED:
            raise OSError("ledger unavailable")
        return super().append_event(task_id, event_type, payload)


def test_ledger_failure_after_commit_burns_the_capability(tmp_path):
    ledger = _EvidenceFailureLedger(ledger_dir=str(tmp_path))
    _issue(ledger)

    result = claim_capability(
        ledger, TASK_ID, CAPABILITY_ID, ARTIFACT_DIGEST, SCOPE_DIGEST,
        claimant_id="agent-a", execution_attempt_id="attempt-1", now=NOW,
    )

    # Not execution-ready, and identified as an evidence-write failure.
    assert not result.allowed
    assert result.reason_code == CLAIM_EVIDENCE_WRITE_FAILED

    # The capability is nonetheless irreversibly claimed, and a retry through a
    # healthy ledger cannot reclaim it.
    store = CapabilityClaimStore(default_db_path(str(tmp_path)))
    assert store.get_row(CAPABILITY_ID)["state"] == STATE_CLAIMED

    healthy = TaskLedger(ledger_dir=str(tmp_path))
    retry = claim_capability(
        healthy, TASK_ID, CAPABILITY_ID, ARTIFACT_DIGEST, SCOPE_DIGEST,
        claimant_id="agent-b", execution_attempt_id="attempt-2", now=NOW,
    )
    assert not retry.allowed and retry.reason_code == CLAIM_ALREADY_CLAIMED


def test_finalize_capability_records_terminal_evidence(tmp_path):
    ledger = TaskLedger(ledger_dir=str(tmp_path))
    _issue(ledger)
    claimed = claim_capability(
        ledger, TASK_ID, CAPABILITY_ID, ARTIFACT_DIGEST, SCOPE_DIGEST,
        claimant_id="agent-a", execution_attempt_id="attempt-1", now=NOW,
    )
    assert claimed.allowed

    terminal = finalize_capability(
        ledger, TASK_ID, CAPABILITY_ID, STATE_COMPLETED,
        claimant_id="agent-a", execution_attempt_id="attempt-1", now=NOW,
    )

    assert terminal.allowed
    events = ledger.get_events(TASK_ID)
    recorded = [e for e in events if e["event_type"] == EVENT_CAPABILITY_TERMINAL]
    assert len(recorded) == 1
    assert recorded[0]["payload"]["terminal_outcome"] == STATE_COMPLETED


# --- Envelope task binding (CR-YK-002 issuance-contract amendment) ------------

def test_issuance_payload_omits_task_id_and_keeps_required_versioned_fields(tmp_path):
    ledger = TaskLedger(ledger_dir=str(tmp_path))
    _issue(ledger)

    event = next(
        e for e in ledger.get_events(TASK_ID)
        if e["event_type"] == EVENT_CAPABILITY_ISSUED
    )

    for field in ("schema", "plan_body_digest", "scope_digest", "issued_at"):
        assert field in event["payload"]
    assert event["payload"]["schema"] == CAPABILITY_SCHEMA
    # The task binding lives in the envelope and is never duplicated.
    assert "task_id" not in event["payload"]
    assert event["task_id"] == TASK_ID


def test_database_stores_the_exact_envelope_task_id(tmp_path):
    ledger = TaskLedger(ledger_dir=str(tmp_path))
    _issue(ledger)

    assert claim_capability(
        ledger, TASK_ID, CAPABILITY_ID, ARTIFACT_DIGEST, SCOPE_DIGEST,
        claimant_id="agent-a", execution_attempt_id="attempt-1", now=NOW,
    ).allowed

    envelope_task_id = next(
        e["task_id"] for e in ledger.get_events(TASK_ID)
        if e["event_type"] == EVENT_CAPABILITY_ISSUED
    )
    row = CapabilityClaimStore(default_db_path(str(tmp_path))).get_row(CAPABILITY_ID)
    assert row["task_id"] == envelope_task_id == TASK_ID


@pytest.mark.parametrize("bad_task_id", ["", "   "])
def test_blank_envelope_task_id_is_never_claimable(tmp_path, bad_task_id):
    ledger = TaskLedger(ledger_dir=str(tmp_path))
    _issue(ledger, task_id=bad_task_id)

    result = claim_capability(
        ledger, bad_task_id, CAPABILITY_ID, ARTIFACT_DIGEST, SCOPE_DIGEST,
        claimant_id="agent-a", now=NOW,
    )

    assert not result.allowed
    assert result.reason_code == CLAIM_LEGACY_UNCLAIMABLE
    assert CapabilityClaimStore(default_db_path(str(tmp_path))).get_row(
        CAPABILITY_ID
    ) is None


def test_missing_envelope_task_id_is_never_claimable(tmp_path):
    """A hand-written event with a null envelope task binding fails closed."""
    ledger = TaskLedger(ledger_dir=str(tmp_path))
    _issue(ledger)  # create the ledger file
    event = {
        "event_id": "00000000-0000-4000-8000-000000000000",
        "task_id": None,
        "timestamp": NOW.isoformat(),
        "event_type": EVENT_CAPABILITY_ISSUED,
        "payload": {
            "schema": CAPABILITY_SCHEMA,
            "capability_id": "aa11bb22-cc33-4d44-8e55-ff6677889900",
            "receipt_digest": RECEIPT_DIGEST,
            "decision_id": "gd-1234567890abcdef",
            "artifact_byte_digest": ARTIFACT_DIGEST,
            "plan_body_digest": PLAN_DIGEST,
            "scope_digest": SCOPE_DIGEST,
            "approver_identity_id": "human-corey",
            "issued_at": NOW.isoformat(),
            "expires_at": EXPIRES.isoformat(),
        },
    }
    with open(tmp_path / "ledger.jsonl", "a", encoding="utf-8") as handle:
        handle.write(json.dumps(event) + "\n")

    result = claim_capability(
        ledger, None, "aa11bb22-cc33-4d44-8e55-ff6677889900",
        ARTIFACT_DIGEST, SCOPE_DIGEST, claimant_id="agent-a", now=NOW,
    )

    assert not result.allowed
    assert result.reason_code == CLAIM_LEGACY_UNCLAIMABLE


def test_conflicting_envelope_task_id_fails_the_immutable_binding_check(tmp_path):
    """A capability cannot be rebound to a different task after it is claimed."""
    ledger = TaskLedger(ledger_dir=str(tmp_path))
    _issue(ledger)
    assert claim_capability(
        ledger, TASK_ID, CAPABILITY_ID, ARTIFACT_DIGEST, SCOPE_DIGEST,
        claimant_id="agent-a", execution_attempt_id="attempt-1", now=NOW,
    ).allowed

    # Re-issue the same capability id under a different task envelope.
    other_task = "8f14e45f-ceea-4e78-b3f4-1a2b3c4d5e6f"
    _issue(ledger, task_id=other_task)

    hijack = claim_capability(
        ledger, other_task, CAPABILITY_ID, ARTIFACT_DIGEST, SCOPE_DIGEST,
        claimant_id="agent-b", execution_attempt_id="attempt-2", now=NOW,
    )

    assert not hijack.allowed
    assert hijack.reason_code == CLAIM_BINDING_MISMATCH
    row = CapabilityClaimStore(default_db_path(str(tmp_path))).get_row(CAPABILITY_ID)
    assert row["task_id"] == TASK_ID
    assert row["claimant_id"] == "agent-a"


# --- Privacy ------------------------------------------------------------------

def test_persistent_rows_and_ledger_payloads_are_privacy_safe(tmp_path):
    ledger = TaskLedger(ledger_dir=str(tmp_path))
    _issue(ledger)
    claim_capability(
        ledger, TASK_ID, CAPABILITY_ID, ARTIFACT_DIGEST, SCOPE_DIGEST,
        claimant_id="agent-a", execution_attempt_id="attempt-1", now=NOW,
    )
    finalize_capability(
        ledger, TASK_ID, CAPABILITY_ID, STATE_COMPLETED,
        claimant_id="agent-a", execution_attempt_id="attempt-1", now=NOW,
    )

    row = CapabilityClaimStore(default_db_path(str(tmp_path))).get_row(CAPABILITY_ID)
    assert_persistent_privacy_safe(row, artifact_name="capability claim row")

    for event in ledger.get_events(TASK_ID):
        assert_persistent_privacy_safe(
            event["payload"], artifact_name=event["event_type"]
        )

    # Nothing prompt-, credential-, or note-shaped reaches either store.
    serialized = json.dumps(row) + (tmp_path / "ledger.jsonl").read_text("utf-8")
    for forbidden in ("clientDataJSON", "signature", "public_key", "note", "prompt"):
        assert forbidden not in serialized


def test_claim_rejects_blank_claimant_or_attempt(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(CapabilityStoreError):
        _claim(store, claimant="   ")
    with pytest.raises(CapabilityStoreError):
        _claim(store, attempt="")
