import json
from unittest.mock import Mock, patch

import pytest
import requests

from triage_core.backends import BackendUnavailableError, QwenCloudBackend, create_backend
from triage_core.destination_policy import DestinationPolicyError


QWEN_BASE = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
QWEN_CANONICAL_BASE = "https://dashscope-intl.aliyuncs.com:443/compatible-mode/v1"
DUMMY_KEY = "synthetic-qwen-key"


@pytest.fixture(autouse=True)
def require_recording_transport(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Qwen must use the recording adapter through its destination guard")

    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", forbidden)


@pytest.fixture
def recorded_sends(monkeypatch):
    sends = []

    def send(self, request, **settings):
        sends.append((request, settings))
        response = requests.Response()
        response.status_code = 200
        response._content = b'{"choices":[{"message":{"content":"Qwen says hi"}}],"usage":{"total_tokens":12}}'
        response._content_consumed = True
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    return sends


def test_create_qwen_backend_uses_env_settings(monkeypatch, recorded_sends):
    monkeypatch.setenv("TRIAGE_QWEN_API_KEY", DUMMY_KEY)
    monkeypatch.setenv("TRIAGE_QWEN_BASE_URL", QWEN_BASE)
    monkeypatch.setenv("TRIAGE_QWEN_MODEL", "env-qwen-model")

    backend = create_backend("qwen", model="auto")

    assert isinstance(backend, QwenCloudBackend)
    assert backend.name == "qwen"
    assert backend.base_url == QWEN_CANONICAL_BASE
    assert backend.model == "env-qwen-model"
    assert backend.api_key == DUMMY_KEY
    assert not recorded_sends


def test_create_qwen_backend_requires_api_key(monkeypatch):
    monkeypatch.delenv("TRIAGE_QWEN_API_KEY", raising=False)

    with pytest.raises(ValueError, match="qwen backend requires api_key"):
        create_backend("qwen")


@pytest.mark.parametrize("construct", [QwenCloudBackend, lambda **kwargs: create_backend("qwen", **kwargs)])
def test_qwen_generation_uses_only_the_approved_post(construct, monkeypatch, recorded_sends):
    monkeypatch.setenv("HTTPS_PROXY", "http://proxy.example.test:8080")
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", "synthetic-ca.pem")
    monkeypatch.setenv("NETRC", "synthetic-netrc")
    backend = construct(model="qwen-test", base_url=QWEN_BASE, api_key=DUMMY_KEY)

    assert backend.resolve_model() == "qwen-test"
    assert not recorded_sends
    result = backend.generate([{"role": "user", "content": "hello"}])

    assert result.text == "Qwen says hi"
    assert result.backend_name == "qwen"
    assert result.usage == {"total_tokens": 12}
    [(request, settings)] = recorded_sends
    assert (request.method, request.url) == ("POST", QWEN_CANONICAL_BASE + "/chat/completions")
    assert request.headers["Authorization"] == f"Bearer {DUMMY_KEY}"
    assert json.loads(request.body)["model"] == "qwen-test"
    assert settings["proxies"] == {}
    assert settings["verify"] is True
    assert settings["cert"] is None


def test_qwen_probe_is_refused_without_blocking_generation(recorded_sends):
    backend = create_backend("qwen", api_key=DUMMY_KEY)

    with pytest.raises(DestinationPolicyError, match="transport_request_not_permitted"):
        backend.ping()

    assert not recorded_sends
    assert backend.generate([]).text == "Qwen says hi"
    [(request, _)] = recorded_sends
    assert request.method == "POST"


@pytest.mark.parametrize("base_url", [
    "https://unapproved.example.test/compatible-mode/v1",
    "http://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    "https://dashscope-intl.aliyuncs.com:8443/compatible-mode/v1",
    "https://dashscope-intl.aliyuncs.com/other-path",
])
def test_direct_qwen_refuses_unapproved_destination(base_url, recorded_sends):
    with pytest.raises(DestinationPolicyError) as refusal:
        QwenCloudBackend(base_url=base_url, api_key=DUMMY_KEY)

    assert base_url not in str(refusal.value)
    assert DUMMY_KEY not in str(refusal.value)
    assert not recorded_sends


def test_qwen_factory_refuses_unapproved_environment_destination(monkeypatch, recorded_sends):
    monkeypatch.setenv("TRIAGE_QWEN_BASE_URL", "https://unapproved.example.test/v1")

    with pytest.raises(DestinationPolicyError, match="cloud_endpoint_not_approved"):
        create_backend("qwen", api_key=DUMMY_KEY)

    assert not recorded_sends


def test_qwen_refuses_a_model_that_requires_discovery(monkeypatch, recorded_sends):
    monkeypatch.setenv("TRIAGE_QWEN_MODEL", "auto")

    with pytest.raises(DestinationPolicyError, match="cloud_model_unbound"):
        create_backend("qwen", api_key=DUMMY_KEY)

    backend = QwenCloudBackend(api_key=DUMMY_KEY)
    backend.model = "auto"
    with pytest.raises(DestinationPolicyError, match="cloud_model_unbound"):
        backend.generate([])
    assert not recorded_sends


def test_qwen_factory_refuses_non_string_model(recorded_sends):
    with pytest.raises(DestinationPolicyError, match="cloud_model_unbound"):
        create_backend("qwen", model=["synthetic-model"], api_key=DUMMY_KEY)

    assert not recorded_sends


def test_qwen_refuses_custom_or_replaced_transport(recorded_sends):
    unguarded = Mock()
    with pytest.raises(DestinationPolicyError, match="transport_not_guarded"):
        QwenCloudBackend(api_key=DUMMY_KEY, transport=unguarded)

    backend = QwenCloudBackend(api_key=DUMMY_KEY)
    backend.transport = unguarded
    with pytest.raises(DestinationPolicyError, match="transport_not_guarded"):
        backend.generate([])
    other_backend = QwenCloudBackend(api_key=DUMMY_KEY)
    with pytest.raises(DestinationPolicyError, match="transport_not_guarded"):
        backend.generate([], _verified_transport=other_backend.transport)
    unguarded.post.assert_not_called()
    unguarded.get.assert_not_called()
    assert not recorded_sends


def test_qwen_refuses_destination_change_after_construction(recorded_sends):
    backend = QwenCloudBackend(api_key=DUMMY_KEY)
    backend.base_url = "https://unapproved.example.test/v1"

    with pytest.raises(DestinationPolicyError, match="destination_binding_mismatch"):
        backend.generate([])

    assert not recorded_sends


def test_qwen_streaming_generation_uses_the_same_destination(monkeypatch):
    sends = []

    def send(self, request, **settings):
        sends.append((request, settings))
        response = requests.Response()
        response.status_code = 200
        response._content = b'data: {"choices":[{"delta":{"content":"streamed"}}]}\n\ndata: [DONE]\n'
        response._content_consumed = True
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    chunks = []
    result = QwenCloudBackend(api_key=DUMMY_KEY).generate([], stream_callback=chunks.append)

    assert result.text == "streamed"
    assert chunks == ["streamed"]
    [(request, settings)] = sends
    assert (request.method, request.url) == ("POST", QWEN_CANONICAL_BASE + "/chat/completions")
    assert request.headers["Authorization"] == f"Bearer {DUMMY_KEY}"
    assert settings["stream"] is True


def test_qwen_stops_on_redirect(monkeypatch):
    sends = []

    def redirect(self, request, **settings):
        sends.append(request.url)
        response = requests.Response()
        response.status_code = 307
        response.headers["Location"] = "https://unapproved.example.test/"
        response._content_consumed = True
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", redirect)
    backend = QwenCloudBackend(api_key=DUMMY_KEY)
    for _ in range(2):
        with pytest.raises(DestinationPolicyError, match="endpoint_redirect_refused"):
            backend.generate([])
    assert sends == [QWEN_CANONICAL_BASE + "/chat/completions"]


@patch("requests.adapters.HTTPAdapter.send", side_effect=requests.RequestException("synthetic transport detail"))
def test_qwen_backend_request_failure_raises_backend_unavailable(mock_send):
    backend = QwenCloudBackend(api_key=DUMMY_KEY)

    with pytest.raises(BackendUnavailableError, match="OpenAI compatible backend unavailable") as unavailable:
        backend.generate([{"role": "user", "content": "hello"}])

    mock_send.assert_called_once()
    assert "synthetic transport detail" not in str(unavailable.value)
