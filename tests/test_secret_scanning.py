import pytest

from triage_core.privacy_invariants import PersistentPrivacyInvariantError
from triage_core.privacy_scanner import PrivacyViolationError, scan_task_packet
from triage_core.safe_task_packet import verify_packet
from triage_core.task_ledger import TaskLedger
from triage_core.task_packet import TaskPacket


@pytest.fixture(params=[
    pytest.param('api_key = "fixtureexample"', id="double-quoted-assignment"),
    pytest.param("SECRET='fixtureexample'", id="single-quoted-assignment"),
    pytest.param("ToKeN = fixtureexample", id="spaced-assignment"),
    pytest.param('{"api_key": "fixtureexample"}', id="json-property"),
    pytest.param('token: "fixtureexample"', id="quoted-config-value"),
    pytest.param("Authorization: Bearer fixture.part.example", id="bearer-header"),
    pytest.param("sk-proj-fixture_fake_key_for_tests", id="project-key"),
    pytest.param("sk-ant-api03-fixture_fake_key_for_tests", id="provider-key"),
])
def fake_credential_text(request):
    return request.param


@pytest.mark.parametrize("field", ["prompt", "data"])
def test_packet_rejects_fake_credential(fake_credential_text, field):
    fields = {"prompt": "Review this sample.", "data": ""}
    fields[field] = fake_credential_text
    packet = TaskPacket(**fields)

    report = scan_task_packet(packet)
    assert not report.passed
    assert "Secret/API key pattern" in report.detections
    with pytest.raises(PrivacyViolationError) as error:
        verify_packet(packet)
    assert "fixture" not in str(error.value)


def test_ledger_rejects_fake_credential_before_writing(tmp_path, fake_credential_text):
    ledger = TaskLedger(str(tmp_path))
    path = tmp_path / "ledger.jsonl"
    payload = {"description": fake_credential_text}

    with pytest.raises(PersistentPrivacyInvariantError) as error:
        ledger.append_event("test-task", "task_created", payload)
    assert not path.exists()
    violation, = error.value.violations
    assert violation.path == "$.description"
    assert violation.reason == "secret_pattern"
    assert "fixture" not in str(error.value)

    ledger.append_event("test-task", "task_created", {"description": "Sample task."})
    original = path.read_bytes()
    with pytest.raises(PersistentPrivacyInvariantError):
        ledger.append_event("test-task", "task_created", payload)
    assert path.read_bytes() == original


@pytest.mark.parametrize("text", [
    'api_key = ""',
    '{"token": ""}',
    "token: budget estimate",
    "Authorization: Bearer",
])
def test_empty_values_and_ordinary_labels_pass_both_scans(tmp_path, text):
    assert scan_task_packet(TaskPacket(prompt=text, data="")).passed

    ledger = TaskLedger(str(tmp_path))
    ledger.append_event("test-task", "task_created", {"description": text})
    assert (tmp_path / "ledger.jsonl").is_file()
