"""Synthetic operator and failure-boundary tests for a single invocation."""

import json
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from triage_core import public_export_evidence as evidence
from triage_core import public_export_release as release




@pytest.mark.parametrize("text", ["", "a\\b\r\n", "x\u202ey\u200b\u0085\0\x1b", "é😀", "literal \\u202e"])
def test_display_is_lossless_and_terminal_safe(text, workflow):
    workflow.kwargs["stage"] = False
    workflow.files[workflow.kwargs["payload_locator"]] = text.encode()
    workflow.run()
    displayed = workflow.op.raw_screen
    assert json.loads(displayed)["payload"].encode() == text.encode()
    assert json.dumps(text, ensure_ascii=True) in displayed
    assert all(c == "\n" or 32 <= ord(c) <= 126 for c in displayed)




class Clock:
    def __init__(self):
        self.start = datetime(2026, 11, 22, 12, tzinfo=timezone.utc)
        self.samples = [0, 1, 2, 3]
        self.offsets = [0, 0, 0, 0]
        self.sample = -2

    def now(self):
        self.sample += 1
        if self.sample == -1:
            return self.start
        return self.start + timedelta(seconds=self.samples[self.sample])

    def monotonic(self):
        return self.samples[self.sample] + self.offsets[self.sample]




class Operator:
    def __init__(self, target):
        self.target = target
        self.events = []
        self.change = lambda: None
        self.ack = None
        self.code = True

    def access(self, provider, surface, programs):
        self.events.append("access")
        return "account:ordinary-1", dict.fromkeys(programs, "none")

    def destination(self):
        self.events.append("destination")
        return self.target, True

    def display(self, screen):
        self.events.append("display")
        self.raw_screen = screen
        self.screen = json.loads(screen)

    def acknowledge(self, triggers):
        self.events.append("ack")
        return triggers if self.ack is None else self.ack

    def confirm(self, code):
        self.events.append("confirm")
        self.change()
        return code if self.code else None




class Handle:
    def __init__(self):
        self.files = {}
        self.fail = None

    def read(self, name):
        return self.files[name]

    def names(self):
        return self.files.keys()

    def revalidate(self):
        pass

    def write_new(self, name, raw):
        if self.fail and name.endswith(self.fail):
            raise OSError
        assert name not in self.files
        self.files[name] = raw
        return evidence.digest(raw)




@pytest.fixture
def workflow(monkeypatch, tmp_path):
    corpus = json.loads((Path(__file__).parent / "fixtures/public_export_v0.json").read_bytes())
    parent, payload = corpus["parent_locator"], corpus["payload_locator"]
    files = {"proposal.json": json.dumps(corpus["proposal"]).encode(),
             parent: json.dumps(corpus["parent"]).encode(), payload: b"Public reading summary.\r\n"}
    destination = tmp_path / "out"
    evidence_dir = tmp_path / "records"
    policy = json.loads(corpus["policy_json"])
    policy.update(version=2, local_staging={"version": 2, "roots": [str(destination)],
                  "evidence_root": str(evidence_dir), "denied_sync_roots": [], "clipboard": False})
    op = Operator(destination)
    clock = Clock()
    files["policy"] = json.dumps(policy).encode()
    records, storage = Handle(), Handle()
    monkeypatch.setattr(release, "read_source", lambda root, name, **kw: files[name])
    monkeypatch.setattr(release, "open_directory", lambda *a, **kw: nullcontext(storage))
    monkeypatch.setattr(release, "open_evidence_directory", lambda *a, **kw: nullcontext(records))

    def stage(handle, data, *, name):
        assert list(records.names()) and evidence.audit(records)[0]["outcome"] == "outcome_unknown"
        value = handle.write_new(name, data)
        return SimpleNamespace(outcome="staged_verified", digest=value, cleanup=None, name=name)

    monkeypatch.setattr(release, "stage_payload", stage)
    kwargs = {"repo_root": tmp_path, "proposal_locator": "proposal.json", "parent_locator": parent,
              "payload_locator": payload, "evidence_dir": evidence_dir,
              "policy_source": lambda: files["policy"], "operator": op,
              "clock": clock, "triagecore_commit": corpus["triagecore_commit"], "stage": True}
    return SimpleNamespace(kwargs=kwargs, files=files, op=op, clock=clock, records=records,
                           storage=storage, run=lambda: release.run_export(**kwargs))


def test_confirmed_file_matches_display_and_intent_precedes_payload(workflow):
    w = workflow
    result = w.run()
    assert result.outcome == "staged_verified" and result.exit_code == 0
    assert w.op.events == ["access", "destination", "display", "confirm"]
    assert list(w.storage.files.values()) == [w.op.screen["payload"].encode()]
    assert w.op.screen["eligibility_id"] == result.eligibility_id
    assert evidence.audit(w.records)[0]["outcome"] == "staged_verified"




@pytest.mark.parametrize(("field", "expected"), [
    ("payload_locator", "bytes_changed"), ("parent_locator", "parent_changed"),
    ("proposal_locator", "proposal_changed"), ("policy", "policy_changed"),
])
def test_change_after_display_refuses_and_requires_new_confirmation(workflow, field, expected):
    w = workflow
    key = w.kwargs.get(field, field)
    w.op.change = lambda: w.files.__setitem__(key, w.files[key] + b" ")
    result = w.run()
    assert result.outcome == "refused_pre_staging" and expected in result.reason_codes
    assert not w.storage.files and not w.records.files
    w.clock.sample = -2
    w.op.code = False
    again = w.run()
    assert again.outcome == "refused_pre_staging"
    assert w.op.events.count("confirm") == 2 and not w.storage.files




@pytest.mark.parametrize(("samples", "offsets", "reason"), [
    ([0, 1, 2, 123], [0, 0, 0, 0], "approval_expired"),
    ([0, 1, 2, 901], [0, 0, 0, 0], "attestation_stale_at_release"),
    ([0, 1, 2, 602], [0, 0, 0, 0], "valid_until_passed"),
    ([0, 1, 2, 1], [0, 0, 0, 0], "clock_inconsistent"),
    ([0, 1, 2, 3], [0, 0, 0, 20], "clock_inconsistent"),
])
def test_release_time_checks(workflow, samples, offsets, reason):
    w = workflow
    w.clock.samples, w.clock.offsets = samples, offsets
    assert reason in w.run().reason_codes
    assert not w.storage.files and not w.records.files


def test_parent_expiry_checked_at_release(workflow):
    w = workflow
    parent = json.loads(w.files[w.kwargs["parent_locator"]])
    parent["expires_at"] = (w.clock.start + timedelta(seconds=3)).isoformat()
    w.files[w.kwargs["parent_locator"]] = json.dumps(parent).encode()
    assert "parent_expired" in w.run().reason_codes
    assert not w.storage.files




@pytest.mark.parametrize("ack", [(), ("elevated_task_risk", "extra"), ("not_requested",)])
def test_inexact_acknowledgement_never_confirms(workflow, ack):
    w = workflow
    proposal = json.loads(w.files["proposal.json"])
    proposal["declared_task_risk"] = "elevated"
    w.files["proposal.json"] = json.dumps(proposal).encode()
    w.op.ack = ack
    assert w.run().outcome == "refused_pre_staging"
    assert "confirm" not in w.op.events and not w.storage.files


def test_read_only_default_has_no_writes_or_confirmation(workflow):
    w = workflow
    w.kwargs.update(stage=False, evidence_dir=None)
    result = w.run()
    assert result.outcome == "eligible_for_operator_reviewed_export"
    assert w.op.events == ["access", "display"]
    assert not w.storage.files and not w.records.files




@pytest.mark.parametrize(("kind", "result", "code"), [
    ("intent.json", "refused_pre_staging", 2), ("release.json", "staged_verified", 4),
])
def test_evidence_write_failures_report_actual_stage(workflow, kind, result, code):
    w = workflow
    w.records.fail = kind
    decision = w.run()
    assert (decision.outcome, decision.exit_code) == (result, code)
    if kind == "release.json":
        assert list(w.storage.files.values()) == [w.op.screen["payload"].encode()]
        assert evidence.audit(w.records)[0]["outcome"] == "outcome_unknown"
    else:
        assert not w.storage.files


def test_hard_refusal_displays_record_without_raw_payload(workflow):
    w = workflow
    w.files[w.kwargs["payload_locator"]] = b"CONFIDENTIAL: local notes."
    result = w.run()
    assert result.outcome == "ineligible"
    assert w.op.screen["eligibility"]["reason_codes"] == list(result.reason_codes)
    assert "payload" not in w.op.screen and "CONFIDENTIAL" not in json.dumps(w.op.screen)
    assert "confirm" not in w.op.events


def test_wrong_code_is_redacted(workflow):
    w = workflow
    w.op.confirm = lambda code: "typed by mistake"
    result = w.run()
    assert result.outcome == "refused_pre_staging" and result.reason_codes == ("confirmation_declined",)
    assert not w.records.files and not w.storage.files


def test_requested_expiry_is_exclusive_at_release(workflow):
    w = workflow
    proposal = json.loads(w.files["proposal.json"])
    proposal["requested_expiry"] = (w.clock.start + timedelta(seconds=3)).isoformat()
    w.files["proposal.json"] = json.dumps(proposal).encode()
    assert "valid_until_passed" in w.run().reason_codes
    assert not w.storage.files and not w.records.files




@pytest.mark.parametrize(("duration", "eligible"), [(119.999999, True), (120, False), (120.000001, False)])
def test_approval_expires_at_confirmation_plus_ttl(workflow, duration, eligible):
    w = workflow
    w.clock.samples = [0, 1, 2, 2 + duration]
    result = w.run()
    if eligible:
        assert result.outcome == "staged_verified"
    else:
        assert "approval_expired" in result.reason_codes and not w.storage.files


def test_destination_disclaimer_required(workflow):
    w = workflow
    w.op.destination = lambda: (w.op.target, False)
    assert w.run().reason_codes == ("destination_not_attested",)
    assert "confirm" not in w.op.events and not w.records.files and not w.storage.files




@pytest.mark.parametrize(("outcome", "cleanup"), [
    ("staging_failed_partial", "unknown"), ("staging_uncertain", "unknown"),
    ("staged_mismatch", None), ("staged_unverified", None),
])
def test_actual_write_fault_outcome_and_incident(workflow, monkeypatch, outcome, cleanup):
    w = workflow
    readback = "sha256:" + "f" * 64 if outcome == "staged_mismatch" else None

    def stage(handle, raw, *, name):
        return SimpleNamespace(outcome=outcome, digest=readback, cleanup=cleanup, name=name)

    monkeypatch.setattr(release, "stage_payload", stage)
    result = w.run()
    row, = evidence.audit(w.records)
    assert result.exit_code == 3 and row["outcome"] == result.outcome == outcome
    assert row["incident"] == ("readback_mismatch" if outcome == "staged_mismatch" else None)




@pytest.mark.parametrize("field", ["proposal", "parent"])
def test_schema_refusal_precedes_any_operator_questions(workflow, field):
    w = workflow
    name = w.kwargs[field + "_locator"]
    value = json.loads(w.files[name])
    value["basis"] = "operator_attested"
    w.files[name] = json.dumps(value).encode()
    result = w.run()
    assert result.outcome == "ineligible"
    assert w.op.events == ["display"]
    assert w.op.screen["eligibility"]["access"]["status"] == "not_collected"
    assert not w.records.files and not w.storage.files




@pytest.mark.parametrize("which", ["storage", "records"])
def test_substituted_directory_before_intent_refuses_without_writes(workflow, which):
    w = workflow

    def substituted():
        raise release.StorageError("destination_changed")

    w.op.change = lambda: setattr(getattr(w, which), "revalidate", substituted)
    assert w.run().reason_codes == ("destination_changed",)
    assert not w.records.files and not w.storage.files




@pytest.mark.parametrize("which", ["open_directory", "open_evidence_directory"])
def test_handle_close_failure_preserves_observed_effects(workflow, monkeypatch, which):
    w = workflow
    handle = w.storage if which == "open_directory" else w.records

    @contextmanager
    def fails_to_close(*args, **kwargs):
        yield handle
        raise OSError

    monkeypatch.setattr(release, which, fails_to_close)
    result = w.run()
    assert result.outcome == "staged_verified" and result.exit_code != 0
    assert result.reason_codes == ("directory_close_failed",)
    assert result.attempt_id == evidence.audit(w.records)[0]["attempt_id"]
    assert list(w.storage.files.values()) == [w.op.screen["payload"].encode()]
