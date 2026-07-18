import re
from typing import Dict, Any, List, Literal
from dataclasses import dataclass, field

class TaskClassifier:
    """Classifies prompts into task categories."""
    CATEGORIES = [
        "docs_update", "bugfix", "test_addition", "refactor", 
        "packaging", "security_review", "architecture_planning", "blocked_or_high_risk"
    ]

    @classmethod
    def classify(cls, prompt: str, backend=None) -> str:
        # If backend is not provided, try to create default (Ollama)
        if not backend:
            try:
                from .backends import create_backend
                from .config import default_config
                model = default_config.get_global("backend", "default_model", "qwen2.5-coder:7b-triagecore")
                backend = create_backend("ollama", model=model)
            except Exception:
                backend = None

        if backend:
            try:
                system_prompt = (
                    "You are the TriageCore Router.\n"
                    "Your ONLY job is to classify the user's task prompt into exactly one of the categories below.\n\n"
                    "Categories:\n"
                    "- docs_update: Update/add/fix docs, readmes, guides.\n"
                    "- bugfix: Fix errors, crashes, exceptions, bugs.\n"
                    "- test_addition: Add tests, fixtures, unit tests.\n"
                    "- refactor: Restructure, rewrite, clean, format code.\n"
                    "- packaging: setup.py, pyproject.toml, package requirements, build.\n"
                    "- security_review: Vulnerabilities, secrets, secure code paths.\n"
                    "- architecture_planning: Design systems, architecture docs, folder structures.\n"
                    "- blocked_or_high_risk: Destructive operations (delete, wipe, format all).\n\n"
                    "Rules:\n"
                    "1. Do NOT solve the task.\n"
                    "2. Do NOT explain your choice.\n"
                    "3. Output ONLY the exact category string from the list above. No other words, no markdown, no punctuation."
                )
                response = backend.generate(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0,
                    timeout=1.5  # short timeout to prevent UI freezes
                )
                if response and response.text:
                    cleaned = response.text.strip().lower().replace('"', '').replace("'", "").replace(".", "")
                    if cleaned in cls.CATEGORIES:
                        return cleaned
            except Exception:
                pass # Fall back to regex classifier

        return cls.classify_deterministic(prompt)

    @classmethod
    def classify_deterministic(cls, prompt: str) -> str:
        """Classify without constructing or calling a model backend."""
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


@dataclass
class DangerInfo:
    risk_level: Literal["low", "medium", "high"]
    recommended_profile: Literal["read-only", "workspace-write", "workspace-write-with-approval", "blocked"]
    reasons: List[str] = field(default_factory=list)
    risk_categories: List[str] = field(default_factory=list)


class DangerDetector:
    """Detects risky operations and recommends permission profiles."""
    
    DESTRUCTIVE_OPS = [r"rm\s+-rf", r"delete all", r"wipe"]
    SYSTEM_MODS = [r"sudo", r"/etc", r"\~/\.bashrc", r"\~/\.zshrc"]
    SECRETS_AUTH = [r"\.env", r"secret", r"password", r"token", r"auth", r"credentials"]
    PACKAGE_MGMT = [r"pip install", r"npm install", r"apt-get", r"poetry add"]
    DEPLOYMENT_CONFIG = [r"deploy", r"docker-compose", r"k8s", r"terraform", r"aws"]

    @classmethod
    def analyze(cls, prompt: str, target_files: List[str] = None) -> DangerInfo:
        target_files = target_files or []
        prompt_lower = prompt.lower()
        
        reasons = []
        categories = set()

        def check_patterns(patterns, category_name):
            for pattern in patterns:
                if re.search(pattern, prompt_lower):
                    reasons.append(f"Prompt contains {category_name} keyword: {pattern}")
                    categories.add(category_name)
                
                # Check target files for the same keywords where relevant
                for f in target_files:
                    if re.search(pattern, f.lower()):
                        reasons.append(f"Target file is sensitive ({category_name}): {f}")
                        categories.add(category_name)

        check_patterns(cls.DESTRUCTIVE_OPS, "destructive_ops")
        check_patterns(cls.SYSTEM_MODS, "system_modifications")
        check_patterns(cls.SECRETS_AUTH, "secrets_and_auth")
        check_patterns(cls.PACKAGE_MGMT, "package_management")
        check_patterns(cls.DEPLOYMENT_CONFIG, "deployment_config")

        categories_list = list(categories)

        if "destructive_ops" in categories or "system_modifications" in categories or "secrets_and_auth" in categories:
            return DangerInfo(
                risk_level="high",
                recommended_profile="blocked",
                reasons=reasons,
                risk_categories=categories_list
            )
            
        if "package_management" in categories or "deployment_config" in categories:
            return DangerInfo(
                risk_level="medium",
                recommended_profile="workspace-write-with-approval",
                reasons=reasons,
                risk_categories=categories_list
            )
        
        # Safe defaults
        if "read" in prompt_lower and "write" not in prompt_lower and "edit" not in prompt_lower:
            return DangerInfo(
                risk_level="low",
                recommended_profile="read-only",
                reasons=["No risky patterns detected. Task appears to be inspection only."],
                risk_categories=[]
            )
        
        return DangerInfo(
            risk_level="low",
            recommended_profile="workspace-write",
            reasons=["Standard code modification requested."],
            risk_categories=[]
        )
