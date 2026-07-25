#!/usr/bin/env python3
"""Standalone change-scope verification tool.

Determines whether every tracked file changed between a base Git reference and HEAD
is within an explicitly supplied allowlist.
"""

import argparse
import json
import os
import subprocess
import sys
from typing import List, Set


def normalize_path(path_str: str) -> str:
    """Normalize repository-relative path to forward-slash form."""
    if not path_str:
        return ""
    clean = path_str.replace("\\", "/")
    norm = os.path.normpath(clean).replace("\\", "/")
    if norm == ".":
        return ""
    return norm


def emit_result_and_exit(
    status: int,
    base: str,
    changed_paths: List[str],
    allowed_paths: List[str],
    unexpected_paths: List[str],
    stderr_message: str = "",
) -> None:
    """Emit a JSON payload to stdout, print error text to stderr if present, and exit."""
    payload = {
        "status": status,
        "base": base,
        "changed_paths": sorted(changed_paths),
        "allowed_paths": sorted(allowed_paths),
        "unexpected_paths": sorted(unexpected_paths),
    }
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    sys.stdout.flush()
    if stderr_message:
        sys.stderr.write(stderr_message + "\n")
        sys.stderr.flush()
    sys.exit(status)


def parse_git_diff_z(raw_bytes: bytes) -> Set[str]:
    """Parse git diff --name-status -z output into a set of normalized relative paths.

    Semantic Contract:
    - Tracked file state change: A path is included in changed_paths if and only if
      its tracked content, mode, or existence at that path differs between <base> and HEAD.
    - Renames ('R'): The old path was deleted and the new path was created; both paths
      differ between <base> and HEAD and are added to changed_paths.
    - Copies ('C'): The destination path was created and is added to changed_paths. The
      copy source path is NOT added solely due to being a provenance source, as its state
      at its original path remains unchanged between <base> and HEAD. (If the copy source
      was also modified, Git emits a separate 'M' status record for it).
    """
    if not raw_bytes:
        return set()

    tokens = [t.decode("utf-8", errors="replace") for t in raw_bytes.split(b"\x00")]
    if tokens and tokens[-1] == "":
        tokens.pop()

    changed_set: Set[str] = set()
    idx = 0
    while idx < len(tokens):
        status_code = tokens[idx]
        idx += 1
        if not status_code:
            continue

        if status_code.startswith("R"):
            # Rename: old_path was deleted, new_path was created
            if idx + 1 < len(tokens):
                old_path = tokens[idx]
                new_path = tokens[idx + 1]
                idx += 2
                if old_path:
                    norm_old = normalize_path(old_path)
                    if norm_old:
                        changed_set.add(norm_old)
                if new_path:
                    norm_new = normalize_path(new_path)
                    if norm_new:
                        changed_set.add(norm_new)
            else:
                break
        elif status_code.startswith("C"):
            # Copy: new_path was created; old_path is an unchanged provenance source
            if idx + 1 < len(tokens):
                _old_source = tokens[idx]
                new_path = tokens[idx + 1]
                idx += 2
                if new_path:
                    norm_new = normalize_path(new_path)
                    if norm_new:
                        changed_set.add(norm_new)
            else:
                break
        else:
            if idx < len(tokens):
                path = tokens[idx]
                idx += 1
                if path:
                    norm_path = normalize_path(path)
                    if norm_path:
                        changed_set.add(norm_path)
            else:
                break

    return changed_set


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify whether changed tracked files between <base> and HEAD are allowed."
    )
    parser.add_argument(
        "--base",
        required=True,
        help="Base Git reference (e.g., origin/main)",
    )
    parser.add_argument(
        "--allow",
        action="append",
        nargs="*",
        default=[],
        help="Allowed repository-relative path",
    )

    args = parser.parse_args()
    base_ref: str = args.base

    raw_allowed: List[str] = [
        path for group in args.allow for path in group if path
    ]
    allowed_set: Set[str] = {
        normalize_path(p) for p in raw_allowed if normalize_path(p)
    }
    sorted_allowed: List[str] = sorted(list(allowed_set))

    # Verify git environment
    try:
        rev_parse = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
        if rev_parse.returncode != 0:
            emit_result_and_exit(
                status=3,
                base=base_ref,
                changed_paths=[],
                allowed_paths=sorted_allowed,
                unexpected_paths=[],
                stderr_message="Error: Not a Git repository or Git command unavailable.",
            )
    except Exception as e:
        emit_result_and_exit(
            status=3,
            base=base_ref,
            changed_paths=[],
            allowed_paths=sorted_allowed,
            unexpected_paths=[],
            stderr_message=f"Error executing Git: {e}",
        )

    # Run git diff between <base>...HEAD
    diff_target = f"{base_ref}...HEAD"
    try:
        diff_proc = subprocess.run(
            [
                "git",
                "diff",
                "--name-status",
                "-z",
                "-M",
                "-C",
                "--find-copies-harder",
                diff_target,
            ],
            capture_output=True,
        )
    except Exception as e:
        emit_result_and_exit(
            status=3,
            base=base_ref,
            changed_paths=[],
            allowed_paths=sorted_allowed,
            unexpected_paths=[],
            stderr_message=f"Error executing git diff: {e}",
        )

    if diff_proc.returncode != 0:
        err_msg = diff_proc.stderr.decode("utf-8", errors="replace").strip()
        emit_result_and_exit(
            status=3,
            base=base_ref,
            changed_paths=[],
            allowed_paths=sorted_allowed,
            unexpected_paths=[],
            stderr_message=f"Error: Git diff failed for target '{diff_target}': {err_msg}",
        )

    changed_set = parse_git_diff_z(diff_proc.stdout)
    sorted_changed = sorted(list(changed_set))

    if not sorted_changed:
        emit_result_and_exit(
            status=3,
            base=base_ref,
            changed_paths=[],
            allowed_paths=sorted_allowed,
            unexpected_paths=[],
            stderr_message=f"No tracked files differ between '{base_ref}' and HEAD.",
        )

    unexpected_set = {p for p in sorted_changed if p not in allowed_set}
    sorted_unexpected = sorted(list(unexpected_set))

    if sorted_unexpected:
        emit_result_and_exit(
            status=2,
            base=base_ref,
            changed_paths=sorted_changed,
            allowed_paths=sorted_allowed,
            unexpected_paths=sorted_unexpected,
            stderr_message=f"Scope violation: Unexpected changed paths detected: {', '.join(sorted_unexpected)}",
        )

    emit_result_and_exit(
        status=0,
        base=base_ref,
        changed_paths=sorted_changed,
        allowed_paths=sorted_allowed,
        unexpected_paths=[],
    )


if __name__ == "__main__":
    main()
