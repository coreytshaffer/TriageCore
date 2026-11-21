"""CR-138 loopback model boundary and attempt-state checks (no model service).

Every test injects the connection, clock, and watchdog timer, so the
production control flow in ``ReviewModel`` runs without network access.
"""

import http.client
import json
import socket
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pytest

from triage_core import checklist_review as cr
from triage_core import checklist_review_local as local
from triage_core.checklist_review_store import ReviewStore

FIXTURES = Path(__file__).parent / "fixtures" / "checklist_review"
MODEL_TAG = "qwen3.5:4b"
MODEL_DIGEST = "d8b0f5e9760cd1682034f292d7ef72ec46f432149be0df7574bf2d6e92e38c04"
OTHER_DIGEST = "e5df7dcdd8a263994df62d610317e07be0d6af23f96fcbd8543273058fce575e"


def text_fixture(relative: str) -> bytes:
    return (FIXTURES / relative).read_bytes().replace(b"\r\n", b"\n")


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.value = start

    def monotonic(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds

    def now(self) -> datetime:
        return datetime(2026, 11, 20, tzinfo=timezone.utc) + timedelta(seconds=self.value)


class ManualTimer:
    """Stands in for threading.Timer; the test decides whether it fires."""

    created = []

    def __init__(self, interval, function):
        self.interval = interval
        self.function = function
        self.daemon = False
        self.started = False
        self.cancelled = False
        ManualTimer.created.append(self)

    def start(self):
        self.started = True

    def cancel(self):
        self.cancelled = True

    def fire(self):
        self.function()


@dataclass
class Reply:
    status: int = 200
    body: bytes = b""
    headers: dict = field(default_factory=dict)
    declare_length: bool = True
    chunk_size: int = 65536
    seconds_per_chunk: float = 0.0
    truncate: bool = False
    endless: bool = False
    connect_error: Optional[BaseException] = None
    connect_seconds: float = 0.0
    response_error: Optional[BaseException] = None
    fire_watchdog_on_read: bool = False
    close_after_headers: bool = False


class FakeSocket:
    def __init__(self):
        self.timeouts = []
        self.shut = False

    def settimeout(self, value):
        self.timeouts.append(value)

    def shutdown(self, how):
        self.shut = True


class FakeResponse:
    def __init__(self, reply: Reply, clock: FakeClock, connection):
        self.reply = reply
        self.status = reply.status
        self.clock = clock
        self.connection = connection
        self.socket = connection.sock
        self.closed = False
        self.offset = 0
        self.reads = 0
        headers = {k.lower(): v for k, v in reply.headers.items()}
        if reply.declare_length and "content-length" not in headers:
            headers["content-length"] = str(len(reply.body))
        self._headers = headers

    def getheader(self, name, default=None):
        return self._headers.get(name.lower(), default)

    def read1(self, amount=-1):
        if self.connection.closed:
            raise ValueError("I/O operation on closed connection")
        self.reads += 1
        if self.reply.fire_watchdog_on_read and self.reads == 2:
            ManualTimer.created[-1].fire()
            raise OSError("connection aborted")
        self.clock.advance(self.reply.seconds_per_chunk)
        if self.reply.endless:
            return b"x" * min(amount, self.reply.chunk_size)
        if self.offset >= len(self.reply.body):
            if self.reply.truncate:
                raise http.client.IncompleteRead(b"")
            return b""
        size = min(amount, self.reply.chunk_size)
        chunk = self.reply.body[self.offset:self.offset + size]
        self.offset += len(chunk)
        return chunk

    def close(self):
        self.closed = True


class FakeConnection:
    def __init__(self, reply: Reply, clock: FakeClock, host, port, timeout):
        self.reply = reply
        self.clock = clock
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = None
        self.requests = []
        self.response = None
        self.closed = False

    def connect(self):
        self.clock.advance(self.reply.connect_seconds)
        if self.reply.connect_error is not None:
            raise self.reply.connect_error
        self.sock = FakeSocket()

    def request(self, method, url, body=None, headers=None):
        self.requests.append((method, url, body, dict(headers or {})))

    def getresponse(self):
        if self.reply.response_error is not None:
            raise self.reply.response_error
        self.response = FakeResponse(self.reply, self.clock, self)
        if self.reply.close_after_headers:
            # http.client leaves the socket with the response in this case.
            self.sock = None
        return self.response

    def close(self):
        self.closed = True


class Wire:
    """Connection factory that hands out one scripted connection per call."""

    def __init__(self, clock: FakeClock, *replies: Reply):
        self.clock = clock
        self.replies = list(replies)
        self.connections = []

    def __call__(self, host, port, timeout):
        if not self.replies:
            raise AssertionError("unexpected connection")
        connection = FakeConnection(self.replies.pop(0), self.clock, host, port, timeout)
        self.connections.append(connection)
        return connection

    @property
    def requests(self):
        return [request for connection in self.connections for request in connection.requests]


@pytest.fixture(autouse=True)
def _reset_timers():
    ManualTimer.created.clear()
    yield
    ManualTimer.created.clear()


@pytest.fixture
def clock():
    return FakeClock()


def model_for(wire: Wire, clock: FakeClock) -> local.ReviewModel:
    return local.ReviewModel(connection_factory=wire, clock=clock, timer_factory=ManualTimer)


def tags_body(*entries) -> bytes:
    return json.dumps({"models": list(entries)}).encode("utf-8")


def tag_entry(name=MODEL_TAG, digest=MODEL_DIGEST, **extra):
    entry = {"name": name, "model": name, "digest": digest, "details": {"format": "gguf"}}
    entry.update(extra)
    return entry


GOOD_TAGS = tags_body(tag_entry("ornith-1.5:9b", OTHER_DIGEST), tag_entry())


def chat_body(content='{"case_id": "DC-03"}', **extra) -> bytes:
    payload = {
        "model": MODEL_TAG,
        "message": {"role": "assistant", "content": content},
        "done": True,
        "done_reason": "stop",
        "total_duration": 909612700,
        "load_duration": 10995600,
        "prompt_eval_count": 1116,
        "prompt_eval_duration": 215299000,
        "eval_count": 93,
        "eval_duration": 642434000,
    }
    payload.update(extra)
    return json.dumps(payload).encode("utf-8")


# --- Preflight: GET /api/tags -----------------------------------------------


def test_preflight_uses_the_fixed_loopback_get_and_checks_tag_and_digest(clock):
    wire = Wire(clock, Reply(body=GOOD_TAGS))
    result = model_for(wire, clock).preflight(MODEL_TAG, MODEL_DIGEST)
    assert result.status == "ok"
    assert result.reason_code is None
    assert (result.observed_tag, result.observed_digest) == (MODEL_TAG, MODEL_DIGEST)
    assert result.identity_source == "observed"
    connection = wire.connections[0]
    assert (connection.host, connection.port) == ("127.0.0.1", 11434)
    assert [(m, u, b) for m, u, b, _ in wire.requests] == [("GET", "/api/tags", None)]
    assert connection.closed
    assert 0 < connection.timeout <= 5.0
    assert all(0 < value <= 5.0 for value in connection.sock.timeouts)
    assert ManualTimer.created[0].interval == pytest.approx(5.0)
    assert ManualTimer.created[0].started and ManualTimer.created[0].cancelled


def test_the_loopback_destination_is_not_configurable():
    assert (local.LOOPBACK_HOST, local.LOOPBACK_PORT) == ("127.0.0.1", 11434)
    assert local.ALLOWED_REQUESTS == (("GET", "/api/tags"), ("POST", "/api/chat"))
    with pytest.raises(TypeError):
        local.ReviewModel(host="example.invalid")  # type: ignore[call-arg]


@pytest.mark.parametrize(
    "reply, code",
    [
        (Reply(body=tags_body(tag_entry("ornith-1.5:9b", OTHER_DIGEST))), "model_not_installed"),
        (Reply(body=tags_body()), "model_not_installed"),
        (Reply(body=tags_body(tag_entry(digest=OTHER_DIGEST))), "model_digest_mismatch"),
        (Reply(body=tags_body(tag_entry(), tag_entry())), "tags_invalid_response"),
        (Reply(body=b"{not json"), "tags_invalid_response"),
        (Reply(body=b'{"models": {}}'), "tags_invalid_response"),
        (Reply(body=b"[]"), "tags_invalid_response"),
        (Reply(body=tags_body({"model": MODEL_TAG, "digest": MODEL_DIGEST})), "tags_invalid_response"),
        (Reply(body=tags_body({"name": MODEL_TAG})), "tags_invalid_response"),
        (Reply(body=GOOD_TAGS[:40], headers={"Content-Length": str(len(GOOD_TAGS))}, truncate=True), "tags_invalid_response"),
        (Reply(body=GOOD_TAGS, headers={"Content-Length": str(len(GOOD_TAGS) + 1)}), "tags_invalid_response"),
        (Reply(body=b"x" * (256 * 1024 + 1)), "tags_response_too_large"),
        (Reply(body=b"x" * (256 * 1024 + 1), declare_length=False), "tags_response_too_large"),
        (Reply(status=301, headers={"Location": "http://example.invalid/api/tags"}), "transport_refused"),
        (Reply(status=307, headers={"Location": "/elsewhere"}), "transport_refused"),
        (Reply(status=308), "transport_refused"),
        (Reply(status=500), "runtime_unavailable"),
        (Reply(status=404), "runtime_unavailable"),
        (Reply(connect_error=ConnectionRefusedError()), "runtime_unavailable"),
        (Reply(response_error=http.client.RemoteDisconnected()), "runtime_unavailable"),
        (Reply(connect_error=socket.timeout()), "tags_timeout"),
        (Reply(connect_seconds=5.0), "tags_timeout"),
        (Reply(endless=True, chunk_size=64, seconds_per_chunk=0.5, declare_length=False), "tags_timeout"),
        (Reply(body=GOOD_TAGS, chunk_size=8, fire_watchdog_on_read=True), "tags_timeout"),
    ],
    ids=[
        "tag-absent",
        "empty-list",
        "digest-mismatch",
        "duplicate-tag",
        "malformed-json",
        "models-not-list",
        "not-object",
        "entry-without-name",
        "match-without-digest",
        "truncated",
        "declared-body-eof",
        "oversize-declared",
        "oversize-undeclared",
        "redirect-301",
        "redirect-307",
        "redirect-308",
        "server-error",
        "not-found",
        "refused",
        "disconnected",
        "connect-timeout",
        "slow-connect-past-deadline",
        "bytes-until-deadline",
        "watchdog-abort",
    ],
)
def test_preflight_stops_with_the_tabled_reason(clock, reply, code):
    wire = Wire(clock, reply)
    result = model_for(wire, clock).preflight(MODEL_TAG, MODEL_DIGEST)
    assert result.status == "stopped"
    assert result.reason_code == code
    assert len(wire.connections) == 1
    assert wire.connections[0].closed
    assert [(m, u) for m, u, _, _ in wire.requests] in ([], [("GET", "/api/tags")])
    if code == "model_digest_mismatch":
        assert result.observed_digest == OTHER_DIGEST


def test_endless_tags_body_is_aborted_at_the_absolute_deadline(clock):
    wire = Wire(clock, Reply(endless=True, chunk_size=16, seconds_per_chunk=0.25, declare_length=False))
    started = clock.monotonic()
    result = model_for(wire, clock).preflight(MODEL_TAG, MODEL_DIGEST)
    assert result.reason_code == "tags_timeout"
    assert clock.monotonic() - started <= 5.0 + 0.25
    assert wire.connections[0].closed


def test_deadline_retains_response_socket_after_headers(clock):
    reply = Reply(
        body=GOOD_TAGS,
        chunk_size=8,
        seconds_per_chunk=0.25,
        fire_watchdog_on_read=True,
        close_after_headers=True,
    )
    wire = Wire(clock, reply)

    result = model_for(wire, clock).preflight(MODEL_TAG, MODEL_DIGEST)

    assert result.status == "stopped"
    assert result.reason_code == "tags_timeout"
    response = wire.connections[0].response
    assert response.socket.shut
    assert response.socket.timeouts[-1] == pytest.approx(4.75)
    assert response.closed


# --- Chat: POST /api/chat ---------------------------------------------------


def _request_body() -> bytes:
    case = cr.parse_case(text_fixture("cases/DC-03.txt"))
    return cr.build_chat_request(model_tag=MODEL_TAG, case=case)


def test_chat_posts_the_exact_body_to_the_fixed_endpoint(clock):
    wire = Wire(clock, Reply(body=chat_body("reply text")))
    body = _request_body()
    result = model_for(wire, clock).chat(body)
    assert result.status == "completed"
    assert result.reply_text == "reply text"
    method, url, sent, headers = wire.requests[0]
    assert (method, url) == ("POST", "/api/chat")
    assert sent == body
    assert headers["Content-Type"] == "application/json"
    assert len(json.loads(sent)["messages"]) == 2
    connection = wire.connections[0]
    assert (connection.host, connection.port) == ("127.0.0.1", 11434)
    assert connection.closed
    assert ManualTimer.created[0].interval == pytest.approx(240.0)
    assert ManualTimer.created[0].cancelled
    runtime = result.runtime
    assert runtime["done_reason"] == "stop"
    assert runtime["eval_duration_ns"] == 642434000
    assert runtime["total_duration_ns"] == 909612700
    assert runtime["load_duration_ns"] == 10995600
    assert runtime["response_model_matches"] is True
    assert runtime["thinking_returned"] is False


def test_chat_runtime_metadata_left_unknown_when_absent(clock):
    body = json.dumps({"message": {"role": "assistant", "content": "x"}, "done": True}).encode()
    wire = Wire(clock, Reply(body=body))
    result = model_for(wire, clock).chat(_request_body())
    assert result.status == "completed"
    assert result.runtime["eval_duration_ns"] == "unknown"
    assert result.runtime["done_reason"] == "unknown"
    assert result.runtime["response_model_matches"] == "unknown"


@pytest.mark.parametrize(
    "reason, expected",
    [("length", "length"), ("runtime_status", "other"), (["stop"], "other")],
)
def test_chat_records_only_known_termination_reasons(clock, reason, expected):
    wire = Wire(clock, Reply(body=chat_body(done_reason=reason)))

    result = model_for(wire, clock).chat(_request_body())

    assert result.status == "completed"
    assert result.runtime["done_reason"] == expected


@pytest.mark.parametrize(
    "reply, code",
    [
        (Reply(status=302, headers={"Location": "http://example.invalid/"}), "transport_refused"),
        (Reply(status=307), "transport_refused"),
        (Reply(status=500), "completion_failed"),
        (Reply(connect_error=ConnectionRefusedError()), "completion_failed"),
        (Reply(response_error=http.client.RemoteDisconnected()), "completion_failed"),
        (Reply(connect_error=socket.timeout()), "timeout"),
        (Reply(endless=True, chunk_size=1024, seconds_per_chunk=10.0, declare_length=False), "timeout"),
        (Reply(body=chat_body(), chunk_size=16, fire_watchdog_on_read=True), "timeout"),
        (Reply(body=b"x" * (64 * 1024 + 1)), "response_too_large"),
        (Reply(body=b"x" * (64 * 1024 + 1), declare_length=False), "response_too_large"),
        (Reply(body=chat_body(done=False)), "chat_invalid_response"),
        (Reply(body=chat_body()[:30], headers={"Content-Length": "999"}, truncate=True), "chat_invalid_response"),
        (Reply(body=chat_body(), headers={"Content-Length": str(len(chat_body()) + 1)}), "chat_invalid_response"),
        (Reply(body=json.dumps({"done": True}).encode()), "chat_invalid_response"),
        (Reply(body=json.dumps({"done": True, "message": {"content": 7}}).encode()), "chat_invalid_response"),
        (Reply(body=b"not json"), "chat_invalid_response"),
    ],
    ids=[
        "redirect-302",
        "redirect-307",
        "server-error",
        "refused",
        "disconnected",
        "connect-timeout",
        "bytes-until-deadline",
        "watchdog-abort",
        "oversize-declared",
        "oversize-undeclared",
        "not-done",
        "truncated",
        "declared-body-eof",
        "missing-message",
        "non-string-content",
        "not-json",
    ],
)
def test_chat_failures_have_no_reply(clock, reply, code):
    wire = Wire(clock, reply)
    result = model_for(wire, clock).chat(_request_body())
    assert result.status == "failed"
    assert result.reason_code == code
    assert result.reply_text is None
    assert wire.connections[0].closed


def test_oversized_chat_request_is_never_sent(clock):
    wire = Wire(clock)
    result = model_for(wire, clock).chat(b"x" * (32 * 1024 + 1))
    assert result.status == "stopped"
    assert result.reason_code == "request_too_large"
    assert wire.connections == []


# --- Attempts through the runner and store ----------------------------------


@pytest.fixture
def store(tmp_path, clock):
    with ReviewStore.create(tmp_path / "store", now=clock.now) as created:
        created.save_definition("docrev-v1", model_tag=MODEL_TAG, model_digest=MODEL_DIGEST)
    opened = ReviewStore.open(tmp_path / "store", now=clock.now)
    yield opened
    opened.close()


def _run(store, wire, clock, case="DC-03", confirm=True):
    return local.run_review(
        store,
        workflow_ref="docrev-v1",
        case_bytes=text_fixture(f"cases/{case}.txt"),
        model=model_for(wire, clock),
        confirm_local_runtime=confirm,
        clock=clock,
    )


def _reopen(tmp_path, clock):
    return ReviewStore.open_readonly(tmp_path / "store", now=clock.now)


def test_missing_operator_confirmation_makes_no_request_and_persists_a_stop(tmp_path, store, clock):
    wire = Wire(clock)
    outcome = _run(store, wire, clock, confirm=False)
    assert wire.connections == []
    assert outcome.status == "stopped"
    assert outcome.reason_code == "runtime_locality_unconfirmed"
    with _reopen(tmp_path, clock) as reopened:
        events = reopened.list_events(outcome.run_id)
        assert [(e.step, e.kind) for e in events] == [("attempt", "started"), ("rule", "result"), ("attempt", "finished")]
        assert events[0].record["runtime_confirmation"] == "absent"
        assert events[-1].status == "stopped"
        assert events[-1].reason_code == "runtime_locality_unconfirmed"
        assert events[1].record["finding"] == "match"


@pytest.mark.parametrize(
    "reply, code",
    [
        (Reply(body=b"{oops"), "tags_invalid_response"),
        (Reply(body=b"x" * (256 * 1024 + 1)), "tags_response_too_large"),
        (Reply(status=307, headers={"Location": "/api/tags2"}), "transport_refused"),
        (Reply(endless=True, chunk_size=64, seconds_per_chunk=1.0, declare_length=False), "tags_timeout"),
        (Reply(connect_error=ConnectionRefusedError()), "runtime_unavailable"),
        (Reply(body=tags_body(tag_entry(digest=OTHER_DIGEST))), "model_digest_mismatch"),
        (Reply(body=tags_body()), "model_not_installed"),
    ],
    ids=["malformed", "oversized", "redirected", "timed-out", "unavailable", "digest-mismatch", "not-installed"],
)
def test_preflight_stop_sends_no_chat_and_reopens_with_its_reason(tmp_path, store, clock, reply, code):
    wire = Wire(clock, reply)
    outcome = _run(store, wire, clock)
    assert outcome.status == "stopped"
    assert outcome.reason_code == code
    assert [(m, u) for m, u, _, _ in wire.requests] in ([], [("GET", "/api/tags")])
    with _reopen(tmp_path, clock) as reopened:
        events = reopened.list_events(outcome.run_id)
        kinds = [(e.step, e.kind) for e in events]
        assert kinds == [("attempt", "started"), ("rule", "result"), ("model", "preflight"), ("attempt", "finished")]
        assert events[2].status == "stopped"
        assert events[2].reason_code == code
        assert events[-1].reason_code == code
        assert events[0].record["runtime_confirmation"] == "confirmed"


def test_completed_live_attempt_records_settings_identity_and_exact_request(tmp_path, store, clock):
    reply_text = json.dumps(
        {"case_id": "DC-03", "finding": "match", "cited_lines": ["WP.L02", "WP.L03", "S1.L04"], "reason": "r"}
    )
    wire = Wire(clock, Reply(body=GOOD_TAGS), Reply(body=chat_body(reply_text)))
    outcome = _run(store, wire, clock)
    assert outcome.status == "returned_valid"
    assert [(m, u) for m, u, _, _ in wire.requests] == [("GET", "/api/tags"), ("POST", "/api/chat")]
    sent_body = wire.requests[1][2]
    with _reopen(tmp_path, clock) as reopened:
        events = reopened.list_events(outcome.run_id)
        assert [(e.step, e.kind) for e in events] == [
            ("attempt", "started"),
            ("rule", "result"),
            ("model", "preflight"),
            ("model", "request"),
            ("model", "result"),
            ("policy", "result"),
            ("attempt", "finished"),
        ]
        assert [e.seq for e in events] == list(range(1, 8))
        preflight, request, result, policy = events[2], events[3], events[4], events[5]
        assert preflight.record["observed_digest"] == MODEL_DIGEST
        assert preflight.record["expected_digest"] == MODEL_DIGEST
        assert request.record["settings_sent"]["options"]["seed"] == 7
        stored_request = reopened.read_artifact(request.artifacts["request"])
        assert stored_request.status == "verified"
        assert stored_request.data == sent_body
        stored_output = reopened.read_artifact(result.artifacts["output"])
        assert stored_output.data == reply_text.encode("utf-8")
        assert result.status == "returned_valid"
        assert result.record["measurements"]["model_generation_s"] == pytest.approx(0.642434)
        assert policy.record["finding"] == "match"
        assert policy.record["agreement"] == "agreed"
        assert policy.record["evidence_status"] == "unassessed"
        assert events[-1].status == "returned_valid"


def test_chat_failure_is_failed_without_parsed_finding_or_policy(tmp_path, store, clock):
    wire = Wire(clock, Reply(body=GOOD_TAGS), Reply(status=307, headers={"Location": "/x"}))
    outcome = _run(store, wire, clock)
    assert outcome.status == "failed"
    assert outcome.reason_code == "transport_refused"
    with _reopen(tmp_path, clock) as reopened:
        events = reopened.list_events(outcome.run_id)
        steps = [(e.step, e.kind) for e in events]
        assert ("model", "result") not in steps
        assert ("policy", "result") not in steps
        assert steps[-1] == ("attempt", "finished")
        assert events[-1].status == "failed"


def test_returned_invalid_reply_is_completed_and_policy_abstains(tmp_path, store, clock):
    wire = Wire(clock, Reply(body=GOOD_TAGS), Reply(body=chat_body("I think it matches.")))
    outcome = _run(store, wire, clock)
    assert outcome.status == "returned_invalid"
    assert outcome.reason_code == "model_output_not_json"
    with _reopen(tmp_path, clock) as reopened:
        events = {(e.step, e.kind): e for e in reopened.list_events(outcome.run_id)}
        assert events[("model", "result")].status == "returned_invalid"
        assert reopened.read_artifact(events[("model", "result")].artifacts["output"]).data == b"I think it matches."
        assert events[("policy", "result")].record["agreement"] == "model_invalid"
        assert events[("policy", "result")].record["finding"] == "insufficient evidence"


def test_request_over_the_definition_cap_stops_before_chat(tmp_path, clock, monkeypatch):
    monkeypatch.setattr(cr, "CHAT_REQUEST_LIMIT_BYTES", 1024)
    with ReviewStore.create(tmp_path / "store", now=clock.now) as store:
        store.save_definition("docrev-v1", model_tag=MODEL_TAG, model_digest=MODEL_DIGEST)
        wire = Wire(clock, Reply(body=GOOD_TAGS))
        outcome = _run(store, wire, clock)
    assert outcome.status == "stopped"
    assert outcome.reason_code == "request_too_large"
    assert [(m, u) for m, u, _, _ in wire.requests] == [("GET", "/api/tags")]


def test_malformed_case_stops_before_inference_and_is_recorded(tmp_path, store, clock):
    wire = Wire(clock)
    outcome = local.run_review(
        store,
        workflow_ref="docrev-v1",
        case_bytes=b"BEGIN CASE DC-09\nnot a case",
        model=model_for(wire, clock),
        confirm_local_runtime=True,
        clock=clock,
    )
    assert wire.connections == []
    assert (outcome.status, outcome.reason_code) == ("stopped", "case_envelope_invalid")
    with _reopen(tmp_path, clock) as reopened:
        events = reopened.list_events(outcome.run_id)
        assert [(e.step, e.kind) for e in events] == [("attempt", "started"), ("attempt", "finished")]


def test_unknown_workflow_reference_creates_no_run(tmp_path, store, clock):
    with pytest.raises(cr.ChecklistReviewError) as raised:
        local.run_review(
            store,
            workflow_ref="docrev-v9",
            case_bytes=text_fixture("cases/DC-03.txt"),
            model=model_for(Wire(clock), clock),
            confirm_local_runtime=True,
            clock=clock,
        )
    assert raised.value.reason_code == "definition_unknown"
    assert store.list_runs() == []


def test_recorded_reply_makes_no_request_and_marks_confirmation_inapplicable(tmp_path, store, clock):
    recorded = local.RecordedReply(
        (FIXTURES / "recorded" / "R01_DC-02_slm.txt").read_bytes().decode("utf-8"),
        model_tag=MODEL_TAG,
        model_digest=MODEL_DIGEST,
        label="recorded R01/DC-02",
        refers_to="R01/DC-02/slm/M1",
    )
    outcome = local.run_review(
        store,
        workflow_ref="docrev-v1",
        case_bytes=text_fixture("cases/DC-02.txt"),
        model=recorded,
        confirm_local_runtime=False,
        clock=clock,
    )
    assert outcome.status == "returned_valid"
    with _reopen(tmp_path, clock) as reopened:
        events = reopened.list_events(outcome.run_id)
        assert events[0].record["origin"] == "recorded"
        assert events[0].record["runtime_confirmation"] == "inapplicable"
        preflight = [e for e in events if e.kind == "preflight"][0]
        assert preflight.record["identity_source"] == "recorded"
