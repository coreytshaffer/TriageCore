import time
import json
from typing import Dict, Any, List, Optional, Callable
from .backends import create_backend, OpenAICompatibleBackend
from .work_orders import WorkOrder
from .config import default_config

class WorkerBase:
    def __init__(self, role: str, default_model: str = "qwen2.5-coder:7b-triagecore", default_backend: str = "ollama"):
        self.role = role
        # Try to load config from work_rules.toml
        worker_cfg = default_config.get_worker_config(role)
        self.backend_type = worker_cfg.get("backend", default_backend)
        global_default_model = default_config.get_global("backend", "default_model", default_model)
        self.model = worker_cfg.get("model", global_default_model)
        self.backend: OpenAICompatibleBackend = create_backend(
            backend_type=self.backend_type, 
            model=self.model
        )
        # Check if the specific backend is online, else fallback to global default
        try:
            if not self.backend.ping():
                global_backend_type = default_config.get_global("backend", "default_type", "ollama")
                global_model = default_config.get_global("backend", "default_model", "qwen2.5-coder:7b-triagecore")
                if self.backend_type != global_backend_type or self.model != global_model:
                    fallback_backend = create_backend(backend_type=global_backend_type, model=global_model)
                    if fallback_backend.ping():
                        self.backend_type = global_backend_type
                        self.model = global_model
                        self.backend = fallback_backend
        except Exception:
            pass

    def _load_skill_prompt(self, skill_name: str) -> str:
        import os
        current_dir = os.path.dirname(os.path.abspath(__file__))
        skill_path = os.path.join(current_dir, "skills", f"{skill_name}.md")
        if os.path.exists(skill_path):
            try:
                with open(skill_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
        return ""

    def process(self, order: WorkOrder, stream_callback: Optional[Callable[[str], None]] = None) -> Dict[str, Any]:
        prompt = self._build_prompt(order)
        
        start_time = time.time()
        try:
            # We enforce JSON mode if supported to return structured responses
            response = self.backend.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                timeout=order.max_seconds,
                response_format={"type": "json_object"} if self.backend_type in ["ollama", "vllm"] else None,
                stream_callback=stream_callback
            )
            elapsed = time.time() - start_time
            
            import re
            text = response.text or ""
            match = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
            if match:
                text = match.group(1).strip()
            
            try:
                result_data = json.loads(text)
            except (json.JSONDecodeError, TypeError):
                result_data = {"raw_text": text}

            in_tokens = response.usage.get("prompt_tokens", 0)
            out_tokens = response.usage.get("completion_tokens", 0)
            
            result_data["worker_id"] = self.role
            result_data["resource_usage"] = {
                "input_tokens_est": in_tokens,
                "output_tokens_est": out_tokens,
                "duration_seconds": elapsed,
                "energy_estimated": (in_tokens + out_tokens) * 0.005,
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
            
    def _resolve_artifacts(
        self,
        input_artifacts: List[str],
        chunk_start: int = 0,
        chunk_end: Optional[int] = None,
    ) -> str:
        """Resolve file paths to content, honouring chunk boundaries for large files."""
        import os
        from .config import default_config

        max_bytes: int = default_config.global_config.get("budgets", {}).get(
            "max_artifact_bytes", 12000
        )
        resolved = []
        for art in input_artifacts:
            if isinstance(art, str) and len(art) < 500 and os.path.isfile(art):
                try:
                    with open(art, "r", encoding="utf-8") as f:
                        all_lines = f.readlines()
                    total_lines = len(all_lines)

                    if chunk_end is not None or chunk_start > 0:
                        # Explicit chunk boundaries supplied by the orchestrator
                        end = chunk_end if chunk_end is not None else total_lines
                        lines = all_lines[chunk_start:end]
                        label = (
                            f" [chunk lines {chunk_start + 1}–{min(end, total_lines)}"
                            f" of {total_lines}]"
                        )
                        resolved.append(
                            f"### File: {art}{label}\n```python\n{''.join(lines)}\n```"
                        )
                    else:
                        content = "".join(all_lines)
                        if len(content.encode("utf-8")) <= max_bytes:
                            # Small enough — send the whole file
                            resolved.append(
                                f"### File: {art}\n```python\n{content}\n```"
                            )
                        else:
                            # Auto-truncate to fit max_artifact_bytes
                            truncated = ""
                            cut_line = total_lines
                            for i, line in enumerate(all_lines):
                                if len((truncated + line).encode("utf-8")) > max_bytes:
                                    cut_line = i
                                    break
                                truncated += line
                            label = (
                                f" [EXCERPT lines 1–{cut_line} of {total_lines};"
                                f" {total_lines - cut_line} lines follow in later chunks]"
                            )
                            resolved.append(
                                f"### File: {art}{label}\n```python\n{truncated}\n```"
                            )
                except Exception as e:
                    resolved.append(
                        f"### File path: {art} (Failed to read content: {e})"
                    )
            else:
                resolved.append(str(art))
        return "\n\n".join(resolved)

    def _build_prompt(self, order: WorkOrder) -> str:
        raise NotImplementedError("Subclasses must implement _build_prompt")

class ContextPlannerWorker(WorkerBase):
    def __init__(self):
        super().__init__("context_planner", default_model="qwen2.5-coder:7b")
        
    def _build_prompt(self, order: WorkOrder) -> str:
        template = self._load_skill_prompt(self.role)
        if not template:
            template = """You are the ContextPlanner.
Analyze these input artifacts: {input_artifacts}
Provide a JSON summary answering this output requirement: {output_required}
Format: {{"summary": "...", "files_identified": []}}"""
        return template.format(
            input_artifacts=self._resolve_artifacts(
                order.input_artifacts, order.chunk_start, order.chunk_end
            ),
            output_required=order.output_required,
        )

class TestStubberWorker(WorkerBase):
    def __init__(self):
        super().__init__("test_stubber", default_model="qwen2.5-coder:7b")

    def _build_prompt(self, order: WorkOrder) -> str:
        template = self._load_skill_prompt(self.role)
        if not template:
            template = """You are the TestStubber.
Input context: {input_artifacts}
Output requirement: {output_required}
Draft Python pytest stubs.
Format: {{"test_code": "...", "files_referenced": []}}"""
        return template.format(
            input_artifacts=self._resolve_artifacts(
                order.input_artifacts, order.chunk_start, order.chunk_end
            ),
            output_required=order.output_required,
        )

class LLMReviewWorker(WorkerBase):
    def __init__(self):
        super().__init__("review_worker", default_model="qwen2.5-coder:7b")

    def _build_prompt(self, order: WorkOrder) -> str:
        template = self._load_skill_prompt(self.role)
        if not template:
            template = """You are the LLMReviewWorker.
Input context: {input_artifacts}
Critique the quality, completeness, and risks of the implementation: {output_required}
Format: {{"is_valid": true/false, "issues_found": ["..."]}}"""
        return template.format(
            input_artifacts=self._resolve_artifacts(
                order.input_artifacts, order.chunk_start, order.chunk_end
            ),
            output_required=order.output_required,
        )

class ImplementerWorker(WorkerBase):
    def __init__(self):
        super().__init__("implementer", default_model="qwen2.5-coder:7b")

    def _build_prompt(self, order: WorkOrder) -> str:
        template = self._load_skill_prompt(self.role)
        if not template:
            template = """You are the ImplementerWorker.
Input context: {input_artifacts}
Task requirement: {output_required}
Provide the fully repaired and hardened code based on the context and requirements.
Format: {{"repaired_code": "..."}}"""
        return template.format(
            input_artifacts=self._resolve_artifacts(
                order.input_artifacts, order.chunk_start, order.chunk_end
            ),
            output_required=order.output_required,
        )

class WorkerRegistry:
    def __init__(self):
        self.workers = {
            "context_planner": ContextPlannerWorker(),
            "test_stubber": TestStubberWorker(),
            "review_worker": LLMReviewWorker(),
            "implementer": ImplementerWorker()
        }

    def get_worker(self, role: str) -> Optional[WorkerBase]:
        return self.workers.get(role)
