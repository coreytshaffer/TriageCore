"""Read-only local backend metadata probe (CR-114).

Metadata-only observations about local backend availability and model/runtime
identity. This module never invokes a model: no completions, chat, or
embeddings. It probes harmless metadata endpoints only:

    ollama     -> /api/tags
    lm_studio  -> /v1/models
    llama_cpp  -> /v1/models

Records are metadata-only and must pass the persistent privacy invariant. See
``docs/operations/local-backend-telemetry.md`` (design brief, CR-113) for the
bounding contract this slice implements. Routing wiring, route-input
population, circuit breakers, degraded modes, and daily-driver enforcement
remain future work.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlsplit

from .privacy_invariants import assert_persistent_privacy_safe

SCHEMA_VERSION = "local_backend_probe_record.v1"

SOURCE_TYPES = frozenset({"ollama", "lm_studio", "llama_cpp"})
EVIDENCE_TIERS = frozenset(
    {"synthetic_fixture", "local_metadata_probe", "operator_recorded"}
)
ERROR_CATEGORIES = frozenset(
    {
        "endpoint_unreachable",
        "timeout",
        "malformed_response",
        "unsupported_backend",
        "permission_or_policy_blocked",
        "probe_disabled",
    }
)

# Metadata-only endpoints per source type. Never a generation endpoint.
METADATA_PATHS = {
    "ollama": "/api/tags",
    "lm_studio": "/v1/models",
    "llama_cpp": "/v1/models",
}

DEFAULT_TIMEOUT_SECONDS = 3.0

# Model identifiers that look like filesystem paths (may embed private paths).
_PATH_LIKE = re.compile(r"[\\/]")

# Transport contract: callable(url, timeout) -> (status_code, parsed_json).
Transport = Callable[[str, float], Tuple[int, Any]]


class ProbeInputError(ValueError):
    """Argument/validation error (secret-bearing or malformed base_url).

    Distinct from a fail-closed probe outcome: input errors are the operator's
    to fix and map to CLI exit 1, whereas an unreachable/disabled backend is a
    valid record (exit 0).
    """


@dataclass(frozen=True)
class LocalBackendProbeRecord:
    source_type: str
    base_url: Optional[str]  # redacted: scheme://host[:port]
    reachable: bool
    evidence_tier: str
    model_count: Optional[int] = None
    observed_models: Optional[List[str]] = None
    response_latency_ms: Optional[int] = None
    error_category: Optional[str] = None
    observed_at: Optional[str] = None
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.evidence_tier not in EVIDENCE_TIERS:
            raise ValueError(f"invalid evidence_tier: {self.evidence_tier}")
        if (
            self.error_category is not None
            and self.error_category not in ERROR_CATEGORIES
        ):
            raise ValueError(f"invalid error_category: {self.error_category}")
        # Determinism: fixture-tier records must carry no timestamp.
        if self.evidence_tier == "synthetic_fixture" and self.observed_at is not None:
            raise ValueError("synthetic_fixture records must not carry observed_at")
        if self.model_count is not None and self.model_count < 0:
            raise ValueError("model_count must be non-negative")

    def to_dict(self) -> Dict[str, Any]:
        record = {
            "schema_version": self.schema_version,
            "source_type": self.source_type,
            "base_url": self.base_url,
            "reachable": self.reachable,
            "evidence_tier": self.evidence_tier,
            "model_count": self.model_count,
            "observed_models": (
                list(self.observed_models)
                if self.observed_models is not None
                else None
            ),
            "response_latency_ms": self.response_latency_ms,
            "error_category": self.error_category,
            "observed_at": self.observed_at,
        }
        # Every emitted record must pass the persistent privacy invariant.
        assert_persistent_privacy_safe(
            record, artifact_name="local backend probe record"
        )
        return record


def redact_base_url(raw_url: str) -> str:
    """Return ``scheme://host[:port]``; reject secret-bearing URLs; strip path.

    Redaction is a validation rule, not a display convention. Userinfo
    (``user:pass@``) and query strings can smuggle credentials or tokens into
    persisted evidence, so they are rejected outright. Path segments are
    stripped rather than stored.
    """
    parts = urlsplit(raw_url.strip())
    if not parts.scheme or not parts.hostname:
        raise ProbeInputError("base_url must include a scheme and host")
    if parts.username or parts.password:
        raise ProbeInputError("base_url must not contain userinfo (credentials)")
    if parts.query:
        raise ProbeInputError("base_url must not contain a query string")
    if parts.fragment:
        raise ProbeInputError("base_url must not contain a fragment")
    if parts.port is not None:
        return f"{parts.scheme}://{parts.hostname}:{parts.port}"
    return f"{parts.scheme}://{parts.hostname}"


def _sanitize_model_identifiers(names: List[str]) -> List[str]:
    """Drop path-like identifiers, which can embed private filesystem paths."""
    return [name for name in names if not _PATH_LIKE.search(str(name))]


def _extract_models(source_type: str, payload: Any) -> Optional[List[str]]:
    """Return reported model identifiers, or ``None`` if the shape is wrong."""
    if not isinstance(payload, dict):
        return None
    if source_type == "ollama":
        models = payload.get("models")
        if not isinstance(models, list):
            return None
        names = [m.get("name") for m in models if isinstance(m, dict)]
    else:  # lm_studio / llama_cpp -> OpenAI-compatible /v1/models
        data = payload.get("data")
        if not isinstance(data, list):
            return None
        names = [m.get("id") for m in data if isinstance(m, dict)]
    return [str(n) for n in names if n is not None]


def _default_transport(url: str, timeout: float) -> Tuple[int, Any]:
    import requests

    response = requests.get(url, timeout=timeout)
    return response.status_code, response.json()


def _record(
    *,
    source_type: str,
    base_url: str,
    reachable: bool,
    error_category: Optional[str] = None,
    model_count: Optional[int] = None,
    observed_models: Optional[List[str]] = None,
    response_latency_ms: Optional[int] = None,
    observed_at: Optional[str] = None,
) -> LocalBackendProbeRecord:
    return LocalBackendProbeRecord(
        source_type=source_type,
        base_url=base_url,
        reachable=reachable,
        evidence_tier="local_metadata_probe",
        model_count=model_count,
        observed_models=observed_models,
        response_latency_ms=response_latency_ms,
        error_category=error_category,
        observed_at=observed_at,
    )


def probe_local_backend(
    *,
    source_type: str,
    base_url: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    include_model_names: bool = False,
    enabled: bool = True,
    transport: Optional[Transport] = None,
) -> LocalBackendProbeRecord:
    """Probe a local backend's metadata endpoint. Never invokes a model.

    Returns a metadata-only :class:`LocalBackendProbeRecord`. Network failures
    fail closed with a closed ``error_category`` (never raw error text); this
    function raises :class:`ProbeInputError` only for argument/validation
    errors (secret-bearing or malformed ``base_url``). ``transport`` is
    injectable for offline tests.
    """
    import requests

    # Validate/redact the URL first so a bad URL never reaches the network.
    redacted = redact_base_url(base_url)

    if not enabled:
        return _record(
            source_type=source_type,
            base_url=redacted,
            reachable=False,
            error_category="probe_disabled",
        )

    if source_type not in SOURCE_TYPES:
        return _record(
            source_type=source_type,
            base_url=redacted,
            reachable=False,
            error_category="unsupported_backend",
        )

    url = redacted.rstrip("/") + METADATA_PATHS[source_type]
    observed_at = datetime.now(timezone.utc).isoformat()
    send: Transport = transport if transport is not None else _default_transport

    start = time.time()
    try:
        status, payload = send(url, timeout)
    except requests.exceptions.Timeout:
        return _record(
            source_type=source_type,
            base_url=redacted,
            reachable=False,
            error_category="timeout",
            observed_at=observed_at,
        )
    except (requests.exceptions.ConnectionError, ConnectionError, OSError) as exc:
        category = (
            "permission_or_policy_blocked"
            if isinstance(exc, PermissionError)
            else "endpoint_unreachable"
        )
        return _record(
            source_type=source_type,
            base_url=redacted,
            reachable=False,
            error_category=category,
            observed_at=observed_at,
        )
    except (ValueError, requests.exceptions.RequestException):
        # JSON decode failure or other response-shape problem.
        return _record(
            source_type=source_type,
            base_url=redacted,
            reachable=False,
            error_category="malformed_response",
            observed_at=observed_at,
        )
    latency_ms = int((time.time() - start) * 1000)

    if status == 403:
        return _record(
            source_type=source_type,
            base_url=redacted,
            reachable=False,
            error_category="permission_or_policy_blocked",
            observed_at=observed_at,
            response_latency_ms=latency_ms,
        )

    models = _extract_models(source_type, payload)
    if models is None:
        return _record(
            source_type=source_type,
            base_url=redacted,
            reachable=False,
            error_category="malformed_response",
            observed_at=observed_at,
            response_latency_ms=latency_ms,
        )

    observed_models = (
        _sanitize_model_identifiers(models) if include_model_names else None
    )
    return _record(
        source_type=source_type,
        base_url=redacted,
        reachable=True,
        model_count=len(models),
        observed_models=observed_models,
        response_latency_ms=latency_ms,
        observed_at=observed_at,
    )


def render_probe_record(record: LocalBackendProbeRecord) -> str:
    """Render a probe record as a human-readable, privacy-safe summary."""
    fields = record.to_dict()
    lines = [
        f"source_type:         {fields['source_type']}",
        f"base_url:            {fields['base_url']}",
        f"reachable:           {fields['reachable']}",
        f"evidence_tier:       {fields['evidence_tier']}",
    ]
    if fields["model_count"] is not None:
        lines.append(f"model_count:         {fields['model_count']}")
    if fields["observed_models"] is not None:
        lines.append(f"observed_models:     {', '.join(fields['observed_models'])}")
    if fields["response_latency_ms"] is not None:
        lines.append(f"response_latency_ms: {fields['response_latency_ms']}")
    if fields["error_category"] is not None:
        lines.append(f"error_category:      {fields['error_category']}")
    if fields["observed_at"] is not None:
        lines.append(f"observed_at:         {fields['observed_at']}")
    return "\n".join(lines)
