import json
from triage_core.workspace_board import WorkItem, RiskLevel

def generate_handoff(item: WorkItem, tool: str, fmt: str = "text") -> str:
    """
    Generates a copyable handoff packet for a specific tool.
    Supported tools: codex, chatgpt, status, closing
    Supported formats: text, markdown, json
    """
    if tool not in ["codex", "chatgpt", "status", "closing"]:
        raise ValueError(f"Unknown tool profile: {tool}")

    if fmt not in ["text", "markdown", "json"]:
        raise ValueError(f"Unknown output format: {fmt}")

    # Extract clean, public fields
    title = item.ux.short_label if item.ux and item.ux.short_label else item.title
    objective = item.pmi.objective if item.pmi and item.pmi.objective else (
        item.gtd.desired_outcome if item.gtd and item.gtd.desired_outcome else ""
    )
    next_action = item.gtd.next_action if item.gtd and item.gtd.next_action else ""
    acc_criteria = item.pmi.acceptance_criteria if item.pmi and item.pmi.acceptance_criteria else []
    
    stop_rule = item.handoff.stop_rule if item.handoff and item.handoff.stop_rule else ""
    return_fmt = item.handoff.return_format if item.handoff and item.handoff.return_format else []
    
    risk = item.risk.level.value if item.risk and item.risk.level else "none"
    checks = item.validation.required_checks if item.validation and item.validation.required_checks else []

    data = {
        "id": item.id,
        "project": item.project,
        "title": title,
        "objective": objective,
        "next_action": next_action,
        "acceptance_criteria": acc_criteria,
        "stop_rule": stop_rule,
        "risk": risk,
        "required_checks": checks,
        "return_format": return_fmt,
    }

    if fmt == "json":
        return json.dumps(data, indent=2, sort_keys=True)

    # Text / Markdown generation
    is_md = (fmt == "markdown")
    b = "**" if is_md else ""
    
    lines = []
    
    if tool == "codex":
        lines.append(f"{b}HANDOFF: {item.id}{b}")
        if is_md:
            lines.append("==================")
        else:
            lines.append("=" * (9 + len(item.id)))
        lines.append("")
        lines.append(f"{b}Target tool:{b} Codex")
        lines.append(f"{b}Project:{b} {item.project}")
        lines.append(f"{b}Work item:{b} {title}")
        lines.append(f"{b}Risk:{b} {risk}")
        lines.append("")
        
        if objective:
            lines.append(f"{b}Objective:{b}")
            lines.append(objective)
            lines.append("")
            
        if next_action:
            lines.append(f"{b}Next action:{b}")
            lines.append(next_action)
            lines.append("")
            
        if stop_rule:
            lines.append(f"{b}Stop rule:{b}")
            lines.append(f"- {stop_rule}")
            lines.append("")
            
        if acc_criteria:
            lines.append(f"{b}Acceptance criteria:{b}")
            for crit in acc_criteria:
                lines.append(f"- {crit}")
            lines.append("")
            
        if checks:
            lines.append(f"{b}Required checks:{b}")
            for c in checks:
                lines.append(f"- {c}")
            lines.append("")
            
        if return_fmt:
            lines.append(f"{b}Return format:{b}")
            for r in return_fmt:
                lines.append(f"- {r}")
            lines.append("")
            
    elif tool == "chatgpt":
        lines.append(f"{b}REVIEW HANDOFF: {item.id}{b}")
        lines.append("")
        lines.append(f"{b}Project:{b} {item.project}")
        lines.append(f"{b}Feature:{b} {title}")
        lines.append("")
        if objective:
            lines.append(f"{b}Context / Objective:{b}")
            lines.append(objective)
            lines.append("")
        lines.append(f"{b}Please assess:{b}")
        lines.append("- scope creep")
        lines.append("- privacy boundary")
        lines.append("- test adequacy")
        lines.append("- UX clarity")
        lines.append("- next best slice")
        lines.append("")
        
    elif tool == "status":
        lines.append(f"{b}STATUS UPDATE: {item.id}{b}")
        lines.append(f"{item.project} - {title}")
        if next_action:
            lines.append(f"Current focus: {next_action}")
        lines.append("")
            
    elif tool == "closing":
        lines.append(f"{b}CLOSING PACKET: {item.id}{b}")
        lines.append(f"{item.project} - {title}")
        lines.append("")
        if acc_criteria:
            lines.append(f"{b}Verified criteria:{b}")
            for crit in acc_criteria:
                lines.append(f"[ ] {crit}")
            lines.append("")
        if checks:
            lines.append(f"{b}Checks passed:{b}")
            for c in checks:
                lines.append(f"[ ] {c}")
            lines.append("")
        lines.append(f"{b}Evidence:{b}")
        lines.append("- <insert PR/commit links here>")
        lines.append("")
        
    return "\n".join(lines).strip()
