"""Immutable, non-integrated input snapshots for governed runs.

This module deliberately has no CLI, configuration, ledger, router, backend,
or artifact dependencies.  CR-DD-012B, not this module, owns integration.
"""

from __future__ import annotations

import codecs
import hashlib
import io
import os
import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields
from typing import Optional, Union


SNAPSHOT_CONTRACT_VERSION = "governed_run_input_snapshot.v1"
ASSEMBLY_CONTRACT_VERSION = "tc_run_worker_user_message.v1"
DECODE_NEWLINE_CONTRACT_VERSION = "tc_run_utf8_universal_newline.v1"
PROFILE_RESOLUTION_VERSION = "governed_run_profile_resolution.v1"
CONSTRUCTION_LIMITS_VERSION = "governed_run_snapshot_construction_limits.v1"
EXECUTION_DATA_SEPARATOR = b"\n\nDATA:\n"

_MAX_CHECKED_LENGTH = (1 << 63) - 1
_SHA256_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
_LOCATOR_DOMAIN = b"triagecore.governed_run_snapshot.source_locator.v1\x00"
_READ_CHUNK_SIZE = 64 * 1024
_DECODE_CHUNK_SIZE = 64 * 1024


class SnapshotError(ValueError):
    """Base class for fail-closed snapshot errors."""


class SnapshotLimitError(SnapshotError):
    """A finite construction bound was invalid or exceeded."""


class SnapshotValidationError(SnapshotError):
    """Snapshot input or an immutable value was malformed."""


def _require_int(value: object, name: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum or value > _MAX_CHECKED_LENGTH:
        qualifier = "positive" if minimum == 1 else "non-negative"
        raise SnapshotValidationError(
            f"{name} must be a finite {qualifier} integer"
        )
    return value


def _require_positive_limit(value: object, name: str) -> int:
    try:
        return _require_int(value, name, minimum=1)
    except SnapshotValidationError as exc:
        raise SnapshotLimitError(str(exc)) from None


def _require_identifier(value: object, name: str) -> str:
    if type(value) is not str or not _IDENTIFIER_RE.fullmatch(value):
        raise SnapshotValidationError(f"{name} is not a supported identifier")
    return value


def _require_task_id(value: object) -> str:
    if type(value) is not str or not value:
        raise SnapshotValidationError("explicit task ID must be bounded identifier text")
    try:
        encoded_length = 0
        for chunk in _utf8_chunks(value):
            encoded_length += len(chunk)
            if encoded_length > 512:
                raise SnapshotValidationError(
                    "explicit task ID must be bounded identifier text"
                )
    except UnicodeEncodeError:
        raise SnapshotValidationError(
            "explicit task ID must be bounded identifier text"
        ) from None
    for index, character in enumerate(value):
        category = unicodedata.category(character)
        allowed = category[0] in {"L", "M", "N"} or character in "._:+-"
        if not allowed or (index == 0 and category[0] not in {"L", "N"}):
            raise SnapshotValidationError(
                "explicit task ID must be bounded identifier text"
            )
    return value


def _require_digest(value: object, name: str) -> str:
    if type(value) is not str or not _SHA256_RE.fullmatch(value):
        raise SnapshotValidationError(f"{name} must be a lower-case SHA-256 digest")
    return value


def sha256_digest(value: bytes) -> str:
    if type(value) is not bytes:
        raise TypeError("sha256_digest requires bytes")
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _locator_digest(path_spelling: str) -> str:
    digest = hashlib.sha256()
    digest.update(_LOCATOR_DOMAIN)
    for chunk in _utf8_chunks(path_spelling):
        digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _checked_add(total: int, increment: int, limit: int, name: str) -> int:
    if increment < 0 or total < 0 or total > _MAX_CHECKED_LENGTH - increment:
        raise SnapshotLimitError(f"{name} length overflow")
    result = total + increment
    if result > limit:
        raise SnapshotLimitError(f"{name} exceeds its finite byte bound")
    return result


def _owned_path_spelling(value: object) -> str:
    try:
        spelling = os.fspath(value)
    except TypeError:
        raise SnapshotValidationError("source path must be a string or path-like") from None
    if type(spelling) is not str:
        raise SnapshotValidationError("source path must resolve to text, not bytes")
    _validate_text_utf8(spelling, "source path")
    return spelling[:]


def _utf8_chunks(text: str) -> Iterable[bytes]:
    encoder = codecs.getincrementalencoder("utf-8")("strict")
    for offset in range(0, len(text), _DECODE_CHUNK_SIZE):
        chunk = encoder.encode(text[offset : offset + _DECODE_CHUNK_SIZE], final=False)
        if chunk:
            yield chunk
    tail = encoder.encode("", final=True)
    if tail:
        yield tail


def _validate_text_utf8(text: object, name: str) -> str:
    if type(text) is not str:
        raise SnapshotValidationError(f"{name} must be text")
    try:
        for _ in _utf8_chunks(text):
            pass
    except UnicodeEncodeError:
        raise SnapshotValidationError(f"{name} is not strict UTF-8 text") from None
    return text


def _bounded_utf8(text: object, limit: int, name: str) -> bytes:
    text = _validate_text_utf8(text, name)
    length = 0
    for chunk in _utf8_chunks(text):
        length = _checked_add(length, len(chunk), limit, name)
    return text.encode("utf-8", "strict")


def _bounded_header(path_spelling: str, limit: int) -> bytes:
    prefix = b"\n--- "
    suffix = b" ---\n"
    length = _checked_add(0, len(prefix), limit, "normalized source component")
    for chunk in _utf8_chunks(path_spelling):
        length = _checked_add(
            length, len(chunk), limit, "normalized source component"
        )
    length = _checked_add(
        length, len(suffix), limit, "normalized source component"
    )
    output = bytearray(length)
    output[: len(prefix)] = prefix
    cursor = len(prefix)
    for chunk in _utf8_chunks(path_spelling):
        output[cursor : cursor + len(chunk)] = chunk
        cursor += len(chunk)
    output[cursor : cursor + len(suffix)] = suffix
    return bytes(output)


def _normalized_chunks(raw: bytes) -> Iterable[bytes]:
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    newline_decoder = io.IncrementalNewlineDecoder(decoder, translate=True)
    for offset in range(0, len(raw), _DECODE_CHUNK_SIZE):
        text = newline_decoder.decode(raw[offset : offset + _DECODE_CHUNK_SIZE])
        if text:
            yield text.encode("utf-8", "strict")
    tail = newline_decoder.decode(b"", final=True)
    if tail:
        yield tail.encode("utf-8", "strict")


def _measure_normalized(raw: bytes, limit: int) -> tuple[int, str]:
    length = 0
    digest = hashlib.sha256()
    try:
        for chunk in _normalized_chunks(raw):
            length = _checked_add(length, len(chunk), limit, "normalized source")
            digest.update(chunk)
    except UnicodeDecodeError:
        raise SnapshotValidationError("source input is not strict UTF-8") from None
    return length, "sha256:" + digest.hexdigest()


def _materialize_component(header: bytes, raw: bytes, content_length: int) -> bytes:
    output = bytearray(len(header) + content_length)
    output[: len(header)] = header
    cursor = len(header)
    try:
        for chunk in _normalized_chunks(raw):
            output[cursor : cursor + len(chunk)] = chunk
            cursor += len(chunk)
    except UnicodeDecodeError:
        raise SnapshotValidationError("source input is not strict UTF-8") from None
    if cursor != len(output):
        raise SnapshotValidationError("normalized source length changed during construction")
    return bytes(output)


@dataclass(frozen=True, slots=True)
class SnapshotConstructionLimits:
    max_source_count: int
    max_instruction_bytes: int
    max_inline_input_bytes: int
    max_source_bytes_per_source: int
    max_total_source_bytes: int
    max_normalized_component_bytes_per_source: int
    max_total_normalized_component_bytes: int
    max_task_data_bytes: int
    max_assembled_execution_bytes: int
    max_retained_source_bytes_per_source: Optional[int] = None
    max_total_retained_source_bytes: Optional[int] = None
    contract_version: str = CONSTRUCTION_LIMITS_VERSION

    def __post_init__(self) -> None:
        if (
            type(self.contract_version) is not str
            or self.contract_version != CONSTRUCTION_LIMITS_VERSION
        ):
            raise SnapshotLimitError("unsupported construction-limits version")
        mandatory = (
            "max_source_count",
            "max_instruction_bytes",
            "max_inline_input_bytes",
            "max_source_bytes_per_source",
            "max_total_source_bytes",
            "max_normalized_component_bytes_per_source",
            "max_total_normalized_component_bytes",
            "max_task_data_bytes",
            "max_assembled_execution_bytes",
        )
        for name in mandatory:
            _require_positive_limit(getattr(self, name), name)
        if self.max_total_source_bytes < self.max_source_bytes_per_source:
            raise SnapshotLimitError("total source bound is smaller than per-source bound")
        if (
            self.max_total_normalized_component_bytes
            < self.max_normalized_component_bytes_per_source
        ):
            raise SnapshotLimitError(
                "total normalized-component bound is smaller than per-source bound"
            )
        optional = (
            self.max_retained_source_bytes_per_source,
            self.max_total_retained_source_bytes,
        )
        if (optional[0] is None) != (optional[1] is None):
            raise SnapshotLimitError("raw-source retention bounds must be supplied together")
        if optional[0] is not None:
            _require_positive_limit(optional[0], "max_retained_source_bytes_per_source")
            _require_positive_limit(optional[1], "max_total_retained_source_bytes")
            if optional[1] < optional[0]:
                raise SnapshotLimitError(
                    "total retained-source bound is smaller than per-source bound"
                )
        if self.max_assembled_execution_bytes < len(EXECUTION_DATA_SEPARATOR):
            raise SnapshotLimitError(
                "assembled-execution bound cannot fit the required separator"
            )

    @property
    def sha256(self) -> str:
        lines = [self.contract_version]
        for item in fields(self):
            if item.name == "contract_version":
                continue
            value = getattr(self, item.name)
            rendered = "absent" if value is None else str(value)
            lines.append(f"{item.name}={rendered}")
        return sha256_digest(("\n".join(lines)).encode("ascii"))


@dataclass(frozen=True, slots=True)
class SourceBytesInput:
    path_spelling: str
    source_bytes: bytes

    def __post_init__(self) -> None:
        if type(self.path_spelling) is not str:
            raise SnapshotValidationError("path_spelling must be text")
        _validate_text_utf8(self.path_spelling, "path_spelling")
        if type(self.source_bytes) is not bytes:
            raise SnapshotValidationError("source_bytes must be immutable bytes")

    @classmethod
    def from_bytes(
        cls,
        path: object,
        source_bytes: Union[bytes, bytearray, memoryview],
        *,
        max_bytes: int,
    ) -> "SourceBytesInput":
        bound = _require_positive_limit(max_bytes, "max_bytes")
        if not isinstance(source_bytes, (bytes, bytearray, memoryview)):
            raise SnapshotValidationError("source input must support immutable byte capture")
        size = source_bytes.nbytes if isinstance(source_bytes, memoryview) else len(source_bytes)
        if size > bound:
            raise SnapshotLimitError("source input exceeds its finite byte bound")
        return cls(_owned_path_spelling(path), bytes(source_bytes))

    @classmethod
    def read(cls, path: object, *, max_bytes: int) -> "SourceBytesInput":
        bound = _require_positive_limit(max_bytes, "max_bytes")
        spelling = _owned_path_spelling(path)
        captured = bytearray()
        with open(spelling, "rb") as handle:
            while True:
                remaining = bound - len(captured)
                chunk = handle.read(min(_READ_CHUNK_SIZE, remaining + 1))
                if not chunk:
                    break
                if len(chunk) > remaining:
                    raise SnapshotLimitError("source input exceeds its finite byte bound")
                captured.extend(chunk)
        return cls(spelling, bytes(captured))


@dataclass(frozen=True, slots=True)
class ContextModelProfile:
    profile_id: str
    context_window_tokens: int
    reserved_output_tokens: int
    safety_margin_tokens: int
    resolution_version: str = PROFILE_RESOLUTION_VERSION

    def __post_init__(self) -> None:
        _require_identifier(self.profile_id, "profile_id")
        _require_int(self.context_window_tokens, "context_window_tokens", minimum=1)
        _require_int(
            self.reserved_output_tokens, "reserved_output_tokens", minimum=0
        )
        _require_int(self.safety_margin_tokens, "safety_margin_tokens", minimum=0)
        if (
            type(self.resolution_version) is not str
            or self.resolution_version != PROFILE_RESOLUTION_VERSION
        ):
            raise SnapshotValidationError("unsupported profile-resolution version")
        if self.usable_input_tokens <= 0:
            raise SnapshotValidationError("usable_input_tokens must be positive")

    @property
    def usable_input_tokens(self) -> int:
        return (
            self.context_window_tokens
            - self.reserved_output_tokens
            - self.safety_margin_tokens
        )


def resolve_context_model_profile(
    requested_profile: Optional[str],
    *,
    default_profile: str,
    profiles: Mapping[str, ContextModelProfile],
) -> ContextModelProfile:
    _require_identifier(default_profile, "default_profile")
    if requested_profile is not None:
        _require_identifier(requested_profile, "requested_profile")
    if not isinstance(profiles, Mapping):
        raise SnapshotValidationError("profiles must be an explicit mapping")
    copied = tuple(profiles.items())
    canonical: dict[str, ContextModelProfile] = {}
    choices: dict[str, ContextModelProfile] = {}
    for spelling, profile in copied:
        _require_identifier(spelling, "profile spelling")
        if type(profile) is not ContextModelProfile:
            raise SnapshotValidationError("profile mapping values must be frozen profiles")
        previous = canonical.get(profile.profile_id)
        if previous is not None and previous != profile:
            raise SnapshotValidationError("ambiguous canonical profile definition")
        canonical[profile.profile_id] = profile
        choices[spelling] = profile
    if default_profile not in choices:
        raise SnapshotValidationError("unknown default context/model profile")
    selected_spelling = default_profile if requested_profile is None else requested_profile
    if selected_spelling not in choices:
        raise SnapshotValidationError("unknown context/model profile")
    selected = choices[selected_spelling]
    return ContextModelProfile(
        selected.profile_id,
        selected.context_window_tokens,
        selected.reserved_output_tokens,
        selected.safety_margin_tokens,
        selected.resolution_version,
    )


@dataclass(frozen=True, slots=True)
class NormalizedOperatorDeclarations:
    task_id_posture: str
    task_id: Optional[str]
    declared_privacy: str
    cloud_intent: bool
    requested_profile: str

    def __post_init__(self) -> None:
        if (
            type(self.task_id_posture) is not str
            or self.task_id_posture not in {"explicit", "implicit_unassigned"}
        ):
            raise SnapshotValidationError("unsupported task-id posture")
        if self.task_id_posture == "implicit_unassigned":
            if self.task_id is not None:
                raise SnapshotValidationError("implicit task posture cannot carry a task ID")
        else:
            _require_task_id(self.task_id)
        if (
            type(self.declared_privacy) is not str
            or self.declared_privacy not in {"local_only", "external_safe", "public"}
        ):
            raise SnapshotValidationError("unsupported declared privacy")
        if type(self.cloud_intent) is not bool:
            raise SnapshotValidationError("cloud_intent must be boolean")
        _require_identifier(self.requested_profile, "requested_profile")


def normalize_operator_declarations(
    *,
    task_id: Optional[str],
    declared_privacy: str,
    cloud_intent: bool,
    resolved_profile: ContextModelProfile,
) -> NormalizedOperatorDeclarations:
    if type(resolved_profile) is not ContextModelProfile:
        raise SnapshotValidationError("resolved_profile must be immutable")
    posture = "implicit_unassigned" if task_id is None else "explicit"
    return NormalizedOperatorDeclarations(
        task_id_posture=posture,
        task_id=task_id[:] if type(task_id) is str else task_id,
        declared_privacy=declared_privacy,
        cloud_intent=cloud_intent,
        requested_profile=resolved_profile.profile_id,
    )


@dataclass(frozen=True, slots=True)
class WorkerSystemMessageBinding:
    version: str
    sha256: str

    def __post_init__(self) -> None:
        _require_identifier(self.version, "worker system-message version")
        _require_digest(self.sha256, "worker system-message digest")


@dataclass(frozen=True, slots=True)
class DigestLengthBinding:
    sha256: str
    byte_length: int

    def __post_init__(self) -> None:
        _require_digest(self.sha256, "digest")
        _require_int(self.byte_length, "byte_length", minimum=0)


@dataclass(frozen=True, slots=True)
class SourceDecisionBinding:
    position: int
    locator_sha256: str
    source_sha256: Optional[str]
    source_byte_length: Optional[int]
    normalized_sha256: str
    normalized_byte_length: int
    component_sha256: str
    component_byte_length: int
    decode_newline_contract_version: str

    def __post_init__(self) -> None:
        _require_int(self.position, "source position", minimum=0)
        _require_digest(self.locator_sha256, "source locator digest")
        if (self.source_sha256 is None) != (self.source_byte_length is None):
            raise SnapshotValidationError("source provenance binding is inconsistent")
        if self.source_sha256 is not None:
            _require_digest(self.source_sha256, "source digest")
            _require_int(self.source_byte_length, "source byte length", minimum=0)
        _require_digest(self.normalized_sha256, "normalized source digest")
        _require_int(
            self.normalized_byte_length,
            "normalized source byte length",
            minimum=0,
        )
        _require_digest(self.component_sha256, "source component digest")
        _require_int(
            self.component_byte_length,
            "source component byte length",
            minimum=0,
        )
        if (
            type(self.decode_newline_contract_version) is not str
            or self.decode_newline_contract_version
            != DECODE_NEWLINE_CONTRACT_VERSION
        ):
            raise SnapshotValidationError("unsupported source decode/newline contract")


@dataclass(frozen=True, slots=True)
class SnapshotDecisionBinding:
    snapshot_contract_version: str
    assembly_contract_version: str
    instruction: DigestLengthBinding
    inline_input: DigestLengthBinding
    inline_input_posture: str
    sources: tuple[SourceDecisionBinding, ...]
    task_data: DigestLengthBinding
    assembled_execution: DigestLengthBinding
    task_id_posture: str
    task_id: Optional[str]
    declared_privacy: str
    cloud_intent: str
    requested_profile: str
    resolved_profile_id: str
    profile_resolution_version: str
    construction_limits_sha256: str
    worker_system_message_version: str
    worker_system_message_sha256: str

    def __post_init__(self) -> None:
        if type(self.sources) is not tuple or any(
            type(source) is not SourceDecisionBinding for source in self.sources
        ):
            raise SnapshotValidationError(
                "decision source bindings must be an immutable tuple"
            )
        if tuple(source.position for source in self.sources) != tuple(
            range(len(self.sources))
        ):
            raise SnapshotValidationError(
                "decision source positions must preserve exact order"
            )


@dataclass(frozen=True, slots=True)
class SourceSnapshot:
    position: int
    path_spelling: str
    locator_sha256: str
    source_bytes: Optional[bytes]
    source_sha256: str
    source_byte_length: int
    normalized_sha256: str
    normalized_byte_length: int
    normalized_component_bytes: bytes
    component_sha256: str
    component_byte_length: int
    decode_newline_contract_version: str = DECODE_NEWLINE_CONTRACT_VERSION

    def __post_init__(self) -> None:
        _require_int(self.position, "source position", minimum=0)
        if type(self.path_spelling) is not str:
            raise SnapshotValidationError("path_spelling must be text")
        _require_digest(self.locator_sha256, "locator_sha256")
        if self.locator_sha256 != _locator_digest(self.path_spelling):
            raise SnapshotValidationError("source locator digest mismatch")
        _require_digest(self.source_sha256, "source_sha256")
        _require_int(self.source_byte_length, "source_byte_length", minimum=0)
        if self.source_bytes is not None:
            if type(self.source_bytes) is not bytes:
                raise SnapshotValidationError("retained source input must be bytes")
            if len(self.source_bytes) != self.source_byte_length:
                raise SnapshotValidationError("retained source length mismatch")
            if sha256_digest(self.source_bytes) != self.source_sha256:
                raise SnapshotValidationError("retained source digest mismatch")
        _require_digest(self.normalized_sha256, "normalized_sha256")
        _require_int(self.normalized_byte_length, "normalized_byte_length", minimum=0)
        if type(self.normalized_component_bytes) is not bytes:
            raise SnapshotValidationError("normalized component must be bytes")
        _require_int(self.component_byte_length, "component_byte_length", minimum=0)
        if self.normalized_byte_length > self.component_byte_length:
            raise SnapshotValidationError("normalized source length is inconsistent")
        header = _bounded_header(
            self.path_spelling,
            self.component_byte_length - self.normalized_byte_length,
        )
        if not self.normalized_component_bytes.startswith(header):
            raise SnapshotValidationError("normalized component header mismatch")
        content = memoryview(self.normalized_component_bytes)[len(header) :]
        if len(content) != self.normalized_byte_length:
            raise SnapshotValidationError("normalized content length mismatch")
        if "sha256:" + hashlib.sha256(content).hexdigest() != self.normalized_sha256:
            raise SnapshotValidationError("normalized content digest mismatch")
        _require_digest(self.component_sha256, "component_sha256")
        if self.component_byte_length != len(self.normalized_component_bytes):
            raise SnapshotValidationError("component length mismatch")
        if sha256_digest(self.normalized_component_bytes) != self.component_sha256:
            raise SnapshotValidationError("component digest mismatch")
        if self.decode_newline_contract_version != DECODE_NEWLINE_CONTRACT_VERSION:
            raise SnapshotValidationError("unsupported source decode/newline contract")

    def to_decision_binding(self) -> SourceDecisionBinding:
        return SourceDecisionBinding(
            position=self.position,
            locator_sha256=self.locator_sha256,
            source_sha256=self.source_sha256,
            source_byte_length=self.source_byte_length,
            normalized_sha256=self.normalized_sha256,
            normalized_byte_length=self.normalized_byte_length,
            component_sha256=self.component_sha256,
            component_byte_length=self.component_byte_length,
            decode_newline_contract_version=self.decode_newline_contract_version,
        )


def _segments_equal(value: bytes, segments: Iterable[bytes]) -> bool:
    view = memoryview(value)
    cursor = 0
    for segment in segments:
        end = cursor + len(segment)
        if end > len(view) or view[cursor:end] != memoryview(segment):
            return False
        cursor = end
    return cursor == len(view)


@dataclass(frozen=True, slots=True)
class GovernedRunInputSnapshot:
    snapshot_contract_version: str
    assembly_contract_version: str
    instruction_bytes: bytes
    instruction_sha256: str
    instruction_byte_length: int
    inline_input_present: bool
    inline_input_bytes: bytes
    inline_input_sha256: str
    inline_input_byte_length: int
    sources: tuple[SourceSnapshot, ...]
    task_data_bytes: bytes
    task_data_sha256: str
    task_data_byte_length: int
    assembled_execution_bytes: bytes
    assembled_execution_sha256: str
    assembled_execution_byte_length: int
    declarations: NormalizedOperatorDeclarations
    resolved_profile: ContextModelProfile
    worker_system_message: WorkerSystemMessageBinding
    construction_limits: SnapshotConstructionLimits
    retains_source_bytes: bool

    def __post_init__(self) -> None:
        if (
            type(self.snapshot_contract_version) is not str
            or self.snapshot_contract_version != SNAPSHOT_CONTRACT_VERSION
        ):
            raise SnapshotValidationError("unsupported snapshot contract")
        if (
            type(self.assembly_contract_version) is not str
            or self.assembly_contract_version != ASSEMBLY_CONTRACT_VERSION
        ):
            raise SnapshotValidationError("unsupported assembly contract")
        for name in (
            "instruction_bytes",
            "inline_input_bytes",
            "task_data_bytes",
            "assembled_execution_bytes",
        ):
            if type(getattr(self, name)) is not bytes:
                raise SnapshotValidationError(f"{name} must be bytes")
        for value, digest, length, label in (
            (
                self.instruction_bytes,
                self.instruction_sha256,
                self.instruction_byte_length,
                "instruction",
            ),
            (
                self.inline_input_bytes,
                self.inline_input_sha256,
                self.inline_input_byte_length,
                "inline input",
            ),
            (
                self.task_data_bytes,
                self.task_data_sha256,
                self.task_data_byte_length,
                "task data",
            ),
            (
                self.assembled_execution_bytes,
                self.assembled_execution_sha256,
                self.assembled_execution_byte_length,
                "assembled execution",
            ),
        ):
            if len(value) != length or sha256_digest(value) != digest:
                raise SnapshotValidationError(f"{label} digest/length mismatch")
        if type(self.inline_input_present) is not bool:
            raise SnapshotValidationError("inline_input_present must be boolean")
        if self.inline_input_present != bool(self.inline_input_bytes):
            raise SnapshotValidationError("inline input posture mismatch")
        if type(self.sources) is not tuple or any(
            type(source) is not SourceSnapshot for source in self.sources
        ):
            raise SnapshotValidationError("sources must be an immutable source tuple")
        if tuple(source.position for source in self.sources) != tuple(
            range(len(self.sources))
        ):
            raise SnapshotValidationError("source positions must preserve exact order")
        expected_task_segments = tuple(
            source.normalized_component_bytes for source in self.sources
        ) + ((self.inline_input_bytes,) if self.inline_input_present else ())
        if not _segments_equal(self.task_data_bytes, expected_task_segments):
            raise SnapshotValidationError("task-data assembly mismatch")
        if not _segments_equal(
            self.assembled_execution_bytes,
            (self.instruction_bytes, EXECUTION_DATA_SEPARATOR, self.task_data_bytes),
        ):
            raise SnapshotValidationError("assembled execution bytes mismatch")
        if type(self.declarations) is not NormalizedOperatorDeclarations:
            raise SnapshotValidationError("declarations must be immutable")
        if type(self.resolved_profile) is not ContextModelProfile:
            raise SnapshotValidationError("resolved profile must be immutable")
        if self.declarations.requested_profile != self.resolved_profile.profile_id:
            raise SnapshotValidationError("declaration/profile mismatch")
        if type(self.worker_system_message) is not WorkerSystemMessageBinding:
            raise SnapshotValidationError("worker system-message binding must be immutable")
        if type(self.construction_limits) is not SnapshotConstructionLimits:
            raise SnapshotValidationError("construction limits must be immutable")
        if type(self.retains_source_bytes) is not bool:
            raise SnapshotValidationError("retains_source_bytes must be boolean")
        if any(
            (source.source_bytes is not None) != self.retains_source_bytes
            for source in self.sources
        ):
            raise SnapshotValidationError("raw-source retention posture mismatch")
        limits = self.construction_limits
        if len(self.sources) > limits.max_source_count:
            raise SnapshotValidationError("source count exceeds construction binding")
        if self.instruction_byte_length > limits.max_instruction_bytes:
            raise SnapshotValidationError("instruction exceeds construction binding")
        if self.inline_input_byte_length > limits.max_inline_input_bytes:
            raise SnapshotValidationError("inline input exceeds construction binding")
        if self.task_data_byte_length > limits.max_task_data_bytes:
            raise SnapshotValidationError("task data exceeds construction binding")
        if (
            self.assembled_execution_byte_length
            > limits.max_assembled_execution_bytes
        ):
            raise SnapshotValidationError(
                "assembled execution exceeds construction binding"
            )
        total_source = 0
        total_component = 0
        total_retained = 0
        for source in self.sources:
            if source.source_byte_length > limits.max_source_bytes_per_source:
                raise SnapshotValidationError("source exceeds construction binding")
            total_source = _checked_add(
                total_source,
                source.source_byte_length,
                limits.max_total_source_bytes,
                "total source input",
            )
            if (
                source.component_byte_length
                > limits.max_normalized_component_bytes_per_source
            ):
                raise SnapshotValidationError(
                    "source component exceeds construction binding"
                )
            total_component = _checked_add(
                total_component,
                source.component_byte_length,
                limits.max_total_normalized_component_bytes,
                "total normalized source components",
            )
            if self.retains_source_bytes:
                if (
                    limits.max_retained_source_bytes_per_source is None
                    or limits.max_total_retained_source_bytes is None
                ):
                    raise SnapshotValidationError(
                        "raw-source retention lacks construction bounds"
                    )
                if (
                    source.source_byte_length
                    > limits.max_retained_source_bytes_per_source
                ):
                    raise SnapshotValidationError(
                        "retained source exceeds construction binding"
                    )
                total_retained = _checked_add(
                    total_retained,
                    source.source_byte_length,
                    limits.max_total_retained_source_bytes,
                    "total retained source",
                )

    def to_decision_binding(self) -> SnapshotDecisionBinding:
        return SnapshotDecisionBinding(
            snapshot_contract_version=self.snapshot_contract_version,
            assembly_contract_version=self.assembly_contract_version,
            instruction=DigestLengthBinding(
                self.instruction_sha256, self.instruction_byte_length
            ),
            inline_input=DigestLengthBinding(
                self.inline_input_sha256, self.inline_input_byte_length
            ),
            inline_input_posture="present" if self.inline_input_present else "absent",
            sources=tuple(source.to_decision_binding() for source in self.sources),
            task_data=DigestLengthBinding(
                self.task_data_sha256, self.task_data_byte_length
            ),
            assembled_execution=DigestLengthBinding(
                self.assembled_execution_sha256,
                self.assembled_execution_byte_length,
            ),
            task_id_posture=self.declarations.task_id_posture,
            task_id=self.declarations.task_id,
            declared_privacy=self.declarations.declared_privacy,
            cloud_intent=(
                "requested" if self.declarations.cloud_intent else "not_requested"
            ),
            requested_profile=self.declarations.requested_profile,
            resolved_profile_id=self.resolved_profile.profile_id,
            profile_resolution_version=self.resolved_profile.resolution_version,
            construction_limits_sha256=self.construction_limits.sha256,
            worker_system_message_version=self.worker_system_message.version,
            worker_system_message_sha256=self.worker_system_message.sha256,
        )


def _assemble_bytes(parts: Iterable[bytes], total_length: int) -> bytes:
    output = bytearray(total_length)
    cursor = 0
    for part in parts:
        output[cursor : cursor + len(part)] = part
        cursor += len(part)
    if cursor != total_length:
        raise SnapshotValidationError("checked assembly length mismatch")
    return bytes(output)


def build_governed_run_input_snapshot(
    *,
    prompt: str,
    sources: Iterable[SourceBytesInput],
    inline_input: Optional[str],
    declarations: NormalizedOperatorDeclarations,
    resolved_profile: ContextModelProfile,
    worker_system_message: WorkerSystemMessageBinding,
    limits: SnapshotConstructionLimits,
    retain_source_bytes: bool = False,
) -> GovernedRunInputSnapshot:
    """Construct one exact, bounded, immutable snapshot without integration."""

    if type(limits) is not SnapshotConstructionLimits:
        raise SnapshotLimitError("explicit finite construction limits are required")
    if type(retain_source_bytes) is not bool:
        raise SnapshotValidationError("retain_source_bytes must be boolean")
    if retain_source_bytes and (
        limits.max_retained_source_bytes_per_source is None
        or limits.max_total_retained_source_bytes is None
    ):
        raise SnapshotLimitError("raw-source retention requires finite bounds")
    if type(declarations) is not NormalizedOperatorDeclarations:
        raise SnapshotValidationError("declarations must be immutable")
    if type(resolved_profile) is not ContextModelProfile:
        raise SnapshotValidationError("resolved_profile must be immutable")
    if type(worker_system_message) is not WorkerSystemMessageBinding:
        raise SnapshotValidationError("worker_system_message must be immutable")
    if inline_input is not None and type(inline_input) is not str:
        raise SnapshotValidationError("inline input must be text or absent")

    source_values: list[SourceBytesInput] = []
    total_source_bytes = 0
    total_retained_bytes = 0
    for source in sources:
        if len(source_values) >= limits.max_source_count:
            raise SnapshotLimitError("source count exceeds its finite bound")
        if type(source) is not SourceBytesInput:
            raise SnapshotValidationError("sources must contain SourceBytesInput values")
        if len(source.source_bytes) > limits.max_source_bytes_per_source:
            raise SnapshotLimitError("source input exceeds its per-source bound")
        total_source_bytes = _checked_add(
            total_source_bytes,
            len(source.source_bytes),
            limits.max_total_source_bytes,
            "total source input",
        )
        if retain_source_bytes:
            if len(source.source_bytes) > limits.max_retained_source_bytes_per_source:
                raise SnapshotLimitError("retained source exceeds its per-source bound")
            total_retained_bytes = _checked_add(
                total_retained_bytes,
                len(source.source_bytes),
                limits.max_total_retained_source_bytes,
                "total retained source",
            )
        source_values.append(source)

    instruction = _bounded_utf8(prompt, limits.max_instruction_bytes, "instruction")
    if inline_input is None or inline_input == "":
        inline = b""
        inline_present = False
    else:
        inline = _bounded_utf8(
            inline_input, limits.max_inline_input_bytes, "inline input"
        )
        inline_present = True

    source_measurements: list[
        tuple[SourceBytesInput, bytes, int, str, int]
    ] = []
    total_component_bytes = 0
    for source in source_values:
        header = _bounded_header(
            source.path_spelling,
            limits.max_normalized_component_bytes_per_source,
        )
        content_limit = (
            limits.max_normalized_component_bytes_per_source - len(header)
        )
        normalized_length, normalized_digest = _measure_normalized(
            source.source_bytes, content_limit
        )
        component_length = _checked_add(
            len(header),
            normalized_length,
            limits.max_normalized_component_bytes_per_source,
            "normalized source component",
        )
        total_component_bytes = _checked_add(
            total_component_bytes,
            component_length,
            limits.max_total_normalized_component_bytes,
            "total normalized source components",
        )
        source_measurements.append(
            (
                source,
                header,
                normalized_length,
                normalized_digest,
                component_length,
            )
        )

    task_length = _checked_add(
        total_component_bytes,
        len(inline),
        limits.max_task_data_bytes,
        "assembled task data",
    )
    assembled_length = 0
    for part_length in (
        len(instruction),
        len(EXECUTION_DATA_SEPARATOR),
        task_length,
    ):
        assembled_length = _checked_add(
            assembled_length,
            part_length,
            limits.max_assembled_execution_bytes,
            "assembled execution",
        )

    source_snapshots: list[SourceSnapshot] = []
    for position, measurement in enumerate(source_measurements):
        source, header, normalized_length, normalized_digest, component_length = (
            measurement
        )
        component = _materialize_component(
            header, source.source_bytes, normalized_length
        )
        source_snapshots.append(
            SourceSnapshot(
                position=position,
                path_spelling=source.path_spelling,
                locator_sha256=_locator_digest(source.path_spelling),
                source_bytes=source.source_bytes if retain_source_bytes else None,
                source_sha256=sha256_digest(source.source_bytes),
                source_byte_length=len(source.source_bytes),
                normalized_sha256=normalized_digest,
                normalized_byte_length=normalized_length,
                normalized_component_bytes=component,
                component_sha256=sha256_digest(component),
                component_byte_length=component_length,
            )
        )

    task_parts = tuple(source.normalized_component_bytes for source in source_snapshots)
    if inline_present:
        task_parts += (inline,)
    task_data = _assemble_bytes(task_parts, task_length)

    assembled = _assemble_bytes(
        (instruction, EXECUTION_DATA_SEPARATOR, task_data), assembled_length
    )

    return GovernedRunInputSnapshot(
        snapshot_contract_version=SNAPSHOT_CONTRACT_VERSION,
        assembly_contract_version=ASSEMBLY_CONTRACT_VERSION,
        instruction_bytes=instruction,
        instruction_sha256=sha256_digest(instruction),
        instruction_byte_length=len(instruction),
        inline_input_present=inline_present,
        inline_input_bytes=inline,
        inline_input_sha256=sha256_digest(inline),
        inline_input_byte_length=len(inline),
        sources=tuple(source_snapshots),
        task_data_bytes=task_data,
        task_data_sha256=sha256_digest(task_data),
        task_data_byte_length=len(task_data),
        assembled_execution_bytes=assembled,
        assembled_execution_sha256=sha256_digest(assembled),
        assembled_execution_byte_length=len(assembled),
        declarations=declarations,
        resolved_profile=resolved_profile,
        worker_system_message=worker_system_message,
        construction_limits=limits,
        retains_source_bytes=retain_source_bytes,
    )
