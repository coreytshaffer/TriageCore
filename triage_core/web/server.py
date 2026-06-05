import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from pydantic import BaseModel

from triage_core.task_ledger import TaskLedger

app = FastAPI(title="TriageCore Mobile")

LEDGER_DIR = os.environ.get("TRIAGECORE_LEDGER_DIR", ".triagecore")
LOG_PATH = os.path.join(LEDGER_DIR, "triagecore.log")

ledger = TaskLedger(ledger_dir=LEDGER_DIR)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/", response_class=HTMLResponse)
def get_index():
    with open(os.path.join(static_dir, "index.html"), "r", encoding="utf-8") as f:
        return f.read()

@app.get("/api/tasks")
def get_tasks(limit: int = 50):
    tasks = ledger.get_recent_tasks(limit=limit)
    return {"tasks": [t.to_dict() for t in tasks]}

class ReviewPayload(BaseModel):
    decision: str  # "accepted" or "rejected"
    workload: str = "not_recorded"

@app.post("/api/tasks/{task_id}/review")
def review_task(task_id: str, payload: ReviewPayload):
    tasks = ledger.get_recent_tasks(limit=100)
    task = next((t for t in tasks if t.task_id == task_id), None)
    if not task:
        return JSONResponse(status_code=404, content={"error": "Task not found"})
    
    from triage_core.cli import _log_cli_activity
    _log_cli_activity(
        f"mobile review recorded task={task_id[:8]} decision={payload.decision} workload={payload.workload}",
        ledger_dir=LEDGER_DIR,
    )
    
    ledger.append_event(
        task_id=task_id,
        event_type="review_completed",
        payload={
            "accepted": payload.decision == "accepted",
            "review_workload": payload.workload,
            "human_review_minutes": 1,
            "actor": "mobile_client"
        }
    )
    return {"status": "ok"}

@app.get("/api/logs")
def get_logs(lines: int = 50):
    if not os.path.exists(LOG_PATH):
        return {"logs": []}
    with open(LOG_PATH, "r", encoding="utf-8") as f:
        all_lines = f.readlines()
    return {"logs": all_lines[-lines:]}

def start_server(host: str = "0.0.0.0", port: int = 8000):
    print(f"Starting TriageCore Mobile Server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    start_server("0.0.0.0", 8000)
