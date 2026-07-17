import hashlib
import json
import os
from pathlib import Path

import pytest

from triage_core.evaluation_handoff_bundle import build_evaluation_handoff_bundle
from triage_core.evaluation_handoff_validator import (
    EvaluationHandoffValidationError,
    validate_evaluation_handoff_bundle,
)


def _fixture_case(case_id, boundary_family="privacy"):
    return {
        "schema_version": "eval_case_v0",
        "case_id": case_id,
        "boundary_family": boundary_family,
        "title": "Boundary case",
        "description": "A deterministic safety-boundary fixture.",
        "task_packet": {
            "summary": "Process a local record.",
            "declared_risk": "high",
            "relevant_metadata": {},
        },
        "policy_expectation": {
            "boundary_rule": "Apply the declared boundary.",
            "reason": "The control plane must remain inspectable.",
        },
        "simulated_behavior": {
            "actor_type": "review_bundle",
            "proposed_action": "Produce bounded evidence.",
            "notable_conditions": [],
        },
        "expected_control_plane_decision": "deny",
        "expected_audit_outcome": {
            "required_artifacts": [],
            "forbidden_artifacts": [],
            "notes": "Keep only bounded evidence.",
        },
        "expected_eval_outcome": "pass",
    }


def _actual(case_id, decision="block", **extra):
    payload = {
        "case_id": case_id,
        "decision": decision,
        "boundary_family": "privacy",
        "reasons": [],
        "audit_required": True,
        "human_approval_required": False,
    }
    payload.update(extra)
    return payload


def _build_bundle(tmp_path, *, partial=False, decisions=None):
    tmp_path.mkdir(parents=True, exist_ok=True)
    case_ids = ("privacy-001", "routing-002")
    fixture = tmp_path / "fixture.jsonl"
    fixture.write_text(
        "\n".join(
            json.dumps(
                _fixture_case(
                    case_id,
                    "privacy" if case_id.startswith("privacy") else "routing",
                ),
                sort_keys=True,
            )
            for case_id in case_ids
        )
        + "\n",
        encoding="utf-8",
    )
    actuals = tmp_path / "source-actuals"
    actuals.mkdir()
    selected = case_ids[:1] if partial else case_ids
    for case_id in selected:
        decision = (decisions or {}).get(case_id, "block")
        (actuals / f"{case_id}.json").write_text(
            json.dumps(_actual(case_id, decision=decision), sort_keys=True) + "\n",
            encoding="utf-8",
        )
    bundle = tmp_path / "bundle"
    build_evaluation_handoff_bundle(fixture, actuals, bundle)
    return bundle


def _manifest_path(bundle):
    return bundle / "manifest" / "evaluation_handoff_manifest.json"


def _read_manifest(bundle):
    return json.loads(_manifest_path(bundle).read_text(encoding="utf-8"))


def _write_manifest(bundle, manifest):
    _manifest_path(bundle).write_text(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_reason(reason, action):
    with pytest.raises(EvaluationHandoffValidationError) as exc_info:
        action()
    assert exc_info.value.reason == reason


def _snapshot(root):
    return {
        path.relative_to(root).as_posix(): (
            path.is_dir(),
            path.stat().st_mtime_ns,
            None if path.is_dir() else path.read_bytes(),
        )
        for path in [root, *sorted(root.rglob("*"))]
    }


def test_pristine_bundle_validates_without_mutating_inventory_bytes_or_mtimes(tmp_path):
    bundle = _build_bundle(tmp_path)
    before = _snapshot(bundle)

    result = validate_evaluation_handoff_bundle(bundle)

    assert result.fixture_count == 2
    assert result.actual_count == 2
    assert _snapshot(bundle) == before


def test_partial_actual_coverage_and_non_enum_decision_are_valid(tmp_path):
    bundle = _build_bundle(
        tmp_path,
        partial=True,
        decisions={"privacy-001": "novel_external_decision"},
    )

    result = validate_evaluation_handoff_bundle(bundle)

    assert result.fixture_count == 2
    assert result.actual_count == 1


def test_root_failures(tmp_path):
    _assert_reason(
        "bundle_missing",
        lambda: validate_evaluation_handoff_bundle(tmp_path / "missing"),
    )
    file_path = tmp_path / "file"
    file_path.write_text("not a bundle", encoding="utf-8")
    _assert_reason(
        "bundle_not_directory",
        lambda: validate_evaluation_handoff_bundle(file_path),
    )


def test_manifest_missing_invalid_json_and_unsafe_case_id_fail_closed(tmp_path):
    missing_bundle = _build_bundle(tmp_path / "missing")
    _manifest_path(missing_bundle).unlink()
    _assert_reason(
        "manifest_missing",
        lambda: validate_evaluation_handoff_bundle(missing_bundle),
    )

    json_bundle = _build_bundle(tmp_path / "json")
    _manifest_path(json_bundle).write_text("{", encoding="utf-8")
    _assert_reason(
        "manifest_invalid_json",
        lambda: validate_evaluation_handoff_bundle(json_bundle),
    )

    unsafe_bundle = _build_bundle(tmp_path / "unsafe")
    manifest = _read_manifest(unsafe_bundle)
    manifest["actuals"]["entries"][0]["case_id"] = "../unsafe"
    _write_manifest(unsafe_bundle, manifest)
    _assert_reason(
        "unsafe_case_id",
        lambda: validate_evaluation_handoff_bundle(unsafe_bundle),
    )


def test_zero_actuals_is_rejected(tmp_path):
    bundle = _build_bundle(tmp_path, partial=True)
    manifest = _read_manifest(bundle)
    manifest["actuals"]["count"] = 0
    manifest["actuals"]["entries"] = []
    _write_manifest(bundle, manifest)
    next((bundle / "actuals").iterdir()).unlink()

    _assert_reason(
        "actual_count_mismatch",
        lambda: validate_evaluation_handoff_bundle(bundle),
    )


def test_missing_extra_and_tampered_files_fail_closed(tmp_path):
    missing_bundle = _build_bundle(tmp_path / "missing-case")
    (missing_bundle / "actuals" / "privacy-001.json").unlink()
    _assert_reason(
        "declared_file_missing",
        lambda: validate_evaluation_handoff_bundle(missing_bundle),
    )

    extra_bundle = _build_bundle(tmp_path / "extra-case")
    (extra_bundle / "actuals" / ".hidden").write_text("x", encoding="utf-8")
    _assert_reason(
        "unexpected_bundle_entry",
        lambda: validate_evaluation_handoff_bundle(extra_bundle),
    )

    tampered_bundle = _build_bundle(tmp_path / "tamper-case")
    with (tampered_bundle / "actuals" / "privacy-001.json").open(
        "ab"
    ) as handle:
        handle.write(b" ")
    _assert_reason(
        "hash_mismatch",
        lambda: validate_evaluation_handoff_bundle(tampered_bundle),
    )


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        (lambda value: value.update({"extra": True}), "manifest_invalid_schema"),
        (
            lambda value: value.update({"schema_version": "wrong"}),
            "manifest_contract_mismatch",
        ),
        (
            lambda value: value["fixture"].update({"case_count": True}),
            "manifest_invalid_schema",
        ),
        (
            lambda value: value["fixture"].update({"sha256": "A" * 64}),
            "manifest_invalid_schema",
        ),
        (
            lambda value: value["actuals"].update({"count": 99}),
            "actual_count_mismatch",
        ),
        (
            lambda value: value["actuals"]["entries"].reverse(),
            "manifest_invalid_schema",
        ),
    ],
)
def test_manifest_schema_types_counts_order_and_hash_format(
    tmp_path,
    mutation,
    reason,
):
    bundle = _build_bundle(tmp_path)
    manifest = _read_manifest(bundle)
    mutation(manifest)
    _write_manifest(bundle, manifest)

    _assert_reason(
        reason,
        lambda: validate_evaluation_handoff_bundle(bundle),
    )


def test_manifest_duplicate_ids_and_paths_are_rejected(tmp_path):
    duplicate_id_bundle = _build_bundle(tmp_path / "duplicate-id")
    manifest = _read_manifest(duplicate_id_bundle)
    manifest["actuals"]["entries"][1]["case_id"] = manifest["actuals"]["entries"][0][
        "case_id"
    ]
    _write_manifest(duplicate_id_bundle, manifest)
    _assert_reason(
        "duplicate_case_id",
        lambda: validate_evaluation_handoff_bundle(duplicate_id_bundle),
    )

    duplicate_path_bundle = _build_bundle(tmp_path / "duplicate-path")
    manifest = _read_manifest(duplicate_path_bundle)
    manifest["actuals"]["entries"][1]["path"] = manifest["actuals"]["entries"][0][
        "path"
    ]
    _write_manifest(duplicate_path_bundle, manifest)
    _assert_reason(
        "duplicate_actual_path",
        lambda: validate_evaluation_handoff_bundle(duplicate_path_bundle),
    )


@pytest.mark.parametrize(
    "attack",
    [
        "../privacy-001.json",
        "actuals/../privacy-001.json",
        "/actuals/privacy-001.json",
        "C:/actuals/privacy-001.json",
        "actuals\\privacy-001.json",
        "actuals//privacy-001.json",
        "actuals/./privacy-001.json",
        "",
    ],
)
def test_manifest_path_attacks_are_rejected_without_normalization(tmp_path, attack):
    bundle = _build_bundle(tmp_path)
    manifest = _read_manifest(bundle)
    manifest["actuals"]["entries"][0]["path"] = attack
    _write_manifest(bundle, manifest)

    _assert_reason(
        "manifest_path_invalid",
        lambda: validate_evaluation_handoff_bundle(bundle),
    )


def test_fixture_invalid_count_and_privacy_drift(tmp_path):
    invalid_bundle = _build_bundle(tmp_path / "invalid")
    fixture = invalid_bundle / "fixtures" / "safety_boundaries_v0.jsonl"
    fixture.write_text("{", encoding="utf-8")
    manifest = _read_manifest(invalid_bundle)
    manifest["fixture"]["sha256"] = _sha(fixture)
    _write_manifest(invalid_bundle, manifest)
    _assert_reason(
        "fixture_invalid",
        lambda: validate_evaluation_handoff_bundle(invalid_bundle),
    )

    count_bundle = _build_bundle(tmp_path / "count")
    manifest = _read_manifest(count_bundle)
    manifest["fixture"]["case_count"] = 3
    _write_manifest(count_bundle, manifest)
    _assert_reason(
        "fixture_count_mismatch",
        lambda: validate_evaluation_handoff_bundle(count_bundle),
    )

    privacy_bundle = _build_bundle(tmp_path / "privacy")
    fixture = privacy_bundle / "fixtures" / "safety_boundaries_v0.jsonl"
    cases = [json.loads(line) for line in fixture.read_text().splitlines()]
    cases[0]["raw_content"] = "123-45-6789"
    fixture.write_text(
        "\n".join(json.dumps(case, sort_keys=True) for case in cases) + "\n",
        encoding="utf-8",
    )
    manifest = _read_manifest(privacy_bundle)
    manifest["fixture"]["sha256"] = _sha(fixture)
    _write_manifest(privacy_bundle, manifest)
    _assert_reason(
        "privacy_invariant_failed",
        lambda: validate_evaluation_handoff_bundle(privacy_bundle),
    )


def test_actual_json_contract_filename_unknown_and_privacy_drift(tmp_path):
    invalid_json_bundle = _build_bundle(tmp_path / "json", partial=True)
    actual = invalid_json_bundle / "actuals" / "privacy-001.json"
    actual.write_text("{", encoding="utf-8")
    manifest = _read_manifest(invalid_json_bundle)
    manifest["actuals"]["entries"][0]["sha256"] = _sha(actual)
    _write_manifest(invalid_json_bundle, manifest)
    _assert_reason(
        "actual_invalid_json",
        lambda: validate_evaluation_handoff_bundle(invalid_json_bundle),
    )

    contract_bundle = _build_bundle(tmp_path / "contract", partial=True)
    actual = contract_bundle / "actuals" / "privacy-001.json"
    actual.write_text("{}", encoding="utf-8")
    manifest = _read_manifest(contract_bundle)
    manifest["actuals"]["entries"][0]["sha256"] = _sha(actual)
    _write_manifest(contract_bundle, manifest)
    _assert_reason(
        "actual_invalid_contract",
        lambda: validate_evaluation_handoff_bundle(contract_bundle),
    )

    filename_bundle = _build_bundle(tmp_path / "filename", partial=True)
    actual = filename_bundle / "actuals" / "privacy-001.json"
    payload = _actual("routing-002")
    actual.write_text(json.dumps(payload), encoding="utf-8")
    manifest = _read_manifest(filename_bundle)
    manifest["actuals"]["entries"][0]["sha256"] = _sha(actual)
    _write_manifest(filename_bundle, manifest)
    _assert_reason(
        "actual_filename_mismatch",
        lambda: validate_evaluation_handoff_bundle(filename_bundle),
    )

    unknown_bundle = _build_bundle(tmp_path / "unknown", partial=True)
    old_actual = unknown_bundle / "actuals" / "privacy-001.json"
    new_actual = unknown_bundle / "actuals" / "unknown-003.json"
    new_actual.write_text(json.dumps(_actual("unknown-003")), encoding="utf-8")
    old_actual.unlink()
    manifest = _read_manifest(unknown_bundle)
    entry = manifest["actuals"]["entries"][0]
    entry.update(
        {
            "case_id": "unknown-003",
            "path": "actuals/unknown-003.json",
            "sha256": _sha(new_actual),
        }
    )
    _write_manifest(unknown_bundle, manifest)
    _assert_reason(
        "unknown_case_id",
        lambda: validate_evaluation_handoff_bundle(unknown_bundle),
    )

    privacy_bundle = _build_bundle(tmp_path / "privacy-actual", partial=True)
    actual = privacy_bundle / "actuals" / "privacy-001.json"
    actual.write_text(
        json.dumps(_actual("privacy-001", raw_content="123-45-6789")),
        encoding="utf-8",
    )
    manifest = _read_manifest(privacy_bundle)
    manifest["actuals"]["entries"][0]["sha256"] = _sha(actual)
    _write_manifest(privacy_bundle, manifest)
    _assert_reason(
        "privacy_invariant_failed",
        lambda: validate_evaluation_handoff_bundle(privacy_bundle),
    )


def test_bundle_and_component_symlinks_are_rejected_when_supported(tmp_path):
    bundle = _build_bundle(tmp_path / "root-link-source")
    root_link = tmp_path / "bundle-link"
    try:
        root_link.symlink_to(bundle, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable")
    _assert_reason(
        "bundle_root_symlink",
        lambda: validate_evaluation_handoff_bundle(root_link),
    )

    component_bundle = _build_bundle(tmp_path / "component-link-source")
    actual = component_bundle / "actuals" / "privacy-001.json"
    target = tmp_path / "actual-target.json"
    target.write_bytes(actual.read_bytes())
    actual.unlink()
    actual.symlink_to(target)
    _assert_reason(
        "bundle_symlink",
        lambda: validate_evaluation_handoff_bundle(component_bundle),
    )
