import os
from typing import List, Optional
from dataclasses import dataclass
from pathlib import Path

from triage_core import diagnostics
from triage_core import review_queue
from triage_core.task_ledger import TaskLedger, TaskRecord
from triage_core import context_planner
from triage_core import packet_renderer
from triage_core import token_budget

@dataclass
class TriageDeskStatusSnapshot:
    git_status: str
    ledger_path: str
    ledger_exists: bool
    ledger_writable: bool
    last_event_timestamp: str

@dataclass
class TriageDeskDoctorSnapshot:
    git_branch: str
    git_status: str
    tc_executable_path: str
    ledger_path: str
    ledger_exists: bool
    ledger_readable: bool
    ledger_writable: bool
    last_event_timestamp: str
    latest_handoff_path: Optional[str]
    pyproject_path: Optional[str]
    failures: int
    warnings: int
    overall: str

@dataclass
class TriageDeskReviewQueueSnapshot:
    pending_tasks: List[TaskRecord]

@dataclass
class TriageDeskContextPlanSnapshot:
    input_path: str
    model_profile: str
    estimated_input_tokens: int
    usable_input_budget: int
    status: str
    recommended_action: str

@dataclass
class TriageDeskPacketPreview:
    content: str
    estimated_tokens: int
    fits_budget: bool
    budget: token_budget.TokenBudget

def _get_ledger_path() -> str:
    base_dir = diagnostics.get_base_dir()
    return os.path.join(base_dir, ".triagecore", "ledger.jsonl")

def get_status_snapshot() -> TriageDeskStatusSnapshot:
    git_status = diagnostics.get_git_status()
    ledger_path = _get_ledger_path()
    exists, readable, writable = diagnostics.get_ledger_status(ledger_path)
    last_event = diagnostics.get_ledger_last_event_timestamp(ledger_path)

    return TriageDeskStatusSnapshot(
        git_status=git_status,
        ledger_path=ledger_path,
        ledger_exists=exists,
        ledger_writable=writable,
        last_event_timestamp=last_event
    )

def get_doctor_snapshot() -> TriageDeskDoctorSnapshot:
    base_dir = diagnostics.get_base_dir()
    failures = 0
    warnings = 0

    tc_executable_path = diagnostics.get_tc_executable_path()
    if tc_executable_path == "unavailable":
        warnings += 1
        
    git_branch = diagnostics.get_git_branch()
    git_status = diagnostics.get_git_status()
    if git_status == "dirty":
        warnings += 1

    ledger_path = _get_ledger_path()
    exists, readable, writable = diagnostics.get_ledger_status(ledger_path)
    if exists:
        if not readable or not writable:
            failures += 1
    else:
        warnings += 1

    last_event = diagnostics.get_ledger_last_event_timestamp(ledger_path)

    handoff_path = os.path.join(base_dir, ".triagecore", "handoffs", "latest.md")
    if not os.path.exists(handoff_path):
        handoff_path = None
        
    pyproject_path = os.path.join(base_dir, "pyproject.toml")
    if not os.path.exists(pyproject_path):
        pyproject_path = None
        warnings += 1

    if failures > 0:
        overall = "FAIL"
    elif warnings > 0:
        overall = "WARN"
    else:
        overall = "OK"

    return TriageDeskDoctorSnapshot(
        git_branch=git_branch,
        git_status=git_status,
        tc_executable_path=tc_executable_path,
        ledger_path=ledger_path,
        ledger_exists=exists,
        ledger_readable=readable,
        ledger_writable=writable,
        last_event_timestamp=last_event,
        latest_handoff_path=handoff_path,
        pyproject_path=pyproject_path,
        failures=failures,
        warnings=warnings,
        overall=overall
    )

def get_review_queue_snapshot() -> TriageDeskReviewQueueSnapshot:
    ledger_path = _get_ledger_path()
    ledger = TaskLedger(Path(ledger_path))
    if not os.path.exists(ledger_path):
        return TriageDeskReviewQueueSnapshot(pending_tasks=[])
    
    pending = review_queue.get_pending_reviews(ledger)
    return TriageDeskReviewQueueSnapshot(pending_tasks=pending)

def plan_context_file(input_path: str, model_profile: str) -> TriageDeskContextPlanSnapshot:
    budget = token_budget.get_token_budget(model_profile)
    
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"File not found: {input_path}")
        
    try:
        with open(input_path, "r", encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError:
        raise ValueError(f"File is binary or unreadable as UTF-8: {input_path}")

    plan = context_planner.plan_context_for_text(input_path, text, budget)
    
    return TriageDeskContextPlanSnapshot(
        input_path=plan.input_path,
        model_profile=plan.model_profile,
        estimated_input_tokens=plan.estimated_input_tokens,
        usable_input_budget=plan.usable_input_budget,
        status=plan.status,
        recommended_action=plan.recommended_action
    )

def preview_packet(task_path: str, model_profile: str, include_paths: List[str] = None) -> TriageDeskPacketPreview:
    budget = token_budget.get_token_budget(model_profile)
    
    # We do NOT want to write the packet, we just want to preview it, so we call render_packet
    result = packet_renderer.render_packet(task_path, budget, include_paths)
    
    return TriageDeskPacketPreview(
        content=result.content,
        estimated_tokens=result.estimated_tokens,
        fits_budget=result.fits_budget,
        budget=result.budget
    )
