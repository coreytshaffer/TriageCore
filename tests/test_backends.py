import pytest
from unittest.mock import patch, Mock
import requests

from triage_core.backends import BackendUnavailableError, create_backend, OllamaBackend


@pytest.mark.parametrize("kind", ["lmstudio", "ollama"])
@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("status", [301, 302, 303, 304, 307, 308])
def test_direct_generation_refuses_redirect_without_consuming_result(kind, streaming, status, capsys):
    response = Mock(spec=requests.Response)
    response.status_code = status
    response.ok = True
    response.headers = {"Location": "https://example.invalid/redirect-fixture"}
    response.json.return_value = {
        "choices": [{"message": {"content": "synthetic-response"}}],
        "message": {"content": "synthetic-response"},
    }
    response.iter_lines.return_value = []
    callback = Mock() if streaming else None
    with patch.object(requests, "post", return_value=response) as post:
        backend = create_backend(kind, model="fixture")
        with pytest.raises(BackendUnavailableError, match="Backend redirect refused") as caught:
            backend.generate([{"role": "user", "content": "synthetic-input"}], stream_callback=callback)

    assert str(caught.value) == "Backend redirect refused."
    post.assert_called_once()
    assert post.call_args.kwargs["allow_redirects"] is False
    response.close.assert_called_once()
    response.json.assert_not_called()
    response.iter_lines.assert_not_called()
    if callback is not None:
        callback.assert_not_called()
    assert capsys.readouterr() == ("", "")


@pytest.mark.parametrize("kind", ["lmstudio", "ollama"])
def test_direct_discovery_redirect_stops_generation(kind):
    response = Mock(spec=requests.Response)
    response.status_code = 307
    response.ok = True
    response.json.return_value = {
        "data": [{"id": "fixture"}],
        "models": [{"name": "fixture"}],
        "choices": [{"message": {"content": "synthetic-response"}}],
        "message": {"content": "synthetic-response"},
    }
    with (
        patch.object(requests, "get", return_value=response) as get,
        patch.object(requests, "post", return_value=response) as post,
    ):
        backend = create_backend(kind, model="auto")
        with pytest.raises(BackendUnavailableError, match="Backend redirect refused"):
            backend.generate([{"role": "user", "content": "synthetic-input"}])

    get.assert_called_once()
    assert get.call_args.kwargs["allow_redirects"] is False
    post.assert_not_called()
    response.close.assert_called_once()
    response.json.assert_not_called()
    assert backend.model == "auto"


@pytest.mark.parametrize("kind", ["lmstudio", "ollama"])
def test_direct_health_check_refuses_redirect(kind, monkeypatch):
    monkeypatch.setenv("TRIAGE_PREFER_LMSTUDIO_SUPERVISOR", "false")
    response = Mock(spec=requests.Response)
    response.status_code = 302
    with patch.object(requests, "get", return_value=response) as get:
        assert create_backend(kind, model="fixture").ping() is False

    get.assert_called_once()
    assert get.call_args.kwargs["allow_redirects"] is False
    response.close.assert_called_once()
    response.json.assert_not_called()


def test_ollama_ignores_redirecting_supervisor_for_readiness(monkeypatch):
    monkeypatch.setenv("TRIAGE_PREFER_LMSTUDIO_SUPERVISOR", "true")
    monkeypatch.setenv("TRIAGE_SUPERVISOR_BASE_URL", "http://127.0.0.1:1234/v1")
    redirect = Mock(spec=requests.Response)
    redirect.status_code = 302
    available = Mock(spec=requests.Response)
    available.status_code = 200
    with patch.object(requests, "get", side_effect=[redirect, available]) as get:
        assert create_backend("ollama", model="fixture").ping() is True

    assert [call.args[0] for call in get.call_args_list] == [
        "http://127.0.0.1:1234/v1/models", "http://127.0.0.1:11434/api/tags",
    ]
    assert all(call.kwargs["allow_redirects"] is False for call in get.call_args_list)
    redirect.close.assert_called_once()


def test_requests_refuses_redirect_before_preparing_another_request(monkeypatch):
    calls = []

    def send(adapter, request, **kwargs):
        calls.append(request.url)
        response = requests.Response()
        response.status_code = 307
        response.request = request
        response.url = request.url
        response._content = b""
        response._content_consumed = True
        return response

    def unexpected_redirect_processing(*args, **kwargs):
        pytest.fail("The backend must refuse a 3xx before Requests prepares a redirect")

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    monkeypatch.setattr(requests.Session, "resolve_redirects", unexpected_redirect_processing)
    backend = create_backend("lmstudio", model="fixture", base_url="http://127.0.0.1:1234/v1")

    with pytest.raises(BackendUnavailableError, match="Backend redirect refused"):
        backend.generate([])

    assert calls == ["http://127.0.0.1:1234/v1/chat/completions"]


def test_injected_requests_session_preserves_successful_response_hooks(monkeypatch):
    def send(adapter, request, **kwargs):
        response = requests.Response()
        response.status_code = 200
        response.request = request
        response.url = request.url
        response._content = b'{"message":{"content":"fixture"}}'
        response._content_consumed = True
        return response

    observed = []

    def observe_response(response, **kwargs):
        observed.append(response.status_code)

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    with requests.Session() as session:
        session.hooks["response"].append(observe_response)
        backend = OllamaBackend(model="fixture", transport=session)
        result = backend.generate([])

    assert result.text == "fixture"
    assert observed == [200]


def test_redirect_returned_by_a_session_hook_is_refused_before_redirect_processing(monkeypatch):
    def send(adapter, request, **kwargs):
        response = requests.Response()
        response.status_code = 200
        response.request = request
        response.url = request.url
        response._content = b""
        response._content_consumed = True
        return response

    def mark_unavailable(response, **kwargs):
        response.status_code = 307
        return response

    def unexpected_redirect_processing(*args, **kwargs):
        pytest.fail("A response hook must not reintroduce redirect processing")

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    monkeypatch.setattr(requests.Session, "resolve_redirects", unexpected_redirect_processing)
    with requests.Session() as session:
        session.hooks["response"].append(mark_unavailable)
        backend = OllamaBackend(model="fixture", transport=session)
        with pytest.raises(BackendUnavailableError, match="Backend redirect refused"):
            backend.generate([])


def test_preset_urls():
    ollama = create_backend("ollama")
    assert isinstance(ollama, OllamaBackend)
    assert ollama.base_url == "http://127.0.0.1:11434"

    lmstudio = create_backend("lmstudio")
    assert lmstudio.base_url == "http://127.0.0.1:1234/v1"
    assert lmstudio.name == "lmstudio"

    vllm = create_backend("vllm")
    assert vllm.base_url == "http://127.0.0.1:8000/v1"

    llamacpp = create_backend("llama.cpp")
    assert llamacpp.base_url == "http://127.0.0.1:8080/v1"


def test_custom_backend_missing_url():
    with pytest.raises(ValueError, match="custom backend requires base_url"):
        create_backend("custom")


def test_unknown_backend():
    with pytest.raises(ValueError, match="Unknown backend_type: invalid"):
        create_backend("invalid")


@patch("triage_core.backends.requests.post")
def test_openai_backend_generate_success(mock_post):
    mock_resp = Mock()
    mock_resp.status_code = 200
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
    assert args[0] == "http://127.0.0.1:1234/v1/chat/completions"
    assert kwargs["json"]["model"] == "test-model"


@patch("triage_core.backends.requests.post")
def test_ollama_backend_generate_uses_native_api(mock_post):
    mock_resp = Mock()
    mock_resp.status_code = 200
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
    assert args[0] == "http://127.0.0.1:11434/api/chat"
    assert kwargs["json"]["model"] == "qwen2.5-coder:7b"
    assert kwargs["json"]["stream"] is False


@patch("triage_core.backends.requests.get")
@patch("triage_core.backends.requests.post")
def test_lmstudio_auto_model_resolution(mock_post, mock_get):
    mock_get_resp = Mock()
    mock_get_resp.status_code = 200
    mock_get_resp.json.return_value = {
        "data": [{"id": "currently-loaded-lm-studio-model"}]
    }
    mock_get.return_value = mock_get_resp

    mock_post_resp = Mock()
    mock_post_resp.status_code = 200
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
    assert args[0] == "http://127.0.0.1:1234/v1/chat/completions"
    assert kwargs["json"]["model"] == "currently-loaded-lm-studio-model"


@patch("triage_core.backends.requests.post")
def test_backend_generate_streaming_omits_stream_options(mock_post):
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.iter_lines.return_value = [
        b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
        b'data: {"choices":[{"delta":{"content":" World"}}],"usage":{"total_tokens":2}}',
        b"data: [DONE]",
    ]
    mock_post.return_value = mock_resp

    chunks = []
    backend = create_backend("custom", model="fixed", base_url="http://localhost:1234/v1")
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
    mock_resp.status_code = 200
    mock_resp.ok = True
    mock_resp.json.return_value = {"choices": []}
    mock_post.return_value = mock_resp

    backend = create_backend("vllm", model="test-model")
    with pytest.raises(ValueError, match="Backend returned no choices."):
        backend.generate([{"role": "user", "content": "hi"}])


@patch("triage_core.backends.requests.post")
def test_backend_generate_no_content(mock_post):
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.ok = True
    mock_resp.json.return_value = {"choices": [{"message": {}}]}
    mock_post.return_value = mock_resp

    backend = create_backend("llama.cpp", model="test-model")
    with pytest.raises(ValueError, match="Backend returned no message content."):
        backend.generate([{"role": "user", "content": "hi"}])


@patch("triage_core.backends.requests.post")
def test_backend_error_output_is_sanitized(mock_post, capsys):
    mock_resp = Mock(spec=requests.Response)
    mock_resp.ok = False
    mock_resp.status_code = 500
    mock_resp.reason = "Internal Server Error"
    mock_resp.text = "secret request trace with api_key=leak"
    mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "500 Server Error"
    )
    mock_post.return_value = mock_resp

    backend = create_backend("lmstudio", model="test-model")
    with pytest.raises(BackendUnavailableError):
        backend.generate([{"role": "user", "content": "hi"}])

    captured = capsys.readouterr()
    assert "status_code=500" in captured.out
    assert "Internal Server Error" in captured.out
    assert "secret request trace" not in captured.out
    assert "api_key" not in captured.out
