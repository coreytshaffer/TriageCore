from typing import Callable, Dict, Any, Optional
from .engine import TriageEngine

class TriageClient:
    def __init__(self, local_url: str = "http://127.0.0.1:1234", cloud_model: str = "claude-3-5-sonnet-latest", timeout_seconds: int = 90):
        """
        Initializes the TriageClient which manages local/cloud task delegation.
        
        Args:
            local_url: The base URL of the local API server (e.g., LM Studio, Ollama).
            cloud_model: The flagship cloud model to escalate to if local fails.
                         Accepts any LiteLLM-compatible model string (e.g., 'gpt-4o', 'gemini/gemini-1.5-pro').
            timeout_seconds: The strict temporal budget for local generation.
        """
        self.engine = TriageEngine(local_url=local_url, cloud_model=cloud_model, timeout_seconds=timeout_seconds)

    def run_task(self, prompt: str, data: str, validator: Optional[Callable[[str], bool]] = None) -> Dict[str, Any]:
        """
        Runs a given prompt and data through the hybrid execution engine.
        It first routes to the local worker and watches the clock.
        If it times out or fails validation, it escalates to the cloud supervisor.
        """
        return self.engine.execute_task(task_prompt=prompt, raw_data=data, validator=validator)
