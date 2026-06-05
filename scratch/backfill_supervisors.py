"""Backfill legacy supervisor metadata in a local TriageCore ledger.

Dry-run is the default. Pass --apply to write changes.
"""

import argparse
import json
import os
from pathlib import Path


DEFAULT_LEDGER_PATH = Path(".triagecore") / "ledger.jsonl"


def _legacy_defaults(tool: str) -> tuple[str, str]:
    normalized = tool.lower()
    if normalized == "codex":
        return "Codex", "5.5 High"
    if normalized == "antigravity":
        return "Gemini 3.1 Pro High", "Standard"
    return "Unknown", "Unknown"


def backfill_supervisor_metadata(ledger_path: Path, apply: bool = False) -> int:
    if not ledger_path.exists():
        print(f"Ledger file not found at {ledger_path}")
        return 0

    updated_lines: list[str] = []
    modified_count = 0

    with ledger_path.open("r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                updated_lines.append(raw_line)
                continue

            if record.get("event_type") == "supervisor_reviewed":
                payload = record.get("payload", {})
                tool = payload.get("supervisor_tool", "")
                if not payload.get("supervisor_model"):
                    model, profile = _legacy_defaults(tool)
                    payload["supervisor_model"] = model
                    payload["supervisor_profile"] = profile

                    notes = payload.get("supervisor_notes", "")
                    suffix = "(Reconstructed legacy model metadata)"
                    if suffix not in notes:
                        payload["supervisor_notes"] = (
                            f"{notes} {suffix}" if notes else suffix
                        )

                    record["payload"] = payload
                    line = json.dumps(record)
                    modified_count += 1

            updated_lines.append(line + "\n")

    if modified_count and apply:
        with ledger_path.open("w", encoding="utf-8") as f:
            f.writelines(updated_lines)
        print(f"Backfilled {modified_count} legacy supervisor entries.")
    elif modified_count:
        print(f"Would backfill {modified_count} legacy supervisor entries.")
    else:
        print("No legacy supervisor entries need backfilling.")

    return modified_count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--ledger",
        default=os.fspath(DEFAULT_LEDGER_PATH),
        help="Path to ledger.jsonl. Defaults to .triagecore/ledger.jsonl.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes. Without this flag the script only reports counts.",
    )
    args = parser.parse_args()

    backfill_supervisor_metadata(Path(args.ledger), apply=args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
