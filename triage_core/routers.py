from typing import Dict, Any
from .classifier import DangerDetector

class TriageRouter:
    """Routes tasks between local execution or hands them off."""
    
    def should_offload(self, prompt: str, data: str) -> Dict[str, Any]:
        danger_info = DangerDetector.analyze(prompt)
        
        if danger_info["risk_level"] in ["medium", "high"]:
            return {
                "offload_recommended": True,
                "reason": f"Risk level {danger_info['risk_level']} detected. {danger_info['reasons']}"
            }
            
        # Optional: Add context length check to offload massive files
        if len(data) > 30000:
            return {
                "offload_recommended": True,
                "reason": "Context exceeds local execution window (30k chars). Handoff required."
            }
            
        return {
            "offload_recommended": False
        }
