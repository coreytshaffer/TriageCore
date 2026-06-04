import time
import requests
from typing import Callable, Dict, Any, Optional
from .backends import LocalBackend

class TriageEngine:
    def __init__(self, backend: LocalBackend, timeout_seconds: int = 45):
        self.backend = backend
        self.timeout = timeout_seconds

    def execute_task(self, task_prompt: str, raw_data: str, validator: Optional[Callable[[str], bool]] = None) -> Dict[str, Any]:
        """
        Attempts to execute a parsing or generation task on the local worker.
        Triggers a handoff if a timeout or validation failure occurs.
        """
        start_time = time.time()
        try:
            messages = [
                {"role": "system", "content": "You are a rigid parsing worker. Output ONLY raw code or markdown requested. No chat."},
                {"role": "user", "content": f"{task_prompt}\n\nDATA:\n{raw_data}"}
            ]
            
            backend_response = self.backend.generate(
                messages=messages,
                temperature=0.1,
                timeout=self.timeout
            )
            
            elapsed = time.time() - start_time
            
            # Run quality gates if provided
            if validator and not validator(backend_response.text):
                return self._trigger_handoff(task_prompt, raw_data, "Local output failed quality gate validation.")
            
            return {
                "status": "success", 
                "source": "local", 
                "elapsed_seconds": elapsed, 
                "output": backend_response.text,
                "backend_name": backend_response.backend_name,
                "usage": backend_response.usage,
                "timings": backend_response.timings
            }

        except requests.exceptions.Timeout:
            # Handle the temporal budget exhaustion
            return self._trigger_handoff(task_prompt, raw_data, f"Local worker exceeded temporal budget of {self.timeout}s.")
        except Exception as e:
            return self._trigger_handoff(task_prompt, raw_data, f"Local runtime error: {str(e)}")

    def _trigger_handoff(self, prompt: str, data: str, reason: str) -> Dict[str, Any]:
        """Triggers a handoff to manual or agentic systems when local fails."""
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"[!] Triggering handoff: {reason}")
        
        return {
            "status": "handoff_required",
            "source": "local_engine",
            "reason": reason
        }
