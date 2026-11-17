# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Private Win32 bindings for HYBA Mine (ctypes; Windows only).

Only ``hyba_mine.portable`` and ``hyba_mine.credentials`` import this module, and
only on Windows. Every function declares its argument and result types, raises
``OSError`` carrying only the Windows error code (never a value it handled),
and frees what the API allocated.

Covered: the current account's SID, file DACLs as SDDL, process queries,
termination and the kill-on-close job object, the process affinity mask,
``SetThreadExecutionState`` and Windows Credential Manager (generic
credentials, ``CredWriteW``/``CredReadW``/``CredDeleteW``/``CredFree``).
"""

from __future__ import annotations

import sys

if sys.platform != "win32":  # pragma: no cover - imported only on Windows
    raise ImportError("hyba_mine._win32 is available on Windows only")

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from typing import Optional

advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# ------------------------------------------------------------------ constants
ERROR_ACCESS_DENIED = 5
ERROR_INVALID_PARAMETER = 87
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_NOT_FOUND = 1168
ERROR_NO_SUCH_LOGON_SESSION = 1312

TOKEN_QUERY = 0x0008
TOKEN_USER_CLASS = 1
SE_FILE_OBJECT = 1
OWNER_SECURITY_INFORMATION = 0x00000001
DACL_SECURITY_INFORMATION = 0x00000004
PROTECTED_DACL_SECURITY_INFORMATION = 0x80000000
UNPROTECTED_DACL_SECURITY_INFORMATION = 0x20000000
SDDL_REVISION_1 = 1

PROCESS_TERMINATE = 0x0001
PROCESS_SET_QUOTA = 0x0100
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
STILL_ACTIVE = 259
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 0x102

JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS = 9
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001

CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
CRED_MAX_CREDENTIAL_BLOB_SIZE = 5 * 512  # 2560 bytes


def _error(code: Optional[int] = None) -> OSError:
    code = ctypes.get_last_error() if code is None else code
    # winerror only; never a message carrying data we handled.
    return OSError(None, f"Windows error {code}", None, code)


def _check(ok) -> None:
    if not ok:
        raise _error()


# ------------------------------------------------------------------- prototypes
LPDWORD = ctypes.POINTER(wintypes.DWORD)
PHANDLE = ctypes.POINTER(wintypes.HANDLE)

kernel32.GetCurrentProcess.argtypes = []
kernel32.GetCurrentProcess.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.LocalFree.argtypes = [wintypes.HLOCAL]
kernel32.LocalFree.restype = wintypes.HLOCAL
kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
kernel32.OpenProcess.restype = wintypes.HANDLE
kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, LPDWORD]
kernel32.GetExitCodeProcess.restype = wintypes.BOOL
kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, LPDWORD]
kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
kernel32.TerminateProcess.restype = wintypes.BOOL
kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
kernel32.WaitForSingleObject.restype = wintypes.DWORD
kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
kernel32.CreateJobObjectW.restype = wintypes.HANDLE
kernel32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
kernel32.SetInformationJobObject.restype = wintypes.BOOL
kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
kernel32.AssignProcessToJobObject.restype = wintypes.BOOL
kernel32.GetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t),
                                            ctypes.POINTER(ctypes.c_size_t)]
kernel32.GetProcessAffinityMask.restype = wintypes.BOOL
kernel32.SetThreadExecutionState.argtypes = [wintypes.DWORD]
kernel32.SetThreadExecutionState.restype = wintypes.DWORD

advapi32.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, PHANDLE]
advapi32.OpenProcessToken.restype = wintypes.BOOL
advapi32.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, LPDWORD]
advapi32.GetTokenInformation.restype = wintypes.BOOL
advapi32.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
advapi32.GetNamedSecurityInfoW.argtypes = [
    wintypes.LPCWSTR, ctypes.c_int, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
    ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p),
]
advapi32.GetNamedSecurityInfoW.restype = wintypes.DWORD
advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
    ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(wintypes.ULONG),
]
advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = wintypes.BOOL
advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
    wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.ULONG),
]
advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
advapi32.GetSecurityDescriptorDacl.argtypes = [
    ctypes.c_void_p, ctypes.POINTER(wintypes.BOOL), ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.BOOL),
]
advapi32.GetSecurityDescriptorDacl.restype = wintypes.BOOL
advapi32.SetNamedSecurityInfoW.argtypes = [
    wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
]
advapi32.SetNamedSecurityInfoW.restype = wintypes.DWORD


# ------------------------------------------------------------------- identity
class _SID_AND_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]


def current_user_sid() -> str:
    """String SID (``S-1-5-...``) of the account this process runs as, from its access token."""
    token = wintypes.HANDLE()
    _check(advapi32.OpenProcessToken(kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)))
    try:
        size = wintypes.DWORD(0)
        advapi32.GetTokenInformation(token, TOKEN_USER_CLASS, None, 0, ctypes.byref(size))
        if size.value == 0:
            raise _error()
        buffer = ctypes.create_string_buffer(size.value)
        _check(advapi32.GetTokenInformation(token, TOKEN_USER_CLASS, buffer, size, ctypes.byref(size)))
        user = _SID_AND_ATTRIBUTES.from_buffer(buffer)
        text = wintypes.LPWSTR()
        _check(advapi32.ConvertSidToStringSidW(user.Sid, ctypes.byref(text)))
        try:
            return text.value
        finally:
            kernel32.LocalFree(ctypes.cast(text, wintypes.HLOCAL))
    finally:
        kernel32.CloseHandle(token)


# ---------------------------------------------------------------- access lists
def get_dacl_sddl(path: str) -> str:
    """The DACL of ``path`` as an SDDL string (``D:...``; locale independent)."""
    descriptor = ctypes.c_void_p()
    dacl = ctypes.c_void_p()
    status = advapi32.GetNamedSecurityInfoW(str(path), SE_FILE_OBJECT, DACL_SECURITY_INFORMATION, None, None,
                                            ctypes.byref(dacl), None, ctypes.byref(descriptor))
    if status != 0:
        raise _error(status)
    try:
        text = wintypes.LPWSTR()
        _check(advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW(
            descriptor, SDDL_REVISION_1, DACL_SECURITY_INFORMATION, ctypes.byref(text), None))
        try:
            return text.value or ""
        finally:
            kernel32.LocalFree(ctypes.cast(text, wintypes.HLOCAL))
    finally:
        kernel32.LocalFree(ctypes.cast(descriptor, wintypes.HLOCAL))


def set_dacl_sddl(path: str, sddl: str, *, protected: bool = True) -> None:
    """Replace the DACL of ``path`` with the one in ``sddl`` (``D:...``).

    ``protected`` stops inheritance from the parent (PROTECTED_DACL_SECURITY_INFORMATION).
    """
    descriptor = ctypes.c_void_p()
    _check(advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
        sddl, SDDL_REVISION_1, ctypes.byref(descriptor), None))
    try:
        present = wintypes.BOOL()
        defaulted = wintypes.BOOL()
        dacl = ctypes.c_void_p()
        _check(advapi32.GetSecurityDescriptorDacl(descriptor, ctypes.byref(present), ctypes.byref(dacl),
                                                  ctypes.byref(defaulted)))
        if not present:
            raise _error(ERROR_INVALID_PARAMETER)
        flags = DACL_SECURITY_INFORMATION | (
            PROTECTED_DACL_SECURITY_INFORMATION if protected else UNPROTECTED_DACL_SECURITY_INFORMATION)
        status = advapi32.SetNamedSecurityInfoW(str(path), SE_FILE_OBJECT, flags, None, None, dacl, None)
        if status != 0:
            raise _error(status)
    finally:
        kernel32.LocalFree(ctypes.cast(descriptor, wintypes.HLOCAL))


def owner_only_sddl(sid: str, *, directory: bool) -> str:
    """Protected DACL granting full access to ``sid`` and LocalSystem only."""
    inherit = "OICI" if directory else ""
    return f"D:P(A;{inherit};FA;;;{sid})(A;{inherit};FA;;;SY)"


def set_protected_dacl(path: str, sid: str, *, directory: bool) -> None:
    set_dacl_sddl(path, owner_only_sddl(sid, directory=directory), protected=True)


# ------------------------------------------------------------------ processes
def _open_process(pid: int, access: int) -> wintypes.HANDLE:
    handle = kernel32.OpenProcess(access, False, int(pid))
    if not handle:
        raise _error()
    return handle


def process_alive(pid: int) -> bool:
    """True while ``pid`` names a running process (no signal is ever sent)."""
    if int(pid) <= 0:
        return False
    try:
        handle = _open_process(pid, PROCESS_QUERY_LIMITED_INFORMATION)
    except OSError as exc:
        if exc.winerror == ERROR_ACCESS_DENIED:
            return True  # exists, but belongs to another account or a protected process
        return False  # ERROR_INVALID_PARAMETER: no such process
    try:
        code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True
        return code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def process_image_name(pid: int) -> Optional[str]:
    try:
        handle = _open_process(pid, PROCESS_QUERY_LIMITED_INFORMATION)
    except OSError:
        return None
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return None
        return buffer.value
    finally:
        kernel32.CloseHandle(handle)


def terminate_process(pid: int, wait_seconds: float = 5.0) -> bool:
    """TerminateProcess(pid, 1) then wait up to ``wait_seconds`` for it to exit."""
    try:
        handle = _open_process(pid, PROCESS_TERMINATE | SYNCHRONIZE)
    except OSError:
        return not process_alive(pid)
    try:
        if not kernel32.TerminateProcess(handle, 1):
            return False
        waited = kernel32.WaitForSingleObject(handle, max(0, int(wait_seconds * 1000)))
        return waited == WAIT_OBJECT_0
    finally:
        kernel32.CloseHandle(handle)


class _IO_COUNTERS(ctypes.Structure):
    _fields_ = [(name, ctypes.c_ulonglong) for name in (
        "ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
        "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]


class _JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class _JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", _JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", _IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


def create_kill_on_close_job_for_current_process() -> wintypes.HANDLE:
    """Put this process in a new job that ends every member when its last handle closes.

    The returned handle must stay open for the life of the process; children
    created afterwards (spawned worker processes) join the job automatically.
    """
    job = kernel32.CreateJobObjectW(None, None)
    if not job:
        raise _error()
    try:
        info = _JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        _check(kernel32.SetInformationJobObject(job, JOB_OBJECT_EXTENDED_LIMIT_INFORMATION_CLASS,
                                                ctypes.byref(info), ctypes.sizeof(info)))
        _check(kernel32.AssignProcessToJobObject(job, kernel32.GetCurrentProcess()))
    except OSError:
        kernel32.CloseHandle(job)
        raise
    return job


def process_affinity_count() -> int:
    """Logical processors this process may run on (one processor group, at most 64)."""
    mask = ctypes.c_size_t()
    system = ctypes.c_size_t()
    _check(kernel32.GetProcessAffinityMask(kernel32.GetCurrentProcess(), ctypes.byref(mask), ctypes.byref(system)))
    return bin(mask.value).count("1")


def keep_system_awake() -> bool:
    """SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED) for this thread's lifetime."""
    return kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED) != 0


# --------------------------------------------------------- credential manager
class _CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", wintypes.FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


_PCREDENTIALW = ctypes.POINTER(_CREDENTIALW)
advapi32.CredWriteW.argtypes = [_PCREDENTIALW, wintypes.DWORD]
advapi32.CredWriteW.restype = wintypes.BOOL
advapi32.CredReadW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(_PCREDENTIALW)]
advapi32.CredReadW.restype = wintypes.BOOL
advapi32.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
advapi32.CredDeleteW.restype = wintypes.BOOL
advapi32.CredFree.argtypes = [ctypes.c_void_p]
advapi32.CredFree.restype = None


@dataclass(frozen=True)
class CredRecord:
    target: str
    username_label: Optional[str]
    persist: int
    type: int
    blob: bytes

    def __repr__(self) -> str:  # never show the blob
        return f"CredRecord(target={self.target!r}, username_label={self.username_label!r}, persist={self.persist})"


def cred_write(target: str, username_label: str, comment: str, blob: bytes) -> None:
    """CredWriteW of a generic, local-machine-persisted credential; the copy of ``blob`` is zeroed."""
    if len(blob) > CRED_MAX_CREDENTIAL_BLOB_SIZE:
        raise _error(ERROR_INVALID_PARAMETER)
    buffer = (ctypes.c_ubyte * max(1, len(blob))).from_buffer_copy(blob if blob else b"\0")
    try:
        cred = _CREDENTIALW()
        cred.Type = CRED_TYPE_GENERIC
        cred.TargetName = target
        cred.Comment = comment
        cred.CredentialBlobSize = len(blob)
        cred.CredentialBlob = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
        cred.Persist = CRED_PERSIST_LOCAL_MACHINE
        cred.UserName = username_label
        _check(advapi32.CredWriteW(ctypes.byref(cred), 0))
    finally:
        ctypes.memset(buffer, 0, ctypes.sizeof(buffer))


def cred_read(target: str) -> Optional[CredRecord]:
    pointer = _PCREDENTIALW()
    if not advapi32.CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
        code = ctypes.get_last_error()
        if code == ERROR_NOT_FOUND:
            return None
        raise _error(code)
    try:
        cred = pointer.contents
        size = cred.CredentialBlobSize
        blob = ctypes.string_at(cred.CredentialBlob, size) if size else b""
        return CredRecord(target=cred.TargetName, username_label=cred.UserName, persist=cred.Persist,
                          type=cred.Type, blob=blob)
    finally:
        advapi32.CredFree(pointer)


def cred_delete(target: str) -> bool:
    if advapi32.CredDeleteW(target, CRED_TYPE_GENERIC, 0):
        return True
    code = ctypes.get_last_error()
    if code == ERROR_NOT_FOUND:
        return False
    raise _error(code)
