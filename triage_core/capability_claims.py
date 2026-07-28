"""Atomic execution-capability claim registry (CR-YK-002).

A standalone local SQLite registry that closes the concurrency gap left by
CR-YK-001. The ledger-only consumption sequence read capability state and then
appended an event, so two concurrent consumers could each observe an unused
capability before either append became visible.

Authority split (binding):

- SQLite is authoritative **only** for atomic claim ownership, current
  lifecycle state, claimant/execution-attempt binding, and terminal-transition
  enforcement. It does not prove authenticity, human approval, device
  identity, plan correctness, execution safety, or ledger integrity.
- The task ledger remains the durable evidence history. It is never the
  concurrency lock.

Lifecycle, and nothing else::

    issued -> claimed -> completed
                      \\-> failed

Terminal states are absorbing and no transition returns a capability to
``issued``. The conservative invariant is binding: **a crash burns the
authorization rather than risking duplicate execution**. Retrying requires
newly verified human authorization and a new capability.

This module performs no ledger access, no execution, no network or subprocess
activity, and imports no optional dependency. Ledger evidence is the caller's
responsibility (see ``triage_core.authz``), which is the sole authorized
compatibility boundary permitted to invoke this store.

Locking scope: local filesystems only. This makes no claim to correct locking
semantics over NFS, SMB, cloud-synced folders, or unusual FUSE mounts.
"""

from __future__ import annotations

import os
import re
import sqlite3
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# --- Schema -------------------------------------------------------------------

# v2 hardens the lifecycle the module claims SQLite owns: legal-transition
# whitelisting, per-state row shape, and immutable claim ownership. A table
# level CHECK cannot be retrofitted onto an existing table by
# ``CREATE TABLE IF NOT EXISTS``, so the version is bumped rather than left to
# silently accept a v1 file that lacks the new guarantees. A v1 database now
# fails closed as an unsupported version.
SCHEMA_VERSION = "triagecore.capability_claims.v2"
DEFAULT_DB_FILENAME = "capability_claims.sqlite3"
DEFAULT_BUSY_TIMEOUT_MS = 5000

STATE_ISSUED = "issued"
STATE_CLAIMED = "claimed"
STATE_COMPLETED = "completed"
STATE_FAILED = "failed"

_STATES = (STATE_ISSUED, STATE_CLAIMED, STATE_COMPLETED, STATE_FAILED)
_TERMINAL_STATES = (STATE_COMPLETED, STATE_FAILED)

# Immutable capability bindings; none may change after insertion.
IMMUTABLE_BINDING_FIELDS = (
    "capability_id",
    "task_id",
    "decision_id",
    "receipt_digest",
    "artifact_byte_digest",
    "plan_body_digest",
    "scope_digest",
    "approver_identity_id",
    "expires_at",
)

# --- Closed claim/terminal vocabularies ---------------------------------------
# House style: no free-text reason ever enters persistent evidence.

CLAIM_OK = "ok"
CLAIM_NOT_FOUND = "capability_not_found"
CLAIM_LEGACY_UNCLAIMABLE = "capability_legacy_unclaimable"
CLAIM_EXPIRED = "capability_expired"
CLAIM_ARTIFACT_DIGEST_MISMATCH = "artifact_digest_mismatch"
CLAIM_SCOPE_DIGEST_MISMATCH = "scope_digest_mismatch"
CLAIM_ALREADY_CLAIMED = "capability_already_claimed"
CLAIM_BINDING_MISMATCH = "capability_binding_mismatch"
CLAIM_STORE_BUSY = "capability_store_busy"
CLAIM_STORE_UNAVAILABLE = "capability_store_unavailable"
CLAIM_EVIDENCE_WRITE_FAILED = "claim_evidence_write_failed"

TERMINAL_OK = "ok"
TERMINAL_NOT_FOUND = "capability_not_found"
TERMINAL_NOT_CLAIMED = "capability_not_claimed"
TERMINAL_ALREADY_TERMINAL = "capability_already_terminal"
TERMINAL_CLAIMANT_MISMATCH = "claimant_mismatch"
TERMINAL_ATTEMPT_MISMATCH = "execution_attempt_mismatch"
TERMINAL_EVIDENCE_WRITE_FAILED = "terminal_evidence_write_failed"
# Operational store failures are not lifecycle facts. Collapsing them into
# TERMINAL_NOT_FOUND would report "this capability does not exist" when the
# truth is "lifecycle state is presently unknowable", inviting a caller to act
# on an absence that was never observed. These mirror the claim-path values.
# TERMINAL_NOT_FOUND is now reserved for a successful read that found no row.
TERMINAL_STORE_BUSY = "capability_store_busy"
TERMINAL_STORE_UNAVAILABLE = "capability_store_unavailable"

_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

_CREATE_SQL = (
    """
    CREATE TABLE IF NOT EXISTS schema_meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS capability_claims (
        capability_id        TEXT PRIMARY KEY,
        task_id              TEXT NOT NULL,
        decision_id          TEXT NOT NULL,
        receipt_digest       TEXT NOT NULL,
        artifact_byte_digest TEXT NOT NULL,
        plan_body_digest     TEXT NOT NULL,
        scope_digest         TEXT NOT NULL,
        approver_identity_id TEXT NOT NULL,
        expires_at           TEXT NOT NULL,
        state                TEXT NOT NULL
            CHECK (state IN ('issued', 'claimed', 'completed', 'failed')),
        claimed_at           TEXT,
        claimant_id          TEXT,
        execution_attempt_id TEXT,
        terminal_at          TEXT,
        terminal_outcome     TEXT
            CHECK (terminal_outcome IS NULL
                   OR terminal_outcome IN ('completed', 'failed')),
        -- Row shape must match the state. Without this a direct SQL writer
        -- could insert a 'claimed' row owned by nobody, or a terminal row that
        -- was never claimed, and every lifecycle field the module treats as
        -- authoritative would be unenforced.
        CHECK (
            (
                state = 'issued'
                AND claimed_at           IS NULL
                AND claimant_id          IS NULL
                AND execution_attempt_id IS NULL
                AND terminal_at          IS NULL
                AND terminal_outcome     IS NULL
            )
            OR (
                state = 'claimed'
                AND claimed_at           IS NOT NULL
                AND claimant_id          IS NOT NULL
                AND execution_attempt_id IS NOT NULL
                AND terminal_at          IS NULL
                AND terminal_outcome     IS NULL
            )
            OR (
                state IN ('completed', 'failed')
                AND claimed_at           IS NOT NULL
                AND claimant_id          IS NOT NULL
                AND execution_attempt_id IS NOT NULL
                AND terminal_at          IS NOT NULL
                AND terminal_outcome     = state
            )
        )
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_capability_execution_attempt
        ON capability_claims (execution_attempt_id)
        WHERE execution_attempt_id IS NOT NULL
    """,
    """
    CREATE TRIGGER IF NOT EXISTS capability_bindings_immutable
    BEFORE UPDATE ON capability_claims
    FOR EACH ROW
    WHEN OLD.capability_id        <> NEW.capability_id
      OR OLD.task_id              <> NEW.task_id
      OR OLD.decision_id          <> NEW.decision_id
      OR OLD.receipt_digest       <> NEW.receipt_digest
      OR OLD.artifact_byte_digest <> NEW.artifact_byte_digest
      OR OLD.plan_body_digest     <> NEW.plan_body_digest
      OR OLD.scope_digest         <> NEW.scope_digest
      OR OLD.approver_identity_id <> NEW.approver_identity_id
      OR OLD.expires_at           <> NEW.expires_at
    BEGIN
        SELECT RAISE(ABORT, 'immutable capability binding');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS capability_state_transition_legal
    BEFORE UPDATE ON capability_claims
    FOR EACH ROW
    WHEN NEW.state <> OLD.state
     AND NOT (
              (OLD.state = 'issued'  AND NEW.state = 'claimed')
           OR (OLD.state = 'claimed' AND NEW.state IN ('completed', 'failed'))
         )
    BEGIN
        SELECT RAISE(ABORT, 'illegal capability state transition');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS capability_claim_ownership_immutable
    BEFORE UPDATE ON capability_claims
    FOR EACH ROW
    WHEN OLD.state <> 'issued'
     AND (   IFNULL(OLD.claimed_at, '')           <> IFNULL(NEW.claimed_at, '')
          OR IFNULL(OLD.claimant_id, '')          <> IFNULL(NEW.claimant_id, '')
          OR IFNULL(OLD.execution_attempt_id, '')
             <> IFNULL(NEW.execution_attempt_id, ''))
    BEGIN
        SELECT RAISE(ABORT, 'claim ownership is immutable once claimed');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS capability_terminal_metadata_immutable
    BEFORE UPDATE ON capability_claims
    FOR EACH ROW
    WHEN OLD.state IN ('completed', 'failed')
     AND (   IFNULL(OLD.terminal_at, '')      <> IFNULL(NEW.terminal_at, '')
          OR IFNULL(OLD.terminal_outcome, '') <> IFNULL(NEW.terminal_outcome, ''))
    BEGIN
        SELECT RAISE(ABORT, 'terminal metadata is immutable');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS capability_claimed_rows_undeletable
    BEFORE DELETE ON capability_claims
    FOR EACH ROW
    WHEN OLD.state <> 'issued'
    BEGIN
        SELECT RAISE(ABORT, 'claimed and terminal rows are not deletable');
    END
    """,
)


class CapabilityStoreError(Exception):
    """Base error for the atomic claim registry."""


class CapabilitySchemaError(CapabilityStoreError):
    """Schema is absent, malformed, or an unsupported version."""


# --- Value types --------------------------------------------------------------

@dataclass(frozen=True)
class CapabilityBinding:
    """Immutable capability bindings materialized on first claim attempt.

    ``scope_digest`` may be the empty string because CR-YK-001 treats scope as
    optional. The empty value is bound literally and matched exactly; it is
    never a wildcard and is never synthesized into a digest.
    """

    capability_id: str
    task_id: str
    decision_id: str
    receipt_digest: str
    artifact_byte_digest: str
    plan_body_digest: str
    scope_digest: str
    approver_identity_id: str
    expires_at: str

    def __post_init__(self) -> None:
        for name in ("capability_id", "task_id", "decision_id",
                     "approver_identity_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise CapabilityStoreError(f"{name} must be a non-empty string")
        for name in ("receipt_digest", "artifact_byte_digest",
                     "plan_body_digest"):
            if not _DIGEST_PATTERN.fullmatch(getattr(self, name) or ""):
                raise CapabilityStoreError(
                    f"{name} must match sha256:<64 lowercase hex>"
                )
        if self.scope_digest and not _DIGEST_PATTERN.fullmatch(self.scope_digest):
            raise CapabilityStoreError(
                "scope_digest must be empty or sha256:<64 lowercase hex>"
            )
        object.__setattr__(self, "expires_at", canonical_utc(self.expires_at))

    def as_row_values(self) -> tuple:
        return tuple(getattr(self, name) for name in IMMUTABLE_BINDING_FIELDS)


@dataclass(frozen=True)
class ClaimResult:
    allowed: bool
    reason_code: str
    capability_id: str = ""
    state: str = ""


@dataclass(frozen=True)
class TerminalResult:
    applied: bool
    reason_code: str
    capability_id: str = ""
    state: str = ""


# --- Helpers ------------------------------------------------------------------

def canonical_utc(value: Any) -> str:
    """Normalize a timestamp to canonical UTC ISO-8601 text."""
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str) and value.strip():
        try:
            moment = datetime.fromisoformat(value.strip())
        except ValueError as exc:
            raise CapabilityStoreError(f"invalid ISO-8601 timestamp: {value!r}") from exc
    else:
        raise CapabilityStoreError("timestamp must be a datetime or ISO-8601 string")
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat()


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _restrict_file_permissions(path: str) -> None:
    """Best-effort owner-only permissions; a no-op where unsupported."""
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except (OSError, NotImplementedError):
        pass


def default_db_path(base_dir: str) -> str:
    """Default claim-database path beneath a ledger/authz base directory."""
    return os.path.join(base_dir, "authz", DEFAULT_DB_FILENAME)


def _is_busy(exc: sqlite3.Error) -> bool:
    text = str(exc).lower()
    return "locked" in text or "busy" in text


# --- Store --------------------------------------------------------------------

class CapabilityClaimStore:
    """Local SQLite registry enforcing atomic, irrevocable capability claims.

    Every operation opens its own connection so independent consumers never
    share connection state, and claim/terminal transactions use
    ``BEGIN IMMEDIATE`` so the write lock is taken before any decision is read.
    """

    def __init__(
        self,
        db_path: str,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    ) -> None:
        if busy_timeout_ms <= 0:
            raise CapabilityStoreError("busy_timeout_ms must be positive and bounded")
        self.db_path = db_path
        self.busy_timeout_ms = busy_timeout_ms
        self._integrity_verified = False

    # -- connection management -------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        parent = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(parent, exist_ok=True)
        pre_existing = os.path.exists(self.db_path)
        # isolation_level=None keeps sqlite3 out of implicit transaction
        # management so BEGIN IMMEDIATE means exactly what it says.
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.busy_timeout_ms / 1000.0,
            isolation_level=None,
        )
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout_ms)}")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA synchronous = FULL")
        if not pre_existing:
            _restrict_file_permissions(self.db_path)
        try:
            if pre_existing and not self._integrity_verified:
                self._verify_integrity(conn)
            self._ensure_schema(conn)
        except Exception:
            conn.close()
            raise
        return conn

    def _verify_integrity(self, conn: sqlite3.Connection) -> None:
        row = conn.execute("PRAGMA integrity_check").fetchone()
        if row is None or str(row[0]).lower() != "ok":
            raise CapabilitySchemaError("sqlite integrity check failed")
        self._integrity_verified = True

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        recorded = None
        has_meta = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'"
        ).fetchone()
        if has_meta:
            row = conn.execute(
                "SELECT value FROM schema_meta WHERE key = 'schema_version'"
            ).fetchone()
            recorded = row["value"] if row else None
            if recorded is not None and recorded != SCHEMA_VERSION:
                raise CapabilitySchemaError(
                    f"unsupported claim schema version: {recorded!r}"
                )
        for statement in _CREATE_SQL:
            conn.execute(statement)
        if recorded is None:
            conn.execute(
                "INSERT OR REPLACE INTO schema_meta (key, value) VALUES (?, ?)",
                ("schema_version", SCHEMA_VERSION),
            )

    # -- public API ------------------------------------------------------------

    def claim(
        self,
        binding: CapabilityBinding,
        *,
        claimant_id: str,
        execution_attempt_id: str,
        now: datetime,
    ) -> ClaimResult:
        """Atomically move ``issued -> claimed``; exactly one claimer wins.

        A denied attempt rolls back, including the row it may have inserted, so
        only committed claims persist. This is deliberate: if denied attempts
        committed their bindings, presenting bogus bindings first would
        materialize a row that permanently locks out the legitimate claimer
        with a binding mismatch.
        """
        if not str(claimant_id or "").strip():
            raise CapabilityStoreError("claimant_id must be a non-empty string")
        if not str(execution_attempt_id or "").strip():
            raise CapabilityStoreError(
                "execution_attempt_id must be a non-empty string"
            )
        moment = canonical_utc(now)
        conn = None
        try:
            conn = self._connect()
            conn.execute("BEGIN IMMEDIATE")
            placeholders = ", ".join("?" for _ in IMMUTABLE_BINDING_FIELDS)
            columns = ", ".join(IMMUTABLE_BINDING_FIELDS)
            conn.execute(
                f"INSERT OR IGNORE INTO capability_claims ({columns}, state) "
                f"VALUES ({placeholders}, ?)",
                (*binding.as_row_values(), STATE_ISSUED),
            )
            row = conn.execute(
                "SELECT * FROM capability_claims WHERE capability_id = ?",
                (binding.capability_id,),
            ).fetchone()
            if row is None:  # pragma: no cover - defensive
                conn.execute("ROLLBACK")
                return ClaimResult(False, CLAIM_STORE_UNAVAILABLE,
                                   binding.capability_id)

            # An existing row must carry exactly the same immutable bindings.
            for field in IMMUTABLE_BINDING_FIELDS:
                if row[field] != getattr(binding, field):
                    conn.execute("ROLLBACK")
                    return ClaimResult(False, CLAIM_BINDING_MISMATCH,
                                       binding.capability_id, row["state"])

            if row["state"] != STATE_ISSUED:
                conn.execute("ROLLBACK")
                return ClaimResult(False, CLAIM_ALREADY_CLAIMED,
                                   binding.capability_id, row["state"])

            # Expiry is evaluated inside the same immediate transaction. It is
            # enforced in Python rather than SQL because ISO-8601 text is not a
            # reliable total order across differing sub-second precision.
            if _parse_utc(moment) > _parse_utc(row["expires_at"]):
                conn.execute("ROLLBACK")
                return ClaimResult(False, CLAIM_EXPIRED,
                                   binding.capability_id, row["state"])

            cursor = conn.execute(
                "UPDATE capability_claims "
                "SET state = ?, claimed_at = ?, claimant_id = ?, "
                "    execution_attempt_id = ? "
                "WHERE capability_id = ? AND state = ? "
                "  AND artifact_byte_digest = ? AND scope_digest = ?",
                (
                    STATE_CLAIMED,
                    moment,
                    claimant_id,
                    execution_attempt_id,
                    binding.capability_id,
                    STATE_ISSUED,
                    binding.artifact_byte_digest,
                    binding.scope_digest,
                ),
            )
            if cursor.rowcount != 1:
                conn.execute("ROLLBACK")
                return ClaimResult(False, CLAIM_STORE_UNAVAILABLE,
                                   binding.capability_id)
            conn.execute("COMMIT")
            return ClaimResult(True, CLAIM_OK, binding.capability_id, STATE_CLAIMED)
        except sqlite3.IntegrityError:
            # Duplicate execution_attempt_id across capabilities is a binding
            # conflict, not a lifecycle outcome.
            self._safe_rollback(conn)
            return ClaimResult(False, CLAIM_BINDING_MISMATCH, binding.capability_id)
        except CapabilitySchemaError:
            self._safe_rollback(conn)
            return ClaimResult(False, CLAIM_STORE_UNAVAILABLE, binding.capability_id)
        except sqlite3.OperationalError as exc:
            self._safe_rollback(conn)
            code = CLAIM_STORE_BUSY if _is_busy(exc) else CLAIM_STORE_UNAVAILABLE
            return ClaimResult(False, code, binding.capability_id)
        except (sqlite3.Error, OSError):
            self._safe_rollback(conn)
            return ClaimResult(False, CLAIM_STORE_UNAVAILABLE, binding.capability_id)
        finally:
            if conn is not None:
                conn.close()

    def finalize(
        self,
        capability_id: str,
        *,
        claimant_id: str,
        execution_attempt_id: str,
        outcome: str,
        now: datetime,
    ) -> TerminalResult:
        """Move ``claimed -> completed|failed``; terminal states are absorbing.

        Failure reasons distinguish lifecycle facts from store conditions.
        ``TERMINAL_NOT_FOUND`` means the row was read and is genuinely absent;
        a busy or unusable store reports ``TERMINAL_STORE_BUSY`` or
        ``TERMINAL_STORE_UNAVAILABLE`` instead, because in those cases the
        lifecycle state was never observed at all.
        """
        if outcome not in _TERMINAL_STATES:
            raise CapabilityStoreError(
                f"terminal outcome must be one of {_TERMINAL_STATES}"
            )
        moment = canonical_utc(now)
        conn = None
        try:
            conn = self._connect()
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM capability_claims WHERE capability_id = ?",
                (capability_id,),
            ).fetchone()
            if row is None:
                conn.execute("ROLLBACK")
                return TerminalResult(False, TERMINAL_NOT_FOUND, capability_id)
            if row["state"] in _TERMINAL_STATES:
                conn.execute("ROLLBACK")
                return TerminalResult(False, TERMINAL_ALREADY_TERMINAL,
                                      capability_id, row["state"])
            if row["state"] != STATE_CLAIMED:
                conn.execute("ROLLBACK")
                return TerminalResult(False, TERMINAL_NOT_CLAIMED,
                                      capability_id, row["state"])
            if row["claimant_id"] != claimant_id:
                conn.execute("ROLLBACK")
                return TerminalResult(False, TERMINAL_CLAIMANT_MISMATCH,
                                      capability_id, row["state"])
            if row["execution_attempt_id"] != execution_attempt_id:
                conn.execute("ROLLBACK")
                return TerminalResult(False, TERMINAL_ATTEMPT_MISMATCH,
                                      capability_id, row["state"])

            cursor = conn.execute(
                "UPDATE capability_claims "
                "SET state = ?, terminal_at = ?, terminal_outcome = ? "
                "WHERE capability_id = ? AND state = ? "
                "  AND claimant_id = ? AND execution_attempt_id = ?",
                (
                    outcome,
                    moment,
                    outcome,
                    capability_id,
                    STATE_CLAIMED,
                    claimant_id,
                    execution_attempt_id,
                ),
            )
            if cursor.rowcount != 1:
                conn.execute("ROLLBACK")
                return TerminalResult(False, TERMINAL_NOT_CLAIMED, capability_id)
            conn.execute("COMMIT")
            return TerminalResult(True, TERMINAL_OK, capability_id, outcome)
        except CapabilitySchemaError:
            self._safe_rollback(conn)
            return TerminalResult(False, TERMINAL_STORE_UNAVAILABLE, capability_id)
        except sqlite3.OperationalError as exc:
            self._safe_rollback(conn)
            code = (
                TERMINAL_STORE_BUSY if _is_busy(exc) else TERMINAL_STORE_UNAVAILABLE
            )
            return TerminalResult(False, code, capability_id)
        except (sqlite3.Error, OSError):
            self._safe_rollback(conn)
            return TerminalResult(False, TERMINAL_STORE_UNAVAILABLE, capability_id)
        finally:
            if conn is not None:
                conn.close()

    def get_row(self, capability_id: str) -> Optional[Dict[str, Any]]:
        """Read-only lifecycle inspection; returns ``None`` when absent."""
        conn = None
        try:
            conn = self._connect()
            row = conn.execute(
                "SELECT * FROM capability_claims WHERE capability_id = ?",
                (capability_id,),
            ).fetchone()
            return dict(row) if row is not None else None
        finally:
            if conn is not None:
                conn.close()

    def check_integrity(self) -> bool:
        """Run ``PRAGMA integrity_check``; ``False`` when the file is unusable."""
        conn = None
        try:
            conn = self._connect()
            row = conn.execute("PRAGMA integrity_check").fetchone()
            return row is not None and str(row[0]).lower() == "ok"
        except (CapabilityStoreError, sqlite3.Error, OSError):
            return False
        finally:
            if conn is not None:
                conn.close()

    @staticmethod
    def _safe_rollback(conn: Optional[sqlite3.Connection]) -> None:
        if conn is None:
            return
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
