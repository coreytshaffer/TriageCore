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


class RecordedHTTP:
    def __init__(self, monkeypatch):
        import requests

        self.calls = []
        self.error = None

        def send(adapter, request, **settings):
            self.calls.append((request, settings))
            if self.error:
                raise self.error
            response = requests.Response()
            response.status_code = 200
            response.url = request.url
            response.request = request
            response._content_consumed = True
            response._content = json.dumps({
                "models": [{"name": "observed-local"}],
                "data": [{"id": "observed-local"}],
                "message": {"content": "LOCAL_RAN"},
                "choices": [{"message": {"content": "LOCAL_RAN"}}],
                "usage": {"total_tokens": 5}
            }).encode()
            return response

        monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)

    @property
    def messages(self):
        if not self.calls:
            return None
        return json.loads(self.calls[-1][0].body)["messages"]

    @property
    def timeout(self):
        return self.calls[-1][1]["timeout"]


@pytest.fixture
def recorded_http(monkeypatch):
    return RecordedHTTP(monkeypatch)


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
        governed_context=None,
    ):
        self.packet = task_packet
        self.snapshot = snapshot
        self.decision = decision
        self.governed_context = governed_context
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
    assert client.governed_context is context
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


def test_execution_invokes_no_second_classifier_or_router(recorded_http, monkeypatch):
    import triage_core.classifier as classifier_module
    import triage_core.client as client_module

    def _forbidden(*args, **kwargs):
        raise AssertionError("execution must not re-derive governed policy")

    monkeypatch.setattr(client_module, "choose_resilience_route", _forbidden)
    monkeypatch.setattr(classifier_module.TaskClassifier, "classify", _forbidden)

    tc_cli.tc_run(_args())
    assert recorded_http.messages is not None


def test_execution_constructs_no_second_snapshot_or_decision(recorded_http, monkeypatch):
    snapshots = _spy(monkeypatch, "build_governed_run_input_snapshot")
    decisions = _spy(monkeypatch, "build_governed_decision")

    tc_cli.tc_run(_args())

    assert len(snapshots) == 1
    assert len(decisions) == 1


# --------------------------------------------------------------------------
# One assembly rule serves digests and execution alike.
# --------------------------------------------------------------------------


def test_worker_receives_the_snapshot_assembly_verbatim(recorded_http, tmp_path, monkeypatch):
    source = tmp_path / "context.txt"
    source.write_text("CONTEXT_BODY\n", encoding="utf-8")
    built = _capture_contexts(monkeypatch)

    tc_cli.tc_run(
        _args(files=[str(source)], data="INLINE_BODY"),
    )

    snapshot = built[0].snapshot
    user_message = next(
        message["content"]
        for message in recorded_http.messages
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
    recorded_http, tmp_path, monkeypatch
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

    tc_cli.tc_run(_args(files=[str(source)]))

    user_message = next(
        message["content"]
        for message in recorded_http.messages
        if message["role"] == "user"
    )
    assert "ORIGINAL_CONTEXT" in user_message
    assert "SWAPPED_CONTEXT" not in user_message
    assert user_message == built[0].snapshot.assembled_execution_bytes.decode("utf-8")


# --------------------------------------------------------------------------
# Privacy: linkage is bounded evidence and nothing more.
# --------------------------------------------------------------------------


def test_bounded_decision_id_linkage_reaches_both_payloads(recorded_http, tmp_path, monkeypatch):
    built = _capture_contexts(monkeypatch)
    tc_cli.tc_run(
        _args(ledger_dir=str(tmp_path), no_ledger=False),
    )

    decision_id = built[0].decision.decision_id
    events = _ledger_events(tmp_path / "ledger.jsonl")
    route_decision = next(e for e in events if e["event_type"] == "route_decision")
    worker_result = next(e for e in events if e["event_type"] == "worker_result")

    assert route_decision["payload"]["decision_id"] == decision_id
    assert worker_result["payload"]["decision_id"] == decision_id


def test_linkage_carries_no_prompt_data_path_or_output(recorded_http, tmp_path, monkeypatch):
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


# --------------------------------------------------------------------------
# No remaining decision-bearing recomputation on the governed path.
#
# The CR's test contract calls for proof that neither consumer invokes a second
# classifier, privacy evaluator, context planner, specialist-policy selector, or
# router. ``ProjectSteward`` and ``SpecialistRouter.route_task`` are the two that
# carry policy: the steward decides the ethical firewall, and ``route_task``
# decides offload. Both are traps, not counts -- calling either at all on the
# governed path fails.
# --------------------------------------------------------------------------


def _replace_after_seam(monkeypatch, target, attribute, replacement):
    """Swap an attribute only once the seam has built the decision.

    The seam performs the single legitimate evaluation, so a trap installed
    before it would catch that one. Installing it afterwards isolates exactly
    the question at issue: does anything *downstream* of the decision decide
    again?
    """

    original_seam = run_plan.build_governed_run_context

    def wrapper(**kwargs):
        context = original_seam(**kwargs)
        monkeypatch.setattr(target, attribute, replacement)
        return context

    monkeypatch.setattr(run_plan, "build_governed_run_context", wrapper)


def test_execution_does_not_re_evaluate_the_ethical_firewall(recorded_http, monkeypatch):
    import triage_core.project_steward as steward_module

    def _forbidden(*args, **kwargs):
        raise AssertionError(
            "the governed decision is authoritative for the ethical firewall"
        )

    _replace_after_seam(monkeypatch, steward_module.ProjectSteward, "evaluate", _forbidden)

    tc_cli.tc_run(_args())
    assert recorded_http.messages is not None


def test_execution_does_not_invoke_the_specialist_policy_selector(recorded_http, monkeypatch):
    import triage_core.routers as routers_module

    def _forbidden(*args, **kwargs):
        raise AssertionError("the specialist-policy selector must not decide again")

    monkeypatch.setattr(routers_module.SpecialistRouter, "route_task", _forbidden)
    # The live connectivity probe the selector depends on is trapped separately,
    # so a partial removal that still probes would fail here too.
    monkeypatch.setattr(
        routers_module,
        "is_internet_available",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("no live connectivity probe on the governed path")
        ),
    )

    tc_cli.tc_run(_args())
    assert recorded_http.messages is not None


def test_firewall_verdict_is_consumed_from_the_decision(recorded_http, monkeypatch):
    """A steward that would say 'clear' cannot un-stop a decision that stopped."""

    import triage_core.project_steward as steward_module

    _replace_after_seam(
        monkeypatch,
        steward_module.ProjectSteward,
        "evaluate",
        lambda *a, **k: {
            "local_result_status": "sufficient",
            "reason": "Local workers succeeded.",
            "firewall_triggered": False,
            "recommended_escalation": "none",
        },
    )

    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(
            _args(prompt="Review the sacred burial site survey"),
        )
    assert exc.value.code == 3


# --------------------------------------------------------------------------
# Execution parameters are pure projections of the classification, and have not
# drifted from the specialist router's own category tables.
# --------------------------------------------------------------------------


DETERMINISTIC_CATEGORIES = (
    "docs_update",
    "bugfix",
    "test_addition",
    "refactor",
    "packaging",
    "security_review",
    "architecture_planning",
    "blocked_or_high_risk",
)


@pytest.mark.parametrize("category", DETERMINISTIC_CATEGORIES)
def test_governed_execution_parameters_match_the_specialist_router(
    category, monkeypatch
):
    import triage_core.routers as routers_module
    from triage_core.client import _governed_execution_parameters

    # A benign low-risk prompt and a pinned offline observation, so ``route_task``
    # reaches its category tables rather than an offload branch.
    monkeypatch.setattr(routers_module, "is_internet_available", lambda *a, **k: False)
    reference = routers_module.SpecialistRouter().route_task(category, "update it", "")

    timeout, post_processor = _governed_execution_parameters(category)
    assert timeout == reference["timeout"]
    assert post_processor is reference["post_processor"]


def test_executed_timeout_is_the_timeout_the_preview_published(recorded_http, monkeypatch, capsys):
    built = _capture_contexts(monkeypatch)
    tc_cli.tc_run(_args(plan=True))
    plan_output = capsys.readouterr().out
    forecast = built[0].presentation.specialist_timeout
    assert f"specialist_timeout_forecast_seconds: {forecast}" in plan_output

    tc_cli.tc_run(_args())
    assert recorded_http.timeout == forecast


# --------------------------------------------------------------------------
# Terminal-route exit semantics (CR-125): a governed handoff is exit 3, an
# unavailable route is exit 2. The distinguishing fact is the binding outcome,
# not the route name.
# --------------------------------------------------------------------------


def test_ethical_firewall_is_a_governed_handoff_not_a_fail_closed_error(recorded_http, tmp_path):

    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(
            _args(
                prompt="Review the sacred burial site survey",
                ledger_dir=str(tmp_path),
                no_ledger=False,
            ),
        )

    assert exc.value.code == 3
    assert recorded_http.messages is None

    events = _ledger_events(tmp_path / "ledger.jsonl")
    route_decision = next(e for e in events if e["event_type"] == "route_decision")
    worker_result = next(e for e in events if e["event_type"] == "worker_result")
    assert route_decision["payload"]["selected_route"] == "human_handoff"
    assert worker_result["payload"]["selected_route"] == "human_handoff"
    assert worker_result["payload"]["worker_result_status"] == "not_attempted"
    assert worker_result["payload"]["failure_type"] == "safety_handoff"


def test_a_firewall_handoff_binds_as_primary_not_as_a_fallback(monkeypatch, capsys):
    """The two human_handoff cases are distinguishable at the binding step."""

    built = _capture_contexts(monkeypatch)
    tc_cli.tc_run(_args(plan=True, prompt="Review the sacred burial site survey"))
    capsys.readouterr()

    policy = built[0].decision.policy
    assert policy.ethical_firewall == "triggered"
    assert policy.preferred_logical_route == "human_handoff"
    assert policy.permitted_fallback_envelope == ()
    assert policy.human_review == "required"


def test_an_unbindable_local_route_is_still_fail_closed(recorded_http, tmp_path, monkeypatch):
    """The capability-driven handoff keeps its exit-2 fail-closed semantics."""

    monkeypatch.setattr(
        capability_evidence,
        "resolve_from_config",
        lambda *a, **k: capability_evidence.unknown_resolution(),
    )

    with pytest.raises(SystemExit) as exc:
        tc_cli.tc_run(
            _args(ledger_dir=str(tmp_path), no_ledger=False),
        )

    assert exc.value.code == 2
    assert recorded_http.messages is None


@pytest.fixture
def cr019_stubbed_client(monkeypatch):
    """Keep routing/evidence real and stop at the external execution boundary."""
    attempts = []

    def forbidden(*args, **kwargs):
        pytest.fail("CR-DD-019 must not create or invoke a model backend")

    def execute(engine, **kwargs):
        attempts.append(kwargs)
        return {"status": "success", "source": "local", "output": "STUB_OUTPUT",
                "worker_result_status": "completed", "validation_status": "not_run"}

    monkeypatch.setattr("requests.adapters.HTTPAdapter.send", forbidden)
    monkeypatch.setattr("triage_core.engine.TriageEngine.execute_task", execute)
    monkeypatch.setattr("triage_core.client.create_backend", forbidden)
    monkeypatch.setattr("triage_core.backends.create_backend", forbidden)
    monkeypatch.setattr(tc_cli.default_config, "get_qwen_enabled", lambda: False)
    return attempts


@pytest.mark.parametrize("prompt,risk,sensitivity,route,exit_code", [
    ("Update docs about sudo", "high", "high", "human_handoff", 2),
    ("Design the architecture", "low", "medium", "local_heavy", None),
    ("Review the sacred burial site survey", "low", "low", "human_handoff", 3),
])
def test_cr019_governed_risk_and_sensitivity_reach_actual_events(
    tmp_path, monkeypatch, cr019_stubbed_client, prompt, risk, sensitivity, route, exit_code
):
    built = _capture_contexts(monkeypatch)
    attempts = cr019_stubbed_client
    args = _args(prompt=prompt, task_id="cr019-task", no_ledger=False, ledger_dir=str(tmp_path))
    if exit_code is None:
        tc_cli.tc_run(args)
    else:
        with pytest.raises(SystemExit) as caught:
            tc_cli.tc_run(args)
        assert caught.value.code == exit_code
    events = _ledger_events(tmp_path / "ledger.jsonl")
    route_event = next(e["payload"] for e in events if e["event_type"] == "route_decision")
    assert route_event["task_sensitivity"] == sensitivity
    assert route_event["governed_risk_posture"] == risk
    assert route_event["selected_route"] == route
    assert route_event["binding_outcome"] == "primary"
    assert route_event["binding_reason_codes"] == (
        ["terminal_human_handoff"] if route == "human_handoff" else ["bound_preferred_route"]
    )
    assert route_event["decision_id"] == built[0].decision.decision_id
    assert route_event["reason"] == built[0].decision.policy.route_reason_codes[0]
    assert len(attempts) == (1 if route == "local_heavy" else 0)
    workers = [e["payload"] for e in events if e["event_type"] == "worker_result"]
    assert len(workers) == (0 if exit_code == 2 else 1)
    for payload in [route_event, *workers]:
        assert_persistent_privacy_safe(payload)
        for key in ("decision_id", "governed_risk_posture", "binding_outcome", "binding_reason_codes"):
            assert payload[key] == route_event[key]
    assert [e["event_type"] for e in events] == (
        ["task_created", "runner_selected", "route_audit", "route_decision"]
        + (["worker_result"] if workers else [])
    )
    from triage_core.task_ledger import TaskLedger
    reduced = TaskLedger(str(tmp_path)).get_task("cr019-task")
    assert reduced.selected_route == route
    assert reduced.route_reason == route_event["reason"]


def test_cr019_fallback_explains_binding_without_changing_decision(
    tmp_path, monkeypatch, cr019_stubbed_client
):
    expected = run_plan.build_governed_run_context(
        prompt="Fix the bug", sources=(), inline_data=None, privacy="local_only",
        allow_cloud=False, model_profile="generic-8k", task_id="cr019-fallback",
    )
    fast_only = capability_evidence.resolve_capability(
        record=None, declare_local_fast=True, declare_local_heavy=False,
        local_fast_model=LOCAL_FAST_MODEL, local_heavy_model="",
        config_reference="test:[capability]", freshness_seconds=300,
    )
    monkeypatch.setattr(capability_evidence, "resolve_from_config", lambda *a, **k: fast_only)
    built = _capture_contexts(monkeypatch)
    attempts = cr019_stubbed_client
    tc_cli.tc_run(_args(prompt="Fix the bug", task_id="cr019-fallback", no_ledger=False,
                        ledger_dir=str(tmp_path)))
    assert serialize_governed_decision(built[0].decision) == serialize_governed_decision(expected.decision)
    assert len(attempts) == 1
    events = _ledger_events(tmp_path / "ledger.jsonl")
    for payload in [e["payload"] for e in events if e["event_type"] in {"route_decision", "worker_result"}]:
        assert payload["selected_route"] == "local_fast"
        assert payload["selected_model"] == LOCAL_FAST_MODEL
        assert payload["fallback_depth"] == 1
        assert payload["reason"] == "local_heavy_available_for_medium_or_complex_task"
        assert payload["binding_outcome"] == "authorized_fallback"
        assert payload["binding_reason_codes"] == [
            "local_capability_unavailable", "bound_authorized_fallback"
        ]


def test_cr019_unknown_routes_keep_duplicate_causes_and_block_before_execution(
    tmp_path, monkeypatch, cr019_stubbed_client
):
    monkeypatch.setattr(capability_evidence, "resolve_from_config",
                        lambda *a, **k: capability_evidence.unknown_resolution())
    attempts = cr019_stubbed_client
    with pytest.raises(SystemExit) as caught:
        tc_cli.tc_run(_args(no_ledger=False, ledger_dir=str(tmp_path)))
    assert caught.value.code == 2
    assert attempts == []
    events = _ledger_events(tmp_path / "ledger.jsonl")
    assert not any(e["event_type"] == "worker_result" for e in events)
    route = next(e["payload"] for e in events if e["event_type"] == "route_decision")
    assert route["binding_outcome"] == "authorized_fallback"
    assert route["fallback_depth"] == 2
    assert route["binding_reason_codes"] == [
        "local_capability_unknown", "local_capability_unknown", "terminal_human_handoff"
    ]


# CR-135. Observe prepared HTTP requests at the last boundary before I/O.
@pytest.mark.parametrize(("protocol", "base_url", "discovery", "generation"), [
    ("ollama", "http://127.0.0.1:11434", "/api/tags", "/api/chat"),
    ("lmstudio", "http://[::1]:1234/v1", "/models", "/chat/completions"),
])
def test_local_only_discovery_and_generation_stay_on_device(
    monkeypatch, recorded_http, protocol, base_url, discovery, generation
):
    monkeypatch.setenv("TRIAGE_BACKEND_TYPE", protocol)
    monkeypatch.setenv("TRIAGE_BASE_URL", base_url)
    monkeypatch.setenv("TRIAGE_MODEL", "auto")
    monkeypatch.setenv("TRIAGE_QWEN_API_KEY", "synthetic-qwen-test-key")
    monkeypatch.setenv("TRIAGE_QWEN_ENABLED", "1")
    capability = capability_evidence.resolve_capability(
        record=None, declare_local_fast=True, declare_local_heavy=True,
        local_fast_model="auto", local_heavy_model="auto",
        config_reference="test:auto", freshness_seconds=300,
    )
    monkeypatch.setattr(capability_evidence, "resolve_from_config", lambda *a, **k: capability)
    contexts = _capture_contexts(monkeypatch)
    tc_cli.tc_run(_args(data="SYNTHETIC_LOCAL_MARKER"))
    assert contexts[0].qwen_api_key is None
    requests = [request for request, _ in recorded_http.calls]
    assert [(r.method, r.url) for r in requests] == [
        ("GET", base_url + discovery), ("POST", base_url + generation)
    ]
    assert all("Authorization" not in r.headers for r in requests)
    assert b"SYNTHETIC_LOCAL_MARKER" in requests[1].body


@pytest.mark.parametrize("preview", [False, True])
def test_nonlocal_backend_refused_before_any_send(monkeypatch, recorded_http, preview, capsys):
    monkeypatch.setenv("TRIAGE_BACKEND_TYPE", "ollama")
    monkeypatch.setenv("TRIAGE_BASE_URL", "http://203.0.113.5:11434")
    with pytest.raises(SystemExit) as refused:
        tc_cli.tc_run(_args(plan=preview))
    assert refused.value.code == 2
    assert "endpoint_not_device_local" in capsys.readouterr().out
    assert recorded_http.calls == []


@pytest.mark.parametrize("url", [
    "https://example.invalid/compatible-mode/v1",
    "http://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    "https://dashscope-intl.aliyuncs.com:444/compatible-mode/v1",
    "https://dashscope-intl.aliyuncs.com/v1",
])
def test_unapproved_qwen_destination_stops_whole_attempt(monkeypatch, recorded_http, url, capsys):
    monkeypatch.setenv("TRIAGE_QWEN_ENABLED", "1")
    monkeypatch.setenv("TRIAGE_QWEN_API_KEY", "synthetic-qwen-test-key")
    monkeypatch.setenv("TRIAGE_QWEN_BASE_URL", url)
    with pytest.raises(SystemExit) as refused:
        tc_cli.tc_run(_args(privacy="public", allow_cloud=True))
    assert refused.value.code == 2
    assert recorded_http.calls == []
    diagnostic = capsys.readouterr().out
    assert "send_count=0" in diagnostic
    assert "synthetic-qwen-test-key" not in diagnostic and url not in diagnostic


def test_qwen_key_reaches_only_approved_provider(monkeypatch, recorded_http, tmp_path, capsys):
    key = "synthetic-qwen-test-key"
    monkeypatch.setenv("TRIAGE_QWEN_ENABLED", "1")
    monkeypatch.setenv("TRIAGE_QWEN_API_KEY", key)
    monkeypatch.setenv("TRIAGE_QWEN_MODEL", "qwen-max")
    monkeypatch.setenv("TRIAGE_QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
    monkeypatch.setattr(capability_evidence, "resolve_from_config",
                        lambda *a, **k: capability_evidence.unknown_resolution())
    contexts = _capture_contexts(monkeypatch)
    tc_cli.tc_run(_args(privacy="public", allow_cloud=True, no_ledger=False,
                        ledger_dir=str(tmp_path)))
    assert len(recorded_http.calls) == 1
    request, settings = recorded_http.calls[0]
    assert (request.method, request.url) == (
        "POST", "https://dashscope-intl.aliyuncs.com:443/compatible-mode/v1/chat/completions"
    )
    assert request.headers["Authorization"] == "Bearer " + key
    assert settings["proxies"] == {}
    output = capsys.readouterr().out
    assert key not in output
    assert "ran locally" not in output
    bound = next(b for b in contexts[0].endpoint_bindings if b.route == "cloud_primary")
    assert f"Destination: {bound.safe_label} ({bound.identity_sha256})" in output
    assert key not in (tmp_path / "ledger.jsonl").read_text(encoding="utf-8")
    assert key not in repr(contexts[0])
    assert key.encode() not in serialize_governed_decision(contexts[0].decision)

def test_governed_loopback_ignores_proxy_netrc_and_ca_environment(monkeypatch, tmp_path):
    from test_endpoint_transport_guard import assert_loopback_environment_isolation

    def run(base_url):
        monkeypatch.setenv("TRIAGE_BACKEND_TYPE", "lmstudio")
        monkeypatch.setenv("TRIAGE_BASE_URL", base_url)
        tc_cli.tc_run(_args())

    assert_loopback_environment_isolation(monkeypatch, tmp_path, invoke=run)


def test_capability_observation_cannot_change_execution_endpoint(monkeypatch, recorded_http):
    from datetime import datetime, timezone
    from triage_core.local_backend_probe import LocalBackendProbeRecord

    monkeypatch.setenv("TRIAGE_BACKEND_TYPE", "ollama")
    monkeypatch.setenv("TRIAGE_BASE_URL", "http://127.0.0.1:11434")
    probe = LocalBackendProbeRecord(
        source_type="lm_studio", base_url="http://127.0.0.1:1234", reachable=True,
        evidence_tier="operator_recorded", observed_at=datetime.now(timezone.utc).isoformat(),
        observed_models=[LOCAL_FAST_MODEL, LOCAL_HEAVY_MODEL],
    )
    capability = capability_evidence.resolve_capability(
        record=probe, declare_local_fast=True, declare_local_heavy=True,
        local_fast_model=LOCAL_FAST_MODEL, local_heavy_model=LOCAL_HEAVY_MODEL,
        config_reference="test:capability", freshness_seconds=300,
    )
    monkeypatch.setattr(capability_evidence, "resolve_from_config", lambda *a, **k: capability)
    tc_cli.tc_run(_args())
    assert [r.url for r, _ in recorded_http.calls] == ["http://127.0.0.1:11434/api/chat"]


@pytest.mark.parametrize(("stage", "change", "code"), [
    ("before_s2", "session", "transport_settings_changed"),
    ("before_s2", "base_url", "destination_binding_mismatch"),
    ("after_s2", "transport", "transport_not_guarded"),
    ("after_s2", "base_url", "destination_binding_mismatch"),
])
def test_changed_governed_backend_fails_closed_before_io(
    monkeypatch, recorded_http, capsys, stage, change, code
):
    from triage_core import client

    original = client.verify_destination_binding

    def verify(context, backends):
        backend = backends[context.decision.policy.preferred_logical_route]
        if stage == "after_s2":
            verified = original(context, backends)
        if change == "base_url":
            backend.base_url = "http://127.0.0.1:20000"
        elif change == "session":
            backend.transport._session.trust_env = True
        else:
            backend.transport = None
        return verified if stage == "after_s2" else original(context, backends)

    monkeypatch.setattr(client, "verify_destination_binding", verify)
    with pytest.raises(SystemExit) as refused:
        tc_cli.tc_run(_args())
    assert refused.value.code == 2
    assert code in capsys.readouterr().out
    assert recorded_http.calls == []


@pytest.mark.parametrize("use_cloud", [False, True])
def test_execution_uses_verified_instance_after_persistent_engine_swap(monkeypatch, recorded_http, use_cloud):
    from unittest.mock import Mock
    from triage_core import client

    monkeypatch.setenv("TRIAGE_QWEN_ENABLED", "1")
    monkeypatch.setenv("TRIAGE_QWEN_API_KEY", "synthetic-swap-test-key")
    if use_cloud:
        monkeypatch.setattr(capability_evidence, "resolve_from_config",
                            lambda *a, **k: capability_evidence.unknown_resolution())
    constructed = []
    original_constructor = client.TriageClient.from_governed_context
    original_verify = client.verify_destination_binding
    replacement = Mock()
    invoked = []

    def construct(context):
        result = original_constructor(context)
        constructed.append(result)
        return result

    def verify(context, backends):
        verified = original_verify(context, backends)
        constructed[0].engine.backend = replacement
        constructed[0].engine = replacement
        for member in verified.values():
            generate = member.backend.generate

            def record(*args, owner=member.backend, call=generate, **kwargs):
                invoked.append(owner)
                return call(*args, **kwargs)

            monkeypatch.setattr(member.backend, "generate", record)
        return verified

    monkeypatch.setattr(client.TriageClient, "from_governed_context", staticmethod(construct))
    monkeypatch.setattr(client, "verify_destination_binding", verify)
    tc_cli.tc_run(_args(privacy="public" if use_cloud else "local_only", allow_cloud=use_cloud))
    assert len(invoked) == 1
    assert invoked[0].transport.owner is invoked[0]
    assert len(invoked[0].transport.sends) == 1
    assert len(recorded_http.calls) == 1
    assert replacement.mock_calls == []


def test_qwen_redirect_reports_one_approved_send_and_stops(monkeypatch, capsys):
    import requests
    calls = []

    def redirect(adapter, request, **settings):
        calls.append(request)
        response = requests.Response()
        response.status_code = 307
        response.headers["Location"] = "https://redirect.invalid/unused"
        response._content = b""
        response._content_consumed = True
        return response

    monkeypatch.setenv("TRIAGE_QWEN_ENABLED", "1")
    monkeypatch.setenv("TRIAGE_QWEN_API_KEY", "synthetic-redirect-key")
    monkeypatch.setenv("TRIAGE_QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")
    monkeypatch.setattr(capability_evidence, "resolve_from_config",
                        lambda *a, **k: capability_evidence.unknown_resolution())
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", redirect)
    with pytest.raises(SystemExit) as refused:
        tc_cli.tc_run(_args(privacy="public", allow_cloud=True))
    assert refused.value.code == 2
    assert [(r.url, r.headers["Authorization"]) for r in calls] == [(
        "https://dashscope-intl.aliyuncs.com:443/compatible-mode/v1/chat/completions",
        "Bearer synthetic-redirect-key"
    )]
    diagnostic = capsys.readouterr().out
    assert "endpoint_redirect_refused" in diagnostic and "send_count=1" in diagnostic
    assert "cloud_primary" in diagnostic and "POST chat/completions" in diagnostic
    assert "identity_sha256=" in diagnostic
    assert "synthetic-redirect-key" not in diagnostic
    assert "https://" not in diagnostic
