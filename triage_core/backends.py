from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol, Callable, NoReturn
import json
import os
import urllib.parse

import requests

from .destination_policy import (
    DEFAULT_TRANSPORT_POLICY,
    DestinationPolicyError,
    EffectiveBackendConfiguration,
    GOVERNED_LOCAL_PRESETS,
    GuardedTransport,
    RouteBinding,
    TransportPolicy,
    backend_protocol_key,
)


_AUTO_MODEL_SENTINELS = {"", "auto", "loaded-model", "local-model"}


class BackendUnavailableError(Exception):
    """Raised when a local backend is offline, unreachable, or times out."""
    pass



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

    def get_sanitized_uri(self) -> str:
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
    return os.getenv("TRIAGE_SUPERVISOR_BASE_URL", "http://127.0.0.1:1234/v1")


def _lmstudio_is_online(base_url: str, transport: Any, timeout: float) -> bool:
    url = f"{base_url.rstrip('/')}/models"
    try:
        response = transport.get(url, timeout=timeout)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def _prefer_lmstudio_supervisor() -> bool:
    return _env_flag("TRIAGE_PREFER_LMSTUDIO_SUPERVISOR", True)


def _backend_error_summary(response: requests.Response, transport: Any) -> str:
    if isinstance(transport, GuardedTransport):
        return f"status_code={response.status_code}"
    reason = response.reason or "HTTP error"
    return f"status_code={response.status_code} reason={reason}"


def _raise_backend_unavailable(
    kind: str, transport: Any, url: str, error: requests.RequestException,
) -> NoReturn:
    if isinstance(transport, GuardedTransport):
        # HTTP exceptions can contain the full URL and a peer-supplied reason.
        raise BackendUnavailableError(f"{kind} backend unavailable on {transport.route}") from None
    raise BackendUnavailableError(f"{kind} backend unavailable at {url}: {error}") from error


def _generation_model(backend: Any, transport: Any, timeout: int) -> str:
    discovery_timeout = min(float(timeout), 2.0)
    if isinstance(transport, GuardedTransport):
        return backend._resolve_model(transport, discovery_timeout)
    # Direct backends may override the public resolver.
    return backend.resolve_model(timeout=discovery_timeout)


@dataclass
class OpenAICompatibleBackend:
    name: str
    base_url: str
    model: str = "auto"
    api_key: str = field(default="not-needed", repr=False)
    transport: Any = field(default=requests, repr=False, compare=False)

    def get_sanitized_uri(self) -> str:
        parsed = urllib.parse.urlparse(self.base_url)
        return f"{parsed.scheme}://{parsed.hostname}" + (f":{parsed.port}" if parsed.port else "") + parsed.path

    def _request_headers(self, transport: Any) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if isinstance(transport, GuardedTransport) and type(self) is not QwenCloudBackend:
            # The S1 configuration has no credential for a governed local backend.
            return headers
        if self.api_key and self.api_key != "not-needed":
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def resolve_model(self, timeout: float = 1.0) -> str:
        return self._resolve_model(self.transport, timeout)

    def _resolve_model(self, transport: Any, timeout: float) -> str:
        if self.model and self.model not in _AUTO_MODEL_SENTINELS:
            return self.model

        url = f"{self.base_url.rstrip('/')}/models"
        try:
            response = transport.get(url, timeout=timeout, headers=self._request_headers(transport))
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
        transport = self.transport
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": _generation_model(self, transport, timeout),
            "messages": messages,
            "temperature": temperature,
            **kwargs,
        }

        if stream_callback:
            payload["stream"] = True
            try:
                response = transport.post(
                    url,
                    json=payload,
                    timeout=timeout,
                    stream=True,
                    headers=self._request_headers(transport),
                )
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                _raise_backend_unavailable("OpenAI compatible", transport, url, e)

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
                        except DestinationPolicyError:
                            raise
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

        try:
            response = transport.post(
                url,
                json=payload,
                timeout=timeout,
                headers=self._request_headers(transport),
            )
            if not response.ok:
                print(
                    "Backend Error: "
                    f"backend={self.name} {_backend_error_summary(response, transport)}"
                )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            _raise_backend_unavailable("OpenAI compatible", transport, url, e)

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
        transport = self.transport
        try:
            response = transport.get(url, timeout=timeout, headers=self._request_headers(transport))
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
class QwenCloudBackend(OpenAICompatibleBackend):
    name: str = "qwen"
    base_url: str = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    model: str = "qwen-max"
    api_key: str = field(default="", repr=False)


@dataclass
class OllamaBackend:
    name: str = "ollama"
    base_url: str = "http://127.0.0.1:11434"
    model: str = "auto"
    transport: Any = field(default=requests, repr=False, compare=False)

    def get_sanitized_uri(self) -> str:
        parsed = urllib.parse.urlparse(self.base_url)
        return f"{parsed.scheme}://{parsed.hostname}" + (f":{parsed.port}" if parsed.port else "") + parsed.path

    def resolve_model(self, timeout: float = 1.0) -> str:
        return self._resolve_model(self.transport, timeout)

    def _resolve_model(self, transport: Any, timeout: float) -> str:
        if self.model and self.model not in _AUTO_MODEL_SENTINELS:
            return self.model

        url = f"{self.base_url.rstrip('/')}/api/tags"
        try:
            response = transport.get(url, timeout=timeout)
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
        transport = self.transport
        url = f"{self.base_url.rstrip('/')}/api/chat"
        payload = {
            "model": _generation_model(self, transport, timeout),
            "messages": messages,
            "stream": bool(stream_callback),
            "options": {"temperature": temperature},
        }
        payload.update(kwargs)

        if stream_callback:
            try:
                response = transport.post(url, json=payload, timeout=timeout, stream=True)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                _raise_backend_unavailable("Ollama", transport, url, e)
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

        try:
            response = transport.post(url, json=payload, timeout=timeout)
            if not response.ok:
                print(
                    "Backend Error: "
                    f"backend={self.name} {_backend_error_summary(response, transport)}"
                )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            _raise_backend_unavailable("Ollama", transport, url, e)
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
        transport = self.transport
        if isinstance(transport, GuardedTransport):
            # The supervisor probe is outside the bound Ollama protocol. Submit
            # it to the same guard without resolving any post-S1 environment.
            supervisor_url = GOVERNED_LOCAL_PRESETS["lmstudio"]
        else:
            supervisor_url = _lmstudio_base_url() if _prefer_lmstudio_supervisor() else None
        if supervisor_url and _lmstudio_is_online(supervisor_url, transport, min(timeout, 0.5)):
            return False

        url = f"{self.base_url.rstrip('/')}/api/tags"
        try:
            response = transport.get(url, timeout=timeout)
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


def _openai_backend_name(kind: str, base_url: str) -> str:
    if kind == "custom" and "1234" in base_url:
        return "lmstudio"
    return {"lm_studio": "lmstudio", "llamacpp": "llama.cpp"}.get(kind, kind)


def create_bound_backend(
    binding: RouteBinding,
    configuration: EffectiveBackendConfiguration,
    *,
    api_key: Optional[str] = None,
    transport_policy: TransportPolicy = DEFAULT_TRANSPORT_POLICY,
) -> LocalBackend:
    """Construct one concrete backend from the frozen S1 inputs, without discovery."""
    guard = GuardedTransport(binding, policy=transport_policy)
    base_url = binding.endpoint.canonical
    if binding.protocol == "qwen":
        backend = QwenCloudBackend(
            base_url=base_url, model=configuration.cloud_model.value,
            api_key=api_key or "", transport=guard,
        )
    elif binding.protocol == "ollama":
        backend = OllamaBackend(
            base_url=base_url, model=configuration.model.value, transport=guard,
        )
    elif binding.protocol == "openai_compatible":
        kind = backend_protocol_key(configuration.backend_type.value)
        backend = OpenAICompatibleBackend(
            name=_openai_backend_name(kind, base_url), base_url=base_url,
            model=configuration.model.value, transport=guard,
        )
    else:
        raise DestinationPolicyError("backend_protocol_unsupported", binding.route)
    guard.bind_owner(backend)
    return backend


def create_backend(
    backend_type: str = "ollama",
    model: str = "auto",
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> LocalBackend:
    normalized_type = (backend_type or "ollama").lower()

    if normalized_type == "ollama":
        return OllamaBackend(
            base_url=base_url or os.getenv("TRIAGE_OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
            model=model,
        )

    if normalized_type == "qwen":
        resolved_api_key = api_key or os.getenv("TRIAGE_QWEN_API_KEY")
        if not resolved_api_key:
            raise ValueError("qwen backend requires api_key")
        return QwenCloudBackend(
            base_url=base_url or os.getenv("TRIAGE_QWEN_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"),
            model=model if model not in _AUTO_MODEL_SENTINELS else os.getenv("TRIAGE_QWEN_MODEL", "qwen-max"),
            api_key=resolved_api_key,
        )

    presets = {
        "lmstudio": {
            "name": "lmstudio",
            "base_url": os.getenv("TRIAGE_SUPERVISOR_BASE_URL", "http://127.0.0.1:1234/v1"),
        },
        "lm_studio": {
            "name": "lmstudio",
            "base_url": os.getenv("TRIAGE_SUPERVISOR_BASE_URL", "http://127.0.0.1:1234/v1"),
        },
        "vllm": {
            "name": "vllm",
            "base_url": "http://127.0.0.1:8000/v1",
        },
        "llama.cpp": {
            "name": "llama.cpp",
            "base_url": "http://127.0.0.1:8080/v1",
        },
        "llamacpp": {
            "name": "llama.cpp",
            "base_url": "http://127.0.0.1:8080/v1",
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

    name = _openai_backend_name(selected["name"], resolved_base_url)

    return OpenAICompatibleBackend(
        name=name,
        base_url=resolved_base_url,
        model=model,
    )
