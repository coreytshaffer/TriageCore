import json
import tempfile
import py_compile
import os
import re

class PythonSyntaxValidator:
    """
    Quality gate that verifies the syntax of generated Python code
    before allowing it to be returned as a success.
    """
    
    @staticmethod
    def validate(code_output: str) -> bool:
        """
        Takes raw Python code, writes it to a secure temporary file,
        and uses native py_compile to check for syntax errors without executing it.
        Returns True if syntax is valid, False otherwise.
        """
        # Clean up markdown code blocks
        code_output = re.sub(r'^```[a-zA-Z]*\s*', '', code_output)
        code_output = re.sub(r'\s*```$', '', code_output)
        code_output = code_output.strip()
        
        # Write to a secure temp file
        fd, path = tempfile.mkstemp(suffix=".py")
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                f.write(code_output)
            # The file is closed automatically by the 'with' block context manager, 
            # which closes the underlying file descriptor.
            
            # Attempt to compile safely without open handles
            py_compile.compile(path, doraise=True)
            return True
            
        except py_compile.PyCompileError as e:
            print(f"[Validator] Syntax error detected: {e}")
            return False
        finally:
            os.remove(path)


class MonitoringJsonValidator:
    """Validator for the Study 001 monitoring-site extraction fixture."""

    REQUIRED_KEYS = {
        "site_id",
        "date",
        "temperature_c",
        "turbidity_ntu",
    }

    @staticmethod
    def validate(output: str) -> bool:
        cleaned = _strip_markdown_fence(output)
        try:
            payload = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            print(f"[Validator] JSON parse error detected: {exc}")
            return False

        if not isinstance(payload, dict):
            print("[Validator] Expected a JSON object.")
            return False

        missing_keys = MonitoringJsonValidator.REQUIRED_KEYS - set(payload)
        if missing_keys:
            print(f"[Validator] Missing JSON keys: {sorted(missing_keys)}")
            return False

        return (
            str(payload["site_id"]) == "CLW-07"
            and str(payload["date"]) == "2026-06-03"
            and _same_number(payload["temperature_c"], 21.4)
            and _same_number(payload["turbidity_ntu"], 8.7)
        )


class ErrorWarningMarkdownValidator:
    """Validator for concise warning/error-only log summaries."""

    @staticmethod
    def validate(output: str) -> bool:
        cleaned = _strip_markdown_fence(output)
        normalized = cleaned.lower()
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]

        if not lines:
            print("[Validator] Empty log summary.")
            return False
        if "info" in normalized or "service started" in normalized or "sync complete" in normalized:
            print("[Validator] Log summary included INFO-only content.")
            return False
        if "warn" not in normalized or "latency spike" not in normalized:
            print("[Validator] Log summary missed the warning signal.")
            return False
        if "error" not in normalized or "connection timeout" not in normalized:
            print("[Validator] Log summary missed the error signal.")
            return False

        return all(line.startswith(("-", "*")) for line in lines)


def _strip_markdown_fence(output: str) -> str:
    output = re.sub(r'^```[a-zA-Z]*\s*', '', output.strip())
    output = re.sub(r'\s*```$', '', output)
    return output.strip()


def _same_number(value: object, expected: float) -> bool:
    try:
        return abs(float(value) - expected) < 0.001
    except (TypeError, ValueError):
        return False
