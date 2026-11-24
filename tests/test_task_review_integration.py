import json
import os
from datetime import datetime, timedelta, timezone

import pytest
from test_task_review_receipt import assertion, make_reviewer

from triage_core.task_ledger import TaskLedger
from triage_core.task_review_service import ReviewService, ReviewServiceError


def write_private(path, content):
    path.write_bytes(content)
    path.chmod(0o600)


@pytest.fixture
def configured_review(tmp_path, monkeypatch):
    trust = tmp_path / "private"
    scope = trust / "workspace-a"
    state = scope / "state"
    evidence = scope / "evidence"
    ledger = tmp_path / "ledger"
    for directory in (trust, scope, state, evidence, ledger):
        directory.mkdir(mode=0o700)
    key, policy = make_reviewer(scope)
    (scope / "authz").chmod(0o700)
    (scope / "authz" / "credentials.json").chmod(0o600)
    write_private(
        trust / "profiles.json",
        json.dumps(
            {
                "schema": "triagecore.task_review_profiles.v1",
                "profiles": [
                    {
                        "ledger_dir": str(ledger),
                        "scope_id": "workspace-a",
                        "reviewer_id": "reviewer-a",
                        "grants": {
                            identity: list(ids)
                            for identity, ids in policy.grants.items()
                        },
                    }
                ],
            }
        ).encode(),
    )
    manifest = scope / "evidence.json"
    write_private(
        manifest,
        json.dumps(
            {
                "schema": "triagecore.task_review_manifest.v1",
                "tasks": {
                    "task-1": {"revision": "rev-1", "items": {"draft": "draft.txt"}}
                },
            }
        ).encode(),
    )
    artifact = evidence / "draft.txt"
    write_private(artifact, b"Exact synthetic text\r\n  with indentation.\n")
    TaskLedger(str(ledger)).append_event(
        "task-1", "task_created", {"title": "Synthetic task"}
    )

    if os.name == "nt":
        # The sandbox's temporary directory ACL is inherited. These tests
        # exercise the application contract with a synthetic private root;
        # the real native directory and file checks are used on Linux.
        from contextlib import nullcontext

        from triage_core import task_review_service

        def read_fixture(root, path, limit):
            assert path.is_relative_to(root)
            with path.open("rb") as stream:
                data = stream.read(limit + 1)
            if len(data) > limit:
                raise ReviewServiceError("review_evidence_too_large")
            return data

        monkeypatch.setattr(task_review_service, "_read_private", read_fixture)
        monkeypatch.setattr(
            task_review_service, "_private_directory", lambda *args: nullcontext()
        )

    def acquire(request, credential_ids):
        assert credential_ids
        return assertion(key, request)

    service = ReviewService(ledger, root=trust, acquire_assertion=acquire)
    service.migrate()
    return service, ledger, trust, artifact, manifest


def test_mobile_only_requests_local_confirmation_and_preserves_ledger(
    configured_review,
):
    service, ledger, *_ = configured_review
    before = (ledger / "ledger.jsonl").read_bytes()
    intent = service.request_intent("task-1", "request-1", "accepted", "low")
    assert intent.status == "pending"
    assert service.project("task-1").status == "pending"
    assert service.project("task-1").binary_label is None
    assert service.pending_for_task("task-1") == (intent,)
    seen = []

    def approve(snapshot):
        seen.extend(snapshot.items)
        return True

    result = service.confirm("task-1", "accepted", approve, intent_id=intent.intent_id)
    assert seen == [("draft", "Exact synthetic text\r\n  with indentation.\n")]
    assert result.status == "verified"
    assert result.binary_label is True
    assert service.project("task-1").decision == "accepted"
    assert service.pending_for_task("task-1") == ()
    assert (
        service.request_intent("task-1", "request-1", "accepted", "low").status
        == "committed"
    )
    assert (ledger / "ledger.jsonl").read_bytes() == before


def test_readers_stop_presenting_receipt_when_trusted_evidence_changes(
    configured_review,
):
    service, _, _, artifact, _ = configured_review
    service.confirm("task-1", "rejected", lambda snapshot: True)
    write_private(artifact, b"Different draft")
    result = service.project("task-1", include_history=True)
    assert result.status == "evidence_changed"
    assert result.binary_label is None
    assert [(row.decision, row.revision) for row in result.history] == [
        ("rejected", "rev-1")
    ]

    with pytest.raises(ReviewServiceError, match="review_evidence_changed"):
        service.confirm("task-1", "accepted", lambda snapshot: True)


def test_confirmation_rechecks_evidence_before_committing(configured_review):
    service, ledger, trust, artifact, _ = configured_review

    def acquire(request, ids):
        write_private(artifact, b"Evidence changed during confirmation")
        return {}  # The evidence check must happen before parsing the assertion.

    guarded = ReviewService(ledger, root=trust, acquire_assertion=acquire)
    intent = service.request_intent("task-1", "request-2", "needs_revision")
    with pytest.raises(ReviewServiceError, match="review_evidence_changed"):
        guarded.confirm(
            "task-1",
            "needs_revision",
            lambda snapshot: True,
            intent_id=intent.intent_id,
        )
    assert service.pending_for_task("task-1") == (intent,)
    assert not service.project("task-1", include_history=True).history


def test_custom_workspace_never_uses_the_paired_store(configured_review, tmp_path):
    service, _, trust, *_ = configured_review
    assert service.confirm("task-1", "accepted", lambda snapshot: True).binary_label
    other = tmp_path / "unpaired"
    other.mkdir()
    isolated = ReviewService(other, root=trust)
    assert isolated.project("task-1").status == "unpaired"
    assert isolated.project("task-1", include_history=True).history == ()
    with pytest.raises(ReviewServiceError, match="review_workspace_unpaired"):
        isolated.request_intent("task-1", "request-1", "accepted")


def test_missing_trust_and_cancelled_confirmation_are_explicit(configured_review):
    service, _, trust, *_ = configured_review
    intent = service.request_intent("task-1", "request-3", "rejected")
    with pytest.raises(ReviewServiceError, match="review_cancelled"):
        service.confirm(
            "task-1", "rejected", lambda snapshot: False, intent_id=intent.intent_id
        )
    assert service.pending_for_task("task-1") == (intent,)
    (trust / "profiles.json").unlink()
    assert service.project("task-1").status == "unavailable"


def test_previously_paired_service_reports_missing_root_as_unavailable(
    configured_review,
):
    service, _, trust, *_ = configured_review
    assert service.project("task-1").status == "no_decision"
    trust.rename(trust.with_name("removed"))
    assert service.project("task-1").status == "unavailable"


def test_policy_consumes_the_checked_snapshot_without_reopening_it(
    configured_review, monkeypatch
):
    service, _, trust, *_ = configured_review
    from triage_core import task_review_service

    read_private = task_review_service._read_private
    registry = trust / "workspace-a" / "authz" / "credentials.json"
    known_snapshot = registry.read_bytes()
    registry.unlink()

    def read(root, path, limit):
        if path == registry:
            return known_snapshot
        return read_private(root, path, limit)

    monkeypatch.setattr(task_review_service, "_read_private", read)
    assert (
        service.confirm("task-1", "accepted", lambda snapshot: True).binary_label
        is True
    )


def test_manifest_cannot_select_a_file_outside_its_evidence_root(configured_review):
    service, _, _, _, manifest = configured_review
    write_private(
        manifest,
        json.dumps(
            {
                "schema": "triagecore.task_review_manifest.v1",
                "tasks": {
                    "task-1": {
                        "revision": "rev-2",
                        "items": {"draft": "../profiles.json"},
                    }
                },
            }
        ).encode(),
    )
    with pytest.raises(ReviewServiceError, match="review_evidence_unavailable"):
        service.confirm(
            "task-1",
            "accepted",
            lambda snapshot: pytest.fail("unsafe snapshot displayed"),
        )


def test_prior_decision_can_coexist_with_a_new_pending_intent(configured_review):
    service, *_ = configured_review
    service.confirm("task-1", "accepted", lambda snapshot: True)
    service.request_intent("task-1", "request-4", "needs_revision")
    state = service.project("task-1")
    assert state.binary_label is True
    assert state.pending_count == 1


def test_mobile_and_desktop_decisions_share_queue_cli_and_metrics(
    configured_review,
    monkeypatch,
    capsys,
    tmp_path,
):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from triage_core import task_review_service
    from triage_core.lab import calculate_scientific_metrics
    from triage_core.review_queue import get_pending_reviews
    from triage_core.task_ledger import TaskLedger
    from triage_core.tc_cli import tc_task_show

    monkeypatch.setenv("TRIAGECORE_LEDGER_DIR", str(tmp_path / "asgi-import"))
    from triage_core.web import server

    service, ledger_dir, *_ = configured_review
    ledger = TaskLedger(str(ledger_dir), review_service=service)
    ledger.append_event("task-1", "task_classified", {"risk_level": "high"})
    original = (ledger_dir / "ledger.jsonl").read_bytes()
    monkeypatch.setattr(server, "ledger", ledger)
    monkeypatch.setattr(server, "MOBILE_TOKEN", "synthetic-mobile-token")
    monkeypatch.setattr(
        task_review_service, "get_review_service", lambda directory: service
    )
    headers = {"Authorization": "Bearer synthetic-mobile-token"}
    with TestClient(server.app) as client:
        result = client.post(
            "/api/tasks/task-1/review",
            headers=headers,
            json={"decision": "needs_revision", "request_id": "integration-1"},
        )
        assert result.status_code == 202
        assert result.json()["status"] == "pending"
        assert [row.task_id for row in get_pending_reviews(ledger)] == ["task-1"]
        assert (
            calculate_scientific_metrics(ledger.get_all_tasks())[
                "binary_review_sample_size"
            ]
            == 0
        )

        service.confirm(
            "task-1",
            "needs_revision",
            lambda snapshot: True,
            intent_id=result.json()["intent_id"],
        )
        task = ledger.get_task("task-1")
        assert task.review.decision == "needs_revision"
        assert [row.task_id for row in get_pending_reviews(ledger)] == ["task-1"]
        assert (
            calculate_scientific_metrics(ledger.get_all_tasks())[
                "binary_review_sample_size"
            ]
            == 0
        )

        service.confirm("task-1", "accepted", lambda snapshot: True)
        assert ledger.get_task_context("task-1").record.review.decision == "accepted"
        assert get_pending_reviews(ledger) == []
        assert (
            calculate_scientific_metrics(ledger.get_all_tasks())[
                "binary_review_sample_size"
            ]
            == 1
        )
        response = client.get("/api/tasks", headers=headers).json()["tasks"][0]
        assert response["accepted"] is True
        assert response["review_decision"] == "accepted"
        assert (ledger_dir / "ledger.jsonl").read_bytes() == original
        assert "Exact synthetic text" not in json.dumps(response)
        tc_task_show("task-1", ledger_dir=str(ledger_dir))
        output = capsys.readouterr().out
        assert "Review status: verified" in output
        assert "Review decision: accepted" in output


def test_local_acquisition_requires_user_verification_and_allowed_credentials(
    monkeypatch,
):
    pytest.importorskip("fido2")
    from fido2.webauthn import UserVerificationRequirement

    from triage_core import fido2_adapter
    from triage_core.authz import RP_ID, b64url_encode

    captured = []

    class AssertionClient:
        def get_assertion(self, options):
            captured.append(options)
            return self

        def get_response(self, index):
            assert index == 0
            return {"type": "public-key"}

    monkeypatch.setattr(fido2_adapter, "_make_client", AssertionClient)
    challenge = b"x" * 32
    creds = (b64url_encode(b"synthetic-review-id"),)
    expires = datetime.now(timezone.utc) + timedelta(minutes=5)
    assert fido2_adapter.acquire_review_assertion(challenge, creds, expires) == {
        "type": "public-key"
    }
    (options,) = captured
    assert options.rp_id == RP_ID
    assert options.challenge == challenge
    assert options.user_verification is UserVerificationRequirement.REQUIRED
    assert [item.id for item in options.allow_credentials] == [b"synthetic-review-id"]
    assert 0 < options.timeout <= 300_000
