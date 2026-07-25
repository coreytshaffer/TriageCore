"""Focused coverage for the deterministic build-review renderers.

Exercises ``render_markdown`` and ``render_html`` through their public
surface only. No filesystem, network, subprocess, or environment access.
"""

from pathlib import Path
from typing import Any, Dict

from triage_core.build_review_report import render_html, render_markdown

EM_DASH = chr(0x2014)
ZERO_WIDTH_SPACE = chr(0x200B)
INJECTION = "<script>alert('xss')</script>"
# Breaks out of an HTML attribute without relying on angle brackets.
ATTRIBUTE_BREAKER = '" onmouseover="alert(1)'
ESCAPED_ATTRIBUTE_BREAKER = "&quot; onmouseover=&quot;alert(1)"
RAW_ATTRIBUTE_ESCAPE = '" onmouseover="'
PACKET_PATH = Path("packets/review-42.json")

APPROVED_DECISION = {
    "status": "approved",
    "reviewer": "Corey Shaffer",
    "note": "Scope respected.",
    "decided_at": "2026-07-24T19:30:00Z",
}


def _payload(**overrides: Any) -> Dict[str, Any]:
    """Build a compact, realistic packet payload; overrides replace top-level keys."""
    payload: Dict[str, Any] = {
        "schema_version": 1,
        "packet_id": "br-2026-07-24-0001",
        "created_at": "2026-07-24T18:00:00Z",
        "repository": "coreytshaffer/TriageCore",
        "request": {"text": "Add focused renderer coverage."},
        "comparison": {
            "base_ref": "main",
            "head_ref": "HEAD",
            "base_commit": "1" * 40,
            "head_commit": "2" * 40,
        },
        "expected_scope": ["tests/test_build_review_report.py"],
        "change_summary": {"files_changed": 1, "additions": 12, "deletions": 3},
        "changed_files": [
            {
                "path": "tests/test_build_review_report.py",
                "status": "A",
                "additions": 12,
                "deletions": 3,
            }
        ],
        "validations": [
            {
                "command": "python -m pytest -q",
                "passed": True,
                "exit_code": 0,
                "duration_seconds": 0.84,
                "stdout": "3 passed in 0.31s\n",
                "stderr": "",
                "timed_out": False,
            }
        ],
        "findings": [
            {
                "code": "SCOPE_OK",
                "severity": "low",
                "title": "Scope respected",
                "detail": "All changed files are inside the declared scope.",
                "files": ["tests/test_build_review_report.py"],
            }
        ],
        "recommendation": "approve",
        "working_tree_clean": True,
        "decision": {
            "status": "pending",
            "reviewer": None,
            "note": None,
            "decided_at": None,
        },
        "evidence_sha256": "a" * 64,
    }
    payload.update(overrides)
    return payload


def _validation(**overrides: Any) -> Dict[str, Any]:
    validation = dict(_payload()["validations"][0])
    validation.update(overrides)
    return validation


def _markdown_row(markdown: str, needle: str) -> str:
    rows = [line for line in markdown.splitlines() if needle in line]
    assert len(rows) == 1, f"expected exactly one row containing {needle!r}"
    return rows[0]


def test_render_markdown_is_byte_identical_across_repeated_calls():
    payload = _payload()
    first = render_markdown(payload, PACKET_PATH)
    second = render_markdown(payload, PACKET_PATH)
    # A structurally equal but distinct payload must also render identically,
    # which additionally proves the renderer does not mutate its input.
    third = render_markdown(_payload(), PACKET_PATH)

    assert first == second == third
    assert first.encode("utf-8") == third.encode("utf-8")


def test_render_html_is_byte_identical_across_repeated_calls():
    payload = _payload()
    first = render_html(payload, PACKET_PATH)
    second = render_html(payload, PACKET_PATH)
    third = render_html(_payload(), PACKET_PATH)

    assert first == second == third
    assert first.encode("utf-8") == third.encode("utf-8")


def test_render_html_escapes_user_controlled_text_paths_and_evidence():
    hostile_path = f"src/{INJECTION}"
    payload = _payload(
        request={"text": INJECTION},
        expected_scope=[hostile_path],
        changed_files=[
            {"path": hostile_path, "status": "M", "additions": 1, "deletions": 0}
        ],
        findings=[
            {
                "code": "RISK",
                "severity": "high",
                "title": INJECTION,
                "detail": INJECTION,
                "files": [hostile_path],
            }
        ],
        validations=[_validation(command=INJECTION, stdout=INJECTION)],
    )

    page = render_html(payload, PACKET_PATH)

    assert "<script>" not in page
    assert "</script>" not in page
    assert "alert('xss')" not in page
    assert "&lt;script&gt;" in page
    assert "alert(&#x27;xss&#x27;)" in page
    # Every injection site is escaped: request, scope, path, title, detail,
    # finding file, validation command, validation output.
    assert page.count("&lt;script&gt;") == 8


def test_markdown_neutralizes_triple_backticks_in_validation_output():
    hostile = "before ``` after"
    payload = _payload(
        decision=APPROVED_DECISION,
        validations=[_validation(stdout=hostile)],
    )

    markdown = render_markdown(payload, PACKET_PATH)

    assert f"before ``{ZERO_WIDTH_SPACE}` after" in markdown
    assert hostile not in markdown
    # Only the renderer's own opening and closing fences survive, so the
    # injected sequence cannot terminate the outer fenced block early.
    assert markdown.count("```") == 2


def test_none_change_counts_render_as_em_dash_not_none():
    payload = _payload(
        changed_files=[
            {"path": "docs/note.md", "status": "M", "additions": None, "deletions": None}
        ]
    )

    row = _markdown_row(render_markdown(payload, PACKET_PATH), "docs/note.md")
    assert f"| {EM_DASH} | {EM_DASH} |" in row
    assert "None" not in row

    page = render_html(payload, PACKET_PATH)
    assert f"<td>{EM_DASH}</td><td>{EM_DASH}</td>" in page
    assert "<td>None</td>" not in page


def test_empty_sections_render_documented_fallbacks_in_both_renderers():
    payload = _payload(
        expected_scope=[], changed_files=[], findings=[], validations=[]
    )

    markdown = render_markdown(payload, PACKET_PATH)
    assert "_not declared_" in markdown
    assert f"| {EM_DASH} | _No changes_ | {EM_DASH} | {EM_DASH} |" in markdown
    assert (
        f"| {EM_DASH} | No findings | Change matches the declared boundary. "
        f"| {EM_DASH} |"
    ) in markdown
    assert "_No validation commands were supplied._" in markdown

    page = render_html(payload, PACKET_PATH)
    assert "<li>Not declared</li>" in page
    assert '<tr><td colspan="4">No changed files.</td></tr>' in page
    assert "<p>No findings. The change matches the declared boundary.</p>" in page
    assert "<p>No validation commands were supplied.</p>" in page


def test_pending_decision_renders_instructions_using_supplied_packet_path():
    markdown = render_markdown(_payload(), PACKET_PATH)
    quoted = f'"{PACKET_PATH}"'

    assert "Decision is pending. Record an explicit decision:" in markdown
    assert f"tc build-review decide {quoted} approved" in markdown
    assert f"tc build-review decide {quoted} rejected" in markdown
    assert f"tc build-review decide {quoted} needs_revision" in markdown

    page = render_html(_payload(), PACKET_PATH)
    assert "<p><strong>Pending human decision.</strong></p>" in page


def test_pending_decision_falls_back_to_default_packet_path():
    markdown = render_markdown(_payload())

    assert f'tc build-review decide "{Path("review.json")}" approved' in markdown


def test_completed_decision_renders_status_reviewer_time_and_note():
    payload = _payload(decision=APPROVED_DECISION)

    markdown = render_markdown(payload, PACKET_PATH)
    assert "- Status: **APPROVED**" in markdown
    assert "- Reviewer: Corey Shaffer" in markdown
    assert "- Time: 2026-07-24T19:30:00Z" in markdown
    assert "- Note: Scope respected." in markdown
    assert "Decision is pending" not in markdown

    page = render_html(payload, PACKET_PATH)
    assert '<p class="decision approved">' in page
    assert "<strong>APPROVED</strong>" in page
    assert "Reviewer: Corey Shaffer" in page
    assert "Time: 2026-07-24T19:30:00Z" in page
    assert "Note: Scope respected." in page
    assert "Pending human decision" not in page


def test_completed_decision_without_note_renders_em_dash():
    payload = _payload(decision={**APPROVED_DECISION, "note": None})

    assert f"- Note: {EM_DASH}" in render_markdown(payload, PACKET_PATH)
    assert f"Note: {EM_DASH}</p>" in render_html(payload, PACKET_PATH)


def test_render_html_escapes_finding_severity_in_class_attribute():
    payload = _payload(
        findings=[
            {
                "code": "RISK",
                "severity": ATTRIBUTE_BREAKER,
                "title": "Hostile severity",
                "detail": "Severity reaches a class attribute.",
                "files": [],
            }
        ]
    )

    page = render_html(payload, PACKET_PATH)

    assert RAW_ATTRIBUTE_ESCAPE not in page
    assert "onmouseover=" not in page.replace(ESCAPED_ATTRIBUTE_BREAKER, "")
    assert f'<article class="finding {ESCAPED_ATTRIBUTE_BREAKER}">' in page


def test_render_html_escapes_completed_decision_status_in_class_attribute():
    payload = _payload(decision={**APPROVED_DECISION, "status": ATTRIBUTE_BREAKER})

    page = render_html(payload, PACKET_PATH)

    assert RAW_ATTRIBUTE_ESCAPE not in page
    assert "onmouseover=" not in page.replace(ESCAPED_ATTRIBUTE_BREAKER, "")
    assert f'<p class="decision {ESCAPED_ATTRIBUTE_BREAKER}">' in page


def test_render_html_escapes_change_summary_files_changed():
    hostile_count = '<img src=x onerror="alert(1)">'
    payload = _payload(
        change_summary={
            "files_changed": hostile_count,
            "additions": 12,
            "deletions": 3,
        }
    )

    page = render_html(payload, PACKET_PATH)

    assert "<img" not in page
    assert 'onerror="alert(1)"' not in page
    assert (
        "Changed files<strong>"
        "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;</strong>"
    ) in page


def test_ordinary_severity_status_and_counts_render_unchanged():
    page = render_html(_payload(decision=APPROVED_DECISION), PACKET_PATH)

    assert '<article class="finding low">' in page
    assert '<p class="decision approved">' in page
    assert "Changed files<strong>1</strong>" in page
