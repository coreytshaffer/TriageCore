from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from triage_core.safe_task_packet import verify_packet
from triage_core.task_ledger import TaskLedger
from triage_core.task_packet import PrivacyMetadata, TaskPacket


DEMO_MESSY_REQUEST = (
    "Please review the repo, propose a safe implementation plan, and draft a"
    " minimal patch path without executing any real backend or mutating source"
    " files."
)
DEMO_DATA = (
    "Targets: triage_core/, docs/change/, tests/. Constraints: preserve local-"
    " first boundaries, keep artifacts auditable, and require human review"
    " before implementation."
)
DEMO_PROPOSED_OUTPUT = (
    "Proposed next step: generate a bounded handoff, identify touched files, and"
    " pause for human review before any backend call or code edit."
)


@dataclass(frozen=True)
class DemoDryRunResult:
    task_id: str
    messy_request: str
    task_packet_summary: dict[str, Any]
    privacy_check: dict[str, Any]
    route_decision: dict[str, Any]
    scoped_context: dict[str, Any]
    proposed_output: dict[str, Any]
    validation: dict[str, Any]
    human_decision: dict[str, Any]
    ledger_event: dict[str, Any]
    ledger_path: str


def validate_demo_output(proposed_output: str) -> dict[str, Any]:
    checks = {
        "mentions_human_review": "human review" in proposed_output.lower(),
        "mentions_no_backend_execution": "backend" in proposed_output.lower(),
        "mentions_bounded_next_step": "next step" in proposed_output.lower(),
    }
    passed = all(checks.values())
    return {
        "validator_name": "deterministic_demo_validator",
        "status": "passed" if passed else "failed",
        "checks": checks,
        "passed": passed,
    }


def run_demo_dry_run(
    ledger_dir: str | Path = ".triagecore",
    *,
    decision: str = "pending",
) -> DemoDryRunResult:
    if decision not in {"pending", "approve", "reject"}:
        raise ValueError("decision must be one of: pending, approve, reject")

    task_id = f"demo-dry-run-{hashlib.sha256(DEMO_MESSY_REQUEST.encode('utf-8')).hexdigest()[:12]}"
    packet = TaskPacket(
        prompt=DEMO_MESSY_REQUEST,
        data=DEMO_DATA,
        task_id=task_id,
        privacy_metadata=PrivacyMetadata(
            data_class="public",
            external_model_allowed=False,
        ),
    )
    verified_packet = verify_packet(packet)

    task_packet_summary = {
        "task_id": verified_packet.task_id,
        "prompt_length": len(verified_packet.prompt),
        "data_length": len(verified_packet.data),
        "data_class": verified_packet.privacy_metadata.data_class,
        "external_model_allowed": verified_packet.privacy_metadata.external_model_allowed,
    }
    privacy_check = {
        "privacy_level": "local_only",
        "passed": verified_packet.scan_report.passed,
        "detections": verified_packet.scan_report.detections,
        "violations": verified_packet.scan_report.violations,
    }
    route_decision = {
        "selected_route": "deterministic",
        "selected_backend": "none",
        "backend_invoked": False,
        "reason": "offline_demo_fixture_requires_no_model_execution",
    }
    scoped_context = {
        "task_id": task_id,
        "task_summary": "Offline deterministic demo fixture",
        "allowed_scope": [
            "task summary",
            "privacy metadata",
            "route rationale",
            "validation status",
        ],
        "forbidden_scope": [
            "raw prompt",
            "raw data",
            "full context",
            "file contents",
        ],
        "privacy_level": "local_only",
        "context_strategy": "deterministic_summary",
        "raw_context_included": False,
    }
    proposed_output = {
        "status": "pending_review",
        "summary": DEMO_PROPOSED_OUTPUT,
    }
    validation = validate_demo_output(DEMO_PROPOSED_OUTPUT)

    if decision == "approve" and validation["passed"]:
        decision_state = "approved"
        finalized = True
    elif decision == "approve":
        decision_state = "approval_blocked"
        finalized = False
    elif decision == "reject":
        decision_state = "rejected"
        finalized = False
    else:
        decision_state = "pending_review"
        finalized = False

    human_decision = {
        "requested_decision": decision,
        "decision_state": decision_state,
        "finalized": finalized,
    }
    ledger_event = {
        "demo_mode": "dry_run",
        "task_id": task_id,
        "selected_route": route_decision["selected_route"],
        "route_reason": route_decision["reason"],
        "privacy_level": privacy_check["privacy_level"],
        "privacy_passed": privacy_check["passed"],
        "scoped_context_created": True,
        "raw_context_included": False,
        "proposed_output_status": proposed_output["status"],
        "validation_status": validation["status"],
        "decision_state": decision_state,
        "finalized": finalized,
    }

    resolved_ledger_dir = Path(ledger_dir)
    ledger = TaskLedger(str(resolved_ledger_dir))
    ledger.append_event(task_id, "demo_dry_run", ledger_event)
    ledger_path = str(resolved_ledger_dir / "ledger.jsonl")

    return DemoDryRunResult(
        task_id=task_id,
        messy_request=DEMO_MESSY_REQUEST,
        task_packet_summary=task_packet_summary,
        privacy_check=privacy_check,
        route_decision=route_decision,
        scoped_context=scoped_context,
        proposed_output=proposed_output,
        validation=validation,
        human_decision=human_decision,
        ledger_event=ledger_event,
        ledger_path=ledger_path,
    )


def format_demo_dry_run(result: DemoDryRunResult) -> str:
    lines = [
        "Messy Request",
        f"  {result.messy_request}",
        "TaskPacket Summary",
        (
            "  "
            f"task_id={result.task_packet_summary['task_id']} | "
            f"prompt_length={result.task_packet_summary['prompt_length']} | "
            f"data_length={result.task_packet_summary['data_length']} | "
            f"data_class={result.task_packet_summary['data_class']} | "
            "external_model_allowed="
            f"{result.task_packet_summary['external_model_allowed']}"
        ),
        "Privacy Check",
        (
            "  "
            f"privacy_level={result.privacy_check['privacy_level']} | "
            f"passed={result.privacy_check['passed']} | "
            f"detections={len(result.privacy_check['detections'])} | "
            f"violations={len(result.privacy_check['violations'])}"
        ),
        "Route Decision",
        (
            "  "
            f"selected_route={result.route_decision['selected_route']} | "
            f"backend_invoked={result.route_decision['backend_invoked']} | "
            f"reason={result.route_decision['reason']}"
        ),
        "Scoped Context",
        (
            "  "
            f"context_strategy={result.scoped_context['context_strategy']} | "
            "raw_context_included="
            f"{result.scoped_context['raw_context_included']} | "
            f"privacy_level={result.scoped_context['privacy_level']}"
        ),
        "Proposed Output",
        f"  status={result.proposed_output['status']} | {result.proposed_output['summary']}",
        "Validation",
        (
            "  "
            f"validator={result.validation['validator_name']} | "
            f"status={result.validation['status']} | "
            f"passed={result.validation['passed']}"
        ),
        "Human Decision",
        (
            "  "
            f"requested={result.human_decision['requested_decision']} | "
            f"decision_state={result.human_decision['decision_state']} | "
            f"finalized={result.human_decision['finalized']}"
        ),
        "Ledger Event",
        (
            "  "
            f"event_type=demo_dry_run | selected_route={result.ledger_event['selected_route']} | "
            f"validation_status={result.ledger_event['validation_status']} | "
            f"raw_context_included={result.ledger_event['raw_context_included']}"
        ),
        "Ledger Path",
        f"  {result.ledger_path}",
    ]
    return "\n".join(lines)
