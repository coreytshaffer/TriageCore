"""Single loopback model boundary and run orchestration for CR-138.

``ReviewModel`` talks only to Ollama at the constant destination
``127.0.0.1:11434`` with exactly two method/path pairs: ``GET /api/tags``
(preflight) and ``POST /api/chat``. It uses standard-library ``http.client``
with no proxy, redirect, fallback, or retry. Each exchange has an absolute
monotonic deadline from before connection through the last body byte, an
inactivity timeout on the socket, a watchdog that aborts the owned
connection at the deadline, and a body cap enforced while reading.

No host name, environment variable, configuration value, or command-line
option can change the destination.
"""

from __future__ import annotations

import http.client
import json
import socket
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional

from triage_core import checklist_review as cr
from triage_core.checklist_review import ChecklistReviewError, ComponentResult, PolicyResult
from triage_core.checklist_review_store import ReviewStore, StoreError

LOOPBACK_HOST = "127.0.0.1"
LOOPBACK_PORT = 11434
TAGS_REQUEST = ("GET", "/api/tags")
CHAT_REQUEST = ("POST", "/api/chat")
ALLOWED_REQUESTS = (TAGS_REQUEST, CHAT_REQUEST)
TAGS_INACTIVITY_SECONDS = 5.0
CHAT_INACTIVITY_SECONDS = 240.0
READ_CHUNK_BYTES = 16 * 1024

RUNTIME_FIELDS = (
    "done_reason",
    "response_model_matches",
    "thinking_returned",
    "total_duration_ns",
    "load_duration_ns",
    "prompt_eval_count",
    "prompt_eval_duration_ns",
    "eval_count",
    "eval_duration_ns",
)
UNKNOWN_RUNTIME: Mapping[str, Any] = {name: "unknown" for name in RUNTIME_FIELDS}
_RUNTIME_INTEGERS = (
    ("total_duration", "total_duration_ns"),
    ("load_duration", "load_duration_ns"),
    ("prompt_eval_count", "prompt_eval_count"),
    ("prompt_eval_duration", "prompt_eval_duration_ns"),
    ("eval_count", "eval_count"),
    ("eval_duration", "eval_duration_ns"),
)
_DONE_REASONS = ("stop", "length")

_FAILURE_CODES = {
    "tags": {
        "unavailable": "runtime_unavailable",
        "timeout": "tags_timeout",
        "redirect": "transport_refused",
        "status": "runtime_unavailable",
        "too_large": "tags_response_too_large",
        "truncated": "tags_invalid_response",
    },
    "chat": {
        "unavailable": "completion_failed",
        "timeout": "timeout",
        "redirect": "transport_refused",
        "status": "completion_failed",
        "too_large": "response_too_large",
        "truncated": "chat_invalid_response",
    },
}


class SystemClock:
    def monotonic(self) -> float:
        return time.monotonic()

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


@dataclass(frozen=True)
class PreflightResult:
    status: str
    reason_code: Optional[str]
    identity_source: str
    observed_tag: Optional[str] = None
    observed_digest: Optional[str] = None


@dataclass(frozen=True)
class ChatResult:
    status: str
    reason_code: Optional[str]
    reply_text: Optional[str] = field(repr=False)
    runtime: Mapping[str, Any]


class _DeadlineExceeded(Exception):
    pass


class _Deadline:
    """Absolute monotonic deadline plus a watchdog that aborts the connection."""

    def __init__(self, clock: Any, seconds: float, timer_factory: Callable[..., Any], abort: Callable[[], None]):
        self._clock = clock
        self._end = clock.monotonic() + seconds
        self._abort = abort
        self.expired = False
        self._timer = timer_factory(seconds, self._fire)
        try:
            self._timer.daemon = True
        except AttributeError:
            pass
        self._timer.start()

    def _fire(self) -> None:
        self.expired = True
        self._abort()

    def remaining(self) -> float:
        return self._end - self._clock.monotonic()

    def check(self) -> None:
        if self.expired or self.remaining() <= 0:
            raise _DeadlineExceeded()

    def cancel(self) -> None:
        self._timer.cancel()


@dataclass(frozen=True)
class _Outcome:
    failure: Optional[str]
    body: Optional[bytes] = None


def _default_connection(host: str, port: int, timeout: float) -> http.client.HTTPConnection:
    return http.client.HTTPConnection(host, port, timeout=timeout)


def _reject_constant(name: str) -> Any:
    raise ValueError(name)


def _load_json(body: bytes) -> Any:
    return json.loads(body.decode("utf-8"), parse_constant=_reject_constant)


class ReviewModel:
    """Loopback-only Ollama client. The destination is a module constant."""

    origin = "live"
    label: Optional[str] = None
    refers_to: Optional[str] = None

    def __init__(
        self,
        *,
        connection_factory: Optional[Callable[[str, int, float], Any]] = None,
        clock: Optional[Any] = None,
        timer_factory: Optional[Callable[..., Any]] = None,
    ) -> None:
        self._connection_factory = connection_factory or _default_connection
        self._clock = clock or SystemClock()
        self._timer_factory = timer_factory or threading.Timer

    # --- Public calls -------------------------------------------------------

    def preflight(self, tag: str, expected_digest: str) -> PreflightResult:
        outcome = self._exchange(
            "tags", TAGS_REQUEST, None, cr.TAGS_DEADLINE_SECONDS, TAGS_INACTIVITY_SECONDS, cr.TAGS_BODY_LIMIT_BYTES
        )
        if outcome.failure is not None:
            return PreflightResult("stopped", outcome.failure, "observed")
        return _check_tags(outcome.body, tag, expected_digest)

    def chat(self, body: bytes) -> ChatResult:
        if len(body) > cr.CHAT_REQUEST_LIMIT_BYTES:
            return ChatResult("stopped", "request_too_large", None, dict(UNKNOWN_RUNTIME))
        try:
            expected_tag = json.loads(body.decode("utf-8")).get("model")
        except (UnicodeDecodeError, ValueError, AttributeError):
            expected_tag = None
        outcome = self._exchange(
            "chat", CHAT_REQUEST, body, cr.CHAT_DEADLINE_SECONDS, CHAT_INACTIVITY_SECONDS, cr.CHAT_BODY_LIMIT_BYTES
        )
        if outcome.failure is not None:
            return ChatResult("failed", outcome.failure, None, dict(UNKNOWN_RUNTIME))
        return _read_chat_envelope(outcome.body, expected_tag)

    # --- Transport ----------------------------------------------------------

    @staticmethod
    def _bound(sock: Any, deadline: _Deadline, inactivity: float) -> None:
        if sock is not None:
            sock.settimeout(max(0.001, min(inactivity, deadline.remaining())))

    def _exchange(
        self,
        endpoint: str,
        request: tuple[str, str],
        body: Optional[bytes],
        deadline_seconds: float,
        inactivity: float,
        cap: int,
    ) -> _Outcome:
        if request not in ALLOWED_REQUESTS:
            raise ChecklistReviewError("transport_refused")
        codes = _FAILURE_CODES[endpoint]
        method, path = request
        connection = None
        response = None
        sock = None

        def abort() -> None:
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

        deadline = _Deadline(self._clock, deadline_seconds, self._timer_factory, abort)
        try:
            try:
                connection = self._connection_factory(
                    LOOPBACK_HOST, LOOPBACK_PORT, max(0.001, min(inactivity, deadline.remaining()))
                )
                deadline.check()
                connection.connect()
                # A connection-closing response can take ownership of this socket.
                sock = getattr(connection, "sock", None)
                deadline.check()
                self._bound(sock, deadline, inactivity)
                headers = {"Accept": "application/json", "Connection": "close"}
                if body is not None:
                    headers["Content-Type"] = "application/json"
                connection.request(method, path, body=body, headers=headers)
                deadline.check()
                self._bound(sock, deadline, inactivity)
                response = connection.getresponse()
                deadline.check()
            except _DeadlineExceeded:
                return _Outcome(codes["timeout"])
            except TimeoutError:
                return _Outcome(codes["timeout"])
            except (OSError, http.client.HTTPException, ValueError):
                return _Outcome(codes["timeout"] if deadline.expired else codes["unavailable"])

            status = response.status
            if 300 <= status < 400:
                return _Outcome(codes["redirect"])
            if status != 200:
                return _Outcome(codes["status"])
            declared_length = None
            declared = response.getheader("Content-Length")
            if declared is not None:
                try:
                    declared_length = int(declared)
                except ValueError:
                    return _Outcome(codes["truncated"])
                if declared_length < 0:
                    return _Outcome(codes["truncated"])
                if declared_length > cap:
                    return _Outcome(codes["too_large"])

            chunks = []
            total = 0
            try:
                # http.client can release the socket when the final body bytes arrive.
                while not response.isclosed():
                    deadline.check()
                    self._bound(sock, deadline, inactivity)
                    chunk = response.read1(min(READ_CHUNK_BYTES, cap + 1 - total))
                    deadline.check()
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > cap:
                        return _Outcome(codes["too_large"])
                    chunks.append(chunk)
            except _DeadlineExceeded:
                return _Outcome(codes["timeout"])
            except TimeoutError:
                return _Outcome(codes["timeout"])
            except http.client.IncompleteRead:
                return _Outcome(codes["timeout"] if deadline.expired else codes["truncated"])
            except (OSError, http.client.HTTPException, ValueError):
                return _Outcome(codes["timeout"] if deadline.expired else codes["truncated"])
            if declared_length is not None and total != declared_length:
                return _Outcome(codes["truncated"])
            return _Outcome(None, b"".join(chunks))
        finally:
            deadline.cancel()
            for resource in (response, connection):
                if resource is not None:
                    try:
                        resource.close()
                    except Exception:  # noqa: BLE001 - closing an owned resource is best effort
                        pass


def _check_tags(body: bytes, tag: str, expected_digest: str) -> PreflightResult:
    def stopped(code: str, digest: Optional[str] = None) -> PreflightResult:
        return PreflightResult("stopped", code, "observed", tag if digest else None, digest)

    try:
        payload = _load_json(body)
    except (UnicodeDecodeError, ValueError, RecursionError):
        return stopped("tags_invalid_response")
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list) or not all(
        isinstance(entry, dict) and isinstance(entry.get("name"), str) for entry in models
    ):
        return stopped("tags_invalid_response")
    matches = [entry for entry in models if entry["name"] == tag]
    if len(matches) > 1:
        return stopped("tags_invalid_response")
    if not matches:
        return stopped("model_not_installed")
    observed = matches[0].get("digest")
    if not cr.is_sha256_hex(observed):
        return stopped("tags_invalid_response")
    if observed != expected_digest:
        return stopped("model_digest_mismatch", observed)
    return PreflightResult("ok", None, "observed", tag, observed)


def _read_chat_envelope(body: bytes, expected_tag: Optional[str]) -> ChatResult:
    def invalid() -> ChatResult:
        return ChatResult("failed", "chat_invalid_response", None, dict(UNKNOWN_RUNTIME))

    try:
        payload = _load_json(body)
    except (UnicodeDecodeError, ValueError, RecursionError):
        return invalid()
    if not isinstance(payload, dict) or payload.get("done") is not True:
        return invalid()
    message = payload.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        return invalid()
    content = message["content"]
    try:
        content.encode("utf-8")
    except UnicodeEncodeError:
        return invalid()
    runtime: dict[str, Any] = dict(UNKNOWN_RUNTIME)
    done_reason = payload.get("done_reason")
    if isinstance(done_reason, str) and done_reason in _DONE_REASONS:
        runtime["done_reason"] = done_reason
    elif done_reason is not None:
        runtime["done_reason"] = "other"
    if isinstance(payload.get("model"), str) and isinstance(expected_tag, str):
        runtime["response_model_matches"] = payload["model"] == expected_tag
    thinking = message.get("thinking")
    runtime["thinking_returned"] = isinstance(thinking, str) and bool(thinking.strip())
    for source, target in _RUNTIME_INTEGERS:
        value = payload.get(source)
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            runtime[target] = value
    return ChatResult("completed", None, content, runtime)


class RecordedReply:
    """Replays one recorded model reply through the same runner with no I/O.

    Its identity is the recorded one, never an observation, and the live
    runtime confirmation is inapplicable."""

    origin = "recorded"

    def __init__(self, reply_text: str, *, model_tag: str, model_digest: str, label: str, refers_to: str) -> None:
        if not isinstance(reply_text, str):
            raise ChecklistReviewError("recorded_reply_invalid")
        cr.validate_model_identity(model_tag, model_digest)
        self.reply_text = reply_text
        self.model_tag = model_tag
        self.model_digest = model_digest
        self.label = label
        self.refers_to = refers_to

    def preflight(self, tag: str, expected_digest: str) -> PreflightResult:
        if tag != self.model_tag:
            return PreflightResult("stopped", "model_not_installed", "recorded")
        if expected_digest != self.model_digest:
            return PreflightResult("stopped", "model_digest_mismatch", "recorded", tag, self.model_digest)
        return PreflightResult("ok", None, "recorded", self.model_tag, self.model_digest)

    def chat(self, body: bytes) -> ChatResult:
        return ChatResult("completed", None, self.reply_text, dict(UNKNOWN_RUNTIME))


@dataclass(frozen=True)
class RunOutcome:
    run_id: str
    status: str
    reason_code: Optional[str]
    stage: str
    stages: tuple[str, ...]
    event_ids: Mapping[str, str]
    rule: Optional[ComponentResult] = None
    model: Optional[ComponentResult] = None
    policy: Optional[PolicyResult] = None


def _seconds(value: Any) -> Any:
    if isinstance(value, int) and not isinstance(value, bool):
        return round(value / 1e9, 6)
    return "unknown"


def run_review(
    store: ReviewStore,
    *,
    workflow_ref: str,
    case_bytes: bytes,
    model: Any,
    confirm_local_runtime: bool = False,
    clock: Optional[Any] = None,
    refers_to: Optional[str] = None,
) -> RunOutcome:
    """Run one saved review on one case, recording every stage reached.

    The attempt start, case, and rule result are saved before any network
    I/O. A missing live confirmation, a definition evidence gap, or a failed
    preflight stops before any chat request."""
    clock = clock or SystemClock()
    definition = store.load_definition(workflow_ref)
    origin = getattr(model, "origin", None)
    if origin not in ("live", "recorded"):
        raise ChecklistReviewError("model_origin_invalid")
    if origin == "recorded":
        confirmation = "inapplicable"
    else:
        confirmation = "confirmed" if confirm_local_runtime else "absent"
    profile = definition.record["model_profile"]
    limits = definition.record["limits"]
    if not isinstance(case_bytes, (bytes, bytearray)):
        raise ChecklistReviewError("case_encoding_invalid")
    case_bytes = bytes(case_bytes)
    case_within_limit = len(case_bytes) <= limits["case_bytes"]

    started_at = clock.monotonic()
    started = store.begin_run(
        definition,
        origin=origin,
        origin_label=getattr(model, "label", None),
        refers_to=getattr(model, "refers_to", None) or refers_to,
        runtime_confirmation=confirmation,
        case_bytes=case_bytes if case_within_limit else None,
        case_size=len(case_bytes),
    )
    run_id = started.run_id
    stages = ["attempt"]
    event_ids = {"attempt": started.event_id}

    def elapsed() -> float:
        return round(max(0.0, clock.monotonic() - started_at), 6)

    def finish(status: str, reason: Optional[str], stage: str, **results: Any) -> RunOutcome:
        event = store.append_event(
            run_id,
            step="attempt",
            kind="finished",
            status=status,
            reason_code=reason,
            record={"stage": stage, "stages_reached": list(stages), "measurements": {"end_to_end_s": elapsed()}},
        )
        event_ids["finished"] = event.event_id
        return RunOutcome(run_id, status, reason, stage, tuple(stages), dict(event_ids), **results)

    if not case_within_limit:
        return finish("stopped", "case_too_large", "input")
    try:
        case = cr.parse_case(case_bytes)
    except cr.CaseInputError as exc:
        return finish("stopped", exc.reason_code, "input")

    rule = cr.apply_rule(case)
    event_ids["rule"] = store.append_event(
        run_id,
        step="rule",
        kind="result",
        status=rule.status,
        item_id=cr.ITEM_ID,
        reason_code=rule.reason_code,
        record=rule.to_metadata(),
    ).event_id
    stages.append("rule")

    try:
        system_text, user_template = store.verify_definition_templates(definition)
    except StoreError as exc:
        return finish("stopped", exc.reason_code, "definition", rule=rule)
    if confirmation == "absent":
        return finish("stopped", "runtime_locality_unconfirmed", "confirmation", rule=rule)

    preflight = model.preflight(profile["tag"], profile["expected_digest"])
    event_ids["preflight"] = store.append_event(
        run_id,
        step="model",
        kind="preflight",
        status=preflight.status,
        reason_code=preflight.reason_code,
        record={
            "identity_source": preflight.identity_source,
            "request": " ".join(TAGS_REQUEST) if origin == "live" else "none",
            "expected_tag": profile["tag"],
            "expected_digest": profile["expected_digest"],
            "observed_tag": preflight.observed_tag,
            "observed_digest": preflight.observed_digest,
        },
    ).event_id
    stages.append("preflight")
    if preflight.status != "ok":
        return finish("stopped", preflight.reason_code, "preflight", rule=rule)

    settings = profile["request_settings"]
    body = cr.build_chat_request(
        model_tag=profile["tag"],
        case=case,
        system_text=system_text,
        user_template=user_template,
        options=settings["options"],
        think=settings["think"],
        stream=settings["stream"],
    )
    if len(body) > limits["chat_request_bytes"]:
        return finish("stopped", "request_too_large", "request", rule=rule)
    event_ids["request"] = store.append_event(
        run_id,
        step="model",
        kind="request",
        status="prepared",
        record={
            "request": " ".join(CHAT_REQUEST) if origin == "live" else "none",
            "settings_sent": {"model": profile["tag"], **settings},
            "message_count": 2,
            "system_text_sha256": cr.sha256_hex(system_text.encode("utf-8")),
            "user_template_sha256": cr.sha256_hex(user_template.encode("utf-8")),
            "case_sha256": case.sha256,
            "request_sha256": cr.sha256_hex(body),
            "request_bytes": len(body),
        },
        new_artifacts={"request": (body, "chat_request")},
    ).event_id
    stages.append("request")

    chat = model.chat(body)
    if chat.status != "completed":
        status = "failed" if chat.status == "failed" else "stopped"
        return finish(status, chat.reason_code, "model", rule=rule)

    parsed = cr.parse_model_result(case, chat.reply_text)
    status = "returned_valid" if parsed.status == "valid" else "returned_invalid"
    runtime = {name: chat.runtime.get(name, "unknown") for name in RUNTIME_FIELDS}
    event_ids["model"] = store.append_event(
        run_id,
        step="model",
        kind="result",
        status=status,
        item_id=cr.ITEM_ID,
        reason_code=parsed.reason_code,
        record={
            **parsed.to_metadata(),
            "runtime": runtime,
            "measurements": {
                "model_generation_s": _seconds(runtime["eval_duration_ns"]),
                "runtime_total_s": _seconds(runtime["total_duration_ns"]),
                "runtime_load_s": _seconds(runtime["load_duration_ns"]),
            },
        },
        new_artifacts={"output": (chat.reply_text.encode("utf-8"), "model_output")},
    ).event_id
    stages.append("model")

    policy = cr.combine(rule, parsed)
    event_ids["policy"] = store.append_event(
        run_id,
        step="policy",
        kind="result",
        status=policy.agreement,
        item_id=cr.ITEM_ID,
        reason_code=policy.reason_code,
        record={
            **policy.to_metadata(),
            "rule_event_id": event_ids["rule"],
            "model_event_id": event_ids["model"],
            "measurements": {"end_to_end_to_policy_s": elapsed()},
        },
    ).event_id
    stages.append("policy")
    return finish(status, parsed.reason_code, "policy", rule=rule, model=parsed, policy=policy)
