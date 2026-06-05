from dataclasses import dataclass, field
from typing import Any, List
from .validators import PythonSyntaxValidator, MonitoringJsonValidator, ErrorWarningMarkdownValidator

@dataclass
class ValidationResult:
    passed: bool
    validator: str
    issues: List[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ValidatorTools:
    @staticmethod
    def infer_validators(target_files: List[str]) -> List[str]:
        validators = set()

        if any(path.endswith(".py") for path in target_files):
            validators.add("python_syntax")

        if any(path.endswith(".json") for path in target_files):
            validators.add("json_parse")

        if any(path.endswith((".md", ".markdown")) for path in target_files):
            validators.add("markdown_basic")

        return sorted(validators)

    @staticmethod
    def run(validators: List[str], text: str, target_files: List[str]) -> List[ValidationResult]:
        results = []
        for v in validators:
            if v == "python_syntax":
                passed = PythonSyntaxValidator.validate(text)
                results.append(ValidationResult(
                    passed=passed,
                    validator=v,
                    issues=[] if passed else ["PythonSyntaxValidator failed. Expected valid python code."]
                ))
            elif v == "json_parse":
                passed = MonitoringJsonValidator.validate(text)
                results.append(ValidationResult(
                    passed=passed,
                    validator=v,
                    issues=[] if passed else ["MonitoringJsonValidator failed. Expected specific JSON schema."]
                ))
            elif v == "markdown_basic":
                passed = ErrorWarningMarkdownValidator.validate(text)
                results.append(ValidationResult(
                    passed=passed,
                    validator=v,
                    issues=[] if passed else ["ErrorWarningMarkdownValidator failed. Ensure markdown contains required sections."]
                ))
            else:
                # unknown validator - maybe log it, but for now we ignore or pass
                results.append(ValidationResult(
                    passed=True,
                    validator=v,
                    issues=[f"Unknown validator '{v}' - skipping."]
                ))
        return results
