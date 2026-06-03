import re
from typing import Dict, Any

class TaskClassifier:
    """Classifies prompts into task categories."""
    CATEGORIES = [
        "docs_update", "bugfix", "test_addition", "refactor", 
        "packaging", "security_review", "architecture_planning", "blocked_or_high_risk"
    ]

    @classmethod
    def classify(cls, prompt: str) -> str:
        prompt_lower = prompt.lower()
        if any(word in prompt_lower for word in ["delete", "remove all", "wipe", "format"]):
            return "blocked_or_high_risk"
        if "test" in prompt_lower or "pytest" in prompt_lower:
            return "test_addition"
        if "doc" in prompt_lower or "readme" in prompt_lower:
            return "docs_update"
        if "bug" in prompt_lower or "fix" in prompt_lower or "error" in prompt_lower:
            return "bugfix"
        if "refactor" in prompt_lower or "rewrite" in prompt_lower:
            return "refactor"
        if "security" in prompt_lower or "vulnerability" in prompt_lower:
            return "security_review"
        if "design" in prompt_lower or "architecture" in prompt_lower:
            return "architecture_planning"
        return "refactor" # default fallback


class DangerDetector:
    """Detects risky operations and recommends permission profiles."""
    
    RISKY_PATTERNS = [
        r"rm\s+-rf", r"\.env", r"secret", r"password", r"auth", r"token", 
        r"deploy", r"\.bashrc", r"\.zshrc", r"sudo", r"install"
    ]

    @classmethod
    def analyze(cls, prompt: str, target_files: list[str] = None) -> Dict[str, str]:
        target_files = target_files or []
        prompt_lower = prompt.lower()
        
        reasons = []
        for pattern in cls.RISKY_PATTERNS:
            if re.search(pattern, prompt_lower):
                reasons.append(f"Prompt contains risky keyword: {pattern}")
        
        for f in target_files:
            if ".env" in f or "secret" in f or "auth" in f:
                reasons.append(f"Target file is sensitive: {f}")

        if len(reasons) > 1 or "sudo" in prompt_lower or "rm -rf" in prompt_lower:
            return {
                "risk_level": "high",
                "recommended_profile": "blocked",
                "reasons": "; ".join(reasons)
            }
        elif len(reasons) == 1:
            return {
                "risk_level": "medium",
                "recommended_profile": "workspace-write-with-approval",
                "reasons": "; ".join(reasons)
            }
        
        # Safe default
        if "read" in prompt_lower and "write" not in prompt_lower and "edit" not in prompt_lower:
            return {
                "risk_level": "low",
                "recommended_profile": "read-only",
                "reasons": "No risky patterns detected. Task appears to be inspection only."
            }
        
        return {
            "risk_level": "low",
            "recommended_profile": "workspace-write",
            "reasons": "Standard code modification requested."
        }
