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
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple
from urllib.parse import urlsplit

from .privacy_invariants import assert_persistent_privacy_safe

SCHEMA_VERSION = "local_backend_probe_record.v1"

SOURCE_TYPES = frozenset({"ollama", "lm_studio", "llama_cpp"})
SERIALIZED_SOURCE_TYPES = SOURCE_TYPES | frozenset({"unsupported"})
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

RECORD_FIELDS = frozenset(
    {
        "schema_version",
        "source_type",
        "base_url",
        "reachable",
        "evidence_tier",
        "model_count",
        "observed_models",
        "response_latency_ms",
        "error_category",
        "observed_at",
    }
)

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
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
        if self.source_type not in SERIALIZED_SOURCE_TYPES:
            raise ValueError(f"invalid source_type: {self.source_type}")
        if self.evidence_tier not in EVIDENCE_TIERS:
            raise ValueError(f"invalid evidence_tier: {self.evidence_tier}")
        if (
            self.error_category is not None
            and self.error_category not in ERROR_CATEGORIES
        ):
            raise ValueError(f"invalid error_category: {self.error_category}")
        if (
            self.error_category == "unsupported_backend"
            and self.source_type != "unsupported"
        ):
            raise ValueError(
                "unsupported_backend records must use source_type=unsupported"
            )
        if (
            self.source_type == "unsupported"
            and self.error_category != "unsupported_backend"
        ):
            raise ValueError(
                "source_type=unsupported is reserved for unsupported_backend records"
            )
        # Determinism: fixture-tier records must carry no timestamp.
        if self.evidence_tier == "synthetic_fixture" and self.observed_at is not None:
            raise ValueError("synthetic_fixture records must not carry observed_at")
        if self.model_count is not None and self.model_count < 0:
            raise ValueError("model_count must be non-negative")
        if self.response_latency_ms is not None and self.response_latency_ms < 0:
            raise ValueError("response_latency_ms must be non-negative")
        if self.observed_models is not None:
            if not isinstance(self.observed_models, Sequence) or isinstance(
                self.observed_models, (str, bytes, bytearray)
            ):
                raise ValueError("observed_models must be a list of strings")
            for model_id in self.observed_models:
                if not isinstance(model_id, str) or not model_id.strip():
                    raise ValueError("observed_models must be a list of strings")
                if _PATH_LIKE.search(model_id):
                    raise ValueError("observed_models must not contain path-like ids")

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


def local_backend_probe_record_from_mapping(
    payload: Mapping[str, Any],
) -> LocalBackendProbeRecord:
    """Load a serialized local backend probe record through the strict contract.

    This is a pure validator/mapper for already-recorded metadata. It does not
    probe endpoints, write artifacts, route tasks, or call a model.
    """
    assert_persistent_privacy_safe(
        dict(payload),
        artifact_name="local backend probe record",
    )
    _reject_unknown_record_fields(payload)

    return LocalBackendProbeRecord(
        schema_version=_mapping_text(payload, "schema_version"),
        source_type=_mapping_text(payload, "source_type"),
        base_url=_mapping_optional_base_url(payload, "base_url"),
        reachable=_mapping_bool(payload, "reachable"),
        evidence_tier=_mapping_text(payload, "evidence_tier"),
        model_count=_mapping_optional_int(payload, "model_count"),
        observed_models=_mapping_optional_string_list(payload, "observed_models"),
        response_latency_ms=_mapping_optional_int(payload, "response_latency_ms"),
        error_category=_mapping_optional_text(payload, "error_category"),
        observed_at=_mapping_optional_text(payload, "observed_at"),
    )


def _reject_unknown_record_fields(payload: Mapping[str, Any]) -> None:
    for key in payload:
        key_text = str(key)
        if key_text not in RECORD_FIELDS:
            raise ValueError(f"unknown field: {key_text}")
    for key in sorted(RECORD_FIELDS):
        if key not in payload:
            raise ValueError(f"missing field: {key}")


def _mapping_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _mapping_optional_text(payload: Mapping[str, Any], key: str) -> Optional[str]:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be null or a non-empty string")
    return value


def _mapping_bool(payload: Mapping[str, Any], key: str) -> bool:
    value = payload.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def _mapping_optional_int(payload: Mapping[str, Any], key: str) -> Optional[int]:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{key} must be null or an integer")
    return value


def _mapping_optional_string_list(
    payload: Mapping[str, Any], key: str
) -> Optional[List[str]]:
    value = payload.get(key)
    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{key} must be null or a list of strings")
    result: List[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{key} must be null or a list of strings")
        result.append(item)
    return result


def _mapping_optional_base_url(payload: Mapping[str, Any], key: str) -> Optional[str]:
    value = _mapping_optional_text(payload, key)
    if value is None:
        return None
    if redact_base_url(value) != value:
        raise ValueError("base_url must be normalized as scheme://host[:port]")
    return value


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
    record = LocalBackendProbeRecord(
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
    return _validate_emitted_probe_record(record)


def _validate_emitted_probe_record(
    record: LocalBackendProbeRecord,
) -> LocalBackendProbeRecord:
    """Fail closed unless the emitted probe record satisfies the CR-118 contract."""
    try:
        return local_backend_probe_record_from_mapping(record.to_dict())
    except (ProbeInputError, ValueError) as exc:
        raise ProbeInputError(
            "probe result failed CR-118 record-contract validation"
        ) from exc


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

    if source_type not in SOURCE_TYPES:
        return _record(
            source_type="unsupported",
            base_url=redacted,
            reachable=False,
            error_category="unsupported_backend",
        )

    if not enabled:
        return _record(
            source_type=source_type,
            base_url=redacted,
            reachable=False,
            error_category="probe_disabled",
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
