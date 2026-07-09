import json
from pathlib import Path

from triage_core.review_result import (
    BOUNDARY,
    SCHEMA_VERSION,
    build_review_result,
    render_review_result,
)
from triage_core.review_submission import validate_review_submission

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "evals" / "model_review"
EXAMPLE_SUBMISSION = FIXTURE_DIR / "review_submission_v0.example.json"
EXAMPLE_PACKET = FIXTURE_DIR / "review_context_packet.example.md"
EXAMPLE_RESULT = FIXTURE_DIR / "review_result_v0.example.json"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


PACKET = (
    "---\nFILE: pyproject.toml\n---\n"
    "name = triagecore\n"
    "dependencies include cryptography\n\n"
    "---\nFILE: tests/test_identity_cli.py\n---\n"
    "def test_anchor_present():\n    pass\n"
)


def base_submission():
    return {
        "schema_version": "review_submission_v0",
        "context_packet_ref": "packet.md",
        "claims": [
            {
                "id": "s1",
                "text": "Supported.",
                "category": "context-supported",
                "citation": "FILE: pyproject.toml",
            },
            {"id": "n1", "text": "A next action.", "category": "authorized-next-action"},
        ],
    }


# --- Example fixture is reproducible and is an intentional FAIL ---------------


def test_example_result_matches_builder_output():
    submission = load(EXAMPLE_SUBMISSION)
    packet = EXAMPLE_PACKET.read_text(encoding="utf-8")
    expected = load(EXAMPLE_RESULT)
    assert build_review_result(submission, packet) == expected


def test_example_submission_is_still_structurally_valid():
    assert validate_review_submission(load(EXAMPLE_SUBMISSION)) == []


def test_example_is_intentional_fail_on_unresolved_citation():
    result = build_review_result(
        load(EXAMPLE_SUBMISSION), EXAMPLE_PACKET.read_text(encoding="utf-8")
    )
    assert result["grounding_gate"] == "fail"
    assert {"claim_id": "c4", "code": "unresolved_citation"} in result["gate_failures"]
    assert result["next_safe_action"] is None


# --- Citation resolution ------------------------------------------------------


def test_resolved_citation_passes_gate_and_selects_next_action():
    result = build_review_result(base_submission(), PACKET)
    assert result["grounding_gate"] == "pass"
    assert result["citation_map"] == [
        {"claim_id": "s1", "resolved": True, "matched_file": "pyproject.toml"}
    ]
    assert result["next_safe_action"] == {"claim_id": "n1"}


def test_unresolved_file_fails_gate():
    submission = base_submission()
    submission["claims"][0]["citation"] = "FILE: does/not/exist.py"
    result = build_review_result(submission, PACKET)
    assert result["grounding_gate"] == "fail"
    assert {"claim_id": "s1", "code": "unresolved_citation"} in result["gate_failures"]
    assert result["citation_map"][0]["resolved"] is False
    assert "matched_file" not in result["citation_map"][0]


def test_anchor_resolution_is_section_scoped():
    # Anchor text lives only in the test file section, but the citation points at
    # pyproject.toml, so it must NOT resolve from another file's content.
    submission = base_submission()
    submission["claims"][0]["citation"] = "FILE: pyproject.toml#test_anchor_present"
    result = build_review_result(submission, PACKET)
    assert result["grounding_gate"] == "fail"
    assert result["citation_map"][0] == {
        "claim_id": "s1",
        "resolved": False,
        "matched_file": "pyproject.toml",
    }


def test_anchor_resolves_within_correct_section():
    submission = base_submission()
    submission["claims"][0]["citation"] = (
        "FILE: tests/test_identity_cli.py#test_anchor_present"
    )
    result = build_review_result(submission, PACKET)
    assert result["grounding_gate"] == "pass"
    assert result["citation_map"][0]["resolved"] is True


# --- Severe contamination gate ------------------------------------------------


def test_severe_unsupported_category_fails_gate():
    for severe in ("production-readiness-claim", "scope-overreach"):
        submission = base_submission()
        submission["claims"].append(
            {
                "id": "u1",
                "text": "Severe claim.",
                "category": "unsupported",
                "unsupported_category": severe,
            }
        )
        result = build_review_result(submission, PACKET)
        assert result["grounding_gate"] == "fail"
        assert {
            "claim_id": "u1",
            "code": "severe_unsupported_category",
        } in result["gate_failures"]
        assert result["next_safe_action"] is None


def test_non_severe_unsupported_is_warning_not_gate_failure():
    submission = base_submission()
    submission["claims"].append(
        {
            "id": "u1",
            "text": "Benign claim.",
            "category": "unsupported",
            "unsupported_category": "assumption-as-fact",
        }
    )
    result = build_review_result(submission, PACKET)
    assert result["grounding_gate"] == "pass"
    assert {"claim_id": "u1", "unsupported_category": "assumption-as-fact"} in result[
        "unsupported_claims"
    ]
    assert {"claim_id": "u1", "code": "non_severe_unsupported"} in result["warnings"]


def test_uncertain_inference_is_warning():
    submission = base_submission()
    submission["claims"].append(
        {"id": "i1", "text": "An inference.", "category": "uncertain-inference"}
    )
    result = build_review_result(submission, PACKET)
    assert {"claim_id": "i1", "code": "uncertain_inference"} in result["warnings"]


# --- Scope check --------------------------------------------------------------


def test_scope_not_checked_when_changed_paths_absent():
    result = build_review_result(base_submission(), PACKET)
    assert result["scope_check"] == {"status": "not_checked", "out_of_scope": []}


def test_scope_pass_when_changes_within_declared_scope():
    submission = base_submission()
    submission["declared_scope"] = ["docs/evals/", "triage_core/review_result.py"]
    result = build_review_result(
        submission,
        PACKET,
        changed_paths=["docs/evals/x.md", "triage_core/review_result.py"],
    )
    assert result["scope_check"]["status"] == "pass"
    assert result["grounding_gate"] == "pass"


def test_scope_fail_when_change_outside_declared_scope():
    submission = base_submission()
    submission["declared_scope"] = ["docs/evals/"]
    result = build_review_result(
        submission, PACKET, changed_paths=["triage_core/tc_cli.py"]
    )
    assert result["scope_check"]["status"] == "fail"
    assert result["scope_check"]["out_of_scope"] == ["triage_core/tc_cli.py"]
    assert {"code": "scope_violation"} in result["gate_failures"]
    assert result["grounding_gate"] == "fail"


# --- Human review routing and next safe action --------------------------------


def test_human_review_required_actions_are_routed():
    submission = base_submission()
    submission["declared_actions"] = [
        {"text": "Safe docs edit.", "requires_human_review": False},
        {"text": "Risky change.", "requires_human_review": True},
    ]
    result = build_review_result(submission, PACKET)
    assert result["human_review_required"] == [{"action_index": 1}]


def test_next_safe_action_is_first_authorized_action_on_pass():
    submission = base_submission()
    submission["claims"].append(
        {"id": "n2", "text": "Second action.", "category": "authorized-next-action"}
    )
    result = build_review_result(submission, PACKET)
    assert result["next_safe_action"] == {"claim_id": "n1"}


def test_next_safe_action_suppressed_on_gate_fail():
    submission = base_submission()
    submission["claims"][0]["citation"] = "FILE: missing.py"
    result = build_review_result(submission, PACKET)
    assert result["grounding_gate"] == "fail"
    assert result["next_safe_action"] is None


def test_next_safe_action_identifies_by_claim_id_only():
    result = build_review_result(base_submission(), PACKET)
    assert set(result["next_safe_action"].keys()) == {"claim_id"}


# --- Boundary, leak-safety, no execution --------------------------------------


def test_result_carries_schema_version_and_boundary():
    result = build_review_result(base_submission(), PACKET)
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["boundary"] == BOUNDARY
    assert "not a correctness, safety, certification, or production-readiness" in (
        result["boundary"]
    )


def test_validation_commands_are_never_executed():
    submission = base_submission()
    submission["validation"] = [
        {"command": "rm -rf /", "recorded_result": "not_recorded"}
    ]
    # build_review_result must ignore validation content entirely (no execution,
    # no influence on the result).
    with_validation = build_review_result(submission, PACKET)
    without = build_review_result(base_submission(), PACKET)
    assert with_validation == without


def test_result_and_render_do_not_echo_claim_text():
    secret = "SECRET-CLAIM-TEXT-SHOULD-NOT-LEAK"
    submission = base_submission()
    submission["claims"][0]["text"] = secret
    result = build_review_result(submission, PACKET)
    assert secret not in json.dumps(result)
    assert secret not in render_review_result(result)


def test_render_contains_boundary_and_gate_and_is_ascii():
    result = build_review_result(base_submission(), PACKET)
    rendered = render_review_result(result)
    assert "grounding_gate: pass" in rendered
    assert BOUNDARY in rendered
    rendered.encode("ascii")  # raises if any non-ASCII char is present
