"""Unit tests for ``triage_core.destination_policy`` (CR-135 slice 1).

Every test here is offline. Guarded-transport tests use a recording adapter mounted on
the guard's own session for both ``http://`` and ``https://``, so no request can reach
the default network adapter, and an autouse fixture makes any socket connection fail
the test. These tests are unit-level evidence of the slice 1 contract only. They are
not evidence that any governed run's network effects are contained: nothing in the
runtime uses this module yet.
"""

from __future__ import annotations

import ast
import dataclasses
import itertools
import json
import os
import pathlib
import re
import socket
import subprocess
import sys

import pytest
import requests
from requests.adapters import BaseAdapter
from requests.structures import CaseInsensitiveDict

from triage_core import destination_policy as dp
from triage_core.destination_policy import (
    CLOUD_PROFILE_ID,
    DEFAULT_TRANSPORT_POLICY,
    DEVICE_LOOPBACK,
    LOCAL_PROFILE_ID,
    REMOTE_CLOUD,
    UNREADABLE_CONFIGURATION,
    DestinationPolicyError,
    GuardedTransport,
    TransportPolicy,
    allowed_request_urls,
    bind_route_endpoints,
    binding_digest_lines,
    canonicalize_base_path,
    normalize_endpoint,
    resolve_effective_configuration,
)

MODULE_PATH = pathlib.Path(dp.__file__)
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
CLOUD_URL = "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
CLOUD_CANONICAL = "https://dashscope-intl.aliyuncs.com:443/compatible-mode/v1"


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("network access attempted in an offline test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def refusal(callable_, *args, **kwargs) -> str:
    with pytest.raises(DestinationPolicyError) as info:
        callable_(*args, **kwargs)
    return info.value.code


class RecordingAdapter(BaseAdapter):
    """Records every request handed to it and answers from a fixed status list."""

    def __init__(self, statuses=None, location="http://203.0.113.9:9/elsewhere"):
        super().__init__()
        self.calls = []
        self._statuses = list(statuses or [])
        self._location = location

    def send(self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None):
        self.calls.append(
            {
                "method": request.method,
                "url": request.url,
                "headers": dict(request.headers),
                "body": request.body,
                "proxies": proxies,
                "verify": verify,
                "cert": cert,
            }
        )
        status = self._statuses.pop(0) if self._statuses else 200
        response = requests.Response()
        response.status_code = status
        response.url = request.url
        response.request = request
        response.headers = CaseInsensitiveDict(
            {"Location": self._location} if 300 <= status < 400 else {}
        )
        response._content = b"{}"
        response._content_consumed = True
        return response

    def close(self):
        pass


class StubBackend:
    """Stands in for a backend instance: only ``base_url`` matters to the guard."""

    def __init__(self, base_url):
        self.base_url = base_url


def make_guard(
    url="http://127.0.0.1:1234/v1",
    backend_type="lmstudio",
    route="local_fast",
    statuses=None,
    cloud=False,
):
    env = {"TRIAGE_BACKEND_TYPE": backend_type, "TRIAGE_BASE_URL": url}
    if cloud:
        env = {"TRIAGE_QWEN_ENABLED": "1", "TRIAGE_QWEN_BASE_URL": url}
    configuration = resolve_effective_configuration(env, None)
    (binding,) = bind_route_endpoints((route,), configuration)
    adapter = RecordingAdapter(statuses)
    guard = GuardedTransport(binding, adapters={"http://": adapter, "https://": adapter})
    owner = StubBackend(binding.endpoint.canonical)
    guard.bind_owner(owner)
    return guard, owner, adapter, binding


# --- Endpoint normalization --------------------------------------------------------


@pytest.mark.parametrize(
    "raw, route, canonical, label",
    [
        ("http://127.0.0.1:11434", "local_fast", "http://127.0.0.1:11434", "loopback-ipv4:11434"),
        ("http://[::1]:1234/v1", "local_heavy", "http://[::1]:1234/v1", "loopback-ipv6:1234"),
        ("http://127.0.0.1", "local_fast", "http://127.0.0.1:80", "loopback-ipv4:80"),
        ("https://127.0.0.1/v1/", "local_fast", "https://127.0.0.1:443/v1", "loopback-ipv4:443"),
    ],
)
def test_literal_loopback_endpoints_canonicalize(raw, route, canonical, label):
    endpoint = normalize_endpoint(raw, route)
    assert endpoint.canonical == canonical
    assert endpoint.locality == DEVICE_LOOPBACK
    assert endpoint.profile_id == LOCAL_PROFILE_ID
    assert endpoint.safe_label == label
    assert DIGEST_RE.fullmatch(endpoint.identity_sha256)
    assert normalize_endpoint(raw, route).identity_sha256 == endpoint.identity_sha256


@pytest.mark.parametrize(
    "raw, code",
    [
        ("http://localhost:11434", "hostname_not_literal_loopback"),
        ("http://LOCALHOST:11434", "hostname_not_literal_loopback"),
        ("http://127.0.0.1.attacker.example:11434", "hostname_not_literal_loopback"),
        ("http://127.1:11434", "endpoint_deceptive_identity"),
        ("http://0x7f.0.0.1:11434", "endpoint_deceptive_identity"),
        ("http://2130706433:11434", "endpoint_deceptive_identity"),
        ("http://0177.0.0.1:11434", "endpoint_deceptive_identity"),
        ("http://0.0.0.0:11434", "endpoint_deceptive_identity"),
        ("http://127.0.0.2:11434", "endpoint_deceptive_identity"),
        ("http://[::]:11434", "endpoint_deceptive_identity"),
        ("http://[::ffff:127.0.0.1]:11434", "endpoint_deceptive_identity"),
        ("http://[0:0:0:0:0:0:0:1]:11434", "endpoint_deceptive_identity"),
        ("http://[fe80::1%eth0]:11434", "endpoint_deceptive_identity"),
        ("http://[fe80::1%25eth0]:11434", "endpoint_deceptive_identity"),
        ("http://[127.0.0.1]:11434", "endpoint_deceptive_identity"),
        ("http://xn--80ak6aa92e.example:11434", "endpoint_deceptive_identity"),
        ("http://lоcalhost:11434", "endpoint_deceptive_identity"),
        ("http://127.0.0.1.:11434", "endpoint_deceptive_identity"),
        ("http://%31%32%37.0.0.1:11434", "endpoint_deceptive_identity"),
        ("http://127.0.0.1\\evil:11434", "endpoint_deceptive_identity"),
        ("http://user:secret@127.0.0.1:11434", "endpoint_credentials_embedded"),
        ("http://127.0.0.1@evil.example:11434", "endpoint_credentials_embedded"),
        ("http://127.0.0.1:11434/?q=1", "endpoint_query_or_fragment"),
        ("http://127.0.0.1:11434?q=1", "endpoint_query_or_fragment"),
        ("http://127.0.0.1:11434/#frag", "endpoint_query_or_fragment"),
        ("ftp://127.0.0.1:21", "endpoint_scheme_not_permitted"),
        ("file:///etc/passwd", "endpoint_scheme_not_permitted"),
        ("HTTP://127.0.0.1:11434", "endpoint_scheme_not_permitted"),
        ("127.0.0.1:11434", "endpoint_malformed"),
        ("", "endpoint_malformed"),
        (None, "endpoint_malformed"),
        ("http://", "endpoint_malformed"),
        ("http://127.0.0.1:0", "endpoint_malformed"),
        ("http://127.0.0.1:011434", "endpoint_malformed"),
        ("http://127.0.0.1:99999", "endpoint_malformed"),
        ("http://127.0.0.1:", "endpoint_malformed"),
        ("http://::1:11434", "endpoint_malformed"),
        ("http://[::1:11434", "endpoint_malformed"),
        ("http://127.0.0.1:11434\n", "endpoint_malformed"),
        ("http://127.0.0.1 :11434", "endpoint_malformed"),
    ],
)
def test_rejected_endpoint_forms_have_named_codes(raw, code):
    assert refusal(normalize_endpoint, raw, "local_fast") == code


@pytest.mark.parametrize(
    "raw",
    [
        "/v1/../v2",
        "/./v1",
        "/v1/%2E%2E",
        "/v1%2Fchat",
        "/v1%5C",
        "/v1\\x",
        "//v1",
        "/v1//",
        "/v1//chat",
        "/v 1",
        "v1",
        "/v1;x",
        "/v1:x",
        "/v1@x",
        "/vé",
    ],
)
def test_noncanonical_base_paths_are_rejected(raw):
    assert refusal(canonicalize_base_path, raw) == "endpoint_path_noncanonical"
    if raw.startswith("/"):
        endpoint = "http://127.0.0.1:1234" + raw
        assert refusal(normalize_endpoint, endpoint, "local_fast") == "endpoint_path_noncanonical"


@pytest.mark.parametrize(
    "raw, expected",
    [("", ""), ("/", ""), ("/v1", "/v1"), ("/v1/", "/v1"), ("/compatible-mode/v1", "/compatible-mode/v1")],
)
def test_canonical_base_paths(raw, expected):
    assert canonicalize_base_path(raw) == expected


def test_trailing_slash_is_the_only_normalization_and_is_equivalent():
    with_slash = normalize_endpoint("http://127.0.0.1:1234/v1/", "local_fast")
    without = normalize_endpoint("http://127.0.0.1:1234/v1", "local_fast")
    assert with_slash == without
    assert with_slash.identity_sha256 == without.identity_sha256
    assert (
        normalize_endpoint("http://127.0.0.1:1234/V1", "local_fast").identity_sha256
        != without.identity_sha256
    )


@pytest.mark.parametrize(
    "raw",
    [
        "http://192.168.1.10:11434",
        "http://10.0.0.2:11434",
        "http://172.16.5.4:11434",
        "http://169.254.1.1:11434",
        "http://[fe80::1]:11434",
        "http://[fd00::1]:11434",
    ],
)
def test_lan_addresses_are_not_device_local(raw):
    assert refusal(normalize_endpoint, raw, "local_heavy") == "trusted_lan_not_in_profile"


@pytest.mark.parametrize(
    "raw",
    ["http://203.0.113.5:11434", "http://8.8.8.8:11434", "http://[2001:db8::1]:11434"],
)
def test_remote_addresses_on_local_routes_are_refused(raw):
    assert refusal(normalize_endpoint, raw, "local_fast") == "endpoint_not_device_local"


def test_cloud_identity_is_the_approved_origin_only():
    endpoint = normalize_endpoint(CLOUD_URL, "cloud_primary")
    assert endpoint.canonical == CLOUD_CANONICAL
    assert endpoint.locality == REMOTE_CLOUD
    assert endpoint.profile_id == CLOUD_PROFILE_ID
    assert endpoint.locality != DEVICE_LOOPBACK
    assert normalize_endpoint(CLOUD_CANONICAL + "/", "cloud_secondary").identity_sha256 == (
        endpoint.identity_sha256
    )


@pytest.mark.parametrize(
    "raw, code",
    [
        ("http://dashscope-intl.aliyuncs.com/compatible-mode/v1", "endpoint_scheme_not_permitted"),
        ("https://evil.example/compatible-mode/v1", "cloud_endpoint_not_approved"),
        ("https://dashscope-intl.aliyuncs.com:8443/compatible-mode/v1", "cloud_endpoint_not_approved"),
        ("https://dashscope-intl.aliyuncs.com/compatible-mode/v2", "cloud_endpoint_not_approved"),
        ("https://dashscope-intl.aliyuncs.com", "cloud_endpoint_not_approved"),
        ("https://DASHSCOPE-INTL.ALIYUNCS.COM/compatible-mode/v1", "cloud_endpoint_not_approved"),
        ("https://dashscope-intl.aliyuncs.com.evil.example/compatible-mode/v1", "cloud_endpoint_not_approved"),
        ("https://47.88.1.1/compatible-mode/v1", "cloud_endpoint_not_approved"),
        ("https://127.0.0.1/compatible-mode/v1", "cloud_endpoint_not_approved"),
        ("https://dashscope-intl.aliyuncs.com./compatible-mode/v1", "endpoint_deceptive_identity"),
    ],
)
def test_cloud_substitutions_are_refused(raw, code):
    assert refusal(normalize_endpoint, raw, "cloud_primary") == code


def test_cloud_origin_is_never_device_local():
    assert refusal(normalize_endpoint, CLOUD_URL, "local_fast") == "hostname_not_literal_loopback"


def test_non_network_routes_are_not_normalized():
    with pytest.raises(TypeError):
        normalize_endpoint("http://127.0.0.1:1", "human_handoff")


def test_allowed_request_urls_are_exact_and_closed():
    local = normalize_endpoint("http://127.0.0.1:1234/v1", "local_fast")
    assert allowed_request_urls(local, "openai_compatible") == {
        ("GET", "http://127.0.0.1:1234/v1/models"),
        ("POST", "http://127.0.0.1:1234/v1/chat/completions"),
    }
    ollama = normalize_endpoint("http://127.0.0.1:11434", "local_fast")
    assert allowed_request_urls(ollama, "ollama") == {
        ("GET", "http://127.0.0.1:11434/api/tags"),
        ("POST", "http://127.0.0.1:11434/api/chat"),
    }
    cloud = normalize_endpoint(CLOUD_URL, "cloud_primary")
    assert allowed_request_urls(cloud, "qwen") == {
        ("POST", CLOUD_CANONICAL + "/chat/completions"),
    }
    assert refusal(allowed_request_urls, local, "grpc") == "backend_protocol_unsupported"


# --- Effective configuration -------------------------------------------------------


def test_defaults_resolve_to_literal_loopback_presets():
    configuration = resolve_effective_configuration({}, None)
    assert configuration.backend_type.value == "lmstudio"
    assert configuration.backend_type.source == "preset"
    assert configuration.local_base_url.value == "http://127.0.0.1:1234/v1"
    assert configuration.local_base_url.source == "preset"
    assert configuration.model.value == "auto"
    assert configuration.timeout_seconds.value == 30
    assert configuration.cloud_enabled.value is False
    assert configuration.cloud_model.value == "qwen-max"
    assert configuration.cloud_base_url.value == CLOUD_URL
    assert configuration.cloud_api_key_present is False
    for preset in dp.GOVERNED_LOCAL_PRESETS.values():
        if preset is not None:
            assert normalize_endpoint(preset, "local_fast").locality == DEVICE_LOOPBACK


def test_precedence_env_then_toml_then_backend_env_then_preset():
    toml = {"backend": {"default_type": "ollama", "base_url": "http://127.0.0.1:11434"}}
    from_toml = resolve_effective_configuration({}, toml)
    assert from_toml.backend_type.source == "toml:triagecore.toml"
    assert from_toml.local_base_url.source == "toml:triagecore.toml"

    from_env = resolve_effective_configuration({"TRIAGE_BASE_URL": "http://127.0.0.1:5"}, toml)
    assert from_env.local_base_url.value == "http://127.0.0.1:5"
    assert from_env.local_base_url.source == "env:TRIAGE_BASE_URL"

    fallthrough = resolve_effective_configuration(
        {"TRIAGE_BASE_URL": "", "TRIAGE_OLLAMA_BASE_URL": "http://127.0.0.1:7"},
        {"backend": {"default_type": "ollama", "base_url": ""}},
    )
    assert fallthrough.local_base_url.value == "http://127.0.0.1:7"
    assert fallthrough.local_base_url.source == "backend_env:TRIAGE_OLLAMA_BASE_URL"

    supervisor = resolve_effective_configuration(
        {"TRIAGE_SUPERVISOR_BASE_URL": "http://127.0.0.1:8"}, None
    )
    assert supervisor.local_base_url.source == "backend_env:TRIAGE_SUPERVISOR_BASE_URL"


def test_present_but_empty_backend_type_means_ollama_as_create_backend_does():
    configuration = resolve_effective_configuration({"TRIAGE_BACKEND_TYPE": ""}, None)
    assert configuration.backend_type.value == ""
    assert configuration.backend_type.source == "env:TRIAGE_BACKEND_TYPE"
    assert dp.backend_protocol_key(configuration.backend_type.value) == "ollama"
    assert configuration.local_base_url.value == "http://127.0.0.1:11434"


def test_api_key_presence_is_recorded_never_its_value():
    secret = "sk-test-0123456789abcdef"
    configuration = resolve_effective_configuration({"TRIAGE_QWEN_API_KEY": secret}, None)
    assert configuration.cloud_api_key_present is True
    assert secret not in repr(configuration)


def test_empty_base_url_variable_beats_toml_and_falls_through_to_backend_env():
    """Review finding 1: the exact conflicting case."""

    configuration = resolve_effective_configuration(
        {"TRIAGE_BASE_URL": "", "TRIAGE_OLLAMA_BASE_URL": "http://127.0.0.1:7"},
        {"backend": {"default_type": "ollama", "base_url": "http://127.0.0.1:5"}},
    )
    assert configuration.local_base_url.value == "http://127.0.0.1:7"
    assert configuration.local_base_url.source == "backend_env:TRIAGE_OLLAMA_BASE_URL"


def test_empty_cloud_url_layers_follow_create_backend():
    from_toml = resolve_effective_configuration({}, {"qwen": {"base_url": ""}})
    assert from_toml.cloud_base_url.value == CLOUD_URL
    assert from_toml.cloud_base_url.source == "preset"
    from_env = resolve_effective_configuration(
        {"TRIAGE_QWEN_BASE_URL": "", "TRIAGE_QWEN_ENABLED": "1"},
        {"qwen": {"base_url": "https://evil.example/v1"}},
    )
    assert from_env.cloud_base_url.value == ""
    assert refusal(bind_route_endpoints, ("cloud_primary",), from_env) == "endpoint_malformed"


def test_cloud_enable_flag_parsing():
    assert resolve_effective_configuration({"TRIAGE_QWEN_ENABLED": "yes"}, None).cloud_enabled.value
    assert not resolve_effective_configuration({"TRIAGE_QWEN_ENABLED": "no"}, None).cloud_enabled.value
    toml = resolve_effective_configuration({}, {"qwen": {"enabled": True}})
    assert toml.cloud_enabled.value is True
    assert toml.cloud_enabled.source == "toml:triagecore.toml"


@pytest.mark.parametrize(
    "env, toml",
    [
        ({}, UNREADABLE_CONFIGURATION),
        ({}, {"backend": "not-a-table"}),
        ({}, {"qwen": ["not", "a", "table"]}),
        ({}, ["not", "a", "mapping"]),
        ({"TRIAGE_TIMEOUT_SECONDS": "abc"}, None),
        ({"TRIAGE_TIMEOUT_SECONDS": ""}, None),
        ({}, {"backend": {"timeout_seconds": "soon"}}),
    ],
)
def test_unusable_configuration_refuses_instead_of_defaulting(env, toml):
    assert refusal(resolve_effective_configuration, env, toml) == "configuration_unreadable"


def test_cloud_model_sentinel_substitution_and_unbound_refusal():
    substituted = resolve_effective_configuration({}, {"qwen": {"model": "auto"}})
    assert substituted.cloud_model.value == "qwen-max"
    unbound = resolve_effective_configuration(
        {"TRIAGE_QWEN_MODEL": "auto", "TRIAGE_QWEN_ENABLED": "1"}, None
    )
    assert refusal(bind_route_endpoints, ("cloud_primary",), unbound) == "cloud_model_unbound"


# --- Route binding -----------------------------------------------------------------


def test_binding_follows_envelope_order_and_skips_non_network_routes():
    configuration = resolve_effective_configuration({}, None)
    bindings = bind_route_endpoints(
        ("local_heavy", "human_handoff", "local_fast", "deterministic"), configuration
    )
    assert [b.route for b in bindings] == ["local_heavy", "local_fast"]
    assert all(b.locality == DEVICE_LOOPBACK for b in bindings)
    assert all(b.protocol == "openai_compatible" for b in bindings)
    assert bindings[0].binding_line().startswith(
        "route=local_heavy;profile=device_local_loopback.v1;class=device_loopback;"
        "protocol=openai_compatible;identity_sha256=sha256:"
    )


def test_cloud_route_is_bound_only_when_cloud_is_enabled():
    disabled = resolve_effective_configuration({}, None)
    assert [b.route for b in bind_route_endpoints(("local_fast", "cloud_primary"), disabled)] == [
        "local_fast"
    ]
    enabled = resolve_effective_configuration({"TRIAGE_QWEN_ENABLED": "1"}, None)
    bindings = bind_route_endpoints(("local_fast", "cloud_primary"), enabled)
    assert [(b.route, b.locality) for b in bindings] == [
        ("local_fast", DEVICE_LOOPBACK),
        ("cloud_primary", REMOTE_CLOUD),
    ]


def test_any_unapproved_member_refuses_the_whole_binding():
    bad_cloud = resolve_effective_configuration(
        {"TRIAGE_QWEN_ENABLED": "1", "TRIAGE_QWEN_BASE_URL": "https://evil.example/v1"}, None
    )
    assert (
        refusal(bind_route_endpoints, ("local_fast", "cloud_primary"), bad_cloud)
        == "cloud_endpoint_not_approved"
    )
    remote_local = resolve_effective_configuration(
        {"TRIAGE_BASE_URL": "http://203.0.113.5:11434"}, None
    )
    assert (
        refusal(bind_route_endpoints, ("local_fast", "cloud_primary"), remote_local)
        == "endpoint_not_device_local"
    )


def test_binding_refusals_for_missing_url_and_unknown_protocol():
    custom = resolve_effective_configuration({"TRIAGE_BACKEND_TYPE": "custom"}, None)
    assert custom.local_base_url.source == "absent"
    assert refusal(bind_route_endpoints, ("local_fast",), custom) == "endpoint_malformed"
    unknown = resolve_effective_configuration(
        {"TRIAGE_BACKEND_TYPE": "mystery", "TRIAGE_BASE_URL": "http://127.0.0.1:9"}, None
    )
    assert refusal(bind_route_endpoints, ("local_fast",), unknown) == "backend_protocol_unsupported"


def test_envelope_contract_violations_are_programming_errors():
    configuration = resolve_effective_configuration({}, None)
    with pytest.raises(TypeError):
        bind_route_endpoints(("local_fast", "local_fast"), configuration)
    with pytest.raises(TypeError):
        bind_route_endpoints(("warp_drive",), configuration)
    with pytest.raises(TypeError):
        bind_route_endpoints("local_fast", configuration)


# --- Deterministic digests ---------------------------------------------------------


def _lines(env, envelope=("local_fast", "local_heavy"), policy=DEFAULT_TRANSPORT_POLICY):
    configuration = resolve_effective_configuration(env, None)
    return binding_digest_lines(bind_route_endpoints(envelope, configuration), policy)


GET_ONLY_OPENAI = TransportPolicy(
    calls=(
        ("ollama", dp.PROTOCOL_CALLS["ollama"]),
        ("openai_compatible", (("GET", "models"),)),
        ("qwen", dp.PROTOCOL_CALLS["qwen"]),
    )
)


def test_digest_lines_change_with_port_order_and_policy():
    base = _lines({})
    assert base[0] == "destination_binding_version=triagecore.destination_binding.v1"
    assert base[-2] == f"transport_policy_sha256={DEFAULT_TRANSPORT_POLICY.sha256}"
    assert base[-1] == f"destination_profiles_sha256={dp.destination_profiles_sha256()}"
    assert _lines({"TRIAGE_BASE_URL": "http://127.0.0.1:1235/v1"}) != base
    assert _lines({}, envelope=("local_heavy", "local_fast")) != base
    assert _lines({}, policy=GET_ONLY_OPENAI) != base
    assert GET_ONLY_OPENAI.sha256 != DEFAULT_TRANSPORT_POLICY.sha256
    assert _lines({}) == base


@pytest.mark.parametrize(
    "overrides",
    [
        {"trust_env": True},
        {"proxies": (("http", "http://127.0.0.1:3128"),)},
        {"redirects": "follow"},
        {"max_redirects": 1},
        {"max_redirects": False},
        {"tls_verify": False},
        {"version": "triagecore.transport_policy.v0"},
        {"calls": (("openai_compatible", (("POST", "embeddings"),)),)},
        {"calls": (("grpc", (("POST", "x"),)),)},
        {"calls": (("qwen", (("GET", "models"),)),)},
        {"calls": (("qwen", ()), ("qwen", ()))},
        {"calls": (("ollama", (("GET", "api/tags"), ("GET", "api/tags"))),)},
    ],
    ids=lambda overrides: "-".join(f"{k}={v!r}"[:40] for k, v in overrides.items()),
)
def test_transport_policy_cannot_weaken_the_v1_floor(overrides):
    with pytest.raises(TypeError):
        TransportPolicy(**overrides)


def test_policy_digest_is_independent_of_runtime_objects():
    configuration = resolve_effective_configuration({}, None)
    (binding,) = bind_route_endpoints(("local_fast",), configuration)
    plain = GuardedTransport(binding)
    adapter = RecordingAdapter()
    mounted = GuardedTransport(binding, adapters={"http://": adapter})
    assert plain.transport_policy_sha256 == mounted.transport_policy_sha256
    assert plain.transport_policy_sha256 == DEFAULT_TRANSPORT_POLICY.sha256
    assert plain.bound_identity_sha256 == mounted.bound_identity_sha256
    # Runtime seals are per instance and process-specific; they never enter a digest.
    assert plain._seal != mounted._seal
    assert binding_digest_lines((binding,)) == binding_digest_lines((binding,))


def test_digests_are_identical_across_processes():
    script = (
        "import json\n"
        "from triage_core import destination_policy as dp\n"
        "from requests.adapters import HTTPAdapter\n"
        "c = dp.resolve_effective_configuration({'TRIAGE_QWEN_ENABLED': '1'}, None)\n"
        "b = dp.bind_route_endpoints(('local_fast', 'cloud_primary'), c)\n"
        "dp.GuardedTransport(b[0], adapters={'http://': HTTPAdapter()})\n"
        "print(json.dumps(list(dp.binding_digest_lines(b))))\n"
    )
    outputs = [
        subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(MODULE_PATH.parent.parent),
        ).stdout
        for _ in range(2)
    ]
    configuration = resolve_effective_configuration({"TRIAGE_QWEN_ENABLED": "1"}, None)
    here = list(binding_digest_lines(bind_route_endpoints(("local_fast", "cloud_primary"), configuration)))
    assert json.loads(outputs[0]) == json.loads(outputs[1]) == here


# --- Error provenance and vocabulary -----------------------------------------------


def test_destination_error_is_not_a_swallowable_type():
    assert not issubclass(DestinationPolicyError, requests.RequestException)
    assert not issubclass(DestinationPolicyError, ValueError)
    with pytest.raises(TypeError):
        DestinationPolicyError("not_a_code")


@pytest.mark.parametrize(
    "raw, route",
    [
        ("http://user:secret@203.0.113.5:1/x?token=abc", "local_fast"),
        ("https://evil.example/secret-path", "cloud_primary"),
        ("http://203.0.113.5:4444/private", "local_fast"),
    ],
)
def test_refusal_messages_never_carry_raw_input(raw, route):
    with pytest.raises(DestinationPolicyError) as info:
        normalize_endpoint(raw, route)
    text = str(info.value)
    for fragment in ("secret", "203.0.113.5", "token", "evil.example", "private", "4444"):
        assert fragment not in text


def _string_codes_raised_in_module():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    codes = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and node.args:
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name in {"DestinationPolicyError", "_refuse"}:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    codes.add(first.value)
    return codes


def test_reason_code_vocabulary_is_closed_and_complete():
    accepted = {
        "endpoint_malformed",
        "endpoint_scheme_not_permitted",
        "endpoint_credentials_embedded",
        "endpoint_query_or_fragment",
        "hostname_not_literal_loopback",
        "endpoint_deceptive_identity",
        "endpoint_not_device_local",
        "trusted_lan_not_in_profile",
        "cloud_endpoint_not_approved",
        "endpoint_path_noncanonical",
        "cloud_model_unbound",
        "configuration_unreadable",
        "destination_binding_mismatch",
        "transport_not_guarded",
        "transport_settings_changed",
        "transport_request_not_permitted",
        "endpoint_redirect_refused",
    }
    # One code beyond CR-135's list, flagged for implementation-acceptance review.
    assert dp.REASON_CODES == accepted | {"backend_protocol_unsupported"}
    assert _string_codes_raised_in_module() <= dp.REASON_CODES


def test_module_imports_only_stdlib_and_requests():
    tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative imports would reach triage_core"
            roots.add(node.module.split(".")[0])
    assert roots <= {
        "__future__",
        "dataclasses",
        "hashlib",
        "ipaddress",
        "json",
        "re",
        "typing",
        "requests",
    }
    assert "triage_core" not in roots


# --- Guarded transport -------------------------------------------------------------


def test_guard_permits_bound_requests_and_records_safe_evidence():
    guard, _owner, adapter, binding = make_guard()
    base = binding.endpoint.canonical
    guard.verify_integrity()
    guard.get(base + "/models", timeout=2)
    guard.post(base + "/chat/completions", json={"model": "fixed"}, timeout=5)
    assert [(c["method"], c["url"]) for c in adapter.calls] == [
        ("GET", "http://127.0.0.1:1234/v1/models"),
        ("POST", "http://127.0.0.1:1234/v1/chat/completions"),
    ]
    assert all(c["proxies"] == {} and c["verify"] is True and c["cert"] is None for c in adapter.calls)
    assert [(s.method, s.suffix, s.status_code) for s in guard.sends] == [
        ("GET", "models", 200),
        ("POST", "chat/completions", 200),
    ]
    for record in guard.sends:
        assert record.safe_label == "loopback-ipv4:1234"
        assert "127.0.0.1" not in repr(record)
    assert guard.refusal is None


def test_guard_owner_identity_mismatch_refuses_even_with_allowed_url():
    """F7(g): the POST URL is built before discovery, as both backends do."""

    guard, owner, adapter, binding = make_guard()
    post_url = owner.base_url.rstrip("/") + "/chat/completions"
    guard.get(owner.base_url + "/models")
    owner.base_url = "http://127.0.0.1:9999/v1"
    assert ("POST", post_url) in binding.allowed_requests
    assert refusal(guard.post, post_url, json={}) == "destination_binding_mismatch"
    assert len(adapter.calls) == 1
    assert [s.suffix for s in guard.sends] == ["models"]
    assert refusal(guard.get, post_url.replace("chat/completions", "models")) == (
        "destination_binding_mismatch"
    )
    assert len(adapter.calls) == 1


def test_guard_owner_mutation_before_first_send_is_refused():
    guard, owner, adapter, _binding = make_guard()
    owner.base_url = "http://203.0.113.5:1234/v1"
    assert refusal(guard.verify_integrity) == "destination_binding_mismatch"
    assert adapter.calls == []


def _set_trust_env(session):
    session.trust_env = True


def _set_proxy(session):
    session.proxies["http"] = "http://127.0.0.1:3128"


def _disable_verify(session):
    session.verify = False


def _mount_adapter(session):
    session.mount("http://127.0.0.1", RecordingAdapter())


def _add_hook(session):
    session.hooks["response"].append(lambda response, **kwargs: response)


def _set_auth(session):
    session.auth = ("user", "pass")


def _set_cert(session):
    session.cert = "/tmp/client.pem"


def _raise_redirect_limit(session):
    session.max_redirects = 30


def _set_authorization_header(session):
    session.headers["Authorization"] = "Bearer injected"


def _change_default_header(session):
    session.headers["User-Agent"] = "spoofed"


def _set_cookie(session):
    session.cookies.set("session", "injected")


def _set_params(session):
    session.params = {"q": "1"}


SESSION_MUTATIONS = [
    _set_trust_env,
    _set_proxy,
    _disable_verify,
    _mount_adapter,
    _add_hook,
    _set_auth,
    _set_cert,
    _raise_redirect_limit,
    _set_authorization_header,
    _change_default_header,
    _set_cookie,
    _set_params,
]


@pytest.mark.parametrize("mutate", SESSION_MUTATIONS, ids=lambda f: f.__name__)
def test_guard_session_mutation_refused_at_integrity_check(mutate):
    """F7(e1): detected by the S2 integrity check, before any send."""

    guard, _owner, adapter, _binding = make_guard()
    mutate(guard._session)
    assert refusal(guard.verify_integrity) == "transport_settings_changed"
    assert adapter.calls == []


@pytest.mark.parametrize("mutate", SESSION_MUTATIONS, ids=lambda f: f.__name__)
def test_guard_session_mutation_refused_before_send(mutate):
    """F7(e2): after the integrity check, before the first request."""

    guard, owner, adapter, _binding = make_guard()
    guard.verify_integrity()
    mutate(guard._session)
    assert refusal(guard.get, owner.base_url + "/models") == "transport_settings_changed"
    assert adapter.calls == []


@pytest.mark.parametrize("mutate", SESSION_MUTATIONS, ids=lambda f: f.__name__)
def test_guard_session_mutation_between_discovery_and_generation(mutate):
    """F7(e3): one permitted discovery request, then zero additional."""

    guard, owner, adapter, _binding = make_guard()
    guard.get(owner.base_url + "/models")
    mutate(guard._session)
    assert refusal(guard.post, owner.base_url + "/chat/completions", json={}) == (
        "transport_settings_changed"
    )
    assert len(adapter.calls) == 1
    assert [s.suffix for s in guard.sends] == ["models"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"proxies": {"http": "http://127.0.0.1:3128"}},
        {"verify": False},
        {"cert": "/tmp/client.pem"},
        {"allow_redirects": True},
        {"auth": ("user", "pass")},
        {"hooks": {"response": []}},
        {"data": b"raw"},
        {"params": {"q": "1"}},
    ],
    ids=lambda kwargs: next(iter(kwargs)),
)
def test_guard_refuses_behaviour_changing_call_arguments(kwargs):
    guard, owner, adapter, _binding = make_guard()
    assert refusal(guard.post, owner.base_url + "/chat/completions", **kwargs) == (
        "transport_settings_changed"
    )
    assert adapter.calls == []


def test_guard_accepts_explicit_allow_redirects_false():
    guard, owner, adapter, _binding = make_guard()
    guard.get(owner.base_url + "/models", allow_redirects=False)
    assert len(adapter.calls) == 1


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
@pytest.mark.parametrize("stream", [False, True])
def test_guard_redirects_on_generation_are_late_refusals(status, stream):
    """F8 (adapter level): a fixed model, so the POST is the first and only request."""

    guard, owner, adapter, _binding = make_guard(statuses=[status])
    url = owner.base_url + "/chat/completions"
    assert refusal(guard.post, url, json={"model": "fixed", "marker": "M04-PROTECTED"}, stream=stream) == (
        "endpoint_redirect_refused"
    )
    assert [c["url"] for c in adapter.calls] == [url]
    assert [(s.suffix, s.status_code) for s in guard.sends] == [("chat/completions", status)]
    assert refusal(guard.post, url, json={}) == "endpoint_redirect_refused"
    assert len(adapter.calls) == 1


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_guard_redirects_on_discovery_are_late_refusals(status):
    guard, owner, adapter, _binding = make_guard(statuses=[status])
    assert refusal(guard.get, owner.base_url + "/models") == "endpoint_redirect_refused"
    assert len(adapter.calls) == 1
    assert refusal(guard.post, owner.base_url + "/chat/completions", json={}) == (
        "endpoint_redirect_refused"
    )
    assert len(adapter.calls) == 1


@pytest.mark.parametrize(
    "method, url",
    [
        ("POST", "http://127.0.0.1:1234/v1evil/chat/completions"),
        ("POST", "http://127.0.0.1:1234/v1//chat/completions"),
        ("POST", "http://127.0.0.1:1234/V1/chat/completions"),
        ("POST", "http://127.0.0.1:1234/v1/../chat/completions"),
        ("POST", "http://127.0.0.1:1234/v1/chat/completions?x=1"),
        ("POST", "http://127.0.0.1:1235/v1/chat/completions"),
        ("POST", "http://localhost:1234/v1/chat/completions"),
        ("POST", "http://127.0.0.1/v1/chat/completions"),
        ("POST", "https://127.0.0.1:1234/v1/chat/completions"),
        ("POST", "http://user@127.0.0.1:1234/v1/chat/completions"),
        ("POST", "http://127.0.0.1:1234/v1/embeddings"),
        ("GET", "http://127.0.0.1:1234/v1/chat/completions"),
        ("POST", "http://127.0.0.1:1234/v1/models"),
        ("POST", "http://203.0.113.5:1234/v1/chat/completions"),
    ],
)
def test_guard_refuses_collisions_and_off_set_urls_before_send(method, url):
    guard, _owner, adapter, _binding = make_guard()
    send = guard.post if method == "POST" else guard.get
    assert refusal(send, url, json={}) == "transport_request_not_permitted"
    assert adapter.calls == []


def test_guard_compares_the_url_actually_sent():
    """A dot segment that Requests resolves to the bound URL is the same wire request."""

    guard, _owner, adapter, _binding = make_guard()
    guard.post("http://127.0.0.1:1234/v1/x/../chat/completions", json={})
    assert [c["url"] for c in adapter.calls] == ["http://127.0.0.1:1234/v1/chat/completions"]


def test_guard_ignores_environment_proxies_netrc_and_ca_bundle(monkeypatch, tmp_path):
    """F9 (unit level). Full proof needs the loopback-server harness in slice 2."""

    netrc = tmp_path / ".netrc"
    netrc.write_text("machine 127.0.0.1 login envuser password envpass\n", encoding="utf-8")
    netrc.chmod(0o600)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("NETRC", str(netrc))
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.setenv(name, "http://127.0.0.1:3128")
    for name in ("NO_PROXY", "no_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(tmp_path / "missing-ca.pem"))

    url = "http://127.0.0.1:1234/v1/models"
    # Positive controls: an ordinary session in this environment would pick these up.
    ordinary = requests.Session().prepare_request(requests.Request("GET", url))
    assert "Authorization" in ordinary.headers
    assert requests.utils.get_environ_proxies(url).get("http") == "http://127.0.0.1:3128"

    guard, _owner, adapter, _binding = make_guard()
    guard.get(url)
    (call,) = adapter.calls
    assert call["proxies"] == {}
    assert "Authorization" not in call["headers"]
    assert call["verify"] is True


def test_guard_cloud_route_permits_only_generation_on_the_canonical_url():
    guard, owner, adapter, _binding = make_guard(url=CLOUD_URL, route="cloud_primary", cloud=True)
    assert owner.base_url == CLOUD_CANONICAL
    assert refusal(make_guard(url=CLOUD_URL, route="cloud_primary", cloud=True)[0].get,
                   CLOUD_CANONICAL + "/models") == "transport_request_not_permitted"
    # The default-port spelling is a different wire URL; slice 2 must build request URLs
    # from the canonical endpoint.
    assert refusal(guard.post, CLOUD_URL + "/chat/completions", json={}) == (
        "transport_request_not_permitted"
    )
    fresh, fresh_owner, fresh_adapter, _ = make_guard(url=CLOUD_URL, route="cloud_primary", cloud=True)
    fresh.post(fresh_owner.base_url + "/chat/completions", json={"model": "qwen-max"})
    assert [c["url"] for c in fresh_adapter.calls] == [CLOUD_CANONICAL + "/chat/completions"]
    assert adapter.calls == []


def test_guard_requires_a_single_matching_owner():
    configuration = resolve_effective_configuration({}, None)
    (binding,) = bind_route_endpoints(("local_fast",), configuration)
    adapter = RecordingAdapter()
    unbound = GuardedTransport(binding, adapters={"http://": adapter})
    assert refusal(unbound.get, binding.endpoint.canonical + "/models") == "transport_not_guarded"
    assert adapter.calls == []

    second = GuardedTransport(binding)
    assert refusal(second.verify_integrity) == "transport_not_guarded"

    wrong = GuardedTransport(binding)
    assert refusal(wrong.bind_owner, StubBackend("http://127.0.0.1:9/v1")) == (
        "destination_binding_mismatch"
    )

    right = GuardedTransport(binding)
    right.bind_owner(StubBackend(binding.endpoint.canonical))
    assert refusal(right.bind_owner, StubBackend(binding.endpoint.canonical)) == (
        "destination_binding_mismatch"
    )


def test_guard_enforces_a_policy_that_removes_post():
    """Review finding 2: the guard's permitted calls come from the policy."""

    configuration = resolve_effective_configuration({}, None)
    (binding,) = bind_route_endpoints(("local_fast",), configuration)
    adapter = RecordingAdapter()
    guard = GuardedTransport(
        binding, policy=GET_ONLY_OPENAI, adapters={"http://": adapter, "https://": adapter}
    )
    guard.bind_owner(StubBackend(binding.endpoint.canonical))
    assert guard.transport_policy_sha256 == GET_ONLY_OPENAI.sha256
    assert ("POST", binding.endpoint.canonical + "/chat/completions") in binding.allowed_requests
    assert refusal(guard.post, binding.endpoint.canonical + "/chat/completions", json={}) == (
        "transport_request_not_permitted"
    )
    assert adapter.calls == []


def test_guard_permits_the_calls_a_tightened_policy_keeps():
    configuration = resolve_effective_configuration({}, None)
    (binding,) = bind_route_endpoints(("local_fast",), configuration)
    adapter = RecordingAdapter()
    guard = GuardedTransport(binding, policy=GET_ONLY_OPENAI, adapters={"http://": adapter})
    guard.bind_owner(StubBackend(binding.endpoint.canonical))
    guard.get(binding.endpoint.canonical + "/models")
    assert [c["method"] for c in adapter.calls] == ["GET"]


def test_policy_omitting_a_protocol_permits_nothing_for_it():
    policy = TransportPolicy(calls=(("ollama", dp.PROTOCOL_CALLS["ollama"]),))
    configuration = resolve_effective_configuration({}, None)
    (binding,) = bind_route_endpoints(("local_fast",), configuration)
    adapter = RecordingAdapter()
    guard = GuardedTransport(binding, policy=policy, adapters={"http://": adapter})
    guard.bind_owner(StubBackend(binding.endpoint.canonical))
    assert refusal(guard.get, binding.endpoint.canonical + "/models") == (
        "transport_request_not_permitted"
    )
    assert adapter.calls == []


def _local_binding():
    configuration = resolve_effective_configuration({}, None)
    (binding,) = bind_route_endpoints(("local_fast",), configuration)
    return binding


def _bound_guard(binding, policy):
    adapter = RecordingAdapter()
    guard = GuardedTransport(binding, policy=policy, adapters={"http://": adapter})
    guard.bind_owner(StubBackend(binding.endpoint.canonical))
    return guard, adapter


def test_policy_ignores_caller_mutation_after_the_guard_is_built():
    """Corrective review case A: tightening the caller's list afterwards changes nothing."""

    binding = _local_binding()
    calls = [("openai_compatible", (("GET", "models"), ("POST", "chat/completions")))]
    policy = TransportPolicy(calls=calls)
    digest = policy.sha256
    guard, adapter = _bound_guard(binding, policy)
    calls[0] = ("openai_compatible", (("GET", "models"),))
    assert type(policy.calls) is tuple
    assert policy.sha256 == digest == guard.transport_policy_sha256
    guard.post(binding.endpoint.canonical + "/chat/completions", json={})
    assert [c["method"] for c in adapter.calls] == ["POST"]


def test_policy_mutation_before_the_guard_cannot_widen_the_floor():
    """Corrective review case B: a post-validation swap cannot add a call."""

    binding = _local_binding()
    calls = [("openai_compatible", (("GET", "models"),))]
    policy = TransportPolicy(calls=calls)
    calls[0] = ("openai_compatible", (("GET", "models"), ("POST", "embeddings")))
    guard, adapter = _bound_guard(binding, policy)
    assert policy.permitted_calls("openai_compatible") == (("GET", "models"),)
    assert refusal(guard.post, binding.endpoint.canonical + "/embeddings", json={}) == (
        "transport_request_not_permitted"
    )
    assert adapter.calls == []


def test_policy_inner_list_mutation_cannot_widen_the_floor():
    """Corrective review case C: the inner call list is copied, not referenced."""

    binding = _local_binding()
    inner = [["GET", "models"]]
    policy = TransportPolicy(calls=(("openai_compatible", inner),))
    inner.append(["POST", "embeddings"])
    inner[0][1] = "embeddings"
    guard, adapter = _bound_guard(binding, policy)
    assert policy.permitted_calls("openai_compatible") == (("GET", "models"),)
    assert refusal(guard.post, binding.endpoint.canonical + "/embeddings", json={}) == (
        "transport_request_not_permitted"
    )
    guard_get, adapter_get = _bound_guard(binding, policy)
    guard_get.get(binding.endpoint.canonical + "/models")
    assert adapter.calls == [] and len(adapter_get.calls) == 1


def test_policy_input_order_and_container_type_do_not_change_the_digest():
    reordered = [
        ["qwen", [["POST", "chat/completions"]]],
        ["openai_compatible", [["POST", "chat/completions"], ["GET", "models"]]],
        ["ollama", [["POST", "api/chat"], ["GET", "api/tags"]]],
    ]
    assert TransportPolicy(calls=reordered).sha256 == DEFAULT_TRANSPORT_POLICY.sha256
    assert TransportPolicy(calls=reordered).calls == DEFAULT_TRANSPORT_POLICY.calls


@pytest.mark.parametrize(
    "kwargs",
    [
        {"calls": "openai_compatible"},
        {"calls": {"openai_compatible": (("GET", "models"),)}},
        {"calls": [("openai_compatible",)]},
        {"calls": [("openai_compatible", "GET models")]},
        {"calls": [("openai_compatible", [("GET",)])]},
        {"calls": [("openai_compatible", [("GET", "models", "extra")])]},
        {"calls": [("openai_compatible", [("GET", 1)])]},
        {"calls": [(1, [("GET", "models")])]},
        {"calls": [("openai_compatible", {("GET", "models")})]},
        {"proxies": []},
    ],
    ids=lambda kwargs: repr(kwargs)[:50],
)
def test_policy_rejects_malformed_call_structures(kwargs):
    with pytest.raises(TypeError):
        TransportPolicy(**kwargs)


def test_guard_refuses_every_send_after_policy_tampering():
    """Defence in depth: a policy changed by bypassing the frozen dataclass."""

    binding = _local_binding()
    policy = TransportPolicy()
    guard, adapter = _bound_guard(binding, policy)
    object.__setattr__(policy, "calls", (("openai_compatible", (("GET", "models"),)),))
    assert refusal(guard.verify_integrity) == "transport_settings_changed"
    assert refusal(guard.get, binding.endpoint.canonical + "/models") == (
        "transport_settings_changed"
    )
    assert adapter.calls == []


def test_guard_enforces_the_binding_allowlist_as_well_as_the_policy():
    """Third corrective review, finding 1: the intersection of both allowlists."""

    binding = _local_binding()
    empty = dataclasses.replace(binding, allowed_requests=frozenset())
    for method, suffix in (("get", "/models"), ("post", "/chat/completions")):
        guard, adapter = _bound_guard(empty, DEFAULT_TRANSPORT_POLICY)
        send = getattr(guard, method)
        assert refusal(send, binding.endpoint.canonical + suffix, json={}) == (
            "transport_request_not_permitted"
        )
        assert adapter.calls == []

    get_only = dataclasses.replace(
        binding,
        allowed_requests=frozenset({("GET", binding.endpoint.canonical + "/models")}),
    )
    guard, adapter = _bound_guard(get_only, DEFAULT_TRANSPORT_POLICY)
    guard.get(binding.endpoint.canonical + "/models")
    assert refusal(guard.post, binding.endpoint.canonical + "/chat/completions", json={}) == (
        "transport_request_not_permitted"
    )
    assert [c["method"] for c in adapter.calls] == ["GET"]


def test_guard_never_inherits_session_state_even_if_the_seal_were_bypassed():
    """Third corrective review, finding 2: session state cannot reach the wire."""

    binding = _local_binding()
    guard, adapter = _bound_guard(binding, DEFAULT_TRANSPORT_POLICY)
    guard._session.headers["Authorization"] = "Bearer injected"
    guard._session.cookies.set("session", "injected")
    guard._session.auth = None
    guard._seal = guard._session_fingerprint()  # simulate a bypassed seal
    guard.post(binding.endpoint.canonical + "/chat/completions", json={"model": "fixed"})
    (call,) = adapter.calls
    assert "Authorization" not in call["headers"]
    assert "Cookie" not in call["headers"]


def test_guard_headers_match_an_ordinary_session_and_keep_call_headers():
    binding = _local_binding()
    guard, adapter = _bound_guard(binding, DEFAULT_TRANSPORT_POLICY)
    url = binding.endpoint.canonical + "/chat/completions"
    guard.post(url, json={"model": "fixed"}, headers={"X-Test": "1"})
    expected = requests.Session().prepare_request(
        requests.Request("POST", url, json={"model": "fixed"}, headers={"X-Test": "1"})
    )
    (call,) = adapter.calls
    assert call["headers"] == dict(expected.headers)
    assert call["headers"]["X-Test"] == "1"


def test_guard_refuses_malformed_call_headers_without_sending():
    binding = _local_binding()
    guard, adapter = _bound_guard(binding, DEFAULT_TRANSPORT_POLICY)
    assert refusal(guard.get, binding.endpoint.canonical + "/models", headers=["bad"]) == (
        "transport_request_not_permitted"
    )
    assert adapter.calls == []


def test_verify_integrity_reports_a_latched_refusal():
    """Third corrective review, finding 3."""

    binding = _local_binding()
    guard, adapter = _bound_guard(binding, DEFAULT_TRANSPORT_POLICY)
    assert refusal(guard.post, binding.endpoint.canonical + "/embeddings", json={}) == (
        "transport_request_not_permitted"
    )
    assert refusal(guard.verify_integrity) == "transport_request_not_permitted"
    assert adapter.calls == []


def test_guard_construction_requires_contract_types():
    with pytest.raises(TypeError):
        GuardedTransport("not-a-binding")


# --- Parity with the existing runtime configuration path ---------------------------
#
# These tests import config.py and backends.py to compare the pure resolver with the
# behaviour governed ``tc run`` has at the baseline. They are verification only; the
# module under test still imports neither.

LEGACY_LOCAL_PRESETS = {
    "ollama": "http://localhost:11434",
    "lmstudio": "http://localhost:1234/v1",
    "vllm": "http://localhost:8000/v1",
    "custom": None,
}
_ABSENT = object()


def _toml_text(sections):
    lines = []
    for section, values in sections.items():
        present = {k: v for k, v in values.items() if v is not _ABSENT}
        if not present:
            continue
        lines.append(f"[{section}]")
        for key, value in present.items():
            rendered = ("true" if value else "false") if isinstance(value, bool) else json.dumps(value)
            lines.append(f"{key} = {rendered}")
    return "\n".join(lines) + "\n"


def _toml_mapping(sections):
    return {
        section: {k: v for k, v in values.items() if v is not _ABSENT}
        for section, values in sections.items()
    }


def _runtime(monkeypatch, tmp_path, env, sections):
    from triage_core.config import Config

    for name in list(os.environ):
        if name.startswith("TRIAGE_"):
            monkeypatch.delenv(name)
    for name, value in env.items():
        if value is not _ABSENT:
            monkeypatch.setenv(name, value)
    (tmp_path / "triagecore.toml").write_text(_toml_text(sections), encoding="utf-8")
    return Config(root_dir=str(tmp_path))


def _resolve(env, sections):
    present_env = {k: v for k, v in env.items() if v is not _ABSENT}
    return resolve_effective_configuration(present_env, _toml_mapping(sections))


LAYER_VALUES = (_ABSENT, "", "LAYER")


@pytest.mark.parametrize(
    "backend_type, env_url, toml_url, backend_env_url",
    list(itertools.product(("ollama", "lmstudio", "vllm", "custom"), LAYER_VALUES, LAYER_VALUES, LAYER_VALUES)),
)
def test_local_url_resolution_matches_config_and_create_backend(
    monkeypatch, tmp_path, backend_type, env_url, toml_url, backend_env_url
):
    from triage_core import backends as runtime_backends

    def layer(value, port):
        return f"http://127.0.0.1:{port}/v1" if value == "LAYER" else value

    backend_env_name = {"ollama": "TRIAGE_OLLAMA_BASE_URL", "lmstudio": "TRIAGE_SUPERVISOR_BASE_URL"}.get(
        backend_type, "TRIAGE_OLLAMA_BASE_URL"
    )
    env = {"TRIAGE_BASE_URL": layer(env_url, 1001), backend_env_name: layer(backend_env_url, 1003)}
    sections = {"backend": {"default_type": backend_type, "base_url": layer(toml_url, 1002)}}
    config = _runtime(monkeypatch, tmp_path, env, sections)
    try:
        actual = runtime_backends.create_backend(
            config.get_backend_type(),
            model=config.get_backend_model(),
            base_url=config.get_backend_base_url(),
        ).base_url
    except ValueError:
        actual = None
    resolved = _resolve(env, sections).local_base_url

    if resolved.source == "preset":
        assert actual == LEGACY_LOCAL_PRESETS[backend_type]
        assert resolved.value == dp.GOVERNED_LOCAL_PRESETS[backend_type]
    elif resolved.source == "absent":
        assert actual is None
    elif resolved.value == "":
        assert actual in ("", None)
    else:
        assert resolved.value == actual


@pytest.mark.parametrize(
    "env_url, toml_url", list(itertools.product(LAYER_VALUES, LAYER_VALUES))
)
def test_cloud_url_resolution_matches_config_and_create_backend(
    monkeypatch, tmp_path, env_url, toml_url
):
    from triage_core import backends as runtime_backends

    def layer(value, host):
        return f"https://{host}.example/v1" if value == "LAYER" else value

    env = {"TRIAGE_QWEN_BASE_URL": layer(env_url, "env"), "TRIAGE_QWEN_API_KEY": "k"}
    sections = {"qwen": {"base_url": layer(toml_url, "toml")}}
    config = _runtime(monkeypatch, tmp_path, env, sections)
    actual = runtime_backends.create_backend(
        "qwen",
        model=config.get_qwen_model(),
        base_url=config.get_qwen_base_url(),
        api_key=config.get_qwen_api_key(),
    ).base_url
    assert _resolve(env, sections).cloud_base_url.value == actual


@pytest.mark.parametrize(
    "env_model, toml_model",
    list(itertools.product((_ABSENT, "", "auto", "env-model"), (_ABSENT, "auto", "toml-model"))),
)
def test_cloud_model_resolution_matches_config_and_create_backend(
    monkeypatch, tmp_path, env_model, toml_model
):
    from triage_core import backends as runtime_backends

    env = {"TRIAGE_QWEN_MODEL": env_model, "TRIAGE_QWEN_API_KEY": "k"}
    sections = {"qwen": {"model": toml_model}}
    config = _runtime(monkeypatch, tmp_path, env, sections)
    actual = runtime_backends.create_backend(
        "qwen", model=config.get_qwen_model(), base_url=None, api_key="k"
    ).model
    assert _resolve(env, sections).cloud_model.value == actual


@pytest.mark.parametrize(
    "env_type, toml_type, env_model, toml_model",
    list(
        itertools.product(
            (_ABSENT, "", "vllm"), (_ABSENT, "ollama"), (_ABSENT, "", "env-model"), (_ABSENT, "toml-model")
        )
    ),
)
def test_backend_type_and_model_resolution_matches_config(
    monkeypatch, tmp_path, env_type, toml_type, env_model, toml_model
):
    from triage_core import backends as runtime_backends

    env = {"TRIAGE_BACKEND_TYPE": env_type, "TRIAGE_MODEL": env_model}
    sections = {"backend": {"default_type": toml_type, "default_model": toml_model}}
    config = _runtime(monkeypatch, tmp_path, env, sections)
    resolved = _resolve(env, sections)
    assert resolved.backend_type.value == config.get_backend_type()
    assert resolved.model.value == config.get_backend_model()
    backend = runtime_backends.create_backend(config.get_backend_type(), base_url="http://127.0.0.1:1")
    expected_protocol = "ollama" if isinstance(backend, runtime_backends.OllamaBackend) else "openai_compatible"
    assert dp._BACKEND_PROTOCOLS[dp.backend_protocol_key(resolved.backend_type.value)] == expected_protocol


@pytest.mark.parametrize(
    "env_enabled, toml_enabled, env_key",
    list(itertools.product((_ABSENT, "", "1", "0", "yes"), (_ABSENT, True, False), (_ABSENT, "", "k"))),
)
def test_cloud_enable_and_key_presence_match_config(
    monkeypatch, tmp_path, env_enabled, toml_enabled, env_key
):
    env = {"TRIAGE_QWEN_ENABLED": env_enabled, "TRIAGE_QWEN_API_KEY": env_key}
    sections = {"qwen": {"enabled": toml_enabled}}
    config = _runtime(monkeypatch, tmp_path, env, sections)
    resolved = _resolve(env, sections)
    assert resolved.cloud_enabled.value == config.get_qwen_enabled()
    assert resolved.cloud_api_key_present == bool(config.get_qwen_api_key())
