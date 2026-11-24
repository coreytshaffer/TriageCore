"""Local persistence for review decisions under a trusted workspace scope."""

from __future__ import annotations

import os
import sqlite3
import stat
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from triage_core.task_review_receipt import (
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

_SCHEMA_VERSION = 1
_SCHEMA = (
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


class ReviewStoreError(RuntimeError):
    """A privacy-safe store failure reason."""


@dataclass(frozen=True)
class CommittedReview:
    receipt: ReviewReceipt = field(repr=False)
    admitted_at: datetime


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

    def _check_scope(self, db: sqlite3.Connection, initialize: bool) -> None:
        version = db.execute("PRAGMA user_version").fetchone()[0]
        if version == 0 and initialize:
            if db.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone() is not None:
                raise ReviewStoreError("review_store_schema_unsupported")
            for statement in _SCHEMA:
                db.execute(statement)
            db.execute("INSERT INTO review_scope VALUES (1, ?)", (self._scope_id,))
            db.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
            return
        if version != _SCHEMA_VERSION:
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
        self, binding: EvidenceBinding, decision: str, reviewer_id: str
    ) -> ReviewRequest:
        """Issue and save a short-lived request for the local confirmation."""
        self._check_evidence_scope(binding)
        with self._transaction(write=True) as db:
            self._require_current_evidence(db, binding)
            self._policy().require_reviewer(reviewer_id)
            now = review_utc(self._clock())
            predecessor = self._head_id(db, binding.task_id)
            request = ReviewRequest.create(
                binding, decision, reviewer_id, predecessor, now
            )
            db.execute(
                "DELETE FROM review_challenge WHERE expires_at <= ?",
                (review_timestamp(now),),
            )
            db.execute(
                "INSERT INTO review_challenge VALUES (?, ?, ?)",
                (
                    request.event_id,
                    review_timestamp(request.expires_at),
                    request.canonical_bytes(),
                ),
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
        task_id, raw, admitted = row
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

    def admit(self, receipt: ReviewReceipt) -> CommittedReview:
        """Confirm once and advance the review head in the same transaction."""
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

            row = db.execute(
                "SELECT request FROM review_challenge WHERE event_id = ?",
                (request.event_id,),
            ).fetchone()
            if row is None:
                raise ReviewStoreError("review_challenge_missing")
            if row[0] != request.canonical_bytes():
                raise ReviewStoreError("review_request_mismatch")
            self._require_current_evidence(db, binding)
            if self._head_id(db, binding.task_id) != request.predecessor_id:
                raise ReviewStoreError("review_predecessor_changed")
            verify_review_receipt(receipt, self._policy(), self._clock())
            admitted_at = review_utc(self._clock())
            if not request.issued_at <= admitted_at < request.expires_at:
                raise ReviewProofError("challenge_not_current")
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
        return CommittedReview(receipt, admitted_at)

    def get_history(self, event_id: str) -> CommittedReview | None:
        """Read the local historical record. Current eligibility is a separate check."""
        validate_review_id(event_id)
        with self._transaction() as db:
            record = self._load_commit(db, event_id)
            if record is not None:
                self._check_evidence_scope(record.receipt.request.evidence)
            return record

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
