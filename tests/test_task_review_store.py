import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from threading import Barrier

import pytest
from test_task_review_receipt import (
    BINDING,
    NOW,
    assertion,
    enroll_reviewer,
    make_reviewer,
)

from triage_core.authz import CredentialStore
from triage_core.task_review_receipt import (
    ReviewerPolicy,
    ReviewProofError,
    ReviewReceipt,
    ReviewRequest,
)
from triage_core.task_review_store import ReviewStore, ReviewStoreError


@pytest.fixture
def setup_store(tmp_path):
    key, policy = make_reviewer(tmp_path)
    private = tmp_path / "review-state"
    private.mkdir(mode=0o700)
    current_time = [NOW]

    def open_store():
        return ReviewStore(
            private, BINDING.scope_id, lambda: policy, clock=lambda: current_time[0]
        )

    store = open_store()
    store.initialize()
    store.register_evidence(BINDING, expected_revision=None)
    return store, key, policy, current_time, open_store


def confirm(store, key, decision="accepted", binding=BINDING):
    request = store.prepare(binding, decision, "reviewer-a")
    return ReviewReceipt.from_assertion(request, assertion(key, request))


def test_historical_proof_survives_challenge_expiry_and_reopen(setup_store):
    store, key, _, clock, reopen = setup_store
    receipt = confirm(store, key)
    assert store.get_current(BINDING.task_id) is None
    assert store.get_history(receipt.request.event_id) is None

    committed = store.admit(receipt)
    assert committed.receipt == receipt
    assert committed.admitted_at == NOW
    clock[0] += timedelta(days=1)
    assert reopen().get_current(BINDING.task_id) == committed
    assert reopen().admit(receipt) == committed
    assert reopen().get_history(receipt.request.event_id) == committed


def test_expiry_and_unissued_receipts_cannot_advance_state(setup_store):
    store, key, _, clock, _ = setup_store
    receipt = confirm(store, key)
    unknown = ReviewRequest.create(BINDING, "rejected", "reviewer-a", None, NOW)
    with pytest.raises(ReviewStoreError, match="review_challenge_missing"):
        store.admit(ReviewReceipt.from_assertion(unknown, assertion(key, unknown)))

    clock[0] += timedelta(minutes=5)
    with pytest.raises(ReviewProofError, match="challenge_not_current"):
        store.admit(receipt)
    assert store.get_current(BINDING.task_id) is None
    assert store.get_history(receipt.request.event_id) is None


def test_pending_receipt_is_bound_to_persisted_request(setup_store):
    store, key, *_ = setup_store
    receipt = confirm(store, key)
    new_request = replace(receipt.request, decision="rejected")
    altered = ReviewReceipt.from_assertion(new_request, assertion(key, new_request))
    with pytest.raises(ReviewStoreError, match="review_request_mismatch"):
        store.admit(altered)
    assert store.get_current(BINDING.task_id) is None
    assert store.admit(receipt).receipt == receipt
    with pytest.raises(ReviewStoreError, match="review_event_conflict"):
        store.admit(altered)


def test_concurrent_confirmations_commit_only_one_successor(setup_store):
    store, key, _, _, reopen = setup_store
    first = confirm(store, key)
    second = confirm(store, key, "needs_revision")
    barrier = Barrier(2)

    def admit(receipt):
        local = reopen()
        barrier.wait(timeout=10)
        try:
            return local.admit(receipt).receipt.request.event_id
        except ReviewStoreError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(admit, [first, second]))
    current = store.get_current(BINDING.task_id)
    assert current is not None
    assert sorted(results) == sorted(
        ["review_predecessor_changed", current.receipt.request.event_id]
    )
    next_receipt = confirm(store, key, "rejected")
    assert next_receipt.request.predecessor_id == current.receipt.request.event_id
    assert store.admit(next_receipt).receipt == next_receipt


def test_changed_evidence_preserves_history_and_requires_fresh_review(setup_store):
    store, key, *_ = setup_store
    old = store.admit(confirm(store, key))
    pending = confirm(store, key)
    changed = replace(BINDING, revision="revision-2", digest="sha256:" + "b" * 64)
    store.register_evidence(changed, expected_revision=BINDING.revision)
    assert store.get_current(BINDING.task_id) is None
    assert store.get_history(old.receipt.request.event_id) == old
    with pytest.raises(ReviewStoreError, match="review_evidence_changed"):
        store.admit(pending)
    with pytest.raises(ReviewStoreError, match="review_evidence_changed"):
        store.prepare(BINDING, "accepted", "reviewer-a")
    with pytest.raises(ReviewStoreError, match="review_evidence_revision_reused"):
        store.register_evidence(BINDING, expected_revision=changed.revision)

    new = store.admit(confirm(store, key, "rejected", changed))
    assert store.get_current(BINDING.task_id) == new


def test_grant_loss_preserves_receipt_without_resurrecting_predecessor(setup_store):
    store, key, policy, _, _ = setup_store
    first = store.admit(confirm(store, key))
    second_id = b"synthetic-second-reviewer"
    second_key, credential = enroll_reviewer(
        policy.credentials, "reviewer-b", second_id
    )
    all_grants = replace(
        policy, grants={**policy.grants, "reviewer-b": {credential.credential_id}}
    )
    second_store = ReviewStore(
        store.path.parent, BINDING.scope_id, lambda: all_grants, clock=lambda: NOW
    )
    request = second_store.prepare(BINDING, "rejected", "reviewer-b")
    proof = assertion(second_key, request, credential_id=second_id)
    head = second_store.admit(ReviewReceipt.from_assertion(request, proof))
    policy.credentials.revoke(head.receipt.credential_id, now=NOW)
    with pytest.raises(ReviewProofError, match="credential_revoked"):
        second_store.get_current(BINDING.task_id)
    assert store.get_history(first.receipt.request.event_id) == first
    assert store.get_history(head.receipt.request.event_id) == head


def test_database_scope_and_evidence_scope_must_match(setup_store):
    store, key, policy, *_ = setup_store
    other = replace(BINDING, scope_id="workspace-b")
    with pytest.raises(ReviewStoreError, match="review_scope_mismatch"):
        store.register_evidence(other, expected_revision=None)
    with pytest.raises(ReviewStoreError, match="review_scope_mismatch"):
        store.prepare(other, "rejected", "reviewer-a")
    stranger = ReviewStore(store.path.parent, other.scope_id, lambda: policy)
    with pytest.raises(ReviewStoreError, match="review_scope_mismatch"):
        stranger.get_current(BINDING.task_id)
    assert store.admit(confirm(store, key)).receipt.request.evidence == BINDING


def test_failed_sqlite_write_rolls_back_receipt_head_and_challenge(setup_store):
    store, key, *_ = setup_store
    receipt = confirm(store, key)
    with sqlite3.connect(store.path) as db:
        db.execute(
            "CREATE TRIGGER test_abort_head BEFORE INSERT ON review_head "
            "BEGIN SELECT RAISE(ABORT, 'synthetic storage failure'); END"
        )

    with pytest.raises(ReviewStoreError, match="review_store_unavailable"):
        store.admit(receipt)
    assert store.get_current(BINDING.task_id) is None
    assert store.get_history(receipt.request.event_id) is None
    with sqlite3.connect(store.path) as db:
        db.execute("DROP TRIGGER test_abort_head")
    assert store.admit(receipt).receipt == receipt


@pytest.fixture
def empty_store(tmp_path):
    private = tmp_path / "inaccessible"
    private.mkdir(mode=0o700)
    policy = ReviewerPolicy(BINDING.scope_id, {}, CredentialStore(str(tmp_path)))
    return ReviewStore(private, BINDING.scope_id, lambda: policy)


def test_unavailable_store_is_distinct_from_no_review(empty_store):
    store = empty_store
    with pytest.raises(ReviewStoreError, match="review_store_unavailable"):
        store.get_current(BINDING.task_id)
    store.path.mkdir()
    with pytest.raises(ReviewStoreError, match="review_store_unavailable"):
        store.initialize()


def test_busy_database_is_distinct_from_no_review(setup_store):
    store, key, *_ = setup_store
    receipt = confirm(store, key)
    db = sqlite3.connect(store.path)
    try:
        db.execute("BEGIN IMMEDIATE")
        with pytest.raises(ReviewStoreError, match="review_store_busy"):
            store.admit(receipt)
    finally:
        db.close()
    assert store.admit(receipt).receipt == receipt


def test_busy_status_without_sqlite_error_code(empty_store, monkeypatch):
    store = empty_store
    store.initialize()

    def legacy_busy(*args, **kwargs):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(sqlite3, "connect", legacy_busy)
    with pytest.raises(ReviewStoreError, match="review_store_busy"):
        store.get_current(BINDING.task_id)


def _install_v1_store(store):
    with sqlite3.connect(store.path) as db:
        db.executescript(
            """CREATE TABLE review_scope (
                singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
                scope_id TEXT NOT NULL
            );
            CREATE TABLE review_evidence (
                task_id TEXT NOT NULL, revision TEXT NOT NULL, digest TEXT NOT NULL,
                active INTEGER NOT NULL CHECK (active IN (0, 1)),
                PRIMARY KEY (task_id, revision)
            );
            CREATE UNIQUE INDEX review_one_current_evidence
                ON review_evidence(task_id) WHERE active = 1;
            CREATE TABLE review_challenge (
                event_id TEXT PRIMARY KEY, expires_at TEXT NOT NULL, request BLOB NOT NULL
            );
            CREATE TABLE review_commit (
                event_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, receipt BLOB NOT NULL,
                admitted_at TEXT NOT NULL, UNIQUE (task_id, event_id)
            );
            CREATE TABLE review_head (
                task_id TEXT PRIMARY KEY, event_id TEXT NOT NULL,
                FOREIGN KEY (task_id, event_id) REFERENCES review_commit(task_id, event_id)
            );
            PRAGMA user_version = 1;"""
        )
        db.execute("INSERT INTO review_scope VALUES (1, ?)", (BINDING.scope_id,))


@pytest.fixture
def v1_store(tmp_path):
    key, policy = make_reviewer(tmp_path)
    private = tmp_path / "v1-review-state"
    private.mkdir(mode=0o700)

    def reopen(scope_id=BINDING.scope_id):
        return ReviewStore(private, scope_id, lambda: policy, clock=lambda: NOW)

    store = reopen()
    _install_v1_store(store)
    store.register_evidence(BINDING, expected_revision=None)
    return store, key, reopen


def test_explicit_migration_preserves_v1_scope_receipts_and_pending_challenges(
    v1_store,
):
    store, key, reopen = v1_store
    previous = store.admit(confirm(store, key))
    old_challenge = confirm(store, key, "rejected")
    store.initialize()
    assert store.get_current(BINDING.task_id) == previous
    with pytest.raises(ReviewStoreError, match="review_store_migration_required"):
        store.request_intent(BINDING.task_id, "mobile-01", "accepted")
    with pytest.raises(ReviewStoreError, match="review_scope_mismatch"):
        reopen("other-scope").migrate()
    with sqlite3.connect(store.path) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (1,)

    store.migrate()
    reopened = reopen()
    reopened.migrate()
    assert reopened.get_current(BINDING.task_id) == previous
    assert reopened.current_evidence(BINDING.task_id) == BINDING
    committed = reopened.admit(old_challenge)
    assert reopened.list_history(BINDING.task_id) == (previous, committed)
    assert (
        reopened.request_intent(BINDING.task_id, "mobile-01", "accepted").status
        == "pending"
    )


def test_failed_migration_rolls_back_schema_and_keeps_the_original_review(
    v1_store, monkeypatch
):
    store, key, reopen = v1_store
    previous = store.admit(confirm(store, key))
    connect = sqlite3.connect
    attempted_tables = []

    def connect_with_migration_failure(*args, **kwargs):
        db = connect(*args, **kwargs)

        def authorize(action, name, table, *_):
            if action in (sqlite3.SQLITE_CREATE_TABLE, sqlite3.SQLITE_ALTER_TABLE):
                attempted_tables.append(
                    name if action == sqlite3.SQLITE_CREATE_TABLE else table
                )
                if len(attempted_tables) == 2:
                    return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        db.set_authorizer(authorize)
        return db

    with monkeypatch.context() as migration:
        migration.setattr(sqlite3, "connect", connect_with_migration_failure)
        with pytest.raises(ReviewStoreError, match="review_store_unavailable"):
            store.migrate()
    assert len(attempted_tables) == 2
    with connect(store.path) as db:
        assert db.execute("PRAGMA user_version").fetchone() == (1,)
        assert (
            db.execute(
                "SELECT name FROM sqlite_master WHERE name = ?", attempted_tables[:1]
            ).fetchall()
            == []
        )
    assert reopen().get_current(BINDING.task_id) == previous
    store.migrate()
    assert reopen().get_history(previous.receipt.request.event_id) == previous


def test_request_retries_preserve_original_expiry_and_reject_payload_conflicts(
    setup_store,
):
    store, _, _, clock, reopen = setup_store
    intent = store.request_intent(BINDING.task_id, "mobile-01", "accepted", "low")
    assert intent.intent_id != "mobile-01"
    assert (intent.task_id, intent.decision, intent.workload, intent.status) == (
        BINDING.task_id,
        "accepted",
        "low",
        "pending",
    )
    clock[0] += timedelta(hours=23)
    assert (
        reopen().request_intent(BINDING.task_id, "mobile-01", "accepted", "low")
        == intent
    )
    assert reopen().list_pending_intents(BINDING.task_id) == (intent,)
    for task_id, decision, workload in (
        (BINDING.task_id, "rejected", "low"),
        (BINDING.task_id, "accepted", None),
        ("other-task", "accepted", "low"),
    ):
        with pytest.raises(ReviewStoreError, match="review_intent_conflict"):
            store.request_intent(task_id, "mobile-01", decision, workload)
    clock[0] += timedelta(hours=1)
    expired = reopen().get_intent(intent.intent_id)
    assert expired is not None and expired.status == "expired"
    assert (
        reopen().request_intent(BINDING.task_id, "mobile-01", "accepted", "low")
        == expired
    )
    assert reopen().list_pending_intents(BINDING.task_id) == ()
    assert store.get_current(BINDING.task_id) is None


@pytest.mark.parametrize(
    ("request_id", "decision", "workload"),
    [
        (" mobile-01", "accepted", None),
        ("mobile-01", "unknown", None),
        ("mobile-01", "accepted", "unrecognized"),
        ("mobile-01", "accepted", []),
    ],
)
def test_request_validates_ids_decisions_and_workload(
    setup_store, request_id, decision, workload
):
    store, *_ = setup_store
    with pytest.raises(ValueError):
        store.request_intent(BINDING.task_id, request_id, decision, workload)
    assert store.list_pending_intents(BINDING.task_id) == ()


def _confirm_intent(store, key, intent):
    request = store.prepare(
        BINDING, intent.decision, "reviewer-a", intent_id=intent.intent_id
    )
    return ReviewReceipt.from_assertion(request, assertion(key, request))


def test_confirmation_must_match_intent_task_and_decision(setup_store):
    store, *_ = setup_store
    rejected = store.request_intent(BINDING.task_id, "mobile-01", "rejected")
    other_task = store.request_intent("other-task", "mobile-02", "accepted")
    for intent in (rejected, other_task):
        with pytest.raises(ReviewStoreError, match="review_intent_mismatch"):
            store.prepare(BINDING, "accepted", "reviewer-a", intent_id=intent.intent_id)
    assert store.get_current(BINDING.task_id) is None


@pytest.mark.parametrize("terminal_status", ["cancelled", "expired"])
def test_intent_cancellation_or_expiry_after_prepare_preserves_actionable_task(
    setup_store, terminal_status
):
    store, key, _, clock, reopen = setup_store
    intent = store.request_intent(BINDING.task_id, "mobile-01", "accepted")
    clock[0] += timedelta(days=1, minutes=-1)
    receipt = _confirm_intent(store, key, intent)
    if terminal_status == "cancelled":
        store.cancel_intent(intent.intent_id)
    else:
        clock[0] += timedelta(minutes=1)

    with pytest.raises(ReviewStoreError, match=f"review_intent_{terminal_status}"):
        reopen().admit(receipt)
    with pytest.raises(ReviewStoreError, match=f"review_intent_{terminal_status}"):
        _confirm_intent(reopen(), key, intent)
    assert reopen().get_intent(intent.intent_id).status == terminal_status
    assert reopen().list_pending_intents(BINDING.task_id) == ()
    assert store.get_current(BINDING.task_id) is None
    assert store.list_history(BINDING.task_id) == ()
    assert store.admit(confirm(store, key)).receipt.request.decision == "accepted"


def test_concurrent_confirmations_resolve_mobile_intent_only_once(setup_store):
    store, key, _, _, reopen = setup_store
    intent = store.request_intent(BINDING.task_id, "mobile-01", "accepted")
    other = store.request_intent(BINDING.task_id, "mobile-02", "needs_revision")
    competing = [_confirm_intent(store, key, intent) for _ in range(2)]
    barrier = Barrier(2)

    def admit(receipt):
        local = reopen()
        barrier.wait(timeout=10)
        try:
            return local.admit(receipt)
        except ReviewStoreError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(admit, competing))
    current = store.get_current(BINDING.task_id)
    assert current in results and "review_intent_committed" in results
    assert store.list_history(BINDING.task_id) == (current,)
    resolved = reopen().get_intent(intent.intent_id)
    assert resolved.status == "committed"
    assert resolved.committed_event_id == current.receipt.request.event_id
    assert reopen().admit(current.receipt) == current
    assert store.request_intent(BINDING.task_id, "mobile-01", "accepted") == resolved
    assert reopen().list_pending_intents(BINDING.task_id) == (other,)


def test_failed_intent_resolution_rolls_back_receipt_head_and_challenge(setup_store):
    store, key, *_ = setup_store
    intent = store.request_intent(BINDING.task_id, "mobile-01", "accepted")
    receipt = _confirm_intent(store, key, intent)
    with sqlite3.connect(store.path) as db:
        db.execute(
            "CREATE TRIGGER test_abort_intent BEFORE UPDATE ON review_intent "
            "BEGIN SELECT RAISE(ABORT, 'synthetic storage failure'); END"
        )

    with pytest.raises(ReviewStoreError, match="review_store_unavailable"):
        store.admit(receipt)
    assert store.get_intent(intent.intent_id) == intent
    assert store.get_current(BINDING.task_id) is None
    assert store.list_history(BINDING.task_id) == ()
    with sqlite3.connect(store.path) as db:
        db.execute("DROP TRIGGER test_abort_intent")
    assert store.admit(receipt).receipt == receipt
    assert store.get_intent(intent.intent_id).status == "committed"


def test_evidence_changed_during_final_admission_check_keeps_intent_pending(
    setup_store,
):
    store, key, *_ = setup_store
    intent = store.request_intent(BINDING.task_id, "mobile-01", "accepted")
    receipt = _confirm_intent(store, key, intent)

    def reject_stale_evidence():
        raise RuntimeError("synthetic evidence change")

    with pytest.raises(RuntimeError, match="synthetic evidence change"):
        store.admit(receipt, check_current=reject_stale_evidence)
    assert store.get_intent(intent.intent_id) == intent
    assert store.get_current(BINDING.task_id) is None
    assert store.list_history(BINDING.task_id) == ()

    rechecked = []
    committed = store.admit(receipt, check_current=lambda: rechecked.append(True))
    assert rechecked == [True]
    assert (
        store.get_intent(intent.intent_id).committed_event_id
        == receipt.request.event_id
    )
    assert store.admit(receipt, check_current=reject_stale_evidence) == committed
