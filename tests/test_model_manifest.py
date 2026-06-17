from pathlib import Path

from triage_core.model_manifest import (
    compare_route_to_manifest,
    load_model_manifest,
    summarize_route_manifest_warning_report,
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


def test_matching_route_manifest_metadata_has_no_warnings():
    manifest = load_model_manifest(_example_path("model_route_manifest_local_ollama.json"))
    route_payload = {
        "selected_backend": "ollama",
        "selected_model": "qwen2.5:7b-instruct-q4_K_M",
        "selected_route": "local-ollama-qwen2.5-7b-instruct-q4km",
    }

    report = compare_route_to_manifest(route_payload, manifest)

    assert report.has_warnings is False
    assert report.warnings == []


def test_backend_mismatch_produces_warning():
    manifest = load_model_manifest(_example_path("model_route_manifest_local_ollama.json"))
    route_payload = {
        "selected_backend": "qwen_cloud",
        "selected_model": "qwen2.5:7b-instruct-q4_K_M",
        "selected_route": "local-ollama-qwen2.5-7b-instruct-q4km",
    }

    report = compare_route_to_manifest(route_payload, manifest)

    assert {warning.reason for warning in report.warnings} == {"backend_mismatch"}


def test_model_mismatch_produces_warning():
    manifest = load_model_manifest(_example_path("model_route_manifest_local_ollama.json"))
    route_payload = {
        "selected_backend": "ollama",
        "selected_model": "different-model",
        "selected_route": "local-ollama-qwen2.5-7b-instruct-q4km",
    }

    report = compare_route_to_manifest(route_payload, manifest)

    assert {warning.reason for warning in report.warnings} == {"model_mismatch"}


def test_alias_only_identity_produces_warning():
    manifest = load_model_manifest(
        _example_path("model_route_manifest_invalid_alias_only.json")
    )
    route_payload = {
        "selected_backend": "ollama",
        "selected_model": "latest",
        "selected_route": "alias-only-fast-route",
    }

    report = compare_route_to_manifest(route_payload, manifest)

    reasons = {warning.reason for warning in report.warnings}
    assert "alias_only_model_identity" in reasons


def test_incomplete_manifest_integrity_produces_warning():
    manifest = load_model_manifest(
        _example_path("model_route_manifest_invalid_alias_only.json")
    )
    route_payload = {
        "selected_backend": "ollama",
        "selected_model": "latest",
        "selected_route": "alias-only-fast-route",
    }

    report = compare_route_to_manifest(route_payload, manifest)

    reasons = {warning.reason for warning in report.warnings}
    assert "incomplete_integrity_status" in reasons


def test_warning_report_contains_only_metadata_without_raw_payload_echo():
    manifest = load_model_manifest(_example_path("model_route_manifest_local_ollama.json"))
    route_payload = {
        "selected_backend": "qwen_cloud",
        "selected_model": "private-model-alias",
        "selected_route": "private-route-alias",
        "prompt": "raw private prompt",
        "data": "raw private data",
    }

    report = compare_route_to_manifest(route_payload, manifest)
    rendered = "\n".join(
        f"{warning.reason} {warning.path} {warning.message}"
        for warning in report.warnings
    )

    assert "raw private prompt" not in rendered
    assert "raw private data" not in rendered
    assert "private-model-alias" not in rendered
    assert "private-route-alias" not in rendered


def test_warning_summary_passes_when_route_matches_manifest():
    manifest = load_model_manifest(_example_path("model_route_manifest_local_ollama.json"))
    route_path = _example_path("route_payload_local_ollama.json")
    route_payload = load_model_manifest(route_path)

    report = compare_route_to_manifest(route_payload, manifest)
    rendered = summarize_route_manifest_warning_report(
        _example_path("model_route_manifest_local_ollama.json"),
        route_path,
        report,
    )

    assert "Model route warning check passed" in rendered
    assert "warnings=0" in rendered


def test_warning_summary_lists_warning_reasons():
    manifest = load_model_manifest(_example_path("model_route_manifest_local_ollama.json"))
    route_payload = {
        "selected_backend": "qwen_cloud",
        "selected_model": "different-model",
        "selected_route": "wrong-route",
    }

    report = compare_route_to_manifest(route_payload, manifest)
    rendered = summarize_route_manifest_warning_report(
        _example_path("model_route_manifest_local_ollama.json"),
        "route-payload.json",
        report,
    )

    assert "Model route warning check warned" in rendered
    assert "warnings=3" in rendered
    assert "warning=backend_mismatch" in rendered
    assert "warning=model_mismatch" in rendered
    assert "warning=route_mismatch" in rendered
