from fastapi.testclient import TestClient

from triage_core.task_ledger import TaskLedger


def test_mobile_web_lists_tasks_and_records_review(tmp_path, monkeypatch):
    import triage_core.web.server as server

    ledger = TaskLedger(ledger_dir=str(tmp_path / "ledger"))
    task_id = "task-mobile"
    ledger.append_event(
        task_id,
        "task_created",
        {"title": "Mobile review", "description": "Review from phone."},
    )
    ledger.append_event(task_id, "runner_selected", {"runner": "local_llm"})

    monkeypatch.setattr(server, "LEDGER_DIR", str(tmp_path / "ledger"))
    monkeypatch.setattr(server, "LOG_PATH", str(tmp_path / "ledger" / "triagecore.log"))
    monkeypatch.setattr(server, "ledger", ledger)

    client = TestClient(server.app)

    tasks_response = client.get("/api/tasks")
    assert tasks_response.status_code == 200
    assert tasks_response.json()["tasks"][0]["task_id"] == task_id

    review_response = client.post(
        f"/api/tasks/{task_id}/review",
        json={"decision": "accepted", "workload": "low"},
    )
    assert review_response.status_code == 200

    reviewed = ledger.get_task(task_id)
    assert reviewed is not None
    assert reviewed.status == "reviewed"
    assert reviewed.accepted is True
    assert reviewed.review_workload == "low"
