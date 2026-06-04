from typing import List, Dict, Any
from .work_orders import WorkOrder
from .handoff import HandoffPacket


class UnionRep:
    """
    The steward agent that audits local worker results and decides if an escalation is required.
    """

    def __init__(self, budgets: Dict[str, Any] = None):
        self.budgets = budgets or {}

    def evaluate(
        self,
        task_prompt: str,
        target_files: List[str],
        completed_orders: List[WorkOrder],
    ) -> Dict[str, Any]:
        """
        Evaluate local outputs against budgets and acceptance criteria.
        """
        total_energy = sum(
            o.result.get("resource_usage", {}).get("energy_kwh_estimate", 0)
            for o in completed_orders
            if o.result
        )
        total_duration = sum(
            o.result.get("resource_usage", {}).get("duration_seconds", 0)
            for o in completed_orders
            if o.result
        )

        # Check validators if any (only the latest run determines final status)
        validators = [o for o in completed_orders if o.assigned_role == "validator"]
        validation_passed = (
            validators[-1].result.get("is_valid", False)
            if (validators and validators[-1].result)
            else True
        )

        needs_escalation = False
        reasons = []

        if not validators:
            # If no validators ran, maybe we escalate or just accept? For MVP, let's accept if there's output.
            pass
        elif not validation_passed:
            needs_escalation = True
            reasons.append("Local validators failed.")

        max_energy = self.budgets.get("max_energy_kwh_per_task", 0.02)
        if total_energy > max_energy:
            needs_escalation = True
            reasons.append(
                f"Exceeded energy budget ({total_energy:.4f} > {max_energy})."
            )

        # Compile summaries
        local_work_summary = []
        for o in completed_orders:
            if o.result:
                local_work_summary.append(
                    f"- {o.assigned_role}: completed with output keys: {list(o.result.keys())}"
                )

        return {
            "local_result_status": "insufficient" if needs_escalation else "sufficient",
            "reason": (
                " ".join(reasons) if needs_escalation else "Local workers succeeded."
            ),
            "recommended_escalation": "codex" if needs_escalation else "none",
            "recommended_permission_profile": (
                "workspace" if needs_escalation else "read-only"
            ),
            "resource_summary": {
                "local_attempts": len(completed_orders),
                "estimated_energy_kwh": total_energy,
                "duration_seconds": total_duration,
            },
            "handoff_summary": "\n".join(local_work_summary),
        }

    def generate_escalation_packet(
        self, evaluation: Dict[str, Any], task_prompt: str, target_files: List[str]
    ) -> HandoffPacket:
        return HandoffPacket(
            title=f"Escalation: {task_prompt[:30]}",
            summary=task_prompt,
            context=f"Local work attempted:\n{evaluation['handoff_summary']}\nReason for escalation: {evaluation['reason']}",
            target_files=target_files,
            constraints=["Follow local codebase styling."],
            acceptance_criteria=["Tests pass."],
            test_commands=["pytest tests/"],
            safety_notes=[],
            recommended_backend=evaluation.get("recommended_escalation", "codex"),
            recommended_permission_profile=evaluation.get(
                "recommended_permission_profile", "workspace"
            ),
            risk_level="medium",
        )
