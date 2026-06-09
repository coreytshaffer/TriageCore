import pytest
from unittest.mock import patch, Mock
from triage_core.backends import create_backend, OpenAICompatibleBackend

def test_preset_urls():
    ollama = create_backend("ollama")
    assert ollama.base_url == "http://localhost:11434/v1"
    
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
def test_backend_generate_success(mock_post):
    mock_resp = Mock()
    mock_resp.json.return_value = {
        "choices": [{"message": {"content": "Hello World"}}],
        "usage": {"total_tokens": 10}
    }
    mock_post.return_value = mock_resp
    
    backend = create_backend("ollama", model="test-model")
    result = backend.generate([{"role": "user", "content": "hi"}])
    
    assert result.text == "Hello World"
    assert result.usage == {"total_tokens": 10}
    assert result.backend_name == "ollama"
    
    # Check that it hit the right URL
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "http://localhost:11434/v1/chat/completions"
    assert kwargs["json"]["model"] == "test-model"


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
    mock_resp.json.return_value = {"choices": []}
    mock_post.return_value = mock_resp
    
    backend = create_backend("vllm")
    with pytest.raises(ValueError, match="Backend returned no choices."):
        backend.generate([{"role": "user", "content": "hi"}])

@patch("triage_core.backends.requests.post")
def test_backend_generate_no_content(mock_post):
    mock_resp = Mock()
    mock_resp.json.return_value = {"choices": [{"message": {}}]}
    mock_post.return_value = mock_resp
    
    backend = create_backend("llama.cpp")
    with pytest.raises(ValueError, match="Backend returned no message content."):
        backend.generate([{"role": "user", "content": "hi"}])
