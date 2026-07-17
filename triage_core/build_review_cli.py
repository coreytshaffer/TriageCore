"""Adapter for integrating build-review into the existing ``tc`` command."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Tuple

from triage_core.build_review import (
    ChangeRequestContract,
    build_review,
    parse_change_request,
    record_decision,
    write_artifacts,
)
from triage_core.build_review_verify import VerificationError, verify_packet


def _add_create_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo", default=".", help="Git repository to inspect")
    request = parser.add_mutually_exclusive_group(required=True)
    request.add_argument("--request", help="Original development request text")
    request.add_argument(
        "--request-file",
        help="File containing the original development request",
    )
    parser.add_argument("--base", default="HEAD", help="Base Git ref")
    parser.add_argument(
        "--head",
        default="WORKTREE",
        help="Head Git ref or WORKTREE",
    )
    parser.add_argument(
        "--expect",
        action="append",
        default=[],
        help="Expected path, directory, or glob; repeat as needed",
    )
    parser.add_argument(
        "--validate",
        action="append",
        default=[],
        help="Trusted local validation command; repeat as needed",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Per-validation timeout in seconds",
    )
    parser.add_argument(
        "--output-dir",
        default=".triagecore/build-reviews",
        help="Root directory for generated review packets",
    )


def configure_parser(parser: argparse.ArgumentParser) -> None:
    actions = parser.add_subparsers(
        dest="build_review_action",
        required=True,
    )
    create_parser = actions.add_parser(
        "create",
        help="Create an evidence-bound review packet",
    )
    _add_create_arguments(create_parser)

    decide_parser = actions.add_parser(
        "decide",
        help="Record one immutable human decision",
    )
    decide_parser.add_argument(
        "packet_path",
        help="Review directory or review.json path",
    )
    decide_parser.add_argument(
        "status",
        choices=["approved", "rejected", "needs_revision"],
    )
    decide_parser.add_argument(
        "--reviewer",
        required=True,
        help="Name of the human reviewer",
    )
    decide_parser.add_argument("--note", help="Optional decision rationale")

    verify_parser = actions.add_parser(
        "verify",
        help="Independently verify packet and decision integrity",
    )
    verify_parser.add_argument(
        "packet_path",
        help="Review directory or review.json path",
    )


def _read_request(
    args: argparse.Namespace,
) -> Tuple[str, str, ChangeRequestContract]:
    if args.request_file:
        path = Path(args.request_file).resolve()
        text = path.read_text(encoding="utf-8")
        return text, str(path), parse_change_request(text)
    text = args.request
    return text, "CLI --request", parse_change_request(text)


def _create_review(args: argparse.Namespace):
    if not 1 <= args.timeout <= 600:
        raise ValueError("--timeout must be between 1 and 600 seconds")
    if len(args.validate) > 10:
        raise ValueError("a review may run at most 10 validation commands")
    request_text, request_source, contract = _read_request(args)
    packet = build_review(
        repo=args.repo,
        request_text=request_text,
        request_source=request_source,
        base=args.base,
        head=args.head,
        expected_scope=args.expect or contract.declared_scope,
        validation_commands=args.validate,
        expected_validations=contract.required_validations,
        request_id=contract.request_id,
        timeout=args.timeout,
    )
    return packet, write_artifacts(packet, args.output_dir)


def _print_created(packet, paths) -> None:
    print(f"Build review: {packet['packet_id']}")
    print(f"Recommendation: {packet['recommendation'].upper()}")
    print(f"JSON evidence: {paths['json']}")
    print(f"Diff summary: {paths['diff_summary']}")
    print(f"Validation results: {paths['validations']}")
    print(f"Readable report: {paths['markdown']}")
    print(f"Review UI: {paths['html']}")


def run(args: argparse.Namespace) -> int:
    try:
        if args.build_review_action == "create":
            packet, paths = _create_review(args)
            _print_created(packet, paths)
            return 0
        if args.build_review_action == "decide":
            supplied = Path(args.packet_path)
            packet_path = supplied / "review.json" if supplied.is_dir() else supplied
            verify_packet(packet_path)
            paths = record_decision(
                packet_path,
                args.status,
                args.reviewer,
                args.note,
            )
            print(f"Decision recorded: {args.status.upper()}")
            print(f"Decision record: {paths['decision']}")
            return 0
        if args.build_review_action == "verify":
            result = verify_packet(args.packet_path)
            print(
                f"VERIFIED {result['review_id']} "
                f"decision={result['decision']} "
                f"evidence_sha256={result['evidence_sha256']}"
            )
            return 0
    except (
        FileExistsError,
        FileNotFoundError,
        OSError,
        VerificationError,
        ValueError,
    ) as exc:
        print(f"tc: error: {exc}", file=sys.stderr)
        return 1
    return 2
