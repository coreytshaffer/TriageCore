from argparse import Namespace
import builtins
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from triage_core import tc_cli
from triage_core.classifier import TaskClassifier


def _args(prompt="Summarize the documentation", **overrides):
    values = {
        "prompt": prompt,
        "files": [],
        "data": None,
        "privacy": "local_only",
        "allow_cloud": False,
        "ledger_dir": None,
        "task_id": None,
        "output": None,
        "print_output": False,
        "no_ledger": False,
        "plan": True,
        "model": "generic-8k",
    }
    values.update(overrides)
    return Namespace(**values)


def test_plan_renders_all_sections_without_execution_or_ledger(tmp_path, monkeypatch, capsys):
    from triage_core.client import TriageClient

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        TriageClient,
        "run_task",
        lambda *args, **kwargs: pytest.fail("run_task must not be called"),
    )

    raw_prompt = "Summarize UNIQUE_RAW_PROMPT documentation"
    tc_cli.tc_run(_args(prompt=raw_prompt))

    out = capsys.readouterr().out
    for section in (
        "Task", "Context", "Privacy and Egress", "Logical Route",
        "Escalation Conditions", "Expected Verification", "Preview Boundaries",
    ):
        assert f"{section}\n" in out
    assert "output_validation: not_configured" in out
    assert "backend_probe_performed: false" in out
    assert raw_prompt not in out
    assert not (tmp_path / ".triagecore").exists()


def test_plan_context_sources_order_and_budget_match_existing_calculation(
    tmp_path, capsys
):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("a" * 40, encoding="utf-8")
    second.write_text("b" * 80, encoding="utf-8")

    tc_cli.tc_run(
        _args(files=[str(first), str(second)], data="c" * 20)
    )

    out = capsys.readouterr().out
    assert out.index(str(first)) < out.index(str(second))
    assert f"{first} (40 chars)" in out
    assert f"{second} (80 chars)" in out
    assert "inline_data_characters: 20" in out
    assert "model_profile: generic-8k" in out
    assert "usable_input_budget: 6912" in out


def test_plan_over_budget_and_repeated_output_is_identical(capsys):
    args = _args(data="x" * 30000)
    tc_cli.tc_run(args)
    first = capsys.readouterr().out
    tc_cli.tc_run(args)
    second = capsys.readouterr().out

    assert "status: over_budget" in first
    assert first == second


@pytest.mark.parametrize(
    ("privacy", "allow_cloud", "posture"),
    [
        ("external_safe", False, "eligible_but_not_authorized"),
        ("external_safe", True, "authorized_for_consideration"),
        ("public", False, "eligible_but_not_authorized"),
        ("public", True, "authorized_for_consideration"),
    ],
)
def test_plan_distinguishes_egress_from_cloud_authorization(
    privacy, allow_cloud, posture, capsys
):
    tc_cli.tc_run(_args(privacy=privacy, allow_cloud=allow_cloud))
    out = capsys.readouterr().out
    assert "egress_eligible: true" in out.lower()
    assert f"cloud_posture: {posture}" in out


def test_plan_privacy_failure_is_bounded_and_does_not_echo_match(capsys):
    secret = "123-45-6789"
    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(_args(data=secret))
    out = capsys.readouterr().out
    assert exc.value.code == 2
    assert "finding_codes=" in out
    assert secret not in out
    assert "SSN pattern" not in out


def test_plan_rejects_local_only_cloud_and_execution_flags(capsys):
    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(_args(allow_cloud=True))
    assert exc.value.code == 1
    assert "--allow-cloud cannot be used" in capsys.readouterr().out

    for field, value, flag in (
        ("output", "result.txt", "--output"),
        ("print_output", True, "--print"),
        ("ledger_dir", "ledger", "--ledger-dir"),
        ("no_ledger", True, "--no-ledger"),
    ):
        with pytest.raises(SystemExit) as exc:
            tc_cli.tc_run(_args(**{field: value}))
        assert exc.value.code == 1
        assert flag in capsys.readouterr().out


def test_plan_requires_known_model(capsys):
    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(_args(model=None))
    assert exc.value.code == 1
    assert "--model is required" in capsys.readouterr().out

    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(_args(model="missing-profile"))
    assert exc.value.code == 1
    assert "Unknown model profile" in capsys.readouterr().out


def test_plan_preserves_existing_ledger_bytes(tmp_path):
    ledger_dir = tmp_path / ".triagecore"
    ledger_dir.mkdir()
    ledger = ledger_dir / "ledger.jsonl"
    original = b'{"existing":true}\n'
    ledger.write_bytes(original)

    tc_cli.tc_run(_args())

    assert ledger.read_bytes() == original


def test_deterministic_classifier_does_not_construct_backend(monkeypatch):
    import triage_core.backends as backends

    monkeypatch.setattr(
        backends,
        "create_backend",
        lambda *args, **kwargs: pytest.fail("backend construction is forbidden"),
    )
    assert TaskClassifier.classify_deterministic("Update the docs") == "docs_update"


@pytest.mark.parametrize(
    ("prompt", "route", "review_required"),
    [
        ("Update the docs", "local_fast", "false"),
        ("Design the architecture", "local_heavy", "true"),
        ("Perform a security review", "human_handoff", "true"),
        pytest.param("Summarize the information.", "local_heavy", "false", id="information"),
        pytest.param("Summarize the transformation.", "local_heavy", "false", id="transformation"),
        pytest.param("FORMAT the scratch drive.", "human_handoff", "true", id="format-drive"),
        pytest.param("Reformat the scratch drive.", "human_handoff", "true", id="reformat-drive"),
        pytest.param("Continue formatting the scratch drive.", "human_handoff", "true", id="formatting-drive"),
        pytest.param("Remove all temporary files.", "human_handoff", "true", id="remove-all"),
        pytest.param("Delete the temporary files.", "human_handoff", "true", id="delete-files"),
        pytest.param("Wipe the scratch drive.", "human_handoff", "true", id="wipe-drive"),
    ],
)
def test_plan_renders_deterministic_route_shapes(
    prompt, route, review_required, capsys
):
    tc_cli.tc_run(_args(prompt=prompt))
    out = capsys.readouterr().out.lower()
    assert f"proposed_route: {route}" in out
    assert f"human_review_required: {review_required}" in out
    assert "backend_probe_performed: false" in out
    assert "execution_performed: false" in out


def test_plan_reports_specialist_risk_conditions_and_model_binding(capsys):
    tc_cli.tc_run(_args(prompt="Update the docs"))
    docs_out = capsys.readouterr().out
    assert "specialist_model_forecast: qwen2.5-coder:7b-triagecore" in docs_out
    assert (
        "configured_backend_binding: "
        + tc_cli.default_config.get_backend_type()
        + ":qwen2.5-coder:7b-triagecore"
    ) in docs_out

    tc_cli.tc_run(_args(prompt="pip install requests"))
    package_out = capsys.readouterr().out
    assert "deterministic_risk_level: medium" in package_out
    assert "recommended_profile: workspace-write-with-approval" in package_out
    assert "medium_risk_route_depends_on_unobserved_internet_state" in package_out

    tc_cli.tc_run(_args(prompt="Delete all files"))
    high_risk_out = capsys.readouterr().out
    assert "deterministic_risk_level: high" in high_risk_out
    assert "proposed_route: human_handoff" in high_risk_out
    assert "high_risk_requires_governed_handoff" in high_risk_out

    tc_cli.tc_run(_args(data="x" * 30001, model="generic-128k"))
    large_out = capsys.readouterr().out
    assert "large_context_route_depends_on_unobserved_internet_state" in large_out


def test_plan_output_escapes_unicode_path_and_task_id(
    tmp_path, monkeypatch, capsys
):
    source = tmp_path / "caf\u00e9-\u2603.txt"
    source.write_text("bounded", encoding="utf-8")
    monkeypatch.setenv("TRIAGE_BACKEND_TYPE", "lmstudio")
    monkeypatch.setenv("TRIAGE_BASE_URL", "http://127.0.0.1:1234/v1")

    tc_cli.tc_run(
        _args(
            prompt="Refactor this",
            files=[str(source)],
            # CR-DD-012B: the governed snapshot bounds an explicit task ID to
            # letters, marks, numbers and ``._:+-``. A non-ASCII *letter* still
            # exercises the escaping this test exists to prove; a symbol such as
            # U+2603 is now rejected at the seam rather than rendered.
            task_id="t\u00e2sk-1",
        )
    )

    out = capsys.readouterr().out
    out.encode("ascii")
    assert "t\\xe2sk-1" in out
    assert "caf\\xe9-\\u2603.txt" in out
    assert "configured_backend_binding: lmstudio:" in out


def test_local_preview_refuses_an_unsupported_configured_protocol(monkeypatch, capsys):
    monkeypatch.setenv("TRIAGE_BACKEND_TYPE", "l\u00f6cal-\u2603")
    monkeypatch.setenv("TRIAGE_BASE_URL", "http://127.0.0.1:1234/v1")

    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(_args(prompt="Refactor this"))

    assert exc.value.code == 2
    output = capsys.readouterr().out
    assert "backend_protocol_unsupported" in output
    assert "send_count=0" in output
    assert "127.0.0.1" not in output


@pytest.fixture
def isolated_backend_configuration(tmp_path, monkeypatch):
    for name in tuple(os.environ):
        if name.startswith("TRIAGE_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    return tmp_path / "triagecore.toml"


@pytest.mark.parametrize("problem", ["malformed", "unreadable", "parser_missing"])
def test_governed_preview_refuses_unreadable_configuration(
    problem, isolated_backend_configuration, monkeypatch, capsys
):
    from triage_core import config
    from triage_core.client import TriageClient

    path = isolated_backend_configuration
    path.write_text("[broken PRIVATE_VALUE" if problem == "malformed" else "[backend]",
                    encoding="utf-8")
    if problem == "unreadable":
        real_open = builtins.open

        def refuse_config(file, *args, **kwargs):
            if Path(file).resolve() == path:
                raise PermissionError("PRIVATE_VALUE")
            return real_open(file, *args, **kwargs)

        monkeypatch.setattr(builtins, "open", refuse_config)
    if problem == "parser_missing":
        monkeypatch.setattr(config, "tomllib", None)
    monkeypatch.setattr(TriageClient, "__init__", lambda *a, **kw: pytest.fail("built a client"))

    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(_args())

    assert exc.value.code == 2
    output = capsys.readouterr().out
    assert "configuration_unreadable send_count=0" in output
    assert "PRIVATE_VALUE" not in output


def test_fresh_cli_never_echoes_private_toml_parser_details(isolated_backend_configuration):
    isolated_backend_configuration.write_text("[PRIVATE_SECTION]\n[PRIVATE_SECTION]", encoding="utf-8")
    environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    result = subprocess.run(
        [sys.executable, "-B", "-m", "triage_core.tc_cli", "run", "Summarize this",
         "--plan", "--model", "generic-8k"],
        env=environment, cwd=isolated_backend_configuration.parent, capture_output=True,
        text=True, timeout=30,
    )
    assert result.returncode == 2
    assert "configuration_unreadable send_count=0" in result.stdout
    assert "PRIVATE_SECTION" not in result.stdout + result.stderr


def _destination_context(**kwargs):
    from triage_core.run_plan import build_governed_run_context

    return build_governed_run_context(
        prompt="Refactor this", sources=(), inline_data=None, privacy="local_only",
        allow_cloud=False, model_profile="generic-8k", task_id=None, **kwargs,
    )


def test_missing_configuration_uses_literal_preset_and_protects_key(
    isolated_backend_configuration, monkeypatch
):
    from triage_core.governed_decision import serialize_governed_decision

    monkeypatch.setenv("TRIAGE_QWEN_API_KEY", "synthetic-credential-a")
    first = _destination_context()
    assert first.effective_config.local_base_url.source == "preset"
    assert first.effective_config.local_base_url.value == "http://127.0.0.1:1234/v1"
    assert first.effective_config.cloud_api_key_present
    assert first.qwen_api_key is None
    assert "synthetic-credential-a" not in repr(first)
    assert b"synthetic-credential-a" not in serialize_governed_decision(first.decision)

    monkeypatch.setenv("TRIAGE_QWEN_API_KEY", "synthetic-credential-b")
    second = _destination_context()
    assert first.decision == second.decision


def test_v2_decision_binds_port_policy_and_route_order(
    isolated_backend_configuration, monkeypatch
):
    from triage_core import run_plan
    from triage_core.client import TriageClient, verify_destination_binding
    from triage_core.destination_policy import TransportPolicy

    original = _destination_context()
    assert original.decision.policy.configuration_version == "governed_decision_configuration.v2"
    assert [binding.route for binding in original.endpoint_bindings] == ["local_heavy", "local_fast"]
    with monkeypatch.context() as change:
        change.setenv("TRIAGE_BASE_URL", "http://127.0.0.1:4321/v1")
        different_port = _destination_context()
    different_policy = _destination_context(transport_policy=TransportPolicy(calls=()))
    restricted_client = TriageClient.from_governed_context(different_policy)
    restricted_routes = verify_destination_binding(different_policy, restricted_client._governed_backends)
    assert all(member.transport.transport_policy_sha256 == different_policy.transport_policy.sha256
               for member in restricted_routes.values())
    old_envelope = run_plan._route_envelope

    def exchange_local_routes(route_input):
        preferred, reason, depth, review, fallback = old_envelope(route_input)
        assert (preferred, *fallback[:1]) == ("local_heavy", "local_fast")
        return fallback[0], reason, depth, review, (preferred, *fallback[1:])

    monkeypatch.setattr(run_plan, "_route_envelope", exchange_local_routes)
    reordered = _destination_context()
    for changed in (different_port, different_policy, reordered):
        assert changed.decision.policy.configuration_sha256 != original.decision.policy.configuration_sha256
        assert changed.decision.decision_id != original.decision.decision_id


def _configured_client_digests():
    from requests.adapters import HTTPAdapter
    from triage_core.client import TriageClient, verify_destination_binding
    from triage_core.destination_policy import GuardedTransport

    class NoSendAdapter(HTTPAdapter):
        def send(self, *args, **kwargs):
            raise AssertionError("construction and verification may not send")

    def guard_with_adapter(*args, **kwargs):
        return GuardedTransport(*args, **kwargs, adapters={"http://": NoSendAdapter()})

    first = _destination_context()
    plain = TriageClient.from_governed_context(first)
    second = _destination_context()
    with patch("triage_core.backends.GuardedTransport", side_effect=guard_with_adapter):
        mounted = TriageClient.from_governed_context(second)
    first_set = verify_destination_binding(first, plain._governed_backends)
    second_set = verify_destination_binding(second, mounted._governed_backends)
    for route, member in first_set.items():
        peer = second_set[route]
        assert member.transport._seal != peer.transport._seal
        assert member.transport.transport_policy_sha256 == peer.transport.transport_policy_sha256
    assert first.decision == second.decision
    return [first.transport_policy.sha256, first.decision.policy.configuration_sha256,
            first.decision.decision_id]


def test_v2_client_digests_are_identical_across_processes(isolated_backend_configuration):
    expected = _configured_client_digests()
    test_dir = Path(__file__).resolve().parent
    environment = dict(os.environ, PYTHONPATH=os.pathsep.join(map(str, (test_dir, test_dir.parent))))
    script = ("import json\nfrom test_tc_run_plan_cli import _configured_client_digests\n"
              "print(json.dumps(_configured_client_digests()))")
    outputs = [subprocess.run(
        [sys.executable, "-B", "-c", script], check=True, capture_output=True, text=True,
        cwd=isolated_backend_configuration.parent, env=environment, timeout=30,
    ).stdout for _ in range(2)]
    assert json.loads(outputs[0]) == json.loads(outputs[1]) == expected


@pytest.mark.parametrize("claim_current_version", [False, True], ids=["historical", "v2-with-v1-digest"])
def test_old_digest_decision_is_refused_before_any_send(
    claim_current_version, isolated_backend_configuration, monkeypatch
):
    from triage_core import governed_decision as gd
    from triage_core.client import TriageClient
    from triage_core.governed_run_snapshot import sha256_digest
    from triage_core.runtime_observation import GovernedBindingError

    current = _destination_context()
    version = "governed_decision_configuration.v1"
    historical = (
        version, "cloud_backend_enabled=False", "cloud_model_binding=not_enabled",
        "local_backend_type=lmstudio", f"policy_version={gd.POLICY_VERSION}",
        f"classification_policy_version={gd.CLASSIFICATION_POLICY_VERSION}",
        f"route_policy_version={gd.ROUTE_POLICY_VERSION}",
        f"verification_policy_version={gd.VERIFICATION_POLICY_VERSION}",
    )
    with monkeypatch.context() as previous:
        if not claim_current_version:
            previous.setattr(gd, "CONFIGURATION_VERSION", version)
        old_policy = replace(
            current.decision.policy,
            configuration_version=gd.CONFIGURATION_VERSION,
            configuration_sha256=sha256_digest("\n".join(historical).encode()),
        )
        old_decision = gd.build_governed_decision(current.snapshot, old_policy)
        assert gd.verify_governed_decision_id(old_decision)

    stale = replace(current, decision=old_decision)
    client = TriageClient.from_governed_context(stale)
    monkeypatch.setattr("requests.adapters.HTTPAdapter.send",
                        lambda *a, **kw: pytest.fail("obsolete decision attempted a send"))
    with pytest.raises(GovernedBindingError) as refused:
        client.run_task(task_packet=stale.packet, snapshot=stale.snapshot,
                        decision=old_decision, governed_context=stale,
                        capability=stale.presentation.capability)
    if claim_current_version:
        assert "destination_binding_mismatch" in str(refused.value)
    assert all(not backend.transport.sends for backend in client._governed_backends.values())


def test_plan_traps_network_subprocess_backend_ledger_and_writes(
    tmp_path, monkeypatch, capsys
):
    import socket
    import triage_core.backends as backends
    import triage_core.project_steward as project_steward

    def forbidden(*args, **kwargs):
        pytest.fail("forbidden planning side effect")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(socket, "socket", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(subprocess, "check_output", forbidden)
    monkeypatch.setattr(backends, "create_backend", forbidden)
    monkeypatch.setattr(tc_cli, "TaskLedger", forbidden)
    monkeypatch.setattr(project_steward, "TaskLedger", forbidden)
    from triage_core.client import TriageClient
    monkeypatch.setattr(TriageClient, "run_task", forbidden)

    real_open = builtins.open

    def read_only_open(file, mode="r", *args, **kwargs):
        if any(marker in mode for marker in ("w", "a", "x", "+")):
            pytest.fail("planning attempted a file write")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", read_only_open)
    tc_cli.tc_run(_args())
    assert "execution_performed: false" in capsys.readouterr().out
    assert list(tmp_path.iterdir()) == []


def test_plan_forecasts_ethical_firewall_without_echo_or_ledger(
    monkeypatch, capsys
):
    import triage_core.project_steward as project_steward

    sensitive_term = "tribal"
    monkeypatch.setattr(
        project_steward,
        "TaskLedger",
        lambda *args, **kwargs: pytest.fail(
            "ethical-firewall preview must not read the ledger"
        ),
    )

    tc_cli.tc_run(_args(prompt=f"Summarize {sensitive_term} context"))

    out = capsys.readouterr().out.lower()
    assert sensitive_term not in out
    assert "ethical_firewall_status: triggered" in out
    assert "ethical_firewall_policy_source: configured_or_hardcoded" in out
    assert "ethical_firewall_recommended_escalation: human_only" in out
    assert "proposed_route: human_handoff" in out
    assert "human_review_required: true" in out
    assert "configured_backend_binding: none" in out


def test_main_parser_dispatches_plan(monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        [
            "tc",
            "run",
            "Update the docs",
            "--plan",
            "--model",
            "generic-8k",
        ],
    )
    tc_cli.main()
    assert "Preview Boundaries\n" in capsys.readouterr().out
