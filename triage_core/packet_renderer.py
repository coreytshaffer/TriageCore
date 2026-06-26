"""
Packet renderer module.
Creates deterministic, bounded handoff packets for human review and
external model execution without autonomous network calls.
"""
import os
from typing import List, Optional
from dataclasses import dataclass

from triage_core.token_budget import TokenBudget
from triage_core.context_planner import estimate_tokens_conservative

@dataclass
class PacketRenderResult:
    content: str
    estimated_tokens: int
    fits_budget: bool
    budget: TokenBudget

def _read_file_text(path: str) -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        raise ValueError(f"File is binary or unreadable as UTF-8: {path}")

def render_packet(
    task_path: str,
    model_budget: TokenBudget,
    include_paths: Optional[List[str]] = None
) -> PacketRenderResult:
    includes = include_paths or []

    task_text = _read_file_text(task_path)
    included_contents = []
    for inc_path in includes:
        text = _read_file_text(inc_path)
        included_contents.append((inc_path, text))

    # Build core content to estimate
    core_lines = []
    core_lines.append("## Task")
    core_lines.append(f"Source: `{task_path}`\n")
    core_lines.append(task_text)
    core_lines.append("")

    core_lines.append("## Included Files")
    if included_contents:
        for path, text in included_contents:
            core_lines.append(f"### `{path}`")
            core_lines.append("```")
            core_lines.append(text)
            core_lines.append("```\n")
    else:
        core_lines.append("No additional files included.\n")

    core_lines.append("## Operator Constraints")
    core_lines.append("- Do not mutate source code outside the approved scope.")
    core_lines.append("- Do not bypass human approval gates.\n")

    core_lines.append("## Acceptance Checks")
    core_lines.append("- Ensure all changes match the requested implementation.")
    core_lines.append("- Do not introduce unrelated refactoring.\n")

    core_lines.append("## Safety Boundaries")
    core_lines.append("- No autonomous tool execution.")
    core_lines.append("- No arbitrary network access.\n")

    core_text = "\n".join(core_lines)

    lines = []
    lines.append("# TriageCore Handoff Packet\n")

    # We estimate the final text by doing a pre-estimate to embed the numbers.
    # The header overhead is roughly 150 chars, let's just add it.
    pre_estimate = estimate_tokens_conservative(core_text) + 40
    fits = pre_estimate <= model_budget.usable_input_tokens

    lines.append("## Model Budget")
    lines.append(f"- Model: {model_budget.model_name}")
    lines.append(f"- Usable tokens: {model_budget.usable_input_tokens}")
    lines.append(f"- Estimated tokens: ~{pre_estimate}\n")

    lines.append("## Context Plan")
    if fits:
        lines.append("Status: fits\n")
    else:
        lines.append("> **WARNING**: Status: over budget")
        lines.append(f"> Estimated packet size (~{pre_estimate}) exceeds usable budget ({model_budget.usable_input_tokens}).\n")

    lines.append(core_text)

    final_content = "\n".join(lines)
    final_estimated = estimate_tokens_conservative(final_content)
    final_fits = final_estimated <= model_budget.usable_input_tokens

    return PacketRenderResult(
        content=final_content,
        estimated_tokens=final_estimated,
        fits_budget=final_fits,
        budget=model_budget
    )
