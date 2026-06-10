import pytest
from unittest.mock import patch, Mock
import requests
from triage_core.backends import create_backend, BackendUnavailableError

def test_ollama_backend_handles_200():
    with patch("requests.post") as mock_post:
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "message": {"content": "Hello from mock"},
            "eval_count": 5
        }
        mock_post.return_value = mock_resp
        
        backend = create_backend("ollama")
        response = backend.generate([{"role": "user", "content": "hi"}])
        assert response.text == "Hello from mock"
        assert response.usage["completion_tokens"] == 5

def test_ollama_backend_handles_connection_error():
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("Offline")):
        backend = create_backend("ollama")
        with pytest.raises(BackendUnavailableError) as exc_info:
            backend.generate([{"role": "user", "content": "hi"}])
        assert "Ollama backend unavailable" in str(exc_info.value)
        assert "Offline" in str(exc_info.value)

def test_openai_compatible_backend_handles_200():
    with patch("requests.post") as mock_post:
        mock_resp = Mock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Hello from LM Studio"}}],
            "usage": {"total_tokens": 10}
        }
        mock_post.return_value = mock_resp
        
        backend = create_backend("lmstudio")
        with patch("requests.get") as mock_get:
            # Mock models endpoint used by resolve_model
            mock_get_resp = Mock()
            mock_get_resp.status_code = 200
            mock_get_resp.json.return_value = {"data": [{"id": "test-model"}]}
            mock_get.return_value = mock_get_resp

            response = backend.generate([{"role": "user", "content": "hi"}])
            assert response.text == "Hello from LM Studio"

def test_openai_compatible_backend_handles_connection_error():
    with patch("requests.post", side_effect=requests.exceptions.ConnectionError("Offline")):
        backend = create_backend("lmstudio")
        with pytest.raises(BackendUnavailableError) as exc_info:
            with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Offline Models")):
                backend.generate([{"role": "user", "content": "hi"}])
        assert "OpenAI compatible backend unavailable" in str(exc_info.value)
        assert "Offline" in str(exc_info.value)

def test_ollama_backend_handles_500():
    with patch("requests.post") as mock_post:
        mock_resp = Mock()
        mock_resp.ok = False
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_post.return_value = mock_resp
        
        backend = create_backend("ollama")
        with pytest.raises(BackendUnavailableError):
            backend.generate([{"role": "user", "content": "hi"}])
