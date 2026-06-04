import argparse
import os
import uuid
from typing import Optional
from .handoff import HandoffPacket
from .classifier import TaskClassifier, DangerDetector
from .config import default_config
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

    # install-desktop
    subparsers.add_parser("install-desktop", help="Create a desktop shortcut for TriageDesk.")

    # push-task
    push_parser = subparsers.add_parser("push-task", help="Push a task to an open TriageDesk instance via IPC.")
    push_parser.add_argument("--prompt", type=str, required=True, help="The instruction to inject into the UI.")
    push_parser.add_argument("--files", type=str, nargs="*", default=[], help="Target files to populate.")
    push_parser.add_argument("--auto-dispatch", type=str, choices=["local", "council", "codex", "antigravity"], help="Optional runner to auto-trigger.")

    # benchmark
    benchmark_parser = subparsers.add_parser("benchmark", help="Run or list model evaluation benchmark tasks.")
    benchmark_parser.add_argument("--tasks", type=str, default=default_config.get_benchmarks_path(), help="Path to benchmark JSONL tasks.")
    benchmark_parser.add_argument("--backend-type", type=str, default=default_config.get_backend_type(), help="Backend preset to use.")
    benchmark_parser.add_argument("--model", type=str, default=default_config.get_backend_model(), help="Model name for the backend.")
    benchmark_parser.add_argument("--base-url", type=str, default=default_config.get_backend_base_url(), help="Optional custom OpenAI-compatible base URL.")
    benchmark_parser.add_argument("--timeout", type=int, default=default_config.get_timeout_seconds(), help="Local timeout budget in seconds.")
    benchmark_parser.add_argument("--limit", type=int, default=None, help="Optional number of benchmark tasks to run.")
    benchmark_parser.add_argument("--ledger-dir", type=str, default=default_config.get_ledger_dir(), help="Directory for the benchmark ledger.")
    benchmark_parser.add_argument("--study-id", type=str, default=None, help="Optional study identifier to tag benchmark evidence.")
    benchmark_parser.add_argument("--list-only", action="store_true", help="List benchmark tasks without running a backend.")

    # benchmark-report
    report_parser = subparsers.add_parser("benchmark-report", help="Summarize benchmark evidence from the ledger.")
    report_parser.add_argument("--ledger-dir", type=str, default=default_config.get_ledger_dir(), help="Directory containing ledger.jsonl.")
    report_parser.add_argument("--output", type=str, default=None, help="Optional markdown output path.")
    report_parser.add_argument("--study-id", type=str, default=None, help="Optional study identifier used to filter benchmark evidence.")

    # propose-lessons
    lessons_parser = subparsers.add_parser("propose-lessons", help="Generate pending learning proposals from ledger evidence.")
    lessons_parser.add_argument("--ledger-dir", type=str, default=default_config.get_ledger_dir(), help="Directory containing ledger.jsonl.")
    lessons_parser.add_argument("--output", type=str, default=os.path.join(default_config.get_ledger_dir(), "learning_proposals.jsonl"), help="JSONL output path for pending proposals.")
    lessons_parser.add_argument("--min-evidence", type=int, default=1, help="Minimum evidence records required for a proposal.")
    lessons_parser.add_argument("--study-id", type=str, default=None, help="Optional study identifier used to filter learning proposal evidence.")

    # review-lesson
    review_parser = subparsers.add_parser("review-lesson", help="Record a human review decision for a learning proposal.")
    review_parser.add_argument("proposal_id", type=str, help="Learning proposal ID to review.")
    review_parser.add_argument("--decision", type=str, choices=["accepted", "rejected"], required=True, help="Human review decision.")
    review_parser.add_argument("--notes", type=str, default="", help="Optional reviewer notes.")
    review_parser.add_argument("--output", type=str, default=os.path.join(default_config.get_ledger_dir(), "learning_reviews.jsonl"), help="JSONL output path for review records.")

    args = parser.parse_args()

    if args.command == "desk":
        from .ui.app import run_app
        run_app()
    elif args.command == "install-desktop":
        _install_desktop_shortcut()
    elif args.command == "push-task":
        _push_task_to_ui(args.prompt, args.files, args.auto_dispatch)
    elif args.command == "audit":
        _audit_task(args.task_id, args.files)
    elif args.command == "codex-task":
        _generate_codex_task(args.prompt, args.files)
    elif args.command == "antigravity-task":
        _generate_antigravity_task(args.prompt, args.files, args.slug)
    elif args.command == "init-agents":
        _init_agents()
    elif args.command == "benchmark":
        _run_benchmarks(
            tasks_path=args.tasks,
            backend_type=args.backend_type,
            model=args.model,
            base_url=args.base_url,
            timeout_seconds=args.timeout,
            limit=args.limit,
            ledger_dir=args.ledger_dir,
            study_id=args.study_id,
            list_only=args.list_only,
        )
    elif args.command == "benchmark-report":
        _benchmark_report(
            ledger_dir=args.ledger_dir,
            output_path=args.output,
            study_id=args.study_id,
        )
    elif args.command == "propose-lessons":
        _propose_lessons(
            ledger_dir=args.ledger_dir,
            output_path=args.output,
            min_evidence=args.min_evidence,
            study_id=args.study_id,
        )
    elif args.command == "review-lesson":
        _review_lesson(
            proposal_id=args.proposal_id,
            decision=args.decision,
            notes=args.notes,
            output_path=args.output,
        )
    else:
        parser.print_help()

def _push_task_to_ui(prompt: str, files: list[str], auto_dispatch: Optional[str] = None):
    import json
    ledger_dir = default_config.get_ledger_dir()
    os.makedirs(ledger_dir, exist_ok=True)
    inbox_path = os.path.join(ledger_dir, "ipc_inbox.json")
    
    payload = {
        "prompt": prompt,
        "files": files,
        "auto_dispatch": auto_dispatch
    }
    with open(inbox_path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    print(f"Success: Task pushed to {inbox_path}.")
    print("If TriageDesk is running, it will automatically import it within 1 second.")

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
    codex_tasks_dir = default_config.get_codex_tasks_dir()
    os.makedirs(codex_tasks_dir, exist_ok=True)
    
    task_id = str(uuid.uuid4())
    filename = os.path.join(codex_tasks_dir, f"codex_task_{task_id[:8]}.md")
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(packet.to_markdown())
        
    _log_to_ledger(task_id, prompt, files, "codex", filename)
    print(f"Success: Generated Codex task packet at {filename}")

def _generate_antigravity_task(prompt: str, files: list[str], slug: str):
    packet = _create_packet(prompt, files)
    task_dir = os.path.join(default_config.get_tasks_dir(), slug)
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

def _run_benchmarks(
    tasks_path: str,
    backend_type: str,
    model: str,
    base_url: Optional[str],
    timeout_seconds: int,
    limit: Optional[int],
    ledger_dir: str,
    study_id: Optional[str],
    list_only: bool,
):
    from .benchmarks import load_benchmark_tasks, resolve_validator, result_to_model_event
    from .client import TriageClient

    tasks = load_benchmark_tasks(tasks_path)
    if limit is not None:
        tasks = tasks[:limit]

    if list_only:
        for task in tasks:
            print(f"{task.task_id} | {task.category} | expected={task.expected_status}")
        return

    client = TriageClient(
        backend_type=backend_type,
        model=model,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )
    ledger = TaskLedger(ledger_dir=ledger_dir)

    for task in tasks:
        task_id = str(uuid.uuid4())
        print(f"Running benchmark: {task.task_id}")

        ledger.append_event(task_id, "task_created", {
            "title": f"Benchmark: {task.task_id}",
            "description": task.prompt,
            "target_files": task.target_files,
            "benchmark_task_id": task.task_id,
            "study_id": study_id,
        })
        ledger.append_event(task_id, "runner_selected", {"runner": "local_benchmark"})

        result = client.run_task(
            prompt=task.prompt,
            data=task.data,
            validator=resolve_validator(task.validator),
        )

        ledger.append_event(task_id, "model_evaluated", result_to_model_event(task, result))
        if result.get("status") == "handoff_required":
            ledger.append_event(task_id, "handoff_generated", {
                "reason": result.get("handoff_reason") or result.get("reason"),
            })

        print(f"  observed={result.get('status')} expected={task.expected_status}")

def _benchmark_report(ledger_dir: str, output_path: Optional[str], study_id: Optional[str]):
    from .reports import build_benchmark_report, render_benchmark_report_markdown

    ledger = TaskLedger(ledger_dir=ledger_dir)
    report = build_benchmark_report(ledger.get_all_tasks(), study_id=study_id)
    markdown = render_benchmark_report_markdown(report)

    if output_path:
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown + "\n")
        print(f"Benchmark report written to {output_path}")
    else:
        print(markdown)

def _propose_lessons(ledger_dir: str, output_path: str, min_evidence: int, study_id: Optional[str]):
    from .learning import append_learning_proposals, build_learning_proposals

    ledger = TaskLedger(ledger_dir=ledger_dir)
    records = ledger.get_all_tasks()
    if study_id:
        records = [record for record in records if record.study_id == study_id]
    proposals = build_learning_proposals(records, min_evidence=min_evidence)
    new_proposals = append_learning_proposals(output_path, proposals)

    if not proposals:
        print("No learning proposals found from current ledger evidence.")
        return

    print(f"Generated {len(new_proposals)} new proposal(s); {len(proposals)} total candidate(s).")
    for proposal in new_proposals:
        print(f"{proposal.proposal_id} | {proposal.trigger} | evidence={len(proposal.evidence_task_ids)}")

def _review_lesson(proposal_id: str, decision: str, notes: str, output_path: str):
    from .learning import append_learning_review

    review = append_learning_review(
        path=output_path,
        proposal_id=proposal_id,
        decision=decision,
        notes=notes,
    )
    print(f"Recorded {review['decision']} review for proposal {review['proposal_id']}.")

if __name__ == "__main__":
    main()
