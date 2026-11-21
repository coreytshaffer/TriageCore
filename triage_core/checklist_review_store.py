"""Local review store for CR-138: SQLite metadata plus content-addressed
private artifacts.

The store is the sole history for this workflow. Definitions, runs, events,
and artifact links are append-only (schema triggers reject UPDATE and
DELETE). Every metadata record is screened by the persistent privacy
invariant; case text, model output, request bodies, frozen templates, and
notes live only in verified private artifacts under the explicit store root.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Optional, Sequence

from triage_core import checklist_review as cr
from triage_core.checklist_review import ChecklistReviewError
from triage_core.privacy_invariants import (
    PersistentPrivacyInvariantError,
    assert_persistent_privacy_safe,
)

DATABASE_NAME = "checklist_review.sqlite3"
ARTIFACT_DIR = "artifacts"
STORE_KIND = "triagecore.checklist_review"
SCHEMA_VERSION = "1"
STEPS = ("attempt", "rule", "model", "policy", "human")
RESULT_STEPS = ("rule", "model", "policy")
ORIGINS = ("live", "recorded")
RUNTIME_CONFIRMATIONS = ("confirmed", "absent", "inapplicable")
HUMAN_DISPOSITIONS = ("accepted", "revised")
LABEL_ASSESSMENTS = ("correct", "incorrect", "unknown")
EVIDENCE_ASSESSMENTS = ("supported", "unsupported", "unknown")
HUMAN_REASON_CODES = (
    "exact_entry_approved",
    "no_matching_document",
    "other_revision_only",
    "entry_field_missing",
    "decision_not_approved",
    "approval_qualified",
    "target_field_missing",
    "controlling_source_absent",
    "citation_unsupported",
    "other",
)
NOTE_LIMIT_BYTES = 8 * 1024
MAX_ACTIVE_SECONDS = 7 * 24 * 3600
ARTIFACT_STATUSES = ("verified", "evidence_missing", "evidence_digest_mismatch")
_SHORT_LABEL_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ./_:-")

_SCHEMA = """
BEGIN;
CREATE TABLE store_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE artifacts (
    artifact_id TEXT PRIMARY KEY,
    sha256 TEXT NOT NULL CHECK (length(sha256) = 64),
    size_bytes INTEGER NOT NULL CHECK (size_bytes >= 0),
    kind TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE definitions (
    ref TEXT PRIMARY KEY,
    definition_id TEXT NOT NULL UNIQUE,
    digest TEXT NOT NULL CHECK (length(digest) = 64),
    record_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE runs (
    run_id TEXT PRIMARY KEY,
    definition_ref TEXT NOT NULL REFERENCES definitions(ref),
    definition_digest TEXT NOT NULL,
    origin TEXT NOT NULL CHECK (origin IN ('live', 'recorded')),
    created_at TEXT NOT NULL
);
CREATE TABLE events (
    event_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id),
    seq INTEGER NOT NULL CHECK (seq >= 1),
    item_id TEXT,
    step TEXT NOT NULL CHECK (step IN ('attempt', 'rule', 'model', 'policy', 'human')),
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    reason_code TEXT,
    target_event_id TEXT REFERENCES events(event_id),
    supersedes_event_id TEXT REFERENCES events(event_id),
    recorded_at TEXT NOT NULL,
    record_json TEXT NOT NULL,
    UNIQUE (run_id, seq)
);
CREATE TABLE event_artifacts (
    event_id TEXT NOT NULL REFERENCES events(event_id),
    role TEXT NOT NULL,
    artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
    PRIMARY KEY (event_id, role)
);
CREATE TRIGGER events_sequence BEFORE INSERT ON events
WHEN NEW.seq != (SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE run_id = NEW.run_id)
BEGIN SELECT RAISE(ABORT, 'checklist_review_sequence'); END;
"""
_IMMUTABLE_TABLES = ("store_meta", "artifacts", "definitions", "runs", "events", "event_artifacts")


def _immutability_triggers() -> str:
    statements = []
    for table in _IMMUTABLE_TABLES:
        for operation in ("UPDATE", "DELETE"):
            statements.append(
                f"CREATE TRIGGER {table}_no_{operation.lower()} BEFORE {operation} ON {table} "
                "BEGIN SELECT RAISE(ABORT, 'checklist_review_immutable'); END;"
            )
    return "\n".join(statements)


class StoreError(ChecklistReviewError):
    """A store failure carrying only a closed reason code."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _stamp(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _parse_stamp(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _short_label(value: Optional[str], code: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or not 1 <= len(value) <= 80 or not set(value) <= _SHORT_LABEL_CHARS:
        raise StoreError(code)
    return value


@dataclass(frozen=True)
class ArtifactRef:
    artifact_id: str
    sha256: str
    size_bytes: int
    kind: str


@dataclass(frozen=True)
class ArtifactRead:
    ref: ArtifactRef
    status: str
    data: Optional[bytes] = field(default=None, repr=False)


@dataclass(frozen=True)
class Definition:
    ref: str
    definition_id: str
    digest: str
    record: Mapping[str, Any]
    created_at: str
    artifacts: Mapping[str, ArtifactRef]
    created: bool = False

    def artifact(self, name: str) -> ArtifactRef:
        return self.artifacts[name]


@dataclass(frozen=True)
class RunInfo:
    run_id: str
    definition_ref: str
    definition_digest: str
    origin: str
    created_at: str


@dataclass(frozen=True)
class Event:
    event_id: str
    run_id: str
    seq: int
    item_id: Optional[str]
    step: str
    kind: str
    status: str
    reason_code: Optional[str]
    target_event_id: Optional[str]
    supersedes_event_id: Optional[str]
    recorded_at: str
    record: Mapping[str, Any]
    artifacts: Mapping[str, ArtifactRef]


@dataclass(frozen=True)
class RunView:
    """Projection of a run over its ordered events."""

    run: RunInfo
    events: tuple[Event, ...]
    started: Event
    finished: Optional[Event]
    attempt_status: str
    attempt_reason: Optional[str]
    stage: Optional[str]
    stages: tuple[str, ...]
    rule: Optional[Event]
    preflight: Optional[Event]
    request: Optional[Event]
    model: Optional[Event]
    policy: Optional[Event]
    human: tuple[Event, ...]
    effective_human: Optional[Event]
    overall: Mapping[str, Any]


class ReviewStore:
    """Explicit private review store rooted at one local directory."""

    def __init__(
        self,
        root: Path,
        connection: sqlite3.Connection,
        *,
        readonly: bool,
        now: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self.root = root
        self.readonly = readonly
        self._connection = connection
        self._now = now or _utc_now

    # --- Opening ------------------------------------------------------------

    @classmethod
    def create(cls, root: os.PathLike | str, *, now: Optional[Callable[[], datetime]] = None) -> "ReviewStore":
        """Open an existing store, or initialize one in a new or empty directory."""
        path = Path(root)
        if path.exists() and not path.is_dir():
            raise StoreError("store_root_invalid")
        if (path / DATABASE_NAME).is_file():
            return cls.open(path, now=now)
        if path.exists():
            if any(path.iterdir()):
                raise StoreError("store_root_not_empty")
        else:
            try:
                path.mkdir()
            except FileNotFoundError:
                raise StoreError("store_parent_missing") from None
            except OSError:
                raise StoreError("store_create_failed") from None
        try:
            (path / ARTIFACT_DIR).mkdir(exist_ok=True)
            connection = sqlite3.connect(path / DATABASE_NAME, isolation_level=None)
        except (OSError, sqlite3.Error):
            raise StoreError("store_create_failed") from None
        try:
            connection.executescript(
                _SCHEMA
                + _immutability_triggers()
                + "\nINSERT INTO store_meta VALUES ('store_kind', '{}');".format(STORE_KIND)
                + "\nINSERT INTO store_meta VALUES ('schema_version', '{}');".format(SCHEMA_VERSION)
                + "\nCOMMIT;"
            )
        except sqlite3.Error:
            connection.close()
            raise StoreError("store_create_failed") from None
        store = cls(path, connection, readonly=False, now=now)
        store._configure()
        return store

    @classmethod
    def open(cls, root: os.PathLike | str, *, now: Optional[Callable[[], datetime]] = None) -> "ReviewStore":
        """Open an existing store for appending; fails closed if it is absent."""
        path = Path(root)
        database = path / DATABASE_NAME
        if not database.is_file():
            raise StoreError("store_missing")
        try:
            connection = sqlite3.connect(database, isolation_level=None)
        except sqlite3.Error:
            raise StoreError("store_unreadable") from None
        store = cls(path, connection, readonly=False, now=now)
        store._configure()
        return store

    @classmethod
    def open_readonly(cls, root: os.PathLike | str, *, now: Optional[Callable[[], datetime]] = None) -> "ReviewStore":
        """Open an existing store read-only: no initialization, no writes."""
        path = Path(root)
        database = path / DATABASE_NAME
        if not database.is_file():
            raise StoreError("store_missing")
        try:
            connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, isolation_level=None)
        except sqlite3.Error:
            raise StoreError("store_unreadable") from None
        store = cls(path, connection, readonly=True, now=now)
        store._configure()
        return store

    def _configure(self) -> None:
        try:
            self._connection.execute("PRAGMA foreign_keys = ON")
            if self.readonly:
                self._connection.execute("PRAGMA query_only = ON")
            else:
                self._connection.execute("PRAGMA synchronous = FULL")
            meta = dict(self._connection.execute("SELECT key, value FROM store_meta").fetchall())
        except sqlite3.Error:
            self.close()
            raise StoreError("store_unreadable") from None
        if meta.get("store_kind") != STORE_KIND or meta.get("schema_version") != SCHEMA_VERSION:
            self.close()
            raise StoreError("store_schema_unsupported")

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None  # type: ignore[assignment]

    def __enter__(self) -> "ReviewStore":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _require_writable(self) -> None:
        if self.readonly:
            raise StoreError("store_readonly")

    # --- Artifacts ----------------------------------------------------------

    def _artifact_path(self, digest: str) -> Path:
        return self.root / ARTIFACT_DIR / "sha256" / digest[:2] / digest

    def _write_staged(self, handle: Any, data: bytes) -> None:
        handle.write(data)

    @staticmethod
    def _verify_file(path: Path, digest: str, size: int) -> None:
        try:
            data = path.read_bytes()
        except OSError:
            raise StoreError("artifact_digest_mismatch") from None
        if len(data) != size or _sha256(data) != digest:
            raise StoreError("artifact_digest_mismatch")

    def _publish(self, data: bytes) -> str:
        """Stage, flush, verify, and atomically publish bytes at their digest
        path without overwriting it. Existing bytes are reused only after
        verification."""
        digest = _sha256(data)
        final = self._artifact_path(digest)
        if final.exists():
            self._verify_file(final, digest, len(data))
            return digest
        staging = self.root / ARTIFACT_DIR / "staging"
        temp = staging / f"{uuid.uuid4().hex}.part"
        try:
            staging.mkdir(parents=True, exist_ok=True)
            final.parent.mkdir(parents=True, exist_ok=True)
            with open(temp, "xb") as handle:
                self._write_staged(handle, data)
                handle.flush()
                os.fsync(handle.fileno())
            if _sha256(temp.read_bytes()) != digest:
                raise StoreError("artifact_write_failed")
            try:
                if os.name == "nt":
                    os.rename(temp, final)
                else:
                    os.link(temp, final)
            except FileExistsError:
                pass
        except OSError:
            raise StoreError("artifact_write_failed") from None
        finally:
            try:
                temp.unlink()
            except OSError:
                pass
        self._verify_file(final, digest, len(data))
        return digest

    def read_artifact(self, ref: ArtifactRef) -> ArtifactRead:
        path = self._artifact_path(ref.sha256)
        try:
            data = path.read_bytes()
        except FileNotFoundError:
            return ArtifactRead(ref, "evidence_missing")
        except OSError:
            return ArtifactRead(ref, "evidence_missing")
        if len(data) != ref.size_bytes or _sha256(data) != ref.sha256:
            return ArtifactRead(ref, "evidence_digest_mismatch")
        return ArtifactRead(ref, "verified", data)

    # --- Transactions -------------------------------------------------------

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connection
        try:
            connection.execute("BEGIN IMMEDIATE")
        except sqlite3.Error:
            raise StoreError("event_write_failed") from None
        try:
            yield connection
            connection.execute("COMMIT")
        except BaseException as exc:
            try:
                connection.execute("ROLLBACK")
            except sqlite3.Error:
                pass
            if isinstance(exc, sqlite3.Error):
                raise StoreError("event_write_failed") from None
            raise

    @staticmethod
    def _check_privacy(record: Mapping[str, Any]) -> None:
        try:
            assert_persistent_privacy_safe(record, artifact_name="checklist review metadata")
        except PersistentPrivacyInvariantError:
            raise StoreError("metadata_privacy_violation") from None

    @staticmethod
    def _encode_record(record: Mapping[str, Any]) -> str:
        try:
            return cr.canonical_json_bytes(record).decode("utf-8")
        except (TypeError, ValueError):
            raise StoreError("metadata_invalid") from None

    # --- Definitions --------------------------------------------------------

    def save_definition(self, ref: str, *, model_tag: str, model_digest: str) -> Definition:
        """Freeze the packaged templates and the model profile under ``ref``."""
        self._require_writable()
        cr.validate_workflow_ref(ref)
        system_bytes = cr.SYSTEM_TEXT.encode("utf-8")
        template_bytes = cr.USER_TEMPLATE.encode("utf-8")
        if _sha256(system_bytes) != cr.SYSTEM_TEXT_SHA256 or _sha256(template_bytes) != cr.USER_TEMPLATE_SHA256:
            raise StoreError("template_digest_mismatch")
        candidate = cr.build_definition(
            model_tag=model_tag,
            model_digest=model_digest,
            system_text_artifact_id="",
            user_template_artifact_id="",
        )
        if self._connection.execute("SELECT 1 FROM definitions WHERE ref = ?", (ref,)).fetchone():
            existing = self.load_definition(ref)
            if cr.definition_content_key(existing.record) == cr.definition_content_key(candidate):
                return replace(existing, created=False)
            raise StoreError("definition_conflict")

        created_at = _stamp(self._now())
        refs = {}
        for name, data, kind in (
            ("system_text", system_bytes, "system_text"),
            ("user_template", template_bytes, "user_template"),
        ):
            refs[name] = ArtifactRef(_new_id(), self._publish(data), len(data), kind)
        record = cr.build_definition(
            model_tag=model_tag,
            model_digest=model_digest,
            system_text_artifact_id=refs["system_text"].artifact_id,
            user_template_artifact_id=refs["user_template"].artifact_id,
        )
        self._check_privacy(record)
        digest = cr.definition_digest(record)
        definition_id = _new_id()
        with self._transaction() as connection:
            for item in refs.values():
                connection.execute(
                    "INSERT INTO artifacts VALUES (?, ?, ?, ?, ?)",
                    (item.artifact_id, item.sha256, item.size_bytes, item.kind, created_at),
                )
            connection.execute(
                "INSERT INTO definitions VALUES (?, ?, ?, ?, ?)",
                (ref, definition_id, digest, self._encode_record(record), created_at),
            )
        saved = self.load_definition(ref)
        if saved.digest != digest or saved.definition_id != definition_id:
            raise StoreError("definition_readback_mismatch")
        return replace(saved, created=True)

    def load_definition(self, ref: str) -> Definition:
        row = self._connection.execute(
            "SELECT ref, definition_id, digest, record_json, created_at FROM definitions WHERE ref = ?",
            (ref,),
        ).fetchone()
        if row is None:
            raise StoreError("definition_unknown")
        record = json.loads(row[3])
        if cr.definition_digest(record) != row[2]:
            raise StoreError("definition_digest_mismatch")
        artifacts = {}
        for name in ("system_text", "user_template"):
            entry = record.get(name) or {}
            artifact = self._artifact_row(entry.get("artifact_id"))
            if artifact is None or artifact.sha256 != entry.get("sha256"):
                raise StoreError("definition_digest_mismatch")
            artifacts[name] = artifact
        return Definition(row[0], row[1], row[2], record, row[4], artifacts)

    def verify_definition_templates(self, definition: Definition) -> tuple[str, str]:
        """Return the frozen template text after verifying both artifacts."""
        texts = []
        for name in ("system_text", "user_template"):
            read = self.read_artifact(definition.artifact(name))
            if read.status != "verified":
                raise StoreError(f"definition_{read.status}")
            texts.append(read.data.decode("utf-8"))
        return texts[0], texts[1]

    def _artifact_row(self, artifact_id: Any) -> Optional[ArtifactRef]:
        if not isinstance(artifact_id, str):
            return None
        row = self._connection.execute(
            "SELECT artifact_id, sha256, size_bytes, kind FROM artifacts WHERE artifact_id = ?",
            (artifact_id,),
        ).fetchone()
        return ArtifactRef(*row) if row else None

    # --- Runs and events ----------------------------------------------------

    def begin_run(
        self,
        definition: Definition,
        *,
        origin: str,
        origin_label: Optional[str],
        refers_to: Optional[str],
        runtime_confirmation: str,
        case_bytes: Optional[bytes],
        case_size: Optional[int] = None,
    ) -> Event:
        """Create a run and its ``attempt/started`` event before any network I/O."""
        self._require_writable()
        if origin not in ORIGINS:
            raise StoreError("run_origin_invalid")
        if runtime_confirmation not in RUNTIME_CONFIRMATIONS:
            raise StoreError("runtime_confirmation_invalid")
        origin_label = _short_label(origin_label, "run_origin_label_invalid")
        refers_to = _short_label(refers_to, "run_refers_to_invalid")
        size = len(case_bytes) if case_bytes is not None else case_size
        record = {
            "origin": origin,
            "origin_label": origin_label,
            "refers_to": refers_to,
            "definition_ref": definition.ref,
            "definition_id": definition.definition_id,
            "definition_digest": definition.digest,
            "runtime_confirmation": runtime_confirmation,
            "case": {
                "sha256": _sha256(case_bytes) if case_bytes is not None else None,
                "size_bytes": size if _is_number(size) else None,
                "stored": case_bytes is not None,
            },
        }
        run = RunInfo(_new_id(), definition.ref, definition.digest, origin, _stamp(self._now()))
        artifacts = {"case": (case_bytes, "case")} if case_bytes is not None else None
        return self._append(
            run.run_id,
            step="attempt",
            kind="started",
            status="started",
            record=record,
            new_artifacts=artifacts,
            new_run=run,
            recorded_at=run.created_at,
        )

    def append_event(
        self,
        run_id: str,
        *,
        step: str,
        kind: str,
        status: str,
        item_id: Optional[str] = None,
        reason_code: Optional[str] = None,
        record: Mapping[str, Any],
        new_artifacts: Optional[Mapping[str, tuple[bytes, str]]] = None,
        target_event_id: Optional[str] = None,
        supersedes_event_id: Optional[str] = None,
    ) -> Event:
        self._require_writable()
        self.get_run(run_id)
        return self._append(
            run_id,
            step=step,
            kind=kind,
            status=status,
            item_id=item_id,
            reason_code=reason_code,
            record=record,
            new_artifacts=new_artifacts,
            target_event_id=target_event_id,
            supersedes_event_id=supersedes_event_id,
        )

    def _insert_event_rows(self, connection: sqlite3.Connection, rows: Mapping[str, Any]) -> None:
        if rows.get("run") is not None:
            connection.execute("INSERT INTO runs VALUES (?, ?, ?, ?, ?)", rows["run"])
        for artifact in rows["artifacts"]:
            connection.execute("INSERT INTO artifacts VALUES (?, ?, ?, ?, ?)", artifact)
        connection.execute(
            "INSERT INTO events (event_id, run_id, seq, item_id, step, kind, status, reason_code,"
            " target_event_id, supersedes_event_id, recorded_at, record_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            rows["event"],
        )
        for link in rows["links"]:
            connection.execute("INSERT INTO event_artifacts VALUES (?, ?, ?)", link)

    def _append(
        self,
        run_id: str,
        *,
        step: str,
        kind: str,
        status: str,
        record: Mapping[str, Any],
        item_id: Optional[str] = None,
        reason_code: Optional[str] = None,
        new_artifacts: Optional[Mapping[str, tuple[bytes, str]]] = None,
        target_event_id: Optional[str] = None,
        supersedes_event_id: Optional[str] = None,
        new_run: Optional[RunInfo] = None,
        recorded_at: Optional[str] = None,
    ) -> Event:
        if step not in STEPS:
            raise StoreError("event_step_invalid")
        record = dict(record)
        self._check_privacy(record)
        self._check_privacy(
            {"kind": kind, "status": status, "item_id": item_id, "reason_code": reason_code}
        )
        record_json = self._encode_record(record)
        recorded_at = recorded_at or _stamp(self._now())

        published: dict[str, ArtifactRef] = {}
        for role, (data, artifact_kind) in (new_artifacts or {}).items():
            if not isinstance(data, (bytes, bytearray)):
                raise StoreError("artifact_invalid")
            published[role] = ArtifactRef(_new_id(), self._publish(bytes(data)), len(data), artifact_kind)

        event_id = _new_id()
        with self._transaction() as connection:
            seq = connection.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE run_id = ?", (run_id,)
            ).fetchone()[0]
            rows = {
                "run": None
                if new_run is None
                else (new_run.run_id, new_run.definition_ref, new_run.definition_digest, new_run.origin, new_run.created_at),
                "artifacts": [
                    (ref.artifact_id, ref.sha256, ref.size_bytes, ref.kind, recorded_at) for ref in published.values()
                ],
                "event": (
                    event_id,
                    run_id,
                    seq,
                    item_id,
                    step,
                    kind,
                    status,
                    reason_code,
                    target_event_id,
                    supersedes_event_id,
                    recorded_at,
                    record_json,
                ),
                "links": [(event_id, role, ref.artifact_id) for role, ref in published.items()],
            }
            self._insert_event_rows(connection, rows)

        event = self._event(event_id)
        if (
            event is None
            or event.run_id != run_id
            or event.seq != seq
            or (event.step, event.kind, event.status) != (step, kind, status)
            or dict(event.record) != json.loads(record_json)
            or {role: ref.sha256 for role, ref in event.artifacts.items()}
            != {role: ref.sha256 for role, ref in published.items()}
        ):
            raise StoreError("event_readback_mismatch")
        return event

    # --- Reads --------------------------------------------------------------

    _EVENT_COLUMNS = (
        "event_id, run_id, seq, item_id, step, kind, status, reason_code,"
        " target_event_id, supersedes_event_id, recorded_at, record_json"
    )

    def _event_from_row(self, row: Sequence[Any]) -> Event:
        links = self._connection.execute(
            "SELECT l.role, a.artifact_id, a.sha256, a.size_bytes, a.kind FROM event_artifacts l"
            " JOIN artifacts a ON a.artifact_id = l.artifact_id WHERE l.event_id = ? ORDER BY l.role",
            (row[0],),
        ).fetchall()
        artifacts = {link[0]: ArtifactRef(link[1], link[2], link[3], link[4]) for link in links}
        return Event(*row[:11], record=json.loads(row[11]), artifacts=artifacts)

    def _event(self, event_id: str) -> Optional[Event]:
        row = self._connection.execute(
            f"SELECT {self._EVENT_COLUMNS} FROM events WHERE event_id = ?", (event_id,)
        ).fetchone()
        return self._event_from_row(row) if row else None

    def get_run(self, run_id: str) -> RunInfo:
        row = self._connection.execute(
            "SELECT run_id, definition_ref, definition_digest, origin, created_at FROM runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise StoreError("run_unknown")
        return RunInfo(*row)

    def list_runs(self) -> list[RunInfo]:
        rows = self._connection.execute(
            "SELECT run_id, definition_ref, definition_digest, origin, created_at FROM runs ORDER BY created_at, rowid"
        ).fetchall()
        return [RunInfo(*row) for row in rows]

    def list_events(self, run_id: str) -> list[Event]:
        rows = self._connection.execute(
            f"SELECT {self._EVENT_COLUMNS} FROM events WHERE run_id = ? ORDER BY seq", (run_id,)
        ).fetchall()
        return [self._event_from_row(row) for row in rows]

    # --- Human assessment ---------------------------------------------------

    def record_human_assessment(
        self,
        run_id: str,
        *,
        item_id: str,
        target_event_id: str,
        finding: str,
        disposition: str,
        label_assessment: str,
        evidence_assessment: str,
        cited_labels: Sequence[str],
        reason_code: str,
        supersedes_event_id: Optional[str] = None,
        note_bytes: Optional[bytes] = None,
        active_seconds: Optional[float] = None,
    ) -> Event:
        """Validate and append one linked human event; nothing is appended on
        any validation failure."""
        self._require_writable()
        if finding not in cr.FINDINGS:
            raise StoreError("review_finding_invalid")
        if disposition not in HUMAN_DISPOSITIONS:
            raise StoreError("review_disposition_invalid")
        if label_assessment not in LABEL_ASSESSMENTS or evidence_assessment not in EVIDENCE_ASSESSMENTS:
            raise StoreError("review_assessment_invalid")
        if reason_code not in HUMAN_REASON_CODES:
            raise StoreError("review_reason_code_invalid")
        if active_seconds is not None and (
            not _is_number(active_seconds) or not 0 <= active_seconds <= MAX_ACTIVE_SECONDS
        ):
            raise StoreError("review_active_seconds_invalid")
        if note_bytes is not None:
            if not isinstance(note_bytes, (bytes, bytearray)) or len(note_bytes) > NOTE_LIMIT_BYTES:
                raise StoreError("review_note_invalid")
            try:
                bytes(note_bytes).decode("utf-8")
            except UnicodeDecodeError:
                raise StoreError("review_note_invalid") from None

        run = self.get_run(run_id)
        events = self.list_events(run_id)
        if not any(event.item_id == item_id for event in events):
            raise StoreError("review_item_unknown")
        by_id = {event.event_id: event for event in events}
        target = by_id.get(target_event_id)
        if (
            target is None
            or target.item_id != item_id
            or target.step not in RESULT_STEPS
            or target.kind != "result"
        ):
            raise StoreError("review_target_invalid")
        if supersedes_event_id is not None:
            earlier = by_id.get(supersedes_event_id)
            if earlier is None or earlier.step != "human" or earlier.item_id != item_id:
                raise StoreError("review_supersedes_invalid")
        target_finding = target.record.get("finding")
        if disposition == "accepted" and finding != target_finding:
            raise StoreError("review_disposition_inconsistent")

        started = events[0]
        case_ref = started.artifacts.get("case")
        case_read = self.read_artifact(case_ref) if case_ref is not None else None
        if case_read is None or case_read.status != "verified":
            raise StoreError("review_case_unavailable")
        try:
            case = cr.parse_case(case_read.data)
        except cr.CaseInputError:
            raise StoreError("review_case_unavailable") from None
        labels = list(dict.fromkeys(cited_labels))
        if any(case.line(label) is None for label in labels):
            raise StoreError("review_citation_unknown")

        if disposition == "accepted":
            revision_of = "none"
        elif finding == target_finding:
            revision_of = "explanation"
        else:
            revision_of = "finding"
        recorded_at = _stamp(self._now())
        to_decision = (_parse_stamp(recorded_at) - _parse_stamp(started.recorded_at)).total_seconds()
        record = {
            "finding": finding,
            "disposition": disposition,
            "revision_of": revision_of,
            "label_assessment": label_assessment,
            "evidence_assessment": evidence_assessment,
            "cited_labels": labels,
            "reason_code": reason_code,
            "record_kind": "demonstration" if run.origin == "recorded" else "operational",
            "target_step": target.step,
            "target_finding": target_finding,
            "note": {"stored": note_bytes is not None},
            "measurements": {
                "active_operator_s": float(active_seconds) if active_seconds is not None else "unknown",
                "end_to_end_to_decision_s": round(max(0.0, to_decision), 6),
                "model_generation_s": "inapplicable",
            },
        }
        artifacts = {"note": (bytes(note_bytes), "note")} if note_bytes is not None else None
        return self._append(
            run_id,
            step="human",
            kind="assessment",
            status="recorded",
            item_id=item_id,
            reason_code=reason_code,
            record=record,
            new_artifacts=artifacts,
            target_event_id=target.event_id,
            supersedes_event_id=supersedes_event_id,
            recorded_at=recorded_at,
        )

    # --- Projections and summaries ------------------------------------------

    def project_run(self, run_id: str) -> RunView:
        run = self.get_run(run_id)
        events = tuple(self.list_events(run_id))
        if not events or (events[0].step, events[0].kind) != ("attempt", "started"):
            raise StoreError("run_incomplete")

        def last(step: str, kind: str) -> Optional[Event]:
            matches = [event for event in events if (event.step, event.kind) == (step, kind)]
            return matches[-1] if matches else None

        finished = last("attempt", "finished")
        human = tuple(event for event in events if event.step == "human")
        superseded = {event.supersedes_event_id for event in human if event.supersedes_event_id}
        effective = next((event for event in reversed(human) if event.event_id not in superseded), None)
        policy = last("policy", "result")
        status = finished.status if finished else "incomplete"
        reason = finished.reason_code if finished else None
        stage = finished.record.get("stage") if finished else None
        stages = tuple(finished.record.get("stages_reached", ())) if finished else ("attempt",)

        if effective is not None:
            overall = {
                "source": "human",
                "finding": effective.record["finding"],
                "event_id": effective.event_id,
                "disposition": effective.record["disposition"],
                "revision_of": effective.record["revision_of"],
                "label_assessment": effective.record["label_assessment"],
                "evidence_assessment": effective.record["evidence_assessment"],
            }
        elif policy is not None:
            overall = {
                "source": "policy",
                "finding": policy.record["finding"],
                "event_id": policy.event_id,
                "agreement": policy.record["agreement"],
                "evidence_status": policy.record["evidence_status"],
                "review_available": True,
            }
        else:
            overall = {
                "source": "attempt",
                "finding": None,
                "status": status,
                "reason_code": reason,
                "stage": stage,
            }
        return RunView(
            run=run,
            events=events,
            started=events[0],
            finished=finished,
            attempt_status=status,
            attempt_reason=reason,
            stage=stage,
            stages=stages,
            rule=last("rule", "result"),
            preflight=last("model", "preflight"),
            request=last("model", "request"),
            model=last("model", "result"),
            policy=policy,
            human=human,
            effective_human=effective,
            overall=overall,
        )

    def summarize(self) -> dict[str, Any]:
        """Measurements over known observations, with coverage over eligible
        observations and the missing count."""
        samples: dict[str, list[Any]] = {
            "model_generation_s": [],
            "end_to_end_to_policy_s": [],
            "active_operator_s": [],
            "end_to_end_to_decision_s": [],
        }
        statuses: dict[str, int] = {}
        runs = self.list_runs()
        for run in runs:
            events = self.list_events(run.run_id)
            finished = [event for event in events if (event.step, event.kind) == ("attempt", "finished")]
            status = finished[-1].status if finished else "incomplete"
            statuses[status] = statuses.get(status, 0) + 1
            for event in events:
                measurements = event.record.get("measurements", {})
                if (event.step, event.kind) == ("model", "result"):
                    samples["model_generation_s"].append(measurements.get("model_generation_s"))
                elif (event.step, event.kind) == ("policy", "result"):
                    samples["end_to_end_to_policy_s"].append(measurements.get("end_to_end_to_policy_s"))
                elif event.step == "human":
                    samples["active_operator_s"].append(measurements.get("active_operator_s"))
                    samples["end_to_end_to_decision_s"].append(measurements.get("end_to_end_to_decision_s"))
        metrics = {}
        for name, values in samples.items():
            known = [float(value) for value in values if _is_number(value)]
            eligible = len(values)
            metrics[name] = {
                "eligible": eligible,
                "known": len(known),
                "missing": eligible - len(known),
                "coverage": round(len(known) / eligible, 4) if eligible else None,
                "sum": round(sum(known), 6) if known else None,
                "mean": round(sum(known) / len(known), 6) if known else None,
            }
        summary = {"runs": len(runs), "attempt_status_counts": statuses, "metrics": metrics}
        self._check_privacy(summary)
        return summary
