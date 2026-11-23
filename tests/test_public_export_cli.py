"""Grant B verification through the registered tc public-export entry point."""

import hashlib
import json
import os
import platform
import socket
import subprocess
import sys

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
        # Preflight with the frozen inputs, stamp the received answer, then evaluate.
        self.last = self.observation if self.calls < 2 else self.evaluation
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


def test_stage_flag_requires_its_full_name(monkeypatch, capsys):
    code, _, errors = invoke_tc(monkeypatch, capsys, "--st")
    assert code == 2 and "unrecognized arguments" in errors


def test_ordinary_action_requires_frozen_input_locators(monkeypatch, capsys):
    code, _, errors = invoke_tc(monkeypatch, capsys)
    assert code == 2
    assert "--proposal" in errors and "--payload" in errors and "--parent" in errors


def materialize(tmp_path, case):
    from test_public_export_staging import private_directory

    repo = tmp_path / "source"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "--template=", "--quiet", str(repo)],
        check=True, env={k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")},
    )
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

    def observed_stage(handle, payload, *, name=None):
        stage_calls.append(sha256(payload))
        return stage_payload(handle, payload, name=name)

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
        monkeypatch.setattr(cli.TerminalOperator, "_read", lambda self, prompt, script=script: script.answer(prompt))
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
            # The full operator display is a readable multi-line JSON object.
            # The final output line separately summarizes this invocation.
            screen, _ = json.JSONDecoder().raw_decode(output.lstrip())
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


def test_evaluation_default_is_read_only(monkeypatch, capsys, tmp_path):
    from triage_core import public_export_cli as cli

    inputs, repo, payload_root, evidence_root, policy = materialize(tmp_path, CORPUS["benign"][0])
    script = ConsentScript(inputs, payload_root)
    monkeypatch.setattr(cli.TerminalOperator, "_read", lambda self, prompt: script.answer(prompt))
    monkeypatch.setattr(cli, "read_system_policy", lambda: policy)
    monkeypatch.setattr(cli, "SystemClock", lambda: FixtureClock(inputs))
    code, out, _ = invoke_tc(
        monkeypatch, capsys, "--repo-root", repo, "--proposal", "proposal.json",
        "--payload", inputs["payload_locator"], "--parent", inputs["parent_locator"],
    )
    assert code == 0 and json.loads(out.splitlines()[-1])["outcome"] == ELIGIBLE
    assert script.fields == ["account_and_program"]
    assert list(payload_root.iterdir()) == list(evidence_root.iterdir()) == []


def test_explicit_source_root_must_be_an_actual_worktree_root(monkeypatch, capsys, tmp_path):
    from triage_core import public_export_cli as cli

    inputs, repo, _, _, _ = materialize(tmp_path, CORPUS["benign"][0])
    monkeypatch.setattr(cli, "read_system_policy", lambda: pytest.fail("untrusted source root accepted"))
    ordinary_dir = tmp_path / "ordinary"
    ordinary_dir.mkdir()
    (ordinary_dir / ".git").mkdir()
    for path in (ordinary_dir, repo / "docs"):
        code, out, _ = invoke_tc(
            monkeypatch, capsys, "--repo-root", path, "--proposal", "proposal.json",
            "--payload", inputs["payload_locator"], "--parent", inputs["parent_locator"],
        )
        assert code == 2 and json.loads(out)["reason_codes"] == ["source_repository_unavailable"]


def test_revision_and_source_ignore_git_overrides_and_bind_clean_package(monkeypatch, tmp_path):
    from triage_core import public_export_cli as cli

    repo = tmp_path / "checkout"
    package = repo / "triage_core"
    package.mkdir(parents=True)
    module = package / "public_export_cli.py"
    module.write_bytes(b"# synthetic implementation\n")
    subprocess.run(["git", "init", "--quiet", "--template=", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "triage_core"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "-c", "user.name=Synthetic", "-c", "user.email=fixture@example.invalid",
         "-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "Synthetic local source"],
        check=True,
    )
    expected = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    monkeypatch.setattr(cli, "__file__", str(module))
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "elsewhere"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path))
    monkeypatch.chdir(package)
    assert cli.source_repository(None) == repo
    (repo / "review-notes.txt").write_bytes(b"unrelated synthetic notes")
    assert cli.implementation_commit() == expected
    new_module = package / "untracked.py"
    new_module.write_bytes(b"pass\n")
    with pytest.raises(OSError, match="implementation_revision_unavailable"):
        cli.implementation_commit()
    new_module.unlink()
    module.write_bytes(b"pass\n")
    with pytest.raises(OSError, match="implementation_revision_unavailable"):
        cli.implementation_commit()


def test_audit_selected_empty_directory_is_read_only(monkeypatch, capsys, tmp_path):
    from triage_core import public_export_cli as cli

    _, _, payload_root, evidence_root, policy = materialize(tmp_path, CORPUS["benign"][0])
    monkeypatch.setattr(cli, "read_system_policy", lambda: policy)
    code, out, _ = invoke_tc(monkeypatch, capsys, "--audit", "--evidence-dir", evidence_root)
    assert code == 0 and json.loads(out) == {"outcome": "audit_complete", "entries": []}
    code, out, _ = invoke_tc(monkeypatch, capsys, "--audit", "--evidence-dir", payload_root)
    assert code == 2 and json.loads(out)["outcome"] == "audit_refused"
    assert list(payload_root.iterdir()) == list(evidence_root.iterdir()) == []


@pytest.mark.parametrize("flags", [("--audit",), ("--stage",), ("--stage", "--audit")])
def test_effectful_action_and_audit_require_explicit_directory(monkeypatch, capsys, flags):
    code, _, _ = invoke_tc(monkeypatch, capsys, *flags)
    assert code == 2


def test_piped_stdin_cannot_authorize_a_stage(monkeypatch):
    from triage_core import public_export_cli as cli

    class Pipe:
        def isatty(self):
            return False

    monkeypatch.setattr(sys, "stdin", Pipe())
    monkeypatch.setattr("builtins.input", lambda prompt: pytest.fail("piped response read"))
    assert cli.TerminalOperator().confirm("consent-code") is None


@pytest.mark.parametrize("answer", [
    "", "account:ordinary-1", "account:ordinary-1 wrong=none", "account:ordinary-1 approved=confirmed",
    "account:ordinary-1 approved=granted approved=none",
])
def test_malformed_terminal_attestation_fails_closed(monkeypatch, answer):
    from triage_core import public_export_cli as cli

    operator = cli.TerminalOperator()
    monkeypatch.setattr(operator, "_read", lambda prompt: answer)
    assert operator.access("provider", "surface", ("approved",)) is None


def test_decline_interrupted_record_and_retry_have_independent_evidence(
    monkeypatch, capsys, tmp_path, record_property,
):
    from triage_core import public_export_cli as cli
    from triage_core import public_export_release as release

    inputs, repo, payload_root, evidence_root, policy = materialize(tmp_path, CORPUS["benign"][0])
    monkeypatch.setattr(cli, "read_system_policy", lambda: policy)
    network = block_network(monkeypatch)
    attempts = []
    with monkeypatch.context() as patch:
        write_record = release.write_record
        for mode in ("decline", "interrupt", "retry"):
            script = ConsentScript(inputs, payload_root)
            before = set(payload_root.iterdir())

            def answer(_operator, prompt, *, script=script, mode=mode):
                value = script.answer(prompt)
                return "" if mode == "decline" and prompt.startswith("Confirmation") else value

            def record(handle, entry, *, mode=mode):
                if mode == "interrupt" and entry["kind"] == "release":
                    raise OSError("synthetic final-record failure")
                return write_record(handle, entry)

            patch.setattr(cli.TerminalOperator, "_read", answer)
            patch.setattr(cli, "SystemClock", lambda: FixtureClock(inputs))
            patch.setattr(release, "write_record", record)
            code, out, err = invoke_tc(
                monkeypatch, capsys, "--stage", "--repo-root", repo, "--proposal", "proposal.json",
                "--payload", inputs["payload_locator"], "--parent", inputs["parent_locator"],
                "--evidence-dir", evidence_root,
            )
            result = json.loads(out.splitlines()[-1])
            files = set(payload_root.iterdir()) - before
            assert script.fields == ["account_and_program", "destination_and_nonsync", "confirmation_code"]
            if mode == "decline":
                assert code == 2 and not files
                assert "confirmation_declined" in result["reason_codes"]
            else:
                assert len(files) == 1 and next(iter(files)).read_bytes() == inputs["payload"]
                assert result["outcome"] == "staged_verified"
                if mode == "interrupt":
                    assert code == 4 and "STAGED" in err and "release_record_failed" in result["reason_codes"]
                else:
                    assert code == 0
            attempts.append({
                "mode": mode, "exit_code": code, "outcome": result["outcome"],
                "responses": len(script.fields), "prompt_fields": script.fields,
                "payload_files": len(files), "attempt_id": result["attempt_id"],
            })
    code, out, _ = invoke_tc(monkeypatch, capsys, "--audit", "--evidence-dir", evidence_root)
    assert code == 0 and not network
    audit_results = {entry["attempt_id"]: entry["outcome"] for entry in json.loads(out)["entries"]}
    assert attempts[1]["attempt_id"] != attempts[2]["attempt_id"]
    assert audit_results == {attempts[1]["attempt_id"]: "outcome_unknown", attempts[2]["attempt_id"]: "staged_verified"}
    record_property("grant_b_retry", json.dumps({"attempts": attempts, "audit": audit_results}, sort_keys=True))
