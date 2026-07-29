"""Atomic client-request reservation (CR-OC-001B).

A local SQLite store binding one client request to at most one capability:

    client_request_id -> request_digest -> broker_connection_id -> capability_id

CR-OC-001A produces deterministic, integrity-bound representations and digests
but reserves nothing: ``classify_request_replay`` compares two bindings it is
*handed* and cannot discover that a prior one exists. This module makes that
discovery atomic and durable.

Lifecycle, and nothing else::

    reserved -> issuing -> authorized
    reserved -> denied

``issuing -> denied`` is illegal: once issuance has begun the decision is made.
Reopening, reassignment, expiry-based release, deletion, and backward
transitions are all forbidden. **Claim and execution lifecycle remain
exclusively owned by CR-YK-002**; nothing here mirrors them.

Ownership is a bearer credential. The raw ``reservation_attempt_token`` is
returned exactly once, to the winner of the insert, and never persisted. Only
``sha256(token)`` is stored, because a raw token at rest would hand the right to
bind or deny any live row to anyone who can read the database. Every transition
out of ``reserved`` or ``issuing`` hashes the supplied raw token and performs one
atomic conditional write.

The one-shot ``reserved -> issuing`` gate exists because **a one-to-one
constraint on binding does not bound how many capabilities exist**. Two holders
of the same valid token could otherwise each call ``issue_capability`` and only
then race to bind; uniqueness would permit one binding while the second
capability already sat in the ledger.

Scope boundary, stated because it is narrow: the mediated claim entry point
here refuses to delegate for an unauthorized reservation. It **does not alter or
constrain direct callers of** ``triage_core.authz.claim_capability``, and
nothing in this module makes an issued-but-unbound capability unclaimable in
general.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from triage_core.privacy_invariants import assert_persistent_privacy_safe
from triage_core.mediated_effect import (
    AuthorizedContentEffect,
    MediatedClientRequest,
    MediatedContractError,
    MediatedPlanLinkage,
    assert_linkage_binds,
    capability_binding_fields,
)

# --- Schema -------------------------------------------------------------------

SCHEMA_VERSION = "triagecore.request_reservation.v1"
DEFAULT_DB_FILENAME = "request_reservations.sqlite3"
DEFAULT_BUSY_TIMEOUT_MS = 5000

STATE_RESERVED = "reserved"
STATE_ISSUING = "issuing"
STATE_AUTHORIZED = "authorized"
STATE_DENIED = "denied"

_STATES = (STATE_RESERVED, STATE_ISSUING, STATE_AUTHORIZED, STATE_DENIED)

# Identity and binding fields, immutable after insert.
IMMUTABLE_FIELDS = (
    "client_request_id",
    "reservation_attempt_digest",
    "request_digest",
    "broker_connection_id",
    "task_id",
)

# --- Closed reason vocabulary -------------------------------------------------
# Exactly the merged contract's vocabulary. No synonyms, no borrowed codes, no
# free-text reason ever enters persistent state.

RESERVE_OK = "ok"
RESERVATION_NOT_FOUND = "reservation_not_found"
REQUEST_ID_REUSE_MISMATCH = "request_id_reuse_mismatch"
RESERVATION_UNBOUND = "reservation_unbound"
RESERVATION_ATTEMPT_MISMATCH = "reservation_attempt_mismatch"
RESERVATION_ALREADY_ISSUING = "reservation_already_issuing"
RESERVATION_ISSUANCE_NOT_BEGUN = "reservation_issuance_not_begun"
RESERVATION_ALREADY_BOUND = "reservation_already_bound"
CAPABILITY_ALREADY_RESERVED = "capability_already_reserved"
RESERVATION_BINDING_MISMATCH = "reservation_binding_mismatch"
RESERVATION_DENIED = "reservation_denied"
RESERVATION_STORE_BUSY = "reservation_store_busy"
RESERVATION_STORE_UNAVAILABLE = "reservation_store_unavailable"

REASON_CODES = frozenset(
    {
        RESERVE_OK,
        RESERVATION_NOT_FOUND,
        REQUEST_ID_REUSE_MISMATCH,
        RESERVATION_UNBOUND,
        RESERVATION_ATTEMPT_MISMATCH,
        RESERVATION_ALREADY_ISSUING,
        RESERVATION_ISSUANCE_NOT_BEGUN,
        RESERVATION_ALREADY_BOUND,
        CAPABILITY_ALREADY_RESERVED,
        RESERVATION_BINDING_MISMATCH,
        RESERVATION_DENIED,
        RESERVATION_STORE_BUSY,
        RESERVATION_STORE_UNAVAILABLE,
    }
)

_DIGEST_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
_TOKEN_BYTES = 32  # 256 bits, well above the 122-bit floor

_CREATE_SQL = (
    """
    CREATE TABLE IF NOT EXISTS schema_meta (
        key   TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS request_reservations (
        client_request_id          TEXT PRIMARY KEY,
        reservation_attempt_digest TEXT NOT NULL,
        request_digest             TEXT NOT NULL,
        broker_connection_id       TEXT NOT NULL,
        task_id                    TEXT NOT NULL,
        capability_id              TEXT,
        state                      TEXT NOT NULL
            CHECK (state IN ('reserved', 'issuing', 'authorized', 'denied')),
        reserved_at                TEXT NOT NULL,
        issuing_at                 TEXT,
        bound_at                   TEXT,
        denied_at                  TEXT,
        -- Row shape is bound to state. Without this a direct SQL writer could
        -- record an authorized row with no capability, or a denied row that had
        -- already begun issuing, and every field the module treats as
        -- authoritative would be unenforced.
        CHECK (
            (
                state = 'reserved'
                AND capability_id IS NULL
                AND issuing_at    IS NULL
                AND bound_at      IS NULL
                AND denied_at     IS NULL
            )
            OR (
                state = 'issuing'
                AND capability_id IS NULL
                AND issuing_at    IS NOT NULL
                AND bound_at      IS NULL
                AND denied_at     IS NULL
            )
            OR (
                state = 'authorized'
                AND capability_id IS NOT NULL
                AND issuing_at    IS NOT NULL
                AND bound_at      IS NOT NULL
                AND denied_at     IS NULL
            )
            OR (
                state = 'denied'
                AND capability_id IS NULL
                AND issuing_at    IS NULL
                AND bound_at      IS NULL
                AND denied_at     IS NOT NULL
            )
        )
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS idx_reservation_capability
        ON request_reservations (capability_id)
        WHERE capability_id IS NOT NULL
    """,
    """
    CREATE TRIGGER IF NOT EXISTS reservation_identity_immutable
    BEFORE UPDATE ON request_reservations
    FOR EACH ROW
    WHEN OLD.client_request_id          <> NEW.client_request_id
      OR OLD.reservation_attempt_digest <> NEW.reservation_attempt_digest
      OR OLD.request_digest             <> NEW.request_digest
      OR OLD.broker_connection_id       <> NEW.broker_connection_id
      OR OLD.task_id                    <> NEW.task_id
    BEGIN
        SELECT RAISE(ABORT, 'immutable reservation identity');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS reservation_transition_legal
    BEFORE UPDATE ON request_reservations
    FOR EACH ROW
    WHEN NEW.state <> OLD.state
     AND NOT (
              (OLD.state = 'reserved' AND NEW.state = 'issuing')
           OR (OLD.state = 'reserved' AND NEW.state = 'denied')
           OR (OLD.state = 'issuing'  AND NEW.state = 'authorized')
         )
    BEGIN
        SELECT RAISE(ABORT, 'illegal reservation state transition');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS reservation_capability_immutable
    BEFORE UPDATE ON request_reservations
    FOR EACH ROW
    WHEN OLD.capability_id IS NOT NULL
     AND IFNULL(NEW.capability_id, '') <> OLD.capability_id
    BEGIN
        SELECT RAISE(ABORT, 'bound capability is immutable');
    END
    """,
    """
    CREATE TRIGGER IF NOT EXISTS reservation_undeletable
    BEFORE DELETE ON request_reservations
    FOR EACH ROW
    BEGIN
        SELECT RAISE(ABORT, 'reservations are not deletable');
    END
    """,
)


REQUIRED_OBJECTS = (
    "schema_meta",
    "request_reservations",
    "idx_reservation_capability",
    "reservation_identity_immutable",
    "reservation_transition_legal",
    "reservation_capability_immutable",
    "reservation_undeletable",
)

_OBJECT_NAME = re.compile(
    r"CREATE\s+(?:UNIQUE\s+)?(?:TABLE|INDEX|TRIGGER)\s+IF NOT EXISTS\s+(\w+)"
)


def _normalize_ddl(sql: str) -> str:
    """Comparable form of a CREATE statement.

    Strips SQL comments, drops ``IF NOT EXISTS``, and collapses whitespace, so
    the stored definition can be compared against the module's canonical DDL
    without being defeated by formatting.
    """
    without_comments = re.sub(r"--[^\n]*", " ", sql or "")
    return re.sub(r"\s+", " ", without_comments.replace("IF NOT EXISTS ", "")).strip()


class ReservationError(Exception):
    """Base error for the reservation store."""


class ReservationSchemaError(ReservationError):
    """Schema is absent, malformed, or an unsupported version."""


class ReservationContractError(ReservationError):
    """A caller violated this module's contract.

    Distinct from a reason code on purpose: a caller defect is not a decision
    about the reservation and must never enter the closed vocabulary.
    """


# --- Results ------------------------------------------------------------------


@dataclass(frozen=True)
class ReserveResult:
    """Outcome of a reservation attempt.

    ``attempt_token`` is populated **only** for the caller that created the row.
    Every other outcome leaves it empty, so a retry learns that a reservation
    exists without learning how to advance it.
    """

    created: bool
    reason_code: str
    client_request_id: str = ""
    state: str = ""
    capability_id: str = ""
    attempt_token: str = ""


@dataclass(frozen=True)
class LookupResult:
    """Decision-bearing read.

    ``reservation_not_found`` is reserved for a **successful** read that found
    no row. A locked, corrupt, or unsupported store reports its own condition,
    so a caller told "no reservation exists" can distinguish that from "the
    store could not be read" -- the former may reasonably create one, the
    latter must not.
    """

    found: bool
    reason_code: str
    row: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class TransitionResult:
    applied: bool
    reason_code: str
    client_request_id: str = ""
    state: str = ""
    capability_id: str = ""


# --- Helpers ------------------------------------------------------------------


def default_db_path(base_dir: str) -> str:
    return os.path.join(base_dir, "authz", DEFAULT_DB_FILENAME)


def _new_attempt_token() -> str:
    """Opaque raw token, 256 bits of OS-backed randomness."""
    return os.urandom(_TOKEN_BYTES).hex()


def token_digest(token: str) -> str:
    """Verifier stored at rest. The raw token is never persisted."""
    if not isinstance(token, str) or not token.strip():
        raise ReservationContractError("attempt token must be a non-empty string")
    return "sha256:" + hashlib.sha256(token.encode("utf-8")).hexdigest()


def _check_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ReservationContractError(f"{label} must be a non-empty stripped string")
    return value


def _check_digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _DIGEST_PATTERN.match(value):
        raise ReservationContractError(f"{label} must be sha256:<64 lowercase hex>")
    return value


def _is_busy(exc: sqlite3.Error) -> bool:
    text = str(exc).lower()
    return "locked" in text or "busy" in text


def _is_client_request_conflict(exc: sqlite3.IntegrityError) -> bool:
    """True only when the client_request_id primary key caused the failure."""
    text = str(exc).lower()
    return "unique" in text and "client_request_id" in text


def _is_capability_conflict(exc: sqlite3.IntegrityError) -> bool:
    """True only when the capability uniqueness index caused the failure.

    A CHECK or trigger failure must not be relabelled as another request
    already owning the capability -- that would name a condition that did not
    occur.
    """
    text = str(exc).lower()
    return "unique" in text and "capability_id" in text


def _isoformat(moment: datetime) -> str:
    return moment.isoformat()


# --- Store --------------------------------------------------------------------


class RequestReservationStore:
    """Local SQLite reservation registry.

    Authoritative **only** for which client request owns which capability, and
    for the reservation lifecycle above. It proves nothing about who sent the
    request, whether the broker connection is authentic, or whether any
    execution occurred.
    """

    def __init__(
        self,
        db_path: str,
        *,
        busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    ) -> None:
        if busy_timeout_ms <= 0:
            raise ReservationContractError("busy_timeout_ms must be positive")
        self.db_path = db_path
        self.busy_timeout_ms = busy_timeout_ms
        self._schema_verified = False

    # -- connection ------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        parent = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(parent, exist_ok=True)
        pre_existing = os.path.exists(self.db_path)
        conn = sqlite3.connect(
            self.db_path,
            timeout=self.busy_timeout_ms / 1000.0,
            isolation_level=None,  # BEGIN IMMEDIATE means exactly what it says
        )
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout = {int(self.busy_timeout_ms)}")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA synchronous = FULL")
        try:
            if pre_existing and not self._schema_verified:
                row = conn.execute("PRAGMA integrity_check").fetchone()
                if row is None or str(row[0]).lower() != "ok":
                    raise ReservationSchemaError("sqlite integrity check failed")
                self._schema_verified = True
            self._ensure_schema(conn)
        except Exception:
            conn.close()
            raise
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        has_meta = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_meta'"
        ).fetchone()
        recorded = None
        if has_meta:
            row = conn.execute(
                "SELECT value FROM schema_meta WHERE key = 'schema_version'"
            ).fetchone()
            recorded = row["value"] if row else None
        if recorded is not None and recorded != SCHEMA_VERSION:
            raise ReservationSchemaError(f"unsupported schema version: {recorded!r}")
        for statement in _CREATE_SQL:
            conn.execute(statement)
        conn.execute(
            "INSERT OR IGNORE INTO schema_meta (key, value) VALUES (?, ?)",
            ("schema_version", SCHEMA_VERSION),
        )
        self._validate_installed_schema(conn)

    @staticmethod
    def _validate_installed_schema(conn: sqlite3.Connection) -> None:
        """Verify the schema actually installed, not merely its recorded version.

        ``CREATE TABLE IF NOT EXISTS`` silently leaves a pre-existing table
        alone, and a table-level ``CHECK`` or ``PRIMARY KEY`` cannot be
        retrofitted. A database can therefore declare the current version while
        its table lacks the row-shape check and the request-id primary key --
        at which point the module would claim SQLite enforces invariants the
        installed schema does not. ``PRAGMA integrity_check`` does not catch
        this: it proves SQLite's own structures are consistent, not that the
        application's constraints exist.

        Table DDL is compared against the canonical definition because SQLite
        exposes no pragma for table-level CHECK clauses. Indexes and triggers
        are checked by presence.
        """
        present = {
            name: sql
            for name, sql in conn.execute(
                "SELECT name, sql FROM sqlite_master "
                "WHERE name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
        missing = [name for name in REQUIRED_OBJECTS if name not in present]
        if missing:
            raise ReservationSchemaError(
                f"schema objects missing: {sorted(missing)}"
            )
        # Presence is not enough. A missing trigger is recreated by
        # CREATE ... IF NOT EXISTS, but an *altered* one of the same name is
        # not -- and a neutered trigger enforces nothing while looking present.
        for statement in _CREATE_SQL:
            match = _OBJECT_NAME.search(statement)
            if match is None:  # pragma: no cover - defensive
                continue
            name = match.group(1)
            if _normalize_ddl(present.get(name)) != _normalize_ddl(statement):
                raise ReservationSchemaError(
                    f"installed definition of {name!r} does not match the "
                    "canonical schema"
                )

    @staticmethod
    def _rollback(conn: Optional[sqlite3.Connection]) -> None:
        if conn is None:
            return
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    def _store_failure(self, exc: Exception) -> str:
        """Corruption and unsupported schema are unavailable, never absence."""
        if isinstance(exc, sqlite3.OperationalError) and _is_busy(exc):
            return RESERVATION_STORE_BUSY
        return RESERVATION_STORE_UNAVAILABLE

    # -- reservation -----------------------------------------------------------

    def reserve(
        self,
        request: MediatedClientRequest,
        *,
        now: datetime,
    ) -> ReserveResult:
        """Create the reservation, or report on the existing one.

        The raw attempt token is returned only when this call created the row.
        """
        if not isinstance(request, MediatedClientRequest):
            raise ReservationContractError("request must be a MediatedClientRequest")
        client_request_id = request.client_request_id
        request_digest = request.request_digest()
        conn = None
        try:
            conn = self._connect()
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM request_reservations WHERE client_request_id = ?",
                (client_request_id,),
            ).fetchone()

            if row is not None:
                outcome = self._classify_existing(row, request, request_digest)
                conn.execute("ROLLBACK")
                return outcome

            token = _new_attempt_token()
            row_payload = {
                "client_request_id": client_request_id,
                "reservation_attempt_digest": token_digest(token),
                "request_digest": request_digest,
                "broker_connection_id": request.broker_connection_id,
                "task_id": request.task_id,
                "state": STATE_RESERVED,
                "reserved_at": _isoformat(now),
            }
            # The exact persistence payload is checked, not a later projection
            # of it: the invariant must gate what actually reaches the database.
            assert_persistent_privacy_safe(
                row_payload, artifact_name="request reservation row"
            )
            conn.execute(
                "INSERT INTO request_reservations ("
                "client_request_id, reservation_attempt_digest, request_digest, "
                "broker_connection_id, task_id, state, reserved_at"
                ") VALUES (?, ?, ?, ?, ?, ?, ?)",
                tuple(row_payload[key] for key in (
                    "client_request_id", "reservation_attempt_digest",
                    "request_digest", "broker_connection_id", "task_id",
                    "state", "reserved_at",
                )),
            )
            conn.execute("COMMIT")
            return ReserveResult(
                True, RESERVE_OK, client_request_id, STATE_RESERVED,
                attempt_token=token,
            )
        except sqlite3.IntegrityError as exc:
            self._rollback(conn)
            # BEGIN IMMEDIATE serialises conforming writers, so a loser should
            # see the winner's row during its SELECT rather than reaching a
            # duplicate insert. An IntegrityError here is therefore not
            # self-evidently a lost race: it can equally be an incompatible
            # trigger or an unexpected constraint on a same-version database.
            # Assuming "a valid reservation exists, you just do not own it"
            # would assert something never observed.
            if not _is_client_request_conflict(exc):
                return ReserveResult(
                    False, RESERVATION_STORE_UNAVAILABLE, client_request_id
                )
            found = self.lookup(client_request_id)
            if not found.found:
                return ReserveResult(
                    False, found.reason_code, client_request_id
                )
            return self._classify_existing(found.row, request, request_digest)
        except (ReservationSchemaError, sqlite3.Error, OSError) as exc:
            self._rollback(conn)
            return ReserveResult(False, self._store_failure(exc), client_request_id)
        finally:
            if conn is not None:
                conn.close()

    def _classify_existing(
        self,
        row: Any,
        request: MediatedClientRequest,
        request_digest: str,
    ) -> ReserveResult:
        """Compare an existing row against the incoming request.

        The connection comparison is deliberately explicit rather than left to
        the digest. ``broker_connection_id`` is inside the request digest today,
        so a digest check alone would appear to cover it — and would silently
        stop covering it if that field ever left the digest object.
        """
        client_request_id = row["client_request_id"]
        if row["broker_connection_id"] != request.broker_connection_id:
            return ReserveResult(
                False, REQUEST_ID_REUSE_MISMATCH, client_request_id, row["state"]
            )
        if row["request_digest"] != request_digest:
            return ReserveResult(
                False, REQUEST_ID_REUSE_MISMATCH, client_request_id, row["state"]
            )
        state = row["state"]
        if state == STATE_AUTHORIZED:
            return ReserveResult(
                False, RESERVE_OK, client_request_id, state, row["capability_id"] or ""
            )
        if state == STATE_ISSUING:
            return ReserveResult(
                False, RESERVATION_ALREADY_ISSUING, client_request_id, state
            )
        if state == STATE_DENIED:
            return ReserveResult(False, RESERVATION_DENIED, client_request_id, state)
        # reserved, and this caller is not the owner: it holds no token.
        return ReserveResult(False, RESERVATION_UNBOUND, client_request_id, state)

    # -- transitions -----------------------------------------------------------

    @staticmethod
    def _reason_for_row(
        row: sqlite3.Row,
        operation: str,
        *,
        capability_id: Optional[str] = None,
        request: Optional[MediatedClientRequest] = None,
    ) -> str:
        """Why a conditional write changed no row, told truthfully.

        A single generic wrong-state code per operation would report, for
        instance, ``reservation_already_issuing`` for a denied row -- naming a
        condition that is not the one that occurred. The order below matches
        the contract: request mismatch, then state, then token.
        """
        if request is not None and (
            row["request_digest"] != request.request_digest()
            or row["broker_connection_id"] != request.broker_connection_id
        ):
            return REQUEST_ID_REUSE_MISMATCH

        state = row["state"]
        if state == STATE_DENIED:
            return RESERVATION_DENIED
        if state == STATE_AUTHORIZED:
            if operation == "bind" and capability_id == row["capability_id"]:
                return RESERVE_OK  # idempotent recovery of the same binding
            return RESERVATION_ALREADY_BOUND
        if state == STATE_ISSUING:
            if operation in ("begin_issuance", "deny"):
                return RESERVATION_ALREADY_ISSUING
            return RESERVATION_ATTEMPT_MISMATCH  # bind: source state was right
        # reserved
        if operation == "bind":
            return RESERVATION_ISSUANCE_NOT_BEGUN
        return RESERVATION_ATTEMPT_MISMATCH  # begin/deny: source state was right

    def _transition(
        self,
        client_request_id: str,
        attempt_token: str,
        *,
        from_state: str,
        to_state: str,
        assignments: str,
        values: tuple,
        operation: str,
        capability_id: Optional[str] = None,
        request: Optional[MediatedClientRequest] = None,
    ) -> TransitionResult:
        """One atomic token-verified conditional write.

        The predicate carries client_request_id, the required current state, and
        the attempt digest, and exactly one row must change. A read, a
        comparison, and a later unconditional update would let two callers each
        observe the same state and both proceed.
        """
        _check_text(client_request_id, "client_request_id")
        digest = token_digest(attempt_token)
        # Binding the request into the predicate closes a transplant: a valid
        # token for reservation A must not advance A on behalf of a coherent
        # but different request B that merely shares the client request id.
        request_predicate = ""
        request_values: tuple = ()
        if request is not None:
            request_predicate = (
                "  AND request_digest = ? AND broker_connection_id = ? "
            )
            request_values = (
                request.request_digest(),
                request.broker_connection_id,
            )
        conn = None
        try:
            conn = self._connect()
            conn.execute("BEGIN IMMEDIATE")
            cursor = conn.execute(
                f"UPDATE request_reservations SET state = ?, {assignments} "
                "WHERE client_request_id = ? AND state = ? "
                f"  AND reservation_attempt_digest = ? {request_predicate}",
                (to_state, *values, client_request_id, from_state, digest,
                 *request_values),
            )
            if cursor.rowcount == 1:
                conn.execute("COMMIT")
                row = self._read(conn, client_request_id)
                return TransitionResult(
                    True, RESERVE_OK, client_request_id,
                    row["state"] if row else to_state,
                    (row["capability_id"] if row else "") or "",
                )

            # Nothing changed. Explain why without ever leaking the digest.
            row = conn.execute(
                "SELECT * FROM request_reservations WHERE client_request_id = ?",
                (client_request_id,),
            ).fetchone()
            conn.execute("ROLLBACK")
            if row is None:
                return TransitionResult(
                    False, RESERVATION_NOT_FOUND, client_request_id
                )
            reason = self._reason_for_row(
                row, operation, capability_id=capability_id, request=request
            )
            # Recovering an identical binding is a success, not a refusal.
            applied = reason == RESERVE_OK
            return TransitionResult(
                applied, reason, client_request_id, row["state"],
                (row["capability_id"] or ""),
            )
        except sqlite3.IntegrityError as exc:
            self._rollback(conn)
            code = (
                CAPABILITY_ALREADY_RESERVED
                if _is_capability_conflict(exc)
                else RESERVATION_STORE_UNAVAILABLE
            )
            return TransitionResult(False, code, client_request_id)
        except (ReservationSchemaError, sqlite3.Error, OSError) as exc:
            self._rollback(conn)
            return TransitionResult(
                False, self._store_failure(exc), client_request_id
            )
        finally:
            if conn is not None:
                conn.close()

    @staticmethod
    def _read(conn: sqlite3.Connection, client_request_id: str):
        return conn.execute(
            "SELECT * FROM request_reservations WHERE client_request_id = ?",
            (client_request_id,),
        ).fetchone()

    def begin_issuance(
        self,
        request: MediatedClientRequest,
        attempt_token: str,
        *,
        now: datetime,
    ) -> TransitionResult:
        """Consume the one-shot right to obtain a capability.

        Winning this transition is what permits ``issue_capability`` to be
        called. Without it, two holders of the same valid token could each mint
        a capability and only then race to bind one.

        The **whole request** is bound into the predicate, not just its id. A
        valid token for reservation A must not advance A on behalf of a
        different-but-coherent request B that happens to share the client
        request id; otherwise the capability is issued for B and bound into A.
        """
        if not isinstance(request, MediatedClientRequest):
            raise ReservationContractError("request must be a MediatedClientRequest")
        return self._transition(
            request.client_request_id,
            attempt_token,
            from_state=STATE_RESERVED,
            to_state=STATE_ISSUING,
            assignments="issuing_at = ?",
            values=(_isoformat(now),),
            operation="begin_issuance",
            request=request,
        )

    def deny(
        self,
        client_request_id: str,
        attempt_token: str,
        *,
        now: datetime,
    ) -> TransitionResult:
        """Record that authorization was refused. Owner-gated.

        Owner-gating matters here for the same reason it matters on binding: a
        stranger able to deny a live reservation could sabotage an in-flight
        issuer.
        """
        return self._transition(
            client_request_id,
            attempt_token,
            from_state=STATE_RESERVED,
            to_state=STATE_DENIED,
            assignments="denied_at = ?",
            values=(_isoformat(now),),
            operation="deny",
        )

    def bind(
        self,
        client_request_id: str,
        attempt_token: str,
        capability_id: str,
        *,
        now: datetime,
    ) -> TransitionResult:
        """Bind exactly one capability, ``issuing -> authorized``."""
        _check_text(capability_id, "capability_id")
        return self._transition(
            client_request_id,
            attempt_token,
            from_state=STATE_ISSUING,
            to_state=STATE_AUTHORIZED,
            assignments="capability_id = ?, bound_at = ?",
            values=(capability_id, _isoformat(now)),
            operation="bind",
            capability_id=capability_id,
        )

    # -- inspection ------------------------------------------------------------

    def lookup(self, client_request_id: str) -> LookupResult:
        """Read a reservation, distinguishing absence from unavailability."""
        conn = None
        try:
            conn = self._connect()
            row = self._read(conn, client_request_id)
            if row is None:
                return LookupResult(False, RESERVATION_NOT_FOUND)
            return LookupResult(True, RESERVE_OK, self._project(row))
        except (ReservationSchemaError, sqlite3.Error, OSError) as exc:
            return LookupResult(False, self._store_failure(exc))
        finally:
            if conn is not None:
                conn.close()

    @staticmethod
    def _project(row) -> Dict[str, Any]:
        """Evidence-safe metadata only.

        Never carries the raw attempt token: it is authority-bearing, and the
        store does not hold it in any case. The stored verifier is withheld too,
        so no projection consumer can mistake it for a token.
        """
        return {
            "client_request_id": row["client_request_id"],
            "request_digest": row["request_digest"],
            "broker_connection_id": row["broker_connection_id"],
            "task_id": row["task_id"],
            "capability_id": row["capability_id"] or "",
            "state": row["state"],
            "reserved_at": row["reserved_at"],
            "issuing_at": row["issuing_at"] or "",
            "bound_at": row["bound_at"] or "",
            "denied_at": row["denied_at"] or "",
        }

    def projection(self, client_request_id: str) -> Optional[Dict[str, Any]]:
        """Convenience read for healthy stores.

        Returns ``None`` only for a successful read that found no row. An
        operational failure raises rather than being flattened into absence: a
        caller cannot act correctly on "not found" when the truth is "could not
        be read".
        """
        result = self.lookup(client_request_id)
        if result.found:
            return result.row
        if result.reason_code == RESERVATION_NOT_FOUND:
            return None
        raise ReservationError(result.reason_code)


# --- Mediated boundaries ------------------------------------------------------


def _verify_trio(
    effect: AuthorizedContentEffect,
    request: MediatedClientRequest,
    linkage: MediatedPlanLinkage,
) -> None:
    """Reuse CR-OC-001A's binding rules rather than re-deriving them."""
    assert_linkage_binds(effect, request, linkage)


def mediated_issue_capability(
    store: RequestReservationStore,
    ledger: Any,
    receipt: Any,
    effect: AuthorizedContentEffect,
    request: MediatedClientRequest,
    linkage: MediatedPlanLinkage,
    attempt_token: str,
    *,
    issue_capability: Any,
    now: datetime,
    ttl_seconds: Optional[int] = None,
) -> TransitionResult:
    """Reserve-gated capability issuance.

    Order is load-bearing: verify, win the one-shot gate, *then* issue, then
    bind. If issuance raises, or binding cannot complete, the row stays
    permanently ``issuing`` -- it never returns to ``reserved``, permits denial,
    or authorizes a second issuance.
    """
    _verify_trio(effect, request, linkage)

    # The receipt must describe this exact trio, not merely be a valid receipt.
    mapped = capability_binding_fields(effect, request, linkage)
    authz_request = receipt.request
    checks = (
        ("task_id", authz_request.task_id, request.task_id),
        ("decision_id", authz_request.decision_id, linkage.decision_id),
        (
            "artifact_byte_digest",
            authz_request.artifact_byte_digest,
            mapped["artifact_byte_digest"],
        ),
        ("scope_digest", authz_request.scope_digest, mapped["scope_digest"]),
        (
            "plan_body_digest",
            authz_request.plan_body_digest,
            mapped["plan_body_digest"],
        ),
    )
    for field, actual, expected in checks:
        if actual != expected:
            return TransitionResult(
                False, RESERVATION_BINDING_MISMATCH, request.client_request_id
            )

    # Request-aware gate: the predicate carries the request digest and broker
    # connection, so a valid token for this reservation cannot advance it on
    # behalf of a different-but-coherent request sharing the client request id.
    gate = store.begin_issuance(request, attempt_token, now=now)
    if not gate.applied:
        return gate

    kwargs = {"now": now}
    if ttl_seconds is not None:
        kwargs["ttl_seconds"] = ttl_seconds
    capability_id = issue_capability(ledger, receipt, **kwargs)

    return store.bind(
        request.client_request_id, attempt_token, capability_id, now=now
    )


def mediated_claim_capability(
    store: RequestReservationStore,
    ledger: Any,
    capability_id: str,
    effect: AuthorizedContentEffect,
    request: MediatedClientRequest,
    linkage: MediatedPlanLinkage,
    *,
    claim_capability: Any,
    claimant_id: str,
    now: datetime,
    **claim_kwargs: Any,
) -> Any:
    """Delegate to CR-YK-002 claiming only for an authorized reservation.

    **This does not alter or constrain direct callers of**
    ``triage_core.authz.claim_capability``. An issued-but-unbound capability is
    rejected *here*; it is not unclaimable in general, and no claim in this
    module should be read that way.
    """
    _verify_trio(effect, request, linkage)
    found = store.lookup(request.client_request_id)
    if not found.found:
        # Operational failure keeps its own reason. Reporting a locked or
        # corrupt store as absence would tell the caller the reservation does
        # not exist when the truth is that it could not be read.
        return TransitionResult(
            False, found.reason_code, request.client_request_id
        )
    projection = found.row
    # Request identity is compared before lifecycle state, matching the
    # transition classifier's order. The requirements do not qualify reuse
    # mismatch by state: the same client request id presented with a different
    # digest or connection is a mismatch, whatever the reservation happens to
    # be doing. Checking state first would report, say,
    # ``reservation_already_issuing`` to a caller whose real problem is that it
    # is not the request that was reserved.
    if projection["request_digest"] != request.request_digest():
        return TransitionResult(
            False, REQUEST_ID_REUSE_MISMATCH, request.client_request_id
        )
    if projection["broker_connection_id"] != request.broker_connection_id:
        return TransitionResult(
            False, REQUEST_ID_REUSE_MISMATCH, request.client_request_id
        )
    if projection["state"] != STATE_AUTHORIZED:
        code = (
            RESERVATION_ISSUANCE_NOT_BEGUN
            if projection["state"] == STATE_RESERVED
            else RESERVATION_ALREADY_ISSUING
            if projection["state"] == STATE_ISSUING
            else RESERVATION_DENIED
        )
        return TransitionResult(
            False, code, request.client_request_id, projection["state"]
        )
    if projection["capability_id"] != capability_id:
        return TransitionResult(
            False, RESERVATION_ALREADY_BOUND, request.client_request_id,
            projection["state"], projection["capability_id"],
        )
    mapped = capability_binding_fields(effect, request, linkage)
    return claim_capability(
        ledger,
        request.task_id,
        capability_id,
        mapped["artifact_byte_digest"],
        mapped["scope_digest"],
        claimant_id=claimant_id,
        now=now,
        **claim_kwargs,
    )
