"""Tests for the CR-OC-001B atomic client-request reservation store.

Covers all 16 named test obligations from the merged contract. Concurrency uses
real threads over independent SQLite connections with a barrier -- never
monkeypatched pseudo-concurrency, because a faked interleaving proves nothing
about the database.

Several tests bypass the Python layer entirely and drive SQLite directly. That
is deliberate: a public-API test stays green after a schema constraint is
removed, because the Python layer still refuses the operation.
"""

import hashlib
import json
import sqlite3
import threading
from datetime import datetime, timedelta, timezone

import pytest

from triage_core.mediated_effect import (
    DeclaredInvocationContext,
    MediatedContractError,
    MediatedFileDescriptor,
    build_authorized_effect,
    build_client_request,
    build_plan_linkage,
    capability_binding_fields,
)
from triage_core.privacy_invariants import assert_persistent_privacy_safe
from triage_core.request_reservation import (
    CAPABILITY_ALREADY_RESERVED,
    REASON_CODES,
    REQUEST_ID_REUSE_MISMATCH,
    RESERVATION_ALREADY_BOUND,
    RESERVATION_ALREADY_ISSUING,
    RESERVATION_ATTEMPT_MISMATCH,
    RESERVATION_BINDING_MISMATCH,
    RESERVATION_DENIED,
    RESERVATION_ISSUANCE_NOT_BEGUN,
    RESERVATION_NOT_FOUND,
    RESERVATION_STORE_BUSY,
    RESERVATION_STORE_UNAVAILABLE,
    RESERVATION_UNBOUND,
    RESERVE_OK,
    SCHEMA_VERSION,
    STATE_AUTHORIZED,
    STATE_DENIED,
    STATE_ISSUING,
    STATE_RESERVED,
    RequestReservationStore,
    ReservationContractError,
    ReservationError,
    default_db_path,
    mediated_claim_capability,
    mediated_issue_capability,
    token_digest,
)

NOW = datetime(2026, 7, 28, 12, 0, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(minutes=5)

CONTENT = b"alpha\nbeta\n"
CONTENT_DIGEST = "sha256:" + hashlib.sha256(CONTENT).hexdigest()
PRE_DIGEST = "sha256:" + "1a" * 32
CONFIG_DIGEST = "sha256:" + "2b" * 32
OTHER_DIGEST = "sha256:" + "3c" * 32

TASK_ID = "3f2504e0-4f89-41d3-9a0c-0305e82c3301"
DECISION_ID = "gd-1234567890abcdef"
CLIENT_REQUEST_ID = "req-0e2f1a3b4c5d4e6f8a9b0c1d2e3f4a5b"
BROKER_CONNECTION_ID = "conn-8f14e45fceea4e78b3f41a2b3c4d5e6f"


def _effect(**overrides):
    request_id = overrides.pop("client_request_id", CLIENT_REQUEST_ID)
    connection = overrides.pop("broker_connection_id", BROKER_CONNECTION_ID)
    content = overrides.pop("proposed_bytes", CONTENT)
    descriptor = MediatedFileDescriptor(
        target_file_id=overrides.pop("target_file_id", "f-abc123"),
        canonical_relpath=overrides.pop("canonical_relpath", "docs/notes.md"),
        maximum_size_bytes=4096,
    )
    context = DeclaredInvocationContext(
        runtime_id="openclaw",
        runtime_version="1.4.2",
        openclaw_config_digest=CONFIG_DIGEST,
        agent_id="agent-a",
        session_id="session-b",
        tool_name="propose_replacement",
        client_request_id=request_id,
    )
    return build_authorized_effect(
        descriptor,
        context,
        expected_pre_digest=PRE_DIGEST,
        proposed_bytes=content,
        expected_post_digest="sha256:" + hashlib.sha256(content).hexdigest(),
        broker_connection_id=connection,
        client_request_id=request_id,
    )


def _trio(task_id=TASK_ID, decision_id=DECISION_ID, **overrides):
    effect = _effect(**overrides)
    request = build_client_request(effect, task_id=task_id)
    linkage = build_plan_linkage(effect, request, decision_id=decision_id)
    return effect, request, linkage


def _store(tmp_path, **kwargs):
    return RequestReservationStore(default_db_path(str(tmp_path)), **kwargs)


def _reserved(tmp_path, **kwargs):
    """Store with one freshly reserved row; returns (store, trio, token)."""
    store = _store(tmp_path, **kwargs)
    effect, request, linkage = _trio()
    result = store.reserve(request, now=NOW)
    assert result.created and result.attempt_token
    return store, (effect, request, linkage), result.attempt_token


# --- 1. Concurrent insert -----------------------------------------------------


def test_concurrent_reserve_creates_exactly_one_row(tmp_path):
    """Real threads, independent connections, barrier-synchronised."""
    _, request, _ = _trio()
    worker_count = 8
    results = _run_threads(
        tmp_path, [lambda s: s.reserve(request, now=NOW)] * worker_count
    )

    winners = [r for r in results if r.created]
    assert len(winners) == 1
    assert winners[0].attempt_token
    # Every loser is empty-handed: no token, no way to advance the row.
    assert all(not r.attempt_token for r in results if not r.created)

    with sqlite3.connect(default_db_path(str(tmp_path))) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM request_reservations"
        ).fetchone()[0]
    assert count == 1


# --- 2-4. Retry semantics -----------------------------------------------------


def test_same_request_and_digest_returns_the_existing_reservation(tmp_path):
    store, (effect, request, _), token = _reserved(tmp_path)
    assert store.begin_issuance(request, token, now=NOW).applied
    assert store.bind(CLIENT_REQUEST_ID, token, "cap-1", now=NOW).applied

    again = store.reserve(request, now=LATER)

    assert not again.created
    assert again.reason_code == RESERVE_OK
    assert again.state == STATE_AUTHORIZED
    assert again.capability_id == "cap-1"
    assert not again.attempt_token


def test_same_request_id_with_a_different_digest_fails(tmp_path):
    store, (_, request, _), _ = _reserved(tmp_path)
    _, other_request, _ = _trio(proposed_bytes=b"different content\n")
    assert other_request.client_request_id == CLIENT_REQUEST_ID

    result = store.reserve(other_request, now=LATER)

    assert not result.created
    assert result.reason_code == REQUEST_ID_REUSE_MISMATCH


def test_same_request_on_a_different_connection_fails(tmp_path):
    """The realistic reconnect path, where the digest changes as well."""
    store, (_, request, _), _ = _reserved(tmp_path)
    _, other_request, _ = _trio(broker_connection_id="conn-different")
    assert other_request.client_request_id == CLIENT_REQUEST_ID

    result = store.reserve(other_request, now=LATER)

    assert not result.created
    assert result.reason_code == REQUEST_ID_REUSE_MISMATCH


def test_connection_mismatch_is_detected_independently_of_the_digest(tmp_path):
    """The connection comparison must stand on its own.

    ``broker_connection_id`` is inside the request digest today, so the test
    above still passes with the connection comparison deleted -- the digests
    already differ. Observing the check itself requires a row whose digest
    *matches* while the connection does not, which the public builder cannot
    produce, so the row is seeded by direct SQL.

    Without this, deleting the comparison looks harmless right up until the day
    ``broker_connection_id`` leaves the digest object, at which point
    cross-connection reuse becomes legal silently.
    """
    store = _store(tmp_path)
    _, probe, _ = _trio()
    _, seed_only, _ = _trio(client_request_id="req-schema-seed")
    store.reserve(seed_only, now=NOW)  # materialise the schema

    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            _INSERT,
            (probe.client_request_id, OTHER_DIGEST, probe.request_digest(),
             "conn-a-different-one", TASK_ID, STATE_RESERVED, "t"),
        )

    result = store.reserve(probe, now=LATER)

    assert not result.created
    assert result.reason_code == REQUEST_ID_REUSE_MISMATCH


# --- 5-6. One-to-one, through the public API ----------------------------------


def test_one_capability_cannot_bind_to_two_client_requests(tmp_path):
    store = _store(tmp_path)
    _, first, _ = _trio()
    _, second, _ = _trio(client_request_id="req-second")

    first_token = store.reserve(first, now=NOW).attempt_token
    second_token = store.reserve(second, now=NOW).attempt_token
    store.begin_issuance(first, first_token, now=NOW)
    store.begin_issuance(second, second_token, now=NOW)

    assert store.bind(first.client_request_id, first_token, "cap-x", now=NOW).applied
    clash = store.bind(second.client_request_id, second_token, "cap-x", now=NOW)

    assert not clash.applied
    assert clash.reason_code == CAPABILITY_ALREADY_RESERVED


def test_one_client_request_cannot_bind_two_capabilities(tmp_path):
    store, (_, request, _), token = _reserved(tmp_path)
    store.begin_issuance(request, token, now=NOW)
    assert store.bind(CLIENT_REQUEST_ID, token, "cap-a", now=NOW).applied

    second = store.bind(CLIENT_REQUEST_ID, token, "cap-b", now=LATER)

    assert not second.applied
    assert second.reason_code == RESERVATION_ALREADY_BOUND
    assert store.projection(CLIENT_REQUEST_ID)["capability_id"] == "cap-a"


# --- 7. Store failure is not absence ------------------------------------------


def test_locked_store_reports_busy_not_absence(tmp_path):
    store, (_, request, _), _ = _reserved(tmp_path, busy_timeout_ms=1)
    _, other, _ = _trio(client_request_id="req-blocked")

    blocker = sqlite3.connect(store.db_path, isolation_level=None)
    try:
        blocker.execute("BEGIN IMMEDIATE")
        blocked = RequestReservationStore(
            store.db_path, busy_timeout_ms=1
        ).reserve(other, now=NOW)
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()

    assert blocked.reason_code == RESERVATION_STORE_BUSY
    assert blocked.reason_code != RESERVATION_NOT_FOUND


def test_corrupt_store_reports_unavailable_not_absence(tmp_path):
    store, (_, request, _), _ = _reserved(tmp_path)
    with open(store.db_path, "wb") as handle:
        handle.write(b"this is not a sqlite database" * 40)

    _, request, _ = _trio()
    result = RequestReservationStore(store.db_path).reserve(request, now=NOW)

    assert result.reason_code == RESERVATION_STORE_UNAVAILABLE
    assert result.reason_code != RESERVATION_NOT_FOUND


def test_unsupported_schema_reports_unavailable_not_absence(tmp_path):
    store, (_, request, _), _ = _reserved(tmp_path)
    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "UPDATE schema_meta SET value = ? WHERE key = 'schema_version'",
            ("triagecore.request_reservation.v999",),
        )

    _, request, _ = _trio()
    result = RequestReservationStore(store.db_path).reserve(request, now=NOW)

    assert result.reason_code == RESERVATION_STORE_UNAVAILABLE
    assert result.reason_code != RESERVATION_NOT_FOUND


def test_absence_is_reported_only_for_a_healthy_read(tmp_path):
    store = _store(tmp_path)
    _, absent, _ = _trio(client_request_id="req-never-reserved")
    missing = store.begin_issuance(absent, "token", now=NOW)
    assert missing.reason_code == RESERVATION_NOT_FOUND


# --- 8-11. Ownership ----------------------------------------------------------


def test_crash_before_issuance_leaves_the_row_unbound_and_inert(tmp_path):
    """The owner's token is gone; nobody else can advance the row."""
    store, (_, request, _), _lost_token = _reserved(tmp_path)
    del _lost_token  # simulate the crash: the raw token is unrecoverable

    retry = store.reserve(request, now=LATER)

    assert not retry.created
    assert retry.reason_code == RESERVATION_UNBOUND
    assert not retry.attempt_token
    assert store.projection(CLIENT_REQUEST_ID)["capability_id"] == ""


def test_a_concurrent_retry_cannot_sabotage_the_insert_winner(tmp_path):
    store, (_, request, _), token = _reserved(tmp_path)

    loser = store.reserve(request, now=LATER)
    assert not loser.attempt_token

    # The loser holds nothing usable, so no forged token can deny the row.
    # Flip the final hex digit deterministically: a fixed replacement would
    # occasionally reproduce the real token and let a legitimate deny succeed.
    flipped = token[:-1] + ("0" if token[-1] != "0" else "1")
    assert flipped != token
    for forged in ("", "guess", flipped):
        if not forged:
            with pytest.raises(ReservationContractError):
                store.deny(CLIENT_REQUEST_ID, forged, now=LATER)
            continue
        blocked = store.deny(CLIENT_REQUEST_ID, forged, now=LATER)
        assert not blocked.applied
        assert blocked.reason_code == RESERVATION_ATTEMPT_MISMATCH

    # The winner can still complete afterwards.
    assert store.begin_issuance(request, token, now=LATER).applied
    assert store.bind(CLIENT_REQUEST_ID, token, "cap-ok", now=LATER).applied


def test_a_later_invocation_cannot_bind_an_orphaned_row(tmp_path):
    """No sequence available to a non-owner advances an orphaned reservation."""
    store, (_, request, _), _ = _reserved(tmp_path)
    forged = "f" * 64

    # It cannot reach issuing, so it can never reach a bindable state.
    gate = store.begin_issuance(request, forged, now=LATER)
    assert not gate.applied
    assert gate.reason_code == RESERVATION_ATTEMPT_MISMATCH

    # And binding directly is refused because issuance never began.
    stolen = store.bind(CLIENT_REQUEST_ID, forged, "cap-x", now=LATER)
    assert not stolen.applied
    assert stolen.reason_code == RESERVATION_ISSUANCE_NOT_BEGUN

    row = store.projection(CLIENT_REQUEST_ID)
    assert row["state"] == STATE_RESERVED and row["capability_id"] == ""


@pytest.mark.parametrize("operation", ["begin_issuance", "deny", "bind"])
def test_a_wrong_token_cannot_advance_the_row(tmp_path, operation):
    store, (_, request, _), token = _reserved(tmp_path)
    wrong = token[:-1] + ("0" if token[-1] != "0" else "1")

    if operation == "bind":
        store.begin_issuance(request, token, now=NOW)
        result = store.bind(CLIENT_REQUEST_ID, wrong, "cap-x", now=NOW)
    elif operation == "begin_issuance":
        result = store.begin_issuance(request, wrong, now=NOW)
    else:
        result = store.deny(CLIENT_REQUEST_ID, wrong, now=NOW)

    assert not result.applied
    assert result.reason_code == RESERVATION_ATTEMPT_MISMATCH


def test_the_stored_digest_is_not_accepted_as_a_token(tmp_path):
    store, (_, request, _), token = _reserved(tmp_path)
    digest = token_digest(token)

    result = store.begin_issuance(request, digest, now=NOW)

    assert not result.applied
    assert result.reason_code == RESERVATION_ATTEMPT_MISMATCH


# --- 12. Cross-object transplant ----------------------------------------------


def test_records_from_different_operations_cannot_be_combined(tmp_path):
    store, (effect, request, linkage), token = _reserved(tmp_path)
    other_effect, other_request, other_linkage = _trio(
        client_request_id="req-other", target_file_id="f-other"
    )

    with pytest.raises(MediatedContractError):
        mediated_issue_capability(
            store, object(), object(), effect, other_request, linkage, token,
            issue_capability=lambda *a, **k: "cap-never",
            now=NOW,
        )
    with pytest.raises(MediatedContractError):
        mediated_claim_capability(
            store, object(), "cap-x", other_effect, request, other_linkage,
            claim_capability=lambda *a, **k: None,
            claimant_id="agent-a", now=NOW,
        )
    assert store.projection(CLIENT_REQUEST_ID)["state"] == STATE_RESERVED


# --- 13. Direct SQL: the schema itself ----------------------------------------

_INSERT = (
    "INSERT INTO request_reservations ("
    "client_request_id, reservation_attempt_digest, request_digest, "
    "broker_connection_id, task_id, state, reserved_at"
    ") VALUES (?, ?, ?, ?, ?, ?, ?)"
)
_ROW = (CLIENT_REQUEST_ID, OTHER_DIGEST, OTHER_DIGEST, BROKER_CONNECTION_ID,
        TASK_ID, STATE_RESERVED, "2026-07-28T12:00:00+00:00")


def test_direct_sql_rejects_a_duplicate_client_request_id(tmp_path):
    store, (_, request, _), _ = _reserved(tmp_path)
    with sqlite3.connect(store.db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(_INSERT, _ROW)


def test_direct_sql_rejects_a_duplicate_capability_binding(tmp_path):
    store, (_, request, _), token = _reserved(tmp_path)
    store.begin_issuance(request, token, now=NOW)
    store.bind(CLIENT_REQUEST_ID, token, "cap-dup", now=NOW)

    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            _INSERT,
            ("req-second", OTHER_DIGEST, OTHER_DIGEST, BROKER_CONNECTION_ID,
             TASK_ID, STATE_RESERVED, "2026-07-28T12:00:00+00:00"),
        )
        # This step must succeed, so the failure below is unambiguously the
        # uniqueness constraint rather than an earlier transition being refused.
        conn.execute(
            "UPDATE request_reservations SET state='issuing', "
            "issuing_at='2026-07-28T12:01:00+00:00' "
            "WHERE client_request_id='req-second'"
        )
        with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
            conn.execute(
                "UPDATE request_reservations SET state='authorized', "
                "capability_id='cap-dup', bound_at='2026-07-28T12:02:00+00:00' "
                "WHERE client_request_id='req-second'"
            )


def test_direct_sql_rejects_skipping_issuing(tmp_path):
    """reserved -> authorized must be unreachable, even by direct SQL."""
    store, (_, request, _), _ = _reserved(tmp_path)
    with sqlite3.connect(store.db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="illegal"):
            conn.execute(
                "UPDATE request_reservations SET state='authorized', "
                "capability_id='c', issuing_at='x', bound_at='y' "
                "WHERE client_request_id = ?",
                (CLIENT_REQUEST_ID,),
            )
    assert store.projection(CLIENT_REQUEST_ID)["state"] == STATE_RESERVED


def test_direct_sql_rejects_backward_and_absorbing_transitions(tmp_path):
    store, (_, request, _), token = _reserved(tmp_path)
    store.begin_issuance(request, token, now=NOW)
    with sqlite3.connect(store.db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="illegal"):
            conn.execute(
                "UPDATE request_reservations SET state='reserved', issuing_at=NULL "
                "WHERE client_request_id = ?",
                (CLIENT_REQUEST_ID,),
            )
    store.bind(CLIENT_REQUEST_ID, token, "cap-final", now=NOW)
    with sqlite3.connect(store.db_path) as conn:
        # authorized is absorbing. The row shape forces this attempt to null the
        # capability, so the capability-immutability trigger fires first; either
        # guard rejecting it is a correct outcome, and both are asserted
        # separately elsewhere.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE request_reservations SET state='denied', "
                "capability_id=NULL, issuing_at=NULL, bound_at=NULL, "
                "denied_at='z' WHERE client_request_id = ?",
                (CLIENT_REQUEST_ID,),
            )
    assert store.projection(CLIENT_REQUEST_ID)["state"] == STATE_AUTHORIZED


def test_direct_sql_rejects_denial_once_issuing(tmp_path):
    """issuing -> denied is illegal: the decision is already made."""
    store, (_, request, _), token = _reserved(tmp_path)
    store.begin_issuance(request, token, now=NOW)
    with sqlite3.connect(store.db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE request_reservations SET state='denied', "
                "issuing_at=NULL, denied_at='z' WHERE client_request_id = ?",
                (CLIENT_REQUEST_ID,),
            )


def test_direct_sql_rejects_malformed_row_shapes(tmp_path):
    store, (_, request, _), _ = _reserved(tmp_path)
    shapes = (
        ("req-shape1", STATE_AUTHORIZED, None, "t", "t", None),
        ("req-shape2", STATE_RESERVED, "cap-nope", None, None, None),
        ("req-shape3", STATE_ISSUING, "cap-nope", "t", None, None),
        ("req-shape4", STATE_DENIED, None, "t", None, "t"),
    )
    with sqlite3.connect(store.db_path) as conn:
        for name, state, capability, issuing_at, bound_at, denied_at in shapes:
            with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
                conn.execute(
                    "INSERT INTO request_reservations ("
                    "client_request_id, reservation_attempt_digest, "
                    "request_digest, broker_connection_id, task_id, state, "
                    "reserved_at, capability_id, issuing_at, bound_at, denied_at"
                    ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (name, OTHER_DIGEST, OTHER_DIGEST, BROKER_CONNECTION_ID,
                     TASK_ID, state, "t", capability, issuing_at, bound_at,
                     denied_at),
                )


def test_direct_sql_rejects_identity_mutation_and_deletion(tmp_path):
    store, (_, request, _), _ = _reserved(tmp_path)
    with sqlite3.connect(store.db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE request_reservations SET request_digest = ? "
                "WHERE client_request_id = ?",
                (OTHER_DIGEST, CLIENT_REQUEST_ID),
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE request_reservations SET broker_connection_id = 'x' "
                "WHERE client_request_id = ?",
                (CLIENT_REQUEST_ID,),
            )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "DELETE FROM request_reservations WHERE client_request_id = ?",
                (CLIENT_REQUEST_ID,),
            )


def test_direct_sql_rejects_rebinding_a_bound_capability(tmp_path):
    store, (_, request, _), token = _reserved(tmp_path)
    store.begin_issuance(request, token, now=NOW)
    store.bind(CLIENT_REQUEST_ID, token, "cap-first", now=NOW)
    with sqlite3.connect(store.db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE request_reservations SET capability_id = 'cap-second' "
                "WHERE client_request_id = ?",
                (CLIENT_REQUEST_ID,),
            )


# --- 14. Expiry does not release ----------------------------------------------


def test_capability_expiry_does_not_release_the_reservation(tmp_path):
    """Otherwise expiry becomes a reuse channel a caller can wait out."""
    store, (_, request, _), token = _reserved(tmp_path)
    store.begin_issuance(request, token, now=NOW)
    store.bind(CLIENT_REQUEST_ID, token, "cap-expiring", now=NOW)

    long_after = NOW + timedelta(days=365)
    retry = store.reserve(request, now=long_after)

    assert not retry.created
    assert retry.state == STATE_AUTHORIZED
    assert retry.capability_id == "cap-expiring"
    assert not retry.attempt_token


# --- 15. Privacy and token secrecy --------------------------------------------


def test_projection_is_privacy_safe_and_never_leaks_the_raw_token(tmp_path):
    store, (_, request, _), token = _reserved(tmp_path)
    projection = store.projection(CLIENT_REQUEST_ID)

    assert_persistent_privacy_safe(
        projection, artifact_name="reservation projection"
    )
    serialized = json.dumps(projection)
    assert token not in serialized
    # The verifier is withheld too, so nobody mistakes it for a token.
    assert token_digest(token) not in serialized


def test_the_raw_token_is_absent_from_the_database_while_the_digest_is_present(
    tmp_path,
):
    store, (_, request, _), token = _reserved(tmp_path)

    with open(store.db_path, "rb") as handle:
        raw_bytes = handle.read()
    assert token.encode("utf-8") not in raw_bytes

    with sqlite3.connect(store.db_path) as conn:
        stored = conn.execute(
            "SELECT reservation_attempt_digest FROM request_reservations "
            "WHERE client_request_id = ?",
            (CLIENT_REQUEST_ID,),
        ).fetchone()[0]
    assert stored == token_digest(token)
    assert stored == "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def test_failure_payloads_never_carry_the_token(tmp_path):
    store, (_, request, _), token = _reserved(tmp_path)
    wrong = token[:-1] + ("0" if token[-1] != "0" else "1")
    result = store.begin_issuance(request, wrong, now=NOW)
    text = json.dumps(
        [result.reason_code, result.client_request_id, result.state,
         result.capability_id]
    )
    assert token not in text and wrong not in text


def test_every_reason_code_is_in_the_closed_vocabulary(tmp_path):
    store, (_, request, _), token = _reserved(tmp_path)
    _, absent, _ = _trio(client_request_id="req-absent")
    emitted = [
        store.reserve(request, now=LATER).reason_code,
        store.begin_issuance(request, "wrong", now=NOW).reason_code,
        store.begin_issuance(absent, token, now=NOW).reason_code,
        store.bind(CLIENT_REQUEST_ID, token, "cap-x", now=NOW).reason_code,
    ]
    for code in emitted:
        assert code in REASON_CODES


# --- 16. Transition race ------------------------------------------------------


def _run_threads(tmp_path, operations, timeout=30.0):
    """Barrier-synchronised workers over independent stores.

    A worker that dies must make the test fail rather than quietly shrink the
    result set: an outcome assertion like "exactly one winner" would otherwise
    pass on a truncated list. Every worker's exception is captured, the join is
    bounded, and the result count is asserted against the worker count.
    """
    barrier = threading.Barrier(len(operations))
    results = []
    errors = []
    lock = threading.Lock()

    def worker(operation):
        try:
            store = RequestReservationStore(default_db_path(str(tmp_path)))
            barrier.wait(timeout=timeout)
            outcome = operation(store)
            with lock:
                results.append(outcome)
        except BaseException as exc:  # noqa: BLE001 - must not vanish
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(op,)) for op in operations]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=timeout)

    assert not [t for t in threads if t.is_alive()], "a worker never finished"
    assert not errors, f"worker exceptions: {errors!r}"
    assert len(results) == len(operations), (
        f"expected {len(operations)} results, got {len(results)}"
    )
    return results


def _race(tmp_path, operations):
    return _run_threads(tmp_path, operations)


def test_begin_issuance_races_itself_and_exactly_one_wins(tmp_path):
    _, (_, request, _), token = _reserved(tmp_path)
    results = _race(
        tmp_path,
        [lambda s: s.begin_issuance(request, token, now=NOW)] * 6,
    )
    assert sum(1 for r in results if r.applied) == 1
    assert all(
        r.reason_code == RESERVATION_ALREADY_ISSUING
        for r in results
        if not r.applied
    )


def test_begin_issuance_races_deny_and_exactly_one_transition_applies(tmp_path):
    _, (_, request, _), token = _reserved(tmp_path)
    results = _race(
        tmp_path,
        [
            lambda s: s.begin_issuance(request, token, now=NOW),
            lambda s: s.deny(CLIENT_REQUEST_ID, token, now=NOW),
        ],
    )
    assert sum(1 for r in results if r.applied) == 1
    final = RequestReservationStore(
        default_db_path(str(tmp_path))
    ).projection(CLIENT_REQUEST_ID)
    assert final["state"] in {STATE_ISSUING, STATE_DENIED}


def test_two_binds_race_from_issuing_and_exactly_one_capability_binds(tmp_path):
    store, (_, request, _), token = _reserved(tmp_path)
    store.begin_issuance(request, token, now=NOW)

    results = _race(
        tmp_path,
        [
            lambda s: s.bind(CLIENT_REQUEST_ID, token, "cap-A", now=NOW),
            lambda s: s.bind(CLIENT_REQUEST_ID, token, "cap-B", now=NOW),
        ],
    )
    assert sum(1 for r in results if r.applied) == 1
    bound = store.projection(CLIENT_REQUEST_ID)["capability_id"]
    assert bound in {"cap-A", "cap-B"}

    with sqlite3.connect(store.db_path) as conn:
        rows = conn.execute(
            "SELECT COUNT(*) FROM request_reservations WHERE capability_id IS NOT NULL"
        ).fetchone()[0]
    assert rows == 1


# --- Mediated boundaries ------------------------------------------------------


class _FakeAuthzRequest:
    def __init__(self, mapped, task_id, decision_id):
        self.task_id = task_id
        self.decision_id = decision_id
        self.artifact_byte_digest = mapped["artifact_byte_digest"]
        self.scope_digest = mapped["scope_digest"]
        self.plan_body_digest = mapped["plan_body_digest"]


class _FakeReceipt:
    def __init__(self, mapped, task_id=TASK_ID, decision_id=DECISION_ID):
        self.request = _FakeAuthzRequest(mapped, task_id, decision_id)


def test_mediated_issuance_gates_then_issues_then_binds(tmp_path):
    store, (effect, request, linkage), token = _reserved(tmp_path)
    mapped = capability_binding_fields(effect, request, linkage)
    calls = []

    def fake_issue(ledger, receipt, **kwargs):
        # The gate must already have been won before issuance is reached.
        assert store.projection(CLIENT_REQUEST_ID)["state"] == STATE_ISSUING
        calls.append("issued")
        return "cap-mediated"

    result = mediated_issue_capability(
        store, object(), _FakeReceipt(mapped), effect, request, linkage, token,
        issue_capability=fake_issue, now=NOW,
    )

    assert result.applied and calls == ["issued"]
    assert store.projection(CLIENT_REQUEST_ID)["capability_id"] == "cap-mediated"


def test_mediated_issuance_rejects_a_receipt_for_a_different_operation(tmp_path):
    store, (effect, request, linkage), token = _reserved(tmp_path)
    mapped = capability_binding_fields(effect, request, linkage)
    wrong = _FakeReceipt(mapped, task_id="8f14e45f-ceea-4e78-b3f4-1a2b3c4d5e6f")

    result = mediated_issue_capability(
        store, object(), wrong, effect, request, linkage, token,
        issue_capability=lambda *a, **k: pytest.fail("must not issue"),
        now=NOW,
    )

    assert not result.applied
    assert result.reason_code == RESERVATION_BINDING_MISMATCH
    assert store.projection(CLIENT_REQUEST_ID)["state"] == STATE_RESERVED


def test_issuance_failure_leaves_the_row_permanently_issuing(tmp_path):
    store, (effect, request, linkage), token = _reserved(tmp_path)
    mapped = capability_binding_fields(effect, request, linkage)

    def exploding_issue(ledger, receipt, **kwargs):
        raise RuntimeError("ledger append failed")

    with pytest.raises(RuntimeError):
        mediated_issue_capability(
            store, object(), _FakeReceipt(mapped), effect, request, linkage,
            token, issue_capability=exploding_issue, now=NOW,
        )

    assert store.projection(CLIENT_REQUEST_ID)["state"] == STATE_ISSUING
    # It never returns to reserved, permits denial, or authorizes a second issue.
    assert not store.deny(CLIENT_REQUEST_ID, token, now=LATER).applied
    assert not store.begin_issuance(request, token, now=LATER).applied


def test_mediated_claim_requires_an_authorized_reservation(tmp_path):
    store, (effect, request, linkage), token = _reserved(tmp_path)
    denied = mediated_claim_capability(
        store, object(), "cap-1", effect, request, linkage,
        claim_capability=lambda *a, **k: pytest.fail("must not delegate"),
        claimant_id="agent-a", now=NOW,
    )
    assert not denied.applied
    assert denied.reason_code == RESERVATION_ISSUANCE_NOT_BEGUN

    store.begin_issuance(request, token, now=NOW)
    store.bind(CLIENT_REQUEST_ID, token, "cap-1", now=NOW)

    delegated = []
    mediated_claim_capability(
        store, object(), "cap-1", effect, request, linkage,
        claim_capability=lambda *a, **k: delegated.append(a) or "claimed",
        claimant_id="agent-a", now=NOW,
    )
    assert len(delegated) == 1


def test_mediated_claim_refuses_a_capability_bound_to_another_request(tmp_path):
    store, (effect, request, linkage), token = _reserved(tmp_path)
    store.begin_issuance(request, token, now=NOW)
    store.bind(CLIENT_REQUEST_ID, token, "cap-real", now=NOW)

    result = mediated_claim_capability(
        store, object(), "cap-someone-else", effect, request, linkage,
        claim_capability=lambda *a, **k: pytest.fail("must not delegate"),
        claimant_id="agent-a", now=NOW,
    )
    assert not result.applied


# --- Control ------------------------------------------------------------------


def test_schema_version_is_recorded(tmp_path):
    """Behavioural control.

    This passes against the intended module and against most mutations of it,
    so it is a control rather than mutant evidence and is reported as such.
    """
    store, (_, request, _), _ = _reserved(tmp_path)
    with sqlite3.connect(store.db_path) as conn:
        recorded = conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        ).fetchone()[0]
    assert recorded == SCHEMA_VERSION

# --- Review round: reservation must be bound to the trio ----------------------


def test_the_gate_refuses_a_coherent_but_different_request(tmp_path):
    """A valid token for A must not advance A on behalf of request B.

    Both are internally coherent and share the client request id. Before the
    request was bound into the gate predicate, this issued a capability for B
    and bound it into A's reservation.
    """
    store, (_, request_a, _), token_a = _reserved(tmp_path)

    effect_b = _effect(
        proposed_bytes=b"totally different content\n",
        broker_connection_id="conn-ATTACKER",
    )
    request_b = build_client_request(effect_b, task_id=TASK_ID)
    linkage_b = build_plan_linkage(effect_b, request_b, decision_id=DECISION_ID)
    mapped_b = capability_binding_fields(effect_b, request_b, linkage_b)
    assert request_b.client_request_id == request_a.client_request_id

    issued = []
    result = mediated_issue_capability(
        store, object(), _FakeReceipt(mapped_b), effect_b, request_b, linkage_b,
        token_a,
        issue_capability=lambda *a, **k: issued.append("B") or "cap-for-B",
        now=NOW,
    )

    assert issued == [], "issue_capability must never be reached"
    assert not result.applied
    assert result.reason_code == REQUEST_ID_REUSE_MISMATCH
    row = store.projection(CLIENT_REQUEST_ID)
    assert row["state"] == STATE_RESERVED and row["capability_id"] == ""


def test_the_gate_refuses_a_different_connection_with_a_valid_token(tmp_path):
    store, (_, request_a, _), token = _reserved(tmp_path)
    _, other_connection, _ = _trio(broker_connection_id="conn-elsewhere")

    result = store.begin_issuance(other_connection, token, now=NOW)

    assert not result.applied
    assert result.reason_code == REQUEST_ID_REUSE_MISMATCH
    assert store.projection(CLIENT_REQUEST_ID)["state"] == STATE_RESERVED


# --- Review round: mediated claim preserves operational reasons ---------------


@pytest.mark.parametrize("breakage", ["corrupt", "unsupported"])
def test_mediated_claim_preserves_operational_reasons(tmp_path, breakage):
    store, (effect, request, linkage), token = _reserved(tmp_path)
    store.begin_issuance(request, token, now=NOW)
    store.bind(CLIENT_REQUEST_ID, token, "cap-1", now=NOW)

    if breakage == "corrupt":
        with open(store.db_path, "wb") as handle:
            handle.write(b"not a sqlite database" * 40)
    else:
        with sqlite3.connect(store.db_path) as conn:
            conn.execute(
                "UPDATE schema_meta SET value = ? WHERE key = 'schema_version'",
                ("triagecore.request_reservation.v999",),
            )

    result = mediated_claim_capability(
        RequestReservationStore(store.db_path), object(), "cap-1",
        effect, request, linkage,
        claim_capability=lambda *a, **k: pytest.fail("must not delegate"),
        claimant_id="agent-a", now=NOW,
    )

    assert result.reason_code == RESERVATION_STORE_UNAVAILABLE
    assert result.reason_code != RESERVATION_NOT_FOUND


def test_mediated_claim_reports_busy_for_a_locked_store(tmp_path):
    store, (effect, request, linkage), token = _reserved(
        tmp_path, busy_timeout_ms=1
    )
    store.begin_issuance(request, token, now=NOW)
    store.bind(CLIENT_REQUEST_ID, token, "cap-1", now=NOW)

    blocker = sqlite3.connect(store.db_path, isolation_level=None)
    try:
        blocker.execute("BEGIN EXCLUSIVE")
        result = mediated_claim_capability(
            RequestReservationStore(store.db_path, busy_timeout_ms=1),
            object(), "cap-1", effect, request, linkage,
            claim_capability=lambda *a, **k: pytest.fail("must not delegate"),
            claimant_id="agent-a", now=NOW,
        )
    finally:
        blocker.execute("ROLLBACK")
        blocker.close()

    # A lock is a lock. Accepting "unavailable" here would not prove the busy
    # classifier survives through the mediated boundary.
    assert result.reason_code == RESERVATION_STORE_BUSY


def test_projection_raises_rather_than_reporting_absence(tmp_path):
    store, _, _ = _reserved(tmp_path)
    with open(store.db_path, "wb") as handle:
        handle.write(b"not a sqlite database" * 40)
    with pytest.raises(ReservationError):
        RequestReservationStore(store.db_path).projection(CLIENT_REQUEST_ID)


# --- Review round: operation x state truth table ------------------------------


def _row_in_state(tmp_path, state, capability="cap-bound"):
    store, (_, request, _), token = _reserved(tmp_path)
    if state == STATE_ISSUING:
        store.begin_issuance(request, token, now=NOW)
    elif state == STATE_AUTHORIZED:
        store.begin_issuance(request, token, now=NOW)
        store.bind(CLIENT_REQUEST_ID, token, capability, now=NOW)
    elif state == STATE_DENIED:
        store.deny(CLIENT_REQUEST_ID, token, now=NOW)
    return store, request, token


@pytest.mark.parametrize(
    "state, operation, expected",
    [
        (STATE_RESERVED, "begin_issuance", RESERVE_OK),
        (STATE_RESERVED, "deny", RESERVE_OK),
        (STATE_RESERVED, "bind", RESERVATION_ISSUANCE_NOT_BEGUN),
        (STATE_ISSUING, "begin_issuance", RESERVATION_ALREADY_ISSUING),
        (STATE_ISSUING, "deny", RESERVATION_ALREADY_ISSUING),
        (STATE_ISSUING, "bind", RESERVE_OK),
        (STATE_AUTHORIZED, "begin_issuance", RESERVATION_ALREADY_BOUND),
        (STATE_AUTHORIZED, "deny", RESERVATION_ALREADY_BOUND),
        (STATE_AUTHORIZED, "bind_other", RESERVATION_ALREADY_BOUND),
        (STATE_AUTHORIZED, "bind_same", RESERVE_OK),
        (STATE_DENIED, "begin_issuance", RESERVATION_DENIED),
        (STATE_DENIED, "deny", RESERVATION_DENIED),
        (STATE_DENIED, "bind", RESERVATION_DENIED),
    ],
)
def test_every_operation_state_pair_reports_truthfully(
    tmp_path, state, operation, expected
):
    """No generic wrong-state code: each reachable pair names what happened."""
    store, request, token = _row_in_state(tmp_path, state)

    if operation == "begin_issuance":
        result = store.begin_issuance(request, token, now=LATER)
    elif operation == "deny":
        result = store.deny(CLIENT_REQUEST_ID, token, now=LATER)
    elif operation == "bind_same":
        result = store.bind(CLIENT_REQUEST_ID, token, "cap-bound", now=LATER)
    elif operation == "bind_other":
        result = store.bind(CLIENT_REQUEST_ID, token, "cap-different", now=LATER)
    else:
        result = store.bind(CLIENT_REQUEST_ID, token, "cap-x", now=LATER)

    assert result.reason_code == expected
    assert result.applied == (expected == RESERVE_OK)


# --- Review round: the persisted row itself passes the invariant --------------


def test_the_persisted_row_passes_the_persistent_privacy_invariant(tmp_path):
    """Obligation 15 covers the stored record, not only its projection."""
    store, _, token = _reserved(tmp_path)
    with sqlite3.connect(store.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM request_reservations WHERE client_request_id = ?",
            (CLIENT_REQUEST_ID,),
        ).fetchone()

    stored = {key: row[key] for key in row.keys()}
    assert set(stored) >= {
        "client_request_id", "reservation_attempt_digest", "request_digest",
        "broker_connection_id", "task_id", "capability_id", "state",
        "reserved_at", "issuing_at", "bound_at", "denied_at",
    }
    assert_persistent_privacy_safe(
        stored, artifact_name="request reservation row"
    )
    assert token not in json.dumps(stored)
    assert stored["reservation_attempt_digest"] == token_digest(token)

def test_an_incompatible_insert_trigger_reports_unavailable_not_unbound(tmp_path):
    """A same-version database that refuses the insert is not a lost race.

    Reporting `reservation_unbound` would assert that a valid reservation
    exists and merely lacks this caller's ownership -- a claim never observed.
    """
    store = _store(tmp_path)
    _, seed, _ = _trio(client_request_id="req-seed")
    store.reserve(seed, now=NOW)  # materialise the schema at this version

    with sqlite3.connect(store.db_path) as conn:
        conn.execute(
            "CREATE TRIGGER hostile_insert BEFORE INSERT ON request_reservations "
            "FOR EACH ROW BEGIN SELECT RAISE(ABORT, 'incompatible trigger'); END"
        )

    _, request, _ = _trio()
    result = RequestReservationStore(store.db_path).reserve(request, now=NOW)

    assert result.reason_code == RESERVATION_STORE_UNAVAILABLE
    assert result.reason_code != RESERVATION_UNBOUND
    assert not result.created and not result.attempt_token


def test_a_genuine_insert_conflict_still_classifies_the_existing_row(tmp_path):
    """The narrowed handler must not lose the real duplicate-insert case."""
    store, (_, request, _), _ = _reserved(tmp_path)
    again = store.reserve(request, now=LATER)
    assert again.reason_code == RESERVATION_UNBOUND
    assert again.state == STATE_RESERVED
