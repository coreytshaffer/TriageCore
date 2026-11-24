import os
import sys
from enum import Enum
from hmac import compare_digest
from ipaddress import ip_address
from typing import Any, Dict, Optional

if sys.version_info[:2] < (3, 11):
    raise RuntimeError("TriageCore Mobile requires Python 3.11 or later.")

_MINIMUM_FASTAPI = "0.163.2"
_FASTAPI_REQUIREMENT = (
    f"TriageCore Mobile requires FastAPI {_MINIMUM_FASTAPI} or later. "
    "From the repository root, run python -m pip install '.[mobile]'."
)

try:
    import fastapi
    from packaging.version import InvalidVersion, Version
except ModuleNotFoundError as exc:
    if exc.name not in {"fastapi", "packaging", "packaging.version"}:
        raise
    raise RuntimeError(_FASTAPI_REQUIREMENT) from exc

_fastapi_version = getattr(fastapi, "__version__", None)
if not isinstance(_fastapi_version, str):
    raise RuntimeError(_FASTAPI_REQUIREMENT)
try:
    _installed_fastapi = Version(_fastapi_version)
except InvalidVersion as exc:
    raise RuntimeError(_FASTAPI_REQUIREMENT) from exc
if _installed_fastapi < Version(_MINIMUM_FASTAPI):
    raise RuntimeError(_FASTAPI_REQUIREMENT)

# Load the server and app dependencies after checking the mobile environment.
import uvicorn  # noqa: E402
from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, Request, Response, status  # noqa: E402
from fastapi.exception_handlers import request_validation_exception_handler  # noqa: E402
from fastapi.exceptions import RequestValidationError  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel, ConfigDict, Field  # noqa: E402

from triage_core.task_ledger import TaskLedger, TaskRecord  # noqa: E402
from triage_core.task_review_service import ReviewServiceError  # noqa: E402

app = FastAPI(title="TriageCore Mobile")

LEDGER_DIR = os.environ.get("TRIAGECORE_LEDGER_DIR", ".triagecore")
MOBILE_TOKEN = os.environ.get("TRIAGECORE_MOBILE_TOKEN", "")
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
        "accepted": task.review.binary_label,
        "review_status": task.review.status,
        "review_decision": task.review.decision,
        "review_reason": task.review.reason,
        "review_pending_count": task.review.pending_count,
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
    ACCEPTED_WITH_MINOR_EDITS = "accepted_with_minor_edits"
    NEEDS_REVISION = "needs_revision"
    REJECTED = "rejected"


class ReviewWorkload(str, Enum):
    NOT_RECORDED = "not_recorded"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReviewPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ReviewDecision
    request_id: str = Field(min_length=1, max_length=128)
    workload: ReviewWorkload | None = None


@api.post("/tasks/{task_id}/review", status_code=status.HTTP_202_ACCEPTED)
def review_task(task_id: str, payload: ReviewPayload, response: Response) -> Dict[str, str]:
    if ledger.get_task(task_id, include_history=False) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found.",
        )

    try:
        intent = ledger.review_service.request_intent(
            task_id,
            payload.request_id,
            payload.decision.value,
            payload.workload.value if payload.workload else None,
        )
    except ReviewServiceError as exc:
        status_code, detail = {
            "review_intent_conflict": (status.HTTP_409_CONFLICT, "Request ID conflict."),
            "invalid_review_request": (422, "Invalid review request."),
            "invalid_review_identifier": (422, "Invalid review request."),
            "review_intent_missing": (status.HTTP_404_NOT_FOUND, "Review request not found."),
        }.get(
            exc.reason,
            (status.HTTP_503_SERVICE_UNAVAILABLE, "Local review is unavailable."),
        )
        raise HTTPException(status_code=status_code, detail=detail) from None

    if intent.status != "pending":
        response.status_code = status.HTTP_200_OK
    return {"status": intent.status, "intent_id": intent.intent_id}


@app.exception_handler(RequestValidationError)
async def _safe_review_validation(request: Request, exc: RequestValidationError):
    if request.scope.get("endpoint") is review_task:
        return JSONResponse(status_code=422, content={"detail": "Invalid review request."})
    return await request_validation_exception_handler(request, exc)


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
    """Start the mobile API. The legacy actor argument has no authority."""
    global MOBILE_TOKEN

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
    print(f"Starting TriageCore Mobile Server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
