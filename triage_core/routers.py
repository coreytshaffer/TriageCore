import re
import socket
from typing import Dict, Any, Optional, Callable
from .classifier import DangerDetector, TaskClassifier

def is_internet_available(host="8.8.8.8", port=53, timeout=1.0) -> bool:
    """Fast check to see if an internet connection is available."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
            return True
    except OSError:
        return False

def extract_first_code_block(text: str) -> str:
    """Post-processor that extracts the content of the first markdown code fence (e.g. ```python ... ```)."""
    text = text.strip()
    match = re.search(r'```(?:python|json|markdown|txt|text)?\s*([\s\S]*?)```', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text

def strip_code_fences(text: str) -> str:
    """Post-processor that strips markdown code fences while keeping surrounding text."""
    return re.sub(r'```(?:[a-zA-Z0-9_]+)?\n?|\n?```', '', text).strip()

class SpecialistRouter:
    """Routes tasks based on classified category to the appropriate model, timeout, and post-processor."""
    
    def route_task(self, category: str, prompt: str, data: str) -> Dict[str, Any]:
        """
        Determines the routing details for a classified category.
        Returns:
            A dict containing:
            - "offload_recommended": bool
            - "reason": str (if offload is recommended)
            - "timeout": int
            - "post_processor": Optional[Callable[[str], str]]
            - "model": Optional[str]
            - "offline_fallback": bool
        """
        danger_info = DangerDetector.analyze(prompt)
        internet_up = is_internet_available()
        
        # High risk or explicit safety handoffs are always blocked/offloaded for safety
        if danger_info.risk_level == "high" or category == "safety_handoff":
            return {
                "offload_recommended": True,
                "reason": f"Risk level {danger_info.risk_level} detected. Category: {category}. {'; '.join(danger_info.reasons)}",
                "offline_fallback": False
            }
            
        # Medium risk tasks: offload if online, fall back to local if offline
        if danger_info.risk_level == "medium":
            if internet_up:
                return {
                    "offload_recommended": True,
                    "reason": f"Risk level medium detected. Category: {category}. {'; '.join(danger_info.reasons)}",
                    "offline_fallback": False
                }
            
            import logging
            logging.getLogger(__name__).warning("Internet offline. Falling back to local execution for medium risk task.")
            return {
                "offload_recommended": False,
                "reason": f"Risk level medium offline fallback. Category: {category}. {'; '.join(danger_info.reasons)}",
                "timeout": 45,
                "post_processor": None,
                "model": "qwen2.5-coder-7b-instruct",
                "offline_fallback": True
            }
        
        # Large context: offload if online, fall back to local if offline
        if len(data) > 30000:
            if internet_up:
                return {
                    "offload_recommended": True,
                    "reason": "Context exceeds local execution window (30k chars). Handoff required.",
                    "offline_fallback": False
                }
            else:
                import logging
                logging.getLogger(__name__).warning("Internet offline. Falling back to local execution for large context.")
            
        # Routing rules based on Study 002 accepted proposals
        if category in ["python_generation", "python_repair", "bugfix", "test_addition", "refactor"]:
            return {
                "offload_recommended": False,
                "timeout": 30,
                "post_processor": None,
                "model": "qwen2.5-coder-7b-instruct",
                "offline_fallback": not internet_up
            }
        elif category in ["structured_extraction", "log_summary", "docs_update", "architecture_planning"]:
            return {
                "offload_recommended": False,
                "timeout": 120,
                "post_processor": extract_first_code_block,
                "model": "deepseek/deepseek-r1-0528-qwen3-8b",
                "offline_fallback": not internet_up
            }
            
        return {
            "offload_recommended": False,
            "timeout": 45,
            "post_processor": None,
            "model": "qwen2.5-coder-7b-instruct",
            "offline_fallback": not internet_up
        }

class TriageRouter:
    """Routes tasks between local execution or hands them off."""
    def __init__(self):
        self.specialist = SpecialistRouter()
        
    def should_offload(self, prompt: str, data: str) -> Dict[str, Any]:
        """Determines if a task should bypass local entirely based on size or risk."""
        category = TaskClassifier.classify(prompt)
        return self.specialist.route_task(category, prompt, data)

