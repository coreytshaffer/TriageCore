"""Generate the portable Build Week review packets from fixed evidence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from triage_core.build_review import build_review, write_artifacts  # noqa: E402
from triage_core.build_review_integrity import (  # noqa: E402
    decision_id,
    display_payload,
    evidence_sha256,
)
from triage_core.build_review_report import render_html, render_markdown  # noqa: E402
from triage_core.privacy_invariants import (  # noqa: E402
    assert_persistent_privacy_safe,
)

CREATED_AT = "2026-07-17T20:00:00+00:00"


def _review(
    *,
    packet_id,
    repository,
    request_id,
    request_text,
    declared_validations,
    expected_scope,
    changed_files,
    validations,
    findings,
    recommendation,
):
    payload = {
        "schema_version": "1.0",
        "packet_id": packet_id,
        "created_at": CREATED_AT,
        "repository": repository,
        "request": {
            "id": request_id,
            "text": request_text,
            "source": "embedded Build Week example request",
            "declared_validations": declared_validations,
        },
        "comparison": {
            "base_ref": "main",
            "head_ref": "HEAD",
            "base_commit": "1" * 40,
            "head_commit": "2" * 40,
        },
        "expected_scope": expected_scope,
        "change_summary": {
            "files_changed": len(changed_files),
            "additions": sum(item["additions"] or 0 for item in changed_files),
            "deletions": sum(item["deletions"] or 0 for item in changed_files),
        },
        "changed_files": changed_files,
        "validations": validations,
        "findings": findings,
        "recommendation": recommendation,
        "working_tree_clean": True,
        "decision": {
            "status": "pending",
            "reviewer": None,
            "note": None,
            "decided_at": None,
        },
        "evidence_sha256": "",
    }
    payload["evidence_sha256"] = evidence_sha256(payload)
    return payload


def _write_decision(packet_dir, review, status, reviewer, note):
    decision = {
        "schema_version": "1.0",
        "decision_id": "",
        "review_packet_id": review["packet_id"],
        "evidence_sha256": review["evidence_sha256"],
        "status": status,
        "reviewer": reviewer,
        "note": note,
        "decided_at": "2026-07-17T20:15:00+00:00",
    }
    decision["decision_id"] = decision_id(decision)
    assert_persistent_privacy_safe(
        decision,
        artifact_name="build-review example decision",
    )
    (packet_dir / "decision.json").write_text(
        json.dumps(decision, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    rendered = display_payload(review, decision)
    (packet_dir / "review.md").write_text(
        render_markdown(rendered, Path("review.json")),
        encoding="utf-8",
    )
    (packet_dir / "review.html").write_text(
        render_html(rendered, Path("review.json")),
        encoding="utf-8",
    )


def main():
    examples = Path(__file__).resolve().parent
    clean_dir = examples / "clean-self-review"
    adversarial_dir = examples / "adversarial-scope-drift"

    focused_validation = "python -m pytest -q tests/test_build_review_cli.py"
    clean = build_review(
        repo=ROOT,
        request_text=(
            "Integrate evidence-bound build review creation, human decisions, "
            "and independent verification into the existing public tc command."
        ),
        request_source=(
            "docs/change/requests/"
            "CR-BW-002-installable-cli-evidence-verification.md"
        ),
        request_id="CR-BW-002",
        base="origin/main",
        head="WORKTREE",
        expected_scope=[
            "triage_core/build_review.py",
            "triage_core/build_review_cli.py",
            "triage_core/build_review_integrity.py",
            "triage_core/build_review_report.py",
            "triage_core/build_review_verify.py",
            "triage_core/tc_cli.py",
            "tests/test_build_review_cli.py",
            "examples/build-week/",
            "docs/build-review-contract.md",
            "docs/change/requests/",
            "README.md",
            "BUILD_WEEK_SCOPE.md",
        ],
        validation_commands=[focused_validation],
        expected_validations=[focused_validation],
    )
    clean["packet_id"] = "clean-self-review"
    clean["repository"] = "https://github.com/coreytshaffer/TriageCore"
    clean["evidence_sha256"] = evidence_sha256(clean)
    write_artifacts(clean, clean_dir, nested=False)

    adversarial = _review(
        packet_id="adversarial-scope-drift",
        repository="example://adversarial-scope-drift",
        request_id="CR-DEMO-DRIFT",
        request_text=(
            "Update triage_core/app.py and prove the change with unit and "
            "lint validations. No other paths are authorized."
        ),
        declared_validations=[
            "python -m pytest -q",
            "python -m ruff check triage_core",
        ],
        expected_scope=["triage_core/app.py"],
        changed_files=[
            {
                "path": "triage_core/app.py",
                "status": "M",
                "additions": 4,
                "deletions": 1,
            },
            {
                "path": "scratch/agent-notes.txt",
                "status": "A",
                "additions": 7,
                "deletions": 0,
            },
        ],
        validations=[
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
        findings=[
            {
                "code": "SCOPE_DRIFT",
                "severity": "high",
                "title": "Changes exceed the expected scope",
                "detail": "1 changed file is outside the declared scope.",
                "files": ["scratch/agent-notes.txt"],
            },
            {
                "code": "EXPECTED_VALIDATION_MISSING",
                "severity": "high",
                "title": "Required validation evidence is missing",
                "detail": "The declared lint validation was not run.",
                "files": ["python -m ruff check triage_core"],
            },
            {
                "code": "UNTESTED_CHANGE",
                "severity": "medium",
                "title": "Source changed without corresponding test changes",
                "detail": "The diff adds no explicit test coverage.",
                "files": [],
            },
        ],
        recommendation="reject",
    )
    write_artifacts(adversarial, adversarial_dir, nested=False)
    _write_decision(
        adversarial_dir,
        adversarial,
        "needs_revision",
        "Build Week reviewer",
        "Remove the undeclared file and provide the missing lint evidence.",
    )

    print(f"Generated examples in {examples}")


if __name__ == "__main__":
    main()
