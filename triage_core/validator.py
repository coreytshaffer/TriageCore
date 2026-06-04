import re
import os
from typing import List, Dict, Any
from dataclasses import dataclass, field
from .task_ledger import TaskRecord

@dataclass
class ValidationResult:
    passed: bool
    violations: List[str] = field(default_factory=list)

class SafetyValidator:
    """Scans generated or modified code against the task's safety profile."""
    
    NETWORK_IMPORTS = [r"import\s+requests", r"from\s+requests", r"import\s+urllib", r"import\s+socket", r"import\s+http"]
    OS_IMPORTS = [r"import\s+subprocess", r"from\s+subprocess", r"os\.system", r"os\.popen"]
    
    @classmethod
    def audit(cls, task: TaskRecord, modified_files: List[str]) -> ValidationResult:
        violations = []
        
        # 1. Scope Validation
        if task.target_files:
            for mod_file in modified_files:
                if mod_file not in task.target_files:
                    violations.append(f"Scope Violation: Modified file '{mod_file}' was not in the original target_files list ({task.target_files}).")
        
        # 2. Profile Validation
        profile = task.permission_profile
        
        # If the task was blocked, any modification is a violation
        if profile == "blocked" and modified_files:
            violations.append(f"Profile Violation: Task was marked 'blocked' but files were modified: {modified_files}")
            
        # Static analysis on the modified files
        for filepath in modified_files:
            if not os.path.exists(filepath):
                continue # Skip deleted files or invalid paths
                
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                    
                # If read-only, why are we here? Oh wait, read-only means no writes.
                if profile == "read-only":
                    violations.append(f"Profile Violation: Task was 'read-only' but '{filepath}' was modified.")
                    
                # Check for network escalations if the original risk didn't warrant it
                # For simplicity, we just flag them if the risk was low
                if task.risk_level == "low":
                    for pattern in cls.NETWORK_IMPORTS:
                        if re.search(pattern, content):
                            violations.append(f"Safety Violation: Detected network import '{pattern}' in '{filepath}' on a low-risk task.")
                    for pattern in cls.OS_IMPORTS:
                        if re.search(pattern, content):
                            violations.append(f"Safety Violation: Detected OS execution import '{pattern}' in '{filepath}' on a low-risk task.")
                            
            except Exception as e:
                violations.append(f"Audit Error: Could not read '{filepath}': {str(e)}")
                
        return ValidationResult(passed=len(violations) == 0, violations=violations)
