"""CR-138 rule, case parsing, citation, and policy checks (no runtime needed)."""

import hashlib
import json
from pathlib import Path

import pytest

from triage_core import checklist_review as cr
from triage_core.privacy_invariants import assert_persistent_privacy_safe

FIXTURES = Path(__file__).parent / "fixtures" / "checklist_review"

PINNED_TEXT_FIXTURES = {
    "workflow_docrev_v1/system.txt": "69d17c5d1de85bddf0ddd321af7d1471ece6abb9ca60f04dbeb7dd03676df316",
    "workflow_docrev_v1/user_template.txt": "4038f3e9de8bb33f58f1da1803951b510176b9f3caa8e3d6dd99f8ee30475176",
    "cases/DC-02.txt": "bd28ba046465e68390a13200de61f3e46168d232ea51834cda0f7f74bb96ed79",
    "cases/DC-03.txt": "ff0d555e3ce5845c20ee746aea44f1922dec4c883375373ad379e7a9772a861f",
}
RECORDED_DC02 = "recorded/R01_DC-02_slm.txt"
RECORDED_DC02_SHA256 = "7fca096c058a6998ae18699a3ae271447a230403721092502141db76db76d6c8"
# SHA-256 of the user message in the sealed R01 requests (see PROVENANCE.md).
R01_USER_MESSAGE_SHA256 = {
    "DC-02": "424b0fbae5bc6fbec2ea1a024b60add88815579f64484f76145b5e23a18524fc",
    "DC-03": "9a9360446cbb1b5917a71d4932ee4760f8f927d9a0106959f0dbfec0808ae46e",
}
MODEL_TAG = "qwen3.5:4b"
MODEL_DIGEST = "d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def text_fixture(relative: str) -> bytes:
    """Canonical fixture bytes: a Windows checkout may have added CR characters."""
    return (FIXTURES / relative).read_bytes().replace(b"\r\n", b"\n")


def dc_case(case_id: str) -> cr.ReviewCase:
    return cr.parse_case(text_fixture(f"cases/{case_id}.txt"))


def case_bytes(case_id, sections):
    lines = [f"BEGIN CASE {case_id}"]
    for name, rows in sections:
        lines += ["---", f"FILE: {name}", "---"]
        lines += [f"{label}  {text}" for label, text in rows]
    lines.append(f"END CASE {case_id}")
    return "\n".join(lines).encode("utf-8")


def standard_sections(
    *,
    document_id="FC-233",
    revision="E",
    controlling="Controlling source: S1 (S1_decision_register.txt)",
    register_rows=("DR-0618 | FC-233 | E | Approved | 2026-06-09 | —",),
    include_register=True,
):
    request = [
        ("RQ.L01", "Review request, case TC-01"),
        ("RQ.L02", "Work product: work_product.txt (synthetic checklist)"),
    ]
    if controlling is not None:
        request.append(("RQ.L03", controlling))
    work_product = [("WP.L01", "SYNTHETIC CHECKLIST")]
    if document_id is not None:
        work_product.append(("WP.L02", f"Document ID: {document_id}"))
    if revision is not None:
        work_product.append(("WP.L03", f"Revision: {revision}"))
    sections = [("request.txt", request), ("work_product.txt", work_product)]
    if include_register:
        register = [
            ("S1.L01", "DECISION REGISTER: document approvals (excerpt)"),
            ("S1.L02", "Decision ID | Document ID | Revision | Decision | Decided on | Remarks"),
        ]
        register += [(f"S1.L{index:02d}", row) for index, row in enumerate(register_rows, start=3)]
        sections.append(("S1_decision_register.txt", register))
    return sections


def synthetic_case(**kwargs) -> cr.ReviewCase:
    return cr.parse_case(case_bytes("TC-01", standard_sections(**kwargs)))


def model_reply(case_id="DC-02", finding="insufficient evidence", cited=("S1.L03",), reason="r", **extra):
    payload = {"case_id": case_id, "finding": finding, "cited_lines": list(cited), "reason": reason}
    payload.update(extra)
    return json.dumps(payload)


# --- Fixture identity -------------------------------------------------------


@pytest.mark.parametrize("relative, digest", sorted(PINNED_TEXT_FIXTURES.items()))
def test_text_fixtures_match_pinned_digests(relative, digest):
    data = text_fixture(relative)
    assert not data.startswith(b"\xef\xbb\xbf")
    assert not data.endswith(b"\n")
    assert _sha256(data) == digest


def test_recorded_reply_matches_its_seal_without_normalization():
    data = (FIXTURES / RECORDED_DC02).read_bytes()
    assert _sha256(data) == RECORDED_DC02_SHA256


def test_packaged_templates_match_fixture_bytes_and_pins():
    system = cr.SYSTEM_TEXT.encode("utf-8")
    template = cr.USER_TEMPLATE.encode("utf-8")
    assert system == text_fixture("workflow_docrev_v1/system.txt")
    assert template == text_fixture("workflow_docrev_v1/user_template.txt")
    assert _sha256(system) == cr.SYSTEM_TEXT_SHA256 == PINNED_TEXT_FIXTURES["workflow_docrev_v1/system.txt"]
    assert _sha256(template) == cr.USER_TEMPLATE_SHA256 == PINNED_TEXT_FIXTURES["workflow_docrev_v1/user_template.txt"]


@pytest.mark.parametrize("case_id", ["DC-02", "DC-03"])
def test_rendered_user_message_reproduces_sealed_r01_request(case_id):
    rendered = cr.render_user_message(dc_case(case_id))
    assert _sha256(rendered.encode("utf-8")) == R01_USER_MESSAGE_SHA256[case_id]


def test_chat_request_has_two_frozen_messages_and_r01_settings():
    case = dc_case("DC-03")
    body = cr.build_chat_request(model_tag=MODEL_TAG, case=case)
    payload = json.loads(body.decode("utf-8"))
    assert set(payload) == {"model", "messages", "options", "think", "stream"}
    assert payload["model"] == MODEL_TAG
    assert payload["messages"] == [
        {"role": "system", "content": cr.SYSTEM_TEXT},
        {"role": "user", "content": cr.render_user_message(case)},
    ]
    assert payload["options"] == {"temperature": 0, "top_p": 1.0, "seed": 7, "num_predict": 256, "num_ctx": 4096}
    assert payload["think"] is False
    assert payload["stream"] is False
    assert len(body) <= cr.CHAT_REQUEST_LIMIT_BYTES


def test_chat_request_inputs_exclude_recorded_answer():
    body = cr.build_chat_request(model_tag=MODEL_TAG, case=dc_case("DC-02")).decode("utf-8")
    recorded = (FIXTURES / RECORDED_DC02).read_bytes().decode("utf-8")
    assert "EQ-INV-07 but only for Revision 2" in recorded
    assert "but only for Revision 2" not in body


# --- Case parsing -----------------------------------------------------------


def test_parse_case_binds_exact_bytes_and_unique_labels():
    raw = text_fixture("cases/DC-02.txt")
    case = cr.parse_case(raw)
    assert case.case_id == "DC-02"
    assert case.raw == raw
    assert case.sha256 == PINNED_TEXT_FIXTURES["cases/DC-02.txt"]
    assert case.files == ("request.txt", "work_product.txt", "S1_decision_register.txt")
    assert case.labels[:2] == ("RQ.L01", "RQ.L02")
    assert case.labels[-1] == "S1.L05"
    assert len(case.labels) == len(set(case.labels)) == 6 + 9 + 5
    assert case.line("WP.L02").text == "Document ID: EQ-INV-07"
    assert case.line("S1.L04").file_name == "S1_decision_register.txt"
    assert case.line("S9.L01") is None


def test_parse_case_accepts_one_trailing_newline_and_binds_those_bytes():
    raw = text_fixture("cases/DC-03.txt") + b"\n"
    case = cr.parse_case(raw)
    assert case.raw == raw
    assert case.sha256 == _sha256(raw)
    assert cr.render_user_message(case) == cr.render_user_message(dc_case("DC-03"))


def _valid_case_text():
    return text_fixture("cases/DC-03.txt").decode("utf-8")


@pytest.mark.parametrize(
    "raw, code",
    [
        (b"BEGIN CASE DC-03\n" + b"x" * cr.CASE_LIMIT_BYTES, "case_too_large"),
        (_valid_case_text().replace("Approved", "Appr\udcffoved", 1).encode("utf-8", "surrogateescape"), "case_encoding_invalid"),
        (_valid_case_text().replace("\n", "\r\n").encode("utf-8"), "case_line_ending_invalid"),
        (_valid_case_text().rsplit("\n", 1)[0].encode("utf-8"), "case_envelope_invalid"),
        (_valid_case_text().replace("END CASE DC-03", "END CASE DC-04").encode("utf-8"), "case_envelope_invalid"),
        (_valid_case_text().replace("WP.L04", "WP.L03").encode("utf-8"), "case_label_duplicate"),
        (_valid_case_text().replace("FILE: S1_decision_register.txt", "FILE: notes.md").encode("utf-8"), "case_file_unsupported"),
        (_valid_case_text().replace("FILE: work_product.txt\n---\n", "FILE: work_product.txt\n").encode("utf-8"), "case_framing_invalid"),
        (_valid_case_text().replace("WP.L06  1.", "WP.L06 1.").encode("utf-8"), "case_framing_invalid"),
        (_valid_case_text().replace("RQ.L05  ", "WP.L99  ").encode("utf-8"), "case_framing_invalid"),
    ],
    ids=[
        "oversize",
        "invalid-utf8",
        "crlf",
        "missing-end",
        "mismatched-end",
        "duplicate-label",
        "unsupported-file",
        "missing-separator",
        "unlabelled-line",
        "label-outside-its-file",
    ],
)
def test_malformed_case_stops_with_a_closed_reason_code(raw, code):
    with pytest.raises(cr.CaseInputError) as raised:
        cr.parse_case(raw)
    assert raised.value.reason_code == code
    assert code in cr.INPUT_REASON_CODES
    assert "FC-233" not in str(raised.value)


def test_input_reason_codes_are_distinct_per_failure_class():
    expected = {
        "case_too_large",
        "case_encoding_invalid",
        "case_line_ending_invalid",
        "case_envelope_invalid",
        "case_framing_invalid",
        "case_file_unsupported",
        "case_label_duplicate",
    }
    assert expected <= set(cr.INPUT_REASON_CODES)
    assert len(cr.INPUT_REASON_CODES) == len(set(cr.INPUT_REASON_CODES))


# --- Rule R-DOCREV v0.1 -----------------------------------------------------


def test_rule_dc03_is_match_citing_s1_l04():
    result = cr.apply_rule(dc_case("DC-03"))
    assert result.component == "rule"
    assert result.status == "valid"
    assert result.finding == "match"
    assert result.reason_code == "R4a_exact_entry"
    assert result.deciding_step == "R4"
    assert result.cited_labels == ("WP.L02", "WP.L03", "S1.L04")
    assert result.kept_rows == ("S1.L03", "S1.L04")
    assert result.gaps == ()


def test_rule_dc02_is_insufficient_evidence_citing_every_entry_row():
    result = cr.apply_rule(dc_case("DC-02"))
    assert result.finding == "insufficient evidence"
    assert result.reason_code == "R3_no_entry_for_document"
    assert result.cited_labels == ("WP.L02", "WP.L03", "S1.L03", "S1.L04", "S1.L05")
    assert result.kept_rows == ()


def test_same_revision_and_date_with_other_document_id_does_not_count():
    case = synthetic_case(
        register_rows=(
            "DR-0618 | FC-234 | E | Approved | 2026-06-09 | —",
            "DR-0619 | fc-233 | E | Approved | 2026-06-09 | —",
        )
    )
    result = cr.apply_rule(case)
    assert result.finding == "insufficient evidence"
    assert result.reason_code == "R3_no_entry_for_document"
    assert result.kept_rows == ()
    assert result.cited_labels == ("WP.L02", "WP.L03", "S1.L03", "S1.L04")


def test_unnamed_controlling_source_is_a_visible_gap():
    case = synthetic_case(controlling=None)
    result = cr.apply_rule(case)
    assert result.finding == "insufficient evidence"
    assert result.reason_code == "R2_controlling_source_absent"
    assert "controlling_source_unnamed" in result.gaps


def test_named_but_missing_controlling_excerpt_is_a_visible_gap():
    case = synthetic_case(controlling="Controlling source: S2 (S2_register.txt)")
    result = cr.apply_rule(case)
    assert result.finding == "insufficient evidence"
    assert result.reason_code == "R2_controlling_source_absent"
    assert "controlling_source_excerpt_absent" in result.gaps


def test_controlling_source_is_read_only_from_the_request():
    sections = standard_sections(controlling=None)
    sections[1][1].append(("WP.L04", "Controlling source: S1 (S1_decision_register.txt)"))
    result = cr.apply_rule(cr.parse_case(case_bytes("TC-01", sections)))
    assert result.reason_code == "R2_controlling_source_absent"


@pytest.mark.parametrize(
    "kwargs, gap",
    [({"revision": None}, "target_revision_missing"), ({"document_id": "—"}, "target_document_id_missing")],
)
def test_missing_header_field_is_insufficient_evidence(kwargs, gap):
    result = cr.apply_rule(synthetic_case(**kwargs))
    assert result.finding == "insufficient evidence"
    assert result.reason_code == "R1_target_field_missing"
    assert result.deciding_step == "R1"
    assert gap in result.gaps


@pytest.mark.parametrize(
    "rows, finding, code, cited_rows",
    [
        (("DR-1 | FC-233 | — | Approved | 2026-06-09 | —",), "insufficient evidence", "R4b_entry_field_missing", ("S1.L03",)),
        (("DR-1 | FC-233 | E | Deferred | 2026-06-09 | —",), "insufficient evidence", "R4c_decision_not_approved", ("S1.L03",)),
        (("DR-1 | FC-233 | D | Approved | 2026-05-28 | —", "DR-2 | FC-233 | C | Approved | 2026-04-01 | —"), "mismatch", "R4d_other_revision_only", ("S1.L03", "S1.L04")),
        (("DR-1 | FC-233 | E | Approved | 2026-06-09 | In principle only",), "match", "R4a_exact_entry", ("S1.L03",)),
    ],
    ids=["empty-revision", "not-approved", "other-revision-only", "remarks-ignored"],
)
def test_rule_entry_steps(rows, finding, code, cited_rows):
    result = cr.apply_rule(synthetic_case(register_rows=rows))
    assert result.finding == finding
    assert result.reason_code == code
    assert result.cited_labels == ("WP.L02", "WP.L03") + cited_rows


def test_rule_metadata_holds_labels_and_codes_but_no_case_text():
    metadata = cr.apply_rule(dc_case("DC-02")).to_metadata()
    assert_persistent_privacy_safe(metadata)
    encoded = json.dumps(metadata)
    assert "EQ-INV-07" not in encoded
    assert "EQ-INV-12" not in encoded


# --- Model output parsing and citations -------------------------------------


def test_recorded_dc02_reply_parses_with_its_original_citations():
    raw = (FIXTURES / RECORDED_DC02).read_bytes().decode("utf-8")
    result = cr.parse_model_result(dc_case("DC-02"), raw)
    assert result.component == "model"
    assert result.status == "valid"
    assert result.reason_code is None
    assert result.finding == "insufficient evidence"
    assert result.cited_labels == ("WP.L02", "WP.L03", "S1.L02", "S1.L03", "S1.L04")
    assert "S1.L05" not in result.cited_labels
    assert result.citation_resolution == "all"
    assert result.reason_text.startswith("The controlling source contains an entry for Document ID EQ-INV-07")


@pytest.mark.parametrize(
    "wrap",
    [
        lambda text: text,
        lambda text: f"  \n{text}\n\n",
        lambda text: f"```json\n{text}\n```",
        lambda text: f"```\n{text}\n```",
        lambda text: f"\n```json\n{text}\n```\n",
    ],
    ids=["bare", "whitespace", "json-fence", "plain-fence", "fence-with-whitespace"],
)
def test_r01_parsing_accepts_one_fence_and_surrounding_whitespace(wrap):
    result = cr.parse_model_result(dc_case("DC-02"), wrap(model_reply()))
    assert result.status == "valid"
    assert result.finding == "insufficient evidence"


def test_r01_parsing_normalizes_findings_and_ignores_extra_keys():
    raw = model_reply(finding="  Insufficient EVIDENCE ", confidence=0.9, notes=["x"])
    result = cr.parse_model_result(dc_case("DC-02"), raw)
    assert result.status == "valid"
    assert result.finding == "insufficient evidence"


def test_same_source_citation_range_resolves_against_the_case():
    raw = model_reply(cited=["WP.L02", "S1.L03-S1.L05"])
    result = cr.parse_model_result(dc_case("DC-02"), raw)
    assert result.cited_labels == ("WP.L02", "S1.L03", "S1.L04", "S1.L05")
    assert result.citation_resolution == "all"
    assert result.unresolved_citations == ()


@pytest.mark.parametrize("entry", ["WP.L02-S1.L03", "S1.L03-S1.L09", "S1.L05-S1.L03", "S9.L01", "the register"])
def test_unresolved_citation_keeps_the_finding_and_shows_a_gap(entry):
    raw = model_reply(finding="mismatch", cited=["S1.L04", entry])
    result = cr.parse_model_result(dc_case("DC-02"), raw)
    assert result.status == "valid"
    assert result.finding == "mismatch"
    assert result.cited_labels == ("S1.L04",)
    assert result.citation_resolution == "some_unresolvable"
    assert result.unresolved_citations == (entry,)
    assert "citation_unresolved" in result.gaps
    metadata = result.to_metadata()
    assert metadata["unresolved_citation_count"] == 1
    assert metadata["cited_labels"] == ["S1.L04"]
    assert "the register" not in json.dumps(metadata)


def test_no_citations_is_recorded_as_none_cited():
    result = cr.parse_model_result(dc_case("DC-02"), model_reply(cited=[]))
    assert result.status == "valid"
    assert result.citation_resolution == "none_cited"
    assert result.cited_labels == ()


@pytest.mark.parametrize(
    "raw, code",
    [
        ("", "model_output_not_json"),
        ("The answer is insufficient evidence.", "model_output_not_json"),
        ('{"case_id": "DC-02", "finding": NaN}', "model_output_not_json"),
        ("Here you go:\n```json\n" + model_reply() + "\n```", "model_output_not_json"),
        ("```json\n" + model_reply() + "\n```\n```json\n" + model_reply() + "\n```", "model_output_not_json"),
        ("[" + model_reply() + "]", "model_output_not_object"),
        (model_reply(case_id="DC-03"), "model_case_id_mismatch"),
        (model_reply(finding="approved"), "model_finding_invalid"),
        (json.dumps({"case_id": "DC-02", "finding": 1, "cited_lines": [], "reason": ""}), "model_finding_invalid"),
        (json.dumps({"case_id": "DC-02", "finding": "match", "cited_lines": "S1.L03", "reason": ""}), "model_citations_invalid"),
        (json.dumps({"case_id": "DC-02", "finding": "match", "cited_lines": [3], "reason": ""}), "model_citations_invalid"),
        (json.dumps({"case_id": "DC-02", "finding": "match", "cited_lines": []}), "model_reason_invalid"),
    ],
    ids=[
        "empty",
        "prose",
        "nan",
        "prose-before-fence",
        "two-fences",
        "array",
        "wrong-case",
        "unknown-finding",
        "non-string-finding",
        "string-citations",
        "non-string-citation",
        "missing-reason",
    ],
)
def test_malformed_model_output_is_returned_invalid(raw, code):
    result = cr.parse_model_result(dc_case("DC-02"), raw)
    assert result.status == "invalid"
    assert result.finding is None
    assert result.reason_code == code
    assert code in cr.PARSER_REASON_CODES


def test_model_metadata_omits_model_reason_text():
    raw = model_reply(reason="SENTINEL-MODEL-REASON-41c7 says the register is fine")
    metadata = cr.parse_model_result(dc_case("DC-02"), raw).to_metadata()
    assert_persistent_privacy_safe(metadata)
    assert "SENTINEL-MODEL-REASON-41c7" not in json.dumps(metadata)


# --- Policy C-AGREE v0.1 ----------------------------------------------------


def _model(case, finding):
    return cr.parse_model_result(case, model_reply(case_id=case.case_id, finding=finding))


def test_policy_agreement_keeps_the_shared_finding_but_not_assessed_evidence():
    case = dc_case("DC-02")
    rule = cr.apply_rule(case)
    model = _model(case, "insufficient evidence")
    policy = cr.combine(rule, model)
    assert policy.finding == "insufficient evidence"
    assert policy.agreement == "agreed"
    assert policy.review_needed is False
    assert policy.evidence_status == "unassessed"
    assert (policy.rule_finding, policy.model_finding) == ("insufficient evidence", "insufficient evidence")


def test_policy_disagreement_abstains_and_retains_both_components():
    case = dc_case("DC-03")
    policy = cr.combine(cr.apply_rule(case), _model(case, "mismatch"))
    assert policy.finding == "insufficient evidence"
    assert policy.agreement == "disagreed"
    assert policy.review_needed is True
    assert (policy.rule_finding, policy.model_finding) == ("match", "mismatch")


def test_policy_with_invalid_model_result_abstains():
    case = dc_case("DC-03")
    invalid = cr.parse_model_result(case, "not json")
    policy = cr.combine(cr.apply_rule(case), invalid)
    assert policy.finding == "insufficient evidence"
    assert policy.agreement == "model_invalid"
    assert policy.review_needed is True
    assert policy.rule_finding == "match"
    assert policy.model_finding is None
    assert_persistent_privacy_safe(policy.to_metadata())


# --- Workflow definition ----------------------------------------------------


def test_definition_freezes_template_digests_rule_parser_policy_and_model():
    definition = cr.build_definition(
        model_tag=MODEL_TAG,
        model_digest=MODEL_DIGEST,
        system_text_artifact_id="00000000-0000-4000-8000-000000000001",
        user_template_artifact_id="00000000-0000-4000-8000-000000000002",
    )
    assert_persistent_privacy_safe(definition)
    assert definition["rule_id"] == "R-DOCREV v0.1"
    assert definition["policy_id"] == "C-AGREE v0.1"
    assert definition["parser_id"] == cr.PARSER_ID
    assert definition["system_text"]["sha256"] == cr.SYSTEM_TEXT_SHA256
    assert definition["user_template"]["sha256"] == cr.USER_TEMPLATE_SHA256
    assert definition["model_profile"]["tag"] == MODEL_TAG
    assert definition["model_profile"]["expected_digest"] == MODEL_DIGEST
    assert definition["model_profile"]["request_settings"] == {
        "options": {"temperature": 0, "top_p": 1.0, "seed": 7, "num_predict": 256, "num_ctx": 4096},
        "think": False,
        "stream": False,
    }
    assert definition["limits"]["case_bytes"] == 8 * 1024
    assert definition["limits"]["chat_request_bytes"] == 32 * 1024
    encoded = json.dumps(definition)
    assert "You are checking documents" not in encoded
    assert "BEGIN INSTRUCTIONS" not in encoded

    digest = cr.definition_digest(definition)
    assert digest == cr.definition_digest(json.loads(json.dumps(definition)))
    changed = json.loads(json.dumps(definition))
    changed["model_profile"]["expected_digest"] = "0" * 64
    assert cr.definition_digest(changed) != digest


@pytest.mark.parametrize(
    "tag, digest",
    [("qwen3.5:4b", "D8B0" + MODEL_DIGEST[4:]), ("qwen3.5:4b", "sha256:" + MODEL_DIGEST), ("", MODEL_DIGEST), ("bad tag", MODEL_DIGEST)],
)
def test_definition_rejects_malformed_model_identity(tag, digest):
    with pytest.raises(cr.ChecklistReviewError):
        cr.build_definition(
            model_tag=tag,
            model_digest=digest,
            system_text_artifact_id="00000000-0000-4000-8000-000000000001",
            user_template_artifact_id="00000000-0000-4000-8000-000000000002",
        )
