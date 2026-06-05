import os
import uuid
import json
from typing import List, Dict, Any, Optional, Tuple
from .work_orders import TaskBoard, WorkOrder
from .worker_registry import WorkerRegistry
from .project_steward import ProjectSteward
from .config import default_config
from .validator_tools import ValidatorTools


def _compute_file_chunks(
    filepath: str, max_bytes: int
) -> List[Tuple[int, Optional[int]]]:
    """Return a list of (start_line, end_line) tuples for filepath.

    If the whole file fits within *max_bytes* a single ``(0, None)`` entry is
    returned.  Otherwise the file is split on line boundaries so each chunk's
    UTF-8 byte count stays below *max_bytes*.
    """
    if not os.path.isfile(filepath):
        return [(0, None)]

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    total = len(lines)
    full_bytes = sum(len(ln.encode("utf-8")) for ln in lines)
    if full_bytes <= max_bytes:
        return [(0, None)]

    chunks: List[Tuple[int, Optional[int]]] = []
    chunk_start = 0
    while chunk_start < total:
        running = 0
        chunk_end = chunk_start
        for i in range(chunk_start, total):
            running += len(lines[i].encode("utf-8"))
            if running > max_bytes:
                break
            chunk_end = i + 1
        else:
            chunk_end = total
        if chunk_end == chunk_start:          # single line > max_bytes — advance anyway
            chunk_end = chunk_start + 1
        chunks.append((chunk_start, chunk_end))
        chunk_start = chunk_end

    return chunks


class ProjectManager:
    def __init__(self):
        self.board = TaskBoard()
        self.registry = WorkerRegistry()
        self.budgets = default_config.global_config.get("budgets", {})
        self.steward = ProjectSteward(budgets=self.budgets)

    def dispatch_task(
        self,
        prompt: str,
        target_files: List[str],
        required_roles: List[str],
        stream_callback=None,
    ) -> Dict[str, Any]:
        """
        Takes a raw prompt and targets, splits large files into chunks, dispatches
        to specialized workers, handles validator loopbacks and early delegation,
        then evaluates with ProjectSteward.
        """
        task_id = str(uuid.uuid4())

        # ── TriageLab Predictive Routing Check ──────────────────────────────
        model_path = os.path.join(default_config.get_ledger_dir(), "predictive_model.json")
        if os.path.exists(model_path):
            try:
                from .classifier import DangerDetector
                from .lab import LightweightDecisionTree
                
                danger = DangerDetector.analyze(prompt, target_files)
                sample = {
                    "runner": "worker_council",
                    "risk_level": danger.risk_level,
                    "permission_profile": danger.recommended_profile
                }
                
                with open(model_path, "r", encoding="utf-8") as f:
                    model_data = json.load(f)
                    
                model = LightweightDecisionTree()
                model.deserialize(model_data)
                
                pred, prob = model.predict(sample)
                if pred == 0 or prob < 0.5:
                    warning_msg = (
                        f"⚠️ [TriageLab Warning] High likelihood of local failure/escalation predicted "
                        f"for this task profile (Risk: {danger.risk_level}, Profile: {danger.recommended_profile}, Runner: worker_council)."
                    )
                    if stream_callback:
                        stream_callback(f"\n{warning_msg}\n")
                    print(warning_msg)
            except Exception:
                pass

        max_artifact_bytes: int = self.budgets.get("max_artifact_bytes", 12000)
        max_tokens: int = self.budgets.get("max_tokens", 800)
        max_repair_attempts: int = self.budgets.get("max_local_attempts", 2)

        # ── 1. Pre-scan target files for chunking ────────────────────────────
        file_chunk_map: Dict[str, List[Tuple[int, Optional[int]]]] = {}
        for fp in target_files:
            file_chunk_map[fp] = _compute_file_chunks(fp, max_artifact_bytes)

        # Determine whether any file needs chunking
        needs_chunking = any(
            len(chunks) > 1 for chunks in file_chunk_map.values()
        )

        if needs_chunking and stream_callback:
            total_chunks = sum(len(v) for v in file_chunk_map.values())
            stream_callback(
                f"\n[CHUNKED MODE] Large file(s) detected — "
                f"dispatching {total_chunks} chunk(s) across "
                f"{len(target_files)} file(s).\n"
            )

        # ── 2. Queue initial work orders ─────────────────────────────────────
        if needs_chunking:
            # context_planner gets the first chunk of the first file (structural overview)
            first_file = target_files[0]
            first_chunk_start, first_chunk_end = file_chunk_map[first_file][0]
            if "context_planner" in required_roles:
                self.board.add_order(
                    WorkOrder(
                        task_id=task_id,
                        assigned_role="context_planner",
                        input_artifacts=target_files + [prompt],
                        output_required=(
                            "Summarise the file structure and list the issues."
                        ),
                        max_tokens=max_tokens,
                        chunk_start=first_chunk_start,
                        chunk_end=first_chunk_end,
                    )
                )

            # One implementer per chunk
            for fp in target_files:
                for chunk_start, chunk_end in file_chunk_map[fp]:
                    line_range = (
                        f"lines {chunk_start + 1}–"
                        + (str(chunk_end) if chunk_end else "EOF")
                    )
                    if "implementer" in required_roles:
                        self.board.add_order(
                            WorkOrder(
                                task_id=task_id,
                                assigned_role="implementer",
                                input_artifacts=[fp, prompt],
                                output_required=(
                                    f"Fix all issues in {fp} ({line_range})."
                                ),
                                max_tokens=max_tokens,
                                chunk_start=chunk_start,
                                chunk_end=chunk_end,
                            )
                        )
        else:
            # Original flat dispatch (file fits in one pass)
            for role in required_roles:
                if role == "review_worker":
                    # review_worker is queued after implementer dynamically
                    continue
                self.board.add_order(
                    WorkOrder(
                        task_id=task_id,
                        assigned_role=role,
                        input_artifacts=target_files + [prompt],
                        output_required="Draft code or validate the previous steps.",
                        max_tokens=max_tokens,
                    )
                )

        # ── 3. Execute dynamically ────────────────────────────────────────────
        completed: List[WorkOrder] = []
        # Map from chunk key -> context list so chunks don't bleed into each other
        # Key: (chunk_start, chunk_end) tuple; None for non-chunked flow
        chunk_contexts: Dict[tuple, List[str]] = {}
        # Global context (context_planner output shared across chunks)
        global_context: List[str] = []
        MAX_CONTEXT_ITEMS = 2  # only inject the most recent N items per order
        repair_attempts = 0
        worker_error_count = 0
        forced_escalation = False
        escalation_target = "codex"
        early_stopped = False
        early_stop_reason = ""
        
        # We will need the event loop logic for sending ledger events, but 
        # normally TriageCore runs through `engine.py` / `TaskLedger`. We don't have
        # direct access to the ledger here without passing it. For now, we will 
        # just record result fields that engine.py can log.

        while True:
            pending = self.board.get_pending()
            if not pending:
                break

            order = pending[0]
            self.board.update_status(order.work_order_id, "running")

            worker = self.registry.get_worker(order.assigned_role)
            if not worker:
                self.board.update_status(
                    order.work_order_id,
                    "failed",
                    {"error": f"Worker role {order.assigned_role} not found"},
                )
                continue

            # Inject capped, chunk-scoped context into the order
            chunk_key = (order.chunk_start, order.chunk_end)
            relevant_context = list(global_context)  # always include context_planner output
            relevant_context += chunk_contexts.get(chunk_key, [])[-MAX_CONTEXT_ITEMS:]
            for item in relevant_context:
                if item not in order.input_artifacts:
                    order.input_artifacts.append(item)

            if stream_callback:
                stream_callback(
                    f"\n\n--- 🤖 [{order.assigned_role.upper()}] IS THINKING"
                    f" (Model: {worker.model}) ---\n"
                )

            result = worker.process(order, stream_callback=stream_callback)
            self.board.update_status(order.work_order_id, "completed", result)
            completed.append(self.board.orders[order.work_order_id])

            # Calculate cumulative energy (current_energy_kwh) of completed orders so far
            current_energy_kwh = 0.0
            for o in completed:
                if o.result:
                    usage = o.result.get("resource_usage") or {}
                    kwh = usage.get("energy_kwh_estimate") or 0.0
                    if not kwh:
                        joules = usage.get("energy_estimated") or 0.0
                        kwh = joules / 3600000.0
                    current_energy_kwh += kwh

            max_energy = self.budgets.get("max_energy_kwh_per_task", 0.02)
            if current_energy_kwh > max_energy:
                forced_escalation = True
                escalation_target = "antigravity"
                early_stopped = True
                early_stop_reason = f"Exceeded energy budget ({current_energy_kwh:.4f} > {max_energy})."

                if stream_callback:
                    stream_callback(
                        f"\n[EARLY STOPPING] Dynamic energy budget exceeded. "
                        f"Cumulative: {current_energy_kwh:.4f} kWh. Max: {max_energy} kWh. "
                        f"Cancelling remaining tasks and escalating to Antigravity.\n"
                    )
                # Cancel all remaining pending work orders
                for pending_order in self.board.get_pending():
                    self.board.update_status(pending_order.work_order_id, "cancelled")
                break

            safe_result = {
                k: v
                for k, v in result.items()
                if k not in ["resource_usage", "worker_id"]
            }
            context_entry = (
                f"Previous Worker [{order.assigned_role}] Output:\n"
                f"```json\n{json.dumps(safe_result, indent=2)}\n```"
            )

            # Store in the appropriate scoped context
            chunk_key = (order.chunk_start, order.chunk_end)
            if order.assigned_role == "context_planner":
                # context_planner output is global — relevant to all chunks
                global_context.append(context_entry)
            else:
                if chunk_key not in chunk_contexts:
                    chunk_contexts[chunk_key] = []
                chunk_contexts[chunk_key].append(context_entry)

            # ── Explicit worker error detection ──────────────────────────────
            if result.get("error") and order.assigned_role != "review_worker":
                worker_error_count += 1
                if stream_callback:
                    snippet = str(result["error"])[:120]
                    stream_callback(
                        f"\n↳ [WORKER ERROR] {order.assigned_role} reported: "
                        f"{snippet}\n"
                    )

            # ── Model-driven early delegation ────────────────────────────────
            delegate_to = result.get("delegate_to")
            if delegate_to in ["codex", "antigravity"]:
                forced_escalation = True
                escalation_target = delegate_to
                if stream_callback:
                    stream_callback(
                        f"\n↳ [DELEGATION] Worker {order.assigned_role} requested "
                        f"direct delegation to {delegate_to.upper()}.\n"
                    )
                for pending_order in self.board.get_pending():
                    self.board.update_status(pending_order.work_order_id, "cancelled")
                break

            # ── Model-driven sequential routing ─────────────────────────────
            next_worker = result.get("next_worker")
            if next_worker and next_worker in self.registry.workers:
                if stream_callback:
                    stream_callback(
                        f"\n↳ [DYNAMIC ROUTE] Worker {order.assigned_role} routed "
                        f"next task to {next_worker}.\n"
                    )
                already_queued = any(
                    o.assigned_role == next_worker and o.status == "pending"
                    for o in self.board.orders.values()
                )
                if not already_queued:
                    self.board.add_order(
                        WorkOrder(
                            task_id=task_id,
                            assigned_role=next_worker,
                            input_artifacts=target_files
                            + [prompt]
                            + [
                                f"Routing context from {order.assigned_role}: "
                                f"{json.dumps(safe_result)}"
                            ],
                            output_required=(
                                f"Process next steps requested by "
                                f"{order.assigned_role}."
                            ),
                            max_tokens=max_tokens,
                        )
                    )

            # ── Deterministic Validation ──────────────────────────────────────
            if order.assigned_role == "implementer":
                if "repaired_code" in result or "raw_text" in result:
                    text_to_validate = result.get("repaired_code", result.get("raw_text", ""))
                    validators_to_run = order.validators or ValidatorTools.infer_validators(target_files)
                    
                    if validators_to_run:
                        val_results = ValidatorTools.run(validators_to_run, text_to_validate, target_files)
                        passed_all = all(vr.passed for vr in val_results)
                        issues = []
                        for vr in val_results:
                            issues.extend(vr.issues)
                            
                        # Save validation results into the order result so the ledger picks it up
                        result["validation_run"] = {
                            "validators": validators_to_run,
                            "passed": passed_all,
                            "issues": issues
                        }

                        if not passed_all:
                            if repair_attempts < max_repair_attempts:
                                repair_attempts += 1
                                issues_str = ", ".join(issues)
                                if stream_callback:
                                    stream_callback(
                                        f"\n↳ [DOUBT] Deterministic Validator issues found: {issues_str}. "
                                        f"Routing back to implementer "
                                        f"(Attempt {repair_attempts}/{max_repair_attempts})...\n"
                                    )
                                self.board.add_order(
                                    WorkOrder(
                                        task_id=task_id,
                                        assigned_role="implementer",
                                        input_artifacts=target_files
                                        + [prompt]
                                        + [f"Feedback from validator tools: {issues_str}"],
                                        output_required=(
                                            "Fix the reported validation issues and output "
                                            "repaired code."
                                        ),
                                        validators=order.validators,
                                        max_tokens=max_tokens,
                                        chunk_start=order.chunk_start,
                                        chunk_end=order.chunk_end,
                                    )
                                )
                            else:
                                if stream_callback:
                                    stream_callback(
                                        "\n↳ [ESCALATION] Validator failed after max repair "
                                        "attempts. Escalating...\n"
                                    )
                        else:
                            # Validation passed, queue qualitative review if requested
                            if "review_worker" in required_roles:
                                if stream_callback:
                                    stream_callback(
                                        "\n↳ [VERIFIED] Deterministic checks passed. "
                                        "Queueing LLMReviewWorker...\n"
                                    )
                                self.board.add_order(
                                    WorkOrder(
                                        task_id=task_id,
                                        assigned_role="review_worker",
                                        input_artifacts=target_files + [prompt, text_to_validate],
                                        output_required=(
                                            "Critique the quality, completeness, and risks of this implementation."
                                        ),
                                        max_tokens=max_tokens,
                                        chunk_start=order.chunk_start,
                                        chunk_end=order.chunk_end,
                                    )
                                )

        # ── 4. Evaluate with ProjectSteward ─────────────────────────────────────────
        evaluation = self.steward.evaluate(prompt, target_files, completed) or {}
        if forced_escalation:
            evaluation["local_result_status"] = "insufficient"
            evaluation["early_stopped"] = early_stopped
            evaluation["early_stop_reason"] = early_stop_reason
            if early_stopped:
                evaluation["reason"] = f"Early stopping: {early_stop_reason}"
            else:
                evaluation["reason"] = (
                    f"Forced delegation by council worker to {escalation_target}."
                )
            evaluation["recommended_escalation"] = escalation_target

        # Promote worker errors to insufficient if reviewers errored out
        if (
            worker_error_count > 0
            and evaluation.get("local_result_status") == "sufficient"
        ):
            reviewers_ok = any(
                o.assigned_role == "review_worker"
                and o.result
                and o.result.get("is_valid")
                and not o.result.get("error")
                for o in completed
            )
            if not reviewers_ok:
                evaluation["local_result_status"] = "insufficient"
                evaluation["reason"] = (
                    f"{worker_error_count} worker error(s) prevented successful "
                    "local execution."
                )
                evaluation["recommended_escalation"] = "codex"

        # ── 5. Write escalation packet if needed ─────────────────────────────
        packet_path = None
        if evaluation.get("local_result_status") == "insufficient":
            packet = self.steward.generate_escalation_packet(
                evaluation, prompt, target_files
            )
            try:
                tasks_dir = default_config.get_tasks_dir()
                os.makedirs(tasks_dir, exist_ok=True)
                packet_path = os.path.join(tasks_dir, f"escalation_{task_id[:8]}.md")
                with open(packet_path, "w", encoding="utf-8") as f:
                    f.write(packet.to_markdown())
            except OSError as e:
                print(f"Failed to write escalation packet: {e}")
                packet_path = None

        return {
            "task_id": task_id,
            "evaluation": evaluation,
            "escalation_packet": packet_path,
            "work_orders": [o.work_order_id for o in completed],
            "all_orders": completed,  # we inject this so engine.py can log them
        }
