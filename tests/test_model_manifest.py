from pathlib import Path

from triage_core.model_manifest import (
    load_model_manifest,
    validate_model_manifest,
)


def _example_path(name: str) -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "security"
        / "examples"
        / name
    )


def test_local_ollama_manifest_passes():
    manifest = load_model_manifest(_example_path("model_route_manifest_local_ollama.json"))

    result = validate_model_manifest(manifest)

    assert result.is_valid is True
    assert result.issues == []


def test_cloud_qwen_manifest_passes():
    manifest = load_model_manifest(_example_path("model_route_manifest_cloud_qwen.json"))

    result = validate_model_manifest(manifest)

    assert result.is_valid is True
    assert result.issues == []


def test_invalid_alias_only_manifest_fails_with_alias_reason():
    manifest = load_model_manifest(
        _example_path("model_route_manifest_invalid_alias_only.json")
    )

    result = validate_model_manifest(manifest)

    assert result.is_valid is False
    reasons = {issue.reason for issue in result.issues}
    assert "alias_only_model_identity" in reasons
    assert "boundary_unknown" in reasons
    assert "missing_required_digest" in reasons


def test_manifest_missing_required_field_fails():
    manifest = {
        "schema_version": "1.0.0",
        "route_id": "missing-fields",
    }

    result = validate_model_manifest(manifest)

    assert result.is_valid is False
    assert any(issue.reason == "missing_required_field" for issue in result.issues)
