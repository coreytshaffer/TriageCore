"""Closed Grant B evidence and restart audit tests."""

import hashlib
import json
import subprocess
import sys
import uuid

import pytest

from triage_core import public_export_evidence as evidence


class Records:
    def __init__(self):
        self.files = {}

    def write_new(self, name, data):
        assert name not in self.files
        self.files[name] = data
        return "sha256:" + hashlib.sha256(data).hexdigest()

    def read(self, name):
        return self.files[name]

    def names(self):
        return sorted(self.files)

    def revalidate(self):
        pass


def records_for_attempt():
    attempt = str(uuid.uuid4())
    digest = "sha256:" + "a" * 64
    intent = evidence.intent_record(attempt, digest, digest, digest, digest, digest, (),
                                    "2026-11-22T12:00:00Z", "2026-11-22T12:02:00Z")
    return attempt, intent


def test_intent_survives_reopen_and_release_pairs_to_intent_bytes():
    records = Records()
    attempt, intent = records_for_attempt()
    bound = evidence.write_record(records, intent)
    assert evidence.audit(records)[0]["outcome"] == "outcome_unknown"
    release = evidence.release_record(attempt, bound, "staged_verified",
                                      intent["payload_digest"], None)
    evidence.write_record(records, release)
    assert evidence.audit(records)[0]["outcome"] == "staged_verified"
    assert evidence.audit(records)[0]["outside_visibility"] == list(evidence.OUTSIDE_VISIBILITY)


@pytest.mark.parametrize("mutation", [
    {"unexpected": True}, {"prompt": "private"}, {"attempt_id": "../../private/file"},
    {"payload_digest": "fake"}, {"acknowledged_triggers": ["free-form"]},
])
def test_rejects_invalid_evidence_before_io(mutation):
    records = Records()
    _, intent = records_for_attempt()
    with pytest.raises(ValueError):
        evidence.write_record(records, {**intent, **mutation})
    assert not records.files


def test_orphan_release_and_wrong_binding_are_invalid_evidence():
    records = Records()
    attempt, intent = records_for_attempt()
    wrong = "sha256:" + "b" * 64
    evidence.write_record(records, evidence.release_record(attempt, wrong, "staged_verified",
                                                          intent["payload_digest"], None))
    orphan, = evidence.audit(records)
    assert orphan["outcome"] == "outcome_unknown" and orphan["incident"] == "release_without_intent"
    assert evidence.has_audit_errors([orphan]) and orphan["eligibility_id"] is None
    evidence.write_record(records, intent)
    unbound, = evidence.audit(records)
    assert unbound["outcome"] == "outcome_unknown" and unbound["incident"] == "evidence_identity_mismatch"
    assert evidence.has_audit_errors([unbound])


def test_audit_rejects_duplicate_fields_and_filename_substitution():
    records = Records()
    attempt, intent = records_for_attempt()
    evidence.write_record(records, intent)
    name, = records.files
    original = records.files[name]
    records.files[name] = original.replace(b"{", b'{"kind":"intent",', 1)
    invalid, = evidence.audit(records)
    assert invalid["outcome"] == "outcome_unknown" and invalid["incident"] == "unreadable_intent_evidence"
    records.files = {name.replace(attempt, str(uuid.uuid4())): original}
    mismatch, = evidence.audit(records)
    assert mismatch["outcome"] == "outcome_unknown" and mismatch["incident"] == "evidence_identity_mismatch"


def test_mismatch_opens_bounded_incident():
    records = Records()
    attempt, intent = records_for_attempt()
    bound = evidence.write_record(records, intent)
    release = evidence.release_record(attempt, bound, "staged_mismatch", "sha256:" + "b" * 64, None)
    evidence.write_record(records, release)
    assert evidence.audit(records)[0]["incident"] == "readback_mismatch"
    assert "/private" not in json.dumps(evidence.audit(records))


@pytest.mark.parametrize("after_stage", [False, True])
def test_process_termination_on_either_side_of_staging(tmp_path, after_stage):
    from tests.test_public_export_staging import private_directory
    from triage_core.public_export_staging import open_directory

    root = private_directory(tmp_path / "records")
    destination = private_directory(tmp_path / "stage")
    attempt = str(uuid.uuid4())
    script = """
import os
from pathlib import Path
import sys
from triage_core import public_export_evidence as evidence
from triage_core.public_export_staging import open_directory, stage_payload
records, stage = Path(sys.argv[1]), Path(sys.argv[2])
attempt, after = sys.argv[3:]
payload = b'synthetic crash case'
checksum = evidence.digest(payload)
intent = evidence.intent_record(attempt, checksum, checksum, checksum,
    evidence.locator_digest(stage), evidence.locator_digest(stage / 'fixture.txt'),
    (), '2026-11-22T12:00:00Z', '2026-11-22T12:02:00Z')
with open_directory(records, root=records, denied_sync_roots=(), evidence=True) as directory:
    evidence.write_record(directory, intent)
    if after == 'yes':
        with open_directory(stage, root=stage, denied_sync_roots=()) as staged:
            result = stage_payload(staged, payload, name='fixture.txt')
            assert result.outcome == 'staged_verified', result
    os._exit(74)
"""
    child = subprocess.run([sys.executable, "-c", script, str(root), str(destination),
                            attempt, "yes" if after_stage else "no"], check=False, capture_output=True, text=True)
    assert child.returncode == 74, child.stderr
    assert (destination / "fixture.txt").exists() is after_stage
    with open_directory(root, root=root, denied_sync_roots=(), evidence=True) as records:
        row, = evidence.audit(records)
        assert row["outcome"] == "outcome_unknown" and row["attempt_id"] == attempt
        raw = records.read(f"{attempt}.intent.json")
        assert str(root).encode() not in raw and b"synthetic crash case" not in raw


def test_interrupted_release_publication_audits_as_unknown():
    records = Records()
    attempt, intent = records_for_attempt()
    evidence.write_record(records, intent)
    records.files[f"{attempt}.release.json"] = b'{"kind":"release"'
    row, = evidence.audit(records)
    assert row["outcome"] == "outcome_unknown" and row["incident"] == "unreadable_release_evidence"
    assert evidence.has_audit_errors([row])


def test_incomplete_intent_does_not_hide_other_verified_or_unmatched_attempts():
    records = Records()
    success, complete = records_for_attempt()
    bound = evidence.write_record(records, complete)
    evidence.write_record(records, evidence.release_record(success, bound, "staged_verified",
                                                          complete["payload_digest"], None))
    unmatched, intent = records_for_attempt()
    evidence.write_record(records, intent)
    assert not evidence.has_audit_errors(evidence.audit(records))
    broken = str(uuid.uuid4())
    records.files[f"{broken}.intent.json"] = b'{"private_input":"sensitive'
    records.files["sensitive-name.release.json"] = b""
    original = dict(records.files)
    rows = evidence.audit(records)
    assert evidence.has_audit_errors(rows) and len(rows) == 4
    by_id = {row["attempt_id"]: row for row in rows}
    assert by_id[success]["outcome"] == "staged_verified"
    assert by_id[unmatched]["outcome"] == "outcome_unknown" and by_id[unmatched]["incident"] is None
    assert by_id[broken]["incident"] == "unreadable_intent_evidence"
    assert by_id[None]["incident"] == "invalid_evidence_name"
    for key in (broken, None):
        assert by_id[key]["eligibility_id"] is None and by_id[key]["outcome"] == "outcome_unknown"
    assert "sensitive" not in json.dumps(rows) and records.files == original
