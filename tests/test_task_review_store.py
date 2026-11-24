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
