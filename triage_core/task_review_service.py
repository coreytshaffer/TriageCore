"""Trusted local composition for CR-140 workspace reviews."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from triage_core.authz import (
    CREDENTIALS_SCHEMA,
    RP_ID,
    AuthzError,
    CredentialStore,
    EnrolledCredential,
)
from triage_core.public_export_staging import (
    _absolute,
    _chain,
    _check_windows_drive,
    _known_folder,
    _leaf,
    _read_fd,
)
from triage_core.task_review_receipt import (
    DECISIONS,
    EvidenceBinding,
    ReviewerPolicy,
    ReviewProofError,
    ReviewReceipt,
    ReviewRequest,
    evidence_manifest_digest,
    review_timestamp,
    validate_review_id,
)
from triage_core.task_review_store import (
    CommittedReview,
    ReviewIntent,
    ReviewStore,
    ReviewStoreError,
)

PROFILE_SCHEMA = "triagecore.task_review_profiles.v1"
MANIFEST_SCHEMA = "triagecore.task_review_manifest.v1"
MAX_EVIDENCE_BYTES = 1024 * 1024
MAX_EVIDENCE_ITEMS = 16
_ACCEPTED = frozenset({"accepted", "accepted_with_minor_edits"})


class ReviewServiceError(RuntimeError):
    """A bounded public reason for a review that could not be completed."""

    @property
    def reason(self) -> str:
        return str(self)


@dataclass(frozen=True)
class ReviewHistory:
    event_id: str
    revision: str
    decision: str
    admitted_at: str
    scope_id: str | None = None


@dataclass(frozen=True)
class ReviewState:
    status: str = "unpaired"
    decision: str | None = None
    reason: str | None = None
    history: tuple[ReviewHistory, ...] = ()
    pending_count: int = 0

    @property
    def binary_label(self) -> bool | None:
        if self.status == "verified":
            if self.decision in _ACCEPTED:
                return True
            if self.decision == "rejected":
                return False
        return None

    @property
    def is_terminal(self) -> bool:
        return self.binary_label is not None


@dataclass(frozen=True)
class EvidenceSnapshot:
    binding: EvidenceBinding
    items: tuple[tuple[str, str], ...] = field(repr=False)


@dataclass(frozen=True)
class _Profile:
    root: Path = field(repr=False)
    directory: Path = field(repr=False)
    scope_id: str
    reviewer_id: str = field(repr=False)
    grants: dict = field(repr=False)


@dataclass(frozen=True)
class _SnapshotPolicy(ReviewerPolicy):
    enrollments: tuple[EnrolledCredential, ...] = field(repr=False)

    def _enrollments(self) -> list[EnrolledCredential]:
        return list(self.enrollments)


def _account_root() -> Path:
    if os.name == "nt":
        home = _known_folder("5e6c858f-0e22-4760-9afe-ea3317b67173", default=True)
    elif os.name == "posix":
        import pwd

        home = Path(pwd.getpwuid(os.geteuid()).pw_dir)
    else:
        raise ReviewServiceError("review_profile_unavailable")
    if home is None or not home.is_absolute():
        raise ReviewServiceError("review_profile_unavailable")
    return home / ".triagecore-review"


@contextmanager
def _private_directory(root: Path, directory: Path) -> Iterator[None]:
    if (
        not root.is_absolute()
        or not directory.is_relative_to(root)
        or ".." in directory.parts
    ):
        raise ReviewServiceError("review_profile_unavailable")
    with _chain(directory, checked_from=root, private=True, exclude_worktrees=True):
        yield


def _read_private(root: Path, path: Path, limit: int) -> bytes:
    if not path.is_relative_to(root) or ".." in path.parts:
        raise ReviewServiceError("review_profile_unavailable")
    with (
        _chain(
            path.parent,
            checked_from=root,
            private=True,
            exclude_worktrees=True,
        ) as directory,
        _read_fd(path, directory, private=True) as stream,
    ):
        content = stream.read(limit + 1)
    if len(content) > limit:
        raise ReviewServiceError("review_evidence_too_large")
    return content


def _json_object(raw: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate member")
            result[key] = value
        return result

    value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise TypeError("expected an object")
    return value


def _credential_answer(
    request: ReviewRequest,
    credential_ids: tuple[str, ...],
) -> Mapping[str, object]:
    from triage_core.fido2_adapter import acquire_review_assertion

    return acquire_review_assertion(
        request.challenge(), credential_ids, request.expires_at
    )


def _history_record(committed: CommittedReview) -> ReviewHistory:
    request = committed.receipt.request
    return ReviewHistory(
        request.event_id,
        request.evidence.revision,
        request.decision,
        review_timestamp(committed.admitted_at),
        request.evidence.scope_id,
    )


class ReviewService:
    """Keep ledger selection separate from user-managed review authority.

    The optional root and acquisition callable are trusted composition seams.
    Normal entry points use the OS account's fixed local profile directory.
    """

    def __init__(
        self,
        ledger_dir: str | Path,
        *,
        root: Path | None = None,
        acquire_assertion: Callable[
            [ReviewRequest, tuple[str, ...]], Mapping[str, object]
        ] = _credential_answer,
    ) -> None:
        self._ledger_dir = Path(ledger_dir)
        self._root = root
        self._acquire_assertion = acquire_assertion
        self._had_pairing = False

    def _profile(self) -> _Profile | None:
        try:
            root = _absolute(self._root if self._root is not None else _account_root())
            if os.name == "nt":
                _check_windows_drive(root)
            try:
                root.lstat()
            except FileNotFoundError:
                if self._had_pairing:
                    raise ReviewServiceError("review_profile_unavailable") from None
                return None
            raw = _json_object(
                _read_private(root, root / "profiles.json", MAX_EVIDENCE_BYTES)
            )
            if raw.keys() != {"schema", "profiles"} or raw["schema"] != PROFILE_SCHEMA:
                raise ValueError("unsupported profile registry")
            if not isinstance(raw["profiles"], list):
                raise TypeError("invalid profiles")
            ledger = self._ledger_dir.resolve()
            matched = None
            directories = set()
            ledgers = set()
            scopes = set()
            for profile in raw["profiles"]:
                if not isinstance(profile, dict) or profile.keys() - {
                    "ledger_dir",
                    "scope_id",
                    "scope_directory",
                    "reviewer_id",
                    "grants",
                }:
                    raise ValueError("invalid profile entry")
                scope = profile["scope_id"]
                validate_review_id(scope)
                directory = root / _leaf(profile.get("scope_directory", scope))
                configured = Path(profile["ledger_dir"])
                if (
                    not configured.is_absolute()
                    or ".." in configured.parts
                    or configured.is_relative_to(root)
                    or root.is_relative_to(configured)
                    or directory in directories
                    or configured in ledgers
                    or scope in scopes
                ):
                    raise ValueError("invalid workspace pairing")
                directories.add(directory)
                ledgers.add(configured)
                scopes.add(scope)
                reviewer = profile["reviewer_id"]
                validate_review_id(reviewer)
                if not isinstance(profile["grants"], dict):
                    raise TypeError("invalid reviewer grants")
                if configured == ledger:
                    matched = _Profile(
                        root, directory, scope, reviewer, profile["grants"]
                    )
            if matched is not None:
                self._had_pairing = True
            elif self._had_pairing:
                raise ReviewServiceError("review_profile_unavailable")
            return matched
        except (
            OSError,
            TypeError,
            ValueError,
            KeyError,
            RuntimeError,
        ):
            raise ReviewServiceError("review_profile_unavailable") from None

    def _required_profile(self) -> _Profile:
        profile = self._profile()
        if profile is None:
            raise ReviewServiceError("review_workspace_unpaired")
        return profile

    def _check_pairing(self, original: _Profile) -> _Profile:
        updated = self._required_profile()
        if (
            original.root != updated.root
            or original.directory != updated.directory
            or original.scope_id != updated.scope_id
            or original.reviewer_id != updated.reviewer_id
        ):
            raise ReviewServiceError("review_profile_changed")
        return updated

    def _policy(self, original: _Profile) -> ReviewerPolicy:
        try:
            profile = self._check_pairing(original)
            credentials = CredentialStore(str(profile.directory))
            registry = _json_object(
                _read_private(profile.root, Path(credentials.path), MAX_EVIDENCE_BYTES)
            )
            entries = registry.get("credentials")
            if registry.get("schema") != CREDENTIALS_SCHEMA or not isinstance(
                entries, list
            ):
                raise ValueError("invalid enrollment registry")
            if any(
                not isinstance(entry, dict)
                or type(entry.get("revoked", False)) is not bool
                for entry in entries
            ):
                raise ValueError("invalid enrollment entry")
            enrollments = tuple(EnrolledCredential(**entry) for entry in entries)
            return _SnapshotPolicy(
                profile.scope_id, profile.grants, credentials, enrollments
            )
        except (AuthzError, OSError, TypeError, ValueError, ReviewServiceError):
            raise ReviewProofError("review_policy_unavailable") from None

    @contextmanager
    def _store(self, profile: _Profile) -> Iterator[ReviewStore]:
        state_dir = profile.directory / "state"
        try:
            with _private_directory(profile.root, state_dir):
                yield ReviewStore(
                    state_dir, profile.scope_id, lambda: self._policy(profile)
                )
        except OSError:
            raise ReviewStoreError("review_store_unavailable") from None

    def _snapshot(self, profile: _Profile, task_id: str) -> EvidenceSnapshot:
        try:
            manifest = _json_object(
                _read_private(
                    profile.root,
                    profile.directory / "evidence.json",
                    MAX_EVIDENCE_BYTES,
                )
            )
            if (
                manifest.keys() != {"schema", "tasks"}
                or manifest["schema"] != MANIFEST_SCHEMA
            ):
                raise ValueError("unsupported evidence manifest")
            entry = manifest["tasks"][task_id]
            if not isinstance(entry, dict) or entry.keys() != {"revision", "items"}:
                raise ValueError("invalid task evidence")
            items = entry["items"]
            if not isinstance(items, dict) or not 1 <= len(items) <= MAX_EVIDENCE_ITEMS:
                raise ValueError("invalid evidence items")
            evidence_root = profile.directory / "evidence"
            payloads: dict[str, bytes] = {}
            displayed: list[tuple[str, str]] = []
            remaining = MAX_EVIDENCE_BYTES
            for item_id in sorted(items):
                validate_review_id(item_id)
                raw = _read_private(
                    profile.root, evidence_root / _leaf(items[item_id]), remaining
                )
                remaining -= len(raw)
                content = raw.decode("utf-8")
                if "\x00" in content:
                    raise ValueError("invalid text artifact")
                payloads[item_id] = raw
                displayed.append((item_id, content))
            binding = EvidenceBinding(
                profile.scope_id,
                task_id,
                entry["revision"],
                evidence_manifest_digest(payloads),
            )
            return EvidenceSnapshot(binding, tuple(displayed))
        except ReviewServiceError:
            raise
        except (OSError, ValueError, TypeError, KeyError, RecursionError):
            raise ReviewServiceError("review_evidence_unavailable") from None

    def migrate(self) -> None:
        """Provision a fresh private store or explicitly migrate the existing one."""
        try:
            profile = self._required_profile()
            with self._store(profile) as store:
                store.initialize()
                store.migrate()
        except (ReviewStoreError, ReviewProofError) as exc:
            raise ReviewServiceError(str(exc)) from None

    def request_intent(
        self,
        task_id: str,
        request_id: str,
        decision: str,
        workload: str | None = None,
    ) -> ReviewIntent:
        try:
            profile = self._required_profile()
            with self._store(profile) as store:
                return store.request_intent(task_id, request_id, decision, workload)
        except (ReviewStoreError, ReviewProofError) as exc:
            raise ReviewServiceError(str(exc)) from None
        except ValueError:
            raise ReviewServiceError("invalid_review_request") from None

    def pending_for_task(self, task_id: str) -> tuple[ReviewIntent, ...]:
        try:
            profile = self._required_profile()
            with self._store(profile) as store:
                return store.list_pending_intents(task_id)
        except (ReviewStoreError, ReviewProofError) as exc:
            raise ReviewServiceError(str(exc)) from None

    def cancel_intent(self, task_id: str, intent_id: str) -> None:
        try:
            profile = self._required_profile()
            with self._store(profile) as store:
                intent = store.get_intent(intent_id)
                if intent is None or intent.task_id != task_id:
                    raise ReviewServiceError("review_intent_missing")
                store.cancel_intent(intent_id)
        except (ReviewStoreError, ReviewProofError) as exc:
            raise ReviewServiceError(str(exc)) from None

    def _allowed_credentials(self, profile: _Profile) -> tuple[str, ...]:
        policy = self._policy(profile)
        grants = policy.grants.get(profile.reviewer_id, ())
        enrolled = policy._enrollments()
        counts = Counter(item.credential_id for item in enrolled)
        allowed = tuple(
            sorted(
                item.credential_id
                for item in enrolled
                if item.human_id == profile.reviewer_id
                and not item.revoked
                and item.rp_id == RP_ID
                and item.credential_id in grants
                and counts[item.credential_id] == 1
            )
        )
        if not allowed:
            raise ReviewProofError("reviewer_credential_unavailable")
        return allowed

    def _recheck(self, profile: _Profile, snapshot: EvidenceSnapshot) -> _Profile:
        current = self._check_pairing(profile)
        if (
            self._snapshot(current, snapshot.binding.task_id).binding
            != snapshot.binding
        ):
            raise ReviewServiceError("review_evidence_changed")
        return current

    def confirm(
        self,
        task_id: str,
        decision: str,
        show: Callable[[EvidenceSnapshot], bool],
        *,
        intent_id: str | None = None,
    ) -> ReviewState:
        """Present the exact snapshot before creating and acquiring the challenge."""
        try:
            validate_review_id(task_id)
            if not isinstance(decision, str) or decision not in DECISIONS:
                raise ReviewServiceError("invalid_review_request")
            profile = self._required_profile()
            snapshot = self._snapshot(profile, task_id)
            if intent_id is not None:
                with self._store(profile) as store:
                    intent = store.get_intent(intent_id)
                    if (
                        intent is None
                        or intent.task_id != task_id
                        or intent.decision != decision
                    ):
                        raise ReviewServiceError("review_intent_missing")
                    if intent.status != "pending":
                        raise ReviewServiceError("review_intent_" + intent.status)
            if show(snapshot) is not True:
                raise ReviewServiceError("review_cancelled")
            profile = self._recheck(profile, snapshot)
            allowed = self._allowed_credentials(profile)
            with self._store(profile) as store:
                current = store.current_evidence(task_id)
                if (
                    current is not None
                    and current.revision == snapshot.binding.revision
                ):
                    if current.digest != snapshot.binding.digest:
                        raise ReviewServiceError("review_evidence_changed")
                else:
                    store.register_evidence(
                        snapshot.binding,
                        expected_revision=current.revision if current else None,
                    )
                request = store.prepare(
                    snapshot.binding,
                    decision,
                    profile.reviewer_id,
                    intent_id=intent_id,
                )
            assertion = self._acquire_assertion(request, allowed)
            profile = self._recheck(profile, snapshot)
            receipt = ReviewReceipt.from_assertion(request, assertion)
            with self._store(profile) as store:
                store.admit(
                    receipt, check_current=lambda: self._recheck(profile, snapshot)
                )
            return ReviewState("verified", decision)
        except (ReviewStoreError, ReviewProofError) as exc:
            raise ReviewServiceError(str(exc)) from None
        except AuthzError:
            raise ReviewServiceError("review_assertion_unavailable") from None
        except (TypeError, ValueError):
            raise ReviewServiceError("invalid_review_request") from None

    def project(self, task_id: str, *, include_history: bool = False) -> ReviewState:
        history: tuple[ReviewHistory, ...] = ()
        try:
            profile = self._profile()
            if profile is None:
                return ReviewState()
            validate_review_id(task_id)
            with self._store(profile) as store:
                if include_history:
                    history = tuple(
                        _history_record(row) for row in store.list_history(task_id)
                    )
                current_binding = store.current_evidence(task_id)
                pending = store.list_pending_intents(task_id)
                if current_binding is not None:
                    try:
                        snapshot = self._snapshot(profile, task_id)
                    except ReviewServiceError as exc:
                        return ReviewState(
                            "evidence_changed",
                            reason=exc.reason,
                            history=history,
                            pending_count=len(pending),
                        )
                    if snapshot.binding != current_binding:
                        return ReviewState(
                            "evidence_changed",
                            reason="review_evidence_changed",
                            history=history,
                            pending_count=len(pending),
                        )
                committed = store.get_current(task_id)
                if committed is not None:
                    request = committed.receipt.request
                    if request.evidence != current_binding:
                        return ReviewState(
                            "evidence_changed",
                            reason="review_evidence_changed",
                            history=history,
                            pending_count=len(pending),
                        )
                    return ReviewState(
                        "verified",
                        request.decision,
                        history=history,
                        pending_count=len(pending),
                    )
                if pending:
                    return ReviewState(
                        "pending", history=history, pending_count=len(pending)
                    )
                return ReviewState("no_decision", history=history)
        except (ReviewServiceError, ReviewProofError, ReviewStoreError) as exc:
            return ReviewState("unavailable", reason=str(exc), history=history)
        except ValueError:
            return ReviewState(
                "unavailable", reason="invalid_review_request", history=history
            )


def get_review_service(ledger_dir: str | Path) -> ReviewService:
    """Compose the OS-account review service without creating any state."""
    return ReviewService(ledger_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage the local task-review store")
    commands = parser.add_subparsers(dest="command", required=True)
    migrate = commands.add_parser(
        "migrate", help="initialize or migrate an explicitly paired store"
    )
    migrate.add_argument("--ledger-dir", required=True)
    args = parser.parse_args()
    try:
        get_review_service(args.ledger_dir).migrate()
    except ReviewServiceError as exc:
        print(exc.reason, file=sys.stderr)
        return 1
    print("Review store ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
