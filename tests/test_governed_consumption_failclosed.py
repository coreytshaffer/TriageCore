"""CR-DD-012B: the fail-closed matrix for governed consumption.

Every condition in CR-DD-012B's fail-closed table terminates the attempt **before
backend construction or invocation**, with no backend call and no
privacy-unsafe ledger write. Termination is not repair: nothing here
revalidates-and-rebuilds, because silent recomputation is the specific failure
mode the slice exists to make impossible.

Staleness is binding-defined, not clock-defined. No test below advances a clock,
touches backend health, or reads current file contents to establish staleness.

Every test is deterministic and fully offline.

CR-DD-019 additionally covers evidence failures after a stubbed execution. Those
failures propagate without pretending that the attempt never happened or retrying.
"""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from triage_core import capability_evidence, run_plan, tc_cli
from triage_core.client import TriageClient
from triage_core.config import default_config
from triage_core.governed_decision import (
    CLASSIFICATION_POLICY_VERSION,
    CONFIGURATION_VERSION,
    POLICY_VERSION,
    ROUTE_POLICY_VERSION,
    VERIFICATION_POLICY_VERSION,
    DecisionPolicyConfiguration,
    GovernedDecisionError,
    build_governed_decision,
)
from triage_core.run_plan import build_governed_run_context
from triage_core.runtime_observation import GovernedBindingError
from triage_core.task_ledger import TaskLedger
from triage_core.task_packet import PrivacyMetadata, TaskPacket

LOCAL_FAST_MODEL = "qwen2.5-coder:7b-triagecore"
LOCAL_HEAVY_MODEL = "deepseek-r1:latest"

ZERO_DIGEST = "sha256:" + ("0" * 64)


@pytest.fixture(autouse=True)
def declared_local_capability(monkeypatch):
    resolution = capability_evidence.resolve_capability(
        record=None,
        declare_local_fast=True,
        declare_local_heavy=True,
        config_reference="test:[capability]",
        freshness_seconds=300,
        local_fast_model=LOCAL_FAST_MODEL,
        local_heavy_model=LOCAL_HEAVY_MODEL,
    )
    monkeypatch.setattr(
        capability_evidence, "resolve_from_config", lambda *a, **k: resolution
    )
    return resolution


class FailClosedBackend:
    """Fails the test if execution ever reaches a backend."""

    name = "fake"
    base_url = "http://localhost"
    model = "fake-model"

    def generate(self, messages, temperature=0.1, timeout=45, **kwargs):
        raise AssertionError("a fail-closed attempt must never reach a backend")


def _context(prompt="Summarize this text", **overrides):
    kwargs = dict(
        prompt=prompt,
        sources=(),
        inline_data=None,
        privacy="local_only",
        allow_cloud=False,
        model_profile="generic-8k",
        task_id=None,
    )
    kwargs.update(overrides)
    return build_governed_run_context(**kwargs)


def _packet(context, *, task_id="failclosed-task-1", prompt=None, data=None):
    return TaskPacket(
        prompt=(
            context.snapshot.instruction_bytes.decode("utf-8")
            if prompt is None
            else prompt
        ),
        data=(
            context.snapshot.task_data_bytes.decode("utf-8")
            if data is None
            else data
        ),
        task_id=task_id,
        privacy_metadata=PrivacyMetadata(external_model_allowed=False),
    )


def _run(context, *, snapshot=None, decision=None, packet=None, ledger=None):
    client = TriageClient(backend=FailClosedBackend())
    return client.run_task(
        task_packet=packet if packet is not None else _packet(context),
        ledger=ledger,
        task_id="failclosed-task-1",
        capability=capability_evidence.resolve_from_config(default_config),
        snapshot=context.snapshot if snapshot is None else snapshot,
        decision=context.decision if decision is None else decision,
    )


def _assert_no_governed_evidence(ledger_dir):
    path = ledger_dir / "ledger.jsonl"
    if not path.exists():
        return
    events = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert not [
        event
        for event in events
        if event["event_type"] in {"route_decision", "worker_result"}
    ]


# --------------------------------------------------------------------------
# The pair is required, and it is required to be well typed.
# --------------------------------------------------------------------------


def test_decision_supplied_without_snapshot_terminates():
    context = _context()
    client = TriageClient(backend=FailClosedBackend())
    with pytest.raises(GovernedBindingError):
        client.run_task(
            task_packet=_packet(context),
            task_id="failclosed-task-1",
            decision=context.decision,
        )


def test_snapshot_supplied_without_decision_terminates():
    context = _context()
    client = TriageClient(backend=FailClosedBackend())
    with pytest.raises(GovernedBindingError):
        client.run_task(
            task_packet=_packet(context),
            task_id="failclosed-task-1",
            snapshot=context.snapshot,
        )


def test_a_non_decision_value_terminates():
    context = _context()
    with pytest.raises(GovernedBindingError):
        _run(context, decision={"decision_id": ZERO_DIGEST})


def test_a_non_snapshot_value_terminates():
    context = _context()
    with pytest.raises(GovernedBindingError):
        _run(context, snapshot={"assembled_execution_bytes": b""})


# --------------------------------------------------------------------------
# Decision malformed, noncanonical, or decision_id mismatch.
# --------------------------------------------------------------------------


def test_a_tampered_decision_id_terminates():
    context = _context()
    tampered = replace(context.decision, decision_id=ZERO_DIGEST)
    with pytest.raises(GovernedBindingError):
        _run(context, decision=tampered)


def test_a_decision_whose_policy_was_swapped_terminates():
    """Swapping policy under a fixed ID is exactly a decision_id mismatch."""

    context = _context()
    other = _context(prompt="Fix the failing bug")
    swapped = replace(context.decision, policy=other.decision.policy)
    with pytest.raises(GovernedBindingError):
        _run(context, decision=swapped)


# --------------------------------------------------------------------------
# Execution received a snapshot other than the one governed.
# --------------------------------------------------------------------------


def test_a_foreign_snapshot_terminates():
    governed = _context()
    other = _context(prompt="Fix the failing bug")
    with pytest.raises(GovernedBindingError):
        _run(governed, snapshot=other.snapshot)


def test_a_packet_that_is_not_the_snapshot_instruction_terminates():
    context = _context()
    packet = _packet(context, prompt="Summarize something else entirely")
    with pytest.raises(GovernedBindingError):
        _run(context, packet=packet)


def test_a_packet_that_is_not_the_snapshot_task_data_terminates():
    context = _context(inline_data="ORIGINAL")
    packet = _packet(context, data="SUBSTITUTED")
    with pytest.raises(GovernedBindingError):
        _run(context, packet=packet)


# --------------------------------------------------------------------------
# Decision-relevant configuration or policy binding changed.
# --------------------------------------------------------------------------


def test_configuration_changed_after_decision_formation_terminates(monkeypatch):
    context = _context()
    monkeypatch.setattr(
        default_config, "get_backend_type", lambda: "a-different-backend"
    )
    with pytest.raises(GovernedBindingError):
        _run(context)


# --------------------------------------------------------------------------
# Privacy, egress, cloud, ethical-firewall, or human-review inconsistency.
# --------------------------------------------------------------------------


def test_runtime_privacy_posture_disagreeing_with_the_decision_terminates():
    """The decision says cloud was not requested; the packet says it was."""

    context = _context()
    packet = TaskPacket(
        prompt=context.snapshot.instruction_bytes.decode("utf-8"),
        data=context.snapshot.task_data_bytes.decode("utf-8"),
        task_id="failclosed-task-1",
        privacy_metadata=PrivacyMetadata(
            data_class="public", external_model_allowed=True
        ),
    )
    with pytest.raises(GovernedBindingError):
        _run(context, packet=packet)


def test_a_cloud_route_outside_the_egress_envelope_is_unbuildable():
    """The builder refuses it, so no such decision can reach execution."""

    context = _context()
    with pytest.raises(GovernedDecisionError):
        build_governed_decision(
            context.snapshot,
            replace(
                context.decision.policy,
                preferred_logical_route="cloud_primary",
                permitted_fallback_envelope=(),
            ),
        )


def test_an_inconsistent_human_review_posture_is_unbuildable():
    context = _context()
    with pytest.raises(GovernedDecisionError):
        build_governed_decision(
            context.snapshot,
            replace(
                context.decision.policy,
                risk_posture="high",
                human_review="not_required",
            ),
        )


def test_an_unsupported_policy_version_is_unbuildable():
    context = _context()
    with pytest.raises(GovernedDecisionError):
        replace(context.decision.policy, route_policy_version="something_else.v9")


# --------------------------------------------------------------------------
# Logical route absent or inconsistent with its envelope.
# --------------------------------------------------------------------------


def test_a_repeated_envelope_member_terminates():
    context = _context()
    duplicated = build_governed_decision(
        context.snapshot,
        replace(
            context.decision.policy,
            preferred_logical_route="local_heavy",
            permitted_fallback_envelope=("local_heavy", "human_handoff"),
        ),
    )
    with pytest.raises(GovernedBindingError):
        _run(context, decision=duplicated)


def test_no_authorized_binding_terminates_before_any_backend(monkeypatch):
    context = _context()
    stranded = build_governed_decision(
        context.snapshot,
        replace(
            context.decision.policy,
            preferred_logical_route="local_heavy",
            permitted_fallback_envelope=("local_fast",),
        ),
    )
    client = TriageClient(backend=FailClosedBackend())
    with pytest.raises(GovernedBindingError):
        client.run_task(
            task_packet=_packet(context),
            task_id="failclosed-task-1",
            capability=capability_evidence.unknown_resolution(),
            snapshot=context.snapshot,
            decision=stranded,
        )


# --------------------------------------------------------------------------
# No backend call and no privacy-unsafe ledger write on any of them.
# --------------------------------------------------------------------------


def test_a_fail_closed_attempt_writes_no_governed_evidence(tmp_path):
    governed = _context()
    other = _context(prompt="Fix the failing bug")
    ledger = TaskLedger(ledger_dir=str(tmp_path))

    with pytest.raises(GovernedBindingError):
        _run(governed, snapshot=other.snapshot, ledger=ledger)

    _assert_no_governed_evidence(tmp_path)


def test_the_cli_maps_a_fail_closed_attempt_to_exit_two(tmp_path, monkeypatch, capsys):
    """A governed-consumption inconsistency is a fail-closed exit, not a crash."""

    original = run_plan.build_governed_run_context

    def tamper(**kwargs):
        context = original(**kwargs)
        return replace(context, decision=replace(context.decision, decision_id=ZERO_DIGEST))

    monkeypatch.setattr(run_plan, "build_governed_run_context", tamper)

    args = SimpleNamespace(
        prompt="Summarize this text",
        files=[],
        data=None,
        privacy="local_only",
        allow_cloud=False,
        ledger_dir=str(tmp_path),
        task_id=None,
        output=None,
        print_output=False,
        no_ledger=False,
        plan=False,
        plan_output=None,
        model="generic-8k",
    )
    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(args, client=TriageClient(backend=FailClosedBackend()))

    assert exc.value.code == 2
    assert "failing closed" in capsys.readouterr().out
    _assert_no_governed_evidence(tmp_path)


# --------------------------------------------------------------------------
# Direct-library compatibility: a caller who supplies nothing is unaffected.
# --------------------------------------------------------------------------


def test_a_caller_supplying_no_decision_is_unaffected():
    """No decision is constructed on the caller's behalf, and none is required."""

    class EchoBackend:
        name = "fake"
        base_url = "http://localhost"
        model = "fake-model"

        def generate(self, messages, temperature=0.1, timeout=45, **kwargs):
            from triage_core.backends import BackendResponse

            return BackendResponse(
                text="LEGACY_RAN",
                raw={},
                usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                backend_name=self.name,
            )

    client = TriageClient(backend=EchoBackend())
    result = client.run_task(prompt="Summarize this text", data="body")

    assert result["status"] in {"success", "handoff_required"}
    assert "decision_id" not in result


def test_no_decision_id_linkage_without_a_decision(tmp_path):
    from triage_core.backends import BackendResponse

    class EchoBackend:
        name = "fake"
        base_url = "http://localhost"
        model = "fake-model"

        def generate(self, messages, temperature=0.1, timeout=45, **kwargs):
            return BackendResponse(
                text="LEGACY_RAN",
                raw={},
                usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                backend_name=self.name,
            )

    ledger = TaskLedger(ledger_dir=str(tmp_path))
    TriageClient(backend=EchoBackend()).run_task(
        prompt="Summarize this text",
        data="body",
        ledger=ledger,
        task_id="legacy-task-1",
    )

    events = [
        json.loads(line)
        for line in (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for event in events:
        assert "decision_id" not in event["payload"]


@pytest.fixture
def cr019_attempt(tmp_path, monkeypatch):
    """A real governed consumer with only the execution boundary stubbed."""
    context = _context()
    client = TriageClient(backend=FailClosedBackend())
    ledger = TaskLedger(str(tmp_path))
    calls = []

    def execute(**kwargs):
        calls.append(kwargs)
        return {"status": "success", "source": "local", "output": "STUB_OUTPUT",
                "worker_result_status": "completed", "validation_status": "not_run"}

    monkeypatch.setattr(client.engine, "execute_task", execute)
    return SimpleNamespace(context=context, client=client, ledger=ledger, calls=calls)


def _cr019_consume(attempt, *, no_ledger=False, context=None):
    context = attempt.context if context is None else context
    return attempt.client.run_task(
        task_packet=_packet(context), snapshot=context.snapshot, decision=context.decision,
        capability=capability_evidence.resolve_from_config(default_config),
        ledger=None if no_ledger else attempt.ledger,
    )


def _cr019_event_types(tmp_path):
    path = tmp_path / "ledger.jsonl"
    return ([json.loads(line)["event_type"] for line in path.read_text(encoding="utf-8").splitlines()]
            if path.exists() else [])


@pytest.mark.parametrize("no_ledger", [False, True])
@pytest.mark.parametrize("prompt", ["Summarize this text", "Update docs about sudo"])
@pytest.mark.parametrize("invalid_risk,reason_code", [
    ("PRIVATE_VALUE", "invalid_governed_evidence_value"),
    (None, "invalid_governed_evidence_shape"),
])
def test_cr019_invalid_route_extension_blocks_even_without_a_ledger(
    tmp_path, monkeypatch, cr019_attempt, no_ledger, prompt, invalid_risk, reason_code
):
    import triage_core.client as client_module
    original = client_module.build_route_decision_payload

    def corrupt(*args, **kwargs):
        evidence = dict(kwargs.get("governed_evidence") or {})
        evidence["governed_risk_posture"] = invalid_risk
        kwargs["governed_evidence"] = evidence
        return original(*args, **kwargs)

    monkeypatch.setattr(client_module, "build_route_decision_payload", corrupt)
    with pytest.raises(GovernedBindingError, match=f"^{reason_code}$"):
        _cr019_consume(cr019_attempt, no_ledger=no_ledger, context=_context(prompt=prompt))
    assert cr019_attempt.calls == []
    assert _cr019_event_types(tmp_path) == ([] if no_ledger else ["route_audit"])


@pytest.mark.parametrize("stage,expected_calls,expected_events", [
    ("route_decision", 0, ["route_audit"]),
    ("worker_result", 1, ["route_audit", "route_decision"]),
])
def test_cr019_persistence_failure_preserves_execution_timing_without_retry(
    tmp_path, monkeypatch, cr019_attempt, stage, expected_calls, expected_events
):
    original = cr019_attempt.ledger.append_event

    def fail_at_stage(task_id, event_type, payload):
        if event_type == stage:
            assert payload["governed_risk_posture"] == "low"
            raise OSError("injected evidence-store failure")
        return original(task_id, event_type, payload)

    monkeypatch.setattr(cr019_attempt.ledger, "append_event", fail_at_stage)
    with pytest.raises(OSError, match="^injected evidence-store failure$"):
        _cr019_consume(cr019_attempt)
    assert len(cr019_attempt.calls) == expected_calls
    assert _cr019_event_types(tmp_path) == expected_events


@pytest.mark.parametrize("prompt,expected_calls", [
    ("Summarize this text", 1), ("Review the sacred burial site survey", 0),
])
def test_cr019_worker_validation_failure_is_not_reclassified_as_preexecution(
    tmp_path, monkeypatch, cr019_attempt, prompt, expected_calls
):
    import triage_core.client as client_module
    original = client_module.build_worker_result_payload

    def corrupt(route, result):
        source = dict(route)
        source["binding_outcome"] = "primary"
        source.pop("binding_reason_codes", None)
        return original(source, result)

    monkeypatch.setattr(client_module, "build_worker_result_payload", corrupt)
    with pytest.raises(ValueError, match="^invalid_governed_evidence_shape$") as caught:
        _cr019_consume(cr019_attempt, context=_context(prompt=prompt))
    assert not isinstance(caught.value, GovernedBindingError)
    assert len(cr019_attempt.calls) == expected_calls
    assert _cr019_event_types(tmp_path) == ["route_audit", "route_decision"]
