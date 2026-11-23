"""Native file boundaries for CR-134 local staging. All public errors carry codes."""

from __future__ import annotations

import ctypes
import hashlib
import os
import re
import stat
import sys
from contextlib import ExitStack, contextmanager, suppress
from ctypes import wintypes
from dataclasses import dataclass
from functools import cache
from pathlib import Path, PurePosixPath
from uuid import UUID, uuid4

from .public_export_policy import InputError, parse_policy


class StorageError(OSError):
    def __init__(self, code: str, *, cleanup: str | None = None, digest: str | None = None):
        super().__init__(code)
        self.code = code
        self.cleanup = cleanup
        self.digest = digest


@dataclass(frozen=True)
class StageResult:
    outcome: str
    digest: str | None
    cleanup: str | None
    name: str | None


def _digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _readback_digest(stream, extent: int) -> str:
    """Hash a stable file extent; concurrent resizing makes verification uncertain."""
    observed = hashlib.sha256()
    remaining = extent
    while remaining:
        block = stream.read(min(remaining, 64 * 1024))
        if not block:
            raise StorageError("staging_uncertain")
        observed.update(block)
        remaining -= len(block)
    if stream.read(1):
        raise StorageError("staging_uncertain")
    return "sha256:" + observed.hexdigest()


def _leaf(value: str) -> str:
    if (not isinstance(value, str) or not value or value in (".", "..")
            or value.endswith((" ", ".")) or any(ord(c) < 32 or c in '<>:"/\\|?*' for c in value)
            or re.fullmatch(r"(?:CON|PRN|AUX|NUL|COM[1-9¹²³]|LPT[1-9¹²³])(?:\..*)?", value, re.IGNORECASE)):
        raise StorageError("invalid_locator")
    return value


def _absolute(path) -> Path:
    path = Path(path)
    if not path.is_absolute() or (os.name == "nt" and not re.fullmatch(r"[A-Za-z]:", path.drive)):
        raise StorageError("invalid_locator")
    for part in path.parts[1:]:
        _leaf(part)
    return path


def _ancestors(path: Path):
    return (*reversed(path.parents), path)


def _contains(parent: Path, candidate: Path) -> bool:
    return candidate == parent or parent in candidate.parents


def _worktree(directory: Path, denied_mounts):
    # lexists semantics, with failure to inspect a marker treated as refusal.
    for marker in (".git", ".hg", ".svn"):
        path = directory / marker
        if os.name == "posix":
            _check_linux_mounts(path, denied_mounts)
        try:
            path.lstat()
        except FileNotFoundError:
            continue
        raise StorageError("destination_in_worktree")


@contextmanager
def _normalized(code: str):
    try:
        yield
    except StorageError:
        raise
    except (OSError, ValueError) as exc:
        raise StorageError(code) from exc


# Only the handle, identity and access-control operations needed for staging.
# Load the system DLLs lazily; POSIX never needs a Windows entry point.
@cache
def _windows_api():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    pointer = ctypes.c_void_p
    output = ctypes.POINTER(pointer)
    handle, word, number, flag = wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.BOOL

    def bind(function, result, *arguments):
        function.restype = result
        function.argtypes = arguments

    bind(kernel.CreateFileW, handle, wintypes.LPCWSTR, number, number, pointer, number, number, handle)
    bind(kernel.CloseHandle, flag, handle)
    bind(kernel.GetCurrentProcess, handle)
    bind(kernel.GetDriveTypeW, wintypes.UINT, wintypes.LPCWSTR)
    bind(kernel.GetFinalPathNameByHandleW, number, handle, word, number, number)
    bind(kernel.GetFileInformationByHandle, flag, handle, ctypes.POINTER(_FileInfo))
    bind(kernel.GetVolumeInformationByHandleW, flag, handle, word, number, pointer, pointer, pointer, word, number)
    bind(kernel.LocalFree, pointer, pointer)
    bind(adv.OpenProcessToken, flag, handle, number, ctypes.POINTER(handle))
    bind(adv.GetTokenInformation, flag, handle, ctypes.c_int, pointer, number, ctypes.POINTER(number))
    bind(adv.ConvertSidToStringSidW, flag, pointer, ctypes.POINTER(word))
    bind(adv.ConvertStringSecurityDescriptorToSecurityDescriptorW, flag, wintypes.LPCWSTR, number, output,
         ctypes.POINTER(number))
    bind(adv.GetSecurityInfo, number, handle, ctypes.c_int, number, output, output, output, output, output)
    bind(adv.IsValidAcl, flag, pointer)
    bind(adv.GetAclInformation, flag, pointer, pointer, number, ctypes.c_int)
    return kernel, adv


class _FileInfo(ctypes.Structure):
    # BY_HANDLE_FILE_INFORMATION. The file times are six DWORDs.
    _fields_ = [("attributes", wintypes.DWORD), ("timestamps", wintypes.DWORD * 6),
                ("volume", wintypes.DWORD), ("size_high", wintypes.DWORD), ("size_low", wintypes.DWORD),
                ("links", wintypes.DWORD), ("index_high", wintypes.DWORD), ("index_low", wintypes.DWORD)]


_REPARSE = 0x400
_DIRECTORY = 0x10
_OPEN_REPARSE = 0x00200000
_BACKUP_SEMANTICS = 0x02000000
_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_DOS_PATH = "\\\\?\\"


def _open_windows(path, access, *, security=None):
    _check_windows_drive(path)
    kernel, _ = _windows_api()
    if security is None:
        # Share reads only; pin existing components against writes and deletion.
        share, disposition, flags = 1, 3, _OPEN_REPARSE | _BACKUP_SEMANTICS
    else:
        share, disposition, flags = 0, 1, _OPEN_REPARSE  # CREATE_NEW
    handle = kernel.CreateFileW(_DOS_PATH + str(path), access, share, security, disposition, flags, None)
    if handle in (None, ctypes.c_void_p(-1).value):
        raise OSError("native_open_failed")
    return handle


def _windows_drive_type(anchor):
    kernel, _ = _windows_api()
    return kernel.GetDriveTypeW(anchor)


def _check_windows_drive(path):
    if not re.fullmatch(r"[A-Za-z]:", path.drive) or _windows_drive_type(path.anchor) not in (2, 3, 6):
        raise StorageError("unsupported_filesystem")


def _close_windows(handle):
    kernel, _ = _windows_api()
    if not kernel.CloseHandle(handle):
        raise OSError("native_close_failed")


def _windows_info(handle):
    kernel, _ = _windows_api()
    info = _FileInfo()
    if not kernel.GetFileInformationByHandle(handle, ctypes.byref(info)):
        raise OSError("file_information_unavailable")
    return info


def _windows_path_matches(handle, path):
    kernel, _ = _windows_api()
    size = kernel.GetFinalPathNameByHandleW(handle, None, 0, 0)
    if not 0 < size <= 32768:
        raise OSError("file_path_unavailable")
    buffer = ctypes.create_unicode_buffer(size)
    written = kernel.GetFinalPathNameByHandleW(handle, buffer, size, 0)
    if not 0 < written < size:
        raise OSError("file_path_unavailable")
    return buffer.value.startswith(_DOS_PATH) and Path(buffer.value[len(_DOS_PATH):]) == path


def _is_windows_regular(handle, path):
    return not _windows_info(handle).attributes & (_DIRECTORY | _REPARSE) and _windows_path_matches(handle, path)


def _volume_is_ntfs(handle):
    kernel, _ = _windows_api()
    name = ctypes.create_unicode_buffer(261)
    if not kernel.GetVolumeInformationByHandleW(handle, None, 0, None, None, None, name, len(name)):
        raise OSError("filesystem_unavailable")
    return name.value.upper() == "NTFS"


def _sid_text(pointer):
    kernel, adv = _windows_api()
    value = wintypes.LPWSTR()
    if not pointer or not adv.ConvertSidToStringSidW(pointer, ctypes.byref(value)):
        raise StorageError("identity_unavailable")
    try:
        return value.value.encode("ascii")
    finally:
        kernel.LocalFree(ctypes.cast(value, ctypes.c_void_p))


def _acl_entries(raw, count):
    """Split the OS-reported ACL extent into complete aligned ACEs."""
    offset = 8  # ACL header
    entries = []
    for _ in range(count):
        if offset + 4 > len(raw):
            raise StorageError("acl_unverifiable")
        size = int.from_bytes(raw[offset + 2:offset + 4], "little")
        if size < 4 or size % 4 or offset + size > len(raw):
            raise StorageError("acl_unverifiable")
        entries.append(raw[offset:offset + size])
        offset += size
    if offset != len(raw):
        raise StorageError("acl_unverifiable")
    return entries


def _windows_acl(handle):
    kernel, adv = _windows_api()
    owner, dacl, descriptor = ctypes.c_void_p(), ctypes.c_void_p(), ctypes.c_void_p()
    # SE_FILE_OBJECT, OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION
    if adv.GetSecurityInfo(handle, 1, 5, ctypes.byref(owner), None, ctypes.byref(dacl), None,
                           ctypes.byref(descriptor)):
        raise StorageError("acl_unverifiable")
    try:
        if not descriptor.value or not dacl.value or not adv.IsValidAcl(dacl):
            raise StorageError("acl_unverifiable")
        # ACL_SIZE_INFORMATION: AceCount, AclBytesInUse, AclBytesFree.
        sizes = (wintypes.DWORD * 3)()
        if not adv.GetAclInformation(dacl, sizes, ctypes.sizeof(sizes), 2):
            raise StorageError("acl_unverifiable")
        count, used, _ = sizes
        header = ctypes.string_at(dacl, 8)
        if (not 8 <= used <= int.from_bytes(header[2:4], "little")
                or count != int.from_bytes(header[4:6], "little")):
            raise StorageError("acl_unverifiable")
        return _sid_text(owner), _acl_entries(ctypes.string_at(dacl, used), count)
    finally:
        kernel.LocalFree(descriptor)


def _sid_from_ace(ace: bytes) -> bytes:
    # Standard access-allowed and access-denied ACEs have an 8-byte header
    # preceding the SID. Other layouts must be classified separately.
    if len(ace) < 16 or ace[0] not in (0, 1) or ace[8] != 1:
        raise StorageError("acl_unverifiable")
    count = ace[9]
    if len(ace) != 16 + count * 4:
        raise StorageError("acl_unverifiable")
    authority = int.from_bytes(ace[10:16], "big")
    fields = [str(int.from_bytes(ace[i:i + 4], "little")) for i in range(16, len(ace), 4)]
    return "-".join(["S", "1", str(authority), *fields]).encode("ascii")


def _win_user_sid() -> bytes:
    kernel, adv = _windows_api()
    token = wintypes.HANDLE()
    if not adv.OpenProcessToken(kernel.GetCurrentProcess(), 0x8, ctypes.byref(token)):
        raise StorageError("identity_unavailable")
    try:
        size = wintypes.DWORD()
        adv.GetTokenInformation(token, 1, None, 0, ctypes.byref(size))  # TokenUser
        if not size.value:
            raise StorageError("identity_unavailable")
        buf = ctypes.create_string_buffer(size.value)
        if not adv.GetTokenInformation(token, 1, buf, size.value, ctypes.byref(size)):
            raise StorageError("identity_unavailable")
        return _sid_text(ctypes.cast(buf, ctypes.POINTER(ctypes.c_void_p))[0])
    finally:
        _close_windows(token.value)


@contextmanager
def _owner_security():
    """Explicit protected, current-user-only DACL supplied at CREATE_NEW."""
    kernel, adv = _windows_api()

    class SecurityAttributes(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("descriptor", ctypes.c_void_p), ("inherit", wintypes.BOOL)]

    sid = _win_user_sid().decode("ascii")
    convert = adv.ConvertStringSecurityDescriptorToSecurityDescriptorW
    descriptor = ctypes.c_void_p()
    if not convert(f"O:{sid}D:P(A;;FA;;;{sid})", 1, ctypes.byref(descriptor), None):
        raise StorageError("acl_unverifiable")
    try:
        yield SecurityAttributes(ctypes.sizeof(SecurityAttributes), descriptor.value, False)
    finally:
        kernel.LocalFree(descriptor)


_ADMIN_SIDS = frozenset({
    b"S-1-5-18", b"S-1-5-32-544",
    b"S-1-5-80-956008885-3418522649-1831038044-1853292631-2271478464",
})
# Generic write/all, DELETE, WRITE_DAC, WRITE_OWNER, file write/append/EA,
# directory delete-child and write-attributes. Read/execute is not write.
_WRITE = 0x40000000 | 0x10000000 | 0x000D0000 | 0x156


def _windows_permissions(handle, *, private=False, admin=False, ancestor=False):
    owner_sid, entries = _windows_acl(handle)
    owner = _win_user_sid()
    trusted = _ADMIN_SIDS if admin else {owner}
    if owner_sid not in trusted:
        raise StorageError("unsafe_permissions")
    for ace in entries:
        sid = _sid_from_ace(ace)
        if ace[0] == 1 or ace[1] & 0x08:  # deny or inherit-only
            continue
        mask = int.from_bytes(ace[4:8], "little")
        # On an ancestor, allowing creation of unrelated children cannot
        # replace an already-existing, protected child. DELETE_CHILD can.
        forbidden = _WRITE & ~0x06 if ancestor else _WRITE
        if sid not in trusted and mask and (private or mask & forbidden):
            raise StorageError("unsafe_permissions")


_ONEDRIVE = "a52bba46-e9e1-435f-b3d9-28daa648c0f6"
_DOCUMENTS = "fdd39ad0-238f-46af-adb4-6c85480369c7"
_DESKTOP = "b4bfcc3a-db2c-424c-b029-7fe99a87c641"


def _known_folder_registered(identifier):
    import winreg

    branch = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\FolderDescriptions"
    access = winreg.KEY_READ | winreg.KEY_WOW64_64KEY
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, branch, 0, access) as descriptions:
        try:
            with winreg.OpenKey(descriptions, "{" + str(UUID(identifier)) + "}", 0, access):
                return True
        except FileNotFoundError:
            return False


def _folder_path(identifier, flags, get, free, *, optional):
    pointer = wintypes.LPWSTR()
    guid = ctypes.create_string_buffer(UUID(identifier).bytes_le)
    try:
        status = get(guid, flags, None, ctypes.byref(pointer)) & 0xFFFFFFFF
        # E_INVALIDARG can also indicate a failure unrelated to registration.
        if status == 0x80070057 and optional and not _known_folder_registered(identifier):
            return None
        if status != 0 or not pointer.value:
            raise StorageError("known_folder_unavailable")
        folder = Path(pointer.value)
        if not folder.is_absolute() or ".." in folder.parts:
            raise StorageError("known_folder_unavailable")
        return folder
    finally:
        free(ctypes.cast(pointer, ctypes.c_void_p))


def _known_folder(identifier: str, *, optional=False, default=False) -> Path | None:
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    ole = ctypes.WinDLL("ole32", use_last_error=True)
    get = shell.SHGetKnownFolderPath
    get.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(wintypes.LPWSTR)]
    get.restype = ctypes.c_long
    ole.CoTaskMemFree.argtypes, ole.CoTaskMemFree.restype = [ctypes.c_void_p], None
    ole.CoInitializeEx.argtypes, ole.CoInitializeEx.restype = [ctypes.c_void_p, wintypes.DWORD], ctypes.c_long
    ole.CoUninitialize.argtypes, ole.CoUninitialize.restype = [], None
    initialized = ole.CoInitializeEx(None, 2) & 0xFFFFFFFF
    # An apartment already initialized in another mode can also call the shell.
    if initialized not in (0, 1, 0x80010106):
        raise StorageError("known_folder_unavailable")
    try:
        # DONT_VERIFY returns offline redirects. DEFAULT_PATH ignores redirection.
        return _folder_path(identifier, 0x4000 | (0x0400 if default else 0), get, ole.CoTaskMemFree, optional=optional)
    finally:
        if initialized in (0, 1):
            ole.CoUninitialize()


def _win_open_dir(path: Path, security: bool):
    # Pin every path component against rename, deletion and reparse writes.
    access = 0x80 | (0x20000 if security else 0)  # READ_ATTRIBUTES, READ_CONTROL
    return _open_windows(path, access)


def _permissions(token, *, private=False, admin=False, ancestor=False):
    if os.name == "nt":
        _windows_permissions(token, private=private, admin=admin, ancestor=ancestor)
    else:
        info = os.fstat(token)
        if info.st_uid != (0 if admin else os.geteuid()) or info.st_mode & (0o077 if private else 0o022):
            raise StorageError("unsafe_permissions")


def _native_supported():
    if os.name == "nt":
        try:
            _windows_api()
        except (AttributeError, OSError):
            return False
        return True
    return (sys.platform.startswith("linux") and hasattr(os, "O_DIRECTORY") and hasattr(os, "O_NOFOLLOW")
            and os.open in os.supports_dir_fd and os.stat in os.supports_dir_fd
            and os.listdir in os.supports_fd)


_LOCAL_FILESYSTEMS = frozenset({b"ext2", b"ext3", b"ext4", b"xfs", b"btrfs", b"f2fs", b"jfs",
                                b"bcachefs", b"ntfs3", b"tmpfs", b"ramfs", b"overlay", b"zfs"})


def _untrusted_mounts(mountinfo):
    """Read only the kernel's mount metadata. Keep every nonlocal/unknown ancestor."""
    denied = []
    have_root = False
    for line in mountinfo.splitlines():
        fields, separator, details = line.partition(b" - ")
        mount, tail = fields.split(), details.split()
        if not separator or len(mount) < 6 or len(tail) < 3:
            raise StorageError("filesystem_unavailable")
        raw = re.sub(rb"\\([0-7]{3})", lambda m: bytes([int(m[1], 8)]), mount[4])
        location = PurePosixPath(os.fsdecode(raw))
        if not location.is_absolute():
            raise StorageError("filesystem_unavailable")
        have_root |= location == PurePosixPath("/")
        if tail[0] not in _LOCAL_FILESYSTEMS:
            denied.append(location)
    if not have_root:
        raise StorageError("filesystem_unavailable")
    return denied


def _linux_mounts():
    return _untrusted_mounts(Path("/proc/self/mountinfo").read_bytes())


def _check_linux_mounts(path, denied):
    if any(path.is_relative_to(mount) for mount in denied):
        raise StorageError("unsupported_filesystem")


def require_local_path(path: Path) -> None:
    """Inspect a local directory and its ancestry before a consumer invokes Git."""
    with _normalized("source_unavailable"), _chain(_absolute(path)):
        pass


@contextmanager
def _chain(path: Path, *, checked_from: Path | None = None, private=False, admin=False,
           exclude_worktrees=False):
    """Open the namespace from its anchor. All directory handles survive the operation."""
    if not _native_supported():
        raise StorageError("unsupported_platform")
    denied_mounts = ()
    if os.name == "posix":
        denied_mounts = _linux_mounts()
        _check_linux_mounts(path, denied_mounts)
    previous = None
    with ExitStack() as stack:
        for component in _ancestors(path):
            checked = checked_from is not None and _contains(checked_from, component)
            if os.name == "nt":
                token = _win_open_dir(component, checked or admin)
                stack.callback(_close_windows, token)
                attrs = _windows_info(token).attributes
                if not attrs & _DIRECTORY or attrs & _REPARSE:
                    raise StorageError("unsafe_directory")
                if not _windows_path_matches(token, component):
                    raise StorageError("unsafe_directory")
            else:
                flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                token = os.open(component.anchor if previous is None else component.name, flags, dir_fd=previous)
                stack.callback(os.close, token)
            if checked or admin:
                _permissions(token, private=private, admin=admin, ancestor=admin)
            elif checked_from is not None and os.name == "posix":
                # An untrusted ancestor could move an otherwise private
                # root outside its approved location. A trusted sticky
                # ancestor (e.g. /tmp) protects its trusted-owned next entry.
                info = os.fstat(token)
                if (info.st_uid not in (0, os.geteuid())
                        or (info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX)):
                    raise StorageError("unsafe_permissions")
            if exclude_worktrees:
                _worktree(component, denied_mounts)
            previous = token
        if os.name == "nt" and not _volume_is_ntfs(previous):
            raise StorageError("unsupported_filesystem")
        yield previous


def _identity(token):
    if os.name == "nt":
        info = _windows_info(token)
        return info.volume, info.index_high, info.index_low
    info = os.fstat(token)
    return info.st_dev, info.st_ino


@contextmanager
def _read_fd(path: Path, parent, *, admin=False, private=False):
    if os.name == "nt":
        import msvcrt

        handle = _open_windows(path, _GENERIC_READ)
        try:
            if not _is_windows_regular(handle, path):
                raise StorageError("unsafe_file")
            if admin or private:
                _permissions(handle, admin=admin, private=private)
            fd = msvcrt.open_osfhandle(handle, os.O_BINARY | os.O_RDONLY)
        except BaseException:
            _close_windows(handle)
            raise
    else:
        _check_linux_mounts(path, _linux_mounts())
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise StorageError("unsafe_file")
        if (admin or private) and info.st_nlink != 1:
            raise StorageError("unsafe_file")
        if os.name != "nt" and (admin or private):
            _permissions(fd, admin=admin, private=private)
        yield stream


def _read_payload(stream, initial_size: int) -> bytes:
    # Retain exact bytes for the one-byte-over boundary refusal in the frozen
    # corpus. Larger files refuse without allocating or hashing their contents.
    boundary = 16_384 + 1
    if initial_size > boundary:
        raise StorageError("payload_too_large")
    raw = stream.read(boundary)
    if len(raw) == boundary and stream.read(1):
        raise StorageError("payload_too_large")
    return raw


def read_source(repo_root: Path, locator: str, *, payload=False) -> bytes:
    with _normalized("source_unavailable"):
        root = _absolute(repo_root)
        if not isinstance(locator, str):
            raise StorageError("invalid_locator")
        parts = [_leaf(p) for p in locator.split("/")]
        path = root.joinpath(*parts)
        with _chain(path.parent) as directory, _read_fd(path, directory) as stream:
            if payload:
                return _read_payload(stream, os.fstat(stream.fileno()).st_size)
            return stream.read()


def _check_policy_location(path: Path, raw: bytes) -> None:
    try:
        policy = parse_policy(raw)
    except InputError as exc:
        raise StorageError(exc.code) from exc
    if policy.evidence_root is not None:
        for root in (*policy.roots, policy.evidence_root):
            if _contains(_absolute(root), path):
                raise StorageError("unsafe_policy_location")


def read_system_policy() -> bytes:
    with _normalized("policy_unavailable"):
        if os.name == "nt":
            if ctypes.windll.shell32.IsUserAnAdmin():
                raise StorageError("policy_unavailable")
            program_data = _absolute(_known_folder("62ab5d82-fdc1-4dc3-a9dd-070d1d495d97"))
            path = program_data / "TriageCore" / "PublicExport" / "policy.json"
        elif os.name == "posix":
            if os.geteuid() == 0:
                raise StorageError("policy_unavailable")
            path = Path("/etc/triagecore/public-export/policy.json")
        else:
            raise StorageError("unsupported_platform")
        with (_chain(path.parent, admin=True, exclude_worktrees=True) as directory,
              _read_fd(path, directory, admin=True) as stream):
            raw = stream.read()
        _check_policy_location(path, raw)
        return raw


def _windows_sync_roots():
    roots = []
    onedrive = _known_folder(_ONEDRIVE, optional=True)
    if onedrive:
        roots.append(onedrive)
    for identifier in (_DOCUMENTS, _DESKTOP):
        actual = _known_folder(identifier)
        if actual != _known_folder(identifier, default=True):
            # A moved known folder may sync even if it is outside all of
            # the OneDrive roots discoverable for this account.
            roots.append(actual)
    for key in ("OneDrive", "OneDriveConsumer", "OneDriveCommercial"):
        if os.environ.get(key):
            roots.append(_absolute(os.environ[key]))
    return roots


def _check_exclusions(path, denied_sync_roots):
    denied = [_absolute(item) for item in denied_sync_roots]
    if os.name == "nt":
        denied.extend(_windows_sync_roots())
    if any(_contains(sync, path) for sync in denied):
        raise StorageError("synchronized_destination")


@contextmanager
def _new_handle(token, close):
    """A file already exists; retain that fact even if validation and closing both fail."""
    try:
        yield
    except BaseException as exc:
        with suppress(OSError):
            close(token)
        if isinstance(exc, Exception):
            raise StorageError("staging_uncertain", cleanup="unknown") from exc
        raise


def _create_fd(path, directory):
    if os.name == "nt":
        import msvcrt

        with _owner_security() as security:
            handle = _open_windows(path, _GENERIC_READ | _GENERIC_WRITE, security=ctypes.byref(security))
        with _new_handle(handle, _close_windows):
            _permissions(handle, private=True)
            if not _is_windows_regular(handle, path):
                raise StorageError("staging_uncertain", cleanup="unknown")
            return msvcrt.open_osfhandle(handle, os.O_BINARY | os.O_RDWR)
    fd = os.open(path.name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
    with _new_handle(fd, os.close):
        if stat.S_IMODE(os.fstat(fd).st_mode) != 0o600:
            # umask may only have removed owner rights. The file was private
            # from first creation; restoring its owner's rights is safe.
            os.fchmod(fd, 0o600)
            if stat.S_IMODE(os.fstat(fd).st_mode) != 0o600:
                raise StorageError("staging_uncertain", cleanup="unknown")
        return fd


class Directory:
    def __init__(self, path, root, denied_sync_roots, evidence, token):
        self.path, self.root = path, root
        self._denied, self._private = tuple(denied_sync_roots), evidence
        self._token = token
        self._identity = _identity(token)

    def revalidate(self):
        with _normalized("destination_changed"):
            if self._token is None:
                raise StorageError("directory_closed")
            _check_exclusions(self.path, self._denied)
            with _chain(self.path, checked_from=self.root, private=self._private,
                        exclude_worktrees=True) as current:
                if _identity(current) != self._identity:
                    raise StorageError("destination_changed")

    def names(self) -> tuple[str, ...]:
        self.revalidate()
        with _normalized("evidence_unavailable"):
            return tuple(sorted(os.listdir(self.path if os.name == "nt" else self._token)))

    def read(self, name: str) -> bytes:
        self.revalidate()
        with (_normalized("evidence_unavailable"),
              _read_fd(self.path / _leaf(name), self._token, private=True) as stream):
            return stream.read()

    def write_new(self, name: str, data: bytes) -> str:
        self.revalidate()
        with _normalized("exclusive_create_failed"):
            fd = _create_fd(self.path / _leaf(name), self._token)
        # From this point, any failure may leave a file. Never unlink a name
        # on cleanup: the POSIX directory entry might have been substituted.
        phase = "staging_failed_partial"
        try:
            with os.fdopen(fd, "w+b", buffering=0) as stream:
                remaining = memoryview(data)
                while remaining:
                    written = stream.write(remaining)
                    if not written:
                        raise OSError("short write")
                    remaining = remaining[written:]
                phase = "staging_uncertain"
                os.fsync(stream.fileno())
                if os.name != "nt":
                    os.fsync(self._token)
                phase = "staged_unverified"
                stream.seek(0)
                observed = _readback_digest(stream, os.fstat(stream.fileno()).st_size)
                if observed != _digest(data):
                    raise StorageError("staged_mismatch", digest=observed)
                self.revalidate()
                verified_fd = stream.fileno()
                if os.fstat(verified_fd).st_nlink != 1:
                    raise StorageError("staging_uncertain")
                if os.name == "nt":
                    import msvcrt

                    with _normalized("staging_uncertain"):
                        _permissions(msvcrt.get_osfhandle(verified_fd), private=True)
                else:
                    _permissions(verified_fd, private=True)
                    info = os.stat(name, dir_fd=self._token, follow_symlinks=False)
                    if (info.st_dev, info.st_ino) != _identity(verified_fd):
                        raise StorageError("staging_uncertain")
                return observed
        except StorageError as exc:
            if exc.code in ("staged_mismatch", "staging_uncertain"):
                raise
            raise StorageError("staging_uncertain", cleanup="unknown") from exc
        except OSError as exc:
            raise StorageError(phase, cleanup="unknown" if phase == "staging_failed_partial" else None) from exc


@contextmanager
def open_directory(path: Path, *, root: Path, denied_sync_roots: tuple, evidence: bool = False):
    # Normalize open errors only; callers retain ownership of exceptions they
    # raise while using the directory.
    with ExitStack() as stack:
        with _normalized("unsafe_directory"):
            path, root = _absolute(path), _absolute(root)
            # POSIX and per-directory case-sensitive NTFS both require exact
            # components for an allowlist. Denylist comparison may be stricter.
            if (path.parts[:len(root.parts)] != root.parts
                    or (evidence and len(path.parts) != len(root.parts))):
                raise StorageError("unapproved_destination")
            _check_exclusions(path, denied_sync_roots)
            token = stack.enter_context(_chain(path, checked_from=root, private=evidence, exclude_worktrees=True))
            handle = Directory(path, root, denied_sync_roots, evidence, token)
        try:
            yield handle
        finally:
            handle._token = None


def stage_payload(handle: Directory, payload: bytes, *, name: str | None = None) -> StageResult:
    name = name if name is not None else uuid4().hex + ".txt"
    try:
        digest = handle.write_new(name, payload)
    except StorageError as exc:
        if exc.code in ("staging_uncertain", "staged_mismatch", "staged_unverified", "staging_failed_partial"):
            return StageResult(exc.code, exc.digest, exc.cleanup, name)
        return StageResult("refused_pre_staging", None, None, None)
    return StageResult("staged_verified", digest, None, name)
