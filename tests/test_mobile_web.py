import json
import runpy
import sys
from pathlib import Path

import fastapi
import pytest
from fastapi.testclient import TestClient
from test_task_review_integration import paired_review

from triage_core.task_ledger import TaskLedger


SERVER_PATH = Path(__file__).resolve().parents[1] / "triage_core/web/server.py"
FASTAPI_REQUIREMENT = r"TriageCore Mobile requires FastAPI 0\.163\.2 or later"


@pytest.fixture
def startup_ledger_path(tmp_path, monkeypatch):
    path = tmp_path / "startup-ledger"
    monkeypatch.setenv("TRIAGECORE_LEDGER_DIR", str(path))
    return path


@pytest.mark.parametrize("dependency", ["fastapi", "packaging.version"])
def test_mobile_import_rejects_missing_dependency(
    dependency, startup_ledger_path, monkeypatch
):
    monkeypatch.setitem(sys.modules, dependency, None)

    with pytest.raises(RuntimeError, match=FASTAPI_REQUIREMENT) as error:
        runpy.run_path(str(SERVER_PATH))

    assert ".[mobile]" in str(error.value)
    assert not startup_ledger_path.exists()


@pytest.mark.parametrize("version", ["0.163.1", "0.163.2rc1", "invalid", None])
def test_mobile_import_rejects_unsupported_fastapi(
    version, startup_ledger_path, monkeypatch
):
    monkeypatch.setattr(fastapi, "__version__", version)

    with pytest.raises(RuntimeError, match=FASTAPI_REQUIREMENT):
        runpy.run_path(str(SERVER_PATH))

    assert not startup_ledger_path.exists()


def test_mobile_import_rejects_absent_fastapi_version(startup_ledger_path, monkeypatch):
    monkeypatch.delattr(fastapi, "__version__")

    with pytest.raises(RuntimeError, match=FASTAPI_REQUIREMENT):
        runpy.run_path(str(SERVER_PATH))

    assert not startup_ledger_path.exists()


@pytest.mark.parametrize("version", ["0.163.2", "0.163.2.post1"])
def test_mobile_import_accepts_supported_fastapi(version, startup_ledger_path, monkeypatch):
    monkeypatch.setattr(fastapi, "__version__", version)

    module = runpy.run_path(str(SERVER_PATH))

    assert module["app"].title == "TriageCore Mobile"
    assert startup_ledger_path.is_dir()


@pytest.fixture
def mobile_api(tmp_path, monkeypatch):
    import triage_core.web.server as server

    ledger = TaskLedger(ledger_dir=str(tmp_path / "mobile-ledger"))
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

    monkeypatch.setattr(server, "LEDGER_DIR", str(tmp_path / "mobile-ledger"))
    monkeypatch.setattr(server, "ledger", ledger)
    monkeypatch.setattr(server, "MOBILE_TOKEN", "test-mobile-token")

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


def test_mobile_web_lists_safe_tasks_and_requests_review(mobile_api, paired_review, monkeypatch):
    server, _, _, client, headers = mobile_api
    service, ledger_dir, *_ = paired_review
    ledger = TaskLedger(str(ledger_dir), review_service=service)
    monkeypatch.setattr(server, "ledger", ledger)
    task_id = "task-1"
    ledger.append_event(task_id, "task_created", {"description": "Private synthetic prompt"})
    before = Path(ledger.ledger_path).read_bytes()
    tasks_response = client.get("/api/tasks", headers=headers)
    assert tasks_response.status_code == 200
    task = tasks_response.json()["tasks"][0]
    assert task["task_id"] == task_id
    assert "title" not in task
    assert "description" not in task
    assert "target_files" not in task
    assert "artifact_paths" not in task
    assert "Private synthetic prompt" not in json.dumps(task)
    assert task["accepted"] is None
    assert task["review_status"] == "no_decision"

    route = f"/api/tasks/{task_id}/review"
    body = {"decision": "accepted", "request_id": "request-1", "workload": "low"}
    review_response = client.post(route, json=body, headers=headers)
    assert review_response.status_code == 202
    intent_id = review_response.json()["intent_id"]
    assert review_response.json() == {"status": "pending", "intent_id": intent_id}
    assert intent_id != body["request_id"]
    retry = client.post(route, json=body, headers=headers)
    assert retry.status_code == 202
    assert retry.json() == review_response.json()
    assert client.post(route, json={**body, "workload": "high"}, headers=headers).status_code == 409
    assert tuple(intent.intent_id for intent in service.pending_for_task(task_id)) == (intent_id,)

    reviewed = ledger.get_task(task_id)
    assert reviewed is not None
    assert reviewed.status != "reviewed"
    assert reviewed.accepted is None
    assert reviewed.human_review_minutes is None
    pending = client.get("/api/tasks", headers=headers).json()["tasks"][0]
    assert pending["review_status"] == "pending"
    assert pending["review_pending_count"] == 1
    assert pending["accepted"] is None
    assert intent_id not in json.dumps(pending)

    service.cancel_intent(task_id, intent_id)
    resolved_retry = client.post(route, json=body, headers=headers)
    assert resolved_retry.status_code == 200
    assert resolved_retry.json() == {"status": "cancelled", "intent_id": intent_id}
    competing = client.post(
        route, json={"request_id": "request-2", "decision": "needs_revision"}, headers=headers,
    )
    assert competing.status_code == 202
    current = client.get("/api/tasks", headers=headers).json()["tasks"][0]
    assert current["review_status"] == "pending"
    assert current["review_decision"] is None
    assert current["review_pending_count"] == 1
    assert current["accepted"] is None
    assert "Exact synthetic text" not in json.dumps(current)
    assert "rev-1" not in json.dumps(current)
    assert Path(ledger.ledger_path).read_bytes() == before


@pytest.mark.parametrize("field", ["actor", "evidence", "assertion", "credential_id"])
def test_mobile_review_rejects_fields_outside_intent_contract(mobile_api, field):
    _, _, task_id, client, headers = mobile_api

    response = client.post(
        f"/api/tasks/{task_id}/review",
        json={"decision": "accepted", "request_id": "request-1", field: "secret-sentinel"},
        headers=headers,
    )

    assert response.status_code == 422
    assert "secret-sentinel" not in response.text


def test_mobile_review_requires_a_request_id(mobile_api):
    _, _, task_id, client, headers = mobile_api

    response = client.post(
        f"/api/tasks/{task_id}/review",
        json={"decision": "accepted"},
        headers=headers,
    )

    assert response.status_code == 422


def test_mobile_web_rejects_invalid_review_decision(mobile_api):
    _, ledger, task_id, client, headers = mobile_api

    response = client.post(
        f"/api/tasks/{task_id}/review",
        json={"decision": "maybe", "request_id": "request-1", "workload": "low"},
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
        json={"decision": "accepted", "request_id": "request-1", "workload": "private notes"},
        headers=headers,
    )

    assert response.status_code == 422
    assert "private notes" not in response.text
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

    server.start_server(token="test-mobile-token", actor_id="legacy-mobile-actor")

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
        allow_network=True,
    )

    assert calls == [(server.app, "0.0.0.0", 9000)]
