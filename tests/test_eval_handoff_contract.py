from pathlib import Path

from triage_core.eval_fixture_validator import SCHEMA_VERSION
from triage_core.eval_outcome_contract import build_actual_outcome, write_actual_outcome


REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_DOC = REPO_ROOT / "docs" / "evals" / "evaluation_handoff_contract.md"
ACTUAL_OUTCOME_DOC = REPO_ROOT / "docs" / "evals" / "actual_outcome_export.md"
FIXTURE_SCHEMA_DOC = REPO_ROOT / "docs" / "research" / "eval_fixture_schema.md"
BRIDGE_DOC = REPO_ROOT / "docs" / "evals" / "eval_integration_bridge.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_eval_handoff_contract_pins_versions_paths_and_exit_codes():
    doc = _read(CONTRACT_DOC)

    assert "evaluation_handoff_contract.v0" in doc
    assert SCHEMA_VERSION in doc
    assert "actual_outcome_export.v0" in doc
    assert "tests/fixtures/evals/safety_boundaries_v0.jsonl" in doc
    assert ".triagecore/eval_actuals/<run_id>/" in doc
    assert "actuals/triagecore_smoke/" in doc
    assert "fixtures/safety_boundaries_v0.jsonl" in doc
    assert "actuals/<case_id>.json" in doc
    assert "manifest/evaluation_handoff_manifest.json" in doc
    assert "Exit `0`" in doc
    assert "Exit `1`" in doc
    assert "Exit `2`" in doc


def test_eval_handoff_contract_preserves_external_scoring_boundary():
    doc = " ".join(_read(CONTRACT_DOC).lower().split())

    required_phrases = (
        "the external evaluator suite owns scoring",
        "treat evaluator findings as external artifacts",
        "cr-123 does not create that bundle, manifest, or builder",
        "no evaluator execution from triagecore",
        "no ledger writes",
        "scoring, pass/fail judgment, aggregate metrics, partial credit, or score interpretation inside triagecore",
    )
    for phrase in required_phrases:
        assert phrase in doc


def test_eval_handoff_contract_matches_actual_outcome_filename_rule(tmp_path):
    outcome = build_actual_outcome(
        case_id="privacy-deny-001",
        decision="block",
        boundary_family="privacy",
        reasons=["privacy_check_failed"],
        audit_required=True,
        human_approval_required=False,
    )

    path = write_actual_outcome(outcome, tmp_path)

    assert path.name == "privacy-deny-001.json"
    assert "<case_id>.json" in _read(CONTRACT_DOC)


def test_existing_eval_docs_link_to_handoff_contract():
    assert "evaluation_handoff_contract.md" in _read(ACTUAL_OUTCOME_DOC)
    assert "Evaluation Handoff Contract" in _read(FIXTURE_SCHEMA_DOC)
    assert "evaluation_handoff_contract.md" in _read(BRIDGE_DOC)
