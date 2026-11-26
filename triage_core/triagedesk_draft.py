"""Prompt-only draft files for explicit TriageDesk import."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from .public_export_staging import (
    _absolute,
    _chain,
    _identity,
    _is_windows_regular,
    _read_fd,
)

DRAFT_VERSION = 1
MAX_DRAFT_BYTES = 64 * 1024
_FORMAT_ERROR = "Draft must be UTF-8 JSON with version 1 and a nonempty prompt."
_READ_ERROR = "Select an available regular draft file on a supported local filesystem."
_SIZE_ERROR = "Draft is too large. The maximum file size is 64 KiB."
_WRITE_ERROR = "Draft write could not be verified. An incomplete file may remain. Choose a new path to retry."


class DraftError(ValueError):
    """A draft could not be safely created or loaded."""


def _prompt_bytes(prompt: str) -> bytes:
    if not isinstance(prompt, str) or not prompt.strip() or "\x00" in prompt:
        raise DraftError(_FORMAT_ERROR)
    try:
        return prompt.encode("utf-8")
    except UnicodeError:
        raise DraftError(_FORMAT_ERROR) from None


def _unique_fields(pairs):
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise DraftError(_FORMAT_ERROR)
    return fields


def _file_snapshot(info: os.stat_result, diagnostic: str = _READ_ERROR) -> tuple[int, int, int, int, int]:
    if not stat.S_ISREG(info.st_mode) or not info.st_ino or info.st_nlink != 1:
        raise DraftError(diagnostic)
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _absolute_path(path: str | os.PathLike[str]) -> Path:
    absolute = Path(path).absolute()
    if absolute == absolute.parent or ".." in absolute.parts:
        raise ValueError("invalid draft path")
    if os.name == "nt":
        if absolute.is_reserved():
            raise ValueError("invalid draft path")
        return _absolute(absolute)
    if absolute.anchor != "/":
        raise ValueError("invalid draft path")
    return absolute


def _load_bytes(path: Path) -> bytes:
    # The staging primitives pin each parent without following links. On
    # Windows the leaf is opened with OPEN_REPARSE_POINT and checked by handle.
    with _chain(path.parent) as parent:
        expected = None
        if os.name == "posix":
            expected = _file_snapshot(os.stat(path.name, dir_fd=parent, follow_symlinks=False))
        with _read_fd(path, parent) as stream:
            opened = os.fstat(stream.fileno())
            snapshot = _file_snapshot(opened)
            if expected is not None and snapshot != expected:
                raise DraftError(_READ_ERROR)
            if opened.st_size > MAX_DRAFT_BYTES:
                raise DraftError(_SIZE_ERROR)
            raw = stream.read(MAX_DRAFT_BYTES + 1)
            if len(raw) > MAX_DRAFT_BYTES:
                raise DraftError(_SIZE_ERROR)
            if len(raw) != opened.st_size or _file_snapshot(os.fstat(stream.fileno())) != snapshot:
                raise DraftError(_READ_ERROR)
            if os.name == "posix":
                with _chain(path.parent) as current_parent:
                    if _identity(current_parent) != _identity(parent) or _file_snapshot(
                        os.stat(path.name, dir_fd=current_parent, follow_symlinks=False)
                    ) != snapshot:
                        raise DraftError(_READ_ERROR)
            return raw


def read_draft(path: str | os.PathLike[str]) -> str:
    """Read a bounded, verified snapshot of a user-selected prompt-only draft."""
    try:
        raw = _load_bytes(_absolute_path(path))
    except DraftError:
        raise
    except (OSError, ValueError):
        raise DraftError(_READ_ERROR) from None

    try:
        draft = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_fields)
    except (ValueError, RecursionError):
        raise DraftError(_FORMAT_ERROR) from None
    if (
        not isinstance(draft, dict)
        or draft.keys() != {"version", "prompt"}
        or type(draft["version"]) is not int
        or draft["version"] != DRAFT_VERSION
    ):
        raise DraftError(_FORMAT_ERROR)
    prompt = draft["prompt"]
    _prompt_bytes(prompt)
    return prompt


def _verify_output_name(path: Path, parent: int, fd: int, snapshot: tuple[int, int, int, int, int]) -> None:
    with _chain(path.parent) as current_parent:
        if _identity(current_parent) != _identity(parent):
            raise DraftError(_WRITE_ERROR)
        if os.name == "nt":
            import msvcrt

            if not _is_windows_regular(msvcrt.get_osfhandle(fd), path):
                raise DraftError(_WRITE_ERROR)
        else:
            current = os.stat(path.name, dir_fd=current_parent, follow_symlinks=False)
            if _file_snapshot(current, _WRITE_ERROR) != snapshot:
                raise DraftError(_WRITE_ERROR)


def write_draft(path: str | os.PathLike[str], prompt: str) -> None:
    """Create a new prompt-only draft without replacing a destination."""
    if len(_prompt_bytes(prompt)) > MAX_DRAFT_BYTES:
        raise DraftError(_SIZE_ERROR)
    raw = json.dumps(
        {"version": DRAFT_VERSION, "prompt": prompt}, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    if len(raw) > MAX_DRAFT_BYTES:
        raise DraftError(_SIZE_ERROR)

    created = False
    try:
        destination = _absolute_path(path)
        with _chain(destination.parent) as parent:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
            if os.name == "nt":
                fd = os.open(destination, flags | os.O_BINARY, 0o600)
            else:
                fd = os.open(destination.name, flags | os.O_NOFOLLOW, 0o600, dir_fd=parent)
            created = True
            with os.fdopen(fd, "wb") as stream:
                initial = _file_snapshot(os.fstat(fd), _WRITE_ERROR)
                if initial[2] != 0:
                    raise DraftError(_WRITE_ERROR)
                stream.write(raw)
                stream.flush()
                written = _file_snapshot(os.fstat(fd), _WRITE_ERROR)
                if written[:2] != initial[:2] or written[2] != len(raw):
                    raise DraftError(_WRITE_ERROR)
                _verify_output_name(destination, parent, fd, written)
    except FileExistsError:
        if created:
            raise DraftError(_WRITE_ERROR) from None
        raise DraftError("The draft output already exists. Choose a new path.") from None
    except DraftError:
        raise
    except (OSError, ValueError):
        # A failed write or identity check can leave an output behind. The
        # pathname may have changed, so leave cleanup to the operator.
        if created:
            raise DraftError(_WRITE_ERROR) from None
        raise DraftError("Draft output could not be created at the selected path.") from None
