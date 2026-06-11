import json

import pytest
from fastapi.testclient import TestClient

from triage_core.task_ledger import TaskLedger


@pytest.fixture
def mobile_api(tmp_path, monkeypatch):
    import triage_core.web.server as server

    ledger = TaskLedger(ledger_dir=str(tmp_path / "ledger"))
    task_id = "task-mobile"
    ledger.append_event(
        task_id,
        "task_created",
        {
            "title": "Mobile review",
            "description": "private prompt: Review from phone.",
        },
    )
    ledger.append_event(task_id, "runner_selected", {"runner": "local_llm"})

    monkeypatch.setattr(server, "LEDGER_DIR", str(tmp_path / "ledger"))
    monkeypatch.setattr(server, "ledger", ledger)
    monkeypatch.setattr(server, "MOBILE_TOKEN", "test-mobile-token")
    monkeypatch.setattr(server, "MOBILE_ACTOR", "test-mobile-operator")

    client = TestClient(server.app)
    headers = {"Authorization": "Bearer test-mobile-token"}
    return server, ledger, task_id, client, headers


def test_mobile_api_requires_authentication(mobile_api):
    _, _, task_id, client, _ = mobile_api

    requests = (
        client.get("/api/tasks"),
        client.get(
            "/api/tasks",
            headers={"Authorization": "Bearer incorrect-token"},
        ),
        client.post(
            f"/api/tasks/{task_id}/review",
            json={"decision": "accepted"},
        ),
        client.get("/api/logs"),
    )

    assert all(response.status_code == 401 for response in requests)


def test_mobile_page_uses_operator_token_entry(mobile_api):
    _, _, _, client, _ = mobile_api

    response = client.get("/")

    assert response.status_code == 200
    assert 'id="mobile-token"' in response.text
    assert "Refresh Logs" not in response.text
    assert "fonts.googleapis.com" not in response.text

    script_response = client.get("/static/app.js")
    assert script_response.status_code == 200
    assert "localStorage" not in script_response.text
    assert "sessionStorage" not in script_response.text
    assert ".innerHTML" not in script_response.text
    assert "console.log" not in script_response.text


def test_mobile_web_lists_safe_tasks_and_records_review(mobile_api):
    _, ledger, task_id, client, headers = mobile_api

    tasks_response = client.get("/api/tasks", headers=headers)
    assert tasks_response.status_code == 200
    task = tasks_response.json()["tasks"][0]
    assert task["task_id"] == task_id
    assert "title" not in task
    assert "description" not in task
    assert "target_files" not in task
    assert "artifact_paths" not in task
    assert "private prompt" not in json.dumps(task)

    review_response = client.post(
        f"/api/tasks/{task_id}/review",
        json={"decision": "accepted", "workload": "low"},
        headers=headers,
    )
    assert review_response.status_code == 200

    reviewed = ledger.get_task(task_id)
    assert reviewed is not None
    assert reviewed.status == "reviewed"
    assert reviewed.accepted is True
    assert reviewed.review_workload == "low"

    events = ledger.get_events(task_id=task_id)
    review_event = next(
        event for event in events if event["event_type"] == "review_completed"
    )
    assert review_event["payload"]["actor"] == "test-mobile-operator"


def test_mobile_web_rejects_invalid_review_decision(mobile_api):
    _, ledger, task_id, client, headers = mobile_api

    response = client.post(
        f"/api/tasks/{task_id}/review",
        json={"decision": "maybe", "workload": "low"},
        headers=headers,
    )

    assert response.status_code == 422
    reviewed = ledger.get_task(task_id)
    assert reviewed is not None
    assert reviewed.status != "reviewed"


def test_mobile_web_rejects_invalid_review_workload(mobile_api):
    _, ledger, task_id, client, headers = mobile_api

    response = client.post(
        f"/api/tasks/{task_id}/review",
        json={"decision": "accepted", "workload": "private notes"},
        headers=headers,
    )

    assert response.status_code == 422
    reviewed = ledger.get_task(task_id)
    assert reviewed is not None
    assert reviewed.status != "reviewed"


def test_mobile_logs_are_disabled(mobile_api):
    _, _, _, client, headers = mobile_api

    response = client.get("/api/logs", headers=headers)

    assert response.status_code == 404


def test_start_server_defaults_to_loopback(monkeypatch):
    import triage_core.web.server as server

    calls = []
    monkeypatch.setattr(
        server.uvicorn,
        "run",
        lambda app, host, port: calls.append((app, host, port)),
    )

    server.start_server(token="test-mobile-token")

    assert calls == [(server.app, "127.0.0.1", 8000)]


def test_start_server_rejects_non_loopback_without_explicit_enablement(
    monkeypatch,
):
    import triage_core.web.server as server

    monkeypatch.setattr(
        server.uvicorn,
        "run",
        lambda *args, **kwargs: pytest.fail("uvicorn must not start"),
    )

    with pytest.raises(RuntimeError, match="allow_network=True"):
        server.start_server(
            host="0.0.0.0",
            token="test-mobile-token",
        )


def test_start_server_rejects_network_binding_without_token(monkeypatch):
    import triage_core.web.server as server

    monkeypatch.delenv("TRIAGECORE_MOBILE_TOKEN", raising=False)
    monkeypatch.setattr(
        server.uvicorn,
        "run",
        lambda *args, **kwargs: pytest.fail("uvicorn must not start"),
    )

    with pytest.raises(RuntimeError, match="authentication is required"):
        server.start_server(host="0.0.0.0", allow_network=True)


def test_start_server_allows_explicit_authenticated_network_binding(
    monkeypatch,
):
    import triage_core.web.server as server

    calls = []
    monkeypatch.setattr(
        server.uvicorn,
        "run",
        lambda app, host, port: calls.append((app, host, port)),
    )

    server.start_server(
        host="0.0.0.0",
        port=9000,
        token="test-mobile-token",
        actor_id="test-operator",
        allow_network=True,
    )

    assert calls == [(server.app, "0.0.0.0", 9000)]
    assert server.MOBILE_ACTOR == "test-operator"
