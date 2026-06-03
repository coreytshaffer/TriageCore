import time
import requests
from typing import Callable, Dict, Any, Optional

class TriageEngine:
    def __init__(self, local_url: str, local_model: str, timeout_seconds: int = 45):
        self.local_url = local_url.rstrip('/')
        self.local_model = local_model
        self.timeout = timeout_seconds

    def execute_task(self, task_prompt: str, raw_data: str, validator: Optional[Callable[[str], bool]] = None) -> Dict[str, Any]:
        """
        Attempts to execute a parsing or generation task on the local worker.
        Triggers a handoff if a timeout or validation failure occurs.
        """
        start_time = time.time()
        try:
            payload = {
                "model": self.local_model,
                "messages": [
                    {"role": "system", "content": "You are a rigid parsing worker. Output ONLY raw code or markdown requested. No chat."},
                    {"role": "user", "content": f"{task_prompt}\n\nDATA:\n{raw_data}"}
                ],
                "temperature": 0.1
            }
            
            # Send post request with strict temporal budget
            response = requests.post(
                f"{self.local_url}/v1/chat/completions", 
                json=payload, 
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                choices = data.get('choices', [])
                if not choices:
                    return self._trigger_handoff(task_prompt, raw_data, "Local worker returned unexpected JSON schema (no choices).")
                
                message = choices[0].get('message', {})
                output = message.get('content')
                if output is None:
                    return self._trigger_handoff(task_prompt, raw_data, "Local worker returned unexpected JSON schema (no content).")
                    
                elapsed = time.time() - start_time
                
                # Run quality gates if provided
                if validator and not validator(output):
                    return self._trigger_handoff(task_prompt, raw_data, "Local output failed quality gate validation.")
                
                return {"status": "success", "source": "local", "elapsed_seconds": elapsed, "output": output}
            else:
                return self._trigger_handoff(task_prompt, raw_data, f"Local worker returned status {response.status_code}.")

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
