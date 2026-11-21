"""Saved document-revision review: pure workflow core (CR-138).

This module holds the frozen workflow text, the bounded case parser, rule
R-DOCREV v0.1, the R01 model-output parser with citation resolution, policy
C-AGREE v0.1, and the workflow definition metadata. It performs no I/O.

Rule, model, and policy results are advisory. Only an explicit human review
records a decision, and that decision confers no authority outside the
review store.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Sequence

ITEM_ID = "revision-approval"
WORKFLOW_KIND = "document-revision-review"
DEFINITION_SCHEMA = "checklist_review.definition.v1"
PROMPT_ID = "P-DOCREV v0.1"
RULE_ID = "R-DOCREV v0.1"
PARSER_ID = "R01 response parsing (run card v0.2-draft)"
POLICY_ID = "C-AGREE v0.1"

MATCH = "match"
MISMATCH = "mismatch"
INSUFFICIENT = "insufficient evidence"
FINDINGS = (MATCH, MISMATCH, INSUFFICIENT)

CASE_LIMIT_BYTES = 8 * 1024
CHAT_REQUEST_LIMIT_BYTES = 32 * 1024
TAGS_DEADLINE_SECONDS = 5.0
TAGS_BODY_LIMIT_BYTES = 256 * 1024
CHAT_DEADLINE_SECONDS = 240.0
CHAT_BODY_LIMIT_BYTES = 64 * 1024
LOOPBACK_ENDPOINT = "http://127.0.0.1:11434"
DEFAULT_OPTIONS = {"temperature": 0, "top_p": 1.0, "seed": 7, "num_predict": 256, "num_ctx": 4096}

# Exact R01 prompt text (run card v0.2-draft, P-DOCREV v0.1). The fixture
# files under tests/fixtures/checklist_review/workflow_docrev_v1/ test this
# identity; `save` freezes these bytes as private artifacts.
SYSTEM_TEXT = (
    "You are checking documents for a review. Use only the text supplied in the user message. "
    "Do not use outside knowledge and do not guess."
)
SYSTEM_TEXT_SHA256 = "69d17c5d1de85bddf0ddd321af7d1471ece6abb9ca60f04dbeb7dd03676df316"

USER_TEMPLATE = """BEGIN INSTRUCTIONS
REVIEW INSTRUCTIONS (the same for every case)

Each case contains a review request (request.txt), a work product (work_product.txt) and one or more source excerpts (S1, S2). Every line begins with a label such as RQ.L03, WP.L02 or S1.L04. Cite lines by these labels exactly as written.

Question for every case: Do the supplied records establish that the document and revision named in the work product's header were approved?

1. Take the document and revision only from the header fields "Document ID:" and "Revision:" in work_product.txt. Do not use titles, file names, approval statements or other text to identify them.
2. Only the source that request.txt names as the controlling source can establish the answer. Other sources, and anything the work product says about itself, are context. Context cannot establish or rule out approval.
3. The controlling source is a table. Each row below the column-header row is one entry. Cells are separated by "|". A cell that is blank or contains only "—" is empty.
4. An entry counts only if its Document ID cell is exactly the Document ID under review, character for character. Entries for any other Document ID do not count, even when the revision, date or wording is similar.
5. Test the findings in this order and give the first that applies:
   match: a counting entry has a Revision exactly equal to the revision under review, its Decision is "Approved", and its Remarks cell is empty or says nothing that qualifies, conditions or limits the approval.
   mismatch: at least one entry counts; every counting entry has a filled Revision cell and a filled Decision cell; and no counting entry names the revision under review. A mismatch means the supplied record names a different revision. It does not show that the revision under review was never approved anywhere.
   insufficient evidence: everything else. Examples: no entry counts; a counting entry has an empty Revision or Decision cell; a counting entry for the revision under review has a Decision or Remarks that leave open whether that revision was approved; a header field is missing or empty; the controlling source is not supplied.
6. Judge only the supplied lines. Do not assume anything about records that were not supplied. A missing record leaves the question unresolved.
7. Report the finding, the labels of the lines it rests on (including the controlling-source line or lines you relied on), and a one-sentence reason.
END INSTRUCTIONS

Answer the question for case {{CASE_ID}} below. Return only one JSON object and no other text, in this form:
{"case_id": "{{CASE_ID}}", "finding": "match or mismatch or insufficient evidence", "cited_lines": ["label", "label"], "reason": "one sentence"}

{{CASE_BLOCK}}"""
USER_TEMPLATE_SHA256 = "4038f3e9de8bb33f58f1da1803951b510176b9f3caa8e3d6dd99f8ee30475176"

INPUT_REASON_CODES = (
    "case_too_large",
    "case_encoding_invalid",
    "case_line_ending_invalid",
    "case_envelope_invalid",
    "case_framing_invalid",
    "case_file_unsupported",
    "case_label_duplicate",
)
RULE_REASON_CODES = (
    "R1_target_field_missing",
    "R2_controlling_source_absent",
    "R3_no_entry_for_document",
    "R4a_exact_entry",
    "R4b_entry_field_missing",
    "R4c_decision_not_approved",
    "R4d_other_revision_only",
)
PARSER_REASON_CODES = (
    "model_output_not_json",
    "model_output_not_object",
    "model_case_id_mismatch",
    "model_finding_invalid",
    "model_citations_invalid",
    "model_reason_invalid",
)
CITATION_RESOLUTIONS = ("all", "some_unresolvable", "none_cited")
GAP_CODES = (
    "target_document_id_missing",
    "target_revision_missing",
    "controlling_source_unnamed",
    "controlling_source_excerpt_absent",
    "controlling_source_table_unreadable",
    "citation_unresolved",
)

_CASE_ID = r"[A-Z]{2,8}-[0-9]{1,4}"
_BEGIN_RE = re.compile(rf"BEGIN CASE ({_CASE_ID})")
_FILE_HEADER_RE = re.compile(r"FILE: (\S+)")
_PREFIX = r"(?:RQ|WP|S[1-9][0-9]?)"
_LABEL_LINE_RE = re.compile(rf"({_PREFIX}\.L[0-9]{{2,3}})  (.*)")
_LABEL_RE = re.compile(rf"({_PREFIX})\.L([0-9]{{2,3}})")
_RANGE_RE = re.compile(rf"({_PREFIX})\.L([0-9]{{2,3}})-({_PREFIX})\.L([0-9]{{2,3}})")
_SOURCE_FILE_RE = re.compile(r"(S[1-9][0-9]?)_[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.txt")
_CONTROLLING_RE = re.compile(r"Controlling source:\s*(S[1-9][0-9]?)\b")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_FIXED_FILES = {"request.txt": "RQ", "work_product.txt": "WP"}
_FENCE_RE = re.compile(r"```(?:json)?\s*\n([\s\S]*?)\n```")
_PLACEHOLDER_RE = re.compile(r"\{\{(CASE_ID|CASE_BLOCK)\}\}")
_WORKFLOW_REF_RE = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_MODEL_TAG_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}")
_DIGEST_RE = re.compile(r"[0-9a-f]{64}")
_REGISTER_COLUMNS = ("Document ID", "Revision", "Decision")


class ChecklistReviewError(Exception):
    """A checklist-review failure carrying only a closed reason code."""

    def __init__(self, reason_code: str) -> None:
        super().__init__(reason_code)
        self.reason_code = reason_code


class CaseInputError(ChecklistReviewError):
    """The supplied case bytes cannot be used; raised before any inference."""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


# --- Case parsing -----------------------------------------------------------


@dataclass(frozen=True)
class CaseLine:
    label: str
    file_name: str
    text: str


@dataclass(frozen=True)
class ReviewCase:
    """A parsed case bound to its exact bytes by digest."""

    case_id: str
    raw: bytes = field(repr=False)
    sha256: str
    block: str = field(repr=False)
    files: tuple[str, ...]
    lines: tuple[CaseLine, ...] = field(repr=False)
    _index: Mapping[str, CaseLine] = field(repr=False, compare=False, default_factory=dict)

    @property
    def labels(self) -> tuple[str, ...]:
        return tuple(line.label for line in self.lines)

    def line(self, label: str) -> Optional[CaseLine]:
        return self._index.get(label)

    def file_for_prefix(self, prefix: str) -> Optional[str]:
        for name in self.files:
            if _file_prefix(name) == prefix:
                return name
        return None

    def lines_with_prefix(self, prefix: str) -> tuple[CaseLine, ...]:
        return tuple(line for line in self.lines if line.label.split(".", 1)[0] == prefix)


def _file_prefix(name: str) -> Optional[str]:
    if name in _FIXED_FILES:
        return _FIXED_FILES[name]
    match = _SOURCE_FILE_RE.fullmatch(name)
    return match.group(1) if match else None


def parse_case(raw: bytes) -> ReviewCase:
    """Parse one bounded UTF-8 case envelope, or raise ``CaseInputError``."""
    if not isinstance(raw, (bytes, bytearray)):
        raise CaseInputError("case_encoding_invalid")
    raw = bytes(raw)
    if len(raw) > CASE_LIMIT_BYTES:
        raise CaseInputError("case_too_large")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise CaseInputError("case_encoding_invalid") from None
    if "\r" in text:
        raise CaseInputError("case_line_ending_invalid")
    block = text[:-1] if text.endswith("\n") else text
    rows = block.split("\n")
    if len(rows) < 2:
        raise CaseInputError("case_envelope_invalid")
    begin = _BEGIN_RE.fullmatch(rows[0])
    if begin is None or rows[-1] != f"END CASE {begin.group(1)}":
        raise CaseInputError("case_envelope_invalid")
    case_id = begin.group(1)
    inner = rows[1:-1]
    if not inner:
        raise CaseInputError("case_framing_invalid")

    files: list[str] = []
    prefixes: set[str] = set()
    lines: list[CaseLine] = []
    index: dict[str, CaseLine] = {}
    position = 0
    while position < len(inner):
        if inner[position] != "---" or position + 2 >= len(inner) or inner[position + 2] != "---":
            raise CaseInputError("case_framing_invalid")
        header = _FILE_HEADER_RE.fullmatch(inner[position + 1])
        if header is None:
            raise CaseInputError("case_framing_invalid")
        name = header.group(1)
        prefix = _file_prefix(name)
        if prefix is None:
            raise CaseInputError("case_file_unsupported")
        if prefix in prefixes:
            raise CaseInputError("case_framing_invalid")
        prefixes.add(prefix)
        files.append(name)
        position += 3
        count = 0
        while position < len(inner) and inner[position] != "---":
            match = _LABEL_LINE_RE.fullmatch(inner[position])
            if match is None or _CONTROL_CHARS_RE.search(inner[position]):
                raise CaseInputError("case_framing_invalid")
            label, line_text = match.groups()
            if label.split(".", 1)[0] != prefix:
                raise CaseInputError("case_framing_invalid")
            if label in index:
                raise CaseInputError("case_label_duplicate")
            line = CaseLine(label=label, file_name=name, text=line_text)
            index[label] = line
            lines.append(line)
            count += 1
            position += 1
        if count == 0:
            raise CaseInputError("case_framing_invalid")

    return ReviewCase(
        case_id=case_id,
        raw=raw,
        sha256=sha256_hex(raw),
        block=block,
        files=tuple(files),
        lines=tuple(lines),
        _index=index,
    )


# --- Rule R-DOCREV v0.1 -----------------------------------------------------


@dataclass(frozen=True)
class ComponentResult:
    """One rule or model result. ``reason_text`` and ``unresolved_citations``
    are model text and never enter persistent metadata."""

    component: str
    status: str
    finding: Optional[str]
    reason_code: Optional[str]
    cited_labels: tuple[str, ...] = ()
    deciding_step: Optional[str] = None
    target_lines: tuple[str, ...] = ()
    kept_rows: tuple[str, ...] = ()
    gaps: tuple[str, ...] = ()
    citation_resolution: Optional[str] = None
    unresolved_citations: tuple[str, ...] = field(default=(), repr=False)
    reason_text: Optional[str] = field(default=None, repr=False)
    case_id: Optional[str] = None

    def to_metadata(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "component": self.component,
            "status": self.status,
            "finding": self.finding,
            "reason_code": self.reason_code,
            "cited_labels": list(self.cited_labels),
            "gaps": list(self.gaps),
            "case_id": self.case_id,
        }
        if self.component == "rule":
            data.update(
                rule_id=RULE_ID,
                deciding_step=self.deciding_step,
                target_lines=list(self.target_lines),
                kept_rows=list(self.kept_rows),
            )
        else:
            data.update(
                parser_id=PARSER_ID,
                citation_resolution=self.citation_resolution,
                unresolved_citation_count=len(self.unresolved_citations),
            )
        return data


def _is_missing(value: Optional[str]) -> bool:
    return value is None or value.strip() in ("", "—")


@dataclass(frozen=True)
class _Target:
    document_id: str
    revision: str
    lines: tuple[str, ...]
    gaps: tuple[str, ...]


def _read_target(case: ReviewCase) -> _Target:
    values = {"Document ID": "", "Revision": ""}
    lines: list[str] = []
    for name in values:
        found = next(
            (line for line in case.lines_with_prefix("WP") if line.text.startswith(name + ":")),
            None,
        )
        if found is not None:
            values[name] = found.text.split(":", 1)[1].strip()
            lines.append(found.label)
    gaps = []
    if _is_missing(values["Document ID"]):
        gaps.append("target_document_id_missing")
    if _is_missing(values["Revision"]):
        gaps.append("target_revision_missing")
    return _Target(values["Document ID"], values["Revision"], tuple(lines), tuple(gaps))


@dataclass(frozen=True)
class _Register:
    prefix: Optional[str]
    file_name: Optional[str]
    gap: Optional[str]
    rows: tuple[tuple[str, Mapping[str, str]], ...] = ()


def _read_register(case: ReviewCase) -> _Register:
    designation = next(
        (line for line in case.lines_with_prefix("RQ") if "Controlling source:" in line.text),
        None,
    )
    match = _CONTROLLING_RE.search(designation.text) if designation else None
    if match is None:
        return _Register(None, None, "controlling_source_unnamed")
    prefix = match.group(1)
    file_name = case.file_for_prefix(prefix)
    if file_name is None:
        return _Register(prefix, None, "controlling_source_excerpt_absent")
    table = [line for line in case.lines_with_prefix(prefix) if "|" in line.text]
    if not table:
        return _Register(prefix, file_name, "controlling_source_table_unreadable")
    headers = [cell.strip() for cell in table[0].text.split("|")]
    if len(set(headers)) != len(headers) or any(column not in headers for column in _REGISTER_COLUMNS):
        return _Register(prefix, file_name, "controlling_source_table_unreadable")
    rows = []
    for line in table[1:]:
        cells = [cell.strip() for cell in line.text.split("|")]
        if len(cells) != len(headers):
            return _Register(prefix, file_name, "controlling_source_table_unreadable")
        rows.append((line.label, dict(zip(headers, cells, strict=True))))
    return _Register(prefix, file_name, None, tuple(rows))


def apply_rule(case: ReviewCase) -> ComponentResult:
    """Apply R-DOCREV v0.1. Remarks are ignored by design, so the result is
    always provisional and review stays available."""
    target = _read_target(case)
    gaps = list(target.gaps)

    def finish(finding: str, code: str, rows: Sequence[str], kept: Sequence[str] = ()) -> ComponentResult:
        cited = tuple(dict.fromkeys([*target.lines, *rows]))
        return ComponentResult(
            component="rule",
            status="valid",
            finding=finding,
            reason_code=code,
            cited_labels=cited,
            deciding_step=code[:2],
            target_lines=target.lines,
            kept_rows=tuple(kept),
            gaps=tuple(gaps),
            case_id=case.case_id,
        )

    if gaps:
        return finish(INSUFFICIENT, "R1_target_field_missing", [])
    register = _read_register(case)
    if register.gap is not None:
        gaps.append(register.gap)
        return finish(INSUFFICIENT, "R2_controlling_source_absent", [])
    kept = [(label, row) for label, row in register.rows if row["Document ID"] == target.document_id]
    kept_labels = [label for label, _ in kept]
    if not kept:
        return finish(INSUFFICIENT, "R3_no_entry_for_document", [label for label, _ in register.rows])
    for label, row in kept:
        if row["Revision"] == target.revision and row["Decision"] == "Approved":
            return finish(MATCH, "R4a_exact_entry", [label], kept_labels)
    for label, row in kept:
        if _is_missing(row["Revision"]) or _is_missing(row["Decision"]):
            return finish(INSUFFICIENT, "R4b_entry_field_missing", [label], kept_labels)
    for label, row in kept:
        if row["Revision"] == target.revision:
            return finish(INSUFFICIENT, "R4c_decision_not_approved", [label], kept_labels)
    return finish(MISMATCH, "R4d_other_revision_only", kept_labels, kept_labels)


@dataclass(frozen=True)
class EvidenceOutline:
    """What an evidence view shows from the recorded case."""

    target_lines: tuple[str, ...]
    document_id: Optional[str]
    controlling_prefix: Optional[str]
    controlling_file: Optional[str]
    register_lines: tuple[str, ...]
    register_rows: tuple[str, ...]
    matching_rows: tuple[str, ...]


def evidence_outline(case: ReviewCase) -> EvidenceOutline:
    target = _read_target(case)
    register = _read_register(case)
    register_lines: tuple[str, ...] = ()
    if register.file_name is not None and register.prefix is not None:
        register_lines = tuple(line.label for line in case.lines_with_prefix(register.prefix))
    document_id = None if _is_missing(target.document_id) else target.document_id
    return EvidenceOutline(
        target_lines=target.lines,
        document_id=document_id,
        controlling_prefix=register.prefix,
        controlling_file=register.file_name,
        register_lines=register_lines,
        register_rows=tuple(label for label, _ in register.rows),
        matching_rows=tuple(
            label for label, row in register.rows if document_id is not None and row["Document ID"] == document_id
        ),
    )


# --- Model output (R01 parsing rule) and citations --------------------------


def _reject_constant(name: str) -> Any:
    raise ValueError(name)


def resolve_citations(case: ReviewCase, entries: Sequence[str]) -> tuple[tuple[str, ...], tuple[str, ...], str]:
    """Resolve single labels and same-source ranges against the recorded case only."""
    resolved: list[str] = []
    unresolved: list[str] = []
    for entry in entries:
        key = entry.strip()
        if case.line(key) is not None:
            resolved.append(key)
            continue
        span = _range_labels(case, key)
        if span:
            resolved.extend(span)
        else:
            unresolved.append(entry)
    if not entries:
        resolution = "none_cited"
    elif unresolved:
        resolution = "some_unresolvable"
    else:
        resolution = "all"
    return tuple(dict.fromkeys(resolved)), tuple(unresolved), resolution


def _range_labels(case: ReviewCase, key: str) -> tuple[str, ...]:
    match = _RANGE_RE.fullmatch(key)
    if match is None or match.group(1) != match.group(3):
        return ()
    prefix = match.group(1)
    first, last = f"{prefix}.L{match.group(2)}", f"{prefix}.L{match.group(4)}"
    start, end = int(match.group(2)), int(match.group(4))
    if case.line(first) is None or case.line(last) is None or start > end:
        return ()
    return tuple(
        line.label
        for line in case.lines_with_prefix(prefix)
        if start <= int(_LABEL_RE.fullmatch(line.label).group(2)) <= end
    )


def parse_model_result(case: ReviewCase, raw: str) -> ComponentResult:
    """Parse one completed model reply with the R01 run card's rule."""

    def invalid(code: str) -> ComponentResult:
        return ComponentResult(component="model", status="invalid", finding=None, reason_code=code, case_id=case.case_id)

    if not isinstance(raw, str):
        return invalid("model_output_not_json")
    text = raw.strip()
    fenced = _FENCE_RE.fullmatch(text)
    if fenced:
        text = fenced.group(1)
    try:
        value = json.loads(text, parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        return invalid("model_output_not_json")
    if not isinstance(value, dict):
        return invalid("model_output_not_object")
    if value.get("case_id") != case.case_id:
        return invalid("model_case_id_mismatch")
    finding = value.get("finding")
    if not isinstance(finding, str) or finding.strip().lower() not in FINDINGS:
        return invalid("model_finding_invalid")
    cited = value.get("cited_lines")
    if not isinstance(cited, list) or not all(isinstance(entry, str) for entry in cited):
        return invalid("model_citations_invalid")
    reason = value.get("reason")
    if not isinstance(reason, str):
        return invalid("model_reason_invalid")
    labels, unresolved, resolution = resolve_citations(case, cited)
    return ComponentResult(
        component="model",
        status="valid",
        finding=finding.strip().lower(),
        reason_code=None,
        cited_labels=labels,
        gaps=("citation_unresolved",) if unresolved else (),
        citation_resolution=resolution,
        unresolved_citations=unresolved,
        reason_text=reason,
        case_id=case.case_id,
    )


# --- Policy C-AGREE v0.1 ----------------------------------------------------


@dataclass(frozen=True)
class PolicyResult:
    finding: str
    agreement: str
    review_needed: bool
    reason_code: str
    rule_finding: Optional[str]
    model_finding: Optional[str]
    evidence_status: str = "unassessed"

    def to_metadata(self) -> dict[str, Any]:
        return {
            "policy_id": POLICY_ID,
            "finding": self.finding,
            "agreement": self.agreement,
            "review_needed": self.review_needed,
            "reason_code": self.reason_code,
            "rule_finding": self.rule_finding,
            "model_finding": self.model_finding,
            "evidence_status": self.evidence_status,
        }


def combine(rule: ComponentResult, model: ComponentResult) -> PolicyResult:
    """C-AGREE v0.1: agreement keeps the shared finding; anything else abstains.
    Agreement never marks the evidence as assessed."""
    if rule.status != "valid" or model.status != "valid":
        return PolicyResult(INSUFFICIENT, "model_invalid", True, "C1_model_invalid", rule.finding, model.finding)
    if rule.finding == model.finding:
        return PolicyResult(rule.finding, "agreed", False, "C1_agreement", rule.finding, model.finding)
    return PolicyResult(INSUFFICIENT, "disagreed", True, "C1_disagreement", rule.finding, model.finding)


# --- Rendering and the chat request -----------------------------------------


def render_user_message(case: ReviewCase, template: str = USER_TEMPLATE) -> str:
    values = {"CASE_ID": case.case_id, "CASE_BLOCK": case.block}
    return _PLACEHOLDER_RE.sub(lambda match: values[match.group(1)], template)


def build_chat_request(
    *,
    model_tag: str,
    case: ReviewCase,
    system_text: str = SYSTEM_TEXT,
    user_template: str = USER_TEMPLATE,
    options: Optional[Mapping[str, Any]] = None,
    think: bool = False,
    stream: bool = False,
) -> bytes:
    """Serialize the exact two-message chat request for one candidate case."""
    payload = {
        "model": model_tag,
        "messages": [
            {"role": "system", "content": system_text},
            {"role": "user", "content": render_user_message(case, user_template)},
        ],
        "options": dict(DEFAULT_OPTIONS if options is None else options),
        "think": think,
        "stream": stream,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


# --- Workflow definition ----------------------------------------------------


def validate_workflow_ref(ref: str) -> str:
    if not isinstance(ref, str) or not _WORKFLOW_REF_RE.fullmatch(ref):
        raise ChecklistReviewError("workflow_ref_invalid")
    return ref


def validate_model_identity(model_tag: str, model_digest: str) -> None:
    if not isinstance(model_tag, str) or not _MODEL_TAG_RE.fullmatch(model_tag):
        raise ChecklistReviewError("model_tag_invalid")
    if not isinstance(model_digest, str) or not _DIGEST_RE.fullmatch(model_digest):
        raise ChecklistReviewError("model_digest_invalid")


def is_sha256_hex(value: Any) -> bool:
    return isinstance(value, str) and bool(_DIGEST_RE.fullmatch(value))


def build_definition(
    *,
    model_tag: str,
    model_digest: str,
    system_text_artifact_id: str,
    user_template_artifact_id: str,
) -> dict[str, Any]:
    """Definition metadata: template references and digests, rule, parser,
    policy, model profile, and limits. No template text."""
    validate_model_identity(model_tag, model_digest)
    return {
        "schema": DEFINITION_SCHEMA,
        "workflow_kind": WORKFLOW_KIND,
        "prompt_id": PROMPT_ID,
        "system_text": {
            "artifact_id": system_text_artifact_id,
            "sha256": SYSTEM_TEXT_SHA256,
            "size_bytes": len(SYSTEM_TEXT.encode("utf-8")),
        },
        "user_template": {
            "artifact_id": user_template_artifact_id,
            "sha256": USER_TEMPLATE_SHA256,
            "size_bytes": len(USER_TEMPLATE.encode("utf-8")),
        },
        "rule_id": RULE_ID,
        "parser_id": PARSER_ID,
        "policy_id": POLICY_ID,
        "item_id": ITEM_ID,
        "model_profile": {
            "provider": "ollama",
            "endpoint": LOOPBACK_ENDPOINT,
            "tag": model_tag,
            "expected_digest": model_digest,
            "request_settings": {"options": dict(DEFAULT_OPTIONS), "think": False, "stream": False},
        },
        "limits": {
            "case_bytes": CASE_LIMIT_BYTES,
            "chat_request_bytes": CHAT_REQUEST_LIMIT_BYTES,
            "tags_deadline_s": TAGS_DEADLINE_SECONDS,
            "tags_body_bytes": TAGS_BODY_LIMIT_BYTES,
            "chat_deadline_s": CHAT_DEADLINE_SECONDS,
            "chat_body_bytes": CHAT_BODY_LIMIT_BYTES,
        },
    }


def definition_digest(definition: Mapping[str, Any]) -> str:
    return sha256_hex(canonical_json_bytes(definition))


def definition_content_key(definition: Mapping[str, Any]) -> str:
    """Digest of a definition with its artifact IDs removed, used to decide
    whether a repeated save is identical."""
    content = json.loads(json.dumps(definition))
    for name in ("system_text", "user_template"):
        content[name].pop("artifact_id", None)
    return definition_digest(content)
