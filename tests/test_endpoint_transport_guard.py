"""Offline CR-135 backend integration checks using canned adapters and loopback HTTP."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sys
from threading import Thread
from uuid import uuid4

import pytest
import requests

from triage_core import backends
from triage_core.destination_policy import (
    DestinationPolicyError,
    GuardedTransport,
    TransportPolicy,
    bind_route_endpoints,
    resolve_effective_configuration,
)
from triage_core.engine import TriageEngine


def bound_backend(kind="lmstudio", *, model="fixture", url=None):
    env = {"TRIAGE_BACKEND_TYPE": kind, "TRIAGE_MODEL": model}
    if url is not None:
        env["TRIAGE_BASE_URL"] = url
    if kind == "qwen":
        env.update(TRIAGE_QWEN_ENABLED="true", TRIAGE_QWEN_MODEL=model,
                   TRIAGE_QWEN_API_KEY="fixture-key")
    config = resolve_effective_configuration(env, None)
    route = "cloud_primary" if kind == "qwen" else "local_fast"
    (binding,) = bind_route_endpoints((route,), config)
    backend = backends.create_bound_backend(binding, config, api_key=env.get("TRIAGE_QWEN_API_KEY"))
    assert backend.base_url == binding.endpoint.canonical
    assert type(backend.transport) is GuardedTransport
    assert backend.transport.owner is backend
    return backend


def transport_tripwires(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("governed HTTP went through an unregistered transport")

    for method in ("get", "post", "request"):
        monkeypatch.setattr(requests, method, forbidden)
    # The sealed transport prepares a request and calls its adapter directly.
    monkeypatch.setattr(requests.Session, "request", forbidden)


def response_body(path, method, stream=False):
    if method == "GET":
        return json.dumps({"data": [{"id": "observed"}], "models": [{"name": "observed"}]}).encode()
    if path.endswith("api/chat"):
        return b'{"message":{"content":"done"},"done":true}\n'
    if stream:
        return b'data: {"choices":[{"delta":{"content":"done"}}]}\n\ndata: [DONE]\n'
    return b'{"choices":[{"message":{"content":"done"}}]}'


def record_adapter(monkeypatch, *, after_request=None):
    calls = []

    def send(self, request, **settings):
        calls.append((request, settings))
        response = requests.Response()
        response.status_code = 200
        response._content = response_body(request.path_url, request.method, settings["stream"])
        response._content_consumed = True
        if after_request:
            after_request(request)
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    return calls


@pytest.mark.parametrize("kind,get_suffix,post_suffix", [
    ("lmstudio", "/v1/models", "/v1/chat/completions"),
    ("ollama", "/api/tags", "/api/chat"),
])
@pytest.mark.parametrize("stream", [False, True])
def test_actual_local_backend_paths_use_its_bound_transport(monkeypatch, kind, get_suffix, post_suffix, stream):
    transport_tripwires(monkeypatch)
    calls = record_adapter(monkeypatch)
    backend = bound_backend(kind, model="auto")
    chunks = []
    marker = "M04-PROTECTED-" + str(uuid4())
    result = backend.generate([{"role": "user", "content": marker}],
                              stream_callback=chunks.append if stream else None)
    assert result.text == "done"
    assert chunks == (["done"] if stream else [])
    assert [(r.method, r.path_url) for r, _ in calls] == [("GET", get_suffix), ("POST", post_suffix)]
    assert calls[0][0].body is None and marker.encode() in calls[1][0].body
    assert json.loads(calls[1][0].body)["model"] == "observed"
    assert [s.method for s in backend.transport.sends] == ["GET", "POST"]


def test_qwen_uses_one_guarded_post_with_transient_credential(monkeypatch):
    transport_tripwires(monkeypatch)
    calls = record_adapter(monkeypatch)
    backend = bound_backend("qwen")
    assert backend.generate([]).text == "done"
    assert len(calls) == 1
    prepared, _ = calls[0]
    assert (prepared.method, prepared.url) == ("POST", backend.base_url + "/chat/completions")
    assert prepared.headers["Authorization"] == "Bearer fixture-key"
    assert "fixture-key" not in repr(backend) + repr(backend.transport.sends)


def test_factory_enforces_the_policy_bound_into_the_decision(monkeypatch):
    transport_tripwires(monkeypatch)
    calls = record_adapter(monkeypatch)
    config = resolve_effective_configuration({"TRIAGE_MODEL": "fixture"}, None)
    (binding,) = bind_route_endpoints(("local_heavy",), config)
    policy = TransportPolicy(calls=())
    backend = backends.create_bound_backend(binding, config, transport_policy=policy)
    assert backend.transport.transport_policy_sha256 == policy.sha256
    with pytest.raises(DestinationPolicyError) as refused:
        backend.generate([])
    assert refused.value.code == "transport_request_not_permitted"
    assert calls == []


@pytest.mark.parametrize("kind", ["lmstudio", "ollama", "qwen"])
@pytest.mark.parametrize("stream", [False, True])
def test_governed_http_failure_contains_only_bounded_diagnostics(monkeypatch, capsys, kind, stream):
    transport_tripwires(monkeypatch)

    def unavailable(adapter, request, **settings):
        response = requests.Response()
        response.status_code = 503
        response.reason = "synthetic-sensitive-reason"
        response.url = request.url
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", unavailable)
    backend = bound_backend(kind)
    result = TriageEngine(backend).execute_task("fixture", "", stream_callback=(lambda chunk: None) if stream else None)
    assert result["failure_type"] == "backend_error"
    diagnostic = result["reason"] + capsys.readouterr().out
    assert backend.base_url not in diagnostic
    assert "synthetic-sensitive-reason" not in diagnostic
    assert "fixture-key" not in diagnostic


@pytest.mark.parametrize("kind", ["lmstudio", "ollama", "qwen"])
def test_governed_ping_uses_bound_protocol_only(monkeypatch, kind):
    transport_tripwires(monkeypatch)
    calls = record_adapter(monkeypatch)
    backend = bound_backend(kind)
    if kind == "lmstudio":
        assert backend.ping()
        assert [r.path_url for r, _ in calls] == ["/v1/models"]
    else:
        with pytest.raises(DestinationPolicyError) as refused:
            backend.ping()
        assert refused.value.code == "transport_request_not_permitted"
        assert calls == []


@pytest.mark.parametrize("kind", ["lmstudio", "ollama"])
@pytest.mark.parametrize("change,code", [("owner", "destination_binding_mismatch"),
                                         ("session", "transport_settings_changed")])
def test_changes_during_discovery_refuse_generation(monkeypatch, kind, change, code):
    transport_tripwires(monkeypatch)
    backend = bound_backend(kind, model="auto")
    original_base = backend.base_url

    def change_after_discovery(request):
        if change == "owner":
            backend.base_url = "http://127.0.0.1:22222"
        else:
            backend.transport._session.trust_env = True

    post_urls = []
    guarded_post = GuardedTransport.post

    def record_post_url(guard, url, **kwargs):
        post_urls.append(url)
        return guarded_post(guard, url, **kwargs)

    monkeypatch.setattr(GuardedTransport, "post", record_post_url)
    calls = record_adapter(monkeypatch, after_request=change_after_discovery)
    with pytest.raises(DestinationPolicyError) as refused:
        TriageEngine(backend).execute_task("fixture", "")
    assert refused.value.code == code
    assert [(r.method, r.url) for r, _ in calls] == [
        ("GET", original_base + ("/api/tags" if kind == "ollama" else "/models"))
    ]
    assert [s.method for s in backend.transport.sends] == ["GET"]
    assert post_urls == [original_base + ("/api/chat" if kind == "ollama" else "/chat/completions")]


def test_local_generate_keeps_verified_transport_and_snapshot_headers(monkeypatch):
    transport_tripwires(monkeypatch)
    backend = bound_backend(model="auto")
    verified = backend.transport
    backend.api_key = "unbound-local-key"

    def change_after_discovery(request):
        if request.method == "GET":
            backend.transport = requests
            backend.api_key = "changed-after-discovery"

    calls = record_adapter(monkeypatch, after_request=change_after_discovery)
    assert backend.generate([]).text == "done"
    assert [request.method for request, _ in calls] == ["GET", "POST"]
    assert all("Authorization" not in request.headers for request, _ in calls)
    assert [record.method for record in verified.sends] == ["GET", "POST"]


@pytest.mark.parametrize("kind", ["lmstudio", "ollama"])
def test_governed_generation_reads_one_transport_for_discovery_and_generation(monkeypatch, kind):
    transport_tripwires(monkeypatch)
    calls = record_adapter(monkeypatch)
    backend = bound_backend(kind, model="auto")
    guard = backend.transport
    reads = []

    def transport(owner):
        reads.append(owner)
        return guard

    monkeypatch.setattr(type(backend), "transport", property(transport))
    assert backend.generate([]).text == "done"
    assert [request.method for request, _ in calls] == ["GET", "POST"]
    assert len(reads) == 1 and reads[0] is backend


@pytest.mark.parametrize("path", [
    "/v1evil/chat/completions", "/v1/../chat/completions",
    "/v1//chat/completions", "/V1/chat/completions",
])
def test_integrated_guard_requires_exact_prepared_url(monkeypatch, path):
    transport_tripwires(monkeypatch)
    calls = record_adapter(monkeypatch)
    backend = bound_backend(url="http://127.0.0.1:1234/v1")
    with pytest.raises(DestinationPolicyError) as refused:
        backend.transport.post("http://127.0.0.1:1234" + path)
    assert refused.value.code == "transport_request_not_permitted"
    assert backend.transport.sends == () and calls == []


@contextmanager
def loopback_server():
    class Handler(BaseHTTPRequestHandler):
        def handle_request(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self.server.requests_seen.append((self.command, self.path, dict(self.headers), body))
            redirect = self.server.reply_method in (None, self.command)
            status = self.server.reply_status if redirect else 200
            data = response_body(self.path, self.command)
            self.send_response(status)
            if redirect and self.server.location:
                self.send_header("Location", self.server.location)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        do_GET = handle_request
        do_POST = handle_request

        def log_message(self, format, *args):
            pass

    class RecordingServer(ThreadingHTTPServer):
        def get_request(self):
            connection = super().get_request()
            self.connections += 1
            return connection

    with RecordingServer(("127.0.0.1", 0), Handler) as server:
        server.connections = 0
        server.requests_seen = []
        server.reply_status = 200
        server.reply_method = None
        server.location = None
        server.url = f"http://127.0.0.1:{server.server_port}"
        thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join()


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("model,stream", [("auto", False), ("fixed", False), ("fixed", True)])
def test_loopback_redirect_ends_attempt_without_following(monkeypatch, status, model, stream):
    transport_tripwires(monkeypatch)
    with loopback_server() as target, loopback_server() as origin:
        origin.reply_status = status
        origin.location = target.url + "/fixture"
        backend = bound_backend(model=model, url=origin.url + "/v1")
        marker = "M04-PROTECTED-" + str(uuid4())
        with pytest.raises(DestinationPolicyError) as refused:
            TriageEngine(backend).execute_task(marker, "", stream_callback=(lambda chunk: None) if stream else None)
        assert refused.value.code == "endpoint_redirect_refused"
        method, suffix = ("GET", "models") if model == "auto" else ("POST", "chat/completions")
        assert [(method_, path) for method_, path, _, _ in origin.requests_seen] == [(method, "/v1/" + suffix)]
        assert (marker.encode() in origin.requests_seen[0][3]) == (method == "POST")
        assert [(s.method, s.suffix, s.status_code) for s in backend.transport.sends] == [(method, suffix, status)]
        assert target.connections == 0


def test_cli_late_refusal_carries_every_permitted_send(monkeypatch, capsys):
    from triage_core import capability_evidence, tc_cli

    transport_tripwires(monkeypatch)
    declared = capability_evidence.resolve_capability(
        record=None, declare_local_fast=True, declare_local_heavy=True,
        local_fast_model="auto", local_heavy_model="auto",
        config_reference="fixture", freshness_seconds=60,
    )
    monkeypatch.setattr(capability_evidence, "resolve_from_config", lambda config: declared)
    marker = "M04-PROTECTED-" + str(uuid4())
    monkeypatch.setattr(sys, "argv", ["tc", "run", "Summarize this text", "--data", marker, "--no-ledger"])
    with loopback_server() as target, loopback_server() as origin:
        origin.reply_status = 307
        origin.reply_method = "POST"
        origin.location = target.url + "/fixture"
        monkeypatch.setenv("TRIAGE_BACKEND_TYPE", "lmstudio")
        monkeypatch.setenv("TRIAGE_BASE_URL", origin.url + "/v1")
        with pytest.raises(SystemExit) as refused:
            tc_cli.main()
        output = capsys.readouterr().out
        assert refused.value.code == 2
        assert "endpoint_redirect_refused" in output and "send_count=2" in output
        assert "GET models" in output and "POST chat/completions" in output
        assert marker not in output and origin.url not in output
        assert [(m, p) for m, p, _, _ in origin.requests_seen] == [
            ("GET", "/v1/models"), ("POST", "/v1/chat/completions")
        ]
        assert target.connections == 0


def assert_loopback_environment_isolation(monkeypatch, tmp_path, *, invoke=None):
    """F9 shared loopback harness for the required Windows and Linux parity job."""
    transport_tripwires(monkeypatch)
    for name in (".netrc", "_netrc"):
        credentials = tmp_path / name
        credentials.write_text("machine 127.0.0.1 login fixture password synthetic\n", encoding="ascii")
        credentials.chmod(0o600)
    monkeypatch.delenv("NETRC", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(tmp_path / "absent-ca.pem"))
    with loopback_server() as proxy, loopback_server() as origin:
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
            monkeypatch.setenv(name, proxy.url)
            monkeypatch.setenv(name.lower(), proxy.url)
        for name in ("NO_PROXY", "no_proxy"):
            monkeypatch.delenv(name, raising=False)
        base_url = origin.url + "/v1"
        assert requests.utils.get_netrc_auth(base_url) == ("fixture", "synthetic")
        tls_settings = []
        send = requests.adapters.HTTPAdapter.send

        def record_tls_settings(adapter, request, **kwargs):
            tls_settings.append(kwargs["verify"])
            return send(adapter, request, **kwargs)

        monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", record_tls_settings)
        if invoke is None:
            assert bound_backend(url=base_url).generate([]).text == "done"
        else:
            invoke(base_url)
        assert [(m, p) for m, p, _, _ in origin.requests_seen] == [("POST", "/v1/chat/completions")]
        assert "authorization" not in {k.lower() for k in origin.requests_seen[0][2]}
        assert proxy.connections == 0
        assert tls_settings == [True]


def test_loopback_transport_ignores_ambient_ca_bundle(monkeypatch, tmp_path):
    assert_loopback_environment_isolation(monkeypatch, tmp_path)
