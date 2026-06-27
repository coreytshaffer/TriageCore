"""
Workspace Dashboard — generates a static HTML orientation view for TriageCore.

Outputs a local, zero-dependency HTML file containing focus cards, blocked items,
and review items. Focuses on copyability for agent handoffs.

Design invariants:
  - Read-only data access (only mutates the explicitly requested output file).
  - Escapes all dynamic data to prevent script injection.
  - Zero external CSS/JS dependencies.
"""

from __future__ import annotations

import html
import datetime
from typing import Any

from triage_core.workspace_board import WorkItem, Status, RiskLevel
from triage_core.workspace_now import TodayFocus


def h(value: Any) -> str:
    """HTML-escape dynamic content to prevent injection."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _render_focus_card(item: WorkItem) -> str:
    """Render a single focus card in HTML."""
    title = h(item.ux.short_label if item.ux and item.ux.short_label else item.title)
    
    # Priority: Next action, Why it matters, Stop rule
    next_action = ""
    if item.gtd and item.gtd.next_action:
        next_action = h(item.gtd.next_action)
        
    why_it_matters = ""
    if item.ux and item.ux.why_it_matters:
        why_it_matters = h(item.ux.why_it_matters)
        
    stop_rule = ""
    if item.handoff and item.handoff.stop_rule:
        stop_rule = h(item.handoff.stop_rule)
        
    status_text = h(item.ux.friendly_status if item.ux and item.ux.friendly_status else item.kanban.status.value.title())
    priority_text = h(item.kanban.priority.value.title())
    risk_text = h(item.risk.level.value.title() if item.risk and item.risk.level else "None")
    
    pref_tool = h(item.handoff.preferred_tool if item.handoff and item.handoff.preferred_tool else item.primary_tool or "None")
    rev_tool = h(item.handoff.reviewer_tool if item.handoff and item.handoff.reviewer_tool else item.reviewer_tool or "None")

    card_html = f"""
    <div class="card">
        <div class="card-header">
            <strong>{h(item.id)}</strong>
            <div class="card-title">{title}</div>
        </div>
        
        <div class="card-meta">
            <span class="badge status-{h(item.kanban.status.value)}">Status: {status_text}</span>
            <span class="badge priority-{h(item.kanban.priority.value)}">Priority: {priority_text}</span>
            <span class="badge risk-{h(item.risk.level.value if item.risk and item.risk.level else 'none')}">Risk: {risk_text}</span>
        </div>
        
        <div class="card-action">
            <strong>Next:</strong> {next_action}
        </div>
    """
    
    if why_it_matters:
        card_html += f"""
        <div class="card-why">
            <strong>Why:</strong> {why_it_matters}
        </div>
        """
        
    if stop_rule:
        card_html += f"""
        <div class="card-stop">
            <strong>Stop rule:</strong> {stop_rule}
        </div>
        """
        
    card_html += f"""
        <div class="card-tools">
            <small>Tool: {pref_tool} | Review: {rev_tool}</small>
        </div>
        
        <div class="card-buttons">
            <button disabled title="Coming in CR-WU-006">Copy Codex Handoff</button>
            <button disabled title="Coming in CR-WU-006">Copy ChatGPT Prompt</button>
            <button disabled title="Coming in CR-WU-006">Copy Status Summary</button>
        </div>
    </div>
    """
    return card_html


def render_html(work_items: list[WorkItem], today: TodayFocus, generated_at: str | None = None) -> str:
    """Render the full HTML dashboard."""
    if generated_at is None:
        generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
    item_map = {item.id: item for item in work_items}
    
    focus_items = []
    high_risk_count = 0
    for fid in today.focus:
        if fid not in item_map:
            raise ValueError(f"Focus ID {fid!r} not found in work items.")
        item = item_map[fid]
        focus_items.append(item)
        if item.risk and item.risk.level == RiskLevel.HIGH:
            high_risk_count += 1
            
    blocked_items = []
    review_items = []
    for item in work_items:
        if item.id in today.focus:
            continue
        if item.kanban.status == Status.BLOCKED:
            blocked_items.append(item)
        elif item.kanban.status == Status.REVIEW:
            review_items.append(item)
            
    warnings = []
    if today.limits:
        if today.limits.max_active_items is not None and len(focus_items) > today.limits.max_active_items:
            warnings.append(f"Focus list contains {len(focus_items)} items; limit is {today.limits.max_active_items}.")
        if today.limits.max_high_risk_items is not None and high_risk_count > today.limits.max_high_risk_items:
            warnings.append(f"Focus list contains {high_risk_count} high risk items; limit is {today.limits.max_high_risk_items}.")

    css = """
    :root {
        --bg: #1e1e1e;
        --fg: #d4d4d4;
        --border: #444;
        --card-bg: #2d2d2d;
        --accent: #007acc;
        --warn: #d7ba7d;
        --error: #f48771;
        --success: #89d185;
    }
    body {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        background-color: var(--bg);
        color: var(--fg);
        margin: 0;
        padding: 20px;
        line-height: 1.5;
    }
    .header-banner {
        border: 1px solid var(--border);
        padding: 15px 20px;
        border-radius: 6px;
        margin-bottom: 30px;
        display: flex;
        justify-content: space-between;
        background: var(--card-bg);
    }
    .focus-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
        gap: 20px;
        margin-bottom: 40px;
    }
    .card {
        background: var(--card-bg);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
    }
    .card-header {
        border-bottom: 1px solid var(--border);
        padding-bottom: 8px;
    }
    .card-title {
        font-size: 1.1em;
        margin-top: 4px;
    }
    .badge {
        font-size: 0.8em;
        padding: 2px 6px;
        border-radius: 3px;
        background: #444;
        margin-right: 4px;
    }
    .status-blocked { background: var(--error); color: #000; }
    .status-done { background: var(--success); color: #000; }
    .status-active { background: var(--accent); color: #fff; }
    .risk-high { background: var(--error); color: #000; }
    .risk-medium { background: var(--warn); color: #000; }
    .card-action {
        font-size: 1.05em;
        color: #fff;
    }
    .card-why { font-style: italic; color: #aaa; }
    .card-stop { color: var(--warn); }
    .card-tools { color: #888; }
    .card-buttons {
        display: flex;
        flex-direction: column;
        gap: 6px;
        margin-top: auto;
    }
    button {
        background: #444;
        color: #888;
        border: 1px solid #555;
        border-radius: 3px;
        padding: 6px;
        cursor: not-allowed;
        text-align: left;
    }
    .list-section {
        margin-bottom: 30px;
    }
    .list-section h2 {
        border-bottom: 1px solid var(--border);
        padding-bottom: 5px;
    }
    ul { list-style-type: none; padding-left: 0; }
    li { margin-bottom: 10px; padding-left: 10px; border-left: 3px solid var(--border); }
    .blocked-li { border-left-color: var(--error); }
    .warning-li { border-left-color: var(--warn); }
    """
    
    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "<meta charset='utf-8'>",
        "<title>TriageCore Workspace</title>",
        f"<style>{css}</style>",
        "</head>",
        "<body>"
    ]
    
    # Header
    today_date = h(today.date if today.date else "No date")
    html_parts.append(f"""
    <div class="header-banner">
        <div><strong>TriageCore Workspace Now</strong></div>
        <div>{today_date}</div>
    </div>
    <div style="margin-bottom: 20px;">
        Focus: {len(focus_items)} items &nbsp;|&nbsp; Warnings: {len(warnings)} &nbsp;|&nbsp; Blocked: {len(blocked_items)} &nbsp;|&nbsp; Review: {len(review_items)}
    </div>
    """)
    
    # Focus Grid
    html_parts.append('<div class="focus-grid">')
    for item in focus_items:
        html_parts.append(_render_focus_card(item))
    html_parts.append('</div>')
    
    # Warnings
    if warnings:
        html_parts.append('<div class="list-section"><h2>Warnings</h2><ul>')
        for w in warnings:
            html_parts.append(f'<li class="warning-li">⚠ {h(w)}</li>')
        html_parts.append('</ul></div>')
        
    # Blocked
    if blocked_items:
        html_parts.append('<div class="list-section"><h2>Blocked</h2><ul>')
        for item in blocked_items:
            blocker = h(item.kanban.blocked_by[0] if item.kanban.blocked_by else "Unknown")
            html_parts.append(f'<li class="blocked-li"><strong>{h(item.id)}</strong> — {h(item.project)} — Waiting on: {blocker}</li>')
        html_parts.append('</ul></div>')
        
    # Review
    if review_items:
        html_parts.append('<div class="list-section"><h2>Review</h2><ul>')
        for item in review_items:
            next_act = h(item.gtd.next_action if item.gtd else "")
            html_parts.append(f'<li><strong>{h(item.id)}</strong> — {h(item.project)} — {next_act}</li>')
        html_parts.append('</ul></div>')
        
    html_parts.append(f'<div style="margin-top: 50px; font-size: 0.8em; color: #666;">Generated at: {h(generated_at)}</div>')
    
    html_parts.append("</body></html>")
    
    return "\n".join(html_parts)
