"""Grant B verification through the registered tc public-export entry point."""

import hashlib
import json
import platform
import re
import socket
import sys
from pathlib import Path

import pytest

from test_public_export import CORPUS, ELIGIBLE, REFUSE, REVIEW, frozen_inputs
from triage_core import tc_cli
from triage_core.public_export import evaluate_export

FROZEN_IDS = "17a65bfddbc8977820353622ae8fba681e727a29248cb75c52f1d58e13cd8def"
CASES = [
    (group, case)
    for group in ("benign", "hard_stops", "policy_controls")
    for case in CORPUS[group]
]


def sha256(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def b_policy(inputs, payload_root, evidence_root):
    """Frozen materialization. Invalid O01 stays byte-exact; V01 retains its recipient flag."""
    policy = json.loads(inputs["policy"])
    if policy == {}:
        return inputs["policy"]
    policy["version"] = 2
    policy["local_staging"] = {
        "version": 2,
        "roots": [str(payload_root)],
        "evidence_root": str(evidence_root),
        "denied_sync_roots": [],
        "clipboard": False,
    }
    return json.dumps(policy, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")


def test_revision_one_reproduces_all_accepted_decision_ids():
    ids = []
    for _, case in CASES:
        decision = evaluate_export(**frozen_inputs(case))
        ids.append((case["id"], decision.eligibility_id))
    assert len(ids) == 54
    canonical = json.dumps(sorted(ids), ensure_ascii=True, separators=(",", ":")).encode("ascii")
    assert hashlib.sha256(canonical).hexdigest() == FROZEN_IDS


class FixtureClock:
    def __init__(self, inputs):
        self.evaluation = inputs["evaluation_time"]
        answers = inputs["attestations"]
        self.observation = answers[0].observed_at if answers else self.evaluation
        self.calls = 0
        self.last = self.observation

    def now(self):
        self.last = self.observation if self.calls == 0 else self.evaluation
        self.calls += 1
        return self.last

    def monotonic(self):
        return (self.last - self.observation).total_seconds()


class ConsentScript:
    """Drive the terminal grammar; record each actual submission separately."""

    def __init__(self, inputs, payload_root):
        self.answers = inputs["attestations"]
        self.payload_root = payload_root
        self.fields = []

    def answer(self, prompt):
        if prompt.startswith("Account and program"):
            self.fields.append("account_and_program")
            if not self.answers:
                return ""
            values = " ".join(f"{a.program}={a.state}" for a in self.answers)
            return f"{self.answers[0].scope} {values}"
        if prompt.startswith("Destination"):
            self.fields.append("destination_and_nonsync")
            return f"UNSYNCED {self.payload_root}"
        if prompt.startswith("Acknowledge"):
            self.fields.append("exact_review_triggers")
            return prompt.split("[", 1)[1].split("]", 1)[0]
        if prompt.startswith("Confirmation"):
            self.fields.append("confirmation_code")
            return prompt.split("[", 1)[1].split("]", 1)[0]
        pytest.fail("Unexpected operator prompt")


def invoke_tc(monkeypatch, capsys, *args):
    monkeypatch.setattr(sys, "argv", ["tc", "public-export", *map(str, args)])
    try:
        tc_cli.main()
    except SystemExit as exc:
        code = exc.code
    else:
        code = 0
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_registered_public_export_help(monkeypatch, capsys):
    code, output, _ = invoke_tc(monkeypatch, capsys, "--help")
    assert code == 0
    assert "--stage" in output and "--audit" in output
    assert "--policy" not in output


def test_unknown_policy_override_rejected(monkeypatch, capsys):
    code, _, errors = invoke_tc(monkeypatch, capsys, "--policy", "override.json")
    assert code == 2
    assert "unrecognized arguments" in errors


def test_ordinary_action_requires_frozen_input_locators(monkeypatch, capsys):
    code, _, errors = invoke_tc(monkeypatch, capsys)
    assert code == 2
    assert "--proposal" in errors and "--payload" in errors and "--parent" in errors


def materialize(tmp_path, case):
    from test_public_export_staging import private_directory

    repo = tmp_path / "source"
    repo.mkdir()
    (repo / ".git").mkdir()
    inputs = frozen_inputs(case)
    for locator, raw in (("proposal.json", inputs["proposal"]), (inputs["parent_locator"], inputs["parent"]),
                         (inputs["payload_locator"], inputs["payload"])):
        path = repo / locator
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    payload_root = private_directory(tmp_path / "stage")
    evidence_root = private_directory(tmp_path / "audit")
    return inputs, repo, payload_root, evidence_root, b_policy(inputs, payload_root, evidence_root)


def block_network(monkeypatch):
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("Staging attempted network I/O")

    for owner, names in ((socket, ("create_connection", "getaddrinfo")),
                         (socket.socket, ("connect", "connect_ex", "send", "sendall", "sendto"))):
        for name in names:
            monkeypatch.setattr(owner, name, forbidden)
    return attempts


@pytest.mark.parametrize(("group", "case"), [
    pytest.param(group, case, id=case["id"]) for group, case in CASES
])
def test_frozen_file_stage(group, case, tmp_path, monkeypatch, capsys, record_property):
    from triage_core import public_export_cli as cli
    from triage_core import public_export_release as release

    inputs, repo, payload_root, evidence_root, policy = materialize(tmp_path, case)
    monkeypatch.setattr(cli, "read_system_policy", lambda: policy)
    network = block_network(monkeypatch)
    stage_calls = []
    stage_payload = release.stage_payload

    def observed_stage(handle, payload):
        stage_calls.append(sha256(payload))
        return stage_payload(handle, payload)

    monkeypatch.setattr(release, "stage_payload", observed_stage)
    expected = case["expected_outcome"]
    wanted_triggers = sorted(case.get("expected_triggers", []))
    wanted_reasons = set(case.get("expected_reasons", []))
    records = []
    # Same clock, paths, policy bytes and operator inputs. Each run receives fresh consent.
    for _ in range(2):
        before = set(payload_root.iterdir())
        stage_calls.clear()
        script = ConsentScript(inputs, payload_root)
        monkeypatch.setattr(cli.TerminalOperator, "_read", lambda self, prompt: script.answer(prompt))
        monkeypatch.setattr(cli, "SystemClock", lambda: FixtureClock(inputs))
        code, output, errors = invoke_tc(
            monkeypatch, capsys, "--repo-root", repo, "--proposal", "proposal.json",
            "--payload", inputs["payload_locator"], "--parent", inputs["parent_locator"],
            "--evidence-dir", evidence_root, "--stage",
        )
        result = json.loads(output.splitlines()[-1])
        added = set(payload_root.iterdir()) - before
        readbacks = sorted(sha256(path.read_bytes()) for path in added)
        assert not network
        assert result["policy_digest"] == sha256(policy)
        if expected == REFUSE:
            assert code == 2 and result["outcome"] == "ineligible", result
            assert wanted_reasons <= set(result["reason_codes"])
            assert "confirmation_code" not in script.fields
            assert not stage_calls and not added
        else:
            assert code == 0 and result["outcome"] == "staged_verified", (result, errors)
            assert result["review_triggers"] == wanted_triggers
            prompts = ["account_and_program", "destination_and_nonsync"]
            if expected == REVIEW:
                prompts.append("exact_review_triggers")
            assert script.fields == [*prompts, "confirmation_code"]
            assert len(script.fields) <= (3 if expected == ELIGIBLE else 4)
            assert stage_calls == readbacks == [sha256(inputs["payload"])]
            screen = json.loads(output.splitlines()[-2])
            assert screen["payload"].encode("utf-8") == inputs["payload"]
            assert screen["payload_digest"] == readbacks[0]
            assert screen["eligibility_id"] == result["eligibility_id"]
        records.append({
            "outcome": result["outcome"], "reasons": result["reason_codes"], "triggers": result["review_triggers"],
            "id": result["eligibility_id"], "prompt_fields": script.fields, "responses": len(script.fields),
            "stage_calls": len(stage_calls), "payload_files": len(added), "readback_digests": readbacks,
        })
    assert records[0] == records[1]
    record_property("grant_b_case", json.dumps({
        "case_id": case["id"], "group": group, "family": case["family"],
        "expected_eligibility": expected, "expected_reasons": sorted(wanted_reasons),
        "expected_triggers": wanted_triggers, "policy_digest": sha256(policy),
        "payload_digest": sha256(inputs["payload"]), "network_attempts": len(network),
        "tested_commit": cli.implementation_commit(), "platform": platform.system(),
        "argv_selections": ["repo_root", "proposal", "payload", "parent", "evidence_dir", "stage"],
        "attempts": records,
    }, sort_keys=True))
