import pytest
import requests
from unittest.mock import Mock, patch

from triage_core.backends import BackendUnavailableError, QwenCloudBackend, create_backend


def test_create_qwen_backend_uses_env_settings(monkeypatch):
    monkeypatch.setenv("TRIAGE_QWEN_API_KEY", "env-qwen-key")
    monkeypatch.setenv("TRIAGE_QWEN_BASE_URL", "https://env.qwen/v1")
    monkeypatch.setenv("TRIAGE_QWEN_MODEL", "env-qwen-model")

    backend = create_backend("qwen", model="auto")

    assert isinstance(backend, QwenCloudBackend)
    assert backend.name == "qwen"
    assert backend.base_url == "https://env.qwen/v1"
    assert backend.model == "env-qwen-model"
    assert backend.api_key == "env-qwen-key"


def test_create_qwen_backend_requires_api_key(monkeypatch):
    monkeypatch.delenv("TRIAGE_QWEN_API_KEY", raising=False)

    with pytest.raises(ValueError, match="qwen backend requires api_key"):
        create_backend("qwen")


@patch("triage_core.backends.requests.post")
def test_qwen_backend_generate_sends_auth_header(mock_post):
    mock_response = Mock()
    mock_response.ok = True
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Qwen says hi"}}],
        "usage": {"total_tokens": 12},
    }
    mock_post.return_value = mock_response

    backend = create_backend(
        "qwen",
        model="qwen-test",
        base_url="https://qwen.example/v1",
        api_key="secret-key",
    )
    result = backend.generate([{"role": "user", "content": "hello"}])

    assert result.text == "Qwen says hi"
    assert result.backend_name == "qwen"
    assert result.usage == {"total_tokens": 12}
    args, kwargs = mock_post.call_args
    assert args[0] == "https://qwen.example/v1/chat/completions"
    assert kwargs["headers"]["Authorization"] == "Bearer secret-key"
    assert kwargs["json"]["model"] == "qwen-test"


@patch("triage_core.backends.requests.post", side_effect=requests.exceptions.RequestException("boom"))
def test_qwen_backend_request_failure_raises_backend_unavailable(mock_post):
    backend = create_backend(
        "qwen",
        model="qwen-test",
        base_url="https://qwen.example/v1",
        api_key="secret-key",
    )

    with pytest.raises(BackendUnavailableError, match="OpenAI compatible backend unavailable"):
        backend.generate([{"role": "user", "content": "hello"}])
