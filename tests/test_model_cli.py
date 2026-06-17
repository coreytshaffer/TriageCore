from pathlib import Path

import pytest

from triage_core.tc_cli import tc_model_check, tc_model_warn


def _example_path(name: str) -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "docs"
        / "security"
        / "examples"
        / name
    )


def test_model_check_passes_local_ollama_manifest(capsys):
    tc_model_check(str(_example_path("model_route_manifest_local_ollama.json")))

    out = capsys.readouterr().out
    assert "Model manifest check passed" in out
    assert "backend_type=ollama" in out
    assert "integrity_status=complete" in out


def test_model_check_passes_cloud_qwen_manifest(capsys):
    tc_model_check(str(_example_path("model_route_manifest_cloud_qwen.json")))

    out = capsys.readouterr().out
    assert "Model manifest check passed" in out
    assert "backend_type=qwen_cloud" in out
    assert "integrity_status=complete" in out


def test_model_check_fails_invalid_alias_only_manifest(capsys):
    with pytest.raises(SystemExit) as exc:
        tc_model_check(str(_example_path("model_route_manifest_invalid_alias_only.json")))

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Model manifest check failed" in out
    assert "reason=alias_only_model_identity" in out


def test_model_check_missing_manifest_fails(capsys):
    with pytest.raises(SystemExit) as exc:
        tc_model_check("missing-model-manifest.json")

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Error: missing-model-manifest.json not found." in out


def test_model_warn_passes_when_route_matches_manifest(capsys):
    tc_model_warn(
        str(_example_path("model_route_manifest_local_ollama.json")),
        str(_example_path("route_payload_local_ollama.json")),
    )

    out = capsys.readouterr().out
    assert "Model route warning check passed" in out
    assert "warnings=0" in out


def test_model_warn_emits_warning_summary_but_exits_zero(capsys, tmp_path):
    route_path = tmp_path / "warning_route_payload.json"
    route_path.write_text(
        (
            "{\n"
            '  "selected_backend": "qwen_cloud",\n'
            '  "selected_model": "different-model",\n'
            '  "selected_route": "wrong-route"\n'
            "}\n"
        ),
        encoding="utf-8",
    )

    tc_model_warn(
        str(_example_path("model_route_manifest_local_ollama.json")),
        str(route_path),
    )

    out = capsys.readouterr().out
    assert "Model route warning check warned" in out
    assert "warning=backend_mismatch" in out
    assert "warning=model_mismatch" in out
    assert "warning=route_mismatch" in out


def test_model_warn_missing_route_fails(capsys):
    with pytest.raises(SystemExit) as exc:
        tc_model_warn(
            str(_example_path("model_route_manifest_local_ollama.json")),
            "missing-route-payload.json",
        )

    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "Error: missing-route-payload.json not found." in out
