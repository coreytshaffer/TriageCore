"""Local persistence for review decisions under a trusted workspace scope."""

from __future__ import annotations

import os
import sqlite3
import stat
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from triage_core.task_review_receipt import (
    DECISIONS,
    EvidenceBinding,
    ReviewerPolicy,
    ReviewProofError,
    ReviewReceipt,
    ReviewRequest,
    review_timestamp,
    review_utc,
    validate_review_id,
    verify_review_receipt,
)

_SCHEMA_VERSION = 2
_SCHEMA_V1 = (
    """CREATE TABLE review_scope (
        singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
        scope_id TEXT NOT NULL
    )""",
    """CREATE TABLE review_evidence (
        task_id TEXT NOT NULL,
        revision TEXT NOT NULL,
        digest TEXT NOT NULL,
        active INTEGER NOT NULL CHECK (active IN (0, 1)),
        PRIMARY KEY (task_id, revision)
    )""",
    """CREATE UNIQUE INDEX review_one_current_evidence
        ON review_evidence(task_id) WHERE active = 1""",
    """CREATE TABLE review_challenge (
        event_id TEXT PRIMARY KEY,
        expires_at TEXT NOT NULL,
        request BLOB NOT NULL
    )""",
    """CREATE TABLE review_commit (
        event_id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        receipt BLOB NOT NULL,
        admitted_at TEXT NOT NULL,
        UNIQUE (task_id, event_id)
    )""",
    """CREATE TABLE review_head (
        task_id TEXT PRIMARY KEY,
        event_id TEXT NOT NULL,
        FOREIGN KEY (task_id, event_id) REFERENCES review_commit(task_id, event_id)
    )""",
)
_SCHEMA_V2_CHANGES = (
    """CREATE TABLE review_intent (
        intent_id TEXT PRIMARY KEY NOT NULL,
        request_id TEXT UNIQUE NOT NULL,
        task_id TEXT NOT NULL,
        decision TEXT NOT NULL,
        workload TEXT,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        cancelled INTEGER NOT NULL DEFAULT 0 CHECK (cancelled IN (0, 1)),
        committed_event_id TEXT UNIQUE,
        CHECK (cancelled = 0 OR committed_event_id IS NULL),
        FOREIGN KEY (task_id, committed_event_id) REFERENCES review_commit(task_id, event_id)
    )""",
    """ALTER TABLE review_challenge
        ADD COLUMN intent_id TEXT REFERENCES review_intent(intent_id)""",
    """CREATE INDEX review_pending_intent_by_task ON review_intent(task_id, created_at)
        WHERE cancelled = 0 AND committed_event_id IS NULL""",
)
_INTENT_TTL = timedelta(hours=24)
_INTENT_WORKLOADS = frozenset({"not_recorded", "low", "medium", "high"})
_INTENT_COLUMNS = (
    "intent_id, task_id, decision, workload, created_at, expires_at, cancelled, "
    "committed_event_id"
)


class ReviewStoreError(RuntimeError):
    """A privacy-safe store failure reason."""


@dataclass(frozen=True)
class CommittedReview:
    receipt: ReviewReceipt = field(repr=False)
    admitted_at: datetime


@dataclass(frozen=True)
class ReviewIntent:
    intent_id: str
    task_id: str
    decision: str
    workload: str | None
    created_at: datetime
    expires_at: datetime
    status: Literal["pending", "committed", "expired", "cancelled"] = "pending"
    committed_event_id: str | None = None


def _validate_intent_payload(task_id: str, decision: str, workload: str | None) -> None:
    validate_review_id(task_id)
    if not isinstance(decision, str) or decision not in DECISIONS:
        raise ValueError("unsupported review decision")
    if workload is not None and (
        not isinstance(workload, str) or workload not in _INTENT_WORKLOADS
    ):
        raise ValueError("unsupported review workload")


def _read_intent(row: tuple, now: datetime) -> ReviewIntent:
    intent_id, task_id, decision, workload, created, expires, cancelled, event_id = row
    try:
        validate_review_id(intent_id)
        _validate_intent_payload(task_id, decision, workload)
        created_at = datetime.fromisoformat(created)
        expires_at = datetime.fromisoformat(expires)
        if (
            review_timestamp(created_at) != created
            or review_timestamp(expires_at) != expires
            or expires_at != created_at + _INTENT_TTL
        ):
            raise ValueError("invalid review intent lifetime")
        if event_id is not None:
            validate_review_id(event_id)
    except (TypeError, ValueError, OverflowError):
        raise ReviewStoreError("review_store_unavailable") from None
    status: Literal["pending", "committed", "expired", "cancelled"] = "pending"
    if event_id is not None:
        status = "committed"
    elif cancelled:
        status = "cancelled"
    elif not created_at <= now < expires_at:
        status = "expired"
    return ReviewIntent(
        intent_id, task_id, decision, workload, created_at, expires_at, status, event_id
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_reparse(info: os.stat_result) -> bool:
    return bool(
        getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def _database_busy(error: sqlite3.Error) -> bool:
    code = getattr(error, "sqlite_errorcode", None)
    if code is not None:
        return code & 0xFF in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED)
    # Python 3.10 does not expose SQLite's numeric error codes.
    return isinstance(error, sqlite3.OperationalError) and str(error).partition(":")[
        0
    ] in {
        "database is locked",
        "database table is locked",
        "database schema is locked",
    }


class ReviewStore:
    """Use a private operator-provisioned directory, independent of the ledger.

    The local caller owns evidence registration, the policy loader and the
    clock. On Windows the caller must provision the directory with a private
    ACL. POSIX installations also check the directory owner and mode here.
    """

    def __init__(
        self,
        private_dir: Path,
        scope_id: str,
        load_policy: Callable[[], ReviewerPolicy],
        *,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        directory = Path(private_dir)
        if not directory.is_absolute():
            raise ValueError("review store directory must be absolute")
        validate_review_id(scope_id)
        self._path = directory / "review.sqlite3"
        self._scope_id = scope_id
        self._load_policy = load_policy
        self._clock = clock

    @property
    def path(self) -> Path:
        return self._path

    def initialize(self) -> None:
        """Explicitly provision a new store or check an existing store."""
        with self._transaction(write=True, initialize=True):
            pass

    def migrate(self) -> None:
        """Explicitly add intent support to an existing scoped v1 database."""
        with self._transaction(write=True) as db:
            if self._schema_version(db) == 1:
                self._add_intent_schema(db)

    def _check_path(self) -> None:
        directory = self.path.parent.lstat()
        if not stat.S_ISDIR(directory.st_mode) or _is_reparse(directory):
            raise ReviewStoreError("review_store_unavailable")
        if os.name == "posix" and (
            directory.st_uid != os.geteuid() or directory.st_mode & 0o077
        ):
            raise ReviewStoreError("review_store_unavailable")
        try:
            database = self.path.lstat()
        except FileNotFoundError:
            return
        if not stat.S_ISREG(database.st_mode) or _is_reparse(database):
            raise ReviewStoreError("review_store_unavailable")

    @staticmethod
    def _schema_version(db: sqlite3.Connection) -> int:
        return db.execute("PRAGMA user_version").fetchone()[0]

    @staticmethod
    def _add_intent_schema(db: sqlite3.Connection) -> None:
        for statement in _SCHEMA_V2_CHANGES:
            db.execute(statement)
        db.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")

    def _check_scope(self, db: sqlite3.Connection, initialize: bool) -> None:
        version = self._schema_version(db)
        if version == 0 and initialize:
            if db.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone() is not None:
                raise ReviewStoreError("review_store_schema_unsupported")
            for statement in _SCHEMA_V1:
                db.execute(statement)
            db.execute("INSERT INTO review_scope VALUES (1, ?)", (self._scope_id,))
            self._add_intent_schema(db)
            return
        if version not in (1, _SCHEMA_VERSION):
            raise ReviewStoreError("review_store_schema_unsupported")
        scope = db.execute(
            "SELECT scope_id FROM review_scope WHERE singleton = 1"
        ).fetchone()
        if scope is None or scope[0] != self._scope_id:
            raise ReviewStoreError("review_scope_mismatch")

    @contextmanager
    def _transaction(
        self,
        *,
        write: bool = False,
        initialize: bool = False,
    ) -> Iterator[sqlite3.Connection]:
        try:
            self._check_path()
            mode = "rwc" if initialize else "rw" if write else "ro"
            with closing(
                sqlite3.connect(
                    f"{self.path.as_uri()}?mode={mode}", uri=True, timeout=0.5
                )
            ) as db:
                db.execute("PRAGMA foreign_keys = ON")
                if write:
                    db.execute("PRAGMA synchronous = FULL")
                with db:
                    db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
                    self._check_scope(db, initialize)
                    yield db
        except sqlite3.Error as exc:
            if _database_busy(exc):
                raise ReviewStoreError("review_store_busy") from None
            raise ReviewStoreError("review_store_unavailable") from None
        except OSError:
            raise ReviewStoreError("review_store_unavailable") from None

    def _policy(self) -> ReviewerPolicy:
        try:
            policy = self._load_policy()
        except (OSError, RuntimeError, ValueError, TypeError, KeyError):
            raise ReviewProofError("review_policy_unavailable") from None
        if not isinstance(policy, ReviewerPolicy):
            raise ReviewProofError("review_policy_unavailable")
        if policy.scope_id != self._scope_id:
            raise ReviewProofError("review_scope_mismatch")
        return policy

    def _require_intent_schema(self, db: sqlite3.Connection) -> None:
        if self._schema_version(db) < 2:
            raise ReviewStoreError("review_store_migration_required")

    def request_intent(
        self, task_id: str, request_id: str, decision: str, workload: str | None = None
    ) -> ReviewIntent:
        """Record a mobile intent, or return the original state for an exact retry."""
        validate_review_id(request_id)
        _validate_intent_payload(task_id, decision, workload)
        with self._transaction(write=True) as db:
            self._require_intent_schema(db)
            now = review_utc(self._clock())
            row = db.execute(
                f"SELECT {_INTENT_COLUMNS} FROM review_intent WHERE request_id = ?",
                (request_id,),
            ).fetchone()
            if row is not None:
                current = _read_intent(row, now)
                if (current.task_id, current.decision, current.workload) != (
                    task_id,
                    decision,
                    workload,
                ):
                    raise ReviewStoreError("review_intent_conflict")
                return current
            intent = ReviewIntent(
                str(uuid4()), task_id, decision, workload, now, now + _INTENT_TTL
            )
            db.execute(
                """INSERT INTO review_intent
                    (intent_id, request_id, task_id, decision, workload, created_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    intent.intent_id,
                    request_id,
                    task_id,
                    decision,
                    workload,
                    review_timestamp(intent.created_at),
                    review_timestamp(intent.expires_at),
                ),
            )
        return intent

    @staticmethod
    def _find_intent(
        db: sqlite3.Connection, intent_id: str, now: datetime
    ) -> ReviewIntent | None:
        row = db.execute(
            f"SELECT {_INTENT_COLUMNS} FROM review_intent WHERE intent_id = ?",
            (intent_id,),
        ).fetchone()
        return _read_intent(row, now) if row is not None else None

    def get_intent(self, intent_id: str) -> ReviewIntent | None:
        validate_review_id(intent_id)
        with self._transaction() as db:
            self._require_intent_schema(db)
            return self._find_intent(db, intent_id, review_utc(self._clock()))

    def list_pending_intents(self, task_id: str) -> tuple[ReviewIntent, ...]:
        validate_review_id(task_id)
        with self._transaction() as db:
            self._require_intent_schema(db)
            now = review_utc(self._clock())
            timestamp = review_timestamp(now)
            rows = db.execute(
                f"""SELECT {_INTENT_COLUMNS} FROM review_intent
                    WHERE task_id = ? AND cancelled = 0 AND committed_event_id IS NULL
                      AND created_at <= ? AND expires_at > ?
                    ORDER BY created_at, rowid""",
                (task_id, timestamp, timestamp),
            )
            return tuple(_read_intent(row, now) for row in rows)

    def cancel_intent(self, intent_id: str) -> ReviewIntent:
        """Cancel a pending intent and keep the underlying review actionable."""
        validate_review_id(intent_id)
        with self._transaction(write=True) as db:
            self._require_intent_schema(db)
            intent = self._find_intent(db, intent_id, review_utc(self._clock()))
            if intent is None:
                raise ReviewStoreError("review_intent_missing")
            if intent.status == "pending":
                db.execute(
                    "UPDATE review_intent SET cancelled = 1 WHERE intent_id = ?",
                    (intent_id,),
                )
                return replace(intent, status="cancelled")
            return intent

    def _require_pending_intent(
        self,
        db: sqlite3.Connection,
        intent_id: str,
        task_id: str,
        decision: str,
        now: datetime,
    ) -> ReviewIntent:
        intent = self._find_intent(db, intent_id, now)
        if intent is None:
            raise ReviewStoreError("review_intent_missing")
        if (intent.task_id, intent.decision) != (task_id, decision):
            raise ReviewStoreError("review_intent_mismatch")
        if intent.status != "pending":
            raise ReviewStoreError(f"review_intent_{intent.status}")
        return intent

    def _check_evidence_scope(self, binding: EvidenceBinding) -> None:
        if binding.scope_id != self._scope_id:
            raise ReviewStoreError("review_scope_mismatch")

    @staticmethod
    def _current_evidence(
        db: sqlite3.Connection, task_id: str
    ) -> tuple[str, str] | None:
        return db.execute(
            "SELECT revision, digest FROM review_evidence WHERE task_id = ? AND active = 1",
            (task_id,),
        ).fetchone()

    def current_evidence(self, task_id: str) -> EvidenceBinding | None:
        validate_review_id(task_id)
        with self._transaction() as db:
            row = self._current_evidence(db, task_id)
            if row is None:
                return None
            try:
                return EvidenceBinding(self._scope_id, task_id, *row)
            except (TypeError, ValueError):
                raise ReviewStoreError("review_store_unavailable") from None

    def register_evidence(
        self, binding: EvidenceBinding, *, expected_revision: str | None
    ) -> None:
        """Register the evidence revision selected by the trusted local preparer."""
        self._check_evidence_scope(binding)
        with self._transaction(write=True) as db:
            current = self._current_evidence(db, binding.task_id)
            if current == (binding.revision, binding.digest):
                return
            if (current[0] if current else None) != expected_revision:
                raise ReviewStoreError("review_evidence_changed")
            if db.execute(
                "SELECT 1 FROM review_evidence WHERE task_id = ? AND revision = ?",
                (binding.task_id, binding.revision),
            ).fetchone():
                raise ReviewStoreError("review_evidence_revision_reused")
            db.execute(
                "UPDATE review_evidence SET active = 0 WHERE task_id = ? AND active = 1",
                (binding.task_id,),
            )
            db.execute(
                "INSERT INTO review_evidence VALUES (?, ?, ?, 1)",
                (binding.task_id, binding.revision, binding.digest),
            )

    @staticmethod
    def _head_id(db: sqlite3.Connection, task_id: str) -> str | None:
        row = db.execute(
            "SELECT event_id FROM review_head WHERE task_id = ?", (task_id,)
        ).fetchone()
        return row[0] if row else None

    def _require_current_evidence(
        self, db: sqlite3.Connection, binding: EvidenceBinding
    ) -> None:
        if self._current_evidence(db, binding.task_id) != (
            binding.revision,
            binding.digest,
        ):
            raise ReviewStoreError("review_evidence_changed")

    def prepare(
        self,
        binding: EvidenceBinding,
        decision: str,
        reviewer_id: str,
        *,
        intent_id: str | None = None,
    ) -> ReviewRequest:
        """Issue and save a short-lived request for the local confirmation."""
        self._check_evidence_scope(binding)
        with self._transaction(write=True) as db:
            self._require_current_evidence(db, binding)
            self._policy().require_reviewer(reviewer_id)
            now = review_utc(self._clock())
            if intent_id is not None:
                validate_review_id(intent_id)
                self._require_intent_schema(db)
                self._require_pending_intent(
                    db, intent_id, binding.task_id, decision, now
                )
            predecessor = self._head_id(db, binding.task_id)
            request = ReviewRequest.create(
                binding, decision, reviewer_id, predecessor, now
            )
            db.execute(
                "DELETE FROM review_challenge WHERE expires_at <= ?",
                (review_timestamp(now),),
            )
            values = (
                request.event_id,
                review_timestamp(request.expires_at),
                request.canonical_bytes(),
            )
            if intent_id is None:
                db.execute(
                    """INSERT INTO review_challenge (event_id, expires_at, request)
                        VALUES (?, ?, ?)""",
                    values,
                )
            else:
                db.execute(
                    """INSERT INTO review_challenge (event_id, expires_at, request, intent_id)
                        VALUES (?, ?, ?, ?)""",
                    (*values, intent_id),
                )
        return request

    @staticmethod
    def _load_commit(db: sqlite3.Connection, event_id: str) -> CommittedReview | None:
        row = db.execute(
            "SELECT task_id, receipt, admitted_at FROM review_commit WHERE event_id = ?",
            (event_id,),
        ).fetchone()
        if row is None:
            return None
        return ReviewStore._read_commit(event_id, *row)

    @staticmethod
    def _read_commit(
        event_id: str, task_id: str, raw: bytes, admitted: str
    ) -> CommittedReview:
        try:
            receipt = ReviewReceipt.from_bytes(raw)
            request = receipt.request
            timestamp = datetime.fromisoformat(admitted)
            if (
                request.event_id != event_id
                or request.evidence.task_id != task_id
                or review_timestamp(timestamp) != admitted
                or not request.issued_at <= timestamp < request.expires_at
            ):
                raise ValueError("invalid review commit")
        except (AttributeError, TypeError, ValueError):
            raise ReviewStoreError("review_store_unavailable") from None
        return CommittedReview(receipt, timestamp)

    def admit(
        self,
        receipt: ReviewReceipt,
        *,
        check_current: Callable[[], None] | None = None,
    ) -> CommittedReview:
        """Check the source before a new commit, within the review write transaction."""
        request = receipt.request
        binding = request.evidence
        self._check_evidence_scope(binding)
        with self._transaction(write=True) as db:
            existing = self._load_commit(db, request.event_id)
            if existing is not None:
                if existing.receipt != receipt:
                    raise ReviewStoreError("review_event_conflict")
                verify_review_receipt(
                    existing.receipt, self._policy(), existing.admitted_at
                )
                return existing

            query = (
                "SELECT request, intent_id FROM review_challenge WHERE event_id = ?"
                if self._schema_version(db) >= 2
                else "SELECT request, NULL FROM review_challenge WHERE event_id = ?"
            )
            row = db.execute(query, (request.event_id,)).fetchone()
            if row is None:
                raise ReviewStoreError("review_challenge_missing")
            raw, intent_id = row
            if raw != request.canonical_bytes():
                raise ReviewStoreError("review_request_mismatch")
            now = review_utc(self._clock())
            intent = None
            if intent_id is not None:
                intent = self._require_pending_intent(
                    db, intent_id, binding.task_id, request.decision, now
                )
            self._require_current_evidence(db, binding)
            if self._head_id(db, binding.task_id) != request.predecessor_id:
                raise ReviewStoreError("review_predecessor_changed")
            verify_review_receipt(receipt, self._policy(), now)
            if check_current is not None:
                check_current()
            admitted_at = review_utc(self._clock())
            if not request.issued_at <= admitted_at < request.expires_at:
                raise ReviewProofError("challenge_not_current")
            if (
                intent is not None
                and not intent.created_at <= admitted_at < intent.expires_at
            ):
                raise ReviewStoreError("review_intent_expired")
            db.execute(
                "DELETE FROM review_challenge WHERE event_id = ?", (request.event_id,)
            )
            db.execute(
                "INSERT INTO review_commit VALUES (?, ?, ?, ?)",
                (
                    request.event_id,
                    binding.task_id,
                    receipt.canonical_bytes(),
                    review_timestamp(admitted_at),
                ),
            )
            db.execute(
                """INSERT INTO review_head VALUES (?, ?)
                ON CONFLICT(task_id) DO UPDATE SET event_id = excluded.event_id""",
                (binding.task_id, request.event_id),
            )
            if intent is not None:
                result = db.execute(
                    """UPDATE review_intent SET committed_event_id = ?
                        WHERE intent_id = ? AND cancelled = 0 AND committed_event_id IS NULL""",
                    (request.event_id, intent.intent_id),
                )
                if result.rowcount != 1:
                    raise ReviewStoreError("review_store_unavailable")
        return CommittedReview(receipt, admitted_at)

    def get_history(self, event_id: str) -> CommittedReview | None:
        """Read the local historical record. Current eligibility is a separate check."""
        validate_review_id(event_id)
        with self._transaction() as db:
            record = self._load_commit(db, event_id)
            if record is not None:
                self._check_evidence_scope(record.receipt.request.evidence)
            return record

    def list_history(self, task_id: str) -> tuple[CommittedReview, ...]:
        """Read the task's historical receipts in local admission order."""
        validate_review_id(task_id)
        with self._transaction() as db:
            rows = db.execute(
                """SELECT event_id, receipt, admitted_at FROM review_commit
                    WHERE task_id = ? ORDER BY admitted_at, rowid""",
                (task_id,),
            )
            records = []
            for event_id, raw, admitted_at in rows:
                record = self._read_commit(event_id, task_id, raw, admitted_at)
                self._check_evidence_scope(record.receipt.request.evidence)
                records.append(record)
            return tuple(records)

    def get_current(self, task_id: str) -> CommittedReview | None:
        """Return the verified decision for the current evidence, if any."""
        validate_review_id(task_id)
        with self._transaction() as db:
            policy = self._policy()
            head = self._head_id(db, task_id)
            if head is None:
                return None
            record = self._load_commit(db, head)
            if record is None or record.receipt.request.evidence.task_id != task_id:
                raise ReviewStoreError("review_store_unavailable")
            binding = record.receipt.request.evidence
            self._check_evidence_scope(binding)
            if self._current_evidence(db, task_id) != (
                binding.revision,
                binding.digest,
            ):
                return None
            verify_review_receipt(record.receipt, policy, record.admitted_at)
            return record
