"""Offline regressions for council dispatch, validation, and preflight.

An empty order list is valid when no work was requested, as in ordinary preflight.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from triage_core import config as config_module
from triage_core import orchestration as orchestration_module
from triage_core import project_steward as project_steward_module
from triage_core.orchestration import ProjectManager
from triage_core.project_steward import ProjectSteward
from triage_core.validator_tools import ValidationResult


class DummyWorker:
    def __init__(self, role, outputs):
        self.role = role
        self.outputs = outputs
        self.call_count = 0
        self.model = "dummy-model"

    def process(self, order, stream_callback=None):
        out = self.outputs[min(self.call_count, len(self.outputs) - 1)]
        self.call_count += 1
        return dict(out)


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Run in an empty directory so no repository config, rules, ledger or
    predictive model is read, and escalation packets land in tmp_path."""
    monkeypatch.chdir(tmp_path)
    fresh_config = config_module.Config(root_dir=str(tmp_path))
    monkeypatch.setattr(orchestration_module, "default_config", fresh_config)
    monkeypatch.setattr(project_steward_module, "default_config", fresh_config)
    return tmp_path


def _manager(workers, budgets=None):
    registry = SimpleNamespace(workers=workers, get_worker=workers.get)
    with patch.object(orchestration_module, "WorkerRegistry", return_value=registry):
        pm = ProjectManager()
    pm.budgets = dict(budgets or {})
    pm.steward = ProjectSteward(budgets=pm.budgets)
    return pm


# ── S03: requested roles that no worker can serve ──────────────────────────


def test_s03_unregistered_roles_are_insufficient(isolated_config):
    implementer = DummyWorker("implementer", [{"repaired_code": "print('ok')"}])
    pm = _manager({"implementer": implementer})

    result = pm.dispatch_task(
        prompt="Fix issues",
        target_files=["file.py"],
        # The roles the desktop Worker Council requests at 55ba42c.
        required_roles=["repo_mapper", "code_repair", "validator"],
    )

    evaluation = result["evaluation"]
    assert evaluation["local_result_status"] == "insufficient"
    assert evaluation["unroutable_roles"] == ["repo_mapper", "code_repair", "validator"]
    assert "repo_mapper, code_repair, validator" in evaluation["reason"]
    assert "No requested work order completed." in evaluation["reason"]
    assert evaluation["recommended_escalation"] == "codex"
    assert result["work_orders"] == []
    assert implementer.call_count == 0
    assert all(o.status == "failed" for o in pm.board.orders.values())
    assert result["escalation_packet"] is not None
    assert (isolated_config / result["escalation_packet"]).exists()


def test_s03_one_missing_role_is_insufficient_even_if_others_succeed(isolated_config):
    implementer = DummyWorker("implementer", [{"repaired_code": "print('ok')"}])
    pm = _manager({"implementer": implementer})

    with patch("triage_core.orchestration.ValidatorTools.run") as mock_val_run:
        mock_val_run.return_value = [ValidationResult(passed=True, validator="dummy")]
        result = pm.dispatch_task(
            prompt="Fix issues",
            target_files=["file.py"],
            required_roles=["implementer", "repo_mapper"],
        )

    evaluation = result["evaluation"]
    assert implementer.call_count == 1
    assert evaluation["local_result_status"] == "insufficient"
    assert evaluation["unroutable_roles"] == ["repo_mapper"]
    assert "No requested work order completed." not in evaluation["reason"]


def test_s03_missing_role_keeps_an_earlier_escalation_target(isolated_config):
    # A worker delegates to antigravity; the missing role must add evidence
    # without overriding that target.
    implementer = DummyWorker("implementer", [{"delegate_to": "antigravity"}])
    pm = _manager({"implementer": implementer})

    result = pm.dispatch_task(
        prompt="Extreme refactoring",
        target_files=["file.py"],
        required_roles=["implementer", "repo_mapper"],
    )

    evaluation = result["evaluation"]
    assert evaluation["local_result_status"] == "insufficient"
    assert evaluation["recommended_escalation"] == "antigravity"
    assert evaluation["reason"].startswith("Forced delegation by council worker")
    assert "repo_mapper" in evaluation["reason"]


# ── S04: validation still failing after the repair budget ──────────────────


def test_s04_exhausted_validation_is_insufficient(isolated_config):
    implementer = DummyWorker("implementer", [{"repaired_code": "print('bad')"}])
    review_worker = DummyWorker("review_worker", [{"is_valid": True, "issues_found": []}])
    pm = _manager(
        {"implementer": implementer, "review_worker": review_worker},
        budgets={"max_local_attempts": 2},
    )
    stream = []

    with patch("triage_core.orchestration.ValidatorTools.run") as mock_val_run:
        mock_val_run.return_value = [
            ValidationResult(passed=False, validator="dummy", issues=["still broken"])
        ]
        result = pm.dispatch_task(
            prompt="Fix issues",
            target_files=["file.py"],
            required_roles=["implementer", "review_worker"],
            stream_callback=stream.append,
        )

    evaluation = result["evaluation"]
    # One initial attempt plus two repairs, then exhaustion.
    assert implementer.call_count == 3
    assert mock_val_run.call_count == 3
    assert review_worker.call_count == 0
    assert evaluation["local_result_status"] == "insufficient"
    assert evaluation["recommended_escalation"] == "codex"
    assert evaluation["validation_exhausted"] is True
    assert evaluation["unroutable_roles"] == []
    assert "still failed after 2 repair attempt(s)" in evaluation["reason"]
    assert any("[ESCALATION] Validator failed after max repair" in s for s in stream)
    assert result["escalation_packet"] is not None
    assert (isolated_config / result["escalation_packet"]).exists()


def test_s04_exhaustion_without_a_stream_callback_is_insufficient(isolated_config):
    implementer = DummyWorker("implementer", [{"repaired_code": "print('bad')"}])
    pm = _manager({"implementer": implementer}, budgets={"max_local_attempts": 0})

    with patch("triage_core.orchestration.ValidatorTools.run") as mock_val_run:
        mock_val_run.return_value = [
            ValidationResult(passed=False, validator="dummy", issues=["broken"])
        ]
        result = pm.dispatch_task(
            prompt="Fix issues",
            target_files=["file.py"],
            required_roles=["implementer"],
        )

    assert implementer.call_count == 1
    assert result["evaluation"]["local_result_status"] == "insufficient"
    assert result["evaluation"]["validation_exhausted"] is True


def test_s04_recovery_within_budget_stays_sufficient(isolated_config):
    implementer = DummyWorker(
        "implementer",
        [{"repaired_code": "print('bad')"}, {"repaired_code": "print('fixed')"}],
    )
    review_worker = DummyWorker("review_worker", [{"is_valid": True, "issues_found": []}])
    pm = _manager(
        {"implementer": implementer, "review_worker": review_worker},
        budgets={"max_local_attempts": 2},
    )

    with patch("triage_core.orchestration.ValidatorTools.run") as mock_val_run:
        mock_val_run.side_effect = [
            [ValidationResult(passed=False, validator="dummy", issues=["syntax error"])],
            [ValidationResult(passed=True, validator="dummy", issues=[])],
        ]
        result = pm.dispatch_task(
            prompt="Fix issues",
            target_files=["file.py"],
            required_roles=["implementer", "review_worker"],
        )

    evaluation = result["evaluation"]
    assert evaluation["local_result_status"] == "sufficient"
    assert evaluation["validation_exhausted"] is False
    assert evaluation["unroutable_roles"] == []
    assert result["escalation_packet"] is None


# ── S07: generic checks for JSON and Markdown output ───────────────────────


@pytest.mark.parametrize(
    ("filename", "output", "validator"),
    [
        pytest.param("settings.json", '{"enabled": true}', "json_parse", id="json-object"),
        pytest.param("items.json", '["alpha", "beta"]', "json_parse", id="json-array"),
        pytest.param("flag.json", "false", "json_parse", id="json-scalar"),
        pytest.param(
            "settings.json",
            '```json\n{"enabled": true}\n```',
            "json_parse",
            id="fenced-json",
        ),
        pytest.param(
            "guide.md", "# Guide\n\nSetup instructions.", "markdown_basic", id="md"
        ),
        pytest.param(
            "guide.markdown",
            "# Guide\n\n1. Run the setup step.",
            "markdown_basic",
            id="markdown",
        ),
    ],
)
def test_s07_council_accepts_generic_json_and_markdown(
    isolated_config, filename, output, validator
):
    implementer = DummyWorker("implementer", [{"repaired_code": output}])
    reviewer = DummyWorker("review_worker", [{"is_valid": True, "issues_found": []}])
    manager = _manager({"implementer": implementer, "review_worker": reviewer})

    result = manager.dispatch_task(
        prompt="Update the sample artifact",
        target_files=[filename],
        required_roles=["implementer", "review_worker"],
    )

    assert result["evaluation"]["local_result_status"] == "sufficient"
    assert result["evaluation"]["validation_exhausted"] is False
    assert result["escalation_packet"] is None
    assert implementer.call_count == reviewer.call_count == 1
    assert result["all_orders"][0].result["validation_run"] == {
        "validators": [validator],
        "passed": True,
        "issues": [],
    }


@pytest.mark.parametrize(
    ("filename", "output", "validator"),
    [
        pytest.param("settings.json", '{"enabled":', "json_parse", id="malformed-json"),
        pytest.param(
            "settings.json", '{"value": NaN}', "json_parse", id="nonstandard-json-number"
        ),
        pytest.param("guide.md", " \n\t", "markdown_basic", id="blank-markdown"),
    ],
)
def test_s07_council_rejects_invalid_json_and_blank_markdown(
    isolated_config, filename, output, validator
):
    implementer = DummyWorker("implementer", [{"repaired_code": output}])
    manager = _manager({"implementer": implementer}, budgets={"max_local_attempts": 1})

    result = manager.dispatch_task(
        prompt="Update the sample artifact",
        target_files=[filename],
        required_roles=["implementer"],
    )

    assert result["evaluation"]["local_result_status"] == "insufficient"
    assert result["evaluation"]["validation_exhausted"] is True
    assert implementer.call_count == 2
    for order in result["all_orders"]:
        validation = order.result["validation_run"]
        assert validation["validators"] == [validator]
        assert validation["passed"] is False
        assert validation["issues"]


# ── No work requested: empty order lists stay valid ─────────────────────────


def test_council_with_no_requested_roles_is_left_to_the_steward(isolated_config):
    pm = _manager({})

    result = pm.dispatch_task(prompt="Update the docs", target_files=[], required_roles=[])

    evaluation = result["evaluation"]
    assert evaluation["local_result_status"] == "sufficient"
    assert evaluation["unroutable_roles"] == []
    assert evaluation["validation_exhausted"] is False
    assert result["escalation_packet"] is None


def test_preflight_steward_call_with_no_orders_is_unchanged(isolated_config):
    # The call shape used by run_plan.py and client.py for ordinary tc run.
    evaluation = ProjectSteward(budgets={}).evaluate("Update the docs", [], [])

    assert evaluation["local_result_status"] == "sufficient"
    assert evaluation["reason"] == "Local workers succeeded."
    assert evaluation["recommended_escalation"] == "none"
    assert "unroutable_roles" not in evaluation
    assert "validation_exhausted" not in evaluation
