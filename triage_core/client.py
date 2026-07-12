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
from .agent_identity import AgentIdentityRegistry
from .task_ledger import TaskLedger
from .privacy_scanner import scan_task_packet, PrivacyViolationError
from .config import default_config

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
        prompt: Optional[str] = None,
        data: Optional[str] = None,
        validator: Optional[Callable[[str], bool]] = None,
        ledger: Optional[TaskLedger] = None,
        task_id: Optional[str] = None,
        task_packet: Optional[Any] = None,
        route_decision_signing_registry: Optional[AgentIdentityRegistry] = None,
        route_decision_signing_agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Runs a given prompt and data through the execution engine.
        First, it classifies and routes the request.
        If it's safe to run locally, it attempts execution.
        If execution fails, times out, or the router blocks it, it creates a structured handoff.
        """
        from .classifier import TaskClassifier
        from .project_steward import ProjectSteward
        from .task_packet import TaskPacket

        if task_packet is None:
            if prompt is None or data is None:
                raise ValueError("Must provide either a task_packet or both prompt and data.")
            task_packet = TaskPacket(
                prompt=prompt,
                data=data,
                task_id=task_id,
                validator=validator,
                # Legacy inputs get default public metadata
            )
        else:
            prompt = task_packet.prompt
            data = task_packet.data
            validator = task_packet.validator
            if task_packet.task_id is not None:
                task_id = task_packet.task_id
        
        from .safe_task_packet import verify_packet, VerifiedTaskPacket, UnsafePacketError, make_external_safe_packet, LocalRouteUnavailableError
        from .privacy_scanner import PrivacyViolationError
        from .route_audit import RouteDecisionAudit
        
        try:
            verified_packet = verify_packet(task_packet)
            scan_passed = True
        except PrivacyViolationError:
            audit = RouteDecisionAudit(
                task_id=task_id,
                privacy_level="unknown",
                privacy_scan_passed=False,
                is_local_only=True,
                recommended_route=None,
                selected_backend=None,
                decision="blocked",
                reason_code="privacy_violation"
            )
            self._append_optional_event(ledger, task_id, "route_audit", audit.to_dict())
            raise
            
        if not isinstance(verified_packet, VerifiedTaskPacket):
            raise UnsafePacketError("Only VerifiedTaskPacket may enter routing boundary.")
            
        try:
            external_safe_packet = make_external_safe_packet(verified_packet)
            is_local_only = False
            privacy_level = "external_safe"
        except UnsafePacketError:
            external_safe_packet = None
            is_local_only = True
            privacy_level = "local_only"
            
        prompt = verified_packet.prompt
        data = verified_packet.data
        
        # Step 1: Routing logic
        category = TaskClassifier.classify(prompt)
        route_decision = self.router.specialist.route_task(category, prompt, data)
        use_timeout = route_decision.get("timeout", self.engine.timeout)
        resilience_input = self._build_resilience_route_input(category=category, validator=validator)
        
        if is_local_only:
            resilience_input.privacy_level = "local_only"
            
        resilience_decision = choose_resilience_route(resilience_input)
        selected_route = resilience_decision.selected_route
        selected_backend_name = self._selected_backend_name(selected_route)
        
        # Ensure local-only packets only use explicitly local routes
        if is_local_only:
            if selected_route not in ["local_heavy", "local_fast", "deterministic"]:
                audit = RouteDecisionAudit(task_id, privacy_level, True, True, selected_route, selected_backend_name, "blocked", "ambiguous_or_remote_route")
                self._append_optional_event(ledger, task_id, "route_audit", audit.to_dict())
                raise LocalRouteUnavailableError(f"Local backend unavailable or route '{selected_route}' is not proven local-safe for local-only packet. Failing closed.")
            if route_decision.get("offload_recommended", False):
                audit = RouteDecisionAudit(task_id, privacy_level, True, True, selected_route, selected_backend_name, "blocked", "offload_recommended_for_local_only")
                self._append_optional_event(ledger, task_id, "route_audit", audit.to_dict())
                raise LocalRouteUnavailableError("Specialist router recommended offload for a local-only packet. Failing closed.")
        
        # Allowed Route Audit
        audit = RouteDecisionAudit(
            task_id=task_id,
            privacy_level=privacy_level,
            privacy_scan_passed=True,
            is_local_only=is_local_only,
            recommended_route=selected_route,
            selected_backend=selected_backend_name,
            decision="allowed",
            reason_code="route_allowed"
        )
        self._append_optional_event(ledger, task_id, "route_audit", audit.to_dict())
        route_payload = build_route_decision_payload(
            resilience_input,
            resilience_decision,
            selected_backend=selected_backend_name,
            selected_model=(
                default_config.get_qwen_model()
                if selected_route in {"cloud_primary", "cloud_secondary"}
                else route_decision.get("model") or getattr(self.engine.backend, "model", "")
            ),
        )
        self._append_route_decision_event(
            ledger=ledger,
            task_id=task_id,
            payload=route_payload,
            signing_registry=route_decision_signing_registry,
            signing_agent_id=route_decision_signing_agent_id,
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

        if selected_route in {"human_handoff", "deterministic"}:
            if selected_route == "human_handoff":
                reason = (
                    "Human handoff required by the resilience route"
                    f": {resilience_decision.reason}"
                )
            else:
                reason = (
                    "Deterministic route selected, but no deterministic executor is "
                    f"wired into the governed loop: {resilience_decision.reason}"
                )
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

        if selected_route in {"cloud_primary", "cloud_secondary"}:
            result = self._execute_cloud_task(
                task_packet=external_safe_packet,
                task_prompt=prompt,
                raw_data=data,
                validator=validator,
                timeout=use_timeout,
                post_processor=route_decision.get("post_processor"),
            )
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
    def _append_route_decision_event(
        ledger: Optional[TaskLedger],
        task_id: Optional[str],
        payload: Dict[str, Any],
        signing_registry: Optional[AgentIdentityRegistry],
        signing_agent_id: Optional[str],
    ) -> None:
        if ledger is None or not task_id:
            return
        if signing_registry is not None and signing_agent_id:
            ledger.append_signed_route_decision_event(
                task_id,
                payload,
                signing_registry=signing_registry,
                signing_agent_id=signing_agent_id,
            )
            return
        ledger.append_event(task_id, "route_decision", payload)

    @staticmethod
    def _merge_route_fields(result: Dict[str, Any], route_payload: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(result)
        merged["selected_route"] = route_payload.get("selected_route")
        merged["route_reason"] = route_payload.get("reason")
        merged["fallback_depth"] = route_payload.get("fallback_depth")
        return merged

    def _selected_backend_name(self, selected_route: str) -> str:
        if selected_route in {"cloud_primary", "cloud_secondary"}:
            return "qwen"
        return getattr(self.engine.backend, "name", "unknown")

    @staticmethod
    def _execute_cloud_task(
        *,
        task_packet: Optional[Any],
        task_prompt: str,
        raw_data: str,
        validator: Optional[Callable[[str], bool]],
        timeout: int,
        post_processor: Optional[Callable[[str], str]],
    ) -> Dict[str, Any]:
        from .engine import TriageEngine
        from .safe_task_packet import ExternalSafeTaskPacket

        if not isinstance(task_packet, ExternalSafeTaskPacket):
            return {
                "status": "handoff_required",
                "source": "router",
                "reason": "Cloud execution requires an external-safe packet. Failing closed.",
                "handoff_reason": "Cloud execution requires an external-safe packet. Failing closed.",
                "worker_result_status": "not_attempted",
                "failure_type": "safety_handoff",
                "failure_stage": "router",
            }

        if not default_config.get_qwen_enabled():
            return {
                "status": "handoff_required",
                "source": "router",
                "reason": "Cloud route selected but Qwen Cloud execution is not enabled.",
                "handoff_reason": "Cloud route selected but Qwen Cloud execution is not enabled.",
                "worker_result_status": "not_attempted",
                "failure_type": "safety_handoff",
                "failure_stage": "router",
            }

        try:
            cloud_backend = create_backend(
                backend_type="qwen",
                model=default_config.get_qwen_model(),
                base_url=default_config.get_qwen_base_url(),
                api_key=default_config.get_qwen_api_key(),
            )
        except ValueError as exc:
            return {
                "status": "handoff_required",
                "source": "router",
                "reason": f"Cloud route selected but Qwen Cloud is not configured: {exc}",
                "handoff_reason": f"Cloud route selected but Qwen Cloud is not configured: {exc}",
                "worker_result_status": "not_attempted",
                "failure_type": "backend_unavailable",
                "failure_stage": "router",
            }

        cloud_engine = TriageEngine(backend=cloud_backend, timeout_seconds=timeout)
        result = cloud_engine.execute_task(
            task_prompt=task_prompt,
            raw_data=raw_data,
            validator=validator,
            timeout=timeout,
            post_processor=post_processor,
        )
        result["source"] = "cloud"
        return result

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
            internet_ok=default_config.get_qwen_enabled(),
            cloud_primary_available=default_config.get_qwen_enabled(),
            cloud_secondary_available=False,
            cloud_credit_state="ok" if default_config.get_qwen_enabled() else "none",
            lm_studio_ok=True,
            local_heavy_available=True,
            local_fast_available=True,
            deterministic_tool_available=validator is not None,
            required_checks=["validator"] if validator is not None else [],
        )
