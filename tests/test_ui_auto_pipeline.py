import json
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import Mock

import pytest

from triage_core import sustainability
from triage_core.backends import BackendResponse
from triage_core.task_ledger import TaskLedger
from triage_core.ui import app


class InlineThread:
    def __init__(self, *, target, daemon):
        self.target = target

    def start(self):
        self.target()


@pytest.mark.parametrize(
    ("prompt", "risk", "raw", "metrics_model"),
    [
        ("Read the draft notes", "low", {"model": "served-model"}, "served-model"),
        ("Review deployment notes", "medium", {}, "configured-model"),
    ],
    ids=["low-risk-completes", "medium-risk-hands-off"],
)
def test_auto_pipeline_records_draft_and_reaches_next_step(
    tmp_path, monkeypatch, prompt, risk, raw, metrics_model
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(app.default_config, "get_ledger_dir", lambda: "ledger")
    monkeypatch.setattr(app, "threading", SimpleNamespace(Thread=InlineThread))
    monkeypatch.setattr(app.PowerMonitor, "get_status", lambda: {"has_battery": False})
    monkeypatch.setattr(sustainability, "PowerSampler", Mock())
    monkeypatch.setattr(sustainability, "integrate_energy_kwh", lambda *_: (0.001, 300.0, "fixture"))
    monkeypatch.setattr(
        app.SustainabilityEstimator,
        "estimate",
        lambda **_: {
            "emissions_gco2e": 0.0,
            "water_liters_estimate": 0.0,
            "embodied_gco2e_allocated": 0.0,
        },
    )

    ui = Mock()
    ui.ledger = TaskLedger(ledger_dir="ledger")
    ui.prompt_box.get.return_value = prompt
    ui.files_entry.get.return_value = ""
    ui.review_timers = {}
    ui._context_runner_label = app.TriageDeskApp._context_runner_label
    ui._model_label = MethodType(app.TriageDeskApp._model_label, ui)
    ui._dispatch_pipeline = MethodType(app.TriageDeskApp._dispatch_pipeline, ui)
    ui.active_backend = SimpleNamespace(
        name="fake",
        model="configured-model",
        generate=Mock(
            side_effect=[
                BackendResponse(text="docs_update", raw={}),
                BackendResponse(
                    text="Example draft text",
                    raw=raw,
                    usage={"prompt_tokens": 9, "completion_tokens": 4},
                ),
            ]
        ),
    )
    app.TriageDeskApp._handle_task(ui, "pipeline")

    status = ui.status_label.configure.call_args.kwargs["text"]
    expected_status = (
        "✓ Pipeline completed" if risk == "low" else "Local draft failed validation. Escalating to Council"
    )
    assert status.startswith(expected_status)
    ui._show_result_metrics.assert_called_once()
    assert ui._show_result_metrics.call_args.args[:4] == (metrics_model, "fake", 9, 4)
    ui.btn_pipeline.configure.assert_called_with(state="normal")

    ledger_text = Path(ui.ledger.ledger_path).read_text(encoding="utf-8")
    events = [json.loads(line) for line in ledger_text.splitlines()]
    assert [event["event_type"] for event in events] == [
        "task_created",
        "task_classified",
        "context_budgeted",
        "runner_selected",
        "local_draft_generated",
        "energy_estimated",
    ]
    task_id = events[0]["task_id"]
    assert all(event["task_id"] == task_id for event in events)
    assert events[1]["payload"]["risk_level"] == risk
    assert Path(events[2]["payload"]["context_pack_path"]).is_file()
    assert events[3]["payload"] == {"runner": "pipeline"}
    draft = events[4]["payload"]
    assert draft["status"] == "success"
    assert draft["backend"] == "fake"
    assert draft["model"] == "configured-model"
    assert (draft["input_tokens"], draft["output_tokens"]) == (9, 4)
    assert draft["validator_passed"] is (risk == "low")
    assert events[5]["payload"]["energy_kwh"] == draft["energy_kwh"] == 0.001

    handoffs = [call.args[1] for call in ui.after.call_args_list if call.args[0] == 1000]
    ui._dispatch_council.assert_not_called()
    if risk == "medium":
        assert len(handoffs) == 1
        handoffs[0]()
        ui._dispatch_council.assert_called_once()
        next_task_id, next_prompt, next_files, danger = ui._dispatch_council.call_args.args
        assert (next_task_id, next_prompt, next_files) == (task_id, prompt, [])
        assert danger.risk_level == "medium"
    else:
        assert handoffs == []
