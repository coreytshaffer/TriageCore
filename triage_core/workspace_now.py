"""
Workspace Now — read-only focus view for TriageCore work items.

Loads a today.yaml focus list and correlates it with the main work_items.yaml,
providing a filtered view of what matters today.

Design invariants:
  - Pure read-only: never writes files, executes commands, calls APIs, or invokes models.
  - Fail-closed: unknown focus IDs raise an exception.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Optional

from triage_core.workspace_board import WorkItem, Status, Priority, RiskLevel


@dataclass
class TodayLimits:
    max_active_items: Optional[int] = None
    max_high_risk_items: Optional[int] = None


@dataclass
class TodayFocus:
    focus: list[str]
    date: Optional[str] = None
    limits: Optional[TodayLimits] = None
    notes: list[str] = field(default_factory=list)


def load_today_file(filepath: str) -> TodayFocus:
    """Load and validate the today.yaml file."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Today file not found: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".json":
        with open(filepath, "r", encoding="utf-8") as f:
            raw = json.load(f)
    elif ext in (".yaml", ".yml"):
        try:
            import yaml
            with open(filepath, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
        except ImportError:
            raise ImportError("PyYAML is required to load YAML files.")
        except Exception as e:
            raise ValueError(f"Failed to parse YAML: {e}")
    else:
        raise ValueError(f"Unsupported file extension: {ext}. Must be .yaml or .json")
    
    if not raw:
        raw = {}

    if not isinstance(raw, dict):
        raise ValueError("Today file must contain a mapping (object) at the root level.")

    if "focus" not in raw:
        raise ValueError("Missing required field 'focus' in today file.")
    
    focus_list = raw["focus"]
    if not isinstance(focus_list, list):
        raise ValueError("'focus' must be a list of item IDs.")

    limits_raw = raw.get("limits")
    limits = None
    if limits_raw:
        if not isinstance(limits_raw, dict):
            raise ValueError("'limits' must be a mapping.")
        limits = TodayLimits(
            max_active_items=limits_raw.get("max_active_items"),
            max_high_risk_items=limits_raw.get("max_high_risk_items")
        )
    
    date_val = raw.get("date")
    if date_val is not None:
        date_val = str(date_val)

    return TodayFocus(
        focus=focus_list,
        date=date_val,
        limits=limits,
        notes=raw.get("notes", [])
    )


def render_now(work_items: list[WorkItem], today: TodayFocus) -> str:
    """Render the Workspace Now view."""
    
    # Create lookup map
    item_map = {item.id: item for item in work_items}
    
    # Resolve focus items
    focus_items = []
    high_risk_count = 0
    for fid in today.focus:
        if fid not in item_map:
            raise ValueError(f"Focus ID {fid!r} not found in work items.")
        item = item_map[fid]
        focus_items.append(item)
        if item.risk and item.risk.level == RiskLevel.HIGH:
            high_risk_count += 1
            
    # Gather other items of interest
    blocked_items = []
    review_items = []
    for item in work_items:
        if item.id in today.focus:
            continue  # Already in focus list
        if item.kanban.status == Status.BLOCKED:
            blocked_items.append(item)
        elif item.kanban.status == Status.REVIEW:
            review_items.append(item)
            
    # Check limits
    warnings = []
    if today.limits:
        if today.limits.max_active_items is not None and len(focus_items) > today.limits.max_active_items:
            warnings.append(f"Focus list contains {len(focus_items)} items; limit is {today.limits.max_active_items}.")
        if today.limits.max_high_risk_items is not None and high_risk_count > today.limits.max_high_risk_items:
            warnings.append(f"Focus list contains {high_risk_count} high risk items; limit is {today.limits.max_high_risk_items}.")

    lines = []
    lines.append("Workspace Now")
    lines.append("=============\n")
    
    lines.append("Focus:")
    for idx, item in enumerate(focus_items, 1):
        risk_str = item.risk.level.value if item.risk and item.risk.level else "none"
        lines.append(f"{idx}. {item.id} | {item.project} | {item.title}")
        
        next_action = ""
        if item.gtd and item.gtd.next_action:
            next_action = item.gtd.next_action
            
        if next_action:
            lines.append(f"   Next: {next_action}")
        
        tool_str = ""
        if item.primary_tool:
            tool_str = item.primary_tool
            
        if tool_str:
            lines.append(f"   Tool: {tool_str}")
            
        lines.append(f"   Risk: {risk_str}\n")
        
    if warnings:
        lines.append("Warnings:")
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")
        
    if blocked_items:
        lines.append("Blocked:")
        for item in blocked_items:
            lines.append(f"- {item.id} | {item.project} | {item.title}")
            blocked_reasons = item.kanban.blocked_by
            if blocked_reasons:
                lines.append(f"  Blocker: {blocked_reasons[0]}")
        lines.append("")
        
    if review_items:
        lines.append("Review:")
        for item in review_items:
            lines.append(f"- {item.id} | {item.project} | {item.title}")
            next_action = item.gtd.next_action if item.gtd else ""
            if next_action:
                lines.append(f"  Next: {next_action}")
        lines.append("")
        
    return "\n".join(lines).rstrip() + "\n"
