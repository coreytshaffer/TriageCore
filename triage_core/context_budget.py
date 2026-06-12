import json
import math
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


ESTIMATED_CHARS_PER_TOKEN = 4
MAX_CONTEXT_SNIPPET_CHARS = 500
HELPFUL_FILE_CHAR_LIMIT = 20_000
OPTIONAL_FILE_CHAR_LIMIT = 80_000

DEFAULT_INCLUDED_FACETS = {
    "task_prompt",
    "target_file",
}

DEFAULT_EXCLUDED_FACETS = {
    "conversation_history",
    "user_preferences",
}

RUNNER_BUDGETS = {
    "local_llm": 4_000,
    "pipeline": 5_000,
    "worker_council": 8_000,
    "codex": 6_000,
    "antigravity": 6_000,
    "local_benchmark": 2_000,
}

CATEGORY_BUDGETS = {
    "structured_extraction": 1_200,
    "log_summary": 1_600,
    "python_generation": 2_500,
    "python_repair": 2_500,
    "safety_handoff": 800,
}


@dataclass
class ContextItem:
    kind: str
    label: str
    role: str
    estimated_tokens: int
    rationale: str
    facet: str = "unknown"
    included: bool = True
    exists: bool = True
    size_bytes: int = 0
    snippet: str = ""


@dataclass
class ContextPack:
    task_id: str
    created_at: str
    runner: str
    category: Optional[str]
    budget_tokens: int
    estimated_tokens: int
    budget_status: str
    items: List[ContextItem] = field(default_factory=list)
    excluded_items: List[ContextItem] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "items": [asdict(item) for item in self.items],
            "excluded_items": [asdict(item) for item in self.excluded_items],
        }


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / ESTIMATED_CHARS_PER_TOKEN))


def budget_for(runner: str, category: Optional[str] = None) -> int:
    if category in CATEGORY_BUDGETS:
        return CATEGORY_BUDGETS[category]
    return RUNNER_BUDGETS.get(runner, 4_000)


def build_context_pack(
    task_id: str,
    prompt: str,
    files: List[str],
    runner: str,
    category: Optional[str] = None,
    budget_tokens: Optional[int] = None,
    exclude_facets: Optional[set[str]] = None,
) -> ContextPack:
    budget = budget_tokens or budget_for(runner, category)
    excluded_facets = set(DEFAULT_EXCLUDED_FACETS)
    if exclude_facets:
        excluded_facets.update(exclude_facets)
    items: List[ContextItem] = [
        ContextItem(
            kind="prompt",
            label="task_prompt",
            role="required",
            estimated_tokens=estimate_tokens(prompt),
            rationale="The task prompt is required to execute or supervise the task.",
            facet="task_prompt",
            snippet=prompt[:MAX_CONTEXT_SNIPPET_CHARS],
        )
    ]
    excluded: List[ContextItem] = []
    items, pruned_items = _prune_items_by_facet(items, excluded_facets)
    excluded.extend(pruned_items)

    for file_path in files:
        item = _context_item_for_file(file_path)
        if item.role == "excluded":
            excluded.append(item)
        else:
            items.append(item)

    estimated = sum(item.estimated_tokens for item in items)
    status = "within_budget" if estimated <= budget else "over_budget"
    warnings: List[str] = []
    if status == "over_budget":
        warnings.append(
            f"Estimated context {estimated} tokens exceeds {budget} token budget."
        )
    if excluded:
        warnings.append(f"{len(excluded)} context item(s) were excluded.")

    return ContextPack(
        task_id=task_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        runner=runner,
        category=category,
        budget_tokens=budget,
        estimated_tokens=estimated,
        budget_status=status,
        items=items,
        excluded_items=excluded,
        warnings=warnings,
    )


def write_context_pack(pack: ContextPack, ledger_dir: str = ".triagecore") -> str:
    output_dir = os.path.join(ledger_dir, "context_packs")
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"context_pack_{pack.task_id[:8]}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pack.to_dict(), f, indent=2)
        f.write("\n")
    return path


def context_pack_event_payload(pack: ContextPack, artifact_path: str) -> Dict[str, Any]:
    return {
        "artifact_path": artifact_path,
        "context_pack_path": artifact_path,
        "context_strategy": "context_budget_planner_v1",
        "context_estimated_tokens": pack.estimated_tokens,
        "context_budget_tokens": pack.budget_tokens,
        "context_budget_status": pack.budget_status,
        "context_required_items": _count_role(pack.items, "required"),
        "context_helpful_items": _count_role(pack.items, "helpful"),
        "context_optional_items": _count_role(pack.items, "optional"),
        "context_excluded_items": len(pack.excluded_items),
        "context_warnings": pack.warnings,
    }


def create_context_pack_artifact(
    task_id: str,
    prompt: str,
    files: List[str],
    runner: str,
    ledger_dir: str = ".triagecore",
    category: Optional[str] = None,
    budget_tokens: Optional[int] = None,
    exclude_facets: Optional[set[str]] = None,
) -> tuple[ContextPack, str, Dict[str, Any]]:
    pack = build_context_pack(
        task_id=task_id,
        prompt=prompt,
        files=files,
        runner=runner,
        category=category,
        budget_tokens=budget_tokens,
        exclude_facets=exclude_facets,
    )
    artifact_path = write_context_pack(pack, ledger_dir=ledger_dir)
    return pack, artifact_path, context_pack_event_payload(pack, artifact_path)


def _context_item_for_file(file_path: str) -> ContextItem:
    if not os.path.exists(file_path):
        return ContextItem(
            kind="file",
            label=file_path,
            role="excluded",
            exists=False,
            estimated_tokens=0,
            rationale="The requested file path does not exist.",
            facet="target_file",
            included=False,
        )

    size = os.path.getsize(file_path)
    role = "helpful"
    rationale = "Target file is small enough to include directly."
    if size > OPTIONAL_FILE_CHAR_LIMIT:
        role = "excluded"
        rationale = "Target file is too large for the initial context pack."
    elif size > HELPFUL_FILE_CHAR_LIMIT:
        role = "optional"
        rationale = "Target file is large; prefer summary or targeted excerpts."

    snippet = ""
    estimated_tokens = estimate_tokens_by_size(size)
    if role != "excluded":
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                snippet = f.read(MAX_CONTEXT_SNIPPET_CHARS)
        except UnicodeDecodeError:
            role = "excluded"
            rationale = "Target file appears to be binary or non-UTF-8 text."
            estimated_tokens = 0
            snippet = ""

    return ContextItem(
        kind="file",
        label=file_path,
        role=role,
        facet="target_file",
        included=role != "excluded",
        exists=True,
        size_bytes=size,
        estimated_tokens=estimated_tokens,
        rationale=rationale,
        snippet=snippet,
    )


def estimate_tokens_by_size(size_bytes: int) -> int:
    return max(1, math.ceil(size_bytes / ESTIMATED_CHARS_PER_TOKEN))


def _count_role(items: List[ContextItem], role: str) -> int:
    return sum(1 for item in items if item.role == role)


def _prune_items_by_facet(
    items: List[ContextItem],
    excluded_facets: set[str],
) -> tuple[List[ContextItem], List[ContextItem]]:
    included_items: List[ContextItem] = []
    excluded_items: List[ContextItem] = []

    for item in items:
        if item.facet in excluded_facets:
            excluded_items.append(
                ContextItem(
                    kind=item.kind,
                    label=item.label,
                    role="excluded",
                    estimated_tokens=0,
                    rationale=f"Excluded by deterministic facet policy for '{item.facet}'.",
                    facet=item.facet,
                    included=False,
                    exists=item.exists,
                    size_bytes=item.size_bytes,
                    snippet="",
                )
            )
            continue

        included_items.append(item)

    return included_items, excluded_items
