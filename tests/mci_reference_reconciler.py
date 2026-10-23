"""Test-only reference reconciler for the synthetic Monitoring Coverage Integrity
contract ``mci/0.1`` revision r5 (CR-136).

This module is a conformance oracle consumer, not a TriageCore capability. It
lives under ``tests/``, imports only the standard library, performs no I/O, and
is not reachable from the ``tc`` or ``triagecore`` entry points. It reconciles
fabricated synthetic evidence; it observes no runtime, monitors nothing, and
can neither establish census completeness nor stop an action. Every report it
returns says ``census_assurance=unknown`` and ``inhibition=not_implemented``.

Entry point: ``reconcile(manifest_bytes, envelope_bytes, as_of)``. Section
references are to docs/research/monitoring-coverage-contract-v0.1.md.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

CONTRACT_VERSION = "mci/0.1"
TOKEN = re.compile(r"[A-Za-z0-9._-]{1,64}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")

INFERENCE_ACTION = "inference.local.generate"
TOOL_ACTION = "tool.synthetic.write"
ROLES = ("controller", "witness", "monitor", "human_authority")
OUTCOMES = {"completed", "error", "timeout", "unknown"}
OUTPUT_STATES = {"complete", "partial", "none"}
VERDICTS = {"clear", "flagged", "indeterminate"}
MESSAGE_ROLES = {"system", "user", "assistant", "tool"}

MANIFEST_KEYS = {
    "contract_version", "run_id", "policy_id", "profile", "protocol", "model", "sources", "eligible_actions",
    "excluded_surfaces", "known_bypasses", "review_wait", "admission_wait", "terminal_wait",
    "checkpoint_interval", "checkpoint_count", "checkpoint_grace", "privacy_profile", "census_assurance",
    "inhibition",
}
RECORD_KEYS = {"contract_version", "kind", "record_id", "run_id", "policy_digest", "source_id", "sequence",
               "occurred_at", "payload"}
PAYLOAD_KEYS = {
    "epoch_open": {"type", "epoch_id", "parent_epoch_id", "prior_context_digest", "new_context_digest"},
    "admit": {"type", "attempt_id", "epoch_id", "action", "retry_of"},
    "dispatch": {"type", "attempt_id", "epoch_id", "action", "retry_of", "input_digest"},
    "terminal": {"type", "attempt_id", "epoch_id", "input_digest", "review_digest", "outcome", "output_state"},
    "cancel": {"type", "attempt_id", "epoch_id"},
    "plan_only": {"type", "attempt_id", "epoch_id"},
    "not_dispatched": {"type", "attempt_id", "epoch_id", "cause"},
    "run_close": {"type"},
    "watermark": {"type", "through_sequence", "through_tick"},
    "review": {"type", "stage", "completed_at", "members"},
    "checkpoint": {"type", "checkpoint_id", "cut_tick", "completed_at", "members"},
    "grant": {"type", "exemption_id", "attempt_ids", "action", "valid_from", "valid_until", "reason",
              "consequential_action_policy"},
    "revoke": {"type", "exemption_id"},
}
KIND_TYPES = {
    "observation": {"epoch_open", "admit", "dispatch", "terminal", "cancel", "plan_only", "not_dispatched",
                    "run_close", "watermark"},
    "receipt": {"review", "checkpoint"},
    "exemption": {"grant", "revoke"},
}
TYPE_ROLE = {"epoch_open": "witness", "dispatch": "witness", "terminal": "witness", "not_dispatched": "witness",
             "admit": "controller", "cancel": "controller", "plan_only": "controller", "run_close": "controller",
             "review": "monitor", "checkpoint": "monitor", "grant": "human_authority",
             "revoke": "human_authority"}
MEMBER_KEYS = {"attempt_id", "epoch_id", "input_digest", "review_digest", "verdict"}

# Section 7: codes that stay current permanently once raised.
PERMANENT = {
    "INVALID_RECORD", "POLICY_MISMATCH", "SOURCE_ROLE_MISMATCH", "SOURCE_CONFLICT", "WATERMARK_CONTRADICTION",
    "ATTEMPT_IDENTITY_CONFLICT", "CONTEXT_UNAVAILABLE", "CONTEXT_MISMATCH", "RECEIPT_TIME_INVALID",
    "EXEMPTION_INVALID", "EXEMPTION_NOT_APPLICABLE", "UNADMITTED_DISPATCH", "CANCEL_DISPATCH_CONFLICT",
    "POST_CLOSE_DISPATCH", "OUT_OF_SCOPE_EVENT", "CHECKPOINT_MEMBERSHIP_MISMATCH",
}
# Persisted codes whose historical entry is not condition-driven (deadline,
# checkpoint and epoch-continuity history is recorded separately).
PERSISTED_ON_SIGHT = {
    "INVALID_RECORD", "POLICY_MISMATCH", "SOURCE_ROLE_MISMATCH", "SOURCE_CONFLICT", "WATERMARK_CONTRADICTION",
    "ATTEMPT_IDENTITY_CONFLICT", "CONTEXT_UNAVAILABLE", "CONTEXT_MISMATCH", "RECEIPT_TIME_INVALID",
    "EXEMPTION_INVALID", "UNADMITTED_DISPATCH", "CANCEL_DISPATCH_CONFLICT", "POST_CLOSE_DISPATCH",
    "CHECKPOINT_MEMBERSHIP_MISMATCH",
}

Finding = Tuple[str, str, Optional[int]]


# ---------------------------------------------------------------- encoding
def canonical(value: Any) -> bytes:
    """Section 8 canonical bytes (ASCII, sorted keys, compact, no floats)."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def commitment(domain: str, value: Any) -> str:
    return hashlib.sha256(f"{CONTRACT_VERSION}/{domain}\n".encode("ascii") + canonical(value)).hexdigest()


class _IngestError(Exception):
    pass


def _reject(*_args: Any) -> Any:
    raise _IngestError("value outside the canonicalization domain")


def _no_duplicates(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise _IngestError("duplicate key")
    return dict(pairs)


def _ascii_only(value: Any) -> None:
    if isinstance(value, str):
        if not value.isascii():
            raise _IngestError("non-ASCII string")
    elif isinstance(value, list):
        for item in value:
            _ascii_only(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            _ascii_only(key)
            _ascii_only(item)


def _strict_load(raw: bytes) -> Any:
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicates, parse_float=_reject,
                           parse_constant=_reject)
    except (UnicodeDecodeError, ValueError, RecursionError) as exc:
        raise _IngestError(str(type(exc).__name__)) from None
    _ascii_only(value)
    return value


# ---------------------------------------------------------------- small predicates
def _tok(v: Any) -> bool:
    return isinstance(v, str) and bool(TOKEN.match(v))


def _tok_or_none(v: Any) -> bool:
    return v is None or _tok(v)


def _hex(v: Any) -> bool:
    return isinstance(v, str) and bool(HEX64.match(v))


def _hex_or_none(v: Any) -> bool:
    return v is None or _hex(v)


def _nat(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def _pos(v: Any) -> bool:
    return _nat(v) and v >= 1


def _sorted_unique_tokens(v: Any, nonempty: bool = False) -> bool:
    if not isinstance(v, list) or (nonempty and not v) or not all(_tok(x) for x in v):
        return False
    return all(a < b for a, b in zip(v, v[1:]))


# ---------------------------------------------------------------- manifest (section 3.1)
def _manifest_ok(m: Any) -> bool:
    if not isinstance(m, dict) or set(m) != MANIFEST_KEYS:
        return False
    if m["contract_version"] != CONTRACT_VERSION or not (_tok(m["run_id"]) and _tok(m["policy_id"])):
        return False
    if m["profile"] not in ("synthetic_inference", "synthetic_tool"):
        return False
    if not (_tok(m["protocol"]) and _tok(m["model"])):
        return False
    src = m["sources"]
    if not isinstance(src, dict) or set(src) != set(ROLES) or not all(_tok(v) for v in src.values()):
        return False
    if len(set(src.values())) != 4:
        return False
    if m["profile"] == "synthetic_inference":
        if m["eligible_actions"] != [INFERENCE_ACTION]:
            return False
    elif m["eligible_actions"] != [TOOL_ACTION] or m["protocol"] != "synthetic-tool" or m["model"] != "no-model":
        return False
    if not (_sorted_unique_tokens(m["excluded_surfaces"]) and _sorted_unique_tokens(m["known_bypasses"])):
        return False
    for key in ("review_wait", "admission_wait", "terminal_wait", "checkpoint_interval", "checkpoint_count",
                "checkpoint_grace"):
        if not _pos(m[key]):
            return False
    return (m["privacy_profile"] == "synthetic_public_context_only" and m["census_assurance"] == "unknown"
            and m["inhibition"] == "not_implemented")


# ---------------------------------------------------------------- context objects (section 8)
def _input_ok(ctx: Any, m: Dict[str, Any]) -> bool:
    if not isinstance(ctx, dict):
        return False
    if m["profile"] == "synthetic_inference":
        if set(ctx) != {"protocol", "model", "messages", "tool_records", "parameters"}:
            return False
        msgs = ctx["messages"]
        if not isinstance(msgs, list) or not msgs:
            return False
        for msg in msgs:
            if (not isinstance(msg, dict) or set(msg) != {"role", "content"} or msg["role"] not in MESSAGE_ROLES
                    or not isinstance(msg["content"], str)):
                return False
        if ctx["tool_records"] != [] or not isinstance(ctx["parameters"], dict):
            return False
    else:
        if set(ctx) != {"protocol", "model", "action", "target_token", "before_content", "proposed_content"}:
            return False
        if (ctx["action"] != m["eligible_actions"][0] or not _tok(ctx["target_token"])
                or not isinstance(ctx["before_content"], str) or not isinstance(ctx["proposed_content"], str)):
            return False
    return ctx["protocol"] == m["protocol"] and ctx["model"] == m["model"]


def _review_ok(obj: Any, m: Dict[str, Any]) -> bool:
    if not isinstance(obj, dict) or set(obj) != {"input", "result"} or not _input_ok(obj["input"], m):
        return False
    res = obj["result"]
    if not isinstance(res, dict) or set(res) != {"outcome", "output", "output_state"}:
        return False
    outcome, output, state = res["outcome"], res["output"], res["output_state"]
    if outcome not in OUTCOMES or state not in OUTPUT_STATES or not isinstance(output, str):
        return False
    if outcome == "completed" and state != "complete":
        return False
    if outcome in ("timeout", "unknown") and state == "complete":
        return False
    if state == "none" and output != "":
        return False
    if m["profile"] == "synthetic_tool" and outcome == "completed" and output != obj["input"]["proposed_content"]:
        return False
    return True


# ---------------------------------------------------------------- envelopes
class _Env:
    """One delivered envelope after exact-retransmission collapse."""

    def __init__(self, raw: Any, m: Dict[str, Any], policy: str) -> None:
        self.raw = raw
        self.canon = canonical(raw)
        rec = raw.get("record") if isinstance(raw, dict) else None
        vis = raw.get("visible_at") if isinstance(raw, dict) else None
        self.vis = vis if _nat(vis) else 0
        self.record = rec if isinstance(rec, dict) else None
        self.views = raw.get("context_views") if isinstance(raw, dict) else None
        r = self.record or {}
        self.rid = r.get("record_id") if _tok(r.get("record_id")) else None
        sid, seq = r.get("source_id"), r.get("sequence")
        self.sid = sid if (_tok(sid) and sid in m["sources"].values()) else None
        self.seq = seq if (self.sid is not None and _pos(seq)) else None
        if self.seq is None:
            self.sid = None
        self.subject = self.rid or hashlib.sha256(self.canon).hexdigest()
        self.codes: List[str] = self._structure(raw, m, policy)
        self.ok = not self.codes
        p = r.get("payload") if isinstance(r.get("payload"), dict) else {}
        self.type = p.get("type") if self.ok else None
        self.p = p
        self.occ = r.get("occurred_at") if self.ok else None

    def _structure(self, raw: Any, m: Dict[str, Any], policy: str) -> List[str]:
        if not self._shape_ok(raw, m):
            return ["INVALID_RECORD"]
        r = raw["record"]
        codes = []
        role = {v: k for k, v in m["sources"].items()}.get(r["source_id"])
        need = TYPE_ROLE.get(r["payload"]["type"])
        if need is not None and role != need:
            codes.append("SOURCE_ROLE_MISMATCH")
        if r["policy_digest"] != policy:
            codes.append("POLICY_MISMATCH")
        return codes

    @staticmethod
    def _shape_ok(raw: Any, m: Dict[str, Any]) -> bool:
        if not isinstance(raw, dict) or set(raw) != {"visible_at", "record", "context_views"}:
            return False
        if not _nat(raw["visible_at"]):
            return False
        views = raw["context_views"]
        if not isinstance(views, dict) or not all(_tok(k) and isinstance(v, dict) for k, v in views.items()):
            return False
        r = raw["record"]
        if not isinstance(r, dict) or set(r) != RECORD_KEYS:
            return False
        if r["contract_version"] != CONTRACT_VERSION or r["run_id"] != m["run_id"]:
            return False
        if not (_tok(r["record_id"]) and _tok(r["source_id"]) and _pos(r["sequence"]) and _nat(r["occurred_at"])
                and _hex(r["policy_digest"])):
            return False
        if r["source_id"] not in m["sources"].values() or r["occurred_at"] > raw["visible_at"]:
            return False
        p, kind = r["payload"], r["kind"]
        if kind not in KIND_TYPES or not isinstance(p, dict) or p.get("type") not in KIND_TYPES[kind]:
            return False
        if set(p) != PAYLOAD_KEYS[p["type"]]:
            return False
        return _payload_ok(p, r)


def _payload_ok(p: Dict[str, Any], r: Dict[str, Any]) -> bool:
    t = p["type"]
    if t == "epoch_open":
        return (_tok(p["epoch_id"]) and _tok_or_none(p["parent_epoch_id"]) and _hex_or_none(p["prior_context_digest"])
                and _hex_or_none(p["new_context_digest"]))
    if t in ("admit", "dispatch"):
        ok = _tok(p["attempt_id"]) and _tok(p["epoch_id"]) and _tok(p["action"]) and _tok_or_none(p["retry_of"])
        return ok and (t == "admit" or _hex(p["input_digest"]))
    if t == "terminal":
        if not (_tok(p["attempt_id"]) and _tok(p["epoch_id"]) and _hex(p["input_digest"])
                and _hex(p["review_digest"])):
            return False
        if p["outcome"] not in OUTCOMES or p["output_state"] not in OUTPUT_STATES:
            return False
        if p["outcome"] == "completed" and p["output_state"] != "complete":
            return False
        return not (p["outcome"] in ("timeout", "unknown") and p["output_state"] == "complete")
    if t in ("cancel", "plan_only"):
        return _tok(p["attempt_id"]) and _tok(p["epoch_id"])
    if t == "not_dispatched":
        return _tok(p["attempt_id"]) and _tok(p["epoch_id"]) and p["cause"] in ("cancel", "plan_only")
    if t == "run_close":
        return True
    if t == "watermark":
        return (_nat(p["through_sequence"]) and _nat(p["through_tick"])
                and p["through_sequence"] == r["sequence"] - 1 and p["through_tick"] <= r["occurred_at"])
    if t == "review":
        members = p["members"]
        if p["stage"] not in ("received", "evaluated") or not isinstance(members, list) or not members:
            return False
        for mem in members:
            if not isinstance(mem, dict) or set(mem) != MEMBER_KEYS:
                return False
            if not (_tok(mem["attempt_id"]) and _tok(mem["epoch_id"]) and _hex(mem["input_digest"])):
                return False
            if p["stage"] == "received":
                if mem["review_digest"] is not None or mem["verdict"] is not None:
                    return False
            elif not (_hex(mem["review_digest"]) and mem["verdict"] in VERDICTS):
                return False
        ids = [mem["attempt_id"] for mem in members]
        if not all(a < b for a, b in zip(ids, ids[1:])):
            return False
        return p["completed_at"] is None if p["stage"] == "received" else _nat(p["completed_at"])
    if t == "checkpoint":
        return (_tok(p["checkpoint_id"]) and _nat(p["cut_tick"]) and _nat(p["completed_at"])
                and _sorted_unique_tokens(p["members"]) and p["checkpoint_id"] == f"cp-{p['cut_tick']}")
    if t == "grant":
        return (_tok(p["exemption_id"]) and _sorted_unique_tokens(p["attempt_ids"], nonempty=True)
                and _tok(p["action"]) and _nat(p["valid_from"]) and _nat(p["valid_until"])
                and p["reason"] == "fixture_exception" and p["consequential_action_policy"] == "no_added_authority")
    if t == "revoke":
        return _tok(p["exemption_id"])
    return False


# ---------------------------------------------------------------- per-source walk (section 4)
class _Source:
    def __init__(self) -> None:
        self.state = "contiguous"
        self.accepted: List[Tuple[_Env, int]] = []  # (envelope, first usable tick)
        self.highest = 0
        self.missing: List[int] = []
        self.quarantine_from: Optional[int] = None
        self.quarantined: List[_Env] = []
        self.watermark: Tuple[Optional[int], Optional[int]] = (None, None)
        self.findings: Set[Finding] = set()
        self.blocked_epoch: Optional[str] = None


class _Epochs:
    """Witness epoch lineage (section 3.2), evaluated in witness sequence order."""

    def __init__(self) -> None:
        self.accepted: Dict[str, Dict[str, Any]] = {}
        self.latest: Optional[str] = None
        self.seen_open = False
        self.history: Set[str] = set()      # contradictory events -> persisted EPOCH_CONTINUITY_FAILURE
        self.rule2: Set[str] = set()        # attempts dispatched into an epoch that already has a child
        self.contradicted: Set[str] = set()  # child epochs whose first dispatch contradicts new_context_digest

    def open(self, e: _Env) -> None:
        p = e.p
        eid = p["epoch_id"]
        if not self.seen_open:
            self.seen_open = True
            ok = (e.occ == 0 and p["parent_epoch_id"] is None and p["prior_context_digest"] is None
                  and p["new_context_digest"] is None)
        else:
            parent = self.accepted.get(p["parent_epoch_id"]) if p["parent_epoch_id"] is not None else None
            ok = (eid not in self.accepted and parent is not None and p["parent_epoch_id"] == self.latest
                  and bool(parent["inputs"]) and p["prior_context_digest"] is not None
                  and p["new_context_digest"] is not None and p["prior_context_digest"] == parent["inputs"][-1])
        if not ok:
            self.history.add(eid)
            return
        self.accepted[eid] = {"parent": p["parent_epoch_id"], "child": None, "inputs": [],
                              "new": p["new_context_digest"]}
        if p["parent_epoch_id"] is not None:
            self.accepted[p["parent_epoch_id"]]["child"] = eid
        self.latest = eid

    def dispatch(self, e: _Env) -> None:
        ep = self.accepted[e.p["epoch_id"]]
        if ep["child"] is not None:
            self.rule2.add(e.p["attempt_id"])
            self.history.add(e.p["epoch_id"])
            return
        if ep["parent"] is not None and not ep["inputs"] and e.p["input_digest"] != ep["new"]:
            self.contradicted.add(e.p["epoch_id"])
            self.history.add(e.p["epoch_id"])
        ep["inputs"].append(e.p["input_digest"])


def _walk(envs: List[_Env], epochs: Optional[_Epochs] = None) -> _Source:
    s = _Source()
    by_seq: Dict[int, List[_Env]] = {}
    for e in envs:
        by_seq.setdefault(e.seq, []).append(e)
    s.highest = max(by_seq) if by_seq else 0
    s.missing = [q for q in range(1, s.highest + 1) if q not in by_seq]
    conflict: Optional[int] = None
    for q, variants in by_seq.items():
        if len(variants) > 1:
            conflict = q if conflict is None else min(conflict, q)
    by_rid: Dict[str, Set[int]] = {}
    for e in envs:
        if e.rid is not None:
            by_rid.setdefault(e.rid, set()).add(e.seq)
    for seqs in by_rid.values():
        if len(seqs) > 1:
            conflict = min(seqs) if conflict is None else min(conflict, min(seqs))
    if conflict is not None:
        s.findings.add(("SOURCE_CONFLICT", envs[0].sid, None))
    blocked = False
    first_usable = 0
    last_wm_tick: Optional[int] = None
    q = 1
    while q in by_seq and (conflict is None or q < conflict):
        e = by_seq[q][0]
        first_usable = max(first_usable, e.vis)
        if not e.ok:
            blocked = True
            break
        if e.type == "watermark":
            through = e.p["through_tick"]
            if last_wm_tick is not None and through < last_wm_tick:
                s.findings.add(("INVALID_RECORD", e.subject, None))
                blocked = True
                break
            if any(x.seq > q and x.ok and x.type != "watermark" and x.occ <= through for x in envs):
                s.findings.add(("WATERMARK_CONTRADICTION", e.sid, None))
                conflict = q
                break
            last_wm_tick = through
            s.watermark = (q, through)
        if epochs is not None:
            if e.type == "epoch_open":
                epochs.open(e)
            elif e.type in ("dispatch", "terminal") and e.p["epoch_id"] not in epochs.accepted:
                s.blocked_epoch = e.p["epoch_id"]
                blocked = True
                break
            elif e.type == "dispatch":
                epochs.dispatch(e)
        s.accepted.append((e, first_usable))
        q += 1
    if conflict is not None:
        s.quarantine_from = conflict
        s.quarantined = [e for e in envs if e.seq >= conflict]
        s.state = "conflicted"
    elif blocked or len(s.accepted) < s.highest:
        s.state = "incomplete"
    if s.missing:
        s.findings.add(("SOURCE_SEQUENCE_GAP", envs[0].sid, None))
    return s


# ---------------------------------------------------------------- snapshot of current state at one tick
class _Unit:
    def __init__(self, attempt: str, desc: _Env) -> None:
        self.attempt = attempt
        self.desc = desc
        self.epoch = desc.p["epoch_id"]
        self.action = desc.p["action"]
        self.retry_of = desc.p["retry_of"]
        self.tick = desc.occ
        self.dispatch_ids: Set[str] = set()
        self.disputed = False
        self.epoch_disputed = False
        self.dispatch_ok = False
        self.terminal: Optional[_Env] = None
        self.terminal_ok = False
        self.reviews: Set[str] = set()
        self.verdicts: Set[str] = set()
        self.exemptions: Set[str] = set()
        self.partition = "uncovered"


class _Snapshot:
    def __init__(self, run: "_Run", t: int) -> None:
        self.t = t
        m = run.m
        visible = [e for e in run.envs if e.vis <= t]
        self.findings: Set[Finding] = set()
        for e in visible:
            for code in e.codes:
                self.findings.add((code, e.subject, None))
        self.epochs = _Epochs()
        self.sources: Dict[str, _Source] = {}
        for role in ROLES:
            sid = m["sources"][role]
            mine = [e for e in visible if e.sid == sid]
            self.sources[sid] = _walk(mine, self.epochs if role == "witness" else None)
            self.findings |= self.sources[sid].findings
        src = {role: self.sources[m["sources"][role]] for role in ROLES}

        def accepted(role: str, typ: str) -> List[Tuple[_Env, int]]:
            return [(e, fu) for e, fu in src[role].accepted if e.type == typ]

        def quarantined(role: str, typ: str) -> List[_Env]:
            return [e for e in src[role].quarantined if e.ok and e.type == typ]

        eligible = set(m["eligible_actions"])
        # ---- units (section 5): healthy dispatches plus the conservative disputed candidates
        healthy: Dict[str, List[_Env]] = {}
        for e, _fu in accepted("witness", "dispatch"):
            if e.p["action"] not in eligible:
                self.findings.add(("OUT_OF_SCOPE_EVENT", e.p["attempt_id"], None))
                continue
            healthy.setdefault(e.p["attempt_id"], []).append(e)
        contested: Dict[str, List[_Env]] = {}
        for e in quarantined("witness", "dispatch"):
            if e.p["action"] in eligible:
                contested.setdefault(e.p["attempt_id"], []).append(e)
        self.units: Dict[str, _Unit] = {}
        for att in set(healthy) | set(contested):
            if att in healthy:
                desc = min(healthy[att], key=lambda x: x.seq)
            else:
                desc = min(contested[att], key=lambda x: (x.vis, x.seq, x.rid or "", x.canon))
            u = _Unit(att, desc)
            u.dispatch_ids = {x.rid for x in healthy.get(att, []) + contested.get(att, []) if x.rid}
            u.disputed = att in contested or len(healthy.get(att, [])) > 1
            self.units[att] = u
        identity_conflicts: Set[str] = {a for a, xs in healthy.items() if len(xs) > 1}
        for typ, role in (("admit", "controller"), ("terminal", "witness"), ("not_dispatched", "witness")):
            seen: Dict[str, int] = {}
            for e, _fu in accepted(role, typ):
                seen[e.p["attempt_id"]] = seen.get(e.p["attempt_id"], 0) + 1
            identity_conflicts |= {a for a, n in seen.items() if n > 1}
        admits: Dict[str, List[Tuple[_Env, int]]] = {}
        for e, fu in accepted("controller", "admit"):
            admits.setdefault(e.p["attempt_id"], []).append((e, fu))
        for att, u in self.units.items():
            for e, _fu in admits.get(att, []):
                if (e.p["epoch_id"], e.p["action"], e.p["retry_of"]) != (u.epoch, u.action, u.retry_of):
                    identity_conflicts.add(att)
        terminals: Dict[str, List[_Env]] = {}
        for e, _fu in accepted("witness", "terminal"):
            terminals.setdefault(e.p["attempt_id"], []).append(e)
            u = self.units.get(e.p["attempt_id"])
            if u is not None and e.p["epoch_id"] != u.epoch:
                identity_conflicts.add(u.attempt)
        for att in identity_conflicts:
            self.findings.add(("ATTEMPT_IDENTITY_CONFLICT", att, None))
        self.unresolved_epochs: Set[str] = set()
        if src["witness"].blocked_epoch is not None:
            self.unresolved_epochs.add(src["witness"].blocked_epoch)
        for u in self.units.values():
            if u.attempt in identity_conflicts:
                u.disputed = True
            if u.attempt in self.epochs.rule2 or u.epoch in self.epochs.contradicted:
                u.disputed = True
                u.epoch_disputed = True
                self.unresolved_epochs.add(u.epoch)
        self.epoch_history = set(self.epochs.history)
        for ep in self.unresolved_epochs:
            self.findings.add(("EPOCH_CONTINUITY_FAILURE", ep, None))

        # ---- witness bindings for nondisputed units (sections 3.2, 8)
        for u in self.units.values():
            if u.disputed:
                continue
            d = u.desc
            view = d.views.get(u.attempt)
            if view is None:
                self.findings.add(("CONTEXT_UNAVAILABLE", d.subject, None))
            elif commitment("input", view) != d.p["input_digest"] or not _input_ok(view, m):
                self.findings.add(("CONTEXT_MISMATCH", d.subject, None))
            else:
                u.dispatch_ok = True
            ts = terminals.get(u.attempt, [])
            if ts:
                term = ts[0]
                u.terminal = term
                tview = term.views.get(u.attempt)
                if tview is None:
                    self.findings.add(("CONTEXT_UNAVAILABLE", term.subject, None))
                elif not (_review_ok(tview, m) and commitment("review", tview) == term.p["review_digest"]
                          and commitment("input", tview["input"]) == term.p["input_digest"]
                          and term.p["input_digest"] == d.p["input_digest"]
                          and tview["result"]["outcome"] == term.p["outcome"]
                          and tview["result"]["output_state"] == term.p["output_state"]
                          and term.occ >= d.occ):
                    self.findings.add(("CONTEXT_MISMATCH", term.subject, None))
                else:
                    u.terminal_ok = True

        # ---- review receipts (section 3.3)
        received: List[_Env] = []
        for e, _fu in accepted("monitor", "review"):
            if e.p["stage"] == "received":
                received.append(e)
                continue
            credited = True
            for mem in e.p["members"]:
                if not self._member(e, mem, self.units.get(mem["attempt_id"]), m):
                    credited = False
            if credited:
                for mem in e.p["members"]:
                    u = self.units[mem["attempt_id"]]
                    u.reviews.add(e.rid)
                    u.verdicts.add(mem["verdict"])
        for e in received:
            atts = [mem["attempt_id"] for mem in e.p["members"]]
            if any(a not in self.units for a in atts):
                self.findings.add(("ORPHAN_RECEIPT", e.subject, None))
            if not all(a in self.units and self.units[a].reviews for a in atts):
                self.findings.add(("RECEIPT_NOT_EVALUATED", e.subject, None))

        # ---- exemptions (section 3.4)
        grants: List[Tuple[_Env, int]] = []
        taken: Set[str] = set()
        for e, fu in accepted("human_authority", "grant"):
            p = e.p
            valid = (p["exemption_id"] not in taken and e.vis <= p["valid_from"] < p["valid_until"]
                     and p["action"] in eligible)
            taken.add(p["exemption_id"])
            if valid:
                grants.append((e, fu))
            else:
                self.findings.add(("EXEMPTION_INVALID", p["exemption_id"], None))
        human = m["sources"]["human_authority"]
        revokes = [e for e in visible if e.sid == human and e.ok and e.type == "revoke"]
        for u in self.units.values():
            if u.disputed:
                continue
            named = [(g, fu) for g, fu in grants if u.attempt in g.p["attempt_ids"]]
            for g, fu in named:
                if (g.p["action"] == u.action and g.p["valid_from"] <= u.tick < g.p["valid_until"]
                        and fu <= u.tick and run.human_state(u.tick) == "contiguous"
                        and not any(r.p["exemption_id"] == g.p["exemption_id"] and r.vis <= u.tick
                                    for r in revokes)):
                    u.exemptions.add(g.p["exemption_id"])
            if named and not u.exemptions:
                self.findings.add(("EXEMPTION_NOT_APPLICABLE", u.attempt, None))

        # ---- per-unit lifecycle findings and partitions (section 5)
        closes = accepted("controller", "run_close")
        self.close_tick = closes[0][1] if closes else None
        for e, _fu in closes[1:]:
            self.findings.add(("INVALID_RECORD", e.subject, None))
        not_dispatched = {e.p["attempt_id"] for e, _fu in accepted("witness", "not_dispatched")}
        for u in self.units.values():
            if not any(e.occ <= u.tick and fu <= u.tick for e, fu in admits.get(u.attempt, [])):
                self.findings.add(("UNADMITTED_DISPATCH", u.attempt, None))
            if u.attempt in not_dispatched:
                self.findings.add(("CANCEL_DISPATCH_CONFLICT", u.attempt, None))
            if self.close_tick is not None and u.tick > self.close_tick:
                self.findings.add(("POST_CLOSE_DISPATCH", u.attempt, None))
            if u.disputed:
                u.partition = "uncovered"
                continue
            if u.reviews:
                u.partition = "reviewed"
            elif u.exemptions:
                u.partition = "exempt_unreviewed"
            elif t < u.tick + m["review_wait"]:
                u.partition = "pending_within_deadline"
            if "flagged" in u.verdicts:
                self.findings.add(("REVIEW_FLAGGED", u.attempt, None))
            if "indeterminate" in u.verdicts:
                self.findings.add(("REVIEW_INDETERMINATE", u.attempt, None))
            if len(u.verdicts) > 1:
                self.findings.add(("REVIEW_VERDICT_DISAGREEMENT", u.attempt, None))
            if u.terminal_ok and u.terminal.p["outcome"] in ("timeout", "unknown"):
                self.findings.add(("EXECUTION_OUTCOME_UNKNOWN", u.attempt, None))

        # ---- admissions (section 5)
        cancels: Dict[str, _Env] = {}
        for typ in ("cancel", "plan_only"):
            for e, _fu in accepted("controller", typ):
                cancels.setdefault(e.p["attempt_id"], e)
        nds: Dict[str, _Env] = {}
        for e, _fu in accepted("witness", "not_dispatched"):
            nds.setdefault(e.p["attempt_id"], e)
        self.resolution: Dict[str, Tuple[str, List[str]]] = {}
        for att in set(cancels) | set(self.units):
            if att in self.units:
                self.resolution[att] = ("dispatched", sorted(self.units[att].dispatch_ids))
            elif att in nds and nds[att].p["cause"] == cancels[att].type:
                self.resolution[att] = ("not_dispatched", sorted({cancels[att].subject, nds[att].subject}))
        self.admissions: Dict[str, Dict[str, Any]] = {}
        quarantined_admits = quarantined("controller", "admit")
        for att in set(admits) | {e.p["attempt_id"] for e in quarantined_admits}:
            ok_admits = [e for e, _fu in admits.get(att, [])]
            q_admits = [e for e in quarantined_admits if e.p["attempt_id"] == att]
            primary = min(ok_admits, key=lambda x: x.seq) if ok_admits else min(q_admits, key=lambda x: x.seq)
            self.admissions[att] = {"primary": primary, "ids": {e.rid for e in ok_admits + q_admits if e.rid}}

        # ---- checkpoint receipts are judged in _Run, which owns the cut history
        self.checkpoint_receipts = [(e, fu) for e, fu in accepted("monitor", "checkpoint")]
        self.integrity_uncertain = (any(s.state != "contiguous" for s in self.sources.values())
                                    or any(u.disputed for u in self.units.values())
                                    or bool(self.unresolved_epochs))

    def _member(self, e: _Env, mem: Dict[str, Any], u: Optional[_Unit], m: Dict[str, Any]) -> bool:
        """Check one evaluated member; return True only if it can be credited."""
        view = e.views.get(mem["attempt_id"])

        def own_checks() -> None:
            if view is None:
                self.findings.add(("CONTEXT_UNAVAILABLE", e.subject, None))
            elif not (_review_ok(view, m) and commitment("review", view) == mem["review_digest"]
                      and commitment("input", view["input"]) == mem["input_digest"]):
                self.findings.add(("CONTEXT_MISMATCH", e.subject, None))
            if e.p["completed_at"] > e.occ:
                self.findings.add(("RECEIPT_TIME_INVALID", e.subject, None))

        if u is None:
            self.findings.add(("ORPHAN_RECEIPT", e.subject, None))
            return False
        if u.disputed:
            own_checks()
            return False
        if u.terminal is None:
            self.findings.add(("CONTEXT_UNSEALED", e.subject, None))
            if e.p["completed_at"] > e.occ:
                self.findings.add(("RECEIPT_TIME_INVALID", e.subject, None))
            return False
        term = u.terminal
        failed: List[str] = []
        if view is None:
            failed.append("CONTEXT_UNAVAILABLE")
        elif not (mem["epoch_id"] == u.epoch and _review_ok(view, m)
                  and commitment("review", view) == mem["review_digest"]
                  and commitment("input", view["input"]) == mem["input_digest"]
                  and mem["input_digest"] == u.desc.p["input_digest"]
                  and mem["review_digest"] == term.p["review_digest"]
                  and view["result"]["outcome"] == term.p["outcome"]
                  and view["result"]["output_state"] == term.p["output_state"]):
            failed.append("CONTEXT_MISMATCH")
        if not (term.occ <= e.p["completed_at"] <= e.occ):
            failed.append("RECEIPT_TIME_INVALID")
        for code in failed:
            self.findings.add((code, e.subject, None))
        return not failed and u.dispatch_ok and u.terminal_ok


# ---------------------------------------------------------------- run: replay, checkpoints, deadlines
class _Run:
    def __init__(self, manifest: Dict[str, Any], raws: List[Any]) -> None:
        self.m = manifest
        self.policy = commitment("manifest", manifest)
        collapsed: Dict[bytes, Any] = {}
        for raw in raws:
            ident = canonical({k: v for k, v in raw.items() if k != "visible_at"}) if isinstance(raw, dict) \
                else canonical(raw)
            vis = raw.get("visible_at") if isinstance(raw, dict) else None
            vis = vis if _nat(vis) else 0
            prev = collapsed.get(ident)
            if prev is None or vis < prev[0]:
                collapsed[ident] = (vis, raw)
        self.envs = [_Env(raw, manifest, self.policy) for _vis, raw in collapsed.values()]
        self._human: Dict[int, str] = {}

    def human_state(self, tick: int) -> str:
        if tick not in self._human:
            sid = self.m["sources"]["human_authority"]
            self._human[tick] = _walk([e for e in self.envs if e.sid == sid and e.vis <= tick]).state
        return self._human[tick]

    def input_set_digest(self, as_of: int) -> str:
        def key(e: _Env) -> Tuple[Any, ...]:
            r = e.record or {}
            return (e.vis, r.get("source_id") if _tok(r.get("source_id")) else "",
                    r.get("sequence") if _pos(r.get("sequence")) else -1, e.rid or "", e.canon)

        delivered = [e.raw for e in sorted((e for e in self.envs if e.vis <= as_of), key=key)]
        return commitment("inputs", {"manifest": self.m, "delivered": delivered})

    def report(self, as_of: int) -> Dict[str, Any]:
        m = self.m
        snaps = [_Snapshot(self, t) for t in range(as_of + 1)]
        now = snaps[as_of]
        history: Set[Finding] = set()
        permanent: Set[Finding] = set()
        for s in snaps:
            history |= {f for f in s.findings if f[0] in PERSISTED_ON_SIGHT}
            history |= {("EPOCH_CONTINUITY_FAILURE", ep, None) for ep in s.epoch_history}
            permanent |= {f for f in s.findings if f[0] in PERMANENT}
        current: Set[Finding] = set(now.findings) | permanent

        # ---- checkpoints (section 6), replayed tick by tick
        cuts: List[int] = []
        counted = 0
        close_tick: Optional[int] = None
        prev_units: Set[str] = set()
        decisions: Dict[str, Tuple[str, _Env]] = {}
        complete_since: Dict[int, Optional[int]] = {}
        ever_complete: Set[int] = set()
        for s in snaps:
            t = s.t
            if close_tick is None and s.close_tick is not None:
                close_tick = s.close_tick
            new_units = sorted(a for a in s.units if a not in prev_units)
            prev_units = set(s.units)
            if close_tick is None or t <= close_tick:
                create = t > 0 and t % m["checkpoint_interval"] == 0
                fresh = [a for a in new_units if not s.units[a].disputed]
                if fresh:
                    before, counted = counted, counted + len(fresh)
                    create = create or counted // m["checkpoint_count"] > before // m["checkpoint_count"]
                if close_tick == t:
                    create = True
                if create and t not in cuts:
                    cuts.append(t)
            for e, fu in s.checkpoint_receipts:
                if fu != t or e.subject in decisions:
                    continue
                cut = e.p["cut_tick"]
                if cut not in cuts:
                    decisions[e.subject] = ("orphan", e)
                elif e.p["members"] != self._members(s, cut):
                    decisions[e.subject] = ("mismatch", e)
                elif not (cut <= e.p["completed_at"] <= e.occ):
                    decisions[e.subject] = ("time", e)
                else:
                    decisions[e.subject] = ("eligible", e)
            for cut in cuts:
                done = self._complete(s, cut, decisions)
                if done:
                    ever_complete.add(cut)
                    if complete_since.get(cut) is None:
                        complete_since[cut] = t
                else:
                    if cut in ever_complete:
                        history.add(("CHECKPOINT_INVALIDATED", f"cp-{cut}", None))
                    complete_since[cut] = None
                if t == cut + m["checkpoint_grace"] and not done:
                    history.add(("CHECKPOINT_MISSED", f"cp-{cut}", t))
        for kind, e in decisions.values():
            if kind == "orphan":
                current.add(("ORPHAN_RECEIPT", e.subject, None))
            elif kind == "mismatch":
                f = ("CHECKPOINT_MEMBERSHIP_MISMATCH", f"cp-{e.p['cut_tick']}", None)
                current.add(f)
                history.add(f)
            elif kind == "time":
                f = ("RECEIPT_TIME_INVALID", e.subject, None)
                current.add(f)
                history.add(f)
        checkpoint_rows = []
        previous = 0
        for cut in sorted(cuts):
            members = self._members(now, cut)
            receipts = sorted(e.subject for kind, e in decisions.values()
                              if kind == "eligible" and e.p["cut_tick"] == cut and e.p["members"] == members
                              and any(x is e for x, _fu in now.checkpoint_receipts))
            if complete_since.get(cut) is not None:
                state, done_at = "complete", complete_since[cut]
            elif cut in ever_complete:
                state, done_at = "invalidated", None
                current.add(("CHECKPOINT_INVALIDATED", f"cp-{cut}", None))
            elif as_of >= cut + m["checkpoint_grace"]:
                state, done_at = "overdue", None
                current.add(("CHECKPOINT_MISSED", f"cp-{cut}", cut + m["checkpoint_grace"]))
            else:
                state, done_at = "pending", None
            checkpoint_rows.append({
                "checkpoint_id": f"cp-{cut}", "previous_cut": previous, "cut_tick": cut,
                "deadline": cut + m["checkpoint_grace"], "members": members, "state": state,
                "receipt_record_ids": receipts, "completed_at": done_at})
            previous = cut

        # ---- per-unit deadlines, each assessed against what was usable at the deadline
        unit_rows = []
        for att in sorted(now.units):
            u = now.units[att]
            review_due = u.tick + m["review_wait"]
            terminal_due = u.tick + m["terminal_wait"]
            if review_due <= as_of:
                then = snaps[review_due].units.get(att)
                if then is None or then.disputed or then.partition not in ("reviewed", "exempt_unreviewed"):
                    history.add(("MISSED_REVIEW_DEADLINE", att, review_due))
                    if u.partition == "uncovered":
                        current.add(("MISSED_REVIEW_DEADLINE", att, review_due))
            if terminal_due <= as_of:
                then = snaps[terminal_due].units.get(att)
                if then is None or then.disputed or not then.terminal_ok:
                    history.add(("TERMINAL_MISSING", att, terminal_due))
                    if u.disputed or not u.terminal_ok:
                        current.add(("TERMINAL_MISSING", att, terminal_due))
            credited_terminal = u.terminal if (u.terminal_ok and not u.disputed) else None
            unit_rows.append({
                "attempt_id": att, "epoch_id": u.epoch, "action": u.action, "retry_of": u.retry_of,
                "dispatch_tick": u.tick, "review_deadline": review_due, "terminal_deadline": terminal_due,
                "partition": u.partition, "disputed": u.disputed, "dispatch_record_ids": sorted(u.dispatch_ids),
                "terminal_record_id": credited_terminal.subject if credited_terminal else None,
                "review_record_ids": sorted(u.reviews), "exemption_ids": sorted(u.exemptions),
                "input_digest": u.desc.p["input_digest"] if (u.dispatch_ok and not u.disputed) else None,
                "review_digest": credited_terminal.p["review_digest"] if credited_terminal else None,
                "outcome": credited_terminal.p["outcome"] if credited_terminal else None,
                "output_state": credited_terminal.p["output_state"] if credited_terminal else None,
                "verdicts": sorted(u.verdicts)})

        admission_rows = []
        waiting = False
        for att in sorted(now.admissions):
            a = now.admissions[att]
            tick = a["primary"].occ
            due = tick + m["admission_wait"]
            if due <= as_of and att not in snaps[due].resolution:
                history.add(("ADMISSION_UNRESOLVED", att, due))
            if att in now.resolution:
                state, res = now.resolution[att]
            elif as_of < due:
                state, res = "waiting", []
                waiting = True
            else:
                state, res = "unresolved", []
                current.add(("ADMISSION_UNRESOLVED", att, due))
            admission_rows.append({
                "attempt_id": att, "epoch_id": a["primary"].p["epoch_id"],
                "admission_record_ids": sorted(a["ids"]), "admission_tick": tick, "deadline": due,
                "state": state, "resolution_record_ids": res})

        # ---- counts (section 5)
        counts = []
        for action in m["eligible_actions"]:
            rows = [r for r in unit_rows if r["action"] == action]
            tally = {k: sum(1 for r in rows if r["partition"] == k)
                     for k in ("reviewed", "exempt_unreviewed", "pending_within_deadline", "uncovered")}
            if now.integrity_uncertain:
                status, ratio = "integrity_uncertain", None
            elif not rows:
                status, ratio = "no_observed_units", None
            else:
                status, ratio = "observed_only", [tally["reviewed"], len(rows)]
            counts.append(dict(action=action, observed=len(rows), coverage_ratio=ratio, ratio_status=status, **tally))

        # ---- closure (section 6)
        window = "open"
        if close_tick is not None and close_tick in cuts and complete_since.get(close_tick) is not None:
            closable = (not waiting
                        and all(s.state == "contiguous" for s in now.sources.values())
                        and all((u.terminal_ok and not u.disputed) or as_of >= u.tick + m["terminal_wait"]
                                for u in now.units.values()))
            if closable:
                window = "closed_reconciled" if not current and not history else "closed_with_findings"

        source_rows = []
        for sid in sorted(m["sources"].values()):
            s = now.sources[sid]
            source_rows.append({
                "source_id": sid, "state": s.state, "accepted_prefix": len(s.accepted), "highest_seen": s.highest,
                "missing_sequences": s.missing,
                "disputed_record_ids": sorted({e.rid for e in s.quarantined if e.rid}),
                "watermark_sequence": s.watermark[0], "watermark_tick": s.watermark[1]})

        return {
            "contract_version": CONTRACT_VERSION,
            "run_id": m["run_id"],
            "policy_digest": self.policy,
            "as_of": as_of,
            "input_set_digest": self.input_set_digest(as_of),
            "window_state": window,
            "source_states": source_rows,
            "unit_states": unit_rows,
            "admission_states": admission_rows,
            "checkpoint_states": checkpoint_rows,
            "counts_by_action": counts,
            "diagnostics": _finding_rows(current),
            "historical_violations": _finding_rows(history),
            "census_assurance": "unknown",
            "inhibition": "not_implemented",
        }

    @staticmethod
    def _members(s: _Snapshot, cut: int) -> List[str]:
        return sorted(a for a, u in s.units.items() if u.tick <= cut)

    def _complete(self, s: _Snapshot, cut: int, decisions: Dict[str, Tuple[str, _Env]]) -> bool:
        members = self._members(s, cut)
        live = {e.subject for e, _fu in s.checkpoint_receipts}
        receipt = any(kind == "eligible" and e.p["cut_tick"] == cut and e.p["members"] == members
                      and e.subject in live for kind, e in decisions.values())
        if not receipt:
            return False
        for a in members:
            u = s.units[a]
            if u.disputed or u.epoch in s.unresolved_epochs or u.partition not in ("reviewed", "exempt_unreviewed"):
                return False
        for src in s.sources.values():
            if src.watermark[1] is None or src.watermark[1] < cut:
                return False
        return True


def _finding_rows(findings: Set[Finding]) -> List[Dict[str, Any]]:
    rows = sorted(findings, key=lambda f: (f[0], f[1], -1 if f[2] is None else f[2]))
    return [{"code": c, "subject_id": s, "first_due_tick": d} for c, s, d in rows]


# ---------------------------------------------------------------- entry point
def reconcile(manifest_bytes: bytes, envelope_bytes: Sequence[bytes], as_of: int) -> Dict[str, Any]:
    """Return the closed mci/0.1 report, or the section 3 input_error object."""
    if not _nat(as_of):
        raise ValueError("as_of must be a nonnegative integer")
    failures: List[Tuple[int, bytes]] = []
    manifest: Any = None
    try:
        manifest = _strict_load(manifest_bytes)
        if not _manifest_ok(manifest):
            raise _IngestError("invalid manifest")
    except _IngestError:
        failures.append((-1, manifest_bytes))
    raws = []
    for index, raw in enumerate(envelope_bytes):
        try:
            raws.append(_strict_load(raw))
        except _IngestError:
            failures.append((index, raw))
    if failures:
        index, raw = min(failures, key=lambda f: f[0])
        return {"status": "input_error", "code": "INVALID_RECORD", "input_index": index,
                "raw_sha256": hashlib.sha256(raw).hexdigest()}
    return _Run(manifest, raws).report(as_of)
