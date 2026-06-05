import os
import re
import yaml
from typing import List, Dict, Any
from .work_orders import WorkOrder
from .handoff import HandoffPacket
from .config import default_config


class ProjectSteward:
    """
    The steward agent that audits local worker results and decides if an escalation is required.
    """

    # Sensitive terms from the Cybernetic Ecology framework
    SENSITIVE_KEYWORDS = {
        "water intake", "sewer lift", "tribal", "bo-no-po-ti", "bloody island", "sacred",
        "archaeological", "burial", "confidential infrastructure"
    }

    def __init__(self, budgets: Dict[str, Any] = None):
        self.budgets = budgets or {}
        self.rules = self._load_boundary_rules()

    def _load_boundary_rules(self) -> List[Dict[str, Any]]:
        try:
            path = default_config.get_boundary_rules_path()
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if isinstance(data, dict) and "rules" in data:
                        return data["rules"]
        except Exception as e:
            print(f"Warning: Failed to load boundary rules: {e}")
        return []

    def evaluate(
        self,
        task_prompt: str,
        target_files: List[str],
        completed_orders: List[WorkOrder],
    ) -> Dict[str, Any]:
        """
        Evaluate local outputs against budgets, acceptance criteria, and ethical firewalls.
        """
        total_energy_kwh = sum(
            o.result.get("resource_usage", {}).get("energy_kwh_estimate", 0)
            for o in completed_orders
            if o.result
        )
        total_energy_joules = sum(
            o.result.get("resource_usage", {}).get("energy_estimated", 0)
            for o in completed_orders
            if o.result
        )
        total_duration = sum(
            o.result.get("resource_usage", {}).get("duration_seconds", 0)
            for o in completed_orders
            if o.result
        )

        # 1. Ethical Firewall (Sensitive GIS/Context)
        needs_escalation = False
        reasons = []
        recommended_escalation = "none"

        # Scan prompt and outputs for sensitive context
        combined_text = task_prompt
        for o in completed_orders:
            if o.result and "output" in o.result:
                combined_text += " " + str(o.result["output"])

        combined_text_lower = combined_text.lower()

        # Run configured boundary rules
        rules_run = False
        if self.rules:
            for rule in self.rules:
                trigger = rule.get("trigger", {})
                decision = rule.get("decision", "human_only")
                msg = rule.get("message", "Sensitive context detected.")
                
                # Check string terms (case-insensitive)
                matched_term = None
                terms = trigger.get("terms", [])
                for term in terms:
                    if term.lower() in combined_text_lower:
                        matched_term = term
                        break
                        
                # Check regex patterns
                matched_regex = None
                regex_patterns = trigger.get("regex", [])
                for pattern in regex_patterns:
                    try:
                        if re.search(pattern, combined_text):
                            matched_regex = pattern
                            break
                    except Exception:
                        pass
                
                if matched_term or matched_regex:
                    needs_escalation = True
                    trigger_detail = matched_term if matched_term else f"regex '{matched_regex}'"
                    reasons.append(f"Ethical Firewall: Triggered rule '{rule.get('id')}' via {trigger_detail}. {msg}")
                    recommended_escalation = decision
                    rules_run = True
                    break

        # Fallback to hardcoded keywords if no rules were loaded or triggered
        if not rules_run:
            for kw in self.SENSITIVE_KEYWORDS:
                if kw in combined_text_lower:
                    needs_escalation = True
                    reasons.append(f"Ethical Firewall: Sensitive context detected ('{kw}').")
                    recommended_escalation = "human_only"
                    break

        # 2. Validation Checks
        reviewers = [o for o in completed_orders if o.assigned_role == "review_worker"]
        validation_passed = (
            reviewers[-1].result.get("is_valid", False)
            if (reviewers and reviewers[-1].result)
            else True
        )

        if not needs_escalation:
            if not reviewers:
                pass
            elif not validation_passed:
                needs_escalation = True
                reasons.append("Local reviewers failed validation.")
                recommended_escalation = "codex"

            # 3. Energy/Token Budget Checks
            max_energy = self.budgets.get("max_energy_kwh_per_task", 0.02)
            if total_energy_kwh > max_energy:
                needs_escalation = True
                reasons.append(f"Exceeded energy budget ({total_energy_kwh:.4f} > {max_energy}).")
                # Escalate to antigravity for credit allowance optimization
                recommended_escalation = "antigravity"

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
            "recommended_escalation": recommended_escalation,
            "recommended_permission_profile": (
                "workspace" if needs_escalation else "read-only"
            ),
            "resource_summary": {
                "local_attempts": len(completed_orders),
                "estimated_energy_kwh": total_energy_kwh,
                "estimated_energy_joules": total_energy_joules,
                "duration_seconds": total_duration,
            },
            "handoff_summary": "\n".join(local_work_summary),
        }

    def generate_escalation_packet(
        self, evaluation: Dict[str, Any], task_prompt: str, target_files: List[str]
    ) -> HandoffPacket:
        escalation_target = evaluation.get("recommended_escalation", "codex")
        risk = "high" if escalation_target == "human_only" else "medium"

        return HandoffPacket(
            title=f"Escalation [{escalation_target.upper()}]: {task_prompt[:30]}",
            summary=task_prompt,
            context=f"Local work attempted:\n{evaluation['handoff_summary']}\nReason for escalation: {evaluation['reason']}",
            target_files=target_files,
            constraints=["Follow Cybernetic Ecology principles.", "Follow local codebase styling."],
            acceptance_criteria=["Ethical clearance verified if human_only.", "Tests pass."],
            test_commands=["pytest tests/"],
            safety_notes=[evaluation['reason']] if escalation_target == "human_only" else [],
            recommended_backend=escalation_target,
            recommended_permission_profile=evaluation.get(
                "recommended_permission_profile", "workspace"
            ),
            risk_level=risk,
        )
