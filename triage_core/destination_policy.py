"""Trusted backend destination policy and guarded transport (CR-135, slice 1).

This module is the contract layer of CR-135, *Governed Backend Destination Policy and
Transport Binding*, as accepted at ``a0bbd93``. It is deliberately **not integrated**:
no CLI, planning, execution, routing, backend, configuration or ledger module imports
it, and it imports none of them. ``tc run`` behaviour, ``CONFIGURATION_VERSION`` and
every decision identifier are unchanged by its presence. Slice 2 wires it in.

It provides:

- the closed ``backend_endpoint`` profiles (``device_local_loopback.v1`` and
  ``qwen_dashscope_intl.v1``) and the closed reason-code vocabulary;
- strict endpoint normalization that validates and never repairs;
- base-path canonicalization;
- a pure effective-configuration resolver over caller-supplied mappings (it never reads
  the process environment or any file itself);
- route-indexed bindings and the deterministic digest lines slice 2 will add to the
  governed configuration digest;
- :class:`GuardedTransport`, a sealed transport that checks its owner's current
  endpoint identity, its session settings against the canonical policy and a
  per-instance runtime seal, and the exact prepared request URL before every send.

What a passing test of this module shows is limited to this module: it is unit-level
evidence of the contract, not evidence that any governed run's network effects are
contained.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import ipaddress
import json
import re
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple

import requests
from requests.adapters import BaseAdapter
from requests.structures import CaseInsensitiveDict


DESTINATION_POLICY_SCHEMA = "triagecore.destination_policy.v1"
TRANSPORT_POLICY_VERSION = "triagecore.transport_policy.v1"
DESTINATION_BINDING_VERSION = "triagecore.destination_binding.v1"
EFFECTIVE_CONFIGURATION_VERSION = "triagecore.effective_backend_configuration.v1"

LOCAL_PROFILE_ID = "device_local_loopback.v1"
CLOUD_PROFILE_ID = "qwen_dashscope_intl.v1"

_IDENTITY_DOMAIN = b"triagecore.destination_policy.endpoint_identity.v1\x00"
_TRANSPORT_POLICY_DOMAIN = b"triagecore.destination_policy.transport_policy.v1\x00"
_PROFILES_DOMAIN = b"triagecore.destination_policy.profiles.v1\x00"

LOCAL_ROUTES = ("local_fast", "local_heavy")
CLOUD_ROUTES = ("cloud_primary", "cloud_secondary")
NON_NETWORK_ROUTES = ("human_handoff", "deterministic")
KNOWN_ROUTES = frozenset(LOCAL_ROUTES + CLOUD_ROUTES + NON_NETWORK_ROUTES)

DEVICE_LOOPBACK = "device_loopback"
REMOTE_CLOUD = "remote_cloud"
LOCALITY_CLASSES = frozenset({DEVICE_LOOPBACK, REMOTE_CLOUD})

REASON_CODES = frozenset(
    {
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
        "backend_protocol_unsupported",
        "destination_binding_mismatch",
        "transport_not_guarded",
        "transport_settings_changed",
        "transport_request_not_permitted",
        "endpoint_redirect_refused",
    }
)

AUTO_MODEL_SENTINELS = frozenset({"", "auto", "loaded-model", "local-model"})

_DEFAULT_PORTS = {"http": 80, "https": 443}

# Literal-loopback presets. Slice 1 cannot import ``backends.py``; slice 2 points the
# backend presets at these values or proves they agree.
GOVERNED_LOCAL_PRESETS: Mapping[str, Optional[str]] = {
    "ollama": "http://127.0.0.1:11434",
    "lmstudio": "http://127.0.0.1:1234/v1",
    "lm_studio": "http://127.0.0.1:1234/v1",
    "vllm": "http://127.0.0.1:8000/v1",
    "llama.cpp": "http://127.0.0.1:8080/v1",
    "llamacpp": "http://127.0.0.1:8080/v1",
    "custom": None,
}

_BACKEND_PROTOCOLS: Mapping[str, str] = {
    "ollama": "ollama",
    "lmstudio": "openai_compatible",
    "lm_studio": "openai_compatible",
    "vllm": "openai_compatible",
    "llama.cpp": "openai_compatible",
    "llamacpp": "openai_compatible",
    "custom": "openai_compatible",
}

# Backend-specific environment defaults, consulted after TRIAGE_BASE_URL and the TOML
# value, mirroring ``backends.create_backend`` at ``1dc9b88``.
_BACKEND_URL_ENV: Mapping[str, str] = {
    "ollama": "TRIAGE_OLLAMA_BASE_URL",
    "lmstudio": "TRIAGE_SUPERVISOR_BASE_URL",
    "lm_studio": "TRIAGE_SUPERVISOR_BASE_URL",
}

# Allowed calls per backend protocol, relative to the bound base path.
PROTOCOL_CALLS: Mapping[str, Tuple[Tuple[str, str], ...]] = {
    "openai_compatible": (("GET", "models"), ("POST", "chat/completions")),
    "ollama": (("GET", "api/tags"), ("POST", "api/chat")),
    "qwen": (("POST", "chat/completions"),),
}

_LOCAL_PROTOCOLS = frozenset({"openai_compatible", "ollama"})

_LOOPBACK_ADDRESSES = frozenset(
    {ipaddress.ip_address("127.0.0.1"), ipaddress.ip_address("::1")}
)
_LAN_NETWORKS = tuple(
    ipaddress.ip_network(net)
    for net in (
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "169.254.0.0/16",
        "fc00::/7",
        "fe80::/10",
    )
)

_APPROVED_CLOUD_HOST = "dashscope-intl.aliyuncs.com"
_APPROVED_CLOUD_PORT = 443
_APPROVED_CLOUD_BASE_PATH = "/compatible-mode/v1"

_SCHEME_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*\Z")
_PORT_RE = re.compile(r"[1-9][0-9]{0,4}\Z")
_PATH_SEGMENT_RE = re.compile(r"[A-Za-z0-9._~\-]+\Z")
_HOST_LABEL_RE = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?\Z")
_NUMERIC_LABEL_RE = re.compile(r"(?:0[xX][0-9A-Fa-f]*|[0-9]+)\Z")


class DestinationPolicyError(Exception):
    """A destination-policy refusal.

    Deliberately neither a ``requests.RequestException`` nor a ``ValueError``, so the
    engine and backends cannot mistake it for a backend failure and turn it into a
    handoff (CR-135 fact 12). Its message carries the reason code and, at most, a safe
    label built by this module. It never carries a raw URL or any caller-supplied text.
    """

    def __init__(self, code: str, safe_label: Optional[str] = None) -> None:
        if code not in REASON_CODES:
            raise TypeError("unknown destination-policy reason code")
        self.code = code
        self.safe_label = safe_label
        super().__init__(code if safe_label is None else f"{code} ({safe_label})")


def _sha256(domain: bytes, payload: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(domain)
    digest.update(payload)
    return "sha256:" + digest.hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


# --- Profiles ----------------------------------------------------------------------

_PROFILE_DEFINITIONS = {
    LOCAL_PROFILE_ID: {
        "kind": "backend_endpoint",
        "locality": DEVICE_LOOPBACK,
        "routes": list(LOCAL_ROUTES),
        "schemes": ["http", "https"],
        "hosts": ["127.0.0.1", "::1"],
        "protocols": sorted(_LOCAL_PROTOCOLS),
    },
    CLOUD_PROFILE_ID: {
        "kind": "backend_endpoint",
        "locality": REMOTE_CLOUD,
        "routes": list(CLOUD_ROUTES),
        "schemes": ["https"],
        "identity": f"https://{_APPROVED_CLOUD_HOST}:{_APPROVED_CLOUD_PORT}"
        f"{_APPROVED_CLOUD_BASE_PATH}",
        "protocols": ["qwen"],
    },
}


def destination_profiles_sha256() -> str:
    """Digest of the built-in profile definitions, under the policy schema."""

    return _sha256(
        _PROFILES_DOMAIN,
        _canonical_json(
            {"schema": DESTINATION_POLICY_SCHEMA, "profiles": _PROFILE_DEFINITIONS}
        ),
    )


# --- Endpoint normalization ---------------------------------------------------------


@dataclass(frozen=True)
class CanonicalEndpoint:
    """A validated endpoint identity. Construct it through :func:`normalize_endpoint`."""

    scheme: str
    host: str
    port: int
    base_path: str
    locality: str
    profile_id: str

    @property
    def host_text(self) -> str:
        return f"[{self.host}]" if ":" in self.host else self.host

    @property
    def canonical(self) -> str:
        return f"{self.scheme}://{self.host_text}:{self.port}{self.base_path}"

    @property
    def identity_sha256(self) -> str:
        return _sha256(_IDENTITY_DOMAIN, self.canonical.encode("ascii"))

    @property
    def safe_label(self) -> str:
        if self.locality == DEVICE_LOOPBACK:
            family = "ipv6" if ":" in self.host else "ipv4"
            return f"loopback-{family}:{self.port}"
        return CLOUD_PROFILE_ID.rsplit(".", 1)[0]


def canonicalize_base_path(raw: str) -> str:
    """Validate a base path. One trailing ``/`` is the only normalization applied."""

    if type(raw) is not str:
        raise DestinationPolicyError("endpoint_path_noncanonical")
    if raw in ("", "/"):
        return ""
    if not raw.startswith("/"):
        raise DestinationPolicyError("endpoint_path_noncanonical")
    path = raw[:-1] if raw.endswith("/") else raw
    for segment in path[1:].split("/"):
        if segment in ("", ".", "..") or not _PATH_SEGMENT_RE.fullmatch(segment):
            raise DestinationPolicyError("endpoint_path_noncanonical")
    return path


def _split_endpoint(raw: Any) -> Tuple[str, str, Optional[int], str]:
    """Split ``raw`` into scheme, host, explicit port and raw path, or refuse."""

    if type(raw) is not str or not raw:
        raise DestinationPolicyError("endpoint_malformed")
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in raw):
        raise DestinationPolicyError("endpoint_malformed")
    scheme, separator, rest = raw.partition("://")
    if not separator or not _SCHEME_RE.fullmatch(scheme):
        raise DestinationPolicyError("endpoint_malformed")
    if scheme not in _DEFAULT_PORTS:
        raise DestinationPolicyError("endpoint_scheme_not_permitted")
    if "?" in rest or "#" in rest:
        raise DestinationPolicyError("endpoint_query_or_fragment")
    slash = rest.find("/")
    authority, path = (rest, "") if slash < 0 else (rest[:slash], rest[slash:])
    if not authority or any(ch.isspace() for ch in authority):
        raise DestinationPolicyError("endpoint_malformed")
    if "@" in authority:
        raise DestinationPolicyError("endpoint_credentials_embedded")
    if "\\" in authority or "%" in authority:
        raise DestinationPolicyError("endpoint_deceptive_identity")
    if any(ord(ch) > 0x7F for ch in authority):
        raise DestinationPolicyError("endpoint_deceptive_identity")

    port_text: Optional[str] = None
    if authority.startswith("["):
        close = authority.find("]")
        if close < 0:
            raise DestinationPolicyError("endpoint_malformed")
        host = authority[1:close]
        tail = authority[close + 1 :]
        if tail:
            if not tail.startswith(":"):
                raise DestinationPolicyError("endpoint_malformed")
            port_text = tail[1:]
        if ":" not in host:
            raise DestinationPolicyError("endpoint_deceptive_identity")
    else:
        if authority.count(":") > 1:
            raise DestinationPolicyError("endpoint_malformed")
        host, colon, port_part = authority.partition(":")
        if colon:
            port_text = port_part
    if not host:
        raise DestinationPolicyError("endpoint_malformed")

    port: Optional[int] = None
    if port_text is not None:
        if not _PORT_RE.fullmatch(port_text) or int(port_text) > 65535:
            raise DestinationPolicyError("endpoint_malformed")
        port = int(port_text)
    return scheme, host, port, path


def _parse_host(host: str, bracketed: bool):
    """Return an IP address object, or the hostname string, or refuse as deceptive."""

    if host.endswith("."):
        raise DestinationPolicyError("endpoint_deceptive_identity")
    if bracketed:
        try:
            address = ipaddress.IPv6Address(host)
        except ValueError:
            raise DestinationPolicyError("endpoint_deceptive_identity") from None
        if str(address) != host or address.ipv4_mapped is not None:
            raise DestinationPolicyError("endpoint_deceptive_identity")
        return address
    try:
        address = ipaddress.IPv4Address(host)
    except ValueError:
        labels = host.split(".")
        if all(_NUMERIC_LABEL_RE.fullmatch(label) for label in labels):
            # 127.1, 0x7f.0.0.1, 2130706433, 0177.0.0.1 and similar.
            raise DestinationPolicyError("endpoint_deceptive_identity") from None
        if any(not _HOST_LABEL_RE.fullmatch(label) for label in labels):
            raise DestinationPolicyError("endpoint_deceptive_identity") from None
        if any(label.lower().startswith("xn--") for label in labels):
            raise DestinationPolicyError("endpoint_deceptive_identity") from None
        return host
    if str(address) != host:
        raise DestinationPolicyError("endpoint_deceptive_identity")
    return address


def _is_lan(address) -> bool:
    return any(address.version == net.version and address in net for net in _LAN_NETWORKS)


def normalize_endpoint(raw: Any, route: str) -> CanonicalEndpoint:
    """Validate ``raw`` as the endpoint for ``route`` under the built-in profiles.

    Refusals raise :class:`DestinationPolicyError` before any network contact. Nothing
    is resolved through DNS: local routes accept literal loopback addresses only, and
    the cloud route accepts exactly one approved origin.
    """

    if route not in LOCAL_ROUTES and route not in CLOUD_ROUTES:
        raise TypeError("normalize_endpoint requires a network-capable logical route")
    scheme, host_raw, port, raw_path = _split_endpoint(raw)
    bracketed = raw.partition("://")[2].startswith("[")
    host = _parse_host(host_raw, bracketed)
    base_path = canonicalize_base_path(raw_path)
    effective_port = port if port is not None else _DEFAULT_PORTS[scheme]

    if route in CLOUD_ROUTES:
        if scheme != "https":
            raise DestinationPolicyError("endpoint_scheme_not_permitted", route)
        if (
            not isinstance(host, str)
            or host != _APPROVED_CLOUD_HOST
            or effective_port != _APPROVED_CLOUD_PORT
            or base_path != _APPROVED_CLOUD_BASE_PATH
        ):
            raise DestinationPolicyError("cloud_endpoint_not_approved", route)
        return CanonicalEndpoint(
            scheme, host, effective_port, base_path, REMOTE_CLOUD, CLOUD_PROFILE_ID
        )

    if isinstance(host, str):
        raise DestinationPolicyError("hostname_not_literal_loopback", route)
    if host in _LOOPBACK_ADDRESSES:
        return CanonicalEndpoint(
            scheme, str(host), effective_port, base_path, DEVICE_LOOPBACK, LOCAL_PROFILE_ID
        )
    if host.is_loopback or host.is_unspecified:
        raise DestinationPolicyError("endpoint_deceptive_identity", route)
    if _is_lan(host):
        raise DestinationPolicyError("trusted_lan_not_in_profile", route)
    raise DestinationPolicyError("endpoint_not_device_local", route)


def allowed_request_urls(
    endpoint: CanonicalEndpoint, protocol: str
) -> FrozenSet[Tuple[str, str]]:
    """The closed set of ``(method, full URL)`` pairs a bound endpoint may receive.

    URLs carry the explicit port of the canonical identity. Requests preserves an
    explicit port when it prepares a request, so a governed backend must build its
    request URLs from the canonical endpoint (slice 2), or the guard refuses them.
    """

    if protocol not in PROTOCOL_CALLS:
        raise DestinationPolicyError("backend_protocol_unsupported")
    return frozenset(
        (method, f"{endpoint.canonical}/{suffix}")
        for method, suffix in PROTOCOL_CALLS[protocol]
    )


# --- Transport policy --------------------------------------------------------------


@dataclass(frozen=True)
class TransportPolicy:
    """The canonical transport policy. Contains nothing process-specific.

    A policy may only tighten the v1 security floor. Environment trust, proxies,
    redirect handling, the redirect limit and TLS verification are fixed, and each
    protocol's calls must be a subset of the built-in :data:`PROTOCOL_CALLS`. A policy
    that would weaken the floor is a programming error and raises ``TypeError`` at
    construction, so no weakened policy can ever reach a guarded transport.

    ``calls`` is copied at construction into sorted, nested tuples of strings, and
    the frozen copy is what is validated and enforced. Nothing the caller still holds
    can change a constructed policy.
    """

    version: str = TRANSPORT_POLICY_VERSION
    trust_env: bool = False
    proxies: Tuple[Tuple[str, str], ...] = ()
    redirects: str = "refuse"
    max_redirects: int = 0
    tls_verify: bool = True
    calls: Tuple[Tuple[str, Tuple[Tuple[str, str], ...]], ...] = tuple(
        sorted(PROTOCOL_CALLS.items())
    )

    def __post_init__(self) -> None:
        # Freeze first, then validate only the frozen copy.
        object.__setattr__(self, "calls", _freeze_calls(self.calls))
        floor_held = (
            self.version == TRANSPORT_POLICY_VERSION
            and self.trust_env is False
            and type(self.proxies) is tuple
            and self.proxies == ()
            and self.redirects == "refuse"
            and type(self.max_redirects) is int
            and self.max_redirects == 0
            and self.tls_verify is True
        )
        if not floor_held:
            raise TypeError("transport policy weakens the v1 security floor")
        seen = set()
        for protocol, calls in self.calls:
            if protocol not in PROTOCOL_CALLS or protocol in seen:
                raise TypeError("transport policy names an unknown or repeated protocol")
            seen.add(protocol)
            if len(set(calls)) != len(calls) or not set(calls) <= set(
                PROTOCOL_CALLS[protocol]
            ):
                raise TypeError("transport policy permits a call outside the v1 table")

    def permitted_calls(self, protocol: str) -> Tuple[Tuple[str, str], ...]:
        """This policy's calls for ``protocol``; none when the policy omits it."""

        return dict(self.calls).get(protocol, ())

    def canonical_body(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "trust_env": self.trust_env,
            "proxies": [list(pair) for pair in self.proxies],
            "redirects": self.redirects,
            "max_redirects": self.max_redirects,
            "tls_verify": self.tls_verify,
            "calls": {
                protocol: [list(call) for call in calls] for protocol, calls in self.calls
            },
        }

    @property
    def sha256(self) -> str:
        return _sha256(_TRANSPORT_POLICY_DOMAIN, _canonical_json(self.canonical_body()))


def _freeze_calls(value: Any) -> Tuple[Tuple[str, Tuple[Tuple[str, str], ...]], ...]:
    """Copy ``calls`` into sorted nested tuples of strings, or raise ``TypeError``.

    Only lists and tuples are accepted at each level, so no caller-held mutable
    container survives into the policy.
    """

    if type(value) not in (tuple, list):
        raise TypeError("transport policy calls must be a sequence of entries")
    entries = []
    for entry in value:
        if type(entry) not in (tuple, list) or len(entry) != 2:
            raise TypeError("transport policy call entries are (protocol, calls) pairs")
        protocol, calls = entry
        if type(protocol) is not str or type(calls) not in (tuple, list):
            raise TypeError("transport policy call entries are (protocol, calls) pairs")
        frozen = []
        for call in calls:
            if (
                type(call) not in (tuple, list)
                or len(call) != 2
                or any(type(part) is not str for part in call)
            ):
                raise TypeError("transport policy calls are (method, suffix) string pairs")
            frozen.append((call[0], call[1]))
        entries.append((protocol, tuple(sorted(frozen))))
    return tuple(sorted(entries))


DEFAULT_TRANSPORT_POLICY = TransportPolicy()


# --- Effective configuration -------------------------------------------------------


class _UnreadableConfiguration:
    """Marker passed instead of a TOML mapping when the file exists but is unusable."""

    def __repr__(self) -> str:
        return "UNREADABLE_CONFIGURATION"


UNREADABLE_CONFIGURATION = _UnreadableConfiguration()


@dataclass(frozen=True)
class ConfiguredValue:
    value: Any
    source: str


@dataclass(frozen=True)
class EffectiveBackendConfiguration:
    """The immutable S1 snapshot of backend-relevant configuration and its sources."""

    backend_type: ConfiguredValue
    model: ConfiguredValue
    local_base_url: ConfiguredValue
    timeout_seconds: ConfiguredValue
    cloud_enabled: ConfiguredValue
    cloud_model: ConfiguredValue
    cloud_base_url: ConfiguredValue
    cloud_api_key_present: bool
    version: str = EFFECTIVE_CONFIGURATION_VERSION


def _backend_fallthrough(
    configured: ConfiguredValue,
    env: Mapping[str, str],
    fallback_env: Optional[str],
    fallback_source: str,
    default: Any,
    default_source: str,
) -> ConfiguredValue:
    """Mirror ``create_backend``: an empty configured value falls through.

    ``create_backend`` treats the value it receives with ``value or os.getenv(name,
    default)``. A falsy value from the ``Config`` layer therefore yields the fallback
    variable when it is present (even when empty), and otherwise the default.
    """

    if configured.value not in (None, ""):
        return configured
    if fallback_env and env.get(fallback_env) is not None:
        return ConfiguredValue(env[fallback_env], fallback_source)
    return ConfiguredValue(default, default_source)


def _env_then_toml(
    env: Mapping[str, str],
    env_name: str,
    section: Mapping[str, Any],
    key: str,
    default: Any,
) -> ConfiguredValue:
    """Mirror ``Config.get_global``: a present variable wins, even when empty."""

    if env.get(env_name) is not None:
        return ConfiguredValue(env[env_name], f"env:{env_name}")
    if section.get(key) is not None:
        return ConfiguredValue(section[key], "toml:triagecore.toml")
    return ConfiguredValue(default, "preset")


def resolve_effective_configuration(
    env: Mapping[str, str], toml: Any
) -> EffectiveBackendConfiguration:
    """Resolve backend configuration from caller-supplied inputs, recording sources.

    ``env`` is a snapshot of the environment taken once by the caller. ``toml`` is the
    parsed ``triagecore.toml`` mapping, ``None`` when the file is absent, or
    :data:`UNREADABLE_CONFIGURATION` when it exists but could not be read or parsed,
    which refuses with ``configuration_unreadable`` instead of falling back to
    defaults. Precedence mirrors ``config.py`` and ``backends.create_backend`` at
    ``1dc9b88``. Only the *presence* of a cloud API key is recorded, never its value.
    """

    if toml is UNREADABLE_CONFIGURATION:
        raise DestinationPolicyError("configuration_unreadable")
    if toml is None:
        toml = {}
    if not isinstance(toml, Mapping) or not isinstance(env, Mapping):
        raise DestinationPolicyError("configuration_unreadable")
    backend_section = toml.get("backend", {})
    qwen_section = toml.get("qwen", {})
    if not isinstance(backend_section, Mapping) or not isinstance(qwen_section, Mapping):
        raise DestinationPolicyError("configuration_unreadable")
    toml_source = "toml:triagecore.toml"

    backend_type = _env_then_toml(
        env, "TRIAGE_BACKEND_TYPE", backend_section, "default_type", "lmstudio"
    )
    model = _env_then_toml(env, "TRIAGE_MODEL", backend_section, "default_model", "auto")
    normalized_type = backend_protocol_key(backend_type.value)
    backend_env_name = _BACKEND_URL_ENV.get(normalized_type)
    preset = GOVERNED_LOCAL_PRESETS.get(normalized_type)
    # Config.get_backend_base_url: a present TRIAGE_BASE_URL wins even when empty,
    # then the TOML value. create_backend then falls through on an empty value.
    local_base_url = _backend_fallthrough(
        _env_then_toml(env, "TRIAGE_BASE_URL", backend_section, "base_url", None),
        env,
        backend_env_name,
        f"backend_env:{backend_env_name}",
        preset,
        "preset" if preset is not None else "absent",
    )

    timeout_raw = _env_then_toml(
        env, "TRIAGE_TIMEOUT_SECONDS", backend_section, "timeout_seconds", 30
    )
    try:
        timeout_seconds = ConfiguredValue(int(timeout_raw.value), timeout_raw.source)
    except (TypeError, ValueError):
        raise DestinationPolicyError("configuration_unreadable") from None

    if env.get("TRIAGE_QWEN_ENABLED") is not None:
        cloud_enabled = ConfiguredValue(
            str(env["TRIAGE_QWEN_ENABLED"]).strip().lower() in {"1", "true", "yes", "on"},
            "env:TRIAGE_QWEN_ENABLED",
        )
    elif "enabled" in qwen_section:
        cloud_enabled = ConfiguredValue(bool(qwen_section["enabled"]), toml_source)
    else:
        cloud_enabled = ConfiguredValue(False, "preset")

    cloud_model_raw = _env_then_toml(env, "TRIAGE_QWEN_MODEL", qwen_section, "model", "qwen-max")
    if str(cloud_model_raw.value) in AUTO_MODEL_SENTINELS:
        # create_backend replaces a sentinel with TRIAGE_QWEN_MODEL or qwen-max.
        substitute = env.get("TRIAGE_QWEN_MODEL", "qwen-max")
        cloud_model = ConfiguredValue(
            substitute,
            "env:TRIAGE_QWEN_MODEL" if "TRIAGE_QWEN_MODEL" in env else "preset",
        )
    else:
        cloud_model = cloud_model_raw
    default_cloud_url = f"https://{_APPROVED_CLOUD_HOST}{_APPROVED_CLOUD_BASE_PATH}"
    cloud_base_url = _backend_fallthrough(
        _env_then_toml(
            env, "TRIAGE_QWEN_BASE_URL", qwen_section, "base_url", default_cloud_url
        ),
        env,
        "TRIAGE_QWEN_BASE_URL",
        "env:TRIAGE_QWEN_BASE_URL",
        default_cloud_url,
        "preset",
    )

    return EffectiveBackendConfiguration(
        backend_type=backend_type,
        model=model,
        local_base_url=local_base_url,
        timeout_seconds=timeout_seconds,
        cloud_enabled=cloud_enabled,
        cloud_model=cloud_model,
        cloud_base_url=cloud_base_url,
        cloud_api_key_present=bool(env.get("TRIAGE_QWEN_API_KEY")),
    )


def backend_protocol_key(backend_type: Any) -> str:
    """Normalize a backend type as ``create_backend`` does: empty means ``ollama``."""

    return str(backend_type or "ollama").lower()


# --- Route binding -----------------------------------------------------------------


@dataclass(frozen=True)
class RouteBinding:
    """One route-indexed binding entry, in envelope order."""

    route: str
    profile_id: str
    locality: str
    protocol: str
    endpoint: CanonicalEndpoint
    allowed_requests: FrozenSet[Tuple[str, str]]

    @property
    def identity_sha256(self) -> str:
        return self.endpoint.identity_sha256

    @property
    def safe_label(self) -> str:
        return self.endpoint.safe_label

    def binding_line(self) -> str:
        return (
            f"route={self.route};profile={self.profile_id};class={self.locality};"
            f"protocol={self.protocol};identity_sha256={self.identity_sha256}"
        )


def bind_route_endpoints(
    envelope: Sequence[str], configuration: EffectiveBackendConfiguration
) -> Tuple[RouteBinding, ...]:
    """Bind every network-capable envelope member, in order, or refuse the attempt.

    ``human_handoff`` and ``deterministic`` contact no network and are skipped. A cloud
    route is bound only when cloud execution is enabled; otherwise it is left unbound,
    because runtime binding already treats it as unavailable. Any refusal ends the whole
    attempt (CR-135 D4): there is no partial binding and no fallback.
    """

    if isinstance(envelope, str) or len(set(envelope)) != len(tuple(envelope)):
        raise TypeError("envelope must be a sequence of distinct logical routes")
    bindings: List[RouteBinding] = []
    for route in envelope:
        if route not in KNOWN_ROUTES:
            raise TypeError("envelope member is not a known logical route")
        if route in NON_NETWORK_ROUTES:
            continue
        if route in LOCAL_ROUTES:
            protocol = _BACKEND_PROTOCOLS.get(
                backend_protocol_key(configuration.backend_type.value)
            )
            endpoint = normalize_endpoint(configuration.local_base_url.value, route)
            if protocol not in _LOCAL_PROTOCOLS:
                raise DestinationPolicyError("backend_protocol_unsupported", route)
        else:
            if not configuration.cloud_enabled.value:
                continue
            if str(configuration.cloud_model.value) in AUTO_MODEL_SENTINELS:
                raise DestinationPolicyError("cloud_model_unbound", route)
            protocol = "qwen"
            endpoint = normalize_endpoint(configuration.cloud_base_url.value, route)
        bindings.append(
            RouteBinding(
                route=route,
                profile_id=endpoint.profile_id,
                locality=endpoint.locality,
                protocol=protocol,
                endpoint=endpoint,
                allowed_requests=allowed_request_urls(endpoint, protocol),
            )
        )
    return tuple(bindings)


def binding_digest_lines(
    bindings: Sequence[RouteBinding],
    policy: TransportPolicy = DEFAULT_TRANSPORT_POLICY,
) -> Tuple[str, ...]:
    """The lines slice 2 adds to ``configuration_digest``. Nothing calls this yet."""

    return (
        f"destination_binding_version={DESTINATION_BINDING_VERSION}",
        *(binding.binding_line() for binding in bindings),
        f"transport_policy_sha256={policy.sha256}",
        f"destination_profiles_sha256={destination_profiles_sha256()}",
    )


# --- Guarded transport -------------------------------------------------------------

_ALLOWED_CALL_KWARGS = frozenset({"timeout", "headers", "json", "stream", "allow_redirects"})


@dataclass(frozen=True)
class SendRecord:
    """Evidence of one permitted send. Carries no URL, headers or body."""

    route: str
    safe_label: str
    method: str
    suffix: str
    status_code: Optional[int]


@dataclass
class _GuardState:
    owner: Any = None
    owner_type: Optional[type] = None
    refusal: Optional[str] = None
    sends: List[SendRecord] = field(default_factory=list)


class GuardedTransport:
    """A sealed HTTP transport bound to one route, one owner and one frozen identity.

    The wrapped ``requests.Session`` is private. Backends call :meth:`get` and
    :meth:`post` only. Before every send the transport checks, in order:

    1. the call's keyword arguments against a closed allowlist;
    2. that an owner has been bound and the transport has not already refused;
    3. that the live session conforms to the canonical :class:`TransportPolicy` and
       still equals the runtime seal recorded at construction, which covers its
       headers, cookies and parameters as well as its transport settings;
    4. that the owner's *current* ``base_url`` still produces the frozen identity,
       independently of the request URL;
    5. that the prepared request's method and URL exactly equal a pair the binding
       allows *and* the transport policy permits; a policy can only remove calls.

    Requests are prepared on their own, never merged with session state, so session
    headers, cookies, authentication and parameters cannot reach the wire even if the
    seal were bypassed. Each request carries a fixed copy of the default headers an
    ordinary ``requests.Session`` adds, captured once at construction, plus the call's
    own headers.

    Any refusal latches: every later call in the attempt is refused without sending,
    and :meth:`verify_integrity` reports the latched refusal. A 3xx response is a late
    refusal: the redirect is never followed.
    """

    def __init__(
        self,
        binding: RouteBinding,
        policy: TransportPolicy = DEFAULT_TRANSPORT_POLICY,
        adapters: Optional[Mapping[str, BaseAdapter]] = None,
    ) -> None:
        if type(binding) is not RouteBinding or type(policy) is not TransportPolicy:
            raise TypeError("GuardedTransport requires a RouteBinding and TransportPolicy")
        self._binding = binding
        self._policy = policy
        # Permitted only when both the binding and the policy allow the request.
        self._suffixes = {
            (method, url): suffix
            for method, suffix in policy.permitted_calls(binding.protocol)
            for url in (f"{binding.endpoint.canonical}/{suffix}",)
            if (method, url) in binding.allowed_requests
        }
        self._default_headers = tuple(requests.utils.default_headers().items())
        session = requests.Session()
        session.trust_env = policy.trust_env
        session.proxies = dict(policy.proxies)
        session.max_redirects = policy.max_redirects
        session.verify = policy.tls_verify
        for prefix, adapter in (adapters or {}).items():
            session.mount(prefix, adapter)
        self._session = session
        self._seal = self._session_fingerprint()
        # The digest of the policy this guard was built to enforce. A policy changed
        # after construction (only possible by bypassing the frozen dataclass) no
        # longer matches, and every later send is refused.
        self._policy_sha256 = policy.sha256
        self._state = _GuardState()

    # Read-only views for S2 and for evidence.

    @property
    def route(self) -> str:
        return self._binding.route

    @property
    def bound_identity_sha256(self) -> str:
        return self._binding.identity_sha256

    @property
    def transport_policy_sha256(self) -> str:
        return self._policy_sha256

    @property
    def owner(self) -> Any:
        return self._state.owner

    @property
    def sends(self) -> Tuple[SendRecord, ...]:
        return tuple(self._state.sends)

    @property
    def refusal(self) -> Optional[str]:
        return self._state.refusal

    def bind_owner(self, owner: Any) -> None:
        """Bind the single backend instance this transport serves. Irrevocable."""

        if self._state.owner is not None:
            self._refuse("destination_binding_mismatch")
        self._state.owner = owner
        self._state.owner_type = type(owner)
        self._check_owner_identity()

    def verify_integrity(self) -> None:
        """The S2 check: policy conformance, runtime seal and owner identity."""

        if self._state.refusal is not None:
            raise DestinationPolicyError(self._state.refusal, self._binding.safe_label)
        if self._state.owner is None:
            self._refuse("transport_not_guarded")
        self._check_session()
        self._check_owner_identity()

    def get(self, url: str, **kwargs: Any) -> requests.Response:
        return self._send("GET", url, kwargs)

    def post(self, url: str, **kwargs: Any) -> requests.Response:
        return self._send("POST", url, kwargs)

    # Internals.

    def _refuse(self, code: str) -> None:
        if self._state.refusal is None:
            self._state.refusal = code
        raise DestinationPolicyError(code, self._binding.safe_label)

    def _record(self, method: str, suffix: str, status_code: Optional[int]) -> None:
        self._state.sends.append(
            SendRecord(
                route=self.route,
                safe_label=self._binding.safe_label,
                method=method,
                suffix=suffix,
                status_code=status_code,
            )
        )

    def _session_fingerprint(self) -> Tuple[Any, ...]:
        session = self._session
        hooks = tuple(
            (event, tuple(id(hook) for hook in hooks))
            for event, hooks in sorted(session.hooks.items())
        )
        return (
            session.trust_env,
            tuple(sorted(session.proxies.items())),
            session.verify,
            session.cert,
            session.max_redirects,
            id(session.auth) if session.auth is not None else None,
            hooks,
            tuple((prefix, id(adapter)) for prefix, adapter in session.adapters.items()),
            tuple(sorted((key.lower(), value) for key, value in session.headers.items())),
            tuple(
                sorted(
                    (cookie.domain, cookie.path, cookie.name, cookie.value)
                    for cookie in session.cookies
                )
            ),
            repr(session.params),
        )

    def _check_session(self) -> None:
        # Inspection boundary: state that cannot even be inspected is a changed
        # setting. The refusal is raised after the ``try`` so it latches, and so it
        # carries neither the inspected value nor the underlying exception.
        try:
            session = self._session
            policy = self._policy
            intact = (
                session.trust_env is policy.trust_env
                and dict(session.proxies) == dict(policy.proxies)
                and session.verify is policy.tls_verify
                and session.cert is None
                and session.max_redirects == policy.max_redirects
                and session.auth is None
                and all(not hooks for hooks in session.hooks.values())
                and self._session_fingerprint() == self._seal
                and self._policy.sha256 == self._policy_sha256
            )
        except Exception:
            intact = False
        if not intact:
            self._refuse("transport_settings_changed")

    def _check_owner_identity(self) -> None:
        # Inspection boundary for the owner, on the same terms as _check_session.
        try:
            owner = self._state.owner
            matches = (
                type(owner) is self._state.owner_type
                and normalize_endpoint(getattr(owner, "base_url", None), self.route)
                .identity_sha256
                == self._binding.identity_sha256
            )
        except Exception:
            matches = False
        if not matches:
            self._refuse("destination_binding_mismatch")

    def _send(self, method: str, url: Any, kwargs: Dict[str, Any]) -> requests.Response:
        if self._state.refusal is not None:
            raise DestinationPolicyError(self._state.refusal, self._binding.safe_label)
        if set(kwargs) - _ALLOWED_CALL_KWARGS or kwargs.get("allow_redirects", False):
            self._refuse("transport_settings_changed")
        if self._state.owner is None:
            self._refuse("transport_not_guarded")
        self._check_session()
        self._check_owner_identity()
        if type(url) is not str:
            self._refuse("transport_request_not_permitted")
        try:
            headers = CaseInsensitiveDict(self._default_headers)
            headers.update(kwargs.get("headers") or {})
            # Prepared on its own: no session headers, cookies, auth or params merge in.
            prepared = requests.Request(
                method, url, headers=headers, json=kwargs.get("json")
            ).prepare()
        except (requests.RequestException, ValueError, TypeError):
            self._refuse("transport_request_not_permitted")
        suffix = self._suffixes.get((prepared.method, prepared.url))
        if suffix is None:
            self._refuse("transport_request_not_permitted")

        # Send through the mounted adapter directly. ``Session.send`` would run its
        # redirect resolution even with redirects disabled; the guard never follows a
        # redirect, so it never enters that machinery.
        adapter = self._session.get_adapter(prepared.url)
        try:
            response = adapter.send(
                prepared,
                stream=bool(kwargs.get("stream", False)),
                timeout=kwargs.get("timeout"),
                verify=self._policy.tls_verify,
                cert=None,
                proxies={},
            )
        except Exception:
            self._record(prepared.method, suffix, None)
            raise
        self._record(prepared.method, suffix, response.status_code)
        if 300 <= response.status_code < 400:
            response.close()
            self._refuse("endpoint_redirect_refused")
        return response
