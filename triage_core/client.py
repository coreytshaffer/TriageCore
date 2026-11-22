from collections.abc import Mapping
from dataclasses import dataclass
from functools import wraps
from threading import RLock
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional
from .engine import TriageEngine
from .routers import TriageRouter
from .backends import (
    LocalBackend, OllamaBackend, OpenAICompatibleBackend, QwenCloudBackend,
    create_backend, create_bound_backend,
)
from .destination_policy import (
    DestinationPolicyError, GuardedTransport, RouteBinding, SendRecord,
    bind_route_endpoints,
)
from .runtime_observation import GovernedBindingError
from .routing import (
    ResilienceRouteDecision,
    ResilienceRouteInput,
    SPECIALIST_OFFLOAD_EVENT_TYPE,
    build_route_decision_payload,
    build_specialist_offload_payload,
    build_worker_result_payload,
    choose_resilience_route,
)
from .agent_identity import AgentIdentityRegistry
from .task_ledger import TaskLedger
from .privacy_scanner import scan_task_packet, PrivacyViolationError
from .config import default_config
from .routing.route_events import GovernedEvidencePayloadError

if TYPE_CHECKING:
    from .run_plan import GovernedRunContext

# CR-DD-012B: the two execution *parameters* the governed path still needs from
# specialist routing, expressed as pure functions of the classification the
# governed decision already carries. Both are read straight out of
# ``SpecialistRouter.route_task``'s own category tables; neither depends on the
# live ``is_internet_available()`` probe or on any offload verdict, so consuming
# them here invokes no second policy decision.
#
# ``routers.py`` is outside this slice's file allowlist, so the category bindings
# are restated rather than imported -- the post-processor *function* is imported,
# only the binding is restated.
# ``tests/test_governed_consumption_parity.py`` asserts these agree with
# ``route_task`` for every category the deterministic classifier can emit.
_GOVERNED_TIMEOUT_SECONDS = {
    "bugfix": 30,
    "test_addition": 30,
    "refactor": 30,
    "docs_update": 120,
    "architecture_planning": 120,
}
_GOVERNED_POST_PROCESSED = frozenset({"docs_update", "architecture_planning"})
_GOVERNED_DEFAULT_TIMEOUT_SECONDS = 45


def _governed_execution_parameters(classification: str):
    """Return ``(timeout_seconds, post_processor)`` for a governed run.

    These are execution parameters, not policy: they cannot change the route,
    the envelope, the privacy posture, or whether the attempt proceeds. The
    timeout returned here is exactly the ``specialist_timeout_forecast_seconds``
    the preview published, so the budget a reviewer read is the budget the
    worker gets.
    """
    from .routers import extract_first_code_block

    return (
        _GOVERNED_TIMEOUT_SECONDS.get(
            classification, _GOVERNED_DEFAULT_TIMEOUT_SECONDS
        ),
        extract_first_code_block if classification in _GOVERNED_POST_PROCESSED else None,
    )


class GovernedDestinationRefusal(GovernedBindingError):
    """Bounded evidence for the permitted sends preceding a terminal refusal."""

    def __init__(
        self,
        refusal: DestinationPolicyError,
        sends: tuple[SendRecord, ...] = (),
        identity_sha256: str | None = None,
    ):
        self.code = refusal.code
        self.sends = sends
        self.identity_sha256 = identity_sha256
        details = " ".join(
            f"{send.route}/{send.safe_label} {send.method} {send.suffix}" for send in sends
        )
        identity = f" identity_sha256={identity_sha256}" if identity_sha256 is not None else ""
        super().__init__(f"{refusal}{identity} send_count={len(sends)} {details}".rstrip())


_PROTOCOL_CLASSES = {
    "ollama": OllamaBackend,
    "openai_compatible": OpenAICompatibleBackend,
    "qwen": QwenCloudBackend,
}


@dataclass(frozen=True)
class VerifiedDestination:
    binding: RouteBinding
    backend: LocalBackend
    transport: GuardedTransport
    initial_send_count: int

    def check_before_invoke(self, backend: LocalBackend) -> None:
        if (
            backend is not self.backend
            or type(backend) is not _PROTOCOL_CLASSES[self.binding.protocol]
        ):
            raise DestinationPolicyError("destination_binding_mismatch", self.binding.safe_label)
        if (
            getattr(backend, "transport", None) is not self.transport
            or self.transport.owner is not backend
        ):
            raise DestinationPolicyError("transport_not_guarded", self.binding.safe_label)
        # Only the provider backend may attach a configured bearer credential.
        if self.binding.protocol == "openai_compatible" and backend.api_key not in (
            None, "", "not-needed"
        ):
            raise DestinationPolicyError("destination_binding_mismatch", self.binding.safe_label)
        self.transport.verify_integrity()

    def execute_task(self, **kwargs):
        """Keep the engine, the checked owner and its transport local to this call."""
        engine = TriageEngine(backend=self.backend, timeout_seconds=kwargs["timeout"])
        try:
            self.check_before_invoke(engine.backend)
            result = engine.execute_task(**kwargs)
        except DestinationPolicyError as exc:
            sends = self.transport.sends[self.initial_send_count:]
            raise GovernedDestinationRefusal(exc, sends, self.binding.identity_sha256) from None
        if len(self.transport.sends) > self.initial_send_count:
            result["destination_safe_label"] = self.binding.safe_label
            result["destination_identity_sha256"] = self.binding.identity_sha256
        return result


def verify_destination_binding(
    context: "GovernedRunContext", backends: Mapping[str, LocalBackend]
) -> Mapping[str, VerifiedDestination]:
    """Verify all network members before observing which one can run."""
    from .run_plan import configuration_digest

    config = context.effective_config
    policy = context.decision.policy
    routes = (policy.preferred_logical_route, *policy.permitted_fallback_envelope)
    try:
        expected = bind_route_endpoints(routes, config)
        digest = configuration_digest(
            cloud_backend_enabled=config.cloud_enabled.value,
            cloud_model_binding=config.cloud_model.value if config.cloud_enabled.value else "not_enabled",
            local_backend_type=config.backend_type.value,
            endpoint_bindings=expected,
            transport_policy=context.transport_policy,
        )
        if expected != context.endpoint_bindings or digest != policy.configuration_sha256:
            raise DestinationPolicyError("destination_binding_mismatch")
        if set(backends) != {binding.route for binding in expected}:
            raise DestinationPolicyError("transport_not_guarded")

        verified = {}
        for binding in expected:
            backend = backends[binding.route]
            guard = getattr(backend, "transport", None)
            if type(guard) is not GuardedTransport:
                raise DestinationPolicyError("transport_not_guarded", binding.safe_label)
            if guard.route != binding.route or guard.bound_identity_sha256 != binding.identity_sha256:
                raise DestinationPolicyError("destination_binding_mismatch", binding.safe_label)
            if guard.transport_policy_sha256 != context.transport_policy.sha256:
                raise DestinationPolicyError("transport_settings_changed", binding.safe_label)
            member = VerifiedDestination(binding, backend, guard, len(guard.sends))
            member.check_before_invoke(backend)
            if binding.protocol == "qwen" and backend.api_key != (context.qwen_api_key or ""):
                raise DestinationPolicyError("destination_binding_mismatch", binding.safe_label)
            verified[binding.route] = member
        return MappingProxyType(verified)
    except DestinationPolicyError as exc:
        raise GovernedDestinationRefusal(exc) from None


def _serialize_governed_attempt(method):
    @wraps(method)
    def run(self, *args, **kwargs):
        # The CLI builds a fresh client per invocation. If another caller reuses
        # one, isolate its model selection and per-attempt send counters.
        if self._governed_lock is None:
            return method(self, *args, **kwargs)
        with self._governed_lock:
            return method(self, *args, **kwargs)

    return run


class TriageClient:
    def __init__(
        self,
        backend_type: str = "ollama",
        model: str = "local-model",
        base_url: Optional[str] = None,
        backend: Optional[LocalBackend] = None,
        timeout_seconds: int = 45,
        *,
        governed_context=None,
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
        self._governed_context = governed_context
        self._governed_lock = RLock() if governed_context is not None else None
        backends = {}
        if governed_context is not None:
            config = governed_context.effective_config
            for binding in governed_context.endpoint_bindings:
                backends[binding.route] = create_bound_backend(
                    binding,
                    config,
                    api_key=governed_context.qwen_api_key if binding.protocol == "qwen" else None,
                    transport_policy=governed_context.transport_policy,
                )
            # A terminal decision can have no network member.
            backend = next(iter(backends.values()), None)
            timeout_seconds = config.timeout_seconds.value
        elif backend is None:
            backend = create_backend(backend_type=backend_type, model=model, base_url=base_url)
            
        self._governed_backends = MappingProxyType(backends)
        self.engine = TriageEngine(backend=backend, timeout_seconds=timeout_seconds)
        self.router = TriageRouter()

    @classmethod
    def from_governed_context(cls, context):
        """Build a fresh client for one attempt, with independent guarded transports."""
        return cls(governed_context=context)

    @_serialize_governed_attempt
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
        capability: Optional[Any] = None,
        snapshot: Optional[Any] = None,
        decision: Optional[Any] = None,
        governed_context: "GovernedRunContext | None" = None,
    ) -> Dict[str, Any]:
        """
        Runs a given prompt and data through the execution engine.
        First, it classifies and routes the request.
        If it's safe to run locally, it attempts execution.
        If execution fails, times out, or the router blocks it, it creates a structured handoff.

        CR-DD-012B. ``snapshot`` and ``decision`` are a new optional pair. When
        absent -- every existing library caller -- behavior is preserved
        unchanged and no decision is constructed on the caller's behalf. When
        supplied together, as ``tc run`` and ``tc run --plan`` always do, policy
        comes from the completed governed decision instead of from in-method
        computation: classification and the logical route are *consumed*, never
        re-derived, and execution reads the exact snapshot bytes rather than the
        caller's own assembly.

        A caller who supplies a decision therefore gets different behavior from
        one who does not. That is the point of the slice, not an accident, and
        the compatibility claim is narrow: existing callers are unaffected
        because they pass nothing, not because the two paths are equivalent.
        """
        from .runtime_observation import (
            GovernedBindingError,
            observe_route_binding,
            validate_envelope_compliance,
        )
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

        if governed_context is None:
            governed_context = self._governed_context
        # The credential is deliberately absent from decision IDs. An equal ID
        # cannot authorize consumption with another attempt's captured key.
        if self._governed_context is not None and governed_context is not self._governed_context:
            raise GovernedDestinationRefusal(DestinationPolicyError("destination_binding_mismatch"))
        governed = decision is not None or snapshot is not None or governed_context is not None
        decision_id = None
        if governed:
            # Fail closed before any backend construction or invocation. A stale
            # or inconsistent decision terminates the attempt; it is never
            # transparently rebuilt. Termination is not repair.
            verified_destinations = self._verify_governed_inputs(
                snapshot=snapshot,
                decision=decision,
                verified_packet=verified_packet,
                is_local_only=is_local_only,
                context=governed_context,
                backends=self._governed_backends,
            )
            decision_id = decision.decision_id
            config = governed_context.effective_config

        # Step 1: Routing logic
        if governed:
            # Policy is consumed, never re-derived. The specialist-policy
            # selector is not invoked at all on this path: its offload verdict
            # is a second policy decision, and two of its three offload branches
            # turn on a live ``is_internet_available()`` probe -- a volatile
            # observation, which under CR-DD-012B Resolved Question 1 may decide
            # whether an authorized plan can execute now but never what route or
            # policy the task receives. Its third branch, high risk, the governed
            # decision already expresses as a preferred ``human_handoff``.
            #
            # Only its two execution *parameters* are still needed, and both are
            # pure functions of the classification the decision already carries.
            category = decision.policy.classification
            route_decision = {}
            use_timeout, post_processor_override = _governed_execution_parameters(
                category
            )
        else:
            category = TaskClassifier.classify(prompt)
            route_decision = self.router.specialist.route_task(category, prompt, data)
            use_timeout = route_decision.get("timeout", self.engine.timeout)
            post_processor_override = None
        resilience_input = self._build_resilience_route_input(
            category=category, validator=validator, capability=capability,
            cloud_enabled=config.cloud_enabled.value if governed else None,
        )

        if is_local_only:
            resilience_input.privacy_level = "local_only"

        governed_evidence = None
        if governed:
            # Runtime binding is a filter over the decision's closed, ordered
            # envelope -- never a selection over the space of backends. The
            # router is not consulted again; capability constrains binding only.
            observation = observe_route_binding(
                decision=decision,
                capability=capability,
                cloud_enabled=config.cloud_enabled.value,
                local_backend_type=config.backend_type.value,
                cloud_model=config.cloud_model.value,
            )
            validate_envelope_compliance(observation, decision)
            if observation.binding_outcome == "closed":
                raise GovernedBindingError(
                    "No authorized binding exists for the governed envelope. "
                    "Failing closed."
                )
            resilience_decision = ResilienceRouteDecision(
                selected_route=observation.selected_route,
                reason=decision.policy.route_reason_codes[0],
                fallback_depth=observation.envelope_position,
                human_review_required=decision.policy.human_review == "required",
                required_checks=list(decision.policy.required_checks),
            )
            selected_route = observation.selected_route
            selected_model = observation.model_binding
            governed_evidence = {
                "governed_risk_posture": decision.policy.risk_posture,
                "binding_outcome": observation.binding_outcome,
                "binding_reason_codes": list(observation.reason_codes),
            }
            # Evidence uses the same high-risk override as the construction seam.
            # No router consumes this input again on the governed path.
            if decision.policy.risk_posture == "high":
                resilience_input.sensitivity = "high"
        else:
            resilience_decision = choose_resilience_route(resilience_input)
            selected_route = resilience_decision.selected_route
            if selected_route in {"cloud_primary", "cloud_secondary"}:
                selected_model = default_config.get_qwen_model()
            elif selected_route in {"local_fast", "local_heavy"}:
                selected_model = (
                    route_decision.get("model")
                    if capability is None
                    else capability.model_for_route(selected_route)
                ) or ""
            else:
                selected_model = ""
        selected_backend_name = observation.backend_binding if governed else self._selected_backend_name(selected_route)

        # A governed decision whose *preferred* route is ``human_handoff``
        # because the ethical firewall triggered is a terminal governed outcome,
        # not an unavailable route. It must reach the handoff branch below and
        # return ``handoff_required`` with a ``worker_result`` record, rather
        # than being caught by the local-only guard as a fail-closed error
        # (CR-125). A ``human_handoff`` reached as an envelope *fallback* is the
        # opposite case -- the authorized route could not bind -- and stays
        # fail-closed.
        governed_terminal_handoff = (
            governed
            and observation.binding_outcome == "primary"
            and selected_route == "human_handoff"
            and decision.policy.ethical_firewall == "triggered"
        )

        # Ensure local-only packets only use explicitly local routes
        if is_local_only and not governed_terminal_handoff:
            if selected_route not in ["local_heavy", "local_fast", "deterministic"]:
                audit = RouteDecisionAudit(task_id, privacy_level, True, True, selected_route, selected_backend_name, "blocked", "ambiguous_or_remote_route")
                self._append_optional_event(ledger, task_id, "route_audit", audit.to_dict())
                try:
                    blocked_route_payload = build_route_decision_payload(
                        resilience_input,
                        resilience_decision,
                        selected_backend=selected_backend_name,
                        selected_model=selected_model,
                        decision_id=decision_id,
                        governed_evidence=governed_evidence,
                    )
                except GovernedEvidencePayloadError as exc:
                    if not governed:
                        raise
                    raise GovernedBindingError(exc.reason_code) from exc
                self._append_route_decision_event(
                    ledger=ledger,
                    task_id=task_id,
                    payload=blocked_route_payload,
                    signing_registry=route_decision_signing_registry,
                    signing_agent_id=route_decision_signing_agent_id,
                )
                raise LocalRouteUnavailableError(f"Local backend unavailable or route '{selected_route}' is not proven local-safe for local-only packet. Failing closed.")
            if route_decision.get("offload_recommended", False):
                audit = RouteDecisionAudit(task_id, privacy_level, True, True, selected_route, selected_backend_name, "blocked", "offload_recommended_for_local_only")
                self._append_optional_event(ledger, task_id, "route_audit", audit.to_dict())
                # CR-DD-018: persist the specialist decision's bounded structured cause
                # from this same route_task result -- never re-derived, never parsed
                # from the free-form reason. No try/except: an evidence-persistence
                # failure must propagate rather than be masked as a routing block.
                self._append_optional_event(
                    ledger,
                    task_id,
                    SPECIALIST_OFFLOAD_EVENT_TYPE,
                    build_specialist_offload_payload(route_decision),
                )
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
        try:
            route_payload = build_route_decision_payload(
                resilience_input,
                resilience_decision,
                selected_backend=selected_backend_name,
                selected_model=selected_model,
                decision_id=decision_id,
                governed_evidence=governed_evidence,
            )
        except GovernedEvidencePayloadError as exc:
            if not governed:
                raise
            raise GovernedBindingError(exc.reason_code) from exc
        self._append_route_decision_event(
            ledger=ledger,
            task_id=task_id,
            payload=route_payload,
            signing_registry=route_decision_signing_registry,
            signing_agent_id=route_decision_signing_agent_id,
        )

        # The ethical firewall, terminal escalation, and human-review posture are
        # first-class fields of the governed decision. On the governed path they
        # are *consumed* from it. ``ProjectSteward`` is not asked to decide
        # again: a second verdict that could stop a run the canonical decision
        # permitted, or permit one it stopped, would mean the decision was never
        # authoritative. The seam performs the single evaluation.
        if governed:
            steward_insufficient = decision.policy.ethical_firewall == "triggered"
            steward_eval = {
                "reason": "ethical_firewall_requires_human_review",
                "firewall_triggered": steward_insufficient,
            }
        else:
            steward = ProjectSteward()
            steward_eval = steward.evaluate(
                task_prompt=prompt, target_files=[], completed_orders=[]
            )
            steward_insufficient = steward_eval["local_result_status"] == "insufficient"
        if steward_insufficient:
            result = {
                "status": "handoff_required",
                "source": "steward",
                "reason": steward_eval["reason"],
                "handoff_reason": steward_eval["reason"],
                "backend_name": selected_backend_name if governed else getattr(self.engine.backend, "name", None),
                "model": selected_model if governed else getattr(self.engine.backend, "model", None),
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
                "backend_name": selected_backend_name if governed else getattr(self.engine.backend, "name", None),
                "model": selected_model if governed else getattr(self.engine.backend, "model", None),
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
                verified_destination=verified_destinations[selected_route] if governed else None,
                post_processor=(
                    post_processor_override
                    if governed
                    else route_decision.get("post_processor")
                ),
            )
            self._append_optional_event(
                ledger=ledger,
                task_id=task_id,
                event_type="worker_result",
                payload=build_worker_result_payload(route_payload, result),
            )
            return self._merge_route_fields(result, route_payload)
            
        # Step 2: Local execution
        post_processor = (
            post_processor_override if governed else route_decision.get("post_processor")
        )
        requested_model = selected_model

        if capability is not None and not requested_model:
            result = {
                "status": "handoff_required",
                "source": "router",
                "reason": "Selected local route has no resolved model binding.",
                "handoff_reason": "Selected local route has no resolved model binding.",
                "worker_result_status": "not_attempted",
                "failure_type": "backend_unavailable",
                "failure_stage": "router",
            }
            self._append_optional_event(
                ledger=ledger,
                task_id=task_id,
                event_type="worker_result",
                payload=build_worker_result_payload(route_payload, result),
            )
            return self._merge_route_fields(result, route_payload)
        
        executor = verified_destinations[selected_route] if governed else self.engine
        backend = executor.backend
        original_model = backend.model
        if getattr(backend, "name", "") != "fake" and requested_model and requested_model != original_model:
            backend.model = requested_model
            
        try:
            result = executor.execute_task(
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
            backend.model = original_model

    @staticmethod
    def _binding_primitive(value: Any) -> Any:
        """Field-name-keyed view of a binding, comparable across its two spellings.

        ``governed_run_snapshot`` and ``governed_decision`` each declare their own
        ``SnapshotDecisionBinding`` -- deliberately, so the decision owns a copy
        rather than an alias. They therefore never compare equal by identity or
        by dataclass equality, and their field *order* differs. Comparing by
        field name is what lets execution check it received the exact snapshot
        the decision governs.
        """
        from dataclasses import fields, is_dataclass

        if is_dataclass(value):
            return {
                item.name: TriageClient._binding_primitive(getattr(value, item.name))
                for item in fields(value)
            }
        if isinstance(value, tuple):
            return tuple(TriageClient._binding_primitive(item) for item in value)
        return value

    @staticmethod
    def _verify_governed_inputs(
        *,
        snapshot: Any,
        decision: Any,
        verified_packet: Any,
        is_local_only: bool,
        context,
        backends,
    ) -> Mapping[str, VerifiedDestination]:
        """Fail closed on any governed-consumption inconsistency.

        Every condition here terminates the attempt before backend construction
        or invocation, with no backend call and no privacy-unsafe ledger write.
        Termination is not repair: the attempt ends, and a new invocation may
        produce a new snapshot and decision. Nothing below revalidates-and-repairs.

        Staleness is binding-defined, not clock-defined -- it is determined by
        the immutable snapshot binding and decision-relevant facts, never by
        elapsed wall time, current file contents, or backend health.
        """
        from .governed_decision import (
            GovernedDecision,
            GovernedDecisionError,
            parse_governed_decision,
            serialize_governed_decision,
            verify_governed_decision_id,
        )
        from .governed_run_snapshot import GovernedRunInputSnapshot, sha256_digest
        from .runtime_observation import GovernedBindingError

        if type(snapshot) is not GovernedRunInputSnapshot:
            raise GovernedBindingError(
                "a governed run requires the immutable snapshot its decision binds"
            )
        if type(decision) is not GovernedDecision:
            raise GovernedBindingError("a governed run requires a governed decision")

        # One canonical round trip rejects a malformed, noncanonical,
        # unsupported-version, missing-field, or unknown-field decision, and
        # independently re-derives the content-linkage ID.
        try:
            canonical = serialize_governed_decision(decision)
            reparsed = parse_governed_decision(canonical)
        except GovernedDecisionError as exc:
            raise GovernedBindingError(
                f"governed decision failed canonical validation: {exc}"
            ) from exc
        if reparsed.decision_id != decision.decision_id or not verify_governed_decision_id(
            decision
        ):
            raise GovernedBindingError("decision_id does not match the decision body")

        binding = decision.snapshot_binding
        if TriageClient._binding_primitive(
            snapshot.to_decision_binding()
        ) != TriageClient._binding_primitive(binding):
            raise GovernedBindingError(
                "execution received a snapshot other than the one governed"
            )

        for value, expected, label in (
            (snapshot.instruction_bytes, binding.instruction, "instruction"),
            (snapshot.inline_input_bytes, binding.inline_input, "inline input"),
            (snapshot.task_data_bytes, binding.task_data, "task data"),
            (
                snapshot.assembled_execution_bytes,
                binding.assembled_execution,
                "assembled execution",
            ),
        ):
            if len(value) != expected.byte_length or sha256_digest(value) != expected.sha256:
                raise GovernedBindingError(f"{label} digest or length mismatch")

        # Execution consumes exact snapshot bytes. A packet assembled from
        # anything else is a second assembly site, which is the drift this
        # slice exists to remove.
        if verified_packet.prompt != snapshot.instruction_bytes.decode("utf-8"):
            raise GovernedBindingError("packet instruction is not the snapshot's")
        if verified_packet.data != snapshot.task_data_bytes.decode("utf-8"):
            raise GovernedBindingError("packet task data is not the snapshot's")

        policy = decision.policy
        egress_eligible = (
            policy.privacy_preflight == "passed"
            and binding.declared_privacy != "local_only"
        )
        decision_allows_cloud = egress_eligible and binding.cloud_intent == "requested"
        if is_local_only != (not decision_allows_cloud):
            raise GovernedBindingError(
                "runtime privacy posture disagrees with the governed decision"
            )

        routes = (policy.preferred_logical_route, *policy.permitted_fallback_envelope)
        if not policy.preferred_logical_route:
            raise GovernedBindingError("governed decision names no logical route")
        if len(set(routes)) != len(routes):
            raise GovernedBindingError("governed envelope repeats a logical route")
        if not egress_eligible and any(
            route in {"cloud_primary", "cloud_secondary"} for route in routes
        ):
            raise GovernedBindingError("cloud route present outside the egress envelope")

        review_required = (
            policy.risk_posture == "high"
            or policy.privacy_preflight != "passed"
            or policy.ethical_firewall == "triggered"
            or policy.preferred_logical_route == "human_handoff"
            or policy.terminal_escalation != "none"
        )
        if review_required and policy.human_review != "required":
            raise GovernedBindingError("human-review posture is inconsistent")

        if context is None or context.decision.decision_id != decision.decision_id:
            raise GovernedDestinationRefusal(DestinationPolicyError("destination_binding_mismatch"))
        return verify_destination_binding(context, backends)

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
        merged["selected_backend"] = route_payload.get("selected_backend", "")
        merged["selected_model"] = route_payload.get("selected_model", "")
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
        verified_destination: VerifiedDestination | None = None,
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

        if verified_destination is None and not default_config.get_qwen_enabled():
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
            if verified_destination is not None:
                cloud_backend = verified_destination.backend
                if not cloud_backend.api_key:
                    raise ValueError("qwen backend requires api_key")
            else:
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

        executor = verified_destination or TriageEngine(backend=cloud_backend, timeout_seconds=timeout)
        result = executor.execute_task(
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
        capability: Optional[Any] = None,
        cloud_enabled: bool | None = None,
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
        # CR-DD-013: when a capability resolution is supplied (the ``tc run``
        # path always supplies one), local availability comes from observation
        # or an explicit declaration -- never from an unobserved literal. When
        # it is absent, direct callers of ``run_task`` keep the previous
        # behavior unchanged.
        if capability is None:
            lm_studio_ok = True
            local_heavy_available = True
            local_fast_available = True
        else:
            lm_studio_ok = capability.lm_studio_ok
            local_heavy_available = capability.local_heavy_available
            local_fast_available = capability.local_fast_available

        if cloud_enabled is None:
            cloud_enabled = default_config.get_qwen_enabled()
        return ResilienceRouteInput(
            task_class=task_class_map.get(category, "general"),
            complexity=complexity_map.get(category, "medium"),
            sensitivity=sensitivity_map.get(category, "low"),
            privacy_level="local_ok",
            internet_ok=cloud_enabled,
            cloud_primary_available=cloud_enabled,
            cloud_secondary_available=False,
            cloud_credit_state="ok" if cloud_enabled else "none",
            lm_studio_ok=lm_studio_ok,
            local_heavy_available=local_heavy_available,
            local_fast_available=local_fast_available,
            deterministic_tool_available=validator is not None,
            required_checks=["validator"] if validator is not None else [],
            capability_evidence=capability,
        )
