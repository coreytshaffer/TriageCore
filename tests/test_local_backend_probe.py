"""Offline tests for the read-only local backend metadata probe (CR-114).

All tests run without a live backend. Network outcomes are exercised through an
injected transport or a closed local port; no test contacts a real model
endpoint, and no test writes to the real ledger.
"""
import json
import socket

import pytest
import requests

import triage_core.local_backend_probe as local_backend_probe
from triage_core.local_backend_probe import (
    ERROR_CATEGORIES,
    LocalBackendProbeRecord,
    ProbeInputError,
    local_backend_probe_record_from_mapping,
    probe_local_backend,
    redact_base_url,
    render_probe_record,
)
from triage_core.privacy_invariants import find_forbidden_persistent_fields


# ---- transports (injected) -------------------------------------------------

def _ollama_ok(url, timeout):
    return 200, {"models": [{"name": "qwen2.5-coder:7b"}, {"name": "llama3.1:8b"}]}


def _openai_ok(url, timeout):
    return 200, {"data": [{"id": "local-model"}, {"id": "another-model"}]}


def _path_like_models(url, timeout):
    return 200, {
        "models": [
            {"name": "qwen2.5-coder:7b"},
            {"name": "/home/corey/models/private.gguf"},
        ]
    }


def _malformed(url, timeout):
    return 200, {"unexpected": "shape"}


def _timeout(url, timeout):
    raise requests.exceptions.Timeout("timed out")


def _refused(url, timeout):
    raise requests.exceptions.ConnectionError("connection refused")


def _blocked(url, timeout):
    raise PermissionError("blocked by policy")


# ---- reachable / model counting -------------------------------------------

def test_reachable_ollama_counts_models_no_names_by_default():
    rec = probe_local_backend(
        source_type="ollama",
        base_url="http://localhost:11434",
        transport=_ollama_ok,
    )
    assert rec.reachable is True
    assert rec.model_count == 2
    assert rec.observed_models is None  # off by default
    assert rec.error_category is None
    assert rec.evidence_tier == "local_metadata_probe"


def test_successful_probe_result_is_validated_against_record_contract(monkeypatch):
    observed_payloads = []

    def spy(payload):
        observed_payloads.append(dict(payload))
        return local_backend_probe_record_from_mapping(payload)

    monkeypatch.setattr(
        local_backend_probe,
        "local_backend_probe_record_from_mapping",
        spy,
    )

    rec = probe_local_backend(
        source_type="ollama",
        base_url="http://localhost:11434",
        transport=_ollama_ok,
    )

    assert rec.reachable is True
    assert observed_payloads
    assert observed_payloads[0]["schema_version"] == "local_backend_probe_record.v1"
    assert observed_payloads[0]["source_type"] == "ollama"


def test_openai_shape_backends_use_v1_models():
    rec = probe_local_backend(
        source_type="lm_studio",
        base_url="http://localhost:1234",
        transport=_openai_ok,
    )
    assert rec.reachable is True
    assert rec.model_count == 2


def test_include_model_names_drops_path_like_identifiers():
    rec = probe_local_backend(
        source_type="ollama",
        base_url="http://localhost:11434",
        include_model_names=True,
        transport=_path_like_models,
    )
    assert rec.model_count == 2
    # The path-like identifier is dropped from the recorded names.
    assert rec.observed_models == ["qwen2.5-coder:7b"]


# ---- fail-closed categories (all valid records, exit 0 territory) ----------

def test_unsupported_backend_is_a_record_not_an_error():
    rec = probe_local_backend(
        source_type="vllm",  # outside the closed vocabulary
        base_url="http://localhost:8000",
        transport=_openai_ok,
    )
    assert rec.reachable is False
    assert rec.source_type == "unsupported"
    assert rec.error_category == "unsupported_backend"


def test_disabled_probe_emits_probe_disabled_record():
    rec = probe_local_backend(
        source_type="ollama",
        base_url="http://localhost:11434",
        enabled=False,
        transport=_ollama_ok,  # must not be consulted
    )
    assert rec.reachable is False
    assert rec.error_category == "probe_disabled"


def test_timeout_category():
    rec = probe_local_backend(
        source_type="ollama", base_url="http://localhost:11434", transport=_timeout
    )
    assert rec.reachable is False
    assert rec.error_category == "timeout"


def test_failed_probe_result_is_validated_against_record_contract(monkeypatch):
    observed_payloads = []

    def spy(payload):
        observed_payloads.append(dict(payload))
        return local_backend_probe_record_from_mapping(payload)

    monkeypatch.setattr(
        local_backend_probe,
        "local_backend_probe_record_from_mapping",
        spy,
    )

    rec = probe_local_backend(
        source_type="ollama",
        base_url="http://localhost:11434",
        transport=_timeout,
    )

    assert rec.reachable is False
    assert rec.error_category == "timeout"
    assert observed_payloads
    assert observed_payloads[0]["error_category"] == "timeout"


def test_probe_result_contract_validation_failure_fails_closed(monkeypatch):
    def reject(payload):
        raise ValueError("schema drift")

    monkeypatch.setattr(
        local_backend_probe,
        "local_backend_probe_record_from_mapping",
        reject,
    )

    with pytest.raises(ProbeInputError, match="CR-118 record-contract"):
        probe_local_backend(
            source_type="ollama",
            base_url="http://localhost:11434",
            transport=_ollama_ok,
        )


def test_endpoint_unreachable_category():
    rec = probe_local_backend(
        source_type="ollama", base_url="http://localhost:11434", transport=_refused
    )
    assert rec.reachable is False
    assert rec.error_category == "endpoint_unreachable"


def test_permission_or_policy_blocked_category():
    rec = probe_local_backend(
        source_type="ollama", base_url="http://localhost:11434", transport=_blocked
    )
    assert rec.reachable is False
    assert rec.error_category == "permission_or_policy_blocked"


def test_malformed_response_category():
    rec = probe_local_backend(
        source_type="ollama", base_url="http://localhost:11434", transport=_malformed
    )
    assert rec.reachable is False
    assert rec.error_category == "malformed_response"


def test_unreachable_against_closed_local_port_no_injection():
    # A genuinely closed local port: fail closed with no network fixture.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    closed_port = sock.getsockname()[1]
    sock.close()
    rec = probe_local_backend(
        source_type="ollama",
        base_url=f"http://127.0.0.1:{closed_port}",
        timeout=0.25,
    )
    assert rec.reachable is False
    assert rec.error_category in {"endpoint_unreachable", "timeout"}


# ---- base_url redaction / secret rejection --------------------------------

def test_base_url_redacts_path_to_scheme_host_port():
    assert redact_base_url("http://localhost:11434/api/tags") == "http://localhost:11434"
    assert redact_base_url("http://localhost:11434/some/path") == "http://localhost:11434"
    assert redact_base_url("http://localhost") == "http://localhost"


def test_base_url_with_userinfo_is_rejected():
    with pytest.raises(ProbeInputError):
        redact_base_url("http://user:secret@localhost:11434")


def test_base_url_with_query_is_rejected():
    with pytest.raises(ProbeInputError):
        redact_base_url("http://localhost:11434/v1/models?token=abc")


def test_probe_raises_input_error_for_secret_bearing_url():
    with pytest.raises(ProbeInputError):
        probe_local_backend(
            source_type="ollama",
            base_url="http://user:pass@localhost:11434",
            transport=_ollama_ok,
        )


# ---- privacy invariant / determinism --------------------------------------

def test_every_record_passes_persistent_privacy_invariant():
    rec = probe_local_backend(
        source_type="ollama",
        base_url="http://localhost:11434",
        include_model_names=True,
        transport=_ollama_ok,
    )
    assert find_forbidden_persistent_fields(rec.to_dict()) == []


def test_synthetic_fixture_tier_forbids_timestamp():
    # Fixture-tier records stay byte-identical: no observed_at allowed.
    ok = LocalBackendProbeRecord(
        source_type="ollama",
        base_url="http://localhost:11434",
        reachable=True,
        evidence_tier="synthetic_fixture",
        model_count=1,
    )
    assert ok.observed_at is None
    with pytest.raises(ValueError):
        LocalBackendProbeRecord(
            source_type="ollama",
            base_url="http://localhost:11434",
            reachable=True,
            evidence_tier="synthetic_fixture",
            model_count=1,
            observed_at="2026-07-09T00:00:00+00:00",
        )


def test_error_category_vocabulary_is_closed():
    with pytest.raises(ValueError):
        LocalBackendProbeRecord(
            source_type="ollama",
            base_url="http://localhost:11434",
            reachable=False,
            evidence_tier="local_metadata_probe",
            error_category="something_new",
        )
    assert "endpoint_unreachable" in ERROR_CATEGORIES


def test_render_is_readable_and_privacy_safe():
    rec = probe_local_backend(
        source_type="ollama",
        base_url="http://localhost:11434",
        transport=_ollama_ok,
    )
    text = render_probe_record(rec)
    assert "source_type:" in text
    assert "reachable:" in text
    # Rendering must not leak forbidden content (it is built from to_dict()).
    assert "secret" not in text.lower()
