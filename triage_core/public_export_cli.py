"""Operator terminal for one CR-134 export invocation or read-only evidence audit."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from .public_export_policy import InputError, parse_policy


class SystemClock:
    def now(self):
        return datetime.now(timezone.utc)

    def monotonic(self):
        return time.monotonic()


class TerminalOperator:
    """A single terminal submission per question. Empty/invalid responses decline."""

    def _read(self, prompt):
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return None
        try:
            return input(prompt)
        except (EOFError, KeyboardInterrupt):
            return None

    def access(self, provider, surface, programs):
        fields = " ".join(f"{p}=<none|granted|unknown>" for p in programs)
        reply = self._read(f"Account and program grants for {provider}/{surface}. Enter <account> {fields}: ")
        if not reply:
            return None
        words = reply.split()
        if len(words) != 1 + len(programs):
            return None
        grants = {}
        for word in words[1:]:
            program, separator, state = word.partition("=")
            if not separator or program not in programs or state not in {"none", "granted", "unknown"}:
                return None
            if program in grants:
                return None
            grants[program] = state
        return words[0], grants

    def destination(self):
        reply = self._read("Destination and sync attestation. Enter UNSYNCED followed by the absolute directory: ")
        if not reply or not reply.startswith("UNSYNCED "):
            return None
        destination = Path(reply.removeprefix("UNSYNCED "))
        return (destination, True) if destination.is_absolute() else None

    def display(self, screen):
        print(screen, flush=True)

    def acknowledge(self, triggers):
        reply = self._read(f"Acknowledge the exact review triggers [{','.join(triggers)}]: ")
        return tuple(part.strip() for part in reply.split(",")) if reply else None

    def confirm(self, code):
        return self._read(f"Confirmation. Type the displayed code [{code}] to stage once: ")


def register_parser(subparsers):
    parser = subparsers.add_parser(
        "public-export", allow_abbrev=False,
        help="Evaluate a public export, stage a file or audit evidence",
    )
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--stage", action="store_true", help="Stage upon explicit in-process confirmation")
    actions.add_argument("--audit", action="store_true", help="Read the selected policy-authorized evidence directory")
    parser.add_argument("--repo-root", type=Path, help="Source repository root (default: current directory)")
    parser.add_argument("--proposal", help="Repository-relative proposal locator")
    parser.add_argument("--payload", help="Repository-relative payload locator")
    parser.add_argument("--parent", help="Repository-relative authority manifest locator")
    parser.add_argument("--evidence-dir", type=Path, help="Explicit evidence directory for staging or audit")
    return parser


def read_system_policy():
    from . import public_export_staging

    return public_export_staging.read_system_policy()


def _git(root, *args):
    # The selected worktree and its own index establish provenance. Ambient Git
    # directory, index, config and worktree overrides could describe a different checkout.
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    env.update(GIT_OPTIONAL_LOCKS="0", GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    result = subprocess.run(
        ["git", "-C", str(root), "-c", "core.fsmonitor=false", *args],
        env=env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False,
    )
    if result.returncode:
        raise OSError("repository_metadata_unavailable")
    return result.stdout


def source_repository(selected):
    start = Path.cwd() if selected is None else selected.absolute()
    values = _git(start, "rev-parse", "--is-inside-work-tree", "--show-toplevel").decode("utf-8").splitlines()
    if len(values) != 2 or values[0] != "true":
        raise OSError("source_repository_unavailable")
    root = Path(values[1])
    if not root.is_absolute() or (selected is not None and root != start) or not (root / ".git").exists():
        raise OSError("source_repository_unavailable")
    return root


def implementation_commit():
    """Bind the clean checkout containing our package, independently of input paths."""
    code_root = source_repository(Path(__file__).resolve().parents[1])
    if _git(code_root, "status", "--porcelain=v1", "--untracked-files=all", "--", "triage_core"):
        raise OSError("implementation_revision_unavailable")
    commit = _git(code_root, "rev-parse", "--verify", "HEAD^{commit}").decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise OSError("implementation_revision_unavailable")
    return commit


def run_command(parser, args):
    source_args = (args.proposal, args.payload, args.parent)
    if (args.stage or args.audit) and not args.evidence_dir:
        parser.error("--stage and --audit require --evidence-dir")
    if args.audit:
        if any(source_args) or args.repo_root:
            parser.error("--audit accepts only --evidence-dir")
        return _audit(args.evidence_dir)
    if not all(source_args):
        parser.error("both evaluation and staging require --proposal, --payload and --parent")
    if args.evidence_dir and not args.stage:
        parser.error("--evidence-dir requires --stage or --audit")
    from .public_export_release import run_export

    try:
        repo = source_repository(args.repo_root)
    except (OSError, ValueError):
        print(json.dumps({"outcome": "refused_pre_staging", "reason_codes": ["source_repository_unavailable"]}))
        return 2
    try:
        commit = implementation_commit()
    except (OSError, ValueError):
        print(json.dumps({"outcome": "refused_pre_staging", "reason_codes": ["implementation_revision_unavailable"]}))
        return 2
    result = run_export(
        repo_root=repo, proposal_locator=args.proposal,
        payload_locator=args.payload, parent_locator=args.parent, evidence_dir=args.evidence_dir,
        stage=args.stage, policy_source=read_system_policy, operator=TerminalOperator(),
        clock=SystemClock(), triagecore_commit=commit,
    )
    if result.exit_code == 4:
        if result.outcome == "staged_verified":
            print("STAGED — evidence record failed", file=sys.stderr)
        else:
            print(f"Staging outcome: {result.outcome}. Evidence record failed.", file=sys.stderr)
    print(json.dumps({
        "outcome": result.outcome, "reason_codes": result.reason_codes, "review_triggers": result.review_triggers,
        "eligibility_id": result.eligibility_id, "policy_digest": result.policy_digest,
        "attempt_id": result.attempt_id, "outside_visibility": result.outside_visibility,
    }, sort_keys=True))
    return result.exit_code


def _audit(evidence_dir):
    from .public_export_evidence import audit, open_evidence_directory

    try:
        policy = parse_policy(read_system_policy())
        with open_evidence_directory(policy, evidence_dir) as handle:
            entries = audit(handle)
    except InputError as exc:
        print(json.dumps({"outcome": "audit_refused", "reason_codes": [exc.code]}))
        return 2
    except (ValueError, OSError):
        print(json.dumps({"outcome": "audit_refused", "reason_codes": ["evidence_unavailable"]}))
        return 2
    print(json.dumps({"outcome": "audit_complete", "entries": entries}, sort_keys=True))
    return 0
