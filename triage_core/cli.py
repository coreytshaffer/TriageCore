import argparse
import os
import uuid
from datetime import datetime, timezone
from typing import Optional
from .handoff import HandoffPacket
from .classifier import TaskClassifier, DangerDetector
from .config import default_config
from .task_ledger import TaskLedger


def _log_cli_activity(message: str, ledger_dir: Optional[str] = None) -> str:
    log_dir = ledger_dir or default_config.get_ledger_dir()
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "triagecore.log")
    timestamp = datetime.now(timezone.utc).isoformat()
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"{timestamp} [cli] {message}\n")
    except OSError as exc:
        print(f"Warning: could not write CLI activity log: {exc}")
    return log_path


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
    push_parser.add_argument("--auto-dispatch", type=str, choices=["local", "council", "codex", "antigravity", "pipeline"], help="Optional runner to auto-trigger.")

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
    benchmark_parser.add_argument("--run-id", type=str, default=None, help="Optional run identifier to tag a specific benchmark trial.")
    benchmark_parser.add_argument("--list-only", action="store_true", help="List benchmark tasks without running a backend.")

    # benchmark-report
    report_parser = subparsers.add_parser("benchmark-report", help="Summarize benchmark evidence from the ledger.")
    report_parser.add_argument("--ledger-dir", type=str, default=default_config.get_ledger_dir(), help="Directory containing ledger.jsonl.")
    report_parser.add_argument("--output", type=str, default=None, help="Optional markdown output path.")
    report_parser.add_argument("--study-id", type=str, default=None, help="Optional study identifier used to filter benchmark evidence.")
    report_parser.add_argument("--run-id", type=str, default=None, help="Optional run identifier used to filter benchmark evidence.")

    # propose-lessons
    lessons_parser = subparsers.add_parser("propose-lessons", help="Generate pending learning proposals from ledger evidence.")
    lessons_parser.add_argument("--ledger-dir", type=str, default=default_config.get_ledger_dir(), help="Directory containing ledger.jsonl.")
    lessons_parser.add_argument("--output", type=str, default=os.path.join(default_config.get_ledger_dir(), "learning_proposals.jsonl"), help="JSONL output path for pending proposals.")
    lessons_parser.add_argument("--min-evidence", type=int, default=1, help="Minimum evidence records required for a proposal.")
    lessons_parser.add_argument("--study-id", type=str, default=None, help="Optional study identifier used to filter learning proposal evidence.")
    lessons_parser.add_argument("--run-id", type=str, default=None, help="Optional run identifier used to filter learning proposal evidence.")

    # review-lesson
    review_parser = subparsers.add_parser("review-lesson", help="Record a human review decision for a learning proposal.")
    review_parser.add_argument("proposal_id", type=str, help="Learning proposal ID to review.")
    review_parser.add_argument("--decision", type=str, choices=["accepted", "rejected"], required=True, help="Human review decision.")
    review_parser.add_argument("--notes", type=str, default="", help="Optional reviewer notes.")
    review_parser.add_argument("--output", type=str, default=os.path.join(default_config.get_ledger_dir(), "learning_reviews.jsonl"), help="JSONL output path for review records.")

    # import-learning-seeds
    seed_parser = subparsers.add_parser(
        "import-learning-seeds",
        help="Validate or import source-project learning seed JSONL records.",
    )
    seed_parser.add_argument("--source-dir", type=str, default=os.path.join("docs", "learning", "examples"), help="Directory containing learning seed JSONL files.")
    seed_parser.add_argument("--ledger-dir", type=str, default=default_config.get_ledger_dir(), help="Directory where validated learning seed records should be stored.")
    seed_parser.add_argument("--write", action="store_true", help="Write validated records. Default is validation-only dry run.")

    # record-supervisor-review
    supervisor_parser = subparsers.add_parser(
        "record-supervisor-review",
        help="Record a Codex, Antigravity, Gemini, or human supervisor review for a task.",
    )
    supervisor_parser.add_argument("task_id", type=str, help="Task ID from the ledger.")
    supervisor_parser.add_argument("--tool", type=str, required=True, help="Supervisor tool, such as codex, antigravity, gemini, or human.")
    supervisor_parser.add_argument("--decision", type=str, choices=["accepted", "rejected", "needs_revision", "escalated"], required=True, help="Supervisor review decision.")
    supervisor_parser.add_argument("--notes", type=str, default="", help="Supervisor notes or review rationale.")
    supervisor_parser.add_argument("--model", type=str, default="", help="Supervisor model, if known.")
    supervisor_parser.add_argument("--profile", type=str, default="", help="Supervisor profile or mode, if known.")
    supervisor_parser.add_argument("--artifact-path", type=str, default="", help="Review packet, transcript, or output artifact path.")
    supervisor_parser.add_argument("--input-tokens-est", type=int, default=0, help="Estimated supervisor input tokens, if known.")
    supervisor_parser.add_argument("--output-tokens-est", type=int, default=0, help="Estimated supervisor output tokens, if known.")
    supervisor_parser.add_argument("--token-source", type=str, choices=["manual_estimate", "imported_estimate", "imported_exact"], default="manual_estimate", help="Source label for supervisor token values.")
    supervisor_parser.add_argument("--ledger-dir", type=str, default=default_config.get_ledger_dir(), help="Directory containing ledger.jsonl.")

    # import-supervisor-usage
    usage_parser = subparsers.add_parser(
        "import-supervisor-usage",
        help="Import supervisor token usage from a JSON or JSONL artifact.",
    )
    usage_parser.add_argument("source", type=str, help="JSON or JSONL file containing supervisor usage records.")
    usage_parser.add_argument("--tool", type=str, default="", help="Default supervisor tool when records omit one.")
    usage_parser.add_argument("--decision", type=str, choices=["accepted", "rejected", "needs_revision", "escalated"], default="accepted", help="Default supervisor decision when records omit one.")
    usage_parser.add_argument("--notes", type=str, default="", help="Default notes when records omit them.")
    usage_parser.add_argument("--model", type=str, default="", help="Default supervisor model when records omit one.")
    usage_parser.add_argument("--profile", type=str, default="", help="Default supervisor profile when records omit one.")
    usage_parser.add_argument("--artifact-path", type=str, default="", help="Default artifact path when records omit one.")
    usage_parser.add_argument("--token-source", type=str, choices=["imported_estimate", "imported_exact"], default="imported_estimate", help="Whether imported token values are estimates or verified exact usage.")
    usage_parser.add_argument("--ledger-dir", type=str, default=default_config.get_ledger_dir(), help="Directory containing ledger.jsonl.")
    usage_parser.add_argument("--dry-run", action="store_true", help="Preview importable records without writing ledger events.")

    # scan-supervisor-usage
    scan_usage_parser = subparsers.add_parser(
        "scan-supervisor-usage",
        help="Scan files or directories for importable supervisor usage JSON/JSONL artifacts.",
    )
    scan_usage_parser.add_argument("paths", type=str, nargs="+", help="Files or directories to scan.")
    scan_usage_parser.add_argument("--tool", type=str, default="", help="Default supervisor tool when candidate records omit one.")
    scan_usage_parser.add_argument("--token-source", type=str, choices=["imported_estimate", "imported_exact"], default="imported_estimate", help="Token source label used while parsing candidates.")
    scan_usage_parser.add_argument("--max-file-bytes", type=int, default=1_000_000, help="Maximum JSON/JSONL file size to inspect.")

    # run-pipeline
    pipeline_parser = subparsers.add_parser("run-pipeline", help="Run the local pipeline headlessly and output tokens.")
    pipeline_parser.add_argument("--prompt", type=str, required=True, help="Task instructions.")
    pipeline_parser.add_argument("--files", type=str, nargs="*", default=[], help="Target files.")
    pipeline_parser.add_argument("--output", type=str, required=True, help="Where to save the output artifact.")
    pipeline_parser.add_argument("--ledger-dir", type=str, default=default_config.get_ledger_dir(), help="Directory for pipeline ledger evidence.")
    pipeline_parser.add_argument("--task-id", type=str, default=None, help="Optional existing task ID to append pipeline evidence to.")

    # stability-pass
    stability_parser = subparsers.add_parser(
        "stability-pass",
        help="Run a post-sprint Codex stability pass to verify boundary, logging, and regression correctness.",
    )
    stability_parser.add_argument("--tasks", type=str, default=default_config.get_benchmarks_path(), help="Path to benchmark JSONL tasks.")
    stability_parser.add_argument("--backend-type", type=str, default=default_config.get_backend_type(), help="Backend preset to use.")
    stability_parser.add_argument("--model", type=str, default=default_config.get_backend_model(), help="Model name for the backend.")
    stability_parser.add_argument("--base-url", type=str, default=default_config.get_backend_base_url(), help="Optional custom OpenAI-compatible base URL.")
    stability_parser.add_argument("--timeout", type=int, default=default_config.get_timeout_seconds(), help="Local timeout budget in seconds.")
    stability_parser.add_argument("--ledger-dir", type=str, default=default_config.get_ledger_dir(), help="Directory for the task ledger and activity logging.")
    stability_parser.add_argument("--study-id", type=str, default="stability_pass", help="Study identifier to tag stability pass benchmark evidence.")
    stability_parser.add_argument("--run-id", type=str, default=None, help="Optional run identifier to tag a specific trial.")

    # stats
    stats_parser = subparsers.add_parser("stats", help="Alias for 'lab report' - calculate primary scientific metrics.")
    stats_parser.add_argument("--ledger-dir", type=str, default=default_config.get_ledger_dir(), help="Directory containing ledger.jsonl.")

    # lab
    lab_parser = subparsers.add_parser("lab", help="TriageLab analytical engine subcommands.")
    lab_subparsers = lab_parser.add_subparsers(dest="lab_command", help="Lab subcommands")

    lab_report_parser = lab_subparsers.add_parser("report", help="Calculate primary scientific metrics over historical runs.")
    lab_report_parser.add_argument("--ledger-dir", type=str, default=default_config.get_ledger_dir(), help="Directory containing ledger.jsonl.")

    lab_export_parser = lab_subparsers.add_parser("export", help="Export historical ledger runs to flat tabular dataset.")
    lab_export_parser.add_argument("--output", type=str, default=None, help="Output CSV path. Defaults to .triagecore/lab_export.csv.")
    lab_export_parser.add_argument("--ledger-dir", type=str, default=default_config.get_ledger_dir(), help="Directory containing ledger.jsonl.")

    lab_train_parser = lab_subparsers.add_parser("train", help="Train a predictive success model on historical ledger runs.")
    lab_train_parser.add_argument("--ledger-dir", type=str, default=default_config.get_ledger_dir(), help="Directory containing ledger.jsonl.")

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
            run_id=args.run_id,
            list_only=args.list_only,
        )
    elif args.command == "benchmark-report":
        _benchmark_report(
            ledger_dir=args.ledger_dir,
            output_path=args.output,
            study_id=args.study_id,
            run_id=args.run_id,
        )
    elif args.command == "propose-lessons":
        _propose_lessons(
            ledger_dir=args.ledger_dir,
            output_path=args.output,
            min_evidence=args.min_evidence,
            study_id=args.study_id,
            run_id=args.run_id,
        )
    elif args.command == "review-lesson":
        _review_lesson(
            proposal_id=args.proposal_id,
            decision=args.decision,
            notes=args.notes,
            output_path=args.output,
        )
    elif args.command == "import-learning-seeds":
        _import_learning_seeds(
            source_dir=args.source_dir,
            ledger_dir=args.ledger_dir,
            write=args.write,
        )
    elif args.command == "record-supervisor-review":
        _record_supervisor_review(
            task_id=args.task_id,
            tool=args.tool,
            decision=args.decision,
            notes=args.notes,
            model=args.model,
            profile=args.profile,
            artifact_path=args.artifact_path,
            input_tokens_est=args.input_tokens_est,
            output_tokens_est=args.output_tokens_est,
            token_source=args.token_source,
            ledger_dir=args.ledger_dir,
        )
    elif args.command == "import-supervisor-usage":
        _import_supervisor_usage(
            source_path=args.source,
            tool=args.tool,
            decision=args.decision,
            notes=args.notes,
            model=args.model,
            profile=args.profile,
            artifact_path=args.artifact_path,
            token_source=args.token_source,
            ledger_dir=args.ledger_dir,
            dry_run=args.dry_run,
        )
    elif args.command == "scan-supervisor-usage":
        _scan_supervisor_usage(
            paths=args.paths,
            tool=args.tool,
            token_source=args.token_source,
            max_file_bytes=args.max_file_bytes,
        )
    elif args.command == "run-pipeline":
        _run_pipeline(args.prompt, args.files, args.output, args.ledger_dir, args.task_id)
    elif args.command == "stability-pass":
        _run_stability_pass(
            tasks_path=args.tasks,
            backend_type=args.backend_type,
            model=args.model,
            base_url=args.base_url,
            timeout_seconds=args.timeout,
            ledger_dir=args.ledger_dir,
            study_id=args.study_id,
            run_id=args.run_id,
        )
    elif args.command == "stats":
        _lab_report(ledger_dir=args.ledger_dir)
    elif args.command == "lab":
        if args.lab_command == "report":
            _lab_report(ledger_dir=args.ledger_dir)
        elif args.lab_command == "export":
            _lab_export(ledger_dir=args.ledger_dir, output_path=args.output)
        elif args.lab_command == "train":
            _lab_train(ledger_dir=args.ledger_dir)
        else:
            lab_parser.print_help()
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
    _log_cli_activity(f"push-task queued auto_dispatch={auto_dispatch or 'none'}", ledger_dir=ledger_dir)
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
    _append_context_pack_event(
        ledger=ledger,
        task_id=task_id,
        prompt=prompt,
        files=files,
        runner=runner,
        category=cat,
        ledger_dir=default_config.get_ledger_dir(),
    )
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
    _log_cli_activity(f"codex-task generated task={task_id[:8]} path={filename}")
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
    _log_cli_activity(f"antigravity-task generated task={task_id[:8]} path={task_file}")
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
    run_id: Optional[str],
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
    _log_cli_activity(
        f"benchmark started backend={backend_type} model={model} study={study_id or 'none'} run={run_id or 'none'}",
        ledger_dir=ledger_dir,
    )

    for task in tasks:
        task_id = str(uuid.uuid4())
        print(f"Running benchmark: {task.task_id}")

        ledger.append_event(task_id, "task_created", {
            "title": f"Benchmark: {task.task_id}",
            "description": task.prompt,
            "target_files": task.target_files,
            "benchmark_task_id": task.task_id,
            "study_id": study_id,
            "run_id": run_id,
        })
        ledger.append_event(task_id, "runner_selected", {"runner": "local_benchmark"})
        _append_context_pack_event(
            ledger=ledger,
            task_id=task_id,
            prompt=f"{task.prompt}\n\nData:\n{task.data}",
            files=task.target_files,
            runner="local_benchmark",
            category=task.category,
            ledger_dir=ledger_dir,
        )

        result = client.run_task(
            prompt=task.prompt,
            data=task.data,
            validator=resolve_validator(task.validator),
        )

        observed = result.get("status")
        expected = task.expected_status
        passed = (observed == expected)
        wasted = 0 if passed else result.get("total_tokens", 0)

        event_payload = result_to_model_event(task, result)
        event_payload["wasted_tokens"] = wasted

        ledger.append_event(task_id, "model_evaluated", event_payload)
        if result.get("status") == "handoff_required":
            ledger.append_event(task_id, "handoff_generated", {
                "reason": result.get("handoff_reason") or result.get("reason"),
                "wasted_tokens": wasted,
            })

        print(f"  observed={result.get('status')} expected={task.expected_status}")
        _log_cli_activity(
            f"benchmark task={task.task_id} observed={result.get('status')} expected={task.expected_status}",
            ledger_dir=ledger_dir,
        )

def _benchmark_report(
    ledger_dir: str,
    output_path: Optional[str],
    study_id: Optional[str],
    run_id: Optional[str],
):
    from .reports import build_benchmark_report, render_benchmark_report_markdown

    ledger = TaskLedger(ledger_dir=ledger_dir)
    report = build_benchmark_report(ledger.get_all_tasks(), study_id=study_id, run_id=run_id)
    markdown = render_benchmark_report_markdown(report)

    if output_path:
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(markdown + "\n")
        _log_cli_activity(
            f"benchmark-report written study={study_id or 'all'} run={run_id or 'all'} path={output_path}",
            ledger_dir=ledger_dir,
        )
        print(f"Benchmark report written to {output_path}")
    else:
        _log_cli_activity(
            f"benchmark-report printed study={study_id or 'all'} run={run_id or 'all'}",
            ledger_dir=ledger_dir,
        )
        print(markdown)

def _propose_lessons(
    ledger_dir: str,
    output_path: str,
    min_evidence: int,
    study_id: Optional[str],
    run_id: Optional[str],
):
    from .learning import append_learning_proposals, build_learning_proposals

    ledger = TaskLedger(ledger_dir=ledger_dir)
    records = ledger.get_all_tasks()
    if study_id:
        records = [record for record in records if record.study_id == study_id]
    if run_id:
        records = [record for record in records if record.run_id == run_id]
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

def _import_learning_seeds(source_dir: str, ledger_dir: str, write: bool = False) -> int:
    from .learning import import_learning_seed_records

    result = import_learning_seed_records(
        source_dir=source_dir,
        ledger_dir=ledger_dir,
        dry_run=not write,
    )
    if result.errors:
        print("Learning seed import failed validation:")
        for error in result.errors:
            print(f"- {error}")
        _log_cli_activity(
            f"learning seed import failed errors={len(result.errors)} source={source_dir}",
            ledger_dir=ledger_dir,
        )
        return 0

    verb = "Would import" if result.dry_run else "Imported"
    print(
        f"{verb} {result.preflight_count} preflight(s), "
        f"{result.context_pack_count} context pack(s), "
        f"and {result.outcome_count} outcome(s)."
    )
    if result.dry_run:
        print("Dry run only. Re-run with --write to store validated seed records.")
    else:
        print(
            "New records written: "
            f"{result.preflight_imported} preflight(s), "
            f"{result.context_pack_imported} context pack(s), "
            f"{result.outcome_imported} outcome(s)."
        )
        for label, path in result.output_paths.items():
            print(f"{label}: {path}")

    _log_cli_activity(
        "learning seed import "
        f"dry_run={result.dry_run} total={result.total_count} imported={result.total_imported} "
        f"source={source_dir}",
        ledger_dir=ledger_dir,
    )
    return result.total_count

def _record_supervisor_review(
    task_id: str,
    tool: str,
    decision: str,
    notes: str,
    model: str,
    profile: str,
    artifact_path: str,
    input_tokens_est: int,
    output_tokens_est: int,
    token_source: str,
    ledger_dir: str,
) -> None:
    ledger = TaskLedger(ledger_dir=ledger_dir)
    task = ledger.get_task(task_id)
    if not task:
        print(f"Error: Task {task_id} not found in ledger.")
        return

    ledger.append_event(
        task_id,
        "supervisor_reviewed",
        {
            "supervisor_tool": tool,
            "supervisor_model": model,
            "supervisor_profile": profile,
            "supervisor_decision": decision,
            "supervisor_notes": notes,
            "supervisor_artifact_path": artifact_path,
            "supervisor_input_tokens_est": input_tokens_est,
            "supervisor_output_tokens_est": output_tokens_est,
            "supervisor_token_source": token_source,
        },
    )
    _log_cli_activity(
        f"supervisor review recorded task={task_id[:8]} tool={tool} model={model} profile={profile} decision={decision}",
        ledger_dir=ledger_dir,
    )
    print(f"Recorded {tool} ({model}) supervisor review for task {task_id}: {decision}.")

def _import_supervisor_usage(
    source_path: str,
    tool: str,
    decision: str,
    notes: str,
    model: str,
    profile: str,
    artifact_path: str,
    token_source: str,
    ledger_dir: str,
    dry_run: bool = False,
) -> int:
    from .supervisor_usage import load_supervisor_usage_records

    ledger = TaskLedger(ledger_dir=ledger_dir)
    records = load_supervisor_usage_records(
        source_path,
        default_tool=tool,
        default_decision=decision,
        default_model=model,
        default_profile=profile,
        default_notes=notes,
        default_artifact_path=artifact_path,
        token_source=token_source,
    )
    imported = 0
    skipped = 0

    for record in records:
        if not ledger.get_task(record.task_id):
            print(f"Skipped {record.task_id}: task not found in ledger.")
            skipped += 1
            continue
        if dry_run:
            print(
                "Would import "
                f"{record.task_id}: {record.tool or tool or 'unknown-tool'} "
                f"{record.decision} "
                f"{record.input_tokens} in/{record.output_tokens} out "
                f"({record.token_source})"
            )
            imported += 1
            continue
        ledger.append_event(
            record.task_id,
            "supervisor_reviewed",
            {
                "supervisor_tool": record.tool,
                "supervisor_model": record.model,
                "supervisor_profile": record.profile,
                "supervisor_decision": record.decision,
                "supervisor_notes": record.notes,
                "supervisor_artifact_path": record.artifact_path,
                "supervisor_input_tokens_est": record.input_tokens,
                "supervisor_output_tokens_est": record.output_tokens,
                "supervisor_token_source": record.token_source,
            },
        )
        imported += 1

    verb = "Would import" if dry_run else "Imported"
    _log_cli_activity(
        f"supervisor usage import dry_run={dry_run} imported={imported} skipped={skipped} source={source_path} tool={tool} model={model}",
        ledger_dir=ledger_dir,
    )
    print(f"{verb} {imported} supervisor usage record(s) for {tool} ({model}); skipped {skipped}.")
    return imported

def _scan_supervisor_usage(
    paths: list[str],
    tool: str,
    token_source: str,
    max_file_bytes: int,
) -> int:
    from .supervisor_usage import scan_supervisor_usage_paths

    candidates = scan_supervisor_usage_paths(
        paths,
        default_tool=tool,
        token_source=token_source,
        max_file_bytes=max_file_bytes,
    )
    if not candidates:
        _log_cli_activity(
            f"supervisor usage scan candidates=0 paths={len(paths)}",
        )
        print("No importable supervisor usage artifacts found.")
        return 0

    print("Importable supervisor usage artifacts:")
    for candidate in candidates:
        print(
            f"{candidate.records} record(s) | "
            f"{candidate.total_input_tokens} in/{candidate.total_output_tokens} out | "
            f"{candidate.path}"
        )
    _log_cli_activity(
        f"supervisor usage scan candidates={len(candidates)} paths={len(paths)}",
    )
    return len(candidates)

def _start_pipeline_task(
    ledger: TaskLedger,
    prompt: str,
    files: list[str],
    task_id: Optional[str] = None,
) -> str:
    pipeline_task_id = task_id or str(uuid.uuid4())
    if not task_id or not ledger.get_task(task_id):
        ledger.append_event(
            pipeline_task_id,
            "task_created",
            {
                "title": f"Pipeline: {prompt[:40]}",
                "description": prompt,
                "target_files": files,
            },
        )
    ledger.append_event(pipeline_task_id, "runner_selected", {"runner": "pipeline"})
    _append_context_pack_event(
        ledger=ledger,
        task_id=pipeline_task_id,
        prompt=prompt,
        files=files,
        runner="pipeline",
        category=None,
        ledger_dir=ledger.ledger_dir,
    )
    return pipeline_task_id


def _append_context_pack_event(
    ledger: TaskLedger,
    task_id: str,
    prompt: str,
    files: list[str],
    runner: str,
    category: Optional[str],
    ledger_dir: str,
) -> Optional[str]:
    from .context_budget import create_context_pack_artifact

    pack, artifact_path, payload = create_context_pack_artifact(
        task_id=task_id,
        prompt=prompt,
        files=files,
        runner=runner,
        category=category,
        ledger_dir=ledger_dir,
    )
    ledger.append_event(task_id, "context_budgeted", payload)
    if pack.budget_status == "over_budget":
        print(
            "Context budget warning: "
            f"{pack.estimated_tokens}/{pack.budget_tokens} tokens estimated."
        )
    return artifact_path


def _record_pipeline_success(
    ledger: TaskLedger,
    task_id: str,
    backend_type: str,
    model: str,
    output_path: str,
    elapsed_seconds: float,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
) -> None:
    ledger.append_event(
        task_id,
        "local_draft_generated",
        {
            "status": "success",
            "duration_seconds": elapsed_seconds,
            "backend": backend_type,
            "backend_name": backend_type,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "energy_estimated": total_tokens * 0.005,
            "artifact_path": output_path,
            "wasted_tokens": 0,
        },
    )


def _record_pipeline_handoff(
    ledger: TaskLedger,
    task_id: str,
    reason: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
) -> None:
    ledger.append_event(
        task_id,
        "task_blocked",
        {
            "reason": reason,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "wasted_tokens": total_tokens,
        },
    )


def _run_pipeline(
    prompt: str,
    files: list[str],
    output_path: str,
    ledger_dir: str,
    task_id: Optional[str] = None,
) -> None:
    import time
    import os
    from .engine import TriageEngine
    from .backends import create_backend
    from .config import default_config

    backend_type = default_config.get_backend_type()
    model = default_config.get_backend_model()
    base_url = default_config.get_backend_base_url()
    ledger = TaskLedger(ledger_dir=ledger_dir)
    task_id = _start_pipeline_task(ledger, prompt, files, task_id)
    _log_cli_activity(
        f"pipeline started task={task_id[:8]} backend={backend_type} model={model}",
        ledger_dir=ledger_dir,
    )
    
    print(f"Running pipeline headless using {backend_type} ({model})...")
    print(f"Ledger task: {task_id}")
    
    backend = create_backend(
        backend_type=backend_type,
        model=model,
        base_url=base_url
    )
    
    engine = TriageEngine(backend=backend, timeout_seconds=120)
    
    raw_data = ""
    for f in files:
        if os.path.exists(f):
            with open(f, "r", encoding="utf-8") as f_in:
                raw_data += f"\n--- {f} ---\n{f_in.read()}"
    
    print("Executing task on local model...")
    t0 = time.time()
    
    # Simple stream callback for progress
    def _stream(chunk):
        print(".", end="", flush=True)
        
    result = engine.execute_task(
        task_prompt=prompt,
        raw_data=raw_data,
        stream_callback=_stream
    )
    
    print()
    elapsed = time.time() - t0
    
    if result.get("status") == "success":
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result["output"])
        
        in_tokens = result.get("input_tokens", 0)
        out_tokens = result.get("output_tokens", 0)
        total = result.get("total_tokens", 0)
        
        # Calculate cloud cost vs local cost
        # GPT-4o pricing approx: $5.00/1M input, $15.00/1M output
        cloud_cost = (in_tokens / 1000000.0) * 5.00 + (out_tokens / 1000000.0) * 15.00
        _record_pipeline_success(
            ledger=ledger,
            task_id=task_id,
            backend_type=backend_type,
            model=model,
            output_path=output_path,
            elapsed_seconds=elapsed,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            total_tokens=total,
        )
        _log_cli_activity(
            f"pipeline completed task={task_id[:8]} tokens={total} output={output_path}",
            ledger_dir=ledger_dir,
        )
        
        print(f"\n--- Pipeline Summary ---")
        print(f"Status: SUCCESS")
        print(f"Time: {elapsed:.2f}s")
        print(f"Tokens: {in_tokens} in | {out_tokens} out | {total} total")
        print(f"Token Savings: Handled {total} tokens locally instead of cloud.")
        print(f"Estimated Cloud Cost Avoided: ${cloud_cost:.6f}")
        print(f"Output saved to: {output_path}")
    else:
        reason = result.get("reason") or result.get("handoff_reason") or "Pipeline handoff required."
        in_tokens = result.get("input_tokens", 0)
        out_tokens = result.get("output_tokens", 0)
        total = result.get("total_tokens", 0)
        _record_pipeline_handoff(
            ledger,
            task_id,
            reason,
            input_tokens=in_tokens,
            output_tokens=out_tokens,
            total_tokens=total,
        )
        _log_cli_activity(
            f"pipeline handoff task={task_id[:8]} reason={reason}",
            ledger_dir=ledger_dir,
        )
        print(f"\n--- Pipeline Summary ---")
        print(f"Status: HANDOFF REQUIRED")
        print(f"Reason: {reason}")
        print("Escalating to Worker Council / Cloud...")

def _run_stability_pass(
    tasks_path: str,
    backend_type: str,
    model: str,
    base_url: Optional[str],
    timeout_seconds: int,
    ledger_dir: str,
    study_id: str,
    run_id: Optional[str],
):
    import sys
    import os
    import uuid
    from .benchmarks import load_benchmark_tasks, resolve_validator, result_to_model_event
    from .client import TriageClient
    from .task_ledger import TaskLedger

    print("======================================================================")
    print("🚀 Starting Codex Post-Sprint Stability Pass...")
    print(f"Tasks: {tasks_path}")
    print(f"Backend: {backend_type} | Model: {model}")
    print("======================================================================")

    # 1. Check/prepare logging and activity
    ledger = TaskLedger(ledger_dir=ledger_dir)
    log_dir = ledger_dir
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "triagecore.log")

    # Record start in CLI activity log
    _log_cli_activity(f"stability-pass started backend={backend_type} model={model} study={study_id}", ledger_dir=ledger_dir)

    try:
        tasks = load_benchmark_tasks(tasks_path)
    except Exception as e:
        print(f"❌ Error loading benchmark tasks: {e}")
        sys.exit(1)

    client = TriageClient(
        backend_type=backend_type,
        model=model,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )

    all_passed = True
    results_summary = []

    for task in tasks:
        task_id = str(uuid.uuid4())
        print(f"Running task {task.task_id} ({task.category})...")

        ledger.append_event(task_id, "task_created", {
            "title": f"Stability Pass: {task.task_id}",
            "description": task.prompt,
            "target_files": task.target_files,
            "benchmark_task_id": task.task_id,
            "study_id": study_id,
            "run_id": run_id,
        })
        ledger.append_event(task_id, "runner_selected", {"runner": "stability_pass"})

        # Log context pack
        _append_context_pack_event(
            ledger=ledger,
            task_id=task_id,
            prompt=f"{task.prompt}\n\nData:\n{task.data}",
            files=task.target_files,
            runner="stability_pass",
            category=task.category,
            ledger_dir=ledger_dir,
        )

        # Execute
        result = client.run_task(
            prompt=task.prompt,
            data=task.data,
            validator=resolve_validator(task.validator),
        )

        observed = result.get("status")
        expected = task.expected_status
        passed = (observed == expected)
        wasted = 0 if passed else result.get("total_tokens", 0)

        # Log completion
        event_payload = result_to_model_event(task, result)
        event_payload["wasted_tokens"] = wasted

        ledger.append_event(task_id, "model_evaluated", event_payload)
        if result.get("status") == "handoff_required":
            ledger.append_event(task_id, "handoff_generated", {
                "reason": result.get("handoff_reason") or result.get("reason"),
                "wasted_tokens": wasted,
            })

        status_char = "✅" if passed else "❌"
        print(f"  {status_char} Observed: {observed} | Expected: {expected}")

        _log_cli_activity(
            f"stability-pass task={task.task_id} observed={observed} expected={expected} passed={passed}",
            ledger_dir=ledger_dir,
        )

        results_summary.append({
            "task_id": task.task_id,
            "category": task.category,
            "expected": expected,
            "observed": observed,
            "passed": passed
        })

        if not passed:
            all_passed = False

    # 2. Verify Logging Compliance
    print("\n----------------------------------------------------------------------")
    print("Checking Logging Compliance...")
    logging_ok = False
    if os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                log_content = f.read()
            # Verify that stability pass logs are present in the file
            if f"stability-pass started backend={backend_type}" in log_content:
                logging_ok = True
                print("✅ Logging compliance check passed (triagecore.log verified).")
            else:
                print("❌ Logging compliance check failed (start message not found in log).")
        except Exception as e:
            print(f"❌ Error checking log file: {e}")
    else:
        print(f"❌ Log file {log_path} does not exist.")

    if not logging_ok:
        all_passed = False

    print("======================================================================")
    print("Stability Pass Summary:")
    for res in results_summary:
        status_str = "PASS" if res["passed"] else "FAIL"
        print(f"  - {res['task_id']} ({res['category']}): {status_str} (Observed: {res['observed']}, Expected: {res['expected']})")

    log_status_str = "PASS" if logging_ok else "FAIL"
    print(f"  - Logging Compliance: {log_status_str}")
    print("======================================================================")

    if all_passed:
        print("🎉 Stability Pass Completed: SUCCESS")
        _log_cli_activity("stability-pass completed status=success", ledger_dir=ledger_dir)
    else:
        print("🚨 Stability Pass Completed: FAILED")
        _log_cli_activity("stability-pass completed status=failed", ledger_dir=ledger_dir)
        sys.exit(1)


def _lab_report(ledger_dir: str):
    from .task_ledger import TaskLedger
    from .lab import calculate_scientific_metrics
    
    ledger = TaskLedger(ledger_dir=ledger_dir)
    records = ledger.get_all_tasks()
    if not records:
        print("No task records found in the ledger to analyze.")
        return
        
    metrics = calculate_scientific_metrics(records)
    
    print("# TriageLab Scientific Metrics Report")
    print()
    print("| Metric | Value |")
    print("| --- | ---: |")
    print(f"| Total Runs | {metrics['total_runs']} |")
    print(f"| Total Reviewed | {metrics['total_reviewed']} |")
    print(f"| Total Accepted | {metrics['total_accepted']} |")
    print(f"| Accepted-Task Yield Rate | {metrics['accepted_yield_pct']:.1f}% |")
    print(f"| Mean Review Burden | {metrics['mean_review_burden_mins']:.2f} mins |")
    print(f"| Mean Tokens / Accepted Task | {metrics['mean_tokens_per_accepted_task']:.1f} |")
    print(f"| Mean Energy / Accepted Task | {metrics['mean_energy_kwh_per_accepted_task']:.6f} kWh |")
    print(f"| Mean Emissions / Accepted Task | {metrics['mean_emissions_gco2e_per_accepted_task']:.3f} gCO2e |")
    print(f"| Mean Water / Accepted Task | {metrics['mean_water_liters_per_accepted_task']:.3f} L |")
    print(f"| Total Tokens Consumed | {metrics['total_tokens']} |")
    print(f"| Total Wasted Tokens | {metrics['total_wasted_tokens']} |")
    print(f"| Token Efficiency Rate | {metrics['token_efficiency_pct']:.1f}% |")
    print()


def _lab_export(ledger_dir: str, output_path: Optional[str]):
    from .task_ledger import TaskLedger
    from .lab import export_tabular_dataset
    
    ledger = TaskLedger(ledger_dir=ledger_dir)
    records = ledger.get_all_tasks()
    if not records:
        print("No task records found to export.")
        return
        
    if not output_path:
        output_path = os.path.join(ledger_dir, "lab_export.csv")
        
    export_tabular_dataset(records, output_path)
    print(f"Success: Exported {len(records)} runs to '{output_path}'.")


def _lab_train(ledger_dir: str):
    from .task_ledger import TaskLedger
    from .lab import LightweightDecisionTree
    
    ledger = TaskLedger(ledger_dir=ledger_dir)
    records = ledger.get_all_tasks()
    if not records:
        print("No task records found to train on.")
        return
        
    X = []
    y = []
    for r in records:
        if not r.runner:
            continue

        # Only train on explicitly reviewed terminal states
        if r.status != "reviewed":
            continue

        accepted_lbl = 1 if r.accepted else 0

        X.append({
            "runner": r.runner or "unknown",
            "risk_level": r.risk_level or "unknown",
            "permission_profile": r.permission_profile or "unknown"
        })
        y.append(accepted_lbl)
        
    if not X:
        print("No valid task runs with assigned runners found to train on.")
        return
        
    features = ["runner", "risk_level", "permission_profile"]
    model = LightweightDecisionTree(max_depth=4)
    model.fit(X, y, features)
    
    model_path = os.path.join(ledger_dir, "predictive_model.json")
    os.makedirs(os.path.dirname(os.path.abspath(model_path)), exist_ok=True)
    import json
    with open(model_path, "w", encoding="utf-8") as f:
        json.dump(model.serialize(), f, indent=2)
        
    print(f"Success: Trained LightweightDecisionTree on {len(X)} samples.")
    print(f"Model saved to '{model_path}'.")
    print()
    print("Learned Decision Rules Visualizer:")
    print(model.render_tree_text())


if __name__ == "__main__":
    main()
