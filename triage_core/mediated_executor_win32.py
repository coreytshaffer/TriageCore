"""Windows mechanism adapter for the constrained replacement executor.

Private to CR-OC-001C. This module owns **mechanism only**: narrow, typed
Win32 operations that observe or act on the filesystem and report primitive
facts. It makes no policy decision, classifies no DACL state, classifies no
execution outcome, produces no persistent projection, and performs no logging,
persistence, network, subprocess, IPC, authorization, reservation, capability,
ledger, or OpenClaw work.

**It imports no TriageCore module.** In particular it never imports
``triage_core.mediated_executor``, and it references no core-owned type. That
is what keeps the dependency one-way: the core imports this adapter
dynamically, only after its Windows platform gate has passed, receives the
adapter-owned :class:`Win32SecurityCapture`, and converts it into the
core-owned snapshot itself.

Errors are :class:`Win32AdapterError`, carrying a fixed operation label and a
numeric code only. No path, name, handle value, SID, ACL, descriptor, or OS
message string is ever placed in an adapter error -- those would flow straight
into a caller's diagnostics and violate the evidence rules the core enforces.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

# --- Win32 constants ----------------------------------------------------------

GENERIC_READ = 0x80000000
GENERIC_WRITE = 0x40000000

FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004

CREATE_NEW = 1
OPEN_EXISTING = 3

FILE_ATTRIBUTE_NORMAL = 0x00000080
FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000

INVALID_FILE_ATTRIBUTES = 0xFFFFFFFF
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

ERROR_FILE_NOT_FOUND = 2
ERROR_PATH_NOT_FOUND = 3

VOLUME_NAME_DOS = 0x0

OWNER_SECURITY_INFORMATION = 0x00000001
DACL_SECURITY_INFORMATION = 0x00000004
SE_FILE_OBJECT = 1

SE_DACL_PRESENT = 0x0004
SE_DACL_AUTO_INHERITED = 0x0400
SE_DACL_PROTECTED = 0x1000

_ACL_SIZE_INFORMATION_CLASS = 2
TOKEN_QUERY = 0x0008

# TokenOwner (information class 4), NOT TokenUser (1). TokenUser identifies the
# token's user account; TokenOwner is the default owner SID Windows applies to
# newly created objects. The caller's ownership gate must reason about the
# owner the temporary file will actually receive, so this is the only token
# quantity this adapter exposes (CR section 10.2a).
_TOKEN_OWNER_CLASS = 4

# ACE_HEADER is AceType (1) + AceFlags (1) + AceSize (2).
ACE_HEADER_SIZE = 4

_VERBATIM_PREFIX = "\\\\?\\"
_UNC_VERBATIM_PREFIX = "\\\\?\\UNC\\"


class Win32AdapterError(Exception):
    """A Windows mechanism operation failed.

    Carries a fixed operation label and a numeric code only -- never a path,
    a name, a descriptor, or an OS message string.
    """

    def __init__(self, operation: str, code: int = 0, *, not_found: bool = False):
        super().__init__(f"{operation} failed with code {int(code)}")
        self.operation = operation
        self.code = int(code)
        self.not_found = bool(not_found)


@dataclass(frozen=True)
class Win32SecurityCapture:
    """Observed security facts. Adapter-owned, primitive, and conclusion-free.

    ``dacl_present`` and ``dacl_is_null`` are reported exactly as observed; the
    three-valued classification built from them belongs to the core, not here.
    ``aces`` holds complete ``AceSize``-byte sequences in enumeration order,
    each already bounds-validated against the ACL's in-use extent, so unused
    ACL capacity and slack never leave this module.
    """

    owner_sid: bytes
    dacl_present: bool
    dacl_is_null: bool
    control_bits: Tuple[bool, bool, bool]
    acl_revision: int
    ace_count: int
    aces: Tuple[bytes, ...]


# --- Structures ---------------------------------------------------------------


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class _BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", _FILETIME),
        ("ftLastAccessTime", _FILETIME),
        ("ftLastWriteTime", _FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    ]


class _ACL(ctypes.Structure):
    _fields_ = [
        ("AclRevision", ctypes.c_ubyte),
        ("Sbz1", ctypes.c_ubyte),
        ("AclSize", wintypes.WORD),
        ("AceCount", wintypes.WORD),
        ("Sbz2", wintypes.WORD),
    ]


class _ACL_SIZE_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("AceCount", wintypes.DWORD),
        ("AclBytesInUse", wintypes.DWORD),
        ("AclBytesFree", wintypes.DWORD),
    ]


class _ACE_HEADER(ctypes.Structure):
    _fields_ = [
        ("AceType", ctypes.c_ubyte),
        ("AceFlags", ctypes.c_ubyte),
        ("AceSize", wintypes.WORD),
    ]


class _TOKEN_OWNER(ctypes.Structure):
    _fields_ = [("Owner", ctypes.c_void_p)]


# --- Library bindings ---------------------------------------------------------


def _bind():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)

    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CloseHandle.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.GetFinalPathNameByHandleW.restype = wintypes.DWORD
    kernel32.GetFinalPathNameByHandleW.argtypes = [
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
    kernel32.GetFileInformationByHandle.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_BY_HANDLE_FILE_INFORMATION),
    ]
    kernel32.GetVolumeInformationByHandleW.restype = wintypes.BOOL
    kernel32.GetVolumeInformationByHandleW.argtypes = [
        wintypes.HANDLE,
        wintypes.LPWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPWSTR,
        wintypes.DWORD,
    ]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    kernel32.WriteFile.restype = wintypes.BOOL
    kernel32.WriteFile.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    kernel32.FlushFileBuffers.restype = wintypes.BOOL
    kernel32.FlushFileBuffers.argtypes = [wintypes.HANDLE]
    kernel32.SetFilePointerEx.restype = wintypes.BOOL
    kernel32.SetFilePointerEx.argtypes = [
        wintypes.HANDLE,
        ctypes.c_longlong,
        ctypes.POINTER(ctypes.c_longlong),
        wintypes.DWORD,
    ]
    kernel32.ReplaceFileW.restype = wintypes.BOOL
    kernel32.ReplaceFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_void_p,
        ctypes.c_void_p,
    ]
    kernel32.DeleteFileW.restype = wintypes.BOOL
    kernel32.DeleteFileW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetFileAttributesW.restype = wintypes.DWORD
    kernel32.GetFileAttributesW.argtypes = [wintypes.LPCWSTR]
    kernel32.LocalFree.restype = ctypes.c_void_p
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetCurrentProcess.argtypes = []

    advapi32.GetSecurityInfo.restype = wintypes.DWORD
    advapi32.GetSecurityInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.GetSecurityDescriptorControl.restype = wintypes.BOOL
    advapi32.GetSecurityDescriptorControl.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.WORD),
        ctypes.POINTER(wintypes.DWORD),
    ]
    advapi32.GetSecurityDescriptorDacl.restype = wintypes.BOOL
    advapi32.GetSecurityDescriptorDacl.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.BOOL),
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(wintypes.BOOL),
    ]
    advapi32.GetAclInformation.restype = wintypes.BOOL
    advapi32.GetAclInformation.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_int,
    ]
    advapi32.GetAce.restype = wintypes.BOOL
    advapi32.GetAce.argtypes = [
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p),
    ]
    advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
    advapi32.ConvertSidToStringSidW.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.LPWSTR),
    ]
    advapi32.OpenProcessToken.restype = wintypes.BOOL
    advapi32.OpenProcessToken.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    advapi32.GetTokenInformation.restype = wintypes.BOOL
    advapi32.GetTokenInformation.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    return kernel32, advapi32


try:  # pragma: no cover - exercised only on Windows
    _K32, _ADV = _bind()
except (OSError, AttributeError):  # pragma: no cover - non-Windows import guard
    _K32 = None
    _ADV = None


_REQUIRED_KERNEL32 = (
    "CreateFileW",
    "CloseHandle",
    "GetFinalPathNameByHandleW",
    "GetFileInformationByHandle",
    "GetVolumeInformationByHandleW",
    "ReadFile",
    "WriteFile",
    "FlushFileBuffers",
    "SetFilePointerEx",
    "ReplaceFileW",
    "DeleteFileW",
    "GetFileAttributesW",
)
_REQUIRED_ADVAPI32 = (
    "GetSecurityInfo",
    "GetSecurityDescriptorControl",
    "GetSecurityDescriptorDacl",
    "GetAclInformation",
    "GetAce",
    "ConvertSidToStringSidW",
    "OpenProcessToken",
    "GetTokenInformation",
)


def windows_support_probe() -> bool:
    """True only when every required Win32 entry point resolves."""
    if _K32 is None or _ADV is None:
        return False
    try:
        for name in _REQUIRED_KERNEL32:
            getattr(_K32, name)
        for name in _REQUIRED_ADVAPI32:
            getattr(_ADV, name)
    except AttributeError:
        return False
    return True


def _last_error() -> int:
    return ctypes.get_last_error()


# --- Path helpers (mechanism: Windows path shape and equality) ----------------


def strip_verbatim_prefix(path: str) -> str:
    if path.startswith(_UNC_VERBATIM_PREFIX):
        return "\\\\" + path[len(_UNC_VERBATIM_PREFIX):]
    if path.startswith(_VERBATIM_PREFIX):
        return path[len(_VERBATIM_PREFIX):]
    return path


def paths_equal(left: str, right: str) -> bool:
    """Ordinal, case-insensitive comparison after normalising path shape.

    Windows path lookup is case-insensitive by default. NTFS supports
    per-directory case sensitivity, so this comparison can in principle accept
    a same-letters path that a case-sensitive directory would treat as
    different; the identity checks the core performs bound the consequence to
    a file that still resolved under the workspace anchor.
    """
    return _comparable(left) == _comparable(right)


def _comparable(path: str) -> str:
    return strip_verbatim_prefix(path).replace("/", "\\").rstrip("\\").casefold()


def expected_final_path(anchor_final_path: str, segments: Sequence[str]) -> str:
    """Join validated relpath segments under the anchored root."""
    base = anchor_final_path.rstrip("\\")
    return base + "\\" + "\\".join(segments)


def parent_directory(anchor_final_path: str, segments: Sequence[str]) -> str:
    base = anchor_final_path.rstrip("\\")
    if len(segments) == 1:
        return base
    return base + "\\" + "\\".join(segments[:-1])


def child_path(directory: str, name: str) -> str:
    return directory.rstrip("\\") + "\\" + name


def _verbatim(path: str) -> str:
    """Extended-length form, so long paths and trailing forms behave."""
    if path.startswith(_VERBATIM_PREFIX):
        return path
    if path.startswith("\\\\"):
        return _UNC_VERBATIM_PREFIX + path[2:]
    return _VERBATIM_PREFIX + path


# --- Handles ------------------------------------------------------------------


def _create_file(
    path: str,
    access: int,
    share: int,
    disposition: int,
    flags: int,
    operation: str,
) -> int:
    handle = _K32.CreateFileW(
        _verbatim(path), access, share, None, disposition, flags, None
    )
    if handle == _INVALID_HANDLE_VALUE or handle is None:
        code = _last_error()
        raise Win32AdapterError(
            operation, code, not_found=code in (ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND)
        )
    return handle


def open_anchor(root_path: str) -> int:
    """Open the trusted workspace root. Registry construction and NTFS check."""
    return _create_file(
        root_path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS,
        "open_anchor",
    )


def walk_open_target(anchor_final_path: str, segments: Sequence[str]) -> int:
    """Open the target for reading, refusing to follow a reparse point.

    Never accepts a caller-supplied path: the path is constructed here from
    the anchored root and the trusted registry's validated segments.

    ``FILE_FLAG_OPEN_REPARSE_POINT`` means a reparse point opens as itself
    rather than as its destination, so :func:`is_regular_file` can reject it
    instead of the executor silently operating on the link's target.

    ``FILE_FLAG_BACKUP_SEMANTICS`` is required to obtain a handle to a
    directory at all. Without it a directory target fails at the open, which
    the caller can only report as a resolution failure; with it the object is
    opened and then *classified*, so a directory is rejected as the non-regular
    file it is. It grants no rights the caller's token does not already have.
    """
    return _create_file(
        expected_final_path(anchor_final_path, segments),
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        OPEN_EXISTING,
        FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_BACKUP_SEMANTICS,
        "walk_open_target",
    )


def create_private_temp(path: str) -> int:
    """Exclusively create the private temporary file. ``CREATE_NEW`` fails if
    the name already exists, so this cannot adopt a squatted file."""
    return _create_file(
        path,
        GENERIC_WRITE,
        0,
        CREATE_NEW,
        FILE_ATTRIBUTE_NORMAL,
        "create_private_temp",
    )


def close_handle(handle: int) -> None:
    if handle is None:
        return
    _K32.CloseHandle(wintypes.HANDLE(handle))


def flush_and_close(handle: int) -> None:
    """Flush to the device, then close. Ordering matters before replacement."""
    if not _K32.FlushFileBuffers(wintypes.HANDLE(handle)):
        code = _last_error()
        close_handle(handle)
        raise Win32AdapterError("flush_and_close", code)
    close_handle(handle)


# --- Observation --------------------------------------------------------------


def final_path(handle: int) -> str:
    length = _K32.GetFinalPathNameByHandleW(
        wintypes.HANDLE(handle), None, 0, VOLUME_NAME_DOS
    )
    if length == 0:
        raise Win32AdapterError("final_path", _last_error())
    buffer = ctypes.create_unicode_buffer(length + 1)
    written = _K32.GetFinalPathNameByHandleW(
        wintypes.HANDLE(handle), buffer, length + 1, VOLUME_NAME_DOS
    )
    if written == 0:
        raise Win32AdapterError("final_path", _last_error())
    return strip_verbatim_prefix(buffer.value)


def volume_is_ntfs(handle: int) -> bool:
    name = ctypes.create_unicode_buffer(261)
    filesystem = ctypes.create_unicode_buffer(261)
    serial = wintypes.DWORD()
    max_component = wintypes.DWORD()
    flags = wintypes.DWORD()
    if not _K32.GetVolumeInformationByHandleW(
        wintypes.HANDLE(handle),
        name,
        261,
        ctypes.byref(serial),
        ctypes.byref(max_component),
        ctypes.byref(flags),
        filesystem,
        261,
    ):
        raise Win32AdapterError("volume_is_ntfs", _last_error())
    return filesystem.value.upper() == "NTFS"


def volume_filesystem_name(handle: int) -> str:
    """Reported for CI evidence only. Not used in any policy decision."""
    name = ctypes.create_unicode_buffer(261)
    filesystem = ctypes.create_unicode_buffer(261)
    serial = wintypes.DWORD()
    max_component = wintypes.DWORD()
    flags = wintypes.DWORD()
    if not _K32.GetVolumeInformationByHandleW(
        wintypes.HANDLE(handle),
        name,
        261,
        ctypes.byref(serial),
        ctypes.byref(max_component),
        ctypes.byref(flags),
        filesystem,
        261,
    ):
        raise Win32AdapterError("volume_filesystem_name", _last_error())
    return filesystem.value


def _file_information(handle: int) -> _BY_HANDLE_FILE_INFORMATION:
    info = _BY_HANDLE_FILE_INFORMATION()
    if not _K32.GetFileInformationByHandle(wintypes.HANDLE(handle), ctypes.byref(info)):
        raise Win32AdapterError("file_information", _last_error())
    return info


def file_identity(handle: int) -> Tuple[int, int, int]:
    """``(volume serial, file index high, file index low)`` while open."""
    info = _file_information(handle)
    return (
        int(info.dwVolumeSerialNumber),
        int(info.nFileIndexHigh),
        int(info.nFileIndexLow),
    )


def file_size(handle: int) -> int:
    info = _file_information(handle)
    return (int(info.nFileSizeHigh) << 32) | int(info.nFileSizeLow)


def is_regular_file(handle: int) -> bool:
    """A regular file is neither a directory nor any reparse-point form."""
    info = _file_information(handle)
    attributes = int(info.dwFileAttributes)
    if attributes & FILE_ATTRIBUTE_DIRECTORY:
        return False
    if attributes & FILE_ATTRIBUTE_REPARSE_POINT:
        return False
    return True


def path_exists(path: str) -> bool:
    return _K32.GetFileAttributesW(_verbatim(path)) != INVALID_FILE_ATTRIBUTES


def file_size_of_path(path: str) -> int:
    handle = _create_file(
        path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        OPEN_EXISTING,
        FILE_FLAG_OPEN_REPARSE_POINT,
        "file_size_of_path",
    )
    try:
        return file_size(handle)
    finally:
        close_handle(handle)


def _is_reparse_path(path: str) -> bool:
    attributes = _K32.GetFileAttributesW(_verbatim(path))
    if attributes == INVALID_FILE_ATTRIBUTES:
        raise Win32AdapterError("reparse_probe", _last_error())
    return bool(attributes & FILE_ATTRIBUTE_REPARSE_POINT)


def has_reparse_ancestor(anchor_final_path: str, segments: Sequence[str]) -> bool:
    """True when any ancestor strictly beneath the anchored root is a reparse
    point -- a symlinked directory, a junction, a mount point, or any other
    reparse tag. Enumerating tags is deliberately avoided; the attribute is the
    check."""
    base = anchor_final_path.rstrip("\\")
    for index in range(len(segments) - 1):
        candidate = base + "\\" + "\\".join(segments[: index + 1])
        if _is_reparse_path(candidate):
            return True
    return False


def has_reparse_target(anchor_final_path: str, segments: Sequence[str]) -> bool:
    """True when the final target component is itself a reparse point.

    Kept separate from the ancestor walk so each half of the contract's
    "for the target and every ancestor" rule is independently verifiable, and
    so the caller can reject a reparse target **before** opening a handle to
    it rather than opening first and classifying afterwards.

    Absence is not a reparse point: an unreadable attribute set here means the
    target does not exist, which the caller's open reports as a missing target.
    """
    attributes = _K32.GetFileAttributesW(
        _verbatim(expected_final_path(anchor_final_path, segments))
    )
    if attributes == INVALID_FILE_ATTRIBUTES:
        return False
    return bool(attributes & FILE_ATTRIBUTE_REPARSE_POINT)


def read_exact_bounded(handle: int, limit: int) -> bytes:
    """Read at most ``limit`` bytes from the start of the open object."""
    new_position = ctypes.c_longlong(0)
    if not _K32.SetFilePointerEx(
        wintypes.HANDLE(handle), 0, ctypes.byref(new_position), 0
    ):
        raise Win32AdapterError("read_exact_bounded", _last_error())
    chunks = []
    remaining = int(limit)
    buffer = ctypes.create_string_buffer(65536)
    while remaining > 0:
        want = min(remaining, len(buffer))
        read = wintypes.DWORD(0)
        if not _K32.ReadFile(
            wintypes.HANDLE(handle), buffer, want, ctypes.byref(read), None
        ):
            raise Win32AdapterError("read_exact_bounded", _last_error())
        count = int(read.value)
        if count == 0:
            break
        chunks.append(buffer.raw[:count])
        remaining -= count
    return b"".join(chunks)


def write_all(handle: int, data: bytes) -> int:
    """Write every byte. A short write is completed, never accepted."""
    view = memoryview(data)
    total = 0
    while total < len(view):
        chunk = view[total:]
        written = wintypes.DWORD(0)
        buffer = (ctypes.c_char * len(chunk)).from_buffer_copy(chunk)
        if not _K32.WriteFile(
            wintypes.HANDLE(handle),
            buffer,
            len(chunk),
            ctypes.byref(written),
            None,
        ):
            raise Win32AdapterError("write_all", _last_error())
        count = int(written.value)
        if count == 0:
            raise Win32AdapterError("write_all", 0)
        total += count
    return total


# --- Security capture ---------------------------------------------------------


def _sid_to_canonical_bytes(sid_pointer: int) -> bytes:
    """Canonical ``S-1-...`` representation, encoded.

    A canonical string is used rather than a raw structure copy so that
    equality of two captures is semantic SID identity, consistently, in one
    representation.
    """
    text = wintypes.LPWSTR()
    if not _ADV.ConvertSidToStringSidW(
        ctypes.c_void_p(sid_pointer), ctypes.byref(text)
    ):
        raise Win32AdapterError("sid_to_string", _last_error())
    try:
        return text.value.encode("ascii")
    finally:
        _K32.LocalFree(ctypes.cast(text, ctypes.c_void_p))


def process_default_owner_sid() -> bytes:
    """Canonical SID of the token's **default owner**.

    This is ``TokenOwner`` (information class 4), the owner Windows applies to
    objects this process creates without an explicit owner in a security
    descriptor -- which is exactly the temporary file the caller is about to
    create. It is deliberately **not** ``TokenUser``, which identifies the
    token's user account and says nothing about the new object's owner.

    Both ``GetTokenInformation`` calls -- the sizing probe and the retrieval --
    pass ``_TOKEN_OWNER_CLASS``, and a test asserts that on both.
    """
    token = wintypes.HANDLE()
    if not _ADV.OpenProcessToken(
        _K32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)
    ):
        raise Win32AdapterError("process_default_owner_sid", _last_error())
    try:
        needed = wintypes.DWORD(0)
        _ADV.GetTokenInformation(
            token, _TOKEN_OWNER_CLASS, None, 0, ctypes.byref(needed)
        )
        if needed.value == 0:
            raise Win32AdapterError("process_default_owner_sid", _last_error())
        buffer = ctypes.create_string_buffer(needed.value)
        if not _ADV.GetTokenInformation(
            token, _TOKEN_OWNER_CLASS, buffer, needed.value, ctypes.byref(needed)
        ):
            raise Win32AdapterError("process_default_owner_sid", _last_error())
        token_owner = ctypes.cast(buffer, ctypes.POINTER(_TOKEN_OWNER)).contents
        return _sid_to_canonical_bytes(token_owner.Owner)
    finally:
        close_handle(token.value)


def capture_security(handle: int) -> Win32SecurityCapture:
    """Walk the security descriptor and report primitive observed facts.

    Every ``AceSize`` is validated before use: non-zero, at least the ACE
    header size, and wholly within the ACL's in-use extent. A malformed
    descriptor, ACL, or ACE raises rather than producing a partially parsed
    capture -- there is no best-effort path. Unknown ACE types are copied whole
    and never interpreted.

    SACL and primary group are deliberately not requested: the SACL needs a
    privilege this executor does not take, and neither carries access rights.
    """
    owner = ctypes.c_void_p()
    dacl = ctypes.c_void_p()
    descriptor = ctypes.c_void_p()
    status = _ADV.GetSecurityInfo(
        wintypes.HANDLE(handle),
        SE_FILE_OBJECT,
        OWNER_SECURITY_INFORMATION | DACL_SECURITY_INFORMATION,
        ctypes.byref(owner),
        None,
        ctypes.byref(dacl),
        None,
        ctypes.byref(descriptor),
    )
    if status != 0:
        raise Win32AdapterError("capture_security", status)
    try:
        if not owner.value:
            raise Win32AdapterError("capture_security", 0)
        owner_sid = _sid_to_canonical_bytes(owner.value)

        control = wintypes.WORD()
        revision = wintypes.DWORD()
        if not _ADV.GetSecurityDescriptorControl(
            descriptor, ctypes.byref(control), ctypes.byref(revision)
        ):
            raise Win32AdapterError("capture_security", _last_error())
        bits = int(control.value)
        control_bits = (
            bool(bits & SE_DACL_PRESENT),
            bool(bits & SE_DACL_PROTECTED),
            bool(bits & SE_DACL_AUTO_INHERITED),
        )

        present = wintypes.BOOL()
        dacl_pointer = ctypes.c_void_p()
        defaulted = wintypes.BOOL()
        if not _ADV.GetSecurityDescriptorDacl(
            descriptor,
            ctypes.byref(present),
            ctypes.byref(dacl_pointer),
            ctypes.byref(defaulted),
        ):
            raise Win32AdapterError("capture_security", _last_error())

        dacl_present = bool(present.value)
        dacl_is_null = dacl_present and not dacl_pointer.value
        if not dacl_present or dacl_is_null:
            return Win32SecurityCapture(
                owner_sid=owner_sid,
                dacl_present=dacl_present,
                dacl_is_null=dacl_is_null,
                control_bits=control_bits,
                acl_revision=0,
                ace_count=0,
                aces=(),
            )

        acl_header = ctypes.cast(dacl_pointer, ctypes.POINTER(_ACL)).contents
        acl_revision = int(acl_header.AclRevision)

        size_info = _ACL_SIZE_INFORMATION()
        if not _ADV.GetAclInformation(
            dacl_pointer,
            ctypes.byref(size_info),
            ctypes.sizeof(size_info),
            _ACL_SIZE_INFORMATION_CLASS,
        ):
            raise Win32AdapterError("capture_security", _last_error())
        ace_count = int(size_info.AceCount)
        bytes_in_use = int(size_info.AclBytesInUse)
        acl_base = int(dacl_pointer.value)

        aces = []
        for index in range(ace_count):
            ace_pointer = ctypes.c_void_p()
            if not _ADV.GetAce(dacl_pointer, index, ctypes.byref(ace_pointer)):
                raise Win32AdapterError("capture_security", _last_error())
            if not ace_pointer.value:
                raise Win32AdapterError("capture_security", 0)
            header = ctypes.cast(ace_pointer, ctypes.POINTER(_ACE_HEADER)).contents
            ace_size = int(header.AceSize)
            offset = int(ace_pointer.value) - acl_base
            if ace_size < ACE_HEADER_SIZE:
                raise Win32AdapterError("capture_security", 0)
            if offset < 0 or offset + ace_size > bytes_in_use:
                # The ACE claims to extend past the ACL's in-use extent.
                raise Win32AdapterError("capture_security", 0)
            aces.append(
                ctypes.string_at(ctypes.c_void_p(ace_pointer.value), ace_size)
            )
        return Win32SecurityCapture(
            owner_sid=owner_sid,
            dacl_present=True,
            dacl_is_null=False,
            control_bits=control_bits,
            acl_revision=acl_revision,
            ace_count=ace_count,
            aces=tuple(aces),
        )
    finally:
        if descriptor.value:
            _K32.LocalFree(descriptor)


# --- Mutation -----------------------------------------------------------------


def replace_file(replaced: str, replacement: str, backup: str) -> Tuple[bool, int]:
    """Invoke ``ReplaceFileW`` exactly once and report primitive facts.

    ``dwReplaceFlags`` is pinned to ``0``: ``REPLACEFILE_IGNORE_MERGE_ERRORS``
    would swallow a failure to merge the replaced file's metadata, which is the
    DACL the caller's invariant depends on.

    Returns ``(succeeded, last_error)``. Classification is the caller's, so the
    mapping from an error code to an outcome stays pure and testable off
    Windows.
    """
    succeeded = bool(
        _K32.ReplaceFileW(
            _verbatim(replaced), _verbatim(replacement), _verbatim(backup), 0, None, None
        )
    )
    return succeeded, 0 if succeeded else _last_error()


def delete_file(path: str) -> bool:
    if not _K32.DeleteFileW(_verbatim(path)):
        raise Win32AdapterError("delete_file", _last_error())
    return True
