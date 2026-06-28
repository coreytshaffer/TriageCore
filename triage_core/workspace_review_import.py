from triage_core.workspace_board import load_work_items

def render_import_review(preview_path: str, label: str = None, updated_since: str = None, limit: int = None) -> str:
    """Render a compact Markdown table of imported items from a preview YAML file."""
    
    items = load_work_items(preview_path)
    
    # Filter items
    filtered_items = []
    for item in items:
        # We only review GitHub external items
        if not item.external or item.external.source != "github" or not item.external.github:
            continue
            
        gh = item.external.github
        
        if label and label not in gh.labels:
            continue
            
        if updated_since and gh.updated_at:
            # We assume updated_since is something like "2026-06-01"
            # and gh.updated_at is ISO format e.g. "2026-06-27T10:00:00Z"
            # Simple lexicographical comparison works for ISO dates
            if gh.updated_at < updated_since:
                continue
                
        filtered_items.append(item)
        
    if limit is not None:
        filtered_items = filtered_items[:limit]
        
    # Generate table
    lines = [
        "GitHub Import Review",
        "====================",
        "",
        "| ID | Repo | Issue | Title | Labels | Updated | Suggested action |",
        "|---|---|---|---|---|---|---|"
    ]
    
    for item in filtered_items:
        gh = item.external.github
        
        # Determine suggested action
        if "tech-debt" in gh.labels:
            action = "clarify"
        elif "bug" in gh.labels or "enhancement" in gh.labels:
            action = "promote"
        else:
            action = "clarify"
            
        repo_clean = gh.repo
        issue_str = f"#{gh.issue_number}"
        
        # Make title safe for markdown table (escape pipes)
        title_safe = item.title.replace("|", "\\|")
        labels_str = ", ".join(gh.labels)
        
        # truncate date to YYYY-MM-DD
        updated_date = gh.updated_at[:10] if gh.updated_at else ""
        
        lines.append(f"| {item.id} | {repo_clean} | {issue_str} | {title_safe} | {labels_str} | {updated_date} | {action} |")
        
    return "\n".join(lines)
