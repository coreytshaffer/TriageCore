"""Strict metadata-only intent, release, and read-only audit for local file staging."""

import hashlib
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from .privacy_invariants import assert_persistent_privacy_safe
from .public_export_policy import decode_object

OUTSIDE_VISIBILITY = (
    "manual_transfer_and_delivered_bytes",
    "provider_retention_logging_and_training",
    "served_model_and_safeguard_mode",
    "recipient_tools_and_browsing",
    "direct_browser_uploads",
)
_INTENT = {
    "kind", "attempt_id", "eligibility_id", "policy_digest", "payload_digest",
    "directory_locator_digest", "file_locator_digest", "acknowledged_triggers",
    "confirmed_at", "approval_expires_at",
}
_RELEASE = {
    "kind", "attempt_id", "intent_digest", "outcome", "readback_digest",
    "cleanup", "incident", "outside_visibility",
}
_TRIGGERS = {"steward_match", "recipient_review_always", "elevated_task_risk"}
_OUTCOMES = {
    "refused_pre_staging", "staging_failed_partial", "staging_uncertain",
    "staged_verified", "staged_unverified", "staged_mismatch",
}
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_FILE = re.compile(r"([0-9a-f-]{36})\.(intent|release)\.json\Z")


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def locator_digest(path: Path) -> str:
    return digest(b"triagecore.export_locator.v0\0" + str(path).encode("utf-8"))


def open_evidence_directory(policy, evidence_dir: Path | None):
    from .public_export_staging import open_directory

    if (policy.version != 2 or evidence_dir is None or not policy.evidence_root
            or Path(evidence_dir) != Path(policy.evidence_root)):
        raise ValueError("evidence_directory_not_authorized")
    return open_directory(Path(evidence_dir), root=Path(policy.evidence_root),
                          denied_sync_roots=policy.denied_sync_roots, evidence=True)


def intent_record(attempt_id, eligibility_id, policy_digest, payload_digest,
                  directory_locator_digest, file_locator_digest, triggers, confirmed_at,
                  approval_expires_at):
    return {
        "kind": "intent", "attempt_id": attempt_id, "eligibility_id": eligibility_id,
        "policy_digest": policy_digest, "payload_digest": payload_digest,
        "directory_locator_digest": directory_locator_digest, "file_locator_digest": file_locator_digest,
        "acknowledged_triggers": list(triggers), "confirmed_at": confirmed_at,
        "approval_expires_at": approval_expires_at,
    }


def release_record(attempt_id, intent_digest, outcome, readback_digest, cleanup):
    return {
        "kind": "release", "attempt_id": attempt_id, "intent_digest": intent_digest,
        "outcome": outcome, "readback_digest": readback_digest, "cleanup": cleanup,
        "incident": "readback_mismatch" if outcome == "staged_mismatch" else None,
        "outside_visibility": list(OUTSIDE_VISIBILITY),
    }


def _is_digest(value):
    return isinstance(value, str) and _DIGEST.fullmatch(value) is not None


def _time(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|\+00:00)", value
    ):
        raise ValueError("invalid_evidence")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _validate(record):
    if not isinstance(record, dict):
        raise ValueError("invalid_evidence")  # noqa: TRY004 - uniformly reject malformed records
    fields = _INTENT if record.get("kind") == "intent" else _RELEASE
    if set(record) != fields or record["kind"] not in ("intent", "release"):
        raise ValueError("invalid_evidence")
    attempt = record["attempt_id"]
    if not isinstance(attempt, str) or str(UUID(attempt)) != attempt or UUID(attempt).version != 4:
        raise ValueError("invalid_evidence")
    if fields is _INTENT:
        for field in ("eligibility_id", "policy_digest", "payload_digest", "directory_locator_digest",
                      "file_locator_digest"):
            if not _is_digest(record[field]):
                raise ValueError("invalid_evidence")
        triggers = record["acknowledged_triggers"]
        if (not isinstance(triggers, list) or any(t not in tuple(_TRIGGERS) for t in triggers)
                or triggers != sorted(set(triggers))):
            raise ValueError("invalid_evidence")
        interval = _time(record["approval_expires_at"]) - _time(record["confirmed_at"])
        if not timedelta(0) <= interval <= timedelta(seconds=120):
            raise ValueError("invalid_evidence")
    else:
        outcome, observed = record["outcome"], record["readback_digest"]
        if (outcome not in tuple(_OUTCOMES) or not _is_digest(record["intent_digest"])
                or (observed is not None and not _is_digest(observed))
                or (outcome in ("staged_verified", "staged_mismatch") and observed is None)
                or record["outside_visibility"] != list(OUTSIDE_VISIBILITY)
                or record["incident"] != ("readback_mismatch" if outcome == "staged_mismatch" else None)):
            raise ValueError("invalid_evidence")
        cleanup = record["cleanup"]
        if cleanup not in (None, "removed", "failed", "unknown"):
            raise ValueError("invalid_evidence")
        if outcome == "staging_failed_partial" and cleanup is None:
            raise ValueError("invalid_evidence")
    assert_persistent_privacy_safe(record, artifact_name="public export evidence")


def write_record(handle, record) -> str:
    _validate(record)
    raw = json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    name = f"{record['attempt_id']}.{record['kind']}.json"
    handle.revalidate()
    committed_digest = handle.write_new(name, raw)
    if committed_digest != digest(raw):
        raise OSError("evidence_write_unverified")
    return committed_digest


def audit(handle) -> list[dict]:
    """Pair each intent with its release. These records never authorize a write."""
    handle.revalidate()
    grouped = {}
    for name in handle.names():
        match = _FILE.fullmatch(name)
        if match:
            attempt, kind = match.groups()
            grouped.setdefault(attempt, {})[kind] = name
    results = []
    for attempt, names in sorted(grouped.items()):
        if "intent" not in names:
            raise ValueError("release_without_intent")
        raw = handle.read(names["intent"])
        intent = decode_object(raw)
        _validate(intent)
        if intent["attempt_id"] != attempt or intent["kind"] != "intent":
            raise ValueError("evidence_identity_mismatch")
        row = {"attempt_id": attempt, "eligibility_id": intent["eligibility_id"],
               "outcome": "outcome_unknown", "incident": None, "outside_visibility": list(OUTSIDE_VISIBILITY)}
        if "release" in names:
            try:
                record = decode_object(handle.read(names["release"]))
                _validate(record)
            except (OSError, ValueError):
                # A crash can leave a partially written release. The intent still exists.
                row["incident"] = "unreadable_release_evidence"
            else:
                if (record["kind"] != "release" or record["attempt_id"] != attempt
                        or record["intent_digest"] != digest(raw)):
                    raise ValueError("evidence_identity_mismatch")
                equal = record["readback_digest"] == intent["payload_digest"]
                if ((record["outcome"] == "staged_verified" and not equal)
                        or (record["outcome"] == "staged_mismatch" and equal)):
                    raise ValueError("evidence_digest_mismatch")
                row.update(outcome=record["outcome"], incident=record["incident"], cleanup=record["cleanup"])
        results.append(row)
    return results
