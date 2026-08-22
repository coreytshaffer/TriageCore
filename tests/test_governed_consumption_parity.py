"""CR-DD-012B: one snapshot, one governed decision, two projections.

This file replaces ``tests/test_governed_decision_integration_absence.py``,
which guarded CR-DD-012A as an unintegrated foundation and failed by design the
moment this slice integrated it. Per CR-DD-012B approval gate 3 the guard is
*retired*, not merely deleted: the positive tests below assert the integrated
shape it previously asserted the absence of, and the two purity tests it also
carried -- which are about ``governed_decision.py`` staying free of ambient and
runtime dependencies, an invariant integration does not retire -- are carried
over verbatim at the end of this file.

Every test here is deterministic and fully offline: no network, socket,
subprocess, model call, or real runtime is involved.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from triage_core import capability_evidence, run_plan, tc_cli
from triage_core.backends import BackendResponse
from triage_core.client import TriageClient
from triage_core.governed_decision import (
    GovernedDecision,
    serialize_governed_decision,
    verify_governed_decision_id,
)
from triage_core.governed_run_snapshot import GovernedRunInputSnapshot
from triage_core.privacy_invariants import assert_persistent_privacy_safe

REPO_ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ROOT = REPO_ROOT / "triage_core"

LOCAL_FAST_MODEL = "qwen2.5-coder:7b-triagecore"
LOCAL_HEAVY_MODEL = "deepseek-r1:latest"


@pytest.fixture(autouse=True)
def declared_local_capability(monkeypatch):
    """Declare both local route classes so binding is deterministic offline."""

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


class RecordingBackend:
    name = "fake"
    base_url = "http://localhost"
    model = "fake-model"

    def __init__(self) -> None:
        self.messages = None

    def generate(self, messages, temperature=0.1, timeout=45, **kwargs):
        self.messages = messages
        return BackendResponse(
            text="LOCAL_RAN",
            raw={},
            usage={"prompt_tokens": 3, "completion_tokens": 2, "total_tokens": 5},
            backend_name=self.name,
        )


class ConsumingClient:
    """Captures exactly what the execution path was handed."""

    def __init__(self) -> None:
        self.packet = None
        self.snapshot = None
        self.decision = None

    def run_task(
        self,
        task_packet,
        ledger=None,
        task_id=None,
        capability=None,
        snapshot=None,
        decision=None,
    ):
        self.packet = task_packet
        self.snapshot = snapshot
        self.decision = decision
        self.capability = capability
        return {"status": "success", "output": "", "selected_route": "local_heavy"}


def _args(prompt="Summarize this text", **overrides):
    base = dict(
        prompt=prompt,
        files=[],
        data=None,
        privacy="local_only",
        allow_cloud=False,
        ledger_dir=None,
        task_id=None,
        output=None,
        print_output=False,
        no_ledger=True,
        plan=False,
        plan_output=None,
        model="generic-8k",
    )
    base.update(overrides)
    if base["plan"]:
        # --plan refuses the execution-only flags, including --no-ledger.
        base["no_ledger"] = False
    return SimpleNamespace(**base)


def _spy(monkeypatch, name):
    """Count calls to a ``run_plan`` collaborator without changing behavior."""

    calls = []
    original = getattr(run_plan, name)

    def wrapper(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(run_plan, name, wrapper)
    return calls


def _capture_contexts(monkeypatch):
    built = []
    original = run_plan.build_governed_run_context

    def wrapper(**kwargs):
        context = original(**kwargs)
        built.append(context)
        return context

    monkeypatch.setattr(run_plan, "build_governed_run_context", wrapper)
    return built


def _ledger_events(path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


# --------------------------------------------------------------------------
# Approval gate 3: the integrated shape. One snapshot, one governed decision,
# two projections.
# --------------------------------------------------------------------------


def test_preview_builds_exactly_one_snapshot_and_one_decision(monkeypatch, capsys):
    snapshots = _spy(monkeypatch, "build_governed_run_input_snapshot")
    decisions = _spy(monkeypatch, "build_governed_decision")

    tc_cli.tc_run(_args(plan=True))
    capsys.readouterr()

    assert len(snapshots) == 1
    assert len(decisions) == 1


def test_execution_builds_exactly_one_snapshot_and_one_decision(monkeypatch):
    snapshots = _spy(monkeypatch, "build_governed_run_input_snapshot")
    decisions = _spy(monkeypatch, "build_governed_decision")
    client = ConsumingClient()

    tc_cli.tc_run(_args(), client=client)

    assert len(snapshots) == 1
    assert len(decisions) == 1


def test_execution_receives_the_seam_snapshot_and_decision(monkeypatch):
    built = _capture_contexts(monkeypatch)
    client = ConsumingClient()

    tc_cli.tc_run(_args(), client=client)

    assert len(built) == 1
    context = built[0]
    assert client.snapshot is context.snapshot
    assert client.decision is context.decision
    assert type(client.snapshot) is GovernedRunInputSnapshot
    assert type(client.decision) is GovernedDecision
    assert verify_governed_decision_id(client.decision)


def test_preview_projects_the_seam_decision_without_recomputing_it(
    monkeypatch, capsys
):
    built = _capture_contexts(monkeypatch)
    tc_cli.tc_run(_args(plan=True))
    capsys.readouterr()

    context = built[0]
    plan = run_plan.build_run_plan(context)
    policy = context.decision.policy

    assert plan["route"] == policy.preferred_logical_route
    assert plan["classification"] == policy.classification
    assert plan["risk_level"] == policy.risk_posture
    assert plan["estimated_tokens"] == policy.estimated_input_tokens
    assert plan["usable_budget"] == policy.usable_input_tokens
    assert plan["required_checks"] == tuple(policy.required_checks)
    assert plan["permitted_fallback_envelope"] == tuple(
        policy.permitted_fallback_envelope
    )
    assert plan["human_review_required"] == (policy.human_review == "required")


# --------------------------------------------------------------------------
# Parity: preview and execution reach the same canonical decision.
# --------------------------------------------------------------------------


PARITY_CASES = [
    pytest.param({}, id="local_route"),
    pytest.param(
        {"privacy": "public", "allow_cloud": True}, id="cloud_eligible_posture"
    ),
    pytest.param({"prompt": "Delete all files"}, id="terminal_handoff"),
    pytest.param({"prompt": "Review the sacred site survey"}, id="ethical_firewall"),
    pytest.param({"data": "x" * 200}, id="fitting_context"),
    pytest.param({"data": "x" * 40000}, id="over_budget_context"),
    pytest.param({"model": "generic-128k"}, id="alternate_profile"),
]


@pytest.mark.parametrize("overrides", PARITY_CASES)
def test_preview_and_execution_reach_the_same_decision(
    tmp_path, monkeypatch, capsys, overrides
):
    preview_built = _capture_contexts(monkeypatch)
    try:
        tc_cli.tc_run(_args(plan=True, **overrides))
    except SystemExit as exc:  # a governed terminal outcome is still parity
        assert exc.code in {2, 3}
    capsys.readouterr()

    execution_built = _capture_contexts(monkeypatch)
    client = ConsumingClient()
    try:
        tc_cli.tc_run(_args(**overrides), client=client)
    except SystemExit as exc:
        assert exc.code in {2, 3}
    capsys.readouterr()

    assert preview_built and execution_built
    preview = preview_built[0]
    execution = execution_built[0]

    assert preview.decision.decision_id == execution.decision.decision_id
    assert serialize_governed_decision(preview.decision) == (
        serialize_governed_decision(execution.decision)
    )
    assert (
        preview.snapshot.assembled_execution_sha256
        == execution.snapshot.assembled_execution_sha256
    )


def test_multiple_ordered_sources_reach_the_same_decision(
    tmp_path, monkeypatch, capsys
):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"
    first.write_text("alpha", encoding="utf-8")
    second.write_text("beta", encoding="utf-8")
    files = [str(first), str(second)]

    preview_built = _capture_contexts(monkeypatch)
    tc_cli.tc_run(_args(plan=True, files=files, data="inline"))
    capsys.readouterr()

    execution_built = _capture_contexts(monkeypatch)
    tc_cli.tc_run(_args(files=files, data="inline"), client=ConsumingClient())

    assert (
        preview_built[0].decision.decision_id
        == execution_built[0].decision.decision_id
    )
    positions = [source.position for source in preview_built[0].snapshot.sources]
    assert positions == [0, 1]

    # Reordering the sources is a decision-relevant change.
    reordered = _capture_contexts(monkeypatch)
    tc_cli.tc_run(
        _args(files=list(reversed(files)), data="inline"), client=ConsumingClient()
    )
    assert (
        reordered[0].decision.decision_id
        != execution_built[0].decision.decision_id
    )


def test_a_run_without_task_id_matches_an_otherwise_identical_run(monkeypatch):
    """The generated execution-correlation ID stays out of decision identity."""

    first = _capture_contexts(monkeypatch)
    tc_cli.tc_run(_args(), client=ConsumingClient())
    second = _capture_contexts(monkeypatch)
    tc_cli.tc_run(_args(), client=ConsumingClient())

    assert first[0].decision.decision_id == second[0].decision.decision_id
    body = json.loads(serialize_governed_decision(first[0].decision))
    assert body["decision_body"]["operator_intent"]["task_id"] is None
    assert body["decision_body"]["operator_intent"]["task_id_posture"] == (
        "implicit_unassigned"
    )


# --------------------------------------------------------------------------
# No-rebuild traps.
# --------------------------------------------------------------------------


def test_projection_invokes_no_classifier_router_or_context_planner(
    monkeypatch, capsys
):
    built = _capture_contexts(monkeypatch)
    tc_cli.tc_run(_args(plan=True))
    capsys.readouterr()
    context = built[0]

    def _forbidden(*args, **kwargs):
        raise AssertionError("build_run_plan must not recompute policy")

    monkeypatch.setattr(run_plan, "choose_resilience_route", _forbidden)
    monkeypatch.setattr(run_plan, "plan_context_for_text", _forbidden)
    monkeypatch.setattr(run_plan, "scan_task_packet", _forbidden)
    monkeypatch.setattr(run_plan, "build_governed_run_input_snapshot", _forbidden)
    monkeypatch.setattr(run_plan, "build_governed_decision", _forbidden)
    monkeypatch.setattr(
        run_plan.TaskClassifier, "classify_deterministic", _forbidden
    )
    monkeypatch.setattr(run_plan.DangerDetector, "analyze", _forbidden)

    plan = run_plan.build_run_plan(context)
    assert plan["route"] == context.decision.policy.preferred_logical_route


def test_execution_invokes_no_second_classifier_or_router(monkeypatch):
    import triage_core.classifier as classifier_module
    import triage_core.client as client_module

    def _forbidden(*args, **kwargs):
        raise AssertionError("execution must not re-derive governed policy")

    monkeypatch.setattr(client_module, "choose_resilience_route", _forbidden)
    monkeypatch.setattr(classifier_module.TaskClassifier, "classify", _forbidden)

    backend = RecordingBackend()
    tc_cli.tc_run(_args(), client=TriageClient(backend=backend))
    assert backend.messages is not None


def test_execution_constructs_no_second_snapshot_or_decision(monkeypatch):
    snapshots = _spy(monkeypatch, "build_governed_run_input_snapshot")
    decisions = _spy(monkeypatch, "build_governed_decision")
    backend = RecordingBackend()

    tc_cli.tc_run(_args(), client=TriageClient(backend=backend))

    assert len(snapshots) == 1
    assert len(decisions) == 1


# --------------------------------------------------------------------------
# One assembly rule serves digests and execution alike.
# --------------------------------------------------------------------------


def test_worker_receives_the_snapshot_assembly_verbatim(tmp_path, monkeypatch):
    source = tmp_path / "context.txt"
    source.write_text("CONTEXT_BODY\n", encoding="utf-8")
    built = _capture_contexts(monkeypatch)
    backend = RecordingBackend()

    tc_cli.tc_run(
        _args(files=[str(source)], data="INLINE_BODY"),
        client=TriageClient(backend=backend),
    )

    snapshot = built[0].snapshot
    user_message = next(
        message["content"]
        for message in backend.messages
        if message["role"] == "user"
    )
    assert user_message == snapshot.assembled_execution_bytes.decode("utf-8")


def test_engine_system_message_has_not_drifted_from_the_snapshot_binding():
    """The snapshot binds a worker system message ``engine.py`` owns.

    ``engine.py`` is outside this slice's file allowlist, so the message is
    duplicated in ``run_plan``. This is the drift guard for that duplication.
    """

    source = (PRODUCTION_ROOT / "engine.py").read_text(encoding="utf-8")
    assert run_plan.WORKER_SYSTEM_MESSAGE in source


# --------------------------------------------------------------------------
# Mutation: any decision-relevant change changes the decision ID.
# --------------------------------------------------------------------------


def _decision_id(monkeypatch, **overrides):
    built = _capture_contexts(monkeypatch)
    tc_cli.tc_run(_args(**overrides), client=ConsumingClient())
    return built[0].decision.decision_id


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"prompt": "Summarize this text!"}, id="instruction"),
        pytest.param({"data": "different inline"}, id="inline_content"),
        pytest.param({"privacy": "external_safe"}, id="declared_privacy"),
        pytest.param(
            {"privacy": "public", "allow_cloud": True}, id="cloud_intent"
        ),
        pytest.param({"model": "generic-32k"}, id="model_profile"),
        pytest.param({"task_id": "explicit-task-1"}, id="task_id_posture"),
    ],
)
def test_a_decision_relevant_change_changes_the_decision_id(monkeypatch, overrides):
    baseline = _decision_id(monkeypatch)
    mutated = _decision_id(monkeypatch, **overrides)
    assert baseline != mutated


def test_changed_source_content_changes_the_decision_id(tmp_path, monkeypatch):
    source = tmp_path / "context.txt"
    source.write_text("original", encoding="utf-8")
    baseline = _decision_id(monkeypatch, files=[str(source)])

    source.write_text("modified", encoding="utf-8")
    mutated = _decision_id(monkeypatch, files=[str(source)])

    assert baseline != mutated


# --------------------------------------------------------------------------
# TOCTOU: the bytes a reviewer saw are the bytes a worker receives.
# --------------------------------------------------------------------------


def test_execution_does_not_reopen_a_source_changed_after_the_seam(
    tmp_path, monkeypatch
):
    source = tmp_path / "context.txt"
    source.write_text("ORIGINAL_CONTEXT", encoding="utf-8")

    original = run_plan.build_governed_run_context
    built = []

    def rewrite_after_seam(**kwargs):
        context = original(**kwargs)
        # The window the slice exists to close: the file changes after the
        # snapshot is built and before the worker is handed anything.
        source.write_text("SWAPPED_CONTEXT", encoding="utf-8")
        built.append(context)
        return context

    monkeypatch.setattr(run_plan, "build_governed_run_context", rewrite_after_seam)

    backend = RecordingBackend()
    tc_cli.tc_run(_args(files=[str(source)]), client=TriageClient(backend=backend))

    user_message = next(
        message["content"]
        for message in backend.messages
        if message["role"] == "user"
    )
    assert "ORIGINAL_CONTEXT" in user_message
    assert "SWAPPED_CONTEXT" not in user_message
    assert user_message == built[0].snapshot.assembled_execution_bytes.decode("utf-8")


# --------------------------------------------------------------------------
# Privacy: linkage is bounded evidence and nothing more.
# --------------------------------------------------------------------------


def test_bounded_decision_id_linkage_reaches_both_payloads(tmp_path, monkeypatch):
    built = _capture_contexts(monkeypatch)
    tc_cli.tc_run(
        _args(ledger_dir=str(tmp_path), no_ledger=False),
        client=TriageClient(backend=RecordingBackend()),
    )

    decision_id = built[0].decision.decision_id
    events = _ledger_events(tmp_path / "ledger.jsonl")
    route_decision = next(e for e in events if e["event_type"] == "route_decision")
    worker_result = next(e for e in events if e["event_type"] == "worker_result")

    assert route_decision["payload"]["decision_id"] == decision_id
    assert worker_result["payload"]["decision_id"] == decision_id


def test_linkage_carries_no_prompt_data_path_or_output(tmp_path, monkeypatch):
    source = tmp_path / "SOURCE_PATH_SENTINEL.txt"
    source.write_text("SOURCE_CONTENT_SENTINEL", encoding="utf-8")

    tc_cli.tc_run(
        _args(
            prompt="PROMPT_SENTINEL",
            data="INLINE_SENTINEL",
            files=[str(source)],
            ledger_dir=str(tmp_path),
            no_ledger=False,
        ),
        client=TriageClient(backend=RecordingBackend()),
    )

    ledger_path = tmp_path / "ledger.jsonl"
    ledger_text = ledger_path.read_text(encoding="utf-8")
    for sentinel in (
        "PROMPT_SENTINEL",
        "INLINE_SENTINEL",
        "SOURCE_CONTENT_SENTINEL",
        "LOCAL_RAN",
    ):
        assert sentinel not in ledger_text

    # The two payloads this slice adds linkage to carry no operator content at
    # all, including the source path that ``task_created.target_files`` has
    # always recorded by existing design.
    linked = [
        event
        for event in _ledger_events(ledger_path)
        if event["event_type"] in {"route_decision", "worker_result"}
    ]
    assert len(linked) == 2
    for event in linked:
        rendered = json.dumps(event["payload"])
        for sentinel in (
            "PROMPT_SENTINEL",
            "INLINE_SENTINEL",
            "SOURCE_CONTENT_SENTINEL",
            "SOURCE_PATH_SENTINEL",
            "LOCAL_RAN",
        ):
            assert sentinel not in rendered
        assert_persistent_privacy_safe(
            event["payload"], artifact_name="governed linkage payload"
        )


def test_decision_id_is_not_present_in_the_plan_artifact(tmp_path, monkeypatch, capsys):
    built = _capture_contexts(monkeypatch)
    artifact_path = tmp_path / "plan.json"

    tc_cli.tc_run(
        _args(
            plan=True,
            plan_output=str(artifact_path),
            task_id="artifact-task-1",
            no_ledger=False,
        )
    )
    capsys.readouterr()

    artifact_text = artifact_path.read_text(encoding="utf-8")
    assert built[0].decision.decision_id not in artifact_text
    assert '"decision_id"' not in artifact_text
    assert json.loads(artifact_text)["contract_version"] == "governed_run_plan.v1"


# --------------------------------------------------------------------------
# Carried over verbatim from the retired integration-absence guard. These two
# assert ``governed_decision.py`` stays free of ambient and runtime dependencies
# -- an invariant integrating the foundation does not retire.
# --------------------------------------------------------------------------


FORBIDDEN_DECISION_IMPORT_ROOTS = frozenset(
    {
        "datetime",
        "http",
        "os",
        "pathlib",
        "random",
        "requests",
        "secrets",
        "socket",
        "subprocess",
        "time",
        "urllib",
        "uuid",
    }
)
FORBIDDEN_DECISION_TRIAGE_MODULE_PARTS = frozenset(
    {
        "artifacts",
        "backends",
        "client",
        "config",
        "engine",
        "ledger",
        "model",
        "renderer",
        "router",
    }
)


def _imported_modules(tree: ast.AST) -> tuple[str, ...]:
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = ("." * node.level) + (node.module or "")
            imports.append(module)
            imports.extend(
                f"{module}.{alias.name}" if module else alias.name
                for alias in node.names
            )
    return tuple(imports)


def test_governed_decision_has_no_ambient_or_runtime_subsystem_imports() -> None:
    path = PRODUCTION_ROOT / "governed_decision.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []

    for imported in _imported_modules(tree):
        root = imported.split(".", 1)[0]
        if root in FORBIDDEN_DECISION_IMPORT_ROOTS:
            violations.append(imported)
        lowered_parts = {
            part.lower().replace("-", "_") for part in imported.split(".")
        }
        if any(
            forbidden in part
            for part in lowered_parts
            for forbidden in FORBIDDEN_DECISION_TRIAGE_MODULE_PARTS
        ):
            violations.append(imported)

    assert violations == []


def test_governed_decision_does_not_call_ambient_discovery_primitives() -> None:
    path = PRODUCTION_ROOT / "governed_decision.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    forbidden_names = {
        "open",
        "getenv",
        "getcwd",
        "time",
        "uuid1",
        "uuid4",
        "urandom",
    }
    calls = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    calls.update(
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    )
    assert calls.isdisjoint(forbidden_names)
