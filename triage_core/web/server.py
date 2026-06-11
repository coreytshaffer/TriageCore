import os
from enum import Enum
from hmac import compare_digest
from ipaddress import ip_address
from typing import Any, Dict, Optional

import uvicorn
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from triage_core.task_ledger import TaskLedger, TaskRecord

app = FastAPI(title="TriageCore Mobile")

LEDGER_DIR = os.environ.get("TRIAGECORE_LEDGER_DIR", ".triagecore")
MOBILE_TOKEN = os.environ.get("TRIAGECORE_MOBILE_TOKEN", "")
MOBILE_ACTOR = os.environ.get("TRIAGECORE_MOBILE_ACTOR", "mobile_operator")

ledger = TaskLedger(ledger_dir=LEDGER_DIR)

static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")


def _require_api_token(authorization: Optional[str] = Header(default=None)) -> None:
    if not MOBILE_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Mobile API authentication is not configured.",
        )

    scheme, separator, supplied_token = (authorization or "").partition(" ")
    valid = (
        separator == " "
        and scheme.lower() == "bearer"
        and bool(supplied_token)
        and compare_digest(supplied_token, MOBILE_TOKEN)
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _safe_task_projection(task: TaskRecord) -> Dict[str, Any]:
    return {
        "task_id": task.task_id,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "runner": task.runner,
        "status": task.status,
        "risk_level": task.risk_level,
        "human_review_required": task.human_review_required,
        "accepted": task.accepted,
        "review_decision": task.review_decision,
        "review_workload": task.review_workload,
        "artifact_status": task.artifact_status,
        "task_outcome": task.task_outcome,
        "selected_route": task.selected_route,
        "validation_status": task.validation_status,
        "completed_at": task.completed_at,
    }


def _is_loopback_host(host: str) -> bool:
    normalized = host.strip().strip("[]")
    if normalized.lower() == "localhost":
        return True
    try:
        return ip_address(normalized).is_loopback
    except ValueError:
        return False


@app.get("/", response_class=HTMLResponse)
def get_index() -> str:
    with open(
        os.path.join(static_dir, "index.html"),
        "r",
        encoding="utf-8",
    ) as index_file:
        return index_file.read()


api = APIRouter(
    prefix="/api",
    dependencies=[Depends(_require_api_token)],
)


@api.get("/tasks")
def get_tasks(limit: int = 50) -> Dict[str, Any]:
    tasks = ledger.get_recent_tasks(limit=limit)
    return {"tasks": [_safe_task_projection(task) for task in tasks]}


class ReviewDecision(str, Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ReviewWorkload(str, Enum):
    NOT_RECORDED = "not_recorded"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReviewPayload(BaseModel):
    decision: ReviewDecision
    workload: ReviewWorkload = ReviewWorkload.NOT_RECORDED


@api.post("/tasks/{task_id}/review")
def review_task(task_id: str, payload: ReviewPayload) -> Dict[str, str]:
    tasks = ledger.get_recent_tasks(limit=100)
    task = next((item for item in tasks if item.task_id == task_id), None)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    from triage_core.cli import _log_cli_activity

    _log_cli_activity(
        (
            "mobile review recorded "
            f"task={task_id[:8]} decision={payload.decision.value} "
            f"workload={payload.workload.value}"
        ),
        ledger_dir=LEDGER_DIR,
    )

    ledger.append_event(
        task_id=task_id,
        event_type="review_completed",
        payload={
            "accepted": payload.decision is ReviewDecision.ACCEPTED,
            "review_workload": payload.workload.value,
            "human_review_minutes": 1,
            "actor": MOBILE_ACTOR,
        },
    )
    return {"status": "ok"}


@api.get("/logs")
def get_logs() -> None:
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Mobile log access is disabled.",
    )


app.include_router(api)


def start_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    *,
    token: Optional[str] = None,
    actor_id: Optional[str] = None,
    allow_network: bool = False,
) -> None:
    global MOBILE_ACTOR, MOBILE_TOKEN

    configured_token = token or os.environ.get("TRIAGECORE_MOBILE_TOKEN", "")
    if not configured_token:
        raise RuntimeError(
            "Mobile API authentication is required. Set "
            "TRIAGECORE_MOBILE_TOKEN or pass token= explicitly."
        )
    if not _is_loopback_host(host) and not allow_network:
        raise RuntimeError(
            "Non-loopback mobile binding requires allow_network=True."
        )

    MOBILE_TOKEN = configured_token
    MOBILE_ACTOR = (
        actor_id
        or os.environ.get("TRIAGECORE_MOBILE_ACTOR")
        or "mobile_operator"
    )

    print(f"Starting TriageCore Mobile Server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
