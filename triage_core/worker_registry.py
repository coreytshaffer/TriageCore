import time
import json
from typing import Dict, Any, List, Optional
from .backends import create_backend, OpenAICompatibleBackend
from .work_orders import WorkOrder
from .config import default_config

class WorkerBase:
    def __init__(self, role: str, default_model: str = "qwen2.5-coder:7b", default_backend: str = "ollama"):
        self.role = role
        # Try to load config from work_rules.toml
        worker_cfg = default_config.get_worker_config(role)
        self.backend_type = worker_cfg.get("backend", default_backend)
        self.model = worker_cfg.get("model", default_model)
        self.backend: OpenAICompatibleBackend = create_backend(
            backend_type=self.backend_type, 
            model=self.model
        )

    def process(self, order: WorkOrder) -> Dict[str, Any]:
        prompt = self._build_prompt(order)
        
        start_time = time.time()
        try:
            # We enforce JSON mode if supported to return structured responses
            response = self.backend.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                timeout=order.max_seconds,
                response_format={"type": "json_object"} if self.backend_type in ["ollama", "vllm"] else None
            )
            elapsed = time.time() - start_time
            
            try:
                result_data = json.loads(response.text)
            except json.JSONDecodeError:
                result_data = {"raw_text": response.text}

            result_data["worker_id"] = self.role
            result_data["resource_usage"] = {
                "input_tokens_est": response.usage.get("prompt_tokens", 0),
                "output_tokens_est": response.usage.get("completion_tokens", 0),
                "duration_seconds": elapsed,
            }
            return result_data
            
        except Exception as e:
            elapsed = time.time() - start_time
            return {
                "worker_id": self.role,
                "error": str(e),
                "resource_usage": {
                    "duration_seconds": elapsed
                }
            }
            
    def _build_prompt(self, order: WorkOrder) -> str:
        raise NotImplementedError("Subclasses must implement _build_prompt")

class RepoMapperWorker(WorkerBase):
    def __init__(self):
        super().__init__("repo_mapper", default_model="qwen2.5-coder:7b")
        
    def _build_prompt(self, order: WorkOrder) -> str:
        return f"""You are the RepoMapper.
Analyze these input artifacts: {order.input_artifacts}
Provide a JSON summary answering this output requirement: {order.output_required}
Format: {{"summary": "...", "files_identified": []}}"""

class TestStubberWorker(WorkerBase):
    def __init__(self):
        super().__init__("test_stubber", default_model="qwen2.5-coder:7b")

    def _build_prompt(self, order: WorkOrder) -> str:
        return f"""You are the TestStubber.
Input context: {order.input_artifacts}
Output requirement: {order.output_required}
Draft Python pytest stubs.
Format: {{"test_code": "...", "files_referenced": []}}"""

class ValidatorWorker(WorkerBase):
    def __init__(self):
        super().__init__("validator", default_model="qwen2.5-coder:7b")

    def _build_prompt(self, order: WorkOrder) -> str:
        return f"""You are the Validator.
Input context: {order.input_artifacts}
Verify if the code fulfills the requirement: {order.output_required}
Format: {{"is_valid": true/false, "issues_found": ["..."]}}"""

class WorkerRegistry:
    def __init__(self):
        self.workers = {
            "repo_mapper": RepoMapperWorker(),
            "test_stubber": TestStubberWorker(),
            "validator": ValidatorWorker()
        }

    def get_worker(self, role: str) -> Optional[WorkerBase]:
        return self.workers.get(role)
