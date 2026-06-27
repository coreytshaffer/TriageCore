"""
Workspace Board — read-only orientation views for TriageCore work items.

Loads work items from local YAML or JSON files and renders them as:
  - Kanban board (grouped by status, sorted by priority)
  - WBS outline (grouped by area → project → component)

Design invariants:
  - Pure read-only: never writes files, executes commands, calls APIs, or invokes models.
  - Fail-closed: missing files, malformed data, and unknown enum values all raise exceptions.
  - No private data in public code: real work-item files live outside the repo.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Enums — authoritative allowed values
# ---------------------------------------------------------------------------

class Status(Enum):
    BACKLOG = "backlog"
    READY = "ready"
    ACTIVE = "active"
    REVIEW = "review"
    BLOCKED = "blocked"
    DONE = "done"
    PARKED = "parked"


class Priority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SOMEDAY = "someday"


class ProcessGroup(Enum):
    INITIATING = "initiating"
    PLANNING = "planning"
    EXECUTING = "executing"
    MONITORING_CONTROLLING = "monitoring-controlling"
    CLOSING = "closing"


class LifecycleModel(Enum):
    PREDICTIVE = "predictive"
    AGILE = "agile"
    HYBRID = "hybrid"
    RESEARCH = "research"
    OPERATIONAL = "operational"


class GtdList(Enum):
    INBOX = "inbox"
    NEXT_ACTIONS = "next-actions"
    WAITING_FOR = "waiting-for"
    SOMEDAY_MAYBE = "someday-maybe"
    REFERENCE = "reference"


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EnergyLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ResponseStrategy(Enum):
    AVOID = "avoid"
    MITIGATE = "mitigate"
    TRANSFER = "transfer"
    ACCEPT = "accept"
    ESCALATE = "escalate"


class DataSensitivity(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# ---------------------------------------------------------------------------
# Helper — safe enum parsing with clear error messages
# ---------------------------------------------------------------------------

def _parse_enum(enum_cls: type[Enum], value: str, field_path: str, item_id: str) -> Enum:
    """Parse a string into an enum member, raising ValueError with a clear message on failure."""
    try:
        return enum_cls(value)
    except ValueError:
        allowed = ", ".join(e.value for e in enum_cls)
        raise ValueError(
            f"Invalid {field_path} for item {item_id}: {value!r} "
            f"(allowed: {allowed})"
        )


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class KanbanState:
    status: Status
    priority: Priority
    blocked_by: list[str] = field(default_factory=list)


@dataclass
class PmiFields:
    process_group: ProcessGroup
    lifecycle_model: Optional[LifecycleModel] = None
    deliverable: Optional[str] = None
    objective: Optional[str] = None
    acceptance_criteria: list[str] = field(default_factory=list)
    stakeholders: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)


@dataclass
class GtdFields:
    next_action: str
    gtd_list: Optional[GtdList] = None
    desired_outcome: Optional[str] = None
    context: list[str] = field(default_factory=list)
    energy: Optional[EnergyLevel] = None
    time_estimate: Optional[str] = None
    waiting_for: list[str] = field(default_factory=list)
    someday_maybe: bool = False


@dataclass
class WbsFields:
    area: Optional[str] = None
    package: Optional[str] = None
    component: Optional[str] = None


@dataclass
class RiskEntry:
    id: str
    description: str
    category: Optional[str] = None
    probability: Optional[RiskLevel] = None
    impact: Optional[RiskLevel] = None
    response_strategy: Optional[ResponseStrategy] = None
    response: Optional[str] = None


@dataclass
class RiskFields:
    level: Optional[RiskLevel] = None
    register: list[RiskEntry] = field(default_factory=list)


@dataclass
class ClosingEvidence:
    commits: list[str] = field(default_factory=list)
    prs: list[str] = field(default_factory=list)
    docs: list[str] = field(default_factory=list)


@dataclass
class ValidationFields:
    required_checks: list[str] = field(default_factory=list)


@dataclass
class ClosingFields:
    done_definition: list[str] = field(default_factory=list)
    lessons_learned: list[str] = field(default_factory=list)
    evidence: Optional[ClosingEvidence] = None


@dataclass
class WorkItem:
    id: str
    project: str
    title: str
    type: str
    kanban: KanbanState
    pmi: Optional[PmiFields] = None
    gtd: Optional[GtdFields] = None
    wbs: Optional[WbsFields] = None
    risk: Optional[RiskFields] = None
    validation: Optional[ValidationFields] = None
    closing: Optional[ClosingFields] = None
    owner: Optional[str] = None
    primary_tool: Optional[str] = None
    reviewer_tool: Optional[str] = None
    data_sensitivity: Optional[DataSensitivity] = None
    notes: Optional[str] = None


# ---------------------------------------------------------------------------
# Loaders — parse raw dicts into validated dataclasses
# ---------------------------------------------------------------------------

def _parse_kanban(raw: dict[str, Any], item_id: str) -> KanbanState:
    """Parse and validate the kanban section."""
    if not isinstance(raw, dict):
        raise ValueError(f"kanban section for item {item_id} must be a mapping")
    if "status" not in raw:
        raise ValueError(f"Missing kanban.status for item {item_id}")
    if "priority" not in raw:
        raise ValueError(f"Missing kanban.priority for item {item_id}")
    return KanbanState(
        status=_parse_enum(Status, raw["status"], "kanban.status", item_id),
        priority=_parse_enum(Priority, raw["priority"], "kanban.priority", item_id),
        blocked_by=raw.get("blocked_by", []),
    )


def _parse_pmi(raw: dict[str, Any], item_id: str) -> PmiFields:
    """Parse and validate the optional PMI section."""
    if "process_group" not in raw:
        raise ValueError(f"Missing pmi.process_group for item {item_id}")
    lifecycle = None
    if "lifecycle_model" in raw:
        lifecycle = _parse_enum(LifecycleModel, raw["lifecycle_model"], "pmi.lifecycle_model", item_id)
    return PmiFields(
        process_group=_parse_enum(ProcessGroup, raw["process_group"], "pmi.process_group", item_id),
        lifecycle_model=lifecycle,
        deliverable=raw.get("deliverable"),
        objective=raw.get("objective"),
        acceptance_criteria=raw.get("acceptance_criteria", []),
        stakeholders=raw.get("stakeholders", []),
        constraints=raw.get("constraints", []),
        assumptions=raw.get("assumptions", []),
    )


def _parse_gtd(raw: dict[str, Any], item_id: str) -> GtdFields:
    """Parse and validate the optional GTD section. Requires next_action when present."""
    if "next_action" not in raw:
        raise ValueError(f"Missing gtd.next_action for item {item_id}: "
                         f"if a gtd section is present, next_action is required")
    gtd_list = None
    if "list" in raw:
        gtd_list = _parse_enum(GtdList, raw["list"], "gtd.list", item_id)
    energy = None
    if "energy" in raw:
        energy = _parse_enum(EnergyLevel, raw["energy"], "gtd.energy", item_id)
    return GtdFields(
        next_action=raw["next_action"],
        gtd_list=gtd_list,
        desired_outcome=raw.get("desired_outcome"),
        context=raw.get("context", []),
        energy=energy,
        time_estimate=raw.get("time_estimate"),
        waiting_for=raw.get("waiting_for", []),
        someday_maybe=raw.get("someday_maybe", False),
    )


def _parse_wbs(raw: dict[str, Any], item_id: str) -> WbsFields:
    """Parse the optional WBS section. All fields are optional."""
    return WbsFields(
        area=raw.get("area"),
        package=raw.get("package"),
        component=raw.get("component"),
    )


def _parse_risk_entry(raw: dict[str, Any], item_id: str, index: int) -> RiskEntry:
    """Parse and validate a single risk register entry."""
    if "id" not in raw:
        raise ValueError(f"Missing risk.register[{index}].id for item {item_id}")
    if "description" not in raw:
        raise ValueError(f"Missing risk.register[{index}].description for item {item_id}")
    probability = None
    if "probability" in raw:
        probability = _parse_enum(RiskLevel, raw["probability"],
                                  f"risk.register[{index}].probability", item_id)
    impact = None
    if "impact" in raw:
        impact = _parse_enum(RiskLevel, raw["impact"],
                             f"risk.register[{index}].impact", item_id)
    strategy = None
    if "response_strategy" in raw:
        strategy = _parse_enum(ResponseStrategy, raw["response_strategy"],
                               f"risk.register[{index}].response_strategy", item_id)
    return RiskEntry(
        id=raw["id"],
        description=raw["description"],
        category=raw.get("category"),
        probability=probability,
        impact=impact,
        response_strategy=strategy,
        response=raw.get("response"),
    )


def _parse_risk(raw: dict[str, Any], item_id: str) -> RiskFields:
    """Parse and validate the optional risk section."""
    level = None
    if "level" in raw:
        level = _parse_enum(RiskLevel, raw["level"], "risk.level", item_id)
    entries = []
    for i, entry_raw in enumerate(raw.get("register", [])):
        entries.append(_parse_risk_entry(entry_raw, item_id, i))
    return RiskFields(level=level, register=entries)


def _parse_validation(raw: dict[str, Any], item_id: str) -> ValidationFields:
    """Parse the optional validation section."""
    return ValidationFields(
        required_checks=raw.get("required_checks", []),
    )


def _parse_closing_evidence(raw: dict[str, Any]) -> ClosingEvidence:
    """Parse the optional closing.evidence section."""
    return ClosingEvidence(
        commits=raw.get("commits", []),
        prs=raw.get("prs", []),
        docs=raw.get("docs", []),
    )


def _parse_closing(raw: dict[str, Any], item_id: str) -> ClosingFields:
    """Parse the optional closing section."""
    evidence = None
    if "evidence" in raw:
        evidence = _parse_closing_evidence(raw["evidence"])
    return ClosingFields(
        done_definition=raw.get("done_definition", []),
        lessons_learned=raw.get("lessons_learned", []),
        evidence=evidence,
    )


def _parse_work_item(raw: dict[str, Any], index: int) -> WorkItem:
    """Parse and validate a single work item dict into a WorkItem dataclass."""
    # Required top-level fields
    for req in ("id", "project", "title", "type"):
        if req not in raw:
            raise ValueError(f"Missing required field '{req}' in item at index {index}")

    item_id = raw["id"]

    # kanban is required
    if "kanban" not in raw:
        raise ValueError(f"Missing required section 'kanban' for item {item_id}")

    kanban = _parse_kanban(raw["kanban"], item_id)

    # Optional sections
    pmi = _parse_pmi(raw["pmi"], item_id) if "pmi" in raw else None
    gtd = _parse_gtd(raw["gtd"], item_id) if "gtd" in raw else None
    wbs = _parse_wbs(raw["wbs"], item_id) if "wbs" in raw else None
    risk = _parse_risk(raw["risk"], item_id) if "risk" in raw else None
    validation = _parse_validation(raw["validation"], item_id) if "validation" in raw else None
    closing = _parse_closing(raw["closing"], item_id) if "closing" in raw else None

    # Optional scalar fields
    data_sensitivity = None
    if "data_sensitivity" in raw:
        data_sensitivity = _parse_enum(DataSensitivity, raw["data_sensitivity"],
                                       "data_sensitivity", item_id)

    return WorkItem(
        id=item_id,
        project=raw["project"],
        title=raw["title"],
        type=raw["type"],
        kanban=kanban,
        pmi=pmi,
        gtd=gtd,
        wbs=wbs,
        risk=risk,
        validation=validation,
        closing=closing,
        owner=raw.get("owner"),
        primary_tool=raw.get("primary_tool"),
        reviewer_tool=raw.get("reviewer_tool"),
        data_sensitivity=data_sensitivity,
        notes=raw.get("notes"),
    )


# ---------------------------------------------------------------------------
# File loading
# ---------------------------------------------------------------------------

def load_work_items(path: str) -> list[WorkItem]:
    """Load and validate work items from a YAML or JSON file.

    Supports .yaml, .yml, and .json extensions.
    Raises FileNotFoundError for missing files, ValueError for malformed or invalid data.
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"Work items file not found: {path}")

    ext = os.path.splitext(path)[1].lower()

    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    if ext in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML is required to load YAML work item files. "
                              "Install it with: pip install pyyaml")
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise ValueError(f"Malformed YAML in {path}: {e}")
    elif ext == ".json":
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Malformed JSON in {path}: {e}")
    else:
        raise ValueError(f"Unsupported file extension {ext!r} for {path}. "
                         f"Use .yaml, .yml, or .json.")

    if not isinstance(data, dict):
        raise ValueError(f"Work items file must contain a mapping, got {type(data).__name__}")

    if "version" not in data:
        raise ValueError(f"Missing required field 'version' in {path}")
    if data["version"] != 1:
        raise ValueError(f"Unsupported schema version {data['version']} in {path}. "
                         f"Only version 1 is supported.")

    if "items" not in data:
        raise ValueError(f"Missing required field 'items' in {path}")
    if not isinstance(data["items"], list):
        raise ValueError(f"'items' must be a list in {path}")

    items = []
    for i, raw_item in enumerate(data["items"]):
        if not isinstance(raw_item, dict):
            raise ValueError(f"Item at index {i} must be a mapping, got {type(raw_item).__name__}")
        items.append(_parse_work_item(raw_item, i))

    return items


# ---------------------------------------------------------------------------
# Board rendering
# ---------------------------------------------------------------------------

# Display order for statuses on the board — lifecycle order, not alphabetical
_STATUS_DISPLAY_ORDER = [
    Status.ACTIVE,
    Status.REVIEW,
    Status.BLOCKED,
    Status.READY,
    Status.BACKLOG,
    Status.PARKED,
    Status.DONE,
]

# Priority sort key — lower number = higher priority
_PRIORITY_SORT_KEY = {
    Priority.CRITICAL: 0,
    Priority.HIGH: 1,
    Priority.MEDIUM: 2,
    Priority.LOW: 3,
    Priority.SOMEDAY: 4,
}


def _get_next_action(item: WorkItem) -> str:
    """Extract the next action string from GTD or return empty string."""
    if item.gtd and item.gtd.next_action:
        return item.gtd.next_action
    return ""


def _get_pmi_phase(item: WorkItem) -> str:
    """Extract the PMI process group label or return empty string."""
    if item.pmi:
        return item.pmi.process_group.value
    return ""


def _get_risk_level(item: WorkItem) -> str:
    """Extract the risk level or return empty string."""
    if item.risk and item.risk.level:
        return item.risk.level.value
    return ""


def render_board(items: list[WorkItem], statuses: Optional[list[str]] = None) -> str:
    """Render work items as a Kanban-style Markdown board.

    Args:
        items: List of validated WorkItem instances.
        statuses: Optional list of status strings to filter by. If None, show all.

    Returns:
        Markdown string with items grouped by status, sorted by priority → project → id.
    """
    if not items:
        return "# Workspace Board\n\nNo work items found.\n"

    # Determine which statuses to show
    if statuses:
        show_statuses = []
        for s in statuses:
            try:
                show_statuses.append(Status(s))
            except ValueError:
                allowed = ", ".join(e.value for e in Status)
                raise ValueError(f"Invalid status filter: {s!r} (allowed: {allowed})")
    else:
        show_statuses = list(_STATUS_DISPLAY_ORDER)

    # Group items by status
    by_status: dict[Status, list[WorkItem]] = {s: [] for s in show_statuses}
    for item in items:
        if item.kanban.status in by_status:
            by_status[item.kanban.status].append(item)

    # Sort within each group: priority (asc), project (asc), id (asc)
    def sort_key(item: WorkItem):
        return (
            _PRIORITY_SORT_KEY.get(item.kanban.priority, 99),
            item.project.lower(),
            item.id.lower(),
        )

    lines = ["# Workspace Board", ""]

    any_items = False
    for status in show_statuses:
        group = sorted(by_status[status], key=sort_key)
        if not group:
            continue
        any_items = True

        status_label = status.value.capitalize()
        if status == Status.MONITORING_CONTROLLING if hasattr(Status, "MONITORING_CONTROLLING") else False:
            status_label = "Monitoring & Controlling"

        lines.append(f"## {status_label}")
        lines.append("")
        lines.append("| Priority | Project | ID | PMI Phase | Work Item | Risk | Next Action |")
        lines.append("|---|---|---|---|---|---|---|")
        for item in group:
            pmi_phase = _get_pmi_phase(item)
            risk = _get_risk_level(item)
            next_action = _get_next_action(item)
            lines.append(
                f"| {item.kanban.priority.value} "
                f"| {item.project} "
                f"| {item.id} "
                f"| {pmi_phase} "
                f"| {item.title} "
                f"| {risk} "
                f"| {next_action} |"
            )
        lines.append("")

    if not any_items:
        lines.append("No work items match the selected statuses.")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# WBS rendering
# ---------------------------------------------------------------------------

def render_wbs(items: list[WorkItem]) -> str:
    """Render work items as a hierarchical WBS outline.

    Groups by wbs.area → project → wbs.component.
    Items without a wbs section are grouped under "(Unclassified)".

    Returns:
        Markdown string with hierarchical WBS outline.
    """
    if not items:
        return "# Work Breakdown Structure\n\nNo work items found.\n"

    # Build hierarchy: area → project → list of (component, item)
    hierarchy: dict[str, dict[str, list[tuple[str, WorkItem]]]] = {}

    for item in items:
        area = "(Unclassified)"
        component = ""
        if item.wbs:
            if item.wbs.area:
                area = item.wbs.area
            if item.wbs.component:
                component = item.wbs.component

        if area not in hierarchy:
            hierarchy[area] = {}
        if item.project not in hierarchy[area]:
            hierarchy[area][item.project] = []
        hierarchy[area][item.project].append((component, item))

    lines = ["# Work Breakdown Structure", ""]

    for area in sorted(hierarchy.keys()):
        # Format area name for display
        area_display = area.replace("_", " ").title()
        lines.append(f"## {area_display}")
        lines.append("")

        projects = hierarchy[area]
        for project in sorted(projects.keys()):
            lines.append(f"### {project}")
            lines.append("")

            components = projects[project]
            # Group by component
            by_component: dict[str, list[WorkItem]] = {}
            for comp, item in components:
                comp_key = comp if comp else "(No component)"
                if comp_key not in by_component:
                    by_component[comp_key] = []
                by_component[comp_key].append(item)

            for comp in sorted(by_component.keys()):
                if comp != "(No component)":
                    lines.append(f"**{comp}**")
                    lines.append("")
                for item in sorted(by_component[comp], key=lambda x: x.id.lower()):
                    status_badge = item.kanban.status.value
                    priority_badge = item.kanban.priority.value
                    lines.append(
                        f"- `{item.id}` {item.title} "
                        f"[{status_badge}] [{priority_badge}]"
                    )
                lines.append("")

    return "\n".join(lines)
