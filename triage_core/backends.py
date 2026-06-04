from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol
import requests

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
        **kwargs: Any,
    ) -> BackendResponse:
        ...


@dataclass
class OpenAICompatibleBackend:
    name: str
    base_url: str
    model: str
    api_key: str = "not-needed"

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        timeout: int = 45,
        **kwargs: Any,
    ) -> BackendResponse:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            **kwargs,
        }

        response = requests.post(url, json=payload, timeout=timeout)
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
        """Check if the local backend is running by querying the /models endpoint."""
        url = f"{self.base_url.rstrip('/')}/models"
        try:
            response = requests.get(url, timeout=timeout)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False


def create_backend(
    backend_type: str = "ollama",
    model: str = "local-model",
    base_url: Optional[str] = None,
) -> OpenAICompatibleBackend:
    presets = {
        "ollama": {
            "name": "ollama",
            "base_url": "http://localhost:11434/v1",
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

    if backend_type not in presets:
        raise ValueError(f"Unknown backend_type: {backend_type}")

    selected = presets[backend_type]
    resolved_base_url = base_url or selected["base_url"]

    if not resolved_base_url:
        raise ValueError("custom backend requires base_url")

    return OpenAICompatibleBackend(
        name=selected["name"],
        base_url=resolved_base_url,
        model=model,
    )
