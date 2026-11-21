"""CR-138 recorded DC-02 inspection, correction, and reopen checks through the
real ``tc checklist-review`` command group (no model service)."""

import hashlib
import http.client
import os
import subprocess
import sys
from pathlib import Path

import pytest

from triage_core import checklist_review as cr
from triage_core import checklist_review_local as local
from triage_core import tc_cli
from triage_core.checklist_review_store import ReviewStore

PROJECT_ROOT = Path(__file__).parent.parent
FIXTURES = Path(__file__).parent / "fixtures" / "checklist_review"
MODEL_TAG = "qwen3.5:4b"
MODEL_DIGEST = "d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04"
RATIONALE = "The supplied register contains no EQ-INV-07 entry. Its revision-4 row belongs to EQ-INV-12."
MODEL_REASON = (
    "The controlling source contains an entry for Document ID EQ-INV-07 but only for Revision 2, "
    "while the work product specifies Revision 4."
)
NETWORK_BLOCKER = """
import socket

def _blocked(*args, **kwargs):
    raise OSError("network blocked by test")

socket.socket.connect = _blocked
socket.socket.connect_ex = _blocked
socket.create_connection = _blocked
"""


def text_fixture(relative: str) -> bytes:
    return (FIXTURES / relative).read_bytes().replace(b"\r\n", b"\n")


def tc(monkeypatch, capsys, *argv):
    monkeypatch.setattr(sys, "argv", ["tc", *[str(item) for item in argv]])
    try:
        tc_cli.main()
        code = 0
    except SystemExit as exc:
        code = exc.code
    out, err = capsys.readouterr()
    return code, out, err


def tc_process(*argv, cwd, extra_paths=()):
    env = dict(os.environ)
    paths = [str(path) for path in extra_paths] + [str(PROJECT_ROOT)]
    if env.get("PYTHONPATH"):
        paths.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(paths)
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "triage_core.tc_cli", *[str(item) for item in argv]],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


@pytest.fixture
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("no network connection may be opened")

    monkeypatch.setattr(http.client, "HTTPConnection", refuse)
    monkeypatch.setattr(local.http.client, "HTTPConnection", refuse)


@pytest.fixture
def recorded(tmp_path, monkeypatch, capsys, no_network):
    """Saved definition plus the recorded R01/DC-02 run, no human decision."""
    monkeypatch.chdir(tmp_path)
    store = tmp_path / "private-store"
    code, out, err = tc(
        monkeypatch, capsys, "checklist-review", "--store", store, "save",
        "--workflow", "docrev-v1", "--model", MODEL_TAG, "--model-digest", MODEL_DIGEST,
    )
    assert code == 0, err
    assert "docrev-v1" in out
    reply = local.RecordedReply(
        (FIXTURES / "recorded" / "R01_DC-02_slm.txt").read_bytes().decode("utf-8"),
        model_tag=MODEL_TAG,
        model_digest=MODEL_DIGEST,
        label="recorded R01/DC-02",
        refers_to="R01/DC-02/slm/M1",
    )
    with ReviewStore.open(store) as opened:
        outcome = local.run_review(
            opened,
            workflow_ref="docrev-v1",
            case_bytes=text_fixture("cases/DC-02.txt"),
            model=reply,
            confirm_local_runtime=False,
        )
        events = {(e.step, e.kind): e for e in opened.list_events(outcome.run_id)}
    return {"store": store, "run_id": outcome.run_id, "outcome": outcome, "events": events, "tmp": tmp_path}


def review_args(ctx, note_path, **overrides):
    values = {
        "--run": ctx["run_id"],
        "--item": cr.ITEM_ID,
        "--target": ctx["events"][("model", "result")].event_id,
        "--finding": "insufficient evidence",
        "--disposition": "revised",
        "--label-assessment": "correct",
        "--evidence-assessment": "unsupported",
        "--reason-code": "no_matching_document",
        "--note-file": note_path,
    }
    values.update(overrides)
    argv = ["checklist-review", "--store", ctx["store"], "review"]
    for flag, value in values.items():
        if value is not None:
            argv += [flag, value]
    for label in ("S1.L03", "S1.L04", "S1.L05"):
        argv += ["--cite", label]
    return argv


def snapshot(root: Path):
    return {
        str(path.relative_to(root)): (path.stat().st_mtime_ns, hashlib.sha256(path.read_bytes()).hexdigest())
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_recorded_dc02_run_matches_the_historical_attempt_with_no_human_decision(recorded, monkeypatch, capsys):
    events = recorded["events"]
    started = events[("attempt", "started")].record
    assert started["origin"] == "recorded"
    assert started["origin_label"] == "recorded R01/DC-02"
    assert started["refers_to"] == "R01/DC-02/slm/M1"
    assert started["runtime_confirmation"] == "inapplicable"
    assert started["case"]["sha256"] == hashlib.sha256(text_fixture("cases/DC-02.txt")).hexdigest()
    for step in ("rule", "model", "policy"):
        assert events[(step, "result")].record["finding"] == "insufficient evidence"
    assert events[("policy", "result")].record["agreement"] == "agreed"
    assert not any(step == "human" for step, _ in events)

    code, out, err = tc(monkeypatch, capsys, "checklist-review", "--store", recorded["store"], "show", "--run", recorded["run_id"])
    assert code == 0, err
    assert recorded["run_id"] in out
    assert "recorded R01/DC-02" in out
    assert "R01/DC-02/slm/M1" in out
    assert "Runtime confirmation: inapplicable" in out
    assert out.count("insufficient evidence") >= 4
    assert "agreed, evidence unassessed" in out
    assert "Human decision: none yet (review available)" in out
    assert events[("model", "result")].event_id in out


def test_show_evidence_displays_header_whole_register_and_unsupported_reason(recorded, monkeypatch, capsys):
    code, out, err = tc(
        monkeypatch, capsys, "checklist-review", "--store", recorded["store"], "show",
        "--run", recorded["run_id"], "--item", cr.ITEM_ID, "--evidence",
    )
    assert code == 0, err
    case = cr.parse_case(text_fixture("cases/DC-02.txt"))
    for label in ("WP.L02", "WP.L03", "S1.L01", "S1.L02", "S1.L03", "S1.L04", "S1.L05"):
        assert f"{label}  {case.line(label).text}" in out
    assert "Rows whose Document ID is EQ-INV-07: none" in out
    assert MODEL_REASON in out
    assert "Controlling-register rows not cited by the model: S1.L05" in out
    assert f"Run: {recorded['run_id']}" in out
    assert f"Item: {cr.ITEM_ID}" in out
    assert f"Back to run view: tc checklist-review --store <store> show --run {recorded['run_id']}" in out


def test_review_records_the_correction_without_changing_original_results(recorded, monkeypatch, capsys):
    note = recorded["tmp"] / "rationale.txt"
    note.write_text(RATIONALE, encoding="utf-8")
    before = {key: (event.event_id, event.record) for key, event in recorded["events"].items()}

    code, out, err = tc(monkeypatch, capsys, *review_args(recorded, note, **{"--active-seconds": None}))
    assert code == 0, err
    assert RATIONALE not in out

    with ReviewStore.open_readonly(recorded["store"]) as store:
        events = store.list_events(recorded["run_id"])
        after = {(e.step, e.kind): (e.event_id, e.record) for e in events if e.step != "human"}
        human = [e for e in events if e.step == "human"]
        assert after == before
        assert len(human) == 1
        record = human[0].record
        assert record["finding"] == "insufficient evidence"
        assert record["disposition"] == "revised"
        assert record["revision_of"] == "explanation"
        assert record["record_kind"] == "demonstration"
        assert record["label_assessment"] == "correct"
        assert record["evidence_assessment"] == "unsupported"
        assert record["cited_labels"] == ["S1.L03", "S1.L04", "S1.L05"]
        assert record["reason_code"] == "no_matching_document"
        assert record["measurements"]["active_operator_s"] == "unknown"
        assert human[0].target_event_id == recorded["events"][("model", "result")].event_id
        assert store.read_artifact(human[0].artifacts["note"]).data == RATIONALE.encode("utf-8")
        model_output = store.read_artifact(recorded["events"][("model", "result")].artifacts["output"])
        assert model_output.data == (FIXTURES / "recorded" / "R01_DC-02_slm.txt").read_bytes()
    database = (recorded["store"] / "checklist_review.sqlite3").read_bytes()
    assert RATIONALE.encode("utf-8") not in database
    assert MODEL_REASON.encode("utf-8") not in database

    code, out, err = tc(
        monkeypatch, capsys, "checklist-review", "--store", recorded["store"], "show",
        "--run", recorded["run_id"], "--item", cr.ITEM_ID, "--evidence",
    )
    assert code == 0, err
    assert MODEL_REASON in out
    assert RATIONALE in out
    assert "revised (explanation)" in out
    assert "demonstration" in out


def test_new_process_with_model_unavailable_reopens_read_only(recorded, monkeypatch, capsys, tmp_path):
    note = recorded["tmp"] / "rationale.txt"
    note.write_text(RATIONALE, encoding="utf-8")
    code, _, err = tc(monkeypatch, capsys, *review_args(recorded, note, **{"--active-seconds": "42"}))
    assert code == 0, err
    blocker = tmp_path / "blocker"
    blocker.mkdir()
    (blocker / "sitecustomize.py").write_text(NETWORK_BLOCKER, encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    before = snapshot(recorded["store"])

    run_view = tc_process("checklist-review", "--store", recorded["store"], "show", "--run", recorded["run_id"],
                          cwd=elsewhere, extra_paths=[blocker])
    detail = tc_process("checklist-review", "--store", recorded["store"], "show", "--run", recorded["run_id"],
                        "--item", cr.ITEM_ID, "--evidence", cwd=elsewhere, extra_paths=[blocker])

    assert run_view.returncode == 0, run_view.stderr
    assert detail.returncode == 0, detail.stderr
    ids = [recorded["events"][(step, "result")].event_id for step in ("rule", "model", "policy")]
    positions = [run_view.stdout.index(event_id) for event_id in ids]
    assert positions == sorted(positions)
    assert run_view.stdout.index("human") > positions[-1]
    assert "active operator s: 42" in run_view.stdout
    assert MODEL_REASON in detail.stdout and RATIONALE in detail.stdout
    assert f"Back to run view: tc checklist-review --store <store> show --run {recorded['run_id']}" in detail.stdout
    assert snapshot(recorded["store"]) == before
    assert list(elsewhere.iterdir()) == []


def test_removed_or_altered_artifact_shows_a_gap_and_keeps_ids_and_decision(recorded, monkeypatch, capsys):
    note = recorded["tmp"] / "rationale.txt"
    note.write_text(RATIONALE, encoding="utf-8")
    assert tc(monkeypatch, capsys, *review_args(recorded, note))[0] == 0
    output_digest = hashlib.sha256((FIXTURES / "recorded" / "R01_DC-02_slm.txt").read_bytes()).hexdigest()
    case_digest = hashlib.sha256(text_fixture("cases/DC-02.txt")).hexdigest()
    artifacts = recorded["store"] / "artifacts" / "sha256"
    (artifacts / output_digest[:2] / output_digest).unlink()
    (artifacts / case_digest[:2] / case_digest).write_bytes(b"BEGIN CASE DC-02\naltered\nEND CASE DC-02")

    for extra in ((), ("--item", cr.ITEM_ID, "--evidence")):
        code, out, err = tc(monkeypatch, capsys, "checklist-review", "--store", recorded["store"], "show",
                            "--run", recorded["run_id"], *extra)
        assert code == 0, err
        assert "evidence_missing" in out
        assert "evidence_digest_mismatch" in out
        for step in ("rule", "model", "policy"):
            assert recorded["events"][(step, "result")].event_id in out
        assert "revised (explanation)" in out
        assert MODEL_REASON not in out


def test_review_rejects_unknown_citations_and_foreign_targets_before_appending(recorded, monkeypatch, capsys):
    note = recorded["tmp"] / "rationale.txt"
    note.write_text(RATIONALE, encoding="utf-8")
    with ReviewStore.open(recorded["store"]) as store:
        other = local.run_review(
            store,
            workflow_ref="docrev-v1",
            case_bytes=text_fixture("cases/DC-03.txt"),
            model=local.ReviewModel(),
            confirm_local_runtime=False,
        )
        foreign_rule = [e for e in store.list_events(other.run_id) if e.step == "rule"][0]
        count = len(store.list_events(recorded["run_id"]))

    argv = review_args(recorded, note) + ["--cite", "S1.L09"]
    code, out, err = tc(monkeypatch, capsys, *argv)
    assert code == 1
    assert "review_citation_unknown" in err
    code, out, err = tc(monkeypatch, capsys, *review_args(recorded, note, **{"--target": foreign_rule.event_id}))
    assert code == 1
    assert "review_target_invalid" in err
    assert RATIONALE not in out + err
    with ReviewStore.open_readonly(recorded["store"]) as store:
        assert len(store.list_events(recorded["run_id"])) == count


def test_run_without_confirmation_records_a_stop_and_makes_no_request(recorded, monkeypatch, capsys):
    case_path = recorded["tmp"] / "DC-03.txt"
    case_path.write_bytes(text_fixture("cases/DC-03.txt"))
    code, out, err = tc(monkeypatch, capsys, "checklist-review", "--store", recorded["store"], "run",
                        "--workflow", "docrev-v1", "--case", case_path)
    assert code == 3
    assert "stopped" in out
    assert "runtime_locality_unconfirmed" in out
    assert "FC-233" not in out + err


def test_malformed_case_reports_a_closed_code_without_echoing_case_text(recorded, monkeypatch, capsys):
    case_path = recorded["tmp"] / "bad.txt"
    case_path.write_bytes(b"BEGIN CASE DC-09\nSENTINEL-CASE-LINE-77aa\n")
    code, out, err = tc(monkeypatch, capsys, "checklist-review", "--store", recorded["store"], "run",
                        "--workflow", "docrev-v1", "--case", case_path, "--confirm-local-runtime")
    assert code == 3
    assert "case_envelope_invalid" in out
    assert "SENTINEL-CASE-LINE-77aa" not in out + err


def test_show_fails_closed_without_creating_a_store(tmp_path, monkeypatch, capsys, recorded):
    absent = tmp_path / "absent-store"
    code, out, err = tc(monkeypatch, capsys, "checklist-review", "--store", absent, "show", "--run", recorded["run_id"])
    assert code == 1
    assert "store_missing" in err
    assert not absent.exists()
    code, out, err = tc(monkeypatch, capsys, "checklist-review", "--store", recorded["store"], "show",
                        "--run", "00000000-0000-4000-8000-000000000000")
    assert code == 1
    assert "run_unknown" in err


def test_commands_require_an_explicit_store(monkeypatch, capsys):
    code, _, err = tc(monkeypatch, capsys, "checklist-review", "save", "--workflow", "docrev-v1",
                      "--model", MODEL_TAG, "--model-digest", MODEL_DIGEST)
    assert code == 2
    assert "--store" in err


def test_build_review_registration_is_unchanged(monkeypatch, capsys):
    code, out, _ = tc(monkeypatch, capsys, "build-review", "--help")
    assert code == 0
    assert "create" in out and "decide" in out and "verify" in out
    code, out, _ = tc(monkeypatch, capsys, "checklist-review", "--help")
    assert code == 0
    for action in ("save", "run", "show", "review"):
        assert action in out
