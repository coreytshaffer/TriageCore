from typing import Callable, Dict, Any, Optional
from .engine import TriageEngine
from .routers import TriageRouter
from .backends import LocalBackend, create_backend

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

    def run_task(self, prompt: str, data: str, validator: Optional[Callable[[str], bool]] = None) -> Dict[str, Any]:
        """
        Runs a given prompt and data through the execution engine.
        First, it classifies and routes the request.
        If it's safe to run locally, it attempts execution.
        If execution fails, times out, or the router blocks it, it creates a structured handoff.
        """
        # Step 1: Routing logic
        route_decision = self.router.should_offload(prompt, data)
        if route_decision.get("offload_recommended", False):
            reason = f"Router bypass: {route_decision.get('reason')}"
            return {
                "status": "handoff_required",
                "source": "router",
                "reason": reason,
                "handoff_reason": reason,
                "backend_name": getattr(self.engine.backend, "name", None),
                "model": getattr(self.engine.backend, "model", None),
                "timeout_seconds": self.engine.timeout,
            }
            
        # Step 2: Local execution
        return self.engine.execute_task(task_prompt=prompt, raw_data=data, validator=validator)
