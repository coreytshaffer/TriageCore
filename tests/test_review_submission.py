import json
from pathlib import Path

from triage_core.review_submission import (
    load_review_submission,
    validate_review_submission,
)

EXAMPLE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "evals"
    / "model_review"
    / "review_submission_v0.example.json"
)


def make_valid():
    return {
        "schema_version": "review_submission_v0",
        "context_packet_ref": "scratch/bundle.md",
        "claims": [
            {
                "id": "c1",
                "text": "A supported claim.",
                "category": "context-supported",
                "citation": "FILE: pyproject.toml",
            },
            {"id": "c2", "text": "An inference.", "category": "uncertain-inference"},
            {
                "id": "c3",
                "text": "An unsupported claim.",
                "category": "unsupported",
                "unsupported_category": "assumption-as-fact",
            },
            {"id": "c4", "text": "A next action.", "category": "authorized-next-action"},
        ],
        "declared_actions": [{"text": "Do X.", "requires_human_review": True}],
    }


def has(errors, path, code):
    return {"path": path, "code": code} in errors


def test_make_valid_helper_passes():
    assert validate_review_submission(make_valid()) == []


def test_example_fixture_is_structurally_valid():
    submission = load_review_submission(EXAMPLE_PATH)
    assert validate_review_submission(submission) == []


def test_example_fixture_uses_schema_version():
    submission = load_review_submission(EXAMPLE_PATH)
    assert submission["schema_version"] == "review_submission_v0"


def test_non_dict_object_is_wrong_type():
    errors = validate_review_submission(["not", "a", "dict"])
    assert errors == [{"path": "$", "code": "wrong_type"}]


def test_missing_schema_version():
    obj = make_valid()
    del obj["schema_version"]
    assert has(validate_review_submission(obj), "$.schema_version", "missing_field")


def test_invalid_schema_version():
    obj = make_valid()
    obj["schema_version"] = "review_submission_v1"
    assert has(
        validate_review_submission(obj), "$.schema_version", "invalid_schema_version"
    )


def test_missing_context_packet_ref():
    obj = make_valid()
    del obj["context_packet_ref"]
    assert has(
        validate_review_submission(obj), "$.context_packet_ref", "missing_field"
    )


def test_empty_context_packet_ref():
    obj = make_valid()
    obj["context_packet_ref"] = "   "
    assert has(validate_review_submission(obj), "$.context_packet_ref", "empty_value")


def test_missing_claims():
    obj = make_valid()
    del obj["claims"]
    assert has(validate_review_submission(obj), "$.claims", "missing_field")


def test_empty_claims():
    obj = make_valid()
    obj["claims"] = []
    assert has(validate_review_submission(obj), "$.claims", "empty_claims")


def test_claim_missing_text():
    obj = make_valid()
    del obj["claims"][0]["text"]
    assert has(validate_review_submission(obj), "$.claims[0].text", "missing_field")


def test_claim_empty_text():
    obj = make_valid()
    obj["claims"][0]["text"] = ""
    assert has(validate_review_submission(obj), "$.claims[0].text", "empty_value")


def test_claim_invalid_category():
    obj = make_valid()
    obj["claims"][1]["category"] = "made-up-category"
    assert has(validate_review_submission(obj), "$.claims[1].category", "invalid_category")


def test_context_supported_missing_citation():
    obj = make_valid()
    del obj["claims"][0]["citation"]
    assert has(validate_review_submission(obj), "$.claims[0].citation", "missing_citation")


def test_context_supported_bad_citation_format():
    obj = make_valid()
    obj["claims"][0]["citation"] = "just some prose with no anchor"
    assert has(
        validate_review_submission(obj), "$.claims[0].citation", "invalid_citation_format"
    )


def test_citation_anchor_pair_is_valid_format():
    obj = make_valid()
    obj["claims"][0]["citation"] = "README.md#safety-invariants"
    assert validate_review_submission(obj) == []


def test_optional_citation_on_other_category_still_format_checked():
    obj = make_valid()
    obj["claims"][1]["citation"] = "bad prose"
    assert has(
        validate_review_submission(obj), "$.claims[1].citation", "invalid_citation_format"
    )


def test_unsupported_missing_unsupported_category():
    obj = make_valid()
    del obj["claims"][2]["unsupported_category"]
    assert has(
        validate_review_submission(obj),
        "$.claims[2].unsupported_category",
        "missing_unsupported_category",
    )


def test_unsupported_invalid_unsupported_category():
    obj = make_valid()
    obj["claims"][2]["unsupported_category"] = "not-a-real-category"
    assert has(
        validate_review_submission(obj),
        "$.claims[2].unsupported_category",
        "invalid_unsupported_category",
    )


def test_duplicate_claim_id():
    obj = make_valid()
    obj["claims"][1]["id"] = "c1"
    assert has(validate_review_submission(obj), "$.claims[1].id", "duplicate_claim_id")


def test_declared_action_missing_requires_human_review():
    obj = make_valid()
    del obj["declared_actions"][0]["requires_human_review"]
    assert has(
        validate_review_submission(obj),
        "$.declared_actions[0].requires_human_review",
        "missing_field",
    )


def test_declared_action_wrong_type_requires_human_review():
    obj = make_valid()
    obj["declared_actions"][0]["requires_human_review"] = "yes"
    assert has(
        validate_review_submission(obj),
        "$.declared_actions[0].requires_human_review",
        "wrong_type",
    )


def test_repo_diff_ref_null_is_allowed():
    obj = make_valid()
    obj["repo_diff_ref"] = None
    assert validate_review_submission(obj) == []


def test_errors_contain_only_path_and_code_keys():
    obj = make_valid()
    del obj["claims"][0]["text"]
    obj["claims"][1]["category"] = "bogus"
    errors = validate_review_submission(obj)
    assert errors
    for e in errors:
        assert set(e.keys()) == {"path", "code"}


def test_errors_do_not_echo_claim_text_or_citation_values():
    secret_text = "SENSITIVE-CLAIM-TEXT-SHOULD-NOT-LEAK"
    secret_citation = "SENSITIVE-CITATION-SHOULD-NOT-LEAK"
    obj = make_valid()
    obj["claims"][0]["text"] = secret_text
    obj["claims"][0]["category"] = "bogus-category"
    obj["claims"][0]["citation"] = secret_citation
    errors = validate_review_submission(obj)
    serialized = json.dumps(errors)
    assert secret_text not in serialized
    assert secret_citation not in serialized


def test_validation_commands_are_not_executed_only_structurally_checked():
    obj = make_valid()
    obj["validation"] = [{"command": "rm -rf /", "recorded_result": "not_recorded"}]
    # A structurally valid (if alarming) command string must not be run; the
    # validator only checks shape and returns no error here.
    assert validate_review_submission(obj) == []
