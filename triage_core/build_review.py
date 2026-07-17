"""Evidence-bound review packet creation and immutable human decisions."""

from __future__ import annotations

import fnmatch
import json
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from triage_core.build_review_integrity import (
    DECISION_STATUSES,
    decision_id,
    diff_summary,
    display_payload,
    evidence_sha256,
    sha256_json,
    validation_results,
)
from triage_core.build_review_report import render_html, render_markdown
from triage_core.privacy_invariants import assert_persistent_privacy_safe

MAX_CAPTURE_CHARS = 12_000
SENSITIVE_PATTERNS = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*id_rsa*",
    "*credentials*",
    "*secret*",
)
BINARY_PATTERNS = ("*.exe", "*.dll", "*.dylib", "*.so", "*.bin")


class GitInspectionError(RuntimeError):
    """Raised when a repository or comparison cannot be inspected."""


@dataclass
class ChangeRequestContract:
    request_id: str = "unidentified"
    declared_scope: List[str] = field(default_factory=list)
    required_validations: List[str] = field(default_factory=list)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _section_items(markdown: str, heading: str) -> List[str]:
    target = heading.strip().casefold()
    in_section = False
    items: List[str] = []
    for line in markdown.splitlines():
        if line.startswith("#"):
            title = line.lstrip("#").strip().casefold()
            if in_section and title != target:
                break
            in_section = title == target
            continue
        if not in_section:
            continue
        match = re.match(r"^\s*[-*]\s+(.+?)\s*$", line)
        if not match:
            continue
        raw = match.group(1).strip()
        code_span = re.search(r"`([^`]+)`", raw)
        items.append((code_span.group(1) if code_span else raw).strip())
    return items


def parse_change_request(markdown: str) -> ChangeRequestContract:
    title_match = re.search(
        r"^#\s+(CR-[A-Z0-9-]+)\b",
        markdown,
        re.MULTILINE,
    )
    return ChangeRequestContract(
        request_id=title_match.group(1) if title_match else "unidentified",
        declared_scope=_section_items(markdown, "Declared scope"),
        required_validations=_section_items(markdown, "Required validations"),
    )


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise GitInspectionError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def repository_root(repo: Path) -> Path:
    return Path(_git(repo, "rev-parse", "--show-toplevel").strip()).resolve()


def _resolve_commit(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", f"{ref}^{{commit}}").strip()


def _worktree_clean(repo: Path) -> bool:
    return not _git(repo, "status", "--porcelain").strip()


def _diff_args(base: str, head: str) -> List[str]:
    return [base, "--"] if head.upper() == "WORKTREE" else [base, head, "--"]


def inspect_changes(
    repo: Path,
    base: str,
    head: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, int], str, str]:
    base_commit = _resolve_commit(repo, base)
    head_commit = _resolve_commit(
        repo,
        "HEAD" if head.upper() == "WORKTREE" else head,
    )
    name_status = _git(
        repo,
        "diff",
        "--no-ext-diff",
        "--no-renames",
        "--name-status",
        *_diff_args(base, head),
    )
    numstat = _git(
        repo,
        "diff",
        "--no-ext-diff",
        "--no-renames",
        "--numstat",
        *_diff_args(base, head),
    )

    counts: Dict[str, Tuple[int, int]] = {}
    for line in numstat.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        additions = 0 if parts[0] == "-" else int(parts[0])
        deletions = 0 if parts[1] == "-" else int(parts[1])
        counts[parts[2].replace("\\", "/")] = (additions, deletions)

    changed_files: List[Dict[str, Any]] = []
    for line in name_status.splitlines():
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        status, raw_path = parts
        path = raw_path.replace("\\", "/")
        additions, deletions = counts.get(path, (None, None))
        changed_files.append(
            {
                "path": path,
                "status": status,
                "additions": additions,
                "deletions": deletions,
            }
        )

    if head.upper() == "WORKTREE":
        untracked = _git(
            repo,
            "ls-files",
            "--others",
            "--exclude-standard",
        ).splitlines()
        tracked_paths = {item["path"] for item in changed_files}
        for raw_path in untracked:
            path = raw_path.replace("\\", "/")
            if path in tracked_paths:
                continue
            file_path = repo / raw_path
            additions: Optional[int]
            if file_path.is_symlink():
                additions = None
            else:
                content = file_path.read_bytes()
                additions = (
                    None
                    if b"\x00" in content
                    else len(
                        content.decode("utf-8", errors="replace").splitlines()
                    )
                )
            changed_files.append(
                {
                    "path": path,
                    "status": "??",
                    "additions": additions,
                    "deletions": 0 if additions is not None else None,
                }
            )
        changed_files.sort(key=lambda item: item["path"])

    summary = {
        "files_changed": len(changed_files),
        "additions": sum(item["additions"] or 0 for item in changed_files),
        "deletions": sum(item["deletions"] or 0 for item in changed_files),
    }
    return changed_files, summary, base_commit, head_commit


def _normalize_path(value: str) -> str:
    return value.strip().replace("\\", "/").lstrip("./")


def _matches_scope(path: str, expected_scope: Iterable[str]) -> bool:
    normalized_path = _normalize_path(path)
    for raw_scope in expected_scope:
        scope = _normalize_path(raw_scope).rstrip("/")
        if not scope:
            continue
        if any(character in scope for character in "*?["):
            if fnmatch.fnmatchcase(normalized_path, scope):
                return True
        elif normalized_path == scope or normalized_path.startswith(f"{scope}/"):
            return True
    return False


def _matches_any(path: str, patterns: Iterable[str]) -> bool:
    name = Path(path).name.lower()
    path_lower = path.lower()
    return any(
        fnmatch.fnmatchcase(name, pattern.lower())
        or fnmatch.fnmatchcase(path_lower, pattern.lower())
        for pattern in patterns
    )


def run_validation(repo: Path, command: str, timeout: int) -> Dict[str, Any]:
    started = time.monotonic()
    try:
        result = subprocess.run(
            command,
            cwd=repo,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return {
            "command": command,
            "passed": result.returncode == 0,
            "exit_code": result.returncode,
            "duration_seconds": round(time.monotonic() - started, 3),
            "stdout": result.stdout[-MAX_CAPTURE_CHARS:],
            "stderr": result.stderr[-MAX_CAPTURE_CHARS:],
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        if isinstance(stdout, bytes):
            stdout = stdout.decode("utf-8", errors="replace")
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return {
            "command": command,
            "passed": False,
            "exit_code": None,
            "duration_seconds": round(time.monotonic() - started, 3),
            "stdout": stdout[-MAX_CAPTURE_CHARS:],
            "stderr": stderr[-MAX_CAPTURE_CHARS:],
            "timed_out": True,
        }


def _finding(
    code: str,
    severity: str,
    title: str,
    detail: str,
    files: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return {
        "code": code,
        "severity": severity,
        "title": title,
        "detail": detail,
        "files": files or [],
    }


def _build_findings(
    changed_files: List[Dict[str, Any]],
    expected_scope: List[str],
    validations: List[Dict[str, Any]],
    expected_validations: List[str],
    clean: bool,
    head: str,
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    changed_paths = [item["path"] for item in changed_files]

    if not expected_scope:
        findings.append(
            _finding(
                "EXPECTED_SCOPE_MISSING",
                "medium",
                "Expected scope was not declared",
                "Scope drift cannot be evaluated without an expected path.",
            )
        )
    else:
        unexpected = [
            path for path in changed_paths if not _matches_scope(path, expected_scope)
        ]
        if unexpected:
            findings.append(
                _finding(
                    "SCOPE_DRIFT",
                    "high",
                    "Changes exceed the expected scope",
                    (
                        f"{len(unexpected)} changed file(s) are outside "
                        "the declared scope."
                    ),
                    unexpected,
                )
            )

    sensitive = [
        path for path in changed_paths if _matches_any(path, SENSITIVE_PATTERNS)
    ]
    if sensitive:
        findings.append(
            _finding(
                "SENSITIVE_FILE_CHANGE",
                "critical",
                "Potential credential or secret material changed",
                "Review these paths before sharing or approving the change.",
                sensitive,
            )
        )

    binaries = [
        path for path in changed_paths if _matches_any(path, BINARY_PATTERNS)
    ]
    if binaries:
        findings.append(
            _finding(
                "BINARY_ARTIFACT",
                "medium",
                "Binary artifacts are present",
                "Binary changes cannot be reviewed through a text diff.",
                binaries,
            )
        )

    if not validations:
        findings.append(
            _finding(
                "VALIDATION_MISSING",
                "medium",
                "No validation evidence was captured",
                "Run at least one relevant test, lint, build, or check.",
            )
        )
    else:
        failed = [item["command"] for item in validations if not item["passed"]]
        if failed:
            findings.append(
                _finding(
                    "VALIDATION_FAILED",
                    "high",
                    "One or more validations failed",
                    "Approval should wait until failures are resolved or accepted.",
                    failed,
                )
            )

    completed = {
        " ".join(item["command"].split()).casefold() for item in validations
    }
    missing_expected = [
        command
        for command in expected_validations
        if " ".join(command.split()).casefold() not in completed
    ]
    if missing_expected:
        findings.append(
            _finding(
                "EXPECTED_VALIDATION_MISSING",
                "high",
                "Required validation evidence is missing",
                (
                    f"{len(missing_expected)} declared validation command(s) "
                    "were not run."
                ),
                missing_expected,
            )
        )

    source_changed = any(
        path.startswith(("triage_core/", "src/"))
        and path.endswith((".py", ".js", ".ts", ".tsx"))
        for path in changed_paths
    )
    tests_changed = any(
        path.startswith("tests/")
        or "/test_" in path
        or path.endswith((".test.js", ".test.ts", ".spec.js", ".spec.ts"))
        for path in changed_paths
    )
    if source_changed and not tests_changed:
        findings.append(
            _finding(
                "UNTESTED_CHANGE",
                "medium",
                "Source changed without corresponding test changes",
                "The diff adds no explicit test coverage for the source change.",
            )
        )

    if not clean and head.upper() != "WORKTREE":
        findings.append(
            _finding(
                "WORKTREE_NOT_CAPTURED",
                "medium",
                "Uncommitted changes are outside this comparison",
                "The selected head is a commit while the worktree is dirty.",
            )
        )

    if not changed_files:
        findings.append(
            _finding(
                "EMPTY_DIFF",
                "medium",
                "The selected comparison contains no changed files",
                "Check the base and head references before deciding.",
            )
        )

    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return sorted(
        findings,
        key=lambda item: (severity_order[item["severity"]], item["code"]),
    )


def _recommendation(findings: List[Dict[str, Any]]) -> str:
    severities = {finding["severity"] for finding in findings}
    if severities.intersection({"critical", "high"}):
        return "reject"
    if "medium" in severities:
        return "needs-review"
    return "approve"


def build_review(
    repo: Union[str, Path],
    request_text: str,
    request_source: str,
    base: str,
    head: str,
    expected_scope: List[str],
    validation_commands: List[str],
    expected_validations: Optional[List[str]] = None,
    request_id: str = "unidentified",
    timeout: int = 120,
) -> Dict[str, Any]:
    repo_root = repository_root(Path(repo).resolve())
    changed_files, summary, base_commit, head_commit = inspect_changes(
        repo_root,
        base,
        head,
    )
    clean = _worktree_clean(repo_root)
    validations = [
        run_validation(repo_root, command, timeout)
        for command in validation_commands
    ]
    expected_validations = expected_validations or []
    findings = _build_findings(
        changed_files,
        expected_scope,
        validations,
        expected_validations,
        clean,
        head,
    )
    created_at = _utc_now()
    identity_material = {
        "repository": str(repo_root),
        "request": request_text,
        "base_commit": base_commit,
        "head_commit": head_commit,
        "expected_scope": expected_scope,
        "created_at": created_at,
    }
    payload: Dict[str, Any] = {
        "schema_version": "1.0",
        "packet_id": sha256_json(identity_material)[:16],
        "created_at": created_at,
        "repository": str(repo_root),
        "request": {
            "id": request_id,
            "text": request_text,
            "source": request_source,
            "declared_validations": expected_validations,
        },
        "comparison": {
            "base_ref": base,
            "head_ref": head,
            "base_commit": base_commit,
            "head_commit": head_commit,
        },
        "expected_scope": expected_scope,
        "change_summary": summary,
        "changed_files": changed_files,
        "validations": validations,
        "findings": findings,
        "recommendation": _recommendation(findings),
        "working_tree_clean": clean,
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


def load_packet(packet_path: Union[str, Path]) -> Dict[str, Any]:
    with Path(packet_path).open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError("review.json must contain a JSON object")
    return value


def write_artifacts(
    packet: Dict[str, Any],
    output_dir: Union[str, Path],
    nested: bool = True,
) -> Dict[str, Path]:
    assert_persistent_privacy_safe(
        packet,
        artifact_name="build-review packet",
    )
    output_path = Path(output_dir)
    if nested:
        output_path = output_path / packet["packet_id"]
    if output_path.exists():
        raise FileExistsError(
            f"Build-review output already exists and will not be overwritten: "
            f"{output_path}"
        )
    output_path.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": output_path / "review.json",
        "markdown": output_path / "review.md",
        "html": output_path / "review.html",
        "diff_summary": output_path / "diff-summary.json",
        "validations": output_path / "validation-results.json",
        "decision": output_path / "decision.json",
    }
    paths["json"].write_text(
        json.dumps(packet, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths["markdown"].write_text(
        render_markdown(packet, Path("review.json")),
        encoding="utf-8",
    )
    paths["html"].write_text(
        render_html(packet, Path("review.json")),
        encoding="utf-8",
    )
    paths["diff_summary"].write_text(
        json.dumps(diff_summary(packet), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths["validations"].write_text(
        json.dumps(validation_results(packet), indent=2, ensure_ascii=False)
        + "\n",
        encoding="utf-8",
    )
    return paths


def record_decision(
    packet_path: Union[str, Path],
    status: str,
    reviewer: str,
    note: Optional[str] = None,
) -> Dict[str, Path]:
    if status not in DECISION_STATUSES:
        raise ValueError(
            "Decision must be approved, rejected, or needs_revision."
        )
    if not reviewer.strip():
        raise ValueError("A reviewer name is required.")

    path = Path(packet_path).resolve()
    payload = load_packet(path)
    decision_path = path.parent / "decision.json"
    if decision_path.exists():
        raise FileExistsError(
            "A decision is already recorded. Existing audit records are not "
            "overwritten."
        )
    decision: Dict[str, Any] = {
        "schema_version": "1.0",
        "decision_id": "",
        "review_packet_id": payload["packet_id"],
        "evidence_sha256": payload["evidence_sha256"],
        "status": status,
        "reviewer": reviewer.strip(),
        "note": (note or "").strip() or None,
        "decided_at": _utc_now(),
    }
    decision["decision_id"] = decision_id(decision)
    assert_persistent_privacy_safe(
        decision,
        artifact_name="build-review decision",
    )
    with decision_path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(decision, indent=2, ensure_ascii=False) + "\n")

    rendered = display_payload(payload, decision)
    markdown_path = path.parent / "review.md"
    html_path = path.parent / "review.html"
    markdown_path.write_text(
        render_markdown(rendered, Path("review.json")),
        encoding="utf-8",
    )
    html_path.write_text(
        render_html(rendered, Path("review.json")),
        encoding="utf-8",
    )
    return {
        "json": path,
        "markdown": markdown_path,
        "html": html_path,
        "diff_summary": path.parent / "diff-summary.json",
        "validations": path.parent / "validation-results.json",
        "decision": decision_path,
    }
