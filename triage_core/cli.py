import argparse
import os
import json
from .handoff import HandoffPacket
from .classifier import TaskClassifier, DangerDetector

def main():
    parser = argparse.ArgumentParser(description="TriageCore: Local-first developer-agent control harness.")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

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

    if args.command == "codex-task":
        _generate_codex_task(args.prompt, args.files)
    elif args.command == "antigravity-task":
        _generate_antigravity_task(args.prompt, args.files, args.slug)
    elif args.command == "init-agents":
        _init_agents()
    else:
        parser.print_help()

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
        safety_notes=[danger_info["reasons"]],
        recommended_backend="Local" if danger_info["risk_level"] == "low" else "Human-in-the-loop",
        recommended_permission_profile=danger_info["recommended_profile"],
        risk_level=danger_info["risk_level"]
    )
    return packet

def _generate_codex_task(prompt: str, files: list[str]):
    packet = _create_packet(prompt, files)
    os.makedirs("triage_tasks", exist_ok=True)
    filename = f"triage_tasks/codex_task_{packet.risk_level}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(packet.to_markdown())
    print(f"✅ Generated Codex task packet at {filename}")

def _generate_antigravity_task(prompt: str, files: list[str], slug: str):
    packet = _create_packet(prompt, files)
    task_dir = f".agent_tasks/{slug}"
    os.makedirs(task_dir, exist_ok=True)
    
    with open(f"{task_dir}/TASK.md", "w", encoding="utf-8") as f:
        f.write(packet.to_markdown())
        
    with open(f"{task_dir}/ACCEPTANCE_CRITERIA.md", "w", encoding="utf-8") as f:
        f.write("# Acceptance Criteria\n")
        for ac in packet.acceptance_criteria:
            f.write(f"- [ ] {ac}\n")
            
    print(f"✅ Generated Antigravity task bundle at {task_dir}/")

def _init_agents():
    content = """# AGENTS.md

This repository uses local developer agents. 
- **Codex**: Use `triagecore codex-task` to queue jobs.
- **Antigravity**: Use `triagecore antigravity-task` to create task bundles.

All tasks are strictly bounded by safety profiles defined in TriageCore.
"""
    with open("AGENTS.md", "w", encoding="utf-8") as f:
        f.write(content)
    print("✅ Initialized AGENTS.md")

if __name__ == "__main__":
    main()
