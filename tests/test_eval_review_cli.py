import json
import sys
from pathlib import Path

import pytest

from triage_core.review_result import BOUNDARY, build_review_result

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "evals" / "model_review"
EXAMPLE_SUBMISSION = str(FIXTURE_DIR / "review_submission_v0.example.json")
EXAMPLE_PACKET = str(FIXTURE_DIR / "review_context_packet.example.md")


def run_cli(monkeypatch, args):
    from triage_core.tc_cli import main

    monkeypatch.setattr(sys, "argv", ["tc"] + args)
    try:
        main()
        return 0
    except SystemExit as exc:
        return exc.code if exc.code is not None else 0


def write_json(path, obj):
    Path(path).write_text(json.dumps(obj), encoding="utf-8")
    return str(path)


def passing_submission():
    return {
        "schema_version": "review_submission_v0",
        "context_packet_ref": "packet.md",
        "claims": [
            {
                "id": "s1",
                "text": "Supported.",
                "category": "context-supported",
                "citation": "FILE: a.txt",
            },
            {"id": "n1", "text": "Next action.", "category": "authorized-next-action"},
        ],
        "declared_scope": ["docs/"],
    }


def passing_packet(path):
    Path(path).write_text(
        "---\nFILE: a.txt\n---\nsome content\n", encoding="utf-8"
    )
    return str(path)


# --- Example fixtures: intentional FAIL ---------------------------------------


def test_example_renders_fail_and_exits_zero(monkeypatch, capsys):
    code = run_cli(
        monkeypatch,
        ["eval", "review", "--submission", EXAMPLE_SUBMISSION, "--context-packet", EXAMPLE_PACKET],
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "grounding_gate: fail" in out
    assert BOUNDARY in out


def test_fail_on_gate_exits_three_on_fail(monkeypatch, capsys):
    code = run_cli(
        monkeypatch,
        [
            "eval",
            "review",
            "--submission",
            EXAMPLE_SUBMISSION,
            "--context-packet",
            EXAMPLE_PACKET,
            "--fail-on-gate",
        ],
    )
    assert code == 3
    assert "grounding_gate: fail" in capsys.readouterr().out


# --- Passing case -------------------------------------------------------------


def test_passing_case_renders_pass_and_exits_zero(monkeypatch, capsys, tmp_path):
    sub = write_json(tmp_path / "sub.json", passing_submission())
    packet = passing_packet(tmp_path / "packet.md")
    code = run_cli(
        monkeypatch,
        ["eval", "review", "--submission", sub, "--context-packet", packet],
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "grounding_gate: pass" in out
    assert "next_safe_action: claim n1" in out


def test_fail_on_gate_exits_zero_when_passing(monkeypatch, tmp_path):
    sub = write_json(tmp_path / "sub.json", passing_submission())
    packet = passing_packet(tmp_path / "packet.md")
    code = run_cli(
        monkeypatch,
        ["eval", "review", "--submission", sub, "--context-packet", packet, "--fail-on-gate"],
    )
    assert code == 0


# --- Output modes -------------------------------------------------------------


def test_output_writes_json_and_prints_success(monkeypatch, capsys, tmp_path):
    sub = write_json(tmp_path / "sub.json", passing_submission())
    packet = passing_packet(tmp_path / "packet.md")
    out_path = tmp_path / "result.json"
    code = run_cli(
        monkeypatch,
        ["eval", "review", "--submission", sub, "--context-packet", packet, "--output", str(out_path)],
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "Success: Wrote review_result_v0 to" in out
    assert "grounding_gate:" not in out  # rendered result is not printed with --output
    written = json.loads(out_path.read_text(encoding="utf-8"))
    expected = build_review_result(
        passing_submission(), Path(packet).read_text(encoding="utf-8")
    )
    assert written == expected


def test_print_json_emits_json(monkeypatch, capsys, tmp_path):
    sub = write_json(tmp_path / "sub.json", passing_submission())
    packet = passing_packet(tmp_path / "packet.md")
    code = run_cli(
        monkeypatch,
        ["eval", "review", "--submission", sub, "--context-packet", packet, "--print-json"],
    )
    out = capsys.readouterr().out
    assert code == 0
    assert '"schema_version": "review_result_v0"' in out


# --- Scope check via --changed-path -------------------------------------------


def test_changed_path_out_of_scope_fails_gate(monkeypatch, capsys, tmp_path):
    sub = write_json(tmp_path / "sub.json", passing_submission())  # declared_scope docs/
    packet = passing_packet(tmp_path / "packet.md")
    code = run_cli(
        monkeypatch,
        [
            "eval",
            "review",
            "--submission",
            sub,
            "--context-packet",
            packet,
            "--changed-path",
            "triage_core/tc_cli.py",
            "--fail-on-gate",
        ],
    )
    out = capsys.readouterr().out
    assert code == 3
    assert "scope_check: fail" in out
    assert "out_of_scope: triage_core/tc_cli.py" in out


def test_changed_path_within_scope_passes(monkeypatch, capsys, tmp_path):
    sub = write_json(tmp_path / "sub.json", passing_submission())
    packet = passing_packet(tmp_path / "packet.md")
    code = run_cli(
        monkeypatch,
        [
            "eval",
            "review",
            "--submission",
            sub,
            "--context-packet",
            packet,
            "--changed-path",
            "docs/evals/x.md",
        ],
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "scope_check: pass" in out


# --- Input and validation errors ----------------------------------------------


def test_invalid_submission_exits_one_and_prints_no_result(monkeypatch, capsys, tmp_path):
    bad = passing_submission()
    bad["claims"][0]["category"] = "made-up-category"
    sub = write_json(tmp_path / "sub.json", bad)
    packet = passing_packet(tmp_path / "packet.md")
    code = run_cli(
        monkeypatch,
        ["eval", "review", "--submission", sub, "--context-packet", packet],
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "Submission failed validation" in out
    assert "$.claims[0].category: invalid_category" in out
    assert "grounding_gate" not in out


def test_malformed_json_submission_exits_one(monkeypatch, capsys, tmp_path):
    sub = tmp_path / "sub.json"
    sub.write_text("{not valid json", encoding="utf-8")
    packet = passing_packet(tmp_path / "packet.md")
    code = run_cli(
        monkeypatch,
        ["eval", "review", "--submission", str(sub), "--context-packet", packet],
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "Could not parse submission JSON" in out


def test_missing_submission_file_exits_one(monkeypatch, capsys, tmp_path):
    packet = passing_packet(tmp_path / "packet.md")
    code = run_cli(
        monkeypatch,
        ["eval", "review", "--submission", str(tmp_path / "nope.json"), "--context-packet", packet],
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "Submission file not found" in out


def test_missing_context_packet_exits_one(monkeypatch, capsys, tmp_path):
    sub = write_json(tmp_path / "sub.json", passing_submission())
    code = run_cli(
        monkeypatch,
        ["eval", "review", "--submission", sub, "--context-packet", str(tmp_path / "nope.md")],
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "Context packet file not found" in out


# --- Leak-safety and no command execution -------------------------------------


def test_stdout_does_not_echo_claim_text(monkeypatch, capsys, tmp_path):
    secret = "SECRET-CLAIM-TEXT-SHOULD-NOT-LEAK"
    submission = passing_submission()
    submission["claims"][0]["text"] = secret
    sub = write_json(tmp_path / "sub.json", submission)
    packet = passing_packet(tmp_path / "packet.md")
    run_cli(
        monkeypatch,
        ["eval", "review", "--submission", sub, "--context-packet", packet, "--print-json"],
    )
    assert secret not in capsys.readouterr().out


def test_validation_command_in_submission_is_never_executed(monkeypatch, capsys, tmp_path):
    submission = passing_submission()
    sentinel = tmp_path / "sentinel_should_not_be_deleted.txt"
    sentinel.write_text("still here", encoding="utf-8")
    submission["validation"] = [
        {"command": f"rm -rf {sentinel}", "recorded_result": "not_recorded"}
    ]
    sub = write_json(tmp_path / "sub.json", submission)
    packet = passing_packet(tmp_path / "packet.md")
    code = run_cli(
        monkeypatch,
        ["eval", "review", "--submission", sub, "--context-packet", packet],
    )
    assert code == 0
    assert "grounding_gate: pass" in capsys.readouterr().out
    assert sentinel.exists()  # command was recorded, never executed
