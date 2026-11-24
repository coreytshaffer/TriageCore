import os
import json
import tempfile
import csv
from types import SimpleNamespace

from triage_core.lab import (
    calculate_scientific_metrics,
    export_tabular_dataset,
    LightweightDecisionTree,
    entropy,
)
from triage_core.task_ledger import TaskLedger, TaskRecord
from triage_core import task_review_service
from triage_core.task_review_service import ReviewState
from triage_core.orchestration import ProjectManager
from triage_core.config import default_config


def test_legacy_observation_is_not_a_scientific_label(tmp_path, capsys):
    from triage_core.cli import _lab_train

    ledger = TaskLedger(str(tmp_path))
    ledger.append_event("task", "runner_selected", {"runner": "pipeline"})
    ledger.append_event("task", "review_completed", {"accepted": True})
    records = ledger.get_all_tasks()
    path = tmp_path / "export.csv"

    metrics = calculate_scientific_metrics(records)
    export_tabular_dataset(records, str(path))
    _lab_train(str(tmp_path))

    assert metrics["total_reviewed"] == 0
    assert metrics["excluded_review_observations"] == 1
    with path.open(newline="", encoding="utf-8") as input_file:
        assert next(csv.DictReader(input_file))["accepted"] == ""
    assert not (tmp_path / "predictive_model.json").exists()
    assert "verified terminal decision" in capsys.readouterr().out


def test_calculate_scientific_metrics():
    records = [
        TaskRecord(
            task_id="t1",
            status="local_draft_generated",
            review=ReviewState(status="verified", decision="accepted"),
            human_review_required=True,
            total_tokens=1000,
            wasted_tokens=100,
            energy_kwh_estimate=0.01,
            emissions_gco2e_estimate=2.0,
            water_liters_estimate=0.5,
        ),
        TaskRecord(
            task_id="t2",
            status="local_draft_generated",
            review=ReviewState(status="verified", decision="rejected"),
            human_review_required=True,
            total_tokens=500,
            wasted_tokens=500,
            energy_kwh_estimate=0.005,
            emissions_gco2e_estimate=1.0,
            water_liters_estimate=0.2,
        ),
        TaskRecord(
            task_id="t3",
            status="local_draft_generated",
            review=ReviewState(status="verified", decision="needs_revision"),
            human_review_required=True,
            total_tokens=300,
            wasted_tokens=0,
            energy_kwh_estimate=0.003,
            emissions_gco2e_estimate=0.6,
        ),
        TaskRecord(task_id="t4", review=ReviewState(status="unavailable")),
    ]

    metrics = calculate_scientific_metrics(records)

    assert metrics["total_runs"] == 4
    assert metrics["review_verification_status"] == "incomplete"
    assert metrics["unavailable_reviews"] == 1
    assert metrics["total_reviewed"] == 3
    assert metrics["binary_review_sample_size"] == 2
    assert metrics["excluded_from_binary_sample"] == 2
    assert metrics["total_accepted"] == 1
    assert metrics["accepted_yield_pct"] == 50.0
    assert metrics["mean_review_burden_mins"] is None
    assert metrics["mean_tokens_per_accepted_task"] == 1000.0
    assert metrics["mean_energy_kwh_per_accepted_task"] == 0.01
    assert metrics["mean_emissions_gco2e_per_accepted_task"] == 2.0
    assert metrics["mean_water_liters_per_accepted_task"] == 0.5
    assert metrics["total_tokens"] == 1800
    assert metrics["total_wasted_tokens"] == 600
    assert metrics["token_efficiency_pct"] == (1200 / 1800) * 100.0


def test_export_tabular_dataset():
    records = [
        TaskRecord(
            task_id="t1",
            status="local_draft_generated",
            review=ReviewState(status="verified", decision="accepted"),
            human_review_required=True,
            total_tokens=1000,
            wasted_tokens=100,
            energy_kwh_estimate=0.01,
            emissions_gco2e_estimate=2.0,
            water_liters_estimate=0.5,
            runner="worker_council",
            backend_name="ollama",
            model="qwen2.5",
            risk_level="medium",
            permission_profile="workspace-write-with-approval",
            elapsed_seconds=5.2,
        ),
        TaskRecord(task_id="t2", review=ReviewState(status="verified", decision="rejected")),
        TaskRecord(task_id="t3", review=ReviewState(status="verified", decision="needs_revision")),
        TaskRecord(task_id="t4", review=ReviewState(status="pending")),
        TaskRecord(task_id="t5", review=ReviewState(status="unavailable")),
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        csv_path = os.path.join(temp_dir, "export.csv")
        export_tabular_dataset(records, csv_path)

        assert os.path.exists(csv_path)
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            assert len(reader) == 5
            row = reader[0]
            assert row["task_id"] == "t1"
            assert row["runner"] == "worker_council"
            assert row["risk_level"] == "medium"
            assert row["accepted"] == "1"
            assert [row["accepted"] for row in reader] == ["1", "0", "", "", ""]
            assert [row["review_status"] for row in reader] == [
                "verified", "verified", "verified", "pending", "unavailable"
            ]


def test_report_and_training_identify_an_incomplete_verified_sample(tmp_path, monkeypatch, capsys):
    from triage_core.cli import _lab_report, _lab_train

    ledger = TaskLedger(str(tmp_path))
    states = {
        "accepted": ReviewState(status="verified", decision="accepted"),
        "rejected": ReviewState(status="verified", decision="rejected"),
        "revision": ReviewState(status="verified", decision="needs_revision"),
        "waiting": ReviewState(status="pending"),
        "unavailable": ReviewState(status="unavailable"),
        "legacy": ReviewState(status="unpaired"),
    }
    for task_id in states:
        ledger.append_event(task_id, "runner_selected", {"runner": "pipeline"})
    ledger.append_event("legacy", "review_completed", {"accepted": True})
    service = SimpleNamespace(project=lambda task_id, *, include_history: states[task_id])
    monkeypatch.setattr(task_review_service, "get_review_service", lambda ledger_dir: service)

    _lab_report(str(tmp_path))
    _lab_train(str(tmp_path))

    output = capsys.readouterr().out
    assert "| Review Verification | incomplete |" in output
    assert "| Verified Binary Sample Size | 2 |" in output
    assert "| Excluded Historical Unsigned Observations | 1 |" in output
    assert "Review verification incomplete." in output
    assert "on 2 samples" in output


def test_decision_tree_logic():
    # Helper entropy check
    assert entropy([]) == 0.0
    assert entropy([1, 1, 1]) == 0.0
    assert entropy([0, 0, 0]) == 0.0
    assert abs(entropy([1, 0]) - 1.0) < 0.0001

    # Simple training set
    # Let's say risk_level='high' -> always fails (0)
    # risk_level='low' -> always succeeds (1)
    X = [
        {"runner": "pipeline", "risk_level": "high", "permission_profile": "blocked"},
        {"runner": "pipeline", "risk_level": "high", "permission_profile": "blocked"},
        {"runner": "council", "risk_level": "low", "permission_profile": "workspace-write"},
        {"runner": "council", "risk_level": "low", "permission_profile": "workspace-write"},
    ]
    y = [0, 0, 1, 1]

    model = LightweightDecisionTree(max_depth=3)
    model.fit(X, y, ["runner", "risk_level", "permission_profile"])

    # Predict high risk sample
    pred_high, prob_high = model.predict({"runner": "pipeline", "risk_level": "high", "permission_profile": "blocked"})
    assert pred_high == 0
    assert prob_high == 0.0

    # Predict low risk sample
    pred_low, prob_low = model.predict({"runner": "council", "risk_level": "low", "permission_profile": "workspace-write"})
    assert pred_low == 1
    assert prob_low == 1.0

    # Test serialization / deserialization
    model_dict = model.serialize()
    assert "feature" in model_dict
    assert model_dict["feature"] in ["runner", "risk_level", "permission_profile"]

    new_model = LightweightDecisionTree()
    new_model.deserialize(model_dict)
    pred_new, prob_new = new_model.predict({"runner": "pipeline", "risk_level": "high", "permission_profile": "blocked"})
    assert pred_new == 0
    assert prob_new == 0.0


def test_orchestration_warning_trigger(monkeypatch):
    # Setup a model in a temp directory and redirect ledger config there
    with tempfile.TemporaryDirectory() as temp_dir:
        model_path = os.path.join(temp_dir, "predictive_model.json")
        
        # Save a model that predicts 0 (failure) for worker_council high risk
        model_data = {
            "feature": "risk_level",
            "label": 1,
            "prob": 0.5,
            "children": {
                "high": {"label": 0, "prob": 0.0},
                "low": {"label": 1, "prob": 1.0}
            }
        }
        
        with open(model_path, "w", encoding="utf-8") as f:
            json.dump(model_data, f)

        # Monkeypatch the default ledger directory in default_config
        monkeypatch.setattr(default_config, "get_ledger_dir", lambda: temp_dir)

        # Try to dispatch a task that has a high risk level (contains delete/wipe)
        pm = ProjectManager()
        
        stream_outputs = []
        def callback(msg):
            stream_outputs.append(msg)

        # Dispatch task with delete keyword to trigger high risk classification
        result = pm.dispatch_task(
            prompt="Please wipe the repository and delete everything.",
            target_files=[],
            required_roles=[],
            stream_callback=callback
        )

        assert any("TriageLab Warning" in out for out in stream_outputs)
