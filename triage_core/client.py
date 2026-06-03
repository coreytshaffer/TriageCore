from typing import Callable, Dict, Any, Optional
from .engine import TriageEngine
from .routers import TriageRouter

class TriageClient:
    def __init__(self, local_url: str = "http://127.0.0.1:1234", local_model: str = "local-model", timeout_seconds: int = 45):
        """
        Initializes the TriageClient which manages local execution and handoff routing.
        
        Args:
            local_url: The base URL of the local API server (e.g., LM Studio, Ollama).
            local_model: The model string expected by the local server.
            timeout_seconds: The strict temporal budget for local generation.
        """
        self.engine = TriageEngine(local_url=local_url, local_model=local_model, timeout_seconds=timeout_seconds)
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
            return {
                "status": "handoff_required",
                "source": "router",
                "reason": f"Router bypass: {route_decision.get('reason')}"
            }
            
        # Step 2: Local execution
        return self.engine.execute_task(task_prompt=prompt, raw_data=data, validator=validator)
