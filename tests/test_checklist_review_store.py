"""CR-138 review store: persistence, chronology, immutability, failure,
privacy, and measurement checks."""

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from triage_core import checklist_review as cr
from triage_core import checklist_review_local as local
from triage_core import checklist_review_store as store_module
from triage_core.checklist_review_store import ReviewStore, StoreError
from triage_core.privacy_invariants import assert_persistent_privacy_safe

FIXTURES = Path(__file__).parent / "fixtures" / "checklist_review"
MODEL_TAG = "qwen3.5:4b"
MODEL_DIGEST = "d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04"
CASE_SENTINEL = "SENTINEL-CASE-TEXT-5e1d"
MODEL_SENTINEL = "SENTINEL-MODEL-TEXT-9b3a"
NOTE_SENTINEL = "SENTINEL-NOTE-TEXT-2c7f"


def text_fixture(relative: str) -> bytes:
    return (FIXTURES / relative).read_bytes().replace(b"\r\n", b"\n")


class StepClock:
    """Monotonic and wall clock that moves one second per reading."""

    def __init__(self):
        self.value = 0.0

    def monotonic(self):
        self.value += 1.0
        return self.value

    def now(self):
        self.value += 1.0
        return datetime(2026, 11, 20, tzinfo=timezone.utc) + timedelta(seconds=self.value)


class ScriptedModel:
    """Test double with the ReviewModel interface; never touches a socket."""

    origin = "live"
    label = None
    refers_to = None

    def __init__(self, reply_text, runtime=None):
        self.reply_text = reply_text
        self.runtime = runtime if runtime is not None else {"eval_duration_ns": 2_500_000_000}
        self.sent = []

    def preflight(self, tag, expected_digest):
        return local.PreflightResult(
            status="ok", reason_code=None, identity_source="observed", observed_tag=tag, observed_digest=expected_digest
        )

    def chat(self, body):
        self.sent.append(body)
        runtime = dict(local.UNKNOWN_RUNTIME)
        runtime.update(self.runtime)
        return local.ChatResult(status="completed", reason_code=None, reply_text=self.reply_text, runtime=runtime)


def reply(case_id="DC-02", finding="insufficient evidence", cited=("S1.L03",), reason="r"):
    return json.dumps({"case_id": case_id, "finding": finding, "cited_lines": list(cited), "reason": reason})


@pytest.fixture
def clock():
    return StepClock()


@pytest.fixture
def root(tmp_path, clock):
    path = tmp_path / "store"
    with ReviewStore.create(path, now=clock.now) as created:
        created.save_definition("docrev-v1", model_tag=MODEL_TAG, model_digest=MODEL_DIGEST)
    return path


def run_case(root, clock, *, case="DC-02", model=None, case_bytes=None):
    with ReviewStore.open(root, now=clock.now) as store:
        return local.run_review(
            store,
            workflow_ref="docrev-v1",
            case_bytes=case_bytes if case_bytes is not None else text_fixture(f"cases/{case}.txt"),
            model=model or ScriptedModel(reply()),
            confirm_local_runtime=True,
            clock=clock,
        )


def events_of(root, run_id):
    with ReviewStore.open_readonly(root) as store:
        return store.list_events(run_id)


def event_of(events, step, kind="result"):
    return next(e for e in events if (e.step, e.kind) == (step, kind))


def metadata_text(root) -> str:
    """Every text value stored in any SQLite column."""
    connection = sqlite3.connect(root / store_module.DATABASE_NAME)
    try:
        values = []
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        for table in tables:
            for row in connection.execute(f"SELECT * FROM {table}"):
                values.extend(str(value) for value in row)
        return "\n".join(values)
    finally:
        connection.close()


# --- Definitions ------------------------------------------------------------


def test_definition_templates_are_verified_private_artifacts(root):
    with ReviewStore.open_readonly(root) as store:
        definition = store.load_definition("docrev-v1")
        assert definition.digest == cr.definition_digest(definition.record)
        system = store.read_artifact(definition.artifact("system_text"))
        template = store.read_artifact(definition.artifact("user_template"))
    assert system.status == template.status == "verified"
    assert system.data == cr.SYSTEM_TEXT.encode("utf-8")
    assert template.data == cr.USER_TEMPLATE.encode("utf-8")
    assert hashlib.sha256(template.data).hexdigest() == cr.USER_TEMPLATE_SHA256
    text = metadata_text(root)
    assert cr.USER_TEMPLATE_SHA256 in text
    assert "BEGIN INSTRUCTIONS" not in text
    assert "You are checking documents" not in text


def test_saving_the_same_reference_again_is_idempotent_and_different_content_conflicts(root, clock):
    with ReviewStore.open(root, now=clock.now) as store:
        before = store.load_definition("docrev-v1")
        again = store.save_definition("docrev-v1", model_tag=MODEL_TAG, model_digest=MODEL_DIGEST)
        assert again.created is False
        assert again.digest == before.digest
        with pytest.raises(StoreError) as raised:
            store.save_definition("docrev-v1", model_tag=MODEL_TAG, model_digest="0" * 64)
        assert raised.value.reason_code == "definition_conflict"
        after = store.load_definition("docrev-v1")
    assert after.digest == before.digest
    assert after.record == before.record


def test_create_refuses_a_non_empty_directory_that_is_not_a_store(tmp_path):
    (tmp_path / "busy").mkdir()
    (tmp_path / "busy" / "unrelated.txt").write_text("x", encoding="utf-8")
    with pytest.raises(StoreError) as raised:
        ReviewStore.create(tmp_path / "busy")
    assert raised.value.reason_code == "store_root_not_empty"


def test_open_fails_closed_on_a_missing_store_without_creating_it(tmp_path):
    for opener in (ReviewStore.open, ReviewStore.open_readonly):
        with pytest.raises(StoreError) as raised:
            opener(tmp_path / "absent")
        assert raised.value.reason_code == "store_missing"
    assert not (tmp_path / "absent").exists()


# --- Reopening, chronology, and immutability --------------------------------


def test_new_store_instance_reopens_run_with_original_records_and_later_human_event(root, clock):
    raw = (FIXTURES / "recorded" / "R01_DC-02_slm.txt").read_bytes()
    outcome = run_case(root, clock, model=ScriptedModel(raw.decode("utf-8")))
    with ReviewStore.open_readonly(root) as store:
        definition_before = store.load_definition("docrev-v1")
    first = events_of(root, outcome.run_id)
    model_event = event_of(first, "model")

    with ReviewStore.open(root, now=clock.now) as store:
        human = store.record_human_assessment(
            outcome.run_id,
            item_id=cr.ITEM_ID,
            target_event_id=model_event.event_id,
            finding="insufficient evidence",
            disposition="revised",
            label_assessment="correct",
            evidence_assessment="unsupported",
            cited_labels=["S1.L03", "S1.L04", "S1.L05"],
            reason_code="no_matching_document",
        )

    with ReviewStore.open_readonly(root) as reopened:
        events = reopened.list_events(outcome.run_id)
        assert [e.seq for e in events] == list(range(1, len(events) + 1))
        assert [e.event_id for e in events[: len(first)]] == [e.event_id for e in first]
        assert events[-1].event_id == human.event_id
        assert events[-1].target_event_id == model_event.event_id
        stamps = [e.recorded_at for e in events]
        assert stamps == sorted(stamps)
        output = reopened.read_artifact(event_of(events, "model").artifacts["output"])
        assert output.status == "verified"
        assert output.data == raw
        assert reopened.load_definition("docrev-v1").record == definition_before.record
        view = reopened.project_run(outcome.run_id)
        assert view.effective_human.event_id == human.event_id
        assert view.model.status == "returned_valid"


def test_definitions_runs_and_events_reject_update_and_delete(root, clock):
    outcome = run_case(root, clock)
    connection = sqlite3.connect(root / store_module.DATABASE_NAME)
    try:
        statements = [
            "UPDATE events SET status = 'x'",
            "DELETE FROM events",
            "UPDATE definitions SET digest = 'x'",
            "DELETE FROM definitions",
            "UPDATE runs SET origin = 'x'",
            "DELETE FROM runs",
            "UPDATE artifacts SET sha256 = 'x'",
            "DELETE FROM event_artifacts",
        ]
        for statement in statements:
            with pytest.raises(sqlite3.DatabaseError, match="checklist_review_immutable"):
                connection.execute(statement)
        with pytest.raises(sqlite3.DatabaseError, match="checklist_review_sequence"):
            connection.execute(
                "INSERT INTO events (event_id, run_id, seq, item_id, step, kind, status, recorded_at, record_json)"
                " VALUES ('e-x', ?, 99, NULL, 'attempt', 'finished', 'stopped', '2026-11-20T00:00:00Z', '{}')",
                (outcome.run_id,),
            )
    finally:
        connection.close()
    assert len(events_of(root, outcome.run_id)) == 7


# --- Failure handling -------------------------------------------------------


def _start_run(store, case="DC-02"):
    definition = store.load_definition("docrev-v1")
    return store.begin_run(
        definition,
        origin="live",
        origin_label=None,
        refers_to=None,
        runtime_confirmation="confirmed",
        case_bytes=text_fixture(f"cases/{case}.txt"),
    )


def _artifact_path(root, data):
    digest = hashlib.sha256(data).hexdigest()
    return root / "artifacts" / "sha256" / digest[:2] / digest


def test_interrupted_artifact_publication_leaves_prior_records_intact(root, clock, monkeypatch):
    payload = b"model output that is interrupted mid-write"
    with ReviewStore.open(root, now=clock.now) as store:
        started = _start_run(store)
        original_write = store._write_staged

        def interrupted(handle, data):
            handle.write(data[: len(data) // 2])
            raise OSError("simulated power loss")

        monkeypatch.setattr(store, "_write_staged", interrupted)
        with pytest.raises(StoreError) as raised:
            store.append_event(
                started.run_id,
                step="model",
                kind="result",
                status="returned_valid",
                item_id=cr.ITEM_ID,
                record={"note": "x"},
                new_artifacts={"output": (payload, "model_output")},
            )
        assert raised.value.reason_code == "artifact_write_failed"
        assert not _artifact_path(root, payload).exists()
        monkeypatch.setattr(store, "_write_staged", original_write)
        recovered = store.append_event(
            started.run_id,
            step="model",
            kind="result",
            status="returned_valid",
            item_id=cr.ITEM_ID,
            record={"note": "x"},
            new_artifacts={"output": (payload, "model_output")},
        )
    events = events_of(root, started.run_id)
    assert [e.seq for e in events] == [1, 2]
    assert events[1].event_id == recovered.event_id
    with ReviewStore.open_readonly(root) as store:
        assert store.read_artifact(events[1].artifacts["output"]).data == payload


def test_corrupt_existing_artifact_is_never_linked(root, clock):
    payload = b"complete model output bytes"
    path = _artifact_path(root, payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload[:10])
    with ReviewStore.open(root, now=clock.now) as store:
        started = _start_run(store)
        with pytest.raises(StoreError) as raised:
            store.append_event(
                started.run_id,
                step="model",
                kind="result",
                status="returned_valid",
                item_id=cr.ITEM_ID,
                record={},
                new_artifacts={"output": (payload, "model_output")},
            )
        assert raised.value.reason_code == "artifact_digest_mismatch"
    assert path.read_bytes() == payload[:10]
    assert [e.seq for e in events_of(root, started.run_id)] == [1]


def test_complete_existing_artifact_is_reused_only_after_verification(root, clock):
    payload = b"previously published complete bytes"
    path = _artifact_path(root, payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    stamp = 1_700_000_000
    os.utime(path, (stamp, stamp))
    with ReviewStore.open(root, now=clock.now) as store:
        started = _start_run(store)
        event = store.append_event(
            started.run_id,
            step="model",
            kind="result",
            status="returned_valid",
            item_id=cr.ITEM_ID,
            record={},
            new_artifacts={"output": (payload, "model_output")},
        )
        assert store.read_artifact(event.artifacts["output"]).status == "verified"
    assert os.stat(path).st_mtime == stamp


def test_failed_event_write_rolls_back_and_leaves_an_inert_artifact(root, clock, monkeypatch):
    payload = b"bytes whose event write fails"
    with ReviewStore.open(root, now=clock.now) as store:
        started = _start_run(store)

        def failing(connection, rows):
            connection.execute("INSERT INTO artifacts VALUES (?, ?, ?, ?, ?)", rows["artifacts"][0])
            raise sqlite3.OperationalError("simulated disk I/O error")

        monkeypatch.setattr(store, "_insert_event_rows", failing)
        with pytest.raises(StoreError) as raised:
            store.append_event(
                started.run_id,
                step="model",
                kind="result",
                status="returned_valid",
                item_id=cr.ITEM_ID,
                record={},
                new_artifacts={"output": (payload, "model_output")},
            )
        assert raised.value.reason_code == "event_write_failed"
    assert _artifact_path(root, payload).read_bytes() == payload
    events = events_of(root, started.run_id)
    assert [e.seq for e in events] == [1]
    connection = sqlite3.connect(root / store_module.DATABASE_NAME)
    try:
        digests = [row[0] for row in connection.execute("SELECT sha256 FROM artifacts")]
    finally:
        connection.close()
    assert hashlib.sha256(payload).hexdigest() not in digests


# --- Human review links -----------------------------------------------------


def _review(store, run_id, target, **overrides):
    values = dict(
        item_id=cr.ITEM_ID,
        target_event_id=target,
        finding="insufficient evidence",
        disposition="revised",
        label_assessment="correct",
        evidence_assessment="unsupported",
        cited_labels=["S1.L03", "S1.L04", "S1.L05"],
        reason_code="no_matching_document",
    )
    values.update(overrides)
    return store.record_human_assessment(run_id, **values)


def test_review_links_to_other_runs_items_or_non_results_fail_before_append(root, clock):
    first = run_case(root, clock)
    second = run_case(root, clock)
    first_events = events_of(root, first.run_id)
    second_events = events_of(root, second.run_id)
    with ReviewStore.open(root, now=clock.now) as store:
        own_human = _review(store, first.run_id, event_of(first_events, "model").event_id)
        other_human = _review(store, second.run_id, event_of(second_events, "model").event_id)
        cases = [
            ({"target_event_id": event_of(second_events, "model").event_id}, "review_target_invalid"),
            ({"target_event_id": first_events[0].event_id}, "review_target_invalid"),
            ({"target_event_id": "00000000-0000-4000-8000-00000000ffff"}, "review_target_invalid"),
            ({"target_event_id": own_human.event_id}, "review_target_invalid"),
            ({"item_id": "other-item"}, "review_item_unknown"),
            ({"supersedes_event_id": other_human.event_id}, "review_supersedes_invalid"),
            ({"supersedes_event_id": event_of(first_events, "rule").event_id}, "review_supersedes_invalid"),
            ({"cited_labels": ["S1.L03", "S1.L09"]}, "review_citation_unknown"),
            ({"cited_labels": ["S1.L03-S1.L05"]}, "review_citation_unknown"),
            ({"finding": "approved"}, "review_finding_invalid"),
            ({"disposition": "overruled"}, "review_disposition_invalid"),
            ({"label_assessment": "maybe"}, "review_assessment_invalid"),
            ({"evidence_assessment": "partly"}, "review_assessment_invalid"),
            ({"reason_code": "free text reason"}, "review_reason_code_invalid"),
            ({"active_seconds": -1}, "review_active_seconds_invalid"),
            ({"note_bytes": b"\xff\xfe"}, "review_note_invalid"),
        ]
        before = len(store.list_events(first.run_id))
        for overrides, code in cases:
            target = overrides.pop("target_event_id", event_of(first_events, "model").event_id)
            with pytest.raises(StoreError) as raised:
                _review(store, first.run_id, target, **overrides)
            assert raised.value.reason_code == code, overrides
        assert len(store.list_events(first.run_id)) == before


def test_valid_corrections_keep_original_and_later_events_in_order(root, clock):
    outcome = run_case(root, clock)
    events = events_of(root, outcome.run_id)
    with ReviewStore.open(root, now=clock.now) as store:
        first = _review(store, outcome.run_id, event_of(events, "policy").event_id, disposition="accepted",
                        evidence_assessment="unknown", reason_code="other")
        second = _review(store, outcome.run_id, event_of(events, "model").event_id, supersedes_event_id=first.event_id)
        view = store.project_run(outcome.run_id)
    assert [e.event_id for e in view.human] == [first.event_id, second.event_id]
    assert view.effective_human.event_id == second.event_id
    assert view.effective_human.supersedes_event_id == first.event_id
    reopened = events_of(root, outcome.run_id)
    assert [e.event_id for e in reopened[: len(events)]] == [e.event_id for e in events]
    assert reopened[-2].record["disposition"] == "accepted"
    assert reopened[-1].record["revision_of"] == "explanation"


# --- Privacy ----------------------------------------------------------------


def _sentinel_case() -> bytes:
    text = text_fixture("cases/DC-02.txt").decode("utf-8")
    return text.replace("survey vehicle kit inventory", CASE_SENTINEL).encode("utf-8")


def test_sentinel_text_stays_out_of_metadata_summaries_and_errors(root, clock, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    checked = []
    original = store_module.assert_persistent_privacy_safe

    def spy(payload, **kwargs):
        checked.append(payload)
        return original(payload, **kwargs)

    monkeypatch.setattr(store_module, "assert_persistent_privacy_safe", spy)
    model = ScriptedModel(reply(reason=f"{MODEL_SENTINEL} explains the register"))
    outcome = run_case(root, clock, model=model, case_bytes=_sentinel_case())
    events = events_of(root, outcome.run_id)
    with ReviewStore.open(root, now=clock.now) as store:
        _review(store, outcome.run_id, event_of(events, "model").event_id, note_bytes=NOTE_SENTINEL.encode("utf-8"))
        with pytest.raises(StoreError) as raised:
            _review(store, outcome.run_id, event_of(events, "model").event_id, cited_labels=[CASE_SENTINEL])
        summary = store.summarize()
        view = store.project_run(outcome.run_id)

    assert checked, "metadata records must pass the persistent privacy invariant"
    stored = metadata_text(root)
    rendered = json.dumps(summary) + json.dumps(view.overall) + str(raised.value)
    for sentinel in (CASE_SENTINEL, MODEL_SENTINEL, NOTE_SENTINEL):
        assert sentinel not in stored
        assert sentinel not in rendered
    assert_persistent_privacy_safe(summary)
    assert CASE_SENTINEL.encode() in model.sent[0]
    assert not (tmp_path / ".triagecore").exists()


def test_standard_ledger_is_neither_created_nor_modified(root, clock, tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    (workspace / ".triagecore").mkdir(parents=True)
    ledger = workspace / ".triagecore" / "ledger.jsonl"
    ledger.write_bytes(b'{"event": "existing"}\n')
    before = ledger.read_bytes()
    monkeypatch.chdir(workspace)
    run_case(root, clock)
    assert ledger.read_bytes() == before
    assert sorted(p.name for p in (workspace / ".triagecore").iterdir()) == ["ledger.jsonl"]


# --- Measurements -----------------------------------------------------------


def test_summary_reports_known_counts_coverage_and_missing(root, clock):
    measured = run_case(root, clock, model=ScriptedModel(reply(), runtime={"eval_duration_ns": 2_000_000_000}))
    unknown = run_case(root, clock, model=ScriptedModel(reply(), runtime={}))
    run_case(root, clock, model=ScriptedModel(reply(), runtime={"eval_duration_ns": 4_000_000_000}))
    with ReviewStore.open(root, now=clock.now) as store:
        stopped = local.run_review(
            store,
            workflow_ref="docrev-v1",
            case_bytes=text_fixture("cases/DC-02.txt"),
            model=ScriptedModel(reply()),
            confirm_local_runtime=False,
            clock=clock,
        )
        for outcome, seconds in ((measured, 30.0), (unknown, None)):
            model_event = event_of(store.list_events(outcome.run_id), "model")
            _review(store, outcome.run_id, model_event.event_id, active_seconds=seconds)
        summary = store.summarize()

    assert stopped.status == "stopped"
    generation = summary["metrics"]["model_generation_s"]
    assert (generation["eligible"], generation["known"], generation["missing"]) == (3, 2, 1)
    assert generation["coverage"] == pytest.approx(2 / 3, abs=1e-4)
    assert generation["sum"] == pytest.approx(6.0)
    assert generation["mean"] == pytest.approx(3.0)
    active = summary["metrics"]["active_operator_s"]
    assert (active["eligible"], active["known"], active["missing"]) == (2, 1, 1)
    assert active["sum"] == pytest.approx(30.0)
    to_policy = summary["metrics"]["end_to_end_to_policy_s"]
    assert (to_policy["eligible"], to_policy["known"], to_policy["missing"]) == (3, 3, 0)
    to_decision = summary["metrics"]["end_to_end_to_decision_s"]
    assert (to_decision["eligible"], to_decision["known"]) == (2, 2)
    assert summary["attempt_status_counts"] == {"returned_valid": 3, "stopped": 1}
    human = [e for e in events_of(root, unknown.run_id) if e.step == "human"][0]
    assert human.record["measurements"]["active_operator_s"] == "unknown"
    assert human.record["measurements"]["model_generation_s"] == "inapplicable"
