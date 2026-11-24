"""Symlink-safe publication for Workspace Unifier YAML mutations."""

from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path
from typing import Callable

import yaml

from triage_core.workspace_board import load_work_items_stream


class WorkspaceFileError(OSError):
    """The requested workspace output cannot be published safely."""


class WorkspaceValidationError(ValueError):
    """The staged workspace payload does not satisfy the work-item contract."""


def output_exists(path: str) -> bool:
    """Return true for every existing output entry, including dangling links."""
    return os.path.lexists(path)


def require_output_available(path: str, *, force: bool) -> None:
    if output_exists(path) and not force:
        raise FileExistsError(
            f"Output file {path} already exists. Use --force to overwrite."
        )


def _is_link_or_reparse(info: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    attributes = getattr(info, "st_file_attributes", 0)
    return stat.S_ISLNK(info.st_mode) or bool(attributes & reparse_flag)


def _reject_legacy_staging_link(output_path: str) -> None:
    legacy_path = f"{output_path}.tmp.yaml"
    try:
        info = os.lstat(legacy_path)
    except FileNotFoundError:
        return
    except OSError as exc:
        raise WorkspaceFileError(
            f"Legacy workspace staging entry is unavailable: {legacy_path}"
        ) from exc
    if _is_link_or_reparse(info):
        raise WorkspaceFileError(
            f"Legacy workspace staging entry is linked or reparse-backed: {legacy_path}"
        )


def _verified_parent(target: Path) -> tuple[Path, os.stat_result]:
    parent = Path(os.path.abspath(target.parent))
    for component in reversed((parent, *parent.parents)):
        try:
            info = os.lstat(component)
        except OSError as exc:
            raise WorkspaceFileError(
                f"Workspace output parent is unavailable: {component}"
            ) from exc
        if _is_link_or_reparse(info):
            raise WorkspaceFileError(
                f"Workspace output parent is linked or reparse-backed: {component}"
            )
        if not stat.S_ISDIR(info.st_mode):
            raise WorkspaceFileError(
                f"Workspace output parent is not a directory: {component}"
            )
    return parent, os.lstat(parent)


def _revalidate_parent(parent: Path, expected: os.stat_result) -> None:
    current_parent, current = _verified_parent(parent / "candidate")
    if current_parent != parent or not os.path.samestat(expected, current):
        raise WorkspaceFileError("Workspace output parent changed during mutation")


def _create_staging_file(
    parent: Path,
    *,
    suffix: str,
) -> tuple[int, str]:
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_BINARY", 0)

    for _ in range(32):
        name = f".triagecore-workspace.{secrets.token_hex(16)}{suffix}"
        temporary_path = os.fspath(parent / name)
        try:
            descriptor = os.open(temporary_path, flags, 0o600)
        except FileExistsError:
            continue
        return descriptor, temporary_path
    raise WorkspaceFileError("Could not allocate an exclusive workspace staging file")


def _same_regular_file(path: str, expected: os.stat_result) -> bool:
    try:
        current = os.lstat(path)
    except OSError:
        return False
    return (
        not _is_link_or_reparse(current)
        and stat.S_ISREG(current.st_mode)
        and current.st_nlink == 1
        and os.path.samestat(expected, current)
    )


def _remove_unchanged_stage(path: str, expected: os.stat_result) -> None:
    if _same_regular_file(path, expected):
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


def write_validated_workspace_yaml(
    output_path: str,
    output_data: dict,
    *,
    force: bool,
    before_replace: Callable[[], None] | None = None,
) -> None:
    """Validate and atomically publish workspace YAML without following links."""
    require_output_available(output_path, force=force)
    _reject_legacy_staging_link(output_path)

    target = Path(os.path.abspath(output_path))
    parent, parent_info = _verified_parent(target)
    descriptor, temporary_path = _create_staging_file(
        parent,
        suffix=".tmp.yaml",
    )
    stage_info = os.fstat(descriptor)
    descriptor_open = True

    try:
        if not stat.S_ISREG(stage_info.st_mode) or stage_info.st_nlink != 1:
            raise WorkspaceFileError("Workspace staging entry is not a regular file")

        with os.fdopen(descriptor, "w+", encoding="utf-8") as stream:
            descriptor_open = False
            try:
                yaml.safe_dump(
                    output_data,
                    stream,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )
                stream.flush()
                os.fsync(stream.fileno())
            except OSError as exc:
                raise WorkspaceFileError("Workspace staging write failed") from exc
            except Exception as exc:
                raise WorkspaceValidationError(str(exc)) from exc

            try:
                stream.seek(0)
                load_work_items_stream(stream, source=temporary_path)
            except Exception as exc:
                raise WorkspaceValidationError(str(exc)) from exc
            stage_info = os.fstat(stream.fileno())

        _revalidate_parent(parent, parent_info)
        if not _same_regular_file(temporary_path, stage_info):
            raise WorkspaceFileError("Workspace staging entry changed during mutation")

        if before_replace is not None:
            before_replace()
        _revalidate_parent(parent, parent_info)
        if not _same_regular_file(temporary_path, stage_info):
            raise WorkspaceFileError("Workspace staging entry changed during mutation")
        require_output_available(output_path, force=force)
        os.replace(temporary_path, target)
    finally:
        if descriptor_open:
            os.close(descriptor)
        _remove_unchanged_stage(temporary_path, stage_info)


def copy_workspace_backup(source_path: str, backup_path: str) -> None:
    """Copy a backup through an exclusive stage without following its output."""
    target = Path(os.path.abspath(backup_path))
    parent, parent_info = _verified_parent(target)
    descriptor, temporary_path = _create_staging_file(
        parent,
        suffix=".tmp",
    )
    stage_info = os.fstat(descriptor)
    descriptor_open = True

    try:
        if not stat.S_ISREG(stage_info.st_mode) or stage_info.st_nlink != 1:
            raise WorkspaceFileError("Workspace backup stage is not a regular file")

        with open(source_path, "rb") as source:
            source_info = os.fstat(source.fileno())
            with os.fdopen(descriptor, "wb") as destination:
                descriptor_open = False
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    destination.write(chunk)
                destination.flush()
                if hasattr(os, "fchmod"):
                    os.fchmod(
                        destination.fileno(),
                        stat.S_IMODE(source_info.st_mode),
                    )
                os.fsync(destination.fileno())
                stage_info = os.fstat(destination.fileno())

        _revalidate_parent(parent, parent_info)
        if not _same_regular_file(temporary_path, stage_info):
            raise WorkspaceFileError("Workspace backup stage changed during mutation")
        os.replace(temporary_path, target)
    finally:
        if descriptor_open:
            os.close(descriptor)
        _remove_unchanged_stage(temporary_path, stage_info)
