import json
from pathlib import Path

import pytest

from triage_core.local_backend_probe import (
    SCHEMA_VERSION,
    LocalBackendProbeRecord,
    local_backend_probe_record_from_mapping,
)


SCHEMA_PATH = Path("schemas/local_backend_probe_record.schema.json")


def _synthetic_record(**overrides):
    record = {
        "schema_version": SCHEMA_VERSION,
        "source_type": "ollama",
        "base_url": "http://localhost:11434",
        "reachable": True,
        "evidence_tier": "synthetic_fixture",
        "model_count": 2,
        "observed_models": None,
        "response_latency_ms": None,
        "error_category": None,
        "observed_at": None,
    }
    record.update(overrides)
    return record


def test_synthetic_fixture_contract_round_trips_without_probe_execution():
    payload = _synthetic_record()

    loaded = local_backend_probe_record_from_mapping(payload)

    assert loaded.to_dict() == payload


def test_contract_rejects_unknown_fields():
    payload = _synthetic_record(extra_field="not allowed")

    with pytest.raises(ValueError, match="unknown field: extra_field"):
        local_backend_probe_record_from_mapping(payload)


def test_contract_rejects_missing_fields():
    payload = _synthetic_record()
    payload.pop("observed_models")

    with pytest.raises(ValueError, match="missing field: observed_models"):
        local_backend_probe_record_from_mapping(payload)


def test_contract_rejects_raw_persistent_content_keys():
    payload = _synthetic_record(raw_prompt="do not persist")

    with pytest.raises(ValueError, match="raw_prompt|forbidden"):
        local_backend_probe_record_from_mapping(payload)


def test_contract_rejects_arbitrary_source_type():
    payload = _synthetic_record(source_type="vllm")

    with pytest.raises(ValueError, match="invalid source_type"):
        local_backend_probe_record_from_mapping(payload)


def test_unsupported_backend_requires_unsupported_sentinel():
    payload = _synthetic_record(
        source_type="ollama",
        reachable=False,
        error_category="unsupported_backend",
    )

    with pytest.raises(ValueError, match="source_type=unsupported"):
        local_backend_probe_record_from_mapping(payload)


def test_unsupported_sentinel_is_reserved_for_unsupported_backend():
    payload = _synthetic_record(
        source_type="unsupported",
        reachable=False,
        error_category="endpoint_unreachable",
    )

    with pytest.raises(ValueError, match="reserved for unsupported_backend"):
        local_backend_probe_record_from_mapping(payload)


def test_valid_unsupported_backend_record_uses_sentinel_only():
    payload = _synthetic_record(
        source_type="unsupported",
        reachable=False,
        model_count=None,
        error_category="unsupported_backend",
    )

    loaded = local_backend_probe_record_from_mapping(payload)

    assert loaded.source_type == "unsupported"
    assert loaded.error_category == "unsupported_backend"


def test_contract_rejects_path_like_model_identifiers():
    payload = _synthetic_record(observed_models=["qwen2.5", "C:\\models\\private.gguf"])

    with pytest.raises(ValueError, match="path-like"):
        local_backend_probe_record_from_mapping(payload)


def test_contract_rejects_secret_bearing_or_unredacted_base_url():
    with pytest.raises(ValueError, match="userinfo"):
        local_backend_probe_record_from_mapping(
            _synthetic_record(base_url="http://user:secret@localhost:11434")
        )
    with pytest.raises(ValueError, match="query string"):
        local_backend_probe_record_from_mapping(
            _synthetic_record(base_url="http://localhost:11434/v1/models?token=abc")
        )
    with pytest.raises(ValueError, match="normalized"):
        local_backend_probe_record_from_mapping(
            _synthetic_record(base_url="http://localhost:11434/v1/models")
        )


def test_synthetic_fixture_records_forbid_timestamps():
    payload = _synthetic_record(observed_at="2026-07-09T00:00:00+00:00")

    with pytest.raises(ValueError, match="synthetic_fixture"):
        local_backend_probe_record_from_mapping(payload)


def test_schema_artifact_pins_closed_source_type_and_unsupported_relation():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["properties"]["source_type"]["enum"] == [
        "ollama",
        "lm_studio",
        "llama_cpp",
        "unsupported",
    ]
    assert schema["additionalProperties"] is False
    assert {
        "properties": {"error_category": {"const": "unsupported_backend"}},
        "required": ["error_category"],
    } in [rule["if"] for rule in schema["allOf"]]


def test_dataclass_rejects_invalid_contract_without_mapping_loader():
    with pytest.raises(ValueError, match="unsupported_backend"):
        LocalBackendProbeRecord(
            source_type="unsupported",
            base_url="http://localhost:11434",
            reachable=False,
            evidence_tier="synthetic_fixture",
        )
