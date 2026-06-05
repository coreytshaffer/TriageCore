import os
import json
import tempfile
import csv
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from triage_core.lab import (
    calculate_scientific_metrics,
    export_tabular_dataset,
    LightweightDecisionTree,
    entropy,
)
from triage_core.task_ledger import TaskRecord
from triage_core.orchestration import ProjectManager
from triage_core.config import default_config


@dataclass
class DummyTaskRecord:
    task_id: str
    status: str
    accepted: bool
    human_review_required: bool
    human_review_minutes: float
    total_tokens: int
    wasted_tokens: int = 0
    energy_kwh_estimate: float = 0.0
    emissions_gco2e_estimate: float = 0.0
    water_liters_estimate: float = 0.0
    runner: str = ""
    backend_name: str = ""
    model: str = ""
    risk_level: str = ""
    permission_profile: str = ""
    elapsed_seconds: float = 0.0
    created_at: str = ""


def test_calculate_scientific_metrics():
    records = [
        DummyTaskRecord(
            task_id="t1",
            status="reviewed",
            accepted=True,
            human_review_required=True,
            human_review_minutes=2.5,
            total_tokens=1000,
            wasted_tokens=100,
            energy_kwh_estimate=0.01,
            emissions_gco2e_estimate=2.0,
            water_liters_estimate=0.5,
        ),
        DummyTaskRecord(
            task_id="t2",
            status="reviewed",
            accepted=False,
            human_review_required=True,
            human_review_minutes=4.0,
            total_tokens=500,
            wasted_tokens=500,
            energy_kwh_estimate=0.005,
            emissions_gco2e_estimate=1.0,
            water_liters_estimate=0.2,
        ),
        DummyTaskRecord(
            task_id="t3",
            status="local_draft_generated",
            accepted=False,
            human_review_required=False,
            human_review_minutes=0.0,
            total_tokens=300,
            wasted_tokens=0,
            energy_kwh_estimate=0.003,
            emissions_gco2e_estimate=0.6,
        ),
    ]

    metrics = calculate_scientific_metrics(records)

    assert metrics["total_runs"] == 3
    assert metrics["total_reviewed"] == 2
    assert metrics["total_accepted"] == 1
    assert metrics["accepted_yield_pct"] == 50.0
    assert metrics["mean_review_burden_mins"] == 3.25
    assert metrics["mean_tokens_per_accepted_task"] == 1000.0
    assert metrics["mean_energy_kwh_per_accepted_task"] == 0.01
    assert metrics["mean_emissions_gco2e_per_accepted_task"] == 2.0
    assert metrics["mean_water_liters_per_accepted_task"] == 0.5
    assert metrics["total_tokens"] == 1800
    assert metrics["total_wasted_tokens"] == 600
    assert metrics["token_efficiency_pct"] == (1200 / 1800) * 100.0


def test_export_tabular_dataset():
    records = [
        DummyTaskRecord(
            task_id="t1",
            status="reviewed",
            accepted=True,
            human_review_required=True,
            human_review_minutes=2.5,
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
        )
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        csv_path = os.path.join(temp_dir, "export.csv")
        export_tabular_dataset(records, csv_path)

        assert os.path.exists(csv_path)
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = list(csv.DictReader(f))
            assert len(reader) == 1
            row = reader[0]
            assert row["task_id"] == "t1"
            assert row["runner"] == "worker_council"
            assert row["risk_level"] == "medium"
            assert row["accepted"] == "1"


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
