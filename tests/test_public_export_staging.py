"""Native Grant B storage checks; tests provision only isolated directories."""

import hashlib
import os
import stat
import subprocess
from pathlib import Path

import pytest

from triage_core import public_export_staging as storage


def private_directory(path: Path) -> Path:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        create = ctypes.WinDLL("kernel32", use_last_error=True).CreateDirectoryW
        create.argtypes = (wintypes.LPCWSTR, ctypes.c_void_p)
        create.restype = wintypes.BOOL
        with storage._owner_security() as security:
            if not create(str(path), ctypes.byref(security)):
                raise ctypes.WinError(ctypes.get_last_error())
    else:
        path.mkdir(mode=0o700)
    return path


def directory(root, *, path=None, denied=(), evidence=False):
    return storage.open_directory(path or root, root=root, denied_sync_roots=denied, evidence=evidence)


@pytest.mark.parametrize("blob,count", [(b"\0" * 8, 1), (b"\0" * 12, 1),
                                         (b"\0" * 8 + b"\0\0\x10\0", 1), (b"\0" * 12, 0)])
def test_native_acl_entries_must_fill_the_bounded_in_use_extent(blob, count):
    with pytest.raises(storage.StorageError, match="acl_unverifiable"):
        storage._acl_entries(blob, count)


def test_private_exclusive_native_file_and_digest(tmp_path):
    root = private_directory(tmp_path / "stage")
    payload = b"public\r\nexample\n"
    digest = "sha256:" + hashlib.sha256(payload).hexdigest()
    with directory(root) as target:
        result = storage.stage_payload(target, payload, name="one.txt")
        assert result.outcome == "staged_verified" and result.digest == digest
        assert target.read("one.txt") == payload
        assert target.names() == ("one.txt",)
        assert storage.stage_payload(target, b"other", name="one.txt").outcome == "refused_pre_staging"
        assert (root / "one.txt").read_bytes() == payload
    if os.name == "nt":
        from triage_core import mediated_executor_win32 as win

        handle = win.walk_open_target(str(root), ("one.txt",))
        try:
            capture = win.capture_security(handle)
            assert capture.control_bits[1] and capture.ace_count == 1
            assert storage._sid_from_ace(capture.aces[0]) == capture.owner_sid
        finally:
            win.close_handle(handle)
    else:
        assert stat.S_IMODE((root / "one.txt").stat().st_mode) == 0o600


@pytest.mark.parametrize("reason", ["outside", "sync", "repo", "evidence-subdir"])
def test_unapproved_directory_is_refused(tmp_path, reason):
    root = private_directory(tmp_path / "stage")
    child = private_directory(root / "child")
    outside = private_directory(tmp_path / "stage-extra")
    if reason == "repo":
        (root / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
    path = outside if reason == "outside" else child
    with (pytest.raises(storage.StorageError),
          directory(root, path=path, denied=(root,) if reason == "sync" else (),
                    evidence=reason == "evidence-subdir")):
        pytest.fail("unsafe directory opened")


@pytest.mark.parametrize("name", ["../outside", "/absolute", "C:alternate", "sub/file", "CON", "x:y"])
def test_single_leaf_required(tmp_path, name):
    root = private_directory(tmp_path / "stage")
    with directory(root) as target, pytest.raises(storage.StorageError):
        target.write_new(name, b"x")
    assert list(root.iterdir()) == []


def test_source_is_regular_repo_relative(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "doc.txt").write_bytes(b"content\r\n")
    assert storage.read_source(repo, "doc.txt") == b"content\r\n"
    for locator in ("../doc.txt", str(repo / "doc.txt"), "doc.txt:stream", "."):
        with pytest.raises(storage.StorageError):
            storage.read_source(repo, locator)


def test_junction_or_symlink_in_any_component_refuses(tmp_path):
    root = private_directory(tmp_path / "stage")
    outside = private_directory(tmp_path / "outside")
    link = root / "redirected"
    if os.name == "nt":
        subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/j", str(link), str(outside)],
                       check=True, capture_output=True)
    else:
        link.symlink_to(outside, target_is_directory=True)
    try:
        (outside / "document").write_bytes(b"public")
        with pytest.raises(storage.StorageError), directory(root, path=link):
            pytest.fail("link opened")
        with pytest.raises(storage.StorageError):
            storage.read_source(root, "redirected/document")
    finally:
        if os.name == "nt":
            link.rmdir()
        else:
            link.unlink()


def test_destination_rename_cannot_redirect_write(tmp_path):
    root = private_directory(tmp_path / "stage")
    child = private_directory(root / "chosen")
    with directory(root, path=child) as target:
        try:
            child.rename(root / "moved")
        except PermissionError:
            assert os.name == "nt"
        else:
            private_directory(child)
            with pytest.raises(storage.StorageError):
                target.write_new("new.txt", b"content")
            assert list(child.iterdir()) == []


def test_writable_root_and_readable_evidence_refused(tmp_path):
    root = private_directory(tmp_path / "stage")
    def grant(read_only):
        if os.name == "nt":
            subprocess.run(["icacls.exe", str(root), "/grant:r",
                            "*S-1-1-0:" + ("(RX)" if read_only else "(M)")],
                           capture_output=True, check=True)
        else:
            root.chmod(0o755 if read_only else 0o777)
    grant(False)
    with pytest.raises(storage.StorageError), directory(root):
        pass
    grant(True)
    with pytest.raises(storage.StorageError), directory(root, evidence=True):
        pass


def test_sync_exclusions_and_untrusted_locator_do_not_read_links(tmp_path):
    parent = private_directory(tmp_path / "OneDrive - Example")
    moved_documents = private_directory(parent / "Documents")
    with pytest.raises(storage.StorageError), directory(moved_documents, denied=(parent,)):
        pytest.fail("redirected directory admitted")
    for name in ("CON.txt", "bad.", "alpha/../x", "name:alternate", "a\\b"):
        with pytest.raises(storage.StorageError):
            storage.read_source(tmp_path, name)


def test_flush_failure_after_creation_is_uncertain(tmp_path, monkeypatch):
    root = private_directory(tmp_path / "stage")
    def fail(_fd):
        raise OSError("synthetic I/O failure")
    monkeypatch.setattr(storage.os, "fsync", fail)
    with directory(root) as target:
        result = storage.stage_payload(target, b"synthetic", name="one.txt")
    assert result.outcome == "staging_uncertain"
    assert (root / "one.txt").read_bytes() == b"synthetic"


def test_readback_mismatch_retains_observed_digest(tmp_path, monkeypatch):
    root = private_directory(tmp_path / "stage")
    original = storage.os.fsync
    def corrupt(fd):
        if stat.S_ISREG(os.fstat(fd).st_mode):
            os.lseek(fd, 0, os.SEEK_SET)
            os.write(fd, b"?")
        return original(fd)
    monkeypatch.setattr(storage.os, "fsync", corrupt)
    with directory(root) as target:
        result = storage.stage_payload(target, b"hello", name="one.txt")
    assert result.outcome == "staged_mismatch"
    assert result.digest == "sha256:" + hashlib.sha256(b"?ello").hexdigest()


@pytest.mark.parametrize(("operation", "outcome"), [
    ("write", "staging_failed_partial"), ("read", "staged_unverified"),
])
def test_native_stream_failure_preserves_accurate_outcome(tmp_path, monkeypatch, operation, outcome):
    from contextlib import contextmanager

    root = private_directory(tmp_path / "stage")
    real_fdopen = os.fdopen
    @contextmanager
    def fail(fd, *args, **kwargs):
        with real_fdopen(fd, *args, **kwargs) as stream:
            class FaultStream:
                def __getattr__(self, name):
                    if name != operation:
                        return getattr(stream, name)
                    def failure(*values):
                        if name == "write":
                            stream.write(values[0][:1])
                        raise OSError("synthetic stream fault")
                    return failure
            yield FaultStream()
    monkeypatch.setattr(storage.os, "fdopen", fail)
    with directory(root) as target:
        result = storage.stage_payload(target, b"one", name="output")
    assert result.outcome == outcome
    assert result.cleanup == ("unknown" if operation == "write" else None)
    assert (root / "output").read_bytes() == (b"o" if operation == "write" else b"one")


def test_closed_directory_cannot_write(tmp_path):
    root = private_directory(tmp_path / "stage")
    with directory(root) as target:
        pass
    with pytest.raises(storage.StorageError, match="directory_closed"):
        target.write_new("payload", b"public")


def test_native_policy_owner_and_mode_cannot_be_user_controlled(tmp_path):
    root = private_directory(tmp_path / "policy")
    item = root / "policy.json"
    item.write_bytes(b"{}")
    if os.name == "posix" and os.geteuid() == 0:
        item.chmod(0o666)
    with (storage._chain(root) as handle, pytest.raises(storage.StorageError),
          storage._read_fd(item, handle, admin=True)):
        pytest.fail("untrusted policy accepted")


@pytest.mark.parametrize("location", ["stage", "evidence", "elsewhere"])
def test_system_policy_location_must_be_separate_from_both_roots(tmp_path, location):
    import json

    corpus = Path(__file__).parent / "fixtures" / "public_export_v0.json"
    doc = json.loads(json.loads(corpus.read_bytes())["policy_json"])
    doc["version"] = 2
    doc["local_staging"] = {"version": 2, "roots": [str(tmp_path / "stage")],
                            "evidence_root": str(tmp_path / "evidence"), "denied_sync_roots": [],
                            "clipboard": False}
    path = tmp_path / location / "policy.json"
    if location == "elsewhere":
        storage._check_policy_location(path, json.dumps(doc).encode())
    else:
        with pytest.raises(storage.StorageError, match="unsafe_policy_location"):
            storage._check_policy_location(path, json.dumps(doc).encode())


@pytest.mark.parametrize("size", [16384, 16385, 2**27])
def test_payload_reads_are_bounded_without_losing_boundary_evidence(tmp_path, size):
    path = tmp_path / "document"
    with path.open("wb") as stream:
        stream.truncate(size)
    if size <= 16385:
        assert len(storage.read_source(tmp_path, "document", payload=True)) == size
    else:
        with pytest.raises(storage.StorageError, match="payload_too_large"):
            storage.read_source(tmp_path, "document", payload=True)


def test_payload_limit_also_handles_growth_after_stat():
    import io

    class GuardedRead(io.BytesIO):
        def read(self, size=-1):
            assert 0 < size <= 16385
            return super().read(size)

    with pytest.raises(storage.StorageError, match="payload_too_large"):
        storage._read_payload(GuardedRead(b"x" * 20000), initial_size=0)


def test_actual_known_folder_move_treated_as_sync_risk(tmp_path, monkeypatch):
    def known(identifier, *, optional=False, default=False):
        if identifier == storage._ONEDRIVE:
            return None
        name = "Documents" if identifier == storage._DOCUMENTS else "Desktop"
        if default or name == "Desktop":
            return tmp_path / "profile" / name
        return tmp_path / "redirected-outside-onedrive" / "work-documents"
    monkeypatch.setattr(storage, "_known_folder", known)
    for key in ("OneDrive", "OneDriveCommercial", "OneDriveConsumer"):
        monkeypatch.delenv(key, raising=False)
    blocked = storage._windows_sync_roots()
    assert tmp_path / "redirected-outside-onedrive" / "work-documents" in blocked
    assert tmp_path / "profile" / "Desktop" not in blocked


@pytest.mark.parametrize("status,registered,value,allowed", [
    (0x80070057, False, "unused", True), (0x80070057, True, "unused", False),
    (0x80070005, False, "unused", False), (0x80004005, False, "unused", False),
    (0, True, None, False), (0, True, "relative", False),
])
def test_unknown_folder_discovery_refuses_and_releases_result(monkeypatch, status, registered, value, allowed):
    import ctypes
    from ctypes import wintypes

    value = wintypes.LPWSTR(value)
    free = []
    def get(_guid, _flags, _token, output):
        ctypes.cast(output, ctypes.POINTER(wintypes.LPWSTR))[0] = value
        return status

    monkeypatch.setattr(storage, "_known_folder_registered", lambda _: registered)
    args = (storage._ONEDRIVE, 0x4000, get, free.append)
    if allowed:
        assert storage._folder_path(*args, optional=True) is None
    else:
        with pytest.raises(storage.StorageError, match="known_folder_unavailable"):
            storage._folder_path(*args, optional=True)
    assert len(free) == 1 and free[0].value == ctypes.cast(value, ctypes.c_void_p).value


def test_create_validation_and_close_fault_preserve_observed_creation(tmp_path):
    from unittest.mock import patch

    root = private_directory(tmp_path / "stage")
    with directory(root) as handle:
        if os.name == "nt":
            checked, close_owner, close_name = "_permissions", storage, "_close_windows"
            check_owner = storage
        else:
            checked, close_owner, close_name = "fstat", os, "close"
            check_owner = os
        close = getattr(close_owner, close_name)
        validation_started = False

        def fail_validation(*args, **kwargs):
            nonlocal validation_started
            validation_started = True
            raise OSError("synthetic validation error")

        def close_then_fail(token):
            close(token)
            if validation_started:
                raise OSError("synthetic close error")

        with (patch.object(check_owner, checked, fail_validation),
              patch.object(close_owner, close_name, close_then_fail),
              pytest.raises(storage.StorageError, match="staging_uncertain") as failure):
            storage._create_fd(root / "created", handle._token)
        assert failure.value.cleanup == "unknown"
    assert (root / "created").is_file()


@pytest.mark.parametrize("kind", [0, 1, 4])
def test_unknown_or_remote_drive_is_refused_before_open(kind, monkeypatch):
    from pathlib import PureWindowsPath

    monkeypatch.setattr(storage, "_windows_drive_type", lambda _: kind)
    monkeypatch.setattr(storage, "_windows_api", lambda: pytest.fail("attempted a native file open"))
    with pytest.raises(storage.StorageError, match="unsupported_filesystem"):
        storage._open_windows(PureWindowsPath("Z:/synthetic"), 0)


@pytest.mark.parametrize("fs", ["nfs4", "cifs", "fuse.sshfs", "autofs", "unrecognized"])
def test_advertised_nonlocal_mount_never_opens_the_target(fs):
    from pathlib import PurePosixPath

    mountinfo = (b"1 1 0:1 / / rw - ext4 /dev/test rw\n"
                 + f"2 1 0:2 / /mnt/remote\\040dir rw - {fs} synthetic rw\n".encode()
                 + b"3 2 0:3 / /mnt/remote\\040dir/nested rw - tmpfs tmpfs rw\n")
    denied = storage._untrusted_mounts(mountinfo)
    with pytest.raises(storage.StorageError, match="unsupported_filesystem"):
        storage._check_linux_mounts(PurePosixPath("/mnt/remote dir/nested"), denied)
    storage._check_linux_mounts(PurePosixPath("/mnt/remote dir2"), denied)


def test_unsupported_native_boundary_refuses_before_staging(tmp_path, monkeypatch):
    root = private_directory(tmp_path / "stage")
    monkeypatch.setattr(storage, "_native_supported", lambda: False)
    with pytest.raises(storage.StorageError, match="unsupported_platform"), directory(root):
        pytest.fail("unsupported native filesystem guard")
    assert list(root.iterdir()) == []


def test_readback_hashes_in_bounded_blocks():
    import io

    class BoundedRead(io.BytesIO):
        def read(self, size=-1):
            assert 0 < size <= 64 * 1024
            return super().read(size)

    contents = b"synthetic-data" * 10000
    assert storage._readback_digest(BoundedRead(contents), len(contents)) == (
        "sha256:" + hashlib.sha256(contents).hexdigest()
    )
    with pytest.raises(storage.StorageError, match="staging_uncertain"):
        storage._readback_digest(BoundedRead(contents + b"unexpected growth"), len(contents))
