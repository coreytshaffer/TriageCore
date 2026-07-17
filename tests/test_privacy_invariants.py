import json

import pytest

from triage_core.privacy_invariants import (
    PersistentPrivacyInvariantError,
    assert_persistent_privacy_safe,
    find_forbidden_persistent_fields,
)
from triage_core.task_ledger import TaskLedger


def test_allows_safe_route_audit_payload():
    payload = {
        "decision": "allowed",
        "reason_code": "audit_self_test",
        "privacy_level": "public",
        "privacy_scan_passed": True,
        "is_local_only": False,
        "recommended_route": "self_test",
        "selected_backend": "self_test",
    }

    assert_persistent_privacy_safe(payload)


def test_rejects_top_level_raw_prompt_without_echoing_value():
    sensitive_value = "secret user request"

    with pytest.raises(PersistentPrivacyInvariantError) as exc:
        assert_persistent_privacy_safe(
            {"prompt": sensitive_value},
            artifact_name="test artifact",
        )

    assert "$.prompt" in str(exc.value)
    assert sensitive_value not in str(exc.value)


def test_rejects_nested_raw_data():
    violations = find_forbidden_persistent_fields(
        {"safe": {"nested": {"raw_data": "secret payload"}}}
    )

    assert len(violations) == 1
    assert violations[0].path == "$.safe.nested.raw_data"
    assert violations[0].key == "raw_data"


def test_rejects_raw_content_inside_list():
    payload = {
        "events": [
            {"decision": "allowed"},
            {"content": "raw model output"},
        ]
    }

    with pytest.raises(PersistentPrivacyInvariantError) as exc:
        assert_persistent_privacy_safe(payload)

    assert "$.events[1].content" in str(exc.value)


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("Contact jane@example.com", "email_pattern"),
        ("SSN 123-45-6789", "ssn_pattern"),
        ("token=super-secret-value", "secret_pattern"),
    ],
)
def test_rejects_sensitive_persistent_values_without_echoing_them(value, reason):
    with pytest.raises(PersistentPrivacyInvariantError) as exc:
        assert_persistent_privacy_safe({"description": value})

    violation = exc.value.violations[0]
    assert violation.path == "$.description"
    assert violation.reason == reason
    assert value not in str(exc.value)


@pytest.mark.parametrize(
    "key",
    [
        "api_key",
        "access_token",
        "authorization",
        "bearer",
        "client_secret",
        "private_key",
        "secret",
        "token",
    ],
)
def test_rejects_secret_bearing_persistent_keys(key):
    with pytest.raises(PersistentPrivacyInvariantError) as exc:
        assert_persistent_privacy_safe({key: "do-not-persist"})

    assert f"$.{key}" in str(exc.value)
    assert "do-not-persist" not in str(exc.value)


def test_task_ledger_rejects_forbidden_payload_before_write(tmp_path):
    ledger = TaskLedger(str(tmp_path / ".triagecore"))

    with pytest.raises(PersistentPrivacyInvariantError):
        ledger.append_event(
            "task-1",
            "route_audit",
            {"decision": "allowed", "prompt": "do the secret thing"},
        )

    ledger_path = tmp_path / ".triagecore" / "ledger.jsonl"
    assert not ledger_path.exists()


def test_task_ledger_does_not_modify_existing_file_on_rejection(tmp_path):
    ledger = TaskLedger(str(tmp_path / ".triagecore"))
    ledger.append_event(
        "task-1",
        "route_audit",
        {"decision": "allowed", "reason_code": "safe_metadata_only"},
    )
    ledger_path = tmp_path / ".triagecore" / "ledger.jsonl"
    original_contents = ledger_path.read_bytes()

    with pytest.raises(PersistentPrivacyInvariantError):
        ledger.append_event(
            "task-2",
            "route_audit",
            {"decision": "blocked", "raw_request": "private task"},
        )

    assert ledger_path.read_bytes() == original_contents


def test_task_ledger_writes_safe_payload(tmp_path):
    ledger = TaskLedger(str(tmp_path / ".triagecore"))

    ledger.append_event(
        "task-1",
        "route_audit",
        {
            "decision": "allowed",
            "reason_code": "safe_metadata_only",
            "privacy_level": "public",
        },
    )

    ledger_path = tmp_path / ".triagecore" / "ledger.jsonl"
    records = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(records) == 1
    assert records[0]["task_id"] == "task-1"
    assert records[0]["event_type"] == "route_audit"
    assert records[0]["payload"]["reason_code"] == "safe_metadata_only"
