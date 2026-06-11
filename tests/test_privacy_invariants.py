import uuid

import pytest

from triage_core.privacy_invariants import (
    PersistentArtifactPrivacyError,
    validate_persistent_artifact_payload,
)
from triage_core.task_ledger import TaskLedger


def test_validate_persistent_artifact_payload_allows_metadata_only_payload():
    validate_persistent_artifact_payload(
        {
            "event_type": "route_audit",
            "route": "local",
            "risk": "low",
            "passed": True,
            "violation_count": 0,
        }
    )


def test_validate_persistent_artifact_payload_rejects_top_level_key():
    with pytest.raises(
        PersistentArtifactPrivacyError,
        match=r"payload\.prompt",
    ):
        validate_persistent_artifact_payload(
            {
                "event_type": "route_audit",
                "prompt": "raw user request here",
            }
        )


def test_validate_persistent_artifact_payload_rejects_nested_key():
    with pytest.raises(
        PersistentArtifactPrivacyError,
        match=r"payload\.nested\.raw_data",
    ):
        validate_persistent_artifact_payload(
            {
                "event_type": "route_audit",
                "nested": {"raw_data": "secret"},
            }
        )


def test_validate_persistent_artifact_payload_rejects_list_key():
    with pytest.raises(
        PersistentArtifactPrivacyError,
        match=r"payload\.items\[0\]\.body",
    ):
        validate_persistent_artifact_payload(
            {
                "event_type": "route_audit",
                "items": [{"body": "secret"}],
            }
        )


def test_append_event_does_not_modify_existing_ledger_on_validation_failure(tmp_path):
    ledger = TaskLedger(ledger_dir=str(tmp_path))
    task_id = str(uuid.uuid4())
    ledger.append_event(task_id, "route_audit", {"decision": "allowed"})

    before = ledger.ledger_path
    before_text = tmp_path.joinpath("ledger.jsonl").read_text(encoding="utf-8")

    with pytest.raises(
        PersistentArtifactPrivacyError,
        match=r"payload\.prompt",
    ):
        ledger.append_event(task_id, "route_audit", {"prompt": "secret"})

    after_text = tmp_path.joinpath("ledger.jsonl").read_text(encoding="utf-8")
    assert ledger.ledger_path == before
    assert after_text == before_text
    assert len(after_text.strip().splitlines()) == 1


def test_append_event_does_not_create_ledger_for_invalid_first_event(tmp_path):
    ledger = TaskLedger(ledger_dir=str(tmp_path))

    with pytest.raises(
        PersistentArtifactPrivacyError,
        match=r"payload\.items\[0\]\.content",
    ):
        ledger.append_event(
            str(uuid.uuid4()),
            "route_audit",
            {"items": [{"content": "secret"}]},
        )

    assert not tmp_path.joinpath("ledger.jsonl").exists()
