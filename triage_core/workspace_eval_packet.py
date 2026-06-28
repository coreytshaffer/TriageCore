from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from triage_core.workspace_board import WorkItem
from triage_core.workspace_now import TodayFocus
from triage_core.workspace_review import is_someday, is_stale


CASE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def _default_case_id(item_id: str) -> str:
    slug = item_id.strip().lower().replace(" ", "_")
    slug = re.sub(r"[^a-z0-9_-]", "_", slug)
    return f"workspace_{slug}"


def _validate_case_id(case_id: str) -> None:
    if not case_id or not isinstance(case_id, str):
        raise ValueError("case_id must be a non-empty string.")
    if not CASE_ID_PATTERN.match(case_id):
        raise ValueError(f"case_id '{case_id}' is not path-safe.")


def _observation(code: str, value: Any) -> dict[str, Any]:
    return {"code": code, "value": value}


def build_workspace_evaluator_packet(
    item: WorkItem,
    *,
    today: Optional[TodayFocus] = None,
    case_id: Optional[str] = None,
    stale_after_days: int = 14,
    generated_at: Optional[str] = None,
) -> dict[str, Any]:
    resolved_case_id = case_id or _default_case_id(item.id)
    _validate_case_id(resolved_case_id)

    today_focus_ids = today.focus if today else []
    in_today_focus = item.id in today_focus_ids
    focus_rank = today_focus_ids.index(item.id) + 1 if in_today_focus else None

    observations = [
        _observation("kanban_status", item.kanban.status.value),
        _observation("kanban_priority", item.kanban.priority.value),
        _observation("in_today_focus", in_today_focus),
        _observation("is_blocked", bool(item.kanban.blocked_by)),
        _observation("is_stale", is_stale(item, default_stale_days=stale_after_days)),
        _observation("is_someday", is_someday(item)),
        _observation("has_handoff", item.handoff is not None),
        _observation("has_stop_rule", bool(item.handoff and item.handoff.stop_rule)),
        _observation("has_required_checks", bool(item.validation and item.validation.required_checks)),
        _observation("has_external_reference", item.external is not None),
        _observation("private_notes_omitted", item.notes is not None),
    ]

    external_summary: dict[str, Any] = {"source": item.external.source if item.external else None}
    if item.external and item.external.github:
        external_summary["github"] = {
            "repo": item.external.github.repo,
            "issue_number": item.external.github.issue_number,
            "state": item.external.github.state,
            "labels": item.external.github.labels,
            "updated_at": item.external.github.updated_at,
            "url": item.external.github.url,
        }

    packet = {
        "schema_version": "workspace_evaluator_input_v1",
        "packet_kind": "workspace_evaluator_input",
        "case_id": resolved_case_id,
        "generated_at": generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {
            "system": "TriageCore",
            "subsystem": "Workspace Unifier",
            "export_command": "tc workspace export-eval",
        },
        "boundary": {
            "triagecore_scores_packet": False,
            "external_evaluator_required": True,
            "evaluator_can_approve": False,
            "approval_authority": "human",
        },
        "work_item": {
            "id": item.id,
            "project": item.project,
            "title": item.title,
            "type": item.type,
            "status": item.kanban.status.value,
            "priority": item.kanban.priority.value,
            "blocked_by": item.kanban.blocked_by,
            "owner": item.owner,
            "primary_tool": item.primary_tool,
            "reviewer_tool": item.reviewer_tool,
            "data_sensitivity": item.data_sensitivity.value if item.data_sensitivity else None,
            "process_group": item.pmi.process_group.value if item.pmi and item.pmi.process_group else None,
            "lifecycle_model": item.pmi.lifecycle_model.value if item.pmi and item.pmi.lifecycle_model else None,
            "deliverable": item.pmi.deliverable if item.pmi else None,
            "objective": item.pmi.objective if item.pmi else None,
            "next_action": item.gtd.next_action if item.gtd else None,
        },
        "focus_context": {
            "today_file_present": today is not None,
            "today_date": today.date if today else None,
            "in_today_focus": in_today_focus,
            "focus_rank": focus_rank,
            "max_active_items": today.limits.max_active_items if today and today.limits else None,
            "max_high_risk_items": today.limits.max_high_risk_items if today and today.limits else None,
            "today_notes_omitted": bool(today and today.notes),
        },
        "evidence_summary": {
            "required_checks": item.validation.required_checks if item.validation else [],
            "done_definition": item.closing.done_definition if item.closing else [],
            "closing_evidence": {
                "commit_count": len(item.closing.evidence.commits) if item.closing and item.closing.evidence else 0,
                "pr_count": len(item.closing.evidence.prs) if item.closing and item.closing.evidence else 0,
                "doc_count": len(item.closing.evidence.docs) if item.closing and item.closing.evidence else 0,
            },
            "external_reference": external_summary,
            "handoff": {
                "preferred_tool": item.handoff.preferred_tool if item.handoff else None,
                "reviewer_tool": item.handoff.reviewer_tool if item.handoff else None,
                "prompt_style": item.handoff.prompt_style if item.handoff else None,
                "stop_rule": item.handoff.stop_rule if item.handoff else None,
                "return_format": item.handoff.return_format if item.handoff else [],
            },
        },
        "observations": observations,
        "omissions": {
            "work_item_notes": item.notes is not None,
            "today_notes": bool(today and today.notes),
            "local_paths": True,
        },
        "non_claims": [
            "TriageCore did not score this packet.",
            "This packet does not approve actions.",
            "The independent evaluator remains external to TriageCore.",
        ],
    }
    return packet



def write_workspace_evaluator_packet(
    packet: Mapping[str, Any],
    output_path: str | Path,
    *,
    force: bool = False,
) -> Path:
    case_id = packet.get("case_id")
    _validate_case_id(case_id)

    target = Path(output_path)
    if target.exists() and not force:
        raise FileExistsError(f"Output file {target} already exists. Use --force to overwrite.")

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as f:
        json.dump(packet, f, indent=2, sort_keys=True)
        f.write("\n")
    return target
