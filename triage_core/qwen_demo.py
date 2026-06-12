from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Sequence

from .client import TriageClient
from .config import default_config
from .task_ledger import TaskLedger
from .task_packet import PrivacyMetadata, TaskPacket


DEMO_PROMPT = (
    "[triagecore:novel_design] Novel design task. Return a JSON object with "
    "exactly these keys: "
    "summary, qwen_role, safeguards, next_step. Describe a public demonstration "
    "of local-first orchestration with bounded Qwen Cloud help. Keep each value "
    "concise. The safeguards value must be a JSON array of strings. Do not use "
    "markdown."
)

DEMO_DATA = (
    "Public synthetic scenario: compare local-first processing with optional "
    "cloud assistance for a fictional documentation workflow."
)


class QwenDemoConfigurationError(RuntimeError):
    """Raised when the optional live Qwen demo is not configured."""


@dataclass(frozen=True)
class QwenDemoEvidence:
    task_id: str
    status: str
    source: str
    selected_route: Optional[str]
    selected_backend: Optional[str]
    model: Optional[str]
    privacy_level: Optional[str]
    route_decision: Optional[str]
    route_reason: Optional[str]
    validation_status: Optional[str]
    elapsed_seconds: float
    input_tokens: int
    output_tokens: int
    total_tokens: int
    output: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_public_demo_packet(task_id: Optional[str] = None) -> TaskPacket:
    return TaskPacket(
        task_id=task_id or f"qwen-demo-{uuid.uuid4().hex[:12]}",
        prompt=DEMO_PROMPT,
        data=DEMO_DATA,
        validator=validate_qwen_demo_response,
        privacy_metadata=PrivacyMetadata(
            data_class="public",
            contains_pii=False,
            contains_sensitive_content=False,
            contains_precise_location=False,
            external_model_allowed=True,
            retention_policy="metadata_only",
            redaction_required=False,
        ),
    )


def validate_qwen_demo_response(response_text: str) -> bool:
    try:
        payload = json.loads(response_text)
    except (TypeError, json.JSONDecodeError):
        return False

    if not isinstance(payload, dict):
        return False

    expected_keys = {"summary", "qwen_role", "safeguards", "next_step"}
    if set(payload) != expected_keys:
        return False

    text_fields = ("summary", "qwen_role", "next_step")
    if any(
        not isinstance(payload[field], str) or not payload[field].strip()
        for field in text_fields
    ):
        return False

    safeguards = payload["safeguards"]
    return (
        isinstance(safeguards, list)
        and bool(safeguards)
        and all(isinstance(item, str) and item.strip() for item in safeguards)
    )


validate_qwen_demo_response.name = "qwen_public_demo_schema"
validate_qwen_demo_response.version = "1.0"
validate_qwen_demo_response.scope = "public_synthetic_json"


def run_qwen_demo(
    *,
    ledger_dir: str = ".triagecore",
    task_id: Optional[str] = None,
    client: Optional[TriageClient] = None,
) -> QwenDemoEvidence:
    if not default_config.get_qwen_enabled():
        raise QwenDemoConfigurationError(
            "Qwen Cloud execution is disabled. Set TRIAGE_QWEN_ENABLED=true."
        )
    if not default_config.get_qwen_api_key():
        raise QwenDemoConfigurationError(
            "Qwen Cloud API key is missing. Set TRIAGE_QWEN_API_KEY."
        )

    packet = build_public_demo_packet(task_id)
    ledger = TaskLedger(ledger_dir=ledger_dir)
    active_client = client or TriageClient()
    result = active_client.run_task(task_packet=packet, ledger=ledger)

    audit_events = [
        event
        for event in ledger.get_events(packet.task_id or "")
        if event.get("event_type") == "route_audit"
    ]
    audit_payload = audit_events[-1].get("payload", {}) if audit_events else {}

    return QwenDemoEvidence(
        task_id=packet.task_id or "",
        status=str(result.get("status", "")),
        source=str(result.get("source", "")),
        selected_route=result.get("selected_route"),
        selected_backend=audit_payload.get("selected_backend"),
        model=result.get("model"),
        privacy_level=audit_payload.get("privacy_level"),
        route_decision=audit_payload.get("decision"),
        route_reason=result.get("route_reason"),
        validation_status=result.get("validation_status"),
        elapsed_seconds=float(result.get("elapsed_seconds", 0.0) or 0.0),
        input_tokens=int(result.get("input_tokens", 0) or 0),
        output_tokens=int(result.get("output_tokens", 0) or 0),
        total_tokens=int(result.get("total_tokens", 0) or 0),
        output=str(result.get("output", "")),
    )


def _print_human_evidence(evidence: QwenDemoEvidence) -> None:
    print("TriageCore Qwen Cloud Proof")
    print(f"Task: {evidence.task_id}")
    print(f"Privacy: {evidence.privacy_level}")
    print(f"Route: {evidence.selected_route}")
    print(f"Backend: {evidence.selected_backend}")
    print(f"Model: {evidence.model}")
    print(f"Status: {evidence.status}")
    print(f"Validation: {evidence.validation_status}")
    print(f"Elapsed: {evidence.elapsed_seconds:.2f}s")
    print(
        "Tokens: "
        f"input={evidence.input_tokens} "
        f"output={evidence.output_tokens} "
        f"total={evidence.total_tokens}"
    )
    print("Public synthetic response:")
    print(evidence.output)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a public, privacy-gated Qwen Cloud proof task."
    )
    parser.add_argument(
        "--ledger-dir",
        default=".triagecore",
        help="Directory containing ledger.jsonl.",
    )
    parser.add_argument("--task-id", default=None)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the privacy-safe evidence summary as JSON.",
    )
    args = parser.parse_args(argv)

    try:
        evidence = run_qwen_demo(
            ledger_dir=args.ledger_dir,
            task_id=args.task_id,
        )
    except QwenDemoConfigurationError as exc:
        print(f"Error: {exc}")
        return 2

    if args.json:
        print(json.dumps(evidence.to_dict(), indent=2, sort_keys=True))
    else:
        _print_human_evidence(evidence)

    return 0 if evidence.status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
