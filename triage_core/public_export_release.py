"""One operator invocation for an exact-byte, locally staged public export."""

from __future__ import annotations

import hmac
import json
import math
from collections.abc import Callable
from contextlib import ExitStack
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from .agent_authority import validate_authority_manifest
from .public_export import AccessAttestation, evaluate_export
from .public_export_evidence import (
    OUTSIDE_VISIBILITY,
    intent_record,
    locator_digest,
    open_evidence_directory,
    release_record,
    write_record,
)
from .public_export_policy import InputError, decode_object, parse_policy
from .public_export_staging import (
    StorageError,
    open_directory,
    read_source,
    stage_payload,
)


@dataclass(frozen=True)
class ReleaseResult:
    outcome: str
    reason_codes: tuple[str, ...] = ()
    review_triggers: tuple[str, ...] = ()
    eligibility_id: str | None = None
    policy_digest: str | None = None
    attempt_id: str | None = None
    exit_code: int = 2
    outside_visibility: tuple[str, ...] = OUTSIDE_VISIBILITY

    def refused(self, *reasons):
        return replace(self, outcome="refused_pre_staging", reason_codes=tuple(sorted(set(reasons))),
                       exit_code=2)


@dataclass(frozen=True)
class _Tick:
    wall: datetime
    mono: float

    @classmethod
    def sample(cls, clock):
        wall, mono = clock.now(), clock.monotonic()
        if (not isinstance(wall, datetime) or wall.utcoffset() != timedelta(0)
                or not isinstance(mono, (int, float)) or not math.isfinite(mono)):
            raise InputError("clock_inconsistent")
        return cls(wall, mono)

    def follows(self, previous):
        elapsed = (self.wall - previous.wall).total_seconds()
        monotonic_elapsed = self.mono - previous.mono
        # The paired samples are taken consecutively on two clocks. Permit small
        # sampling jitter, but never allow either clock to go backwards.
        return elapsed >= 0 and monotonic_elapsed >= 0 and abs(elapsed - monotonic_elapsed) <= 0.050


@dataclass(frozen=True)
class _Inputs:
    proposal: bytes
    payload: bytes
    parent: bytes
    policy: bytes


@dataclass(frozen=True)
class _Source:
    repo_root: Path
    proposal_locator: str
    payload_locator: str
    parent_locator: str
    policy_source: Callable[[], bytes]

    def freeze(self):
        return _Inputs(read_source(self.repo_root, self.proposal_locator),
                       read_source(self.repo_root, self.payload_locator, payload=True),
                       read_source(self.repo_root, self.parent_locator), self.policy_source())

    def evaluate(self, frozen, answers, now, commit):
        return evaluate_export(proposal=frozen.proposal, payload=frozen.payload, parent=frozen.parent,
                               policy=frozen.policy, payload_locator=self.payload_locator,
                               parent_locator=self.parent_locator, attestations=answers,
                               evaluation_time=now, triagecore_commit=commit)


def _display(operator, frozen, decision, destination):
    body = decision.body
    screen = {"eligibility": body, "eligibility_id": decision.eligibility_id,
              "outside_visibility": OUTSIDE_VISIBILITY}
    if decision.outcome != "ineligible":
        screen.update(payload=frozen.payload.decode("utf-8"), payload_length=len(frozen.payload),
                      payload_digest=body["payload"]["digest"], policy_digest=body["policy"]["digest"],
                      destination=str(destination) if destination is not None else None)
    # ASCII JSON is losslessly reversible and escapes controls and literal backslashes.
    operator.display(json.dumps(screen, ensure_ascii=True, indent=2, allow_nan=False))


def _collect_access(policy, recipient, operator, clock):
    """Only policy-listed recipient channels can ask for program attestations."""
    selected = policy.recipient(recipient["provider"], recipient["surface"])
    response = operator.access(selected.provider, selected.surface, selected.programs)
    observed = _Tick.sample(clock)
    if response is None:
        return (), observed
    if not isinstance(response, tuple) or len(response) != 2 or not isinstance(response[1], dict):
        raise InputError("invalid_structure")
    scope, grants = response
    answers = tuple(AccessAttestation(selected.provider, selected.surface, program, scope, state,
                                      observed.wall) for program, state in grants.items())
    return answers, observed


def _parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _deadline(confirmed_at, seconds, valid_until):
    if valid_until <= confirmed_at or valid_until - confirmed_at <= timedelta(seconds=seconds):
        return valid_until
    return confirmed_at + timedelta(seconds=seconds)


def _release_checks(source, frozen, decision, answers, evaluated, confirmed, clock, policy, commit):
    # Recompute on fresh reads with exactly the original time and channel inputs.
    fresh = source.freeze()
    changes = {value for key, value in (("proposal", "proposal_changed"), ("payload", "bytes_changed"),
                                        ("parent", "parent_changed"), ("policy", "policy_changed"))
               if getattr(fresh, key) != getattr(frozen, key)}
    if changes:
        return changes, None
    repeated = source.evaluate(fresh, answers, evaluated.wall, commit)
    if repeated.eligibility_id != decision.eligibility_id:
        return {"eligibility_id_mismatch"}, None
    now = _Tick.sample(clock)
    reasons = set()
    if not confirmed.follows(evaluated) or not now.follows(confirmed) or not now.follows(evaluated):
        reasons.add("clock_inconsistent")
    parent_check = validate_authority_manifest(decode_object(fresh.parent), now=now.wall)
    for issue in parent_check.issues:
        reasons.add({"expired_authority_manifest": "parent_expired",
                     "inactive_authority_manifest": "parent_inactive"}.get(issue.reason, "parent_invalid"))
    until = _parse_time(decision.body["valid_until"])
    expires = _deadline(confirmed.wall, policy.approval_ttl_seconds, until)
    if now.wall >= until:
        reasons.add("valid_until_passed")
    if now.wall >= expires:
        reasons.add("approval_expired")
    if any((now.wall - a.observed_at).total_seconds() > policy.attestation_freshness_seconds
           for a in answers):
        reasons.add("attestation_stale_at_release")
    return reasons, expires


def _stage_with_intent(directory, records, selected, frozen, decision, approved_at, expires, result):
    attempt = str(uuid4())
    name = f"{attempt}.txt"
    result = replace(result, attempt_id=attempt)
    expected = decision.body["payload"]["digest"]
    intent = intent_record(attempt, decision.eligibility_id, result.policy_digest, expected,
                           locator_digest(selected), locator_digest(selected / name),
                           decision.review_triggers, approved_at.isoformat(), expires.isoformat())
    directory.revalidate()
    records.revalidate()
    try:
        bound = write_record(records, intent)
    except (ValueError, OSError):
        return result.refused("intent_write_failed")
    try:
        stage = stage_payload(directory, frozen.payload, name=name)
        outcome, observed, cleanup = stage.outcome, stage.digest, stage.cleanup
        if outcome == "staged_verified" and observed != expected:
            outcome = "staged_mismatch" if observed is not None else "staging_uncertain"
    except OSError:
        # Once staging began an unclassified I/O error cannot establish noncreation.
        outcome, observed, cleanup = "staging_uncertain", None, "unknown"
    result = replace(result, outcome=outcome, reason_codes=() if outcome == "staged_verified" else (outcome,),
                     exit_code={"staged_verified": 0, "refused_pre_staging": 2}.get(outcome, 3))
    try:
        write_record(records, release_record(attempt, bound, outcome, observed, cleanup))
    except (ValueError, OSError):
        # Preserve the observed staging outcome even when the final evidence is lost.
        return replace(result, reason_codes=tuple(sorted((*result.reason_codes, "release_record_failed"))),
                       exit_code=2 if outcome == "refused_pre_staging" else 4)
    return result


def _operator_stage(source, frozen, decision, answers, evaluated, result, evidence_dir, operator, clock, commit):
    policy = parse_policy(frozen.policy)
    if policy.version != 2 or len(policy.roots) != 1:
        return result.refused("staging_policy_required")
    with ExitStack() as handles:
        records = handles.enter_context(open_evidence_directory(policy, evidence_dir))
        selection = operator.destination()
        if not isinstance(selection, tuple) or len(selection) != 2 or selection[1] is not True:
            return result.refused("destination_not_attested")
        if not isinstance(selection[0], (str, Path)):
            return result.refused("unapproved_destination")
        selected = Path(selection[0])
        directory = handles.enter_context(open_directory(
            selected, root=Path(policy.roots[0]), denied_sync_roots=policy.denied_sync_roots))
        _display(operator, frozen, decision, selected)
        if decision.review_triggers:
            ack = operator.acknowledge(decision.review_triggers)
            if (not isinstance(ack, tuple) or not all(isinstance(t, str) for t in ack)
                    or tuple(sorted(ack)) != decision.review_triggers):
                return result.refused("review_triggers_not_acknowledged")
        code = decision.eligibility_id.removeprefix("sha256:")[:12]
        answer = operator.confirm(code)
        if not isinstance(answer, str) or not answer.isascii() or not hmac.compare_digest(answer, code):
            return result.refused("confirmation_declined")
        # The approval exists exclusively on this invocation's call stack.
        # There is no reusable approval object, retry loop, or import path.
        confirmed = _Tick.sample(clock)
        reasons, expires = _release_checks(source, frozen, decision, answers, evaluated,
                                          confirmed, clock, policy, commit)
        if reasons:
            return result.refused(*reasons)
        result = _stage_with_intent(directory, records, selected, frozen, decision,
                                    confirmed.wall, expires, result)
        try:
            handles.close()
        except OSError:
            # Closing the directory handles cannot reverse an observed write.
            return replace(result, reason_codes=(*result.reason_codes, "directory_close_failed"),
                           exit_code=result.exit_code or 3)
        return result


def run_export(*, repo_root: Path, proposal_locator: str, payload_locator: str, parent_locator: str,
               evidence_dir: Path | None, stage: bool, policy_source: Callable[[], bytes],
               operator, clock, triagecore_commit: str) -> ReleaseResult:
    """Run a fresh, single-use evaluation/confirmation cycle with caller-owned I/O."""
    source = _Source(repo_root, proposal_locator, payload_locator, parent_locator, policy_source)
    result = ReleaseResult("refused_pre_staging")
    try:
        frozen = source.freeze()
        # Reuse Grant A's exact closure/diagnostic order. Only a structurally usable
        # snapshot reaches its access check. The provisional outcome grants nothing.
        decision = source.evaluate(frozen, (), clock.now(), triagecore_commit)
        preflight = decision.body
        if preflight["access"]["status"] != "not_collected":
            answers, observed = _collect_access(parse_policy(frozen.policy), preflight["recipient"],
                                                operator, clock)
            evaluated = _Tick.sample(clock)
            decision = source.evaluate(frozen, answers, evaluated.wall, triagecore_commit)
        result = ReleaseResult(decision.outcome, decision.reason_codes, decision.review_triggers,
                               decision.eligibility_id, decision.body["policy"]["digest"],
                               exit_code=2 if decision.outcome == "ineligible" else 0)
        if decision.outcome == "ineligible":
            _display(operator, frozen, decision, None)
            return result
        if not evaluated.follows(observed):
            return result.refused("clock_inconsistent")
        if not stage:
            _display(operator, frozen, decision, None)
            return result
        return _operator_stage(source, frozen, decision, answers, evaluated, result, evidence_dir,
                               operator, clock, triagecore_commit)
    except StorageError as exc:
        return result.refused(exc.code)
    except InputError as exc:
        return result.refused(exc.code)
    except (OSError, EOFError):
        return result.refused("input_unavailable")
    except (ValueError, OverflowError):
        return result.refused("invalid_release_input")
