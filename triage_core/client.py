from typing import Callable, Dict, Any, Optional
from .engine import TriageEngine
from .routers import TriageRouter
from .backends import LocalBackend, create_backend
from .routing import (
    ResilienceRouteInput,
    build_route_decision_payload,
    build_worker_result_payload,
    choose_resilience_route,
)
from .task_ledger import TaskLedger

class TriageClient:
    def __init__(
        self,
        backend_type: str = "ollama",
        model: str = "local-model",
        base_url: Optional[str] = None,
        backend: Optional[LocalBackend] = None,
        timeout_seconds: int = 45
    ):
        """
        Initializes the TriageClient which manages local execution and handoff routing.
        
        Args:
            backend_type: The preset to use ("ollama", "vllm", "llama.cpp", "custom").
            model: The model string expected by the local server.
            base_url: Optional custom URL base.
            backend: Explicit LocalBackend instance (overrides preset factory).
            timeout_seconds: The strict temporal budget for local generation.
        """
        if backend is None:
            backend = create_backend(backend_type=backend_type, model=model, base_url=base_url)
            
        self.engine = TriageEngine(backend=backend, timeout_seconds=timeout_seconds)
        self.router = TriageRouter()

    def run_task(
        self,
        prompt: str,
        data: str,
        validator: Optional[Callable[[str], bool]] = None,
        ledger: Optional[TaskLedger] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Runs a given prompt and data through the execution engine.
        First, it classifies and routes the request.
        If it's safe to run locally, it attempts execution.
        If execution fails, times out, or the router blocks it, it creates a structured handoff.
        """
        from .classifier import TaskClassifier
        from .project_steward import ProjectSteward
        
        # Step 1: Routing logic
        category = TaskClassifier.classify(prompt)
        route_decision = self.router.specialist.route_task(category, prompt, data)
        use_timeout = route_decision.get("timeout", self.engine.timeout)
        resilience_input = self._build_resilience_route_input(category=category, validator=validator)
        resilience_decision = choose_resilience_route(resilience_input)
        route_payload = build_route_decision_payload(
            resilience_input,
            resilience_decision,
            selected_backend=getattr(self.engine.backend, "name", ""),
            selected_model=route_decision.get("model") or getattr(self.engine.backend, "model", ""),
        )
        self._append_optional_event(
            ledger=ledger,
            task_id=task_id,
            event_type="route_decision",
            payload=route_payload,
        )
        
        steward = ProjectSteward()
        steward_eval = steward.evaluate(task_prompt=prompt, target_files=[], completed_orders=[])
        if steward_eval["local_result_status"] == "insufficient":
            result = {
                "status": "handoff_required",
                "source": "steward",
                "reason": steward_eval["reason"],
                "handoff_reason": steward_eval["reason"],
                "backend_name": getattr(self.engine.backend, "name", None),
                "model": getattr(self.engine.backend, "model", None),
                "timeout_seconds": use_timeout,
                "firewall_triggered": steward_eval.get("firewall_triggered", False),
                "firewall_reason": steward_eval.get("firewall_reason", ""),
                "credit_allowance_total": steward_eval.get("credit_allowance_total", 0),
                "credit_allowance_used": steward_eval.get("credit_allowance_used", 0),
                "credit_allowance_remaining": steward_eval.get("credit_allowance_remaining", 0),
                "credit_allowance_exhausted": steward_eval.get("credit_allowance_exhausted", False),
                "worker_result_status": "not_attempted",
                "failure_type": "safety_handoff",
                "failure_stage": "router",
            }
            self._append_optional_event(
                ledger=ledger,
                task_id=task_id,
                event_type="worker_result",
                payload=build_worker_result_payload(route_payload, result),
            )
            return self._merge_route_fields(result, route_payload)

        if route_decision.get("offload_recommended", False):
            reason = f"Router bypass: {route_decision.get('reason')}"
            result = {
                "status": "handoff_required",
                "source": "router",
                "reason": reason,
                "handoff_reason": reason,
                "backend_name": getattr(self.engine.backend, "name", None),
                "model": getattr(self.engine.backend, "model", None),
                "timeout_seconds": use_timeout,
                "worker_result_status": "not_attempted",
                "failure_type": "safety_handoff",
                "failure_stage": "router",
            }
            self._append_optional_event(
                ledger=ledger,
                task_id=task_id,
                event_type="worker_result",
                payload=build_worker_result_payload(route_payload, result),
            )
            return self._merge_route_fields(result, route_payload)
            
        # Step 2: Local execution
        post_processor = route_decision.get("post_processor")
        original_model = self.engine.backend.model
        requested_model = route_decision.get("model")
        
        # Swapping model dynamically for real backends, but preserving mock backend names in tests
        if getattr(self.engine.backend, "name", "") != "fake" and requested_model and requested_model != original_model:
            self.engine.backend.model = requested_model
            
        try:
            result = self.engine.execute_task(
                task_prompt=prompt,
                raw_data=data,
                validator=validator,
                timeout=use_timeout,
                post_processor=post_processor
            )
            self._append_optional_event(
                ledger=ledger,
                task_id=task_id,
                event_type="worker_result",
                payload=build_worker_result_payload(route_payload, result),
            )
            return self._merge_route_fields(result, route_payload)
        finally:
            self.engine.backend.model = original_model

    @staticmethod
    def _append_optional_event(
        ledger: Optional[TaskLedger],
        task_id: Optional[str],
        event_type: str,
        payload: Dict[str, Any],
    ) -> None:
        if ledger is None or not task_id:
            return
        ledger.append_event(task_id, event_type, payload)

    @staticmethod
    def _merge_route_fields(result: Dict[str, Any], route_payload: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(result)
        merged["selected_route"] = route_payload.get("selected_route")
        merged["route_reason"] = route_payload.get("reason")
        merged["fallback_depth"] = route_payload.get("fallback_depth")
        return merged

    @staticmethod
    def _build_resilience_route_input(
        *,
        category: str,
        validator: Optional[Callable[[str], bool]],
    ) -> ResilienceRouteInput:
        task_class_map = {
            "docs_update": "docs_update",
            "bugfix": "code_repair",
            "test_addition": "code_generation",
            "refactor": "code_repair",
            "packaging": "configuration_review",
            "security_review": "security_review",
            "architecture_planning": "architecture_planning",
            "blocked_or_high_risk": "security_review",
        }
        complexity_map = {
            "docs_update": "low",
            "bugfix": "medium",
            "test_addition": "medium",
            "refactor": "medium",
            "packaging": "medium",
            "security_review": "high",
            "architecture_planning": "high",
            "blocked_or_high_risk": "high",
        }
        sensitivity_map = {
            "docs_update": "low",
            "bugfix": "low",
            "test_addition": "low",
            "refactor": "low",
            "packaging": "medium",
            "security_review": "high",
            "architecture_planning": "medium",
            "blocked_or_high_risk": "high",
        }
        return ResilienceRouteInput(
            task_class=task_class_map.get(category, "general"),
            complexity=complexity_map.get(category, "medium"),
            sensitivity=sensitivity_map.get(category, "low"),
            privacy_level="local_ok",
            internet_ok=False,
            cloud_primary_available=False,
            cloud_secondary_available=False,
            cloud_credit_state="none",
            lm_studio_ok=True,
            local_heavy_available=True,
            local_fast_available=True,
            deterministic_tool_available=validator is not None,
            required_checks=["validator"] if validator is not None else [],
        )
