import argparse
import os
import uuid
from .handoff import HandoffPacket
from .classifier import TaskClassifier, DangerDetector
from .task_ledger import TaskLedger

def main():
    parser = argparse.ArgumentParser(description="TriageCore: Local-first developer-agent control harness.")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # desk
    subparsers.add_parser("desk", help="Launch the TriageDesk TUI application.")

    # audit
    audit_parser = subparsers.add_parser("audit", help="Run a post-execution safety audit on a completed task.")
    audit_parser.add_argument("task_id", type=str, help="The ID of the task to audit.")
    audit_parser.add_argument("--files", type=str, nargs="+", required=True, help="The files modified by the agent.")

    # codex-task
    codex_parser = subparsers.add_parser("codex-task", help="Generate a markdown task packet for Codex.")
    codex_parser.add_argument("--prompt", type=str, required=True, help="The instruction for the agent.")
    codex_parser.add_argument("--files", type=str, nargs="+", default=[], help="Target files to modify.")

    # antigravity-task
    anti_parser = subparsers.add_parser("antigravity-task", help="Generate a task bundle for Antigravity.")
    anti_parser.add_argument("--prompt", type=str, required=True, help="The instruction for the agent.")
    anti_parser.add_argument("--files", type=str, nargs="+", default=[], help="Target files to modify.")
    anti_parser.add_argument("--slug", type=str, required=True, help="Task slug for the folder name.")

    # init-agents
    subparsers.add_parser("init-agents", help="Generate a default AGENTS.md helper file.")

    args = parser.parse_args()

    if args.command == "desk":
        from .ui.app import run_app
        run_app()
    elif args.command == "install-desktop":
        _install_desktop_shortcut()
    elif args.command == "audit":
        _audit_task(args.task_id, args.files)
    elif args.command == "codex-task":
        _generate_codex_task(args.prompt, args.files)
    elif args.command == "antigravity-task":
        _generate_antigravity_task(args.prompt, args.files, args.slug)
    elif args.command == "init-agents":
        _init_agents()
    else:
        parser.print_help()

def _audit_task(task_id: str, files: list[str]):
    from .task_ledger import TaskLedger
    from .validator import SafetyValidator
    
    ledger = TaskLedger()
    task = ledger.get_task(task_id)
    if not task:
        print(f"Error: Task {task_id} not found in ledger.")
        return
        
    result = SafetyValidator.audit(task, files)
    
    ledger.append_event(task_id, "task_audited", {
        "passed": result.passed,
        "violations": result.violations,
        "audited_files": files
    })
    
    if result.passed:
        print(f"Success: Task {task_id} passed safety audit.")
    else:
        print(f"FAIL: Task {task_id} violated safety constraints!")
        for v in result.violations:
            print(f" - {v}")
        # Return non-zero exit code for CI/CD integrations
        import sys
        sys.exit(1)

def _install_desktop_shortcut():
    try:
        from pyshortcuts import make_shortcut
    except ImportError:
        print("Error: pyshortcuts is not installed. Run `pip install triagecore[ui]`")
        return
        
    import sys
    current_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(current_dir, "ui", "icon.ico")
    
    script_path = os.path.join(os.path.dirname(sys.executable), "triagecore.exe")
    if not os.path.exists(script_path):
        # Fallback to python -m triage_core.cli desk if entrypoint not found
        script_path = f"{sys.executable} -m triage_core.cli desk"
    else:
        script_path = f"{script_path} desk"
        
    try:
        make_shortcut(script_path, name="TriageDesk", icon=icon_path, desktop=True, terminal=False)
        print(f"Success: Desktop shortcut created with icon: {icon_path}")
    except Exception as e:
        print(f"Failed to create desktop shortcut: {e}")

def _log_to_ledger(task_id: str, prompt: str, files: list[str], runner: str, artifact_path: str):
    ledger = TaskLedger()
    ledger.append_event(task_id, "task_created", {
        "title": f"Task: {prompt[:30]}...",
        "description": prompt,
        "target_files": files
    })
    
    cat = TaskClassifier.classify(prompt)
    danger = DangerDetector.analyze(prompt, files)
    
    ledger.append_event(task_id, "task_classified", {
        "category": cat,
        "risk_level": danger.risk_level,
        "recommended_profile": danger.recommended_profile,
        "reasons": danger.reasons
    })
    
    ledger.append_event(task_id, "runner_selected", {"runner": runner})
    ledger.append_event(task_id, "handoff_generated", {"artifact_path": artifact_path})

def _create_packet(prompt: str, files: list[str]) -> HandoffPacket:
    category = TaskClassifier.classify(prompt)
    danger_info = DangerDetector.analyze(prompt, files)
    
    packet = HandoffPacket(
        title=f"Task: {category.replace('_', ' ').title()}",
        summary=prompt,
        context="Auto-generated handoff from TriageCore.",
        target_files=files,
        constraints=["Do not escalate to cloud APIs.", "Follow local codebase styling."],
        acceptance_criteria=["Tests pass.", "No security regressions."],
        test_commands=["pytest tests/"],
        safety_notes=danger_info.reasons,
        recommended_backend="Local" if danger_info.risk_level == "low" else "Human-in-the-loop",
        recommended_permission_profile=danger_info.recommended_profile,
        risk_level=danger_info.risk_level
    )
    return packet

def _generate_codex_task(prompt: str, files: list[str]):
    packet = _create_packet(prompt, files)
    os.makedirs("triage_tasks", exist_ok=True)
    
    task_id = str(uuid.uuid4())
    filename = f"triage_tasks/codex_task_{task_id[:8]}.md"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(packet.to_markdown())
        
    _log_to_ledger(task_id, prompt, files, "codex", filename)
    print(f"Success: Generated Codex task packet at {filename}")

def _generate_antigravity_task(prompt: str, files: list[str], slug: str):
    packet = _create_packet(prompt, files)
    task_dir = f".agent_tasks/{slug}"
    os.makedirs(task_dir, exist_ok=True)
    
    task_id = str(uuid.uuid4())
    task_file = f"{task_dir}/TASK.md"
    
    with open(task_file, "w", encoding="utf-8") as f:
        f.write(packet.to_markdown())
        
    with open(f"{task_dir}/ACCEPTANCE_CRITERIA.md", "w", encoding="utf-8") as f:
        f.write("# Acceptance Criteria\n")
        for ac in packet.acceptance_criteria:
            f.write(f"- [ ] {ac}\n")
            
    _log_to_ledger(task_id, prompt, files, "antigravity", task_file)
    print(f"Success: Generated Antigravity task bundle at {task_dir}/")

def _init_agents():
    content = """# AGENTS.md

This repository uses local developer agents. 
- **Codex**: Use `triagecore codex-task` to queue jobs.
- **Antigravity**: Use `triagecore antigravity-task` to create task bundles.

All tasks are strictly bounded by safety profiles defined in TriageCore.
"""
    with open("AGENTS.md", "w", encoding="utf-8") as f:
        f.write(content)
    print("Success: Initialized AGENTS.md")

if __name__ == "__main__":
    main()
