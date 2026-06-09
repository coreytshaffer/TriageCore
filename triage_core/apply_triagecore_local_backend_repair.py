# Apply TriageCore local backend repair.
#
# Run from the root of your local TriageCore repo:
#
#   python apply_triagecore_local_backend_repair.py
#   pytest tests/test_backends.py
#   triagecore desk
#
# This script keeps backups beside the replaced files using a .bak suffix.

from pathlib import Path


BACKENDS_PY = r"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Callable
import json
import os

import requests


_AUTO_MODEL_SENTINELS = {"", "auto", "loaded-model", "local-model"}


@dataclass
class BackendResponse:
    text: str
    raw: Dict[str, Any]
    usage: Dict[str, Any] = field(default_factory=dict)
    timings: Dict[str, Any] = field(default_factory=dict)
    backend_name: str = "unknown"


class LocalBackend(Protocol):
    name: str
    base_url: str
    model: str

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        timeout: int = 45,
        stream_callback: Optional[Callable[[str], None]] = None,
        **kwargs: Any,
    ) -> BackendResponse:
        ...

    def ping(self, timeout: float = 1.0) -> bool:
        ...


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _model_id_from_openai_models(data: Dict[str, Any]) -> Optional[str]:
    models = data.get("data") or []
    if not models:
        return None
    first = models[0]
    if isinstance(first, dict):
        return first.get("id") or first.get("model") or first.get("name")
    if isinstance(first, str):
        return first
    return None


def _lmstudio_base_url() -> str:
    return os.getenv("TRIAGE_SUPERVISOR_BASE_URL", "http://localhost:1234/v1")


def _lmstudio_is_online(timeout: float = 0.5) -> bool:
    url = f"{_lmstudio_base_url().rstrip('/')}/models"
    try:
        response = requests.get(url, timeout=timeout)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def _prefer_lmstudio_supervisor() -> bool:
    return _env_flag("TRIAGE_PREFER_LMSTUDIO_SUPERVISOR", True)


@dataclass
class OpenAICompatibleBackend:
    name: str
    base_url: str
    model: str = "auto"
    api_key: str = "not-needed"

    def resolve_model(self, timeout: float = 1.0) -> str:
        if self.model and self.model not in _AUTO_MODEL_SENTINELS:
            return self.model

        url = f"{self.base_url.rstrip('/')}/models"
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            resolved = _model_id_from_openai_models(response.json())
            if resolved:
                self.model = resolved
                return resolved
        except requests.exceptions.RequestException:
            pass
        except ValueError:
            pass

        self.model = self.model or "auto"
        return self.model

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        timeout: int = 45,
        stream_callback: Optional[Callable[[str], None]] = None,
        **kwargs: Any,
    ) -> BackendResponse:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.resolve_model(timeout=min(float(timeout), 2.0)),
            "messages": messages,
            "temperature": temperature,
            **kwargs,
        }

        if stream_callback:
            payload["stream"] = True
            response = requests.post(url, json=payload, timeout=timeout, stream=True)
            response.raise_for_status()

            text_parts = []
            final_usage = {}
            for line in response.iter_lines():
                if line:
                    decoded = line.decode("utf-8")
                    if decoded.startswith("data: "):
                        data_str = decoded[6:].strip()
                        if data_str == "[DONE]":
                            break
                        if not data_str:
                            continue
                        try:
                            chunk = json.loads(data_str)
                            if "usage" in chunk and chunk["usage"]:
                                final_usage = chunk["usage"]
                            choices = chunk.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                content = delta.get("content", "")
                                if content:
                                    text_parts.append(content)
                                    stream_callback(content)
                        except Exception:
                            pass

            text = "".join(text_parts)
            data = {"usage": final_usage}
            return BackendResponse(
                text=text,
                raw=data,
                usage=final_usage,
                backend_name=self.name,
            )

        response = requests.post(url, json=payload, timeout=timeout)
        if not response.ok:
            print(f"Backend Error Output: {response.text}")
        response.raise_for_status()

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("Backend returned no choices.")

        message = choices[0].get("message", {})
        text = message.get("content")
        if text is None:
            raise ValueError("Backend returned no message content.")

        return BackendResponse(
            text=text,
            raw=data,
            usage=data.get("usage", {}),
            timings=data.get("timings", {}),
            backend_name=self.name,
        )

    def ping(self, timeout: float = 1.0) -> bool:
        url = f"{self.base_url.rstrip('/')}/models"
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200 and self.model in _AUTO_MODEL_SENTINELS:
                try:
                    resolved = _model_id_from_openai_models(response.json())
                    if resolved:
                        self.model = resolved
                except ValueError:
                    pass
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False


@dataclass
class OllamaBackend:
    name: str = "ollama"
    base_url: str = "http://localhost:11434"
    model: str = "auto"

    def resolve_model(self, timeout: float = 1.0) -> str:
        if self.model and self.model not in _AUTO_MODEL_SENTINELS:
            return self.model

        url = f"{self.base_url.rstrip('/')}/api/tags"
        try:
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            models = response.json().get("models") or []
            if models:
                first = models[0]
                if isinstance(first, dict):
                    resolved = first.get("name") or first.get("model")
                else:
                    resolved = str(first)
                if resolved:
                    self.model = resolved
                    return resolved
        except requests.exceptions.RequestException:
            pass
        except ValueError:
            pass

        self.model = self.model or "auto"
        return self.model

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        timeout: int = 45,
        stream_callback: Optional[Callable[[str], None]] = None,
        **kwargs: Any,
    ) -> BackendResponse:
        url = f"{self.base_url.rstrip('/')}/api/chat"
        payload = {
            "model": self.resolve_model(timeout=min(float(timeout), 2.0)),
            "messages": messages,
            "stream": bool(stream_callback),
            "options": {"temperature": temperature},
        }
        payload.update(kwargs)

        if stream_callback:
            response = requests.post(url, json=payload, timeout=timeout, stream=True)
            response.raise_for_status()
            text_parts: List[str] = []
            final_raw: Dict[str, Any] = {}
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line.decode("utf-8"))
                except ValueError:
                    continue
                final_raw = chunk
                message = chunk.get("message") or {}
                content = message.get("content", "")
                if content:
                    text_parts.append(content)
                    stream_callback(content)
                if chunk.get("done"):
                    break
            text = "".join(text_parts)
            return BackendResponse(
                text=text,
                raw=final_raw,
                usage=_ollama_usage(final_raw),
                timings=final_raw,
                backend_name=self.name,
            )

        response = requests.post(url, json=payload, timeout=timeout)
        if not response.ok:
            print(f"Backend Error Output: {response.text}")
        response.raise_for_status()
        data = response.json()
        message = data.get("message") or {}
        text = message.get("content")
        if text is None:
            raise ValueError("Ollama backend returned no message content.")

        return BackendResponse(
            text=text,
            raw=data,
            usage=_ollama_usage(data),
            timings=data,
            backend_name=self.name,
        )

    def ping(self, timeout: float = 1.0) -> bool:
        # When LM Studio is online, make the existing TriageDesk probe order pick
        # LM Studio as the control-plane/supervisor instead of Ollama.
        if _prefer_lmstudio_supervisor() and _lmstudio_is_online(timeout=min(timeout, 0.5)):
            return False

        url = f"{self.base_url.rstrip('/')}/api/tags"
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200 and self.model in _AUTO_MODEL_SENTINELS:
                try:
                    models = response.json().get("models") or []
                    if models:
                        first = models[0]
                        if isinstance(first, dict):
                            self.model = first.get("name") or first.get("model") or self.model
                except ValueError:
                    pass
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False


def _ollama_usage(data: Dict[str, Any]) -> Dict[str, Any]:
    prompt_tokens = data.get("prompt_eval_count", 0) or 0
    completion_tokens = data.get("eval_count", 0) or 0
    total_tokens = prompt_tokens + completion_tokens
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def create_backend(
    backend_type: str = "ollama",
    model: str = "auto",
    base_url: Optional[str] = None,
) -> LocalBackend:
    normalized_type = (backend_type or "ollama").lower()

    if normalized_type == "ollama":
        return OllamaBackend(
            base_url=base_url or os.getenv("TRIAGE_OLLAMA_BASE_URL", "http://localhost:11434"),
            model=model,
        )

    presets = {
        "lmstudio": {
            "name": "lmstudio",
            "base_url": os.getenv("TRIAGE_SUPERVISOR_BASE_URL", "http://localhost:1234/v1"),
        },
        "lm_studio": {
            "name": "lmstudio",
            "base_url": os.getenv("TRIAGE_SUPERVISOR_BASE_URL", "http://localhost:1234/v1"),
        },
        "vllm": {
            "name": "vllm",
            "base_url": "http://localhost:8000/v1",
        },
        "llama.cpp": {
            "name": "llama.cpp",
            "base_url": "http://localhost:8080/v1",
        },
        "llamacpp": {
            "name": "llama.cpp",
            "base_url": "http://localhost:8080/v1",
        },
        "custom": {
            "name": "custom",
            "base_url": base_url,
        },
    }

    if normalized_type not in presets:
        raise ValueError(f"Unknown backend_type: {backend_type}")

    selected = presets[normalized_type]
    resolved_base_url = base_url or selected["base_url"]

    if not resolved_base_url:
        raise ValueError("custom backend requires base_url")

    name = selected["name"]
    if name == "custom" and "1234" in resolved_base_url:
        name = "lmstudio"

    return OpenAICompatibleBackend(
        name=name,
        base_url=resolved_base_url,
        model=model,
    )
"""


CONFIG_PY = r"""
import os
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomli as tomllib
    except ImportError:
        tomllib = None


def load_toml(path: str) -> dict:
    if not tomllib or not os.path.exists(path):
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception as e:
        print(f"Warning: Failed to parse TOML file {path}: {e}")
        return {}


_BACKEND_ENV_OVERRIDES = {
    ("backend", "default_type"): "TRIAGE_BACKEND_TYPE",
    ("backend", "default_model"): "TRIAGE_MODEL",
    ("backend", "base_url"): "TRIAGE_BASE_URL",
    ("backend", "timeout_seconds"): "TRIAGE_TIMEOUT_SECONDS",
}


class Config:
    def __init__(self, root_dir: str = "."):
        self.global_config_path = os.path.join(root_dir, "triagecore.toml")
        self.work_rules_path = os.path.join(root_dir, ".triagecore", "work_rules.toml")

        self.global_config = load_toml(self.global_config_path)
        self.work_rules = load_toml(self.work_rules_path)

    def get_global(self, section: str, key: str, default=None):
        env_name = _BACKEND_ENV_OVERRIDES.get((section, key))
        if env_name and os.getenv(env_name) is not None:
            return os.getenv(env_name)
        if section == "backend" and key == "default_model":
            return self.global_config.get(section, {}).get(key, "auto")
        return self.global_config.get(section, {}).get(key, default)

    def get_rule(self, section: str, key: str, default=None):
        return self.work_rules.get(section, {}).get(key, default)

    def get_worker_config(self, worker_name: str) -> dict:
        return self.work_rules.get("workers", {}).get(worker_name, {})

    def get_backend_type(self) -> str:
        return os.getenv(
            "TRIAGE_BACKEND_TYPE",
            self.get_global("backend", "default_type", "lmstudio"),
        )

    def get_backend_model(self) -> str:
        return os.getenv(
            "TRIAGE_MODEL",
            self.get_global("backend", "default_model", "auto"),
        )

    def get_backend_base_url(self):
        return os.getenv(
            "TRIAGE_BASE_URL",
            self.get_global("backend", "base_url", None),
        )

    def get_ledger_dir(self) -> str:
        return self.get_global("paths", "ledger_dir", ".triagecore")

    def get_benchmarks_path(self) -> str:
        return self.get_global("paths", "benchmarks_path", "benchmarks/tasks.jsonl")

    def get_tasks_dir(self) -> str:
        return self.get_global("paths", "tasks_dir", ".agent_tasks")

    def get_codex_tasks_dir(self) -> str:
        return self.get_global("paths", "codex_tasks_dir", "triage_tasks")

    def get_report_path(self) -> str:
        return self.get_global("paths", "benchmark_report_path", "reports/benchmark-report.md")

    def get_timeout_seconds(self) -> int:
        return int(self.get_global("backend", "timeout_seconds", 30))

    def get_boundary_rules_path(self) -> str:
        return self.get_global("policies", "boundary_rules_path", "policies/cybernetic_ecology_boundary.yaml")


default_config = Config()
"""


TEST_BACKENDS_PY = r"""
import pytest
from unittest.mock import patch, Mock
from triage_core.backends import create_backend, OllamaBackend


def test_preset_urls():
    ollama = create_backend("ollama")
    assert isinstance(ollama, OllamaBackend)
    assert ollama.base_url == "http://localhost:11434"

    lmstudio = create_backend("lmstudio")
    assert lmstudio.base_url == "http://localhost:1234/v1"
    assert lmstudio.name == "lmstudio"

    vllm = create_backend("vllm")
    assert vllm.base_url == "http://localhost:8000/v1"

    llamacpp = create_backend("llama.cpp")
    assert llamacpp.base_url == "http://localhost:8080/v1"


def test_custom_backend_missing_url():
    with pytest.raises(ValueError, match="custom backend requires base_url"):
        create_backend("custom")


def test_unknown_backend():
    with pytest.raises(ValueError, match="Unknown backend_type: invalid"):
        create_backend("invalid")


@patch("triage_core.backends.requests.post")
def test_openai_backend_generate_success(mock_post):
    mock_resp = Mock()
    mock_resp.ok = True
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Hello World"}}],
        "usage": {"total_tokens": 10}
    }
    mock_post.return_value = mock_resp

    backend = create_backend("lmstudio", model="test-model")
    result = backend.generate([{"role": "user", "content": "hi"}])

    assert result.text == "Hello World"
    assert result.usage == {"total_tokens": 10}
    assert result.backend_name == "lmstudio"

    args, kwargs = mock_post.call_args
    assert args[0] == "http://localhost:1234/v1/chat/completions"
    assert kwargs["json"]["model"] == "test-model"


@patch("triage_core.backends.requests.post")
def test_ollama_backend_generate_uses_native_api(mock_post):
    mock_resp = Mock()
    mock_resp.ok = True
    mock_resp.json.return_value = {
        "message": {"content": "Hello from Ollama"},
        "prompt_eval_count": 3,
        "eval_count": 4,
    }
    mock_post.return_value = mock_resp

    backend = create_backend("ollama", model="qwen2.5-coder:7b")
    result = backend.generate([{"role": "user", "content": "hi"}])

    assert result.text == "Hello from Ollama"
    assert result.usage == {
        "prompt_tokens": 3,
        "completion_tokens": 4,
        "total_tokens": 7,
    }
    args, kwargs = mock_post.call_args
    assert args[0] == "http://localhost:11434/api/chat"
    assert kwargs["json"]["model"] == "qwen2.5-coder:7b"
    assert kwargs["json"]["stream"] is False


@patch("triage_core.backends.requests.get")
@patch("triage_core.backends.requests.post")
def test_lmstudio_auto_model_resolution(mock_post, mock_get):
    mock_get_resp = Mock()
    mock_get_resp.json.return_value = {
        "data": [{"id": "currently-loaded-lm-studio-model"}]
    }
    mock_get.return_value = mock_get_resp

    mock_post_resp = Mock()
    mock_post_resp.ok = True
    mock_post_resp.json.return_value = {
        "choices": [{"message": {"content": "auto ok"}}],
        "usage": {"total_tokens": 2},
    }
    mock_post.return_value = mock_post_resp

    backend = create_backend("lmstudio", model="auto")
    result = backend.generate([{"role": "user", "content": "hi"}])

    assert result.text == "auto ok"
    args, kwargs = mock_post.call_args
    assert args[0] == "http://localhost:1234/v1/chat/completions"
    assert kwargs["json"]["model"] == "currently-loaded-lm-studio-model"


@patch("triage_core.backends.requests.post")
def test_backend_generate_streaming_omits_stream_options(mock_post):
    mock_resp = Mock()
    mock_resp.iter_lines.return_value = [
        b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        b'data: {"choices":[{"delta":{"content":" World"}}],"usage":{"total_tokens":2}}',
        b"data: [DONE]",
    ]
    mock_post.return_value = mock_resp

    chunks = []
    backend = create_backend("custom", base_url="http://localhost:1234/v1")
    result = backend.generate(
        [{"role": "user", "content": "hi"}],
        stream_callback=chunks.append,
    )

    assert result.text == "Hello World"
    assert chunks == ["Hello", " World"]
    assert result.usage == {"total_tokens": 2}
    args, kwargs = mock_post.call_args
    assert args[0] == "http://localhost:1234/v1/chat/completions"
    assert kwargs["stream"] is True
    assert kwargs["json"]["stream"] is True
    assert "stream_options" not in kwargs["json"]


@patch("triage_core.backends.requests.post")
def test_backend_generate_no_choices(mock_post):
    mock_resp = Mock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"choices": []}
    mock_post.return_value = mock_resp

    backend = create_backend("vllm", model="test-model")
    with pytest.raises(ValueError, match="Backend returned no choices."):
        backend.generate([{"role": "user", "content": "hi"}])


@patch("triage_core.backends.requests.post")
def test_backend_generate_no_content(mock_post):
    mock_resp = Mock()
    mock_resp.ok = True
    mock_resp.json.return_value = {"choices": [{"message": {}}]}
    mock_post.return_value = mock_resp

    backend = create_backend("llama.cpp", model="test-model")
    with pytest.raises(ValueError, match="Backend returned no message content."):
        backend.generate([{"role": "user", "content": "hi"}])
"""


def write(path: str, text: str) -> None:
    target = Path(path)
    if target.exists():
        backup = target.with_suffix(target.suffix + ".bak")
        backup.write_text(target.read_text(encoding="utf-8"), encoding="utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text.lstrip(), encoding="utf-8")
    print(f"Wrote {target}")


def main() -> None:
    root = Path.cwd()
    if not (root / "triage_core").exists():
        raise SystemExit("Run this from the root of your local TriageCore repository.")

    write("triage_core/backends.py", BACKENDS_PY)
    write("triage_core/config.py", CONFIG_PY)
    write("tests/test_backends.py", TEST_BACKENDS_PY)

    print()
    print("Repair applied. Backups were written beside existing files with .bak suffix.")
    print()
    print("Next:")
    print("  pytest tests/test_backends.py")
    print("  $env:TRIAGE_BACKEND_TYPE='lmstudio'")
    print("  $env:TRIAGE_MODEL='auto'")
    print("  $env:TRIAGE_SUPERVISOR_BASE_URL='http://localhost:1234/v1'")
    print("  triagecore desk")


if __name__ == "__main__":
    main()
