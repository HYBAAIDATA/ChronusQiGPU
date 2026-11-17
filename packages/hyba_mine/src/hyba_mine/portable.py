# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Operating-system portability for HYBA Mine (macOS, Linux, Windows).

Every mechanism that differs by OS lives here, chosen at run time; callers do
not branch on the platform themselves except where behaviour is genuinely
different (for example how ``hyba-mine stop`` reaches the miner).

* Locks: :class:`FileLock` is an exclusive lock on a dedicated lock file:
  ``fcntl.flock`` on POSIX, an ``msvcrt.locking`` byte-range lock on Windows.
  Both are released when the holder closes the file or exits. Neither is
  re-entrant: a second acquire of the same path, even in the same process,
  waits (or raises :class:`LockHeld` when non-blocking).
* Identity: :func:`user_identity` is the POSIX uid or the Windows account SID
  from the process token (never an environment variable).
* Durability: :func:`fsync_file`, :func:`fsync_directory`; Windows has no
  directory handle through ``os.open``, so directory syncs are reported as not
  performed (NTFS journals rename and unlink metadata).
* Access control: :func:`restrict_to_current_user` and :func:`describe_access`
  (POSIX mode bits; on Windows an owner-only, protected DACL checked through
  its SDDL text).
* Processes: :func:`process_alive` never sends a signal on Windows, where
  ``os.kill`` is TerminateProcess; :func:`terminate_process` is the bounded
  last resort; :func:`bind_children_to_process` keeps worker processes from
  outliving the miner on Windows.
* Signals: :func:`install_stop_handlers` (asyncio signal handlers on POSIX,
  ``signal.signal`` for Ctrl+C / Ctrl+Break on Windows).
* CPUs: :func:`available_cpus` counts the logical CPUs this process may use.
"""

from __future__ import annotations

import contextlib
import errno
import os
import platform
import re
import signal
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator, Optional, Union

IS_WINDOWS = os.name == "nt"
IS_MACOS = sys.platform == "darwin"
_BINARY = getattr(os, "O_BINARY", 0)


def platform_id() -> str:
    """``macos``, ``windows``, ``linux`` or ``other``."""
    if sys.platform == "darwin":
        return "macos"
    if sys.platform == "win32":
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    return "other"


def host_platform() -> dict:
    """What this process runs on, for session records (no performance claim)."""
    return {
        "os": platform_id(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
    }


def _win32():
    from hyba_mine import _win32 as module

    return module


# ---------------------------------------------------------------------- locks
class LockHeld(BlockingIOError):
    """A non-blocking acquire found the lock held by another handle or process."""


class FileLock:
    """Exclusive lock on ``path`` (created 0600 if missing); not re-entrant."""

    mechanism = "msvcrt.locking" if IS_WINDOWS else "fcntl.flock"

    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)
        self._fd: Optional[int] = None

    @property
    def held(self) -> bool:
        return self._fd is not None

    def acquire(self, blocking: bool = True) -> "FileLock":
        if self._fd is not None:
            raise RuntimeError(f"lock {self.path} is already held by this FileLock")
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT | _BINARY, 0o600)
        try:
            if IS_WINDOWS:
                self._acquire_windows(fd, blocking)
            else:
                import fcntl

                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
                except BlockingIOError:
                    raise LockHeld(errno.EWOULDBLOCK, f"lock is held: {self.path}") from None
        except BaseException:
            os.close(fd)
            raise
        self._fd = fd
        return self

    def _acquire_windows(self, fd: int, blocking: bool) -> None:
        import msvcrt

        delay = 0.001
        while True:
            os.lseek(fd, 0, os.SEEK_SET)
            try:
                # LK_NBLCK in a loop: LK_LOCK gives up after ten one-second retries.
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                return
            except OSError as exc:
                if exc.errno not in (errno.EACCES, errno.EDEADLK, getattr(errno, "EDEADLOCK", errno.EDEADLK)):
                    raise
                if not blocking:
                    raise LockHeld(errno.EWOULDBLOCK, f"lock is held: {self.path}") from None
            time.sleep(delay)
            delay = min(0.05, delay * 2)

    def release(self) -> None:
        fd, self._fd = self._fd, None
        if fd is None:
            return
        try:
            if IS_WINDOWS:
                import msvcrt

                os.lseek(fd, 0, os.SEEK_SET)
                with contextlib.suppress(OSError):
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)

    def __enter__(self) -> "FileLock":
        return self.acquire(blocking=True)

    def __exit__(self, *exc) -> None:
        self.release()


@contextlib.contextmanager
def exclusive_lock(path: Union[str, Path], *, blocking: bool = True) -> Iterator[FileLock]:
    lock = FileLock(path).acquire(blocking=blocking)
    try:
        yield lock
    finally:
        lock.release()


def lock_is_held(path: Union[str, Path]) -> bool:
    """True when another handle holds the lock on ``path``; never leaves it held."""
    lock = FileLock(path)
    try:
        lock.acquire(blocking=False)
    except LockHeld:
        return True
    lock.release()
    return False


# ------------------------------------------------------------------- identity
@dataclass(frozen=True)
class UserIdentity:
    kind: str  # "posix_uid" or "windows_sid"
    value: Union[int, str]


class IdentityUnavailable(RuntimeError):
    """This account's identity could not be determined; callers fail closed."""


def user_identity() -> UserIdentity:
    if IS_WINDOWS:
        try:
            return UserIdentity("windows_sid", _win32().current_user_sid())
        except (OSError, ImportError) as exc:
            raise IdentityUnavailable(f"the Windows account SID could not be read ({exc})") from None
    getuid = getattr(os, "getuid", None)
    if getuid is None:
        raise IdentityUnavailable("this platform reports no user id")
    return UserIdentity("posix_uid", getuid())


# ----------------------------------------------------------------- durability
def fsync_file(path: Union[str, Path]) -> None:
    """Flush ``path`` to stable storage (Windows needs a writable handle for FlushFileBuffers)."""
    if IS_WINDOWS:
        fd = os.open(path, os.O_RDWR | _BINARY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return
    with open(path, "rb") as handle:
        os.fsync(handle.fileno())


def fsync_directory(path: Union[str, Path]) -> bool:
    """Flush a directory's entries. Returns False where the OS offers no directory handle (Windows)."""
    if IS_WINDOWS:
        return False
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return True


_SHARING_ERRORS = frozenset({5, 32})  # ERROR_ACCESS_DENIED, ERROR_SHARING_VIOLATION
_RETRY_ATTEMPTS = 20
_RETRY_DELAY = 0.05


def _retry_sharing(action: Callable[[], None]) -> None:
    if not IS_WINDOWS:
        action()
        return
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            action()
            return
        except PermissionError as exc:
            if getattr(exc, "winerror", None) not in _SHARING_ERRORS or attempt == _RETRY_ATTEMPTS - 1:
                raise
            # Another process has the file open without FILE_SHARE_DELETE; it closes it shortly.
            time.sleep(_RETRY_DELAY)


def replace_file(src: Union[str, Path], dst: Union[str, Path]) -> None:
    """``os.replace``; on Windows retried for about a second while a reader holds ``dst`` open."""
    _retry_sharing(lambda: os.replace(src, dst))


def unlink_file(path: Union[str, Path], *, missing_ok: bool = True) -> None:
    def action() -> None:
        try:
            os.unlink(path)
        except FileNotFoundError:
            if not missing_ok:
                raise

    _retry_sharing(action)


# -------------------------------------------------------------- access control
@dataclass(frozen=True)
class AccessReport:
    private: bool
    protected: bool
    foreign_trustees: tuple = ()
    mechanism: str = "posix_mode"
    error: Optional[str] = None
    detail: dict = field(default_factory=dict)


_ACE = re.compile(r"\((?P<type>[A-Z]+);(?P<flags>[A-Z]*);[^;()]*;[^;()]*;[^;()]*;(?P<sid>[^;()]+)(?:;[^()]*)?\)")
_GRANT_TYPES = frozenset({"A", "OA", "XA", "ZA"})


def _sddl_report(sddl: str, sid: str) -> AccessReport:
    text = sddl.strip()
    if not text.startswith("D:"):
        return AccessReport(False, False, (), "windows_dacl", "no DACL in the security descriptor")
    body = text[2:]
    if body.startswith("NO_ACCESS_CONTROL"):
        return AccessReport(False, False, ("Everyone (null DACL)",), "windows_dacl", None)
    head = body.split("(", 1)[0]
    protected = "P" in head.replace("AI", "").replace("AR", "")
    aces = list(_ACE.finditer(body))
    # Everything after the header must be well-formed ACEs; anything else fails closed.
    if "".join(m.group(0) for m in aces) != body[len(head):]:
        return AccessReport(False, protected, (), "windows_dacl", "the access list could not be parsed")
    foreign: list = []
    for ace in aces:
        if ace.group("type") not in _GRANT_TYPES:
            continue
        flags = ace.group("flags")
        if "IO" in [flags[i:i + 2] for i in range(0, len(flags), 2)]:
            continue  # inherit-only: grants nothing on this object
        trustee = ace.group("sid")
        if trustee not in (sid, "SY") and trustee not in foreign:
            foreign.append(trustee)
    return AccessReport(not foreign, protected, tuple(foreign), "windows_dacl", None)


def describe_access(path: Union[str, Path]) -> AccessReport:
    """Whether only this account (and, on Windows, LocalSystem) can access ``path``. Fails closed."""
    if IS_WINDOWS:
        try:
            win = _win32()
            return _sddl_report(win.get_dacl_sddl(str(path)), win.current_user_sid())
        except (OSError, ImportError) as exc:
            return AccessReport(False, False, (), "windows_dacl", f"{type(exc).__name__}: {exc}")
    try:
        mode = os.stat(path).st_mode & 0o777
    except OSError as exc:
        return AccessReport(False, False, (), "posix_mode", f"{type(exc).__name__}: {exc}")
    private = not (mode & 0o077)
    return AccessReport(private, True, () if private else (f"mode {mode:o}",), "posix_mode", None, {"mode": mode})


def restrict_to_current_user(path: Union[str, Path], *, directory: bool) -> None:
    """POSIX: chmod 0700/0600. Windows: protected DACL for this account and LocalSystem only."""
    if IS_WINDOWS:
        win = _win32()
        win.set_protected_dacl(str(path), win.current_user_sid(), directory=directory)
        return
    os.chmod(path, 0o700 if directory else 0o600)


# ------------------------------------------------------------------ processes
def process_alive(pid: int) -> bool:
    if pid is None or int(pid) <= 0:
        return False
    if IS_WINDOWS:
        return _win32().process_alive(int(pid))
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def process_image_name(pid: int) -> Optional[str]:
    """Full image path of ``pid`` on Windows; None elsewhere or when it cannot be read."""
    if not IS_WINDOWS:
        return None
    return _win32().process_image_name(int(pid))


def terminate_process(pid: int, *, wait_seconds: float = 5.0) -> bool:
    """Windows only: TerminateProcess, then wait up to ``wait_seconds``. True when it has exited."""
    if not IS_WINDOWS:
        raise RuntimeError("terminate_process is the Windows fallback; POSIX stops the miner with SIGTERM")
    return _win32().terminate_process(int(pid), wait_seconds)


_JOB_LOCK = threading.Lock()
_JOB: dict = {}


def bind_children_to_process() -> dict:
    """Windows: put this process (and every child it starts later) in a kill-on-close job object.

    When the process ends for any reason its worker processes end with it.
    Idempotent. Elsewhere, or when the job cannot be created, returns
    ``{"mechanism": "none", "active": False, "detail": ...}`` and nothing changes.
    """
    if not IS_WINDOWS:
        return {"mechanism": "none", "active": False,
                "detail": "POSIX: worker processes exit when their pipes to this process close"}
    with _JOB_LOCK:
        if "result" in _JOB:
            return dict(_JOB["result"])
        try:
            _JOB["handle"] = _win32().create_kill_on_close_job_for_current_process()
            result = {"mechanism": "windows_job_object_kill_on_close", "active": True}
        except (OSError, ImportError) as exc:
            result = {"mechanism": "none", "active": False,
                      "detail": f"job object not created ({type(exc).__name__}: {exc})"}
        _JOB["result"] = result
        return dict(result)


# -------------------------------------------------------------------- signals
def install_stop_handlers(loop, callback: Callable[[str], None]) -> tuple:
    """Route the OS stop signals to ``callback(reason)`` on ``loop``.

    Returns ``(mechanisms, restore)``. POSIX: SIGTERM and SIGINT through
    ``loop.add_signal_handler``. Windows: SIGINT (Ctrl+C) and SIGBREAK
    (Ctrl+Break) through ``signal.signal``, main thread only; a process started
    by Task Scheduler with pythonw receives neither, so ``hyba-mine stop``
    writes a stop request instead.
    """
    mechanisms: list = []
    if not IS_WINDOWS:
        installed = []
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, callback, f"signal {sig.name}")
            installed.append(sig)
            mechanisms.append(f"signal {sig.name}")

        def restore() -> None:
            for sig in installed:
                with contextlib.suppress(Exception):
                    loop.remove_signal_handler(sig)

        return mechanisms, restore
    if threading.current_thread() is not threading.main_thread():
        return mechanisms, lambda: None
    previous: dict = {}
    for name in ("SIGINT", "SIGBREAK"):
        sig = getattr(signal, name, None)
        if sig is None:
            continue

        def handler(signum, frame, _name=name) -> None:
            loop.call_soon_threadsafe(callback, f"signal {_name}")

        try:
            previous[sig] = signal.signal(sig, handler)
        except (OSError, ValueError):
            continue
        mechanisms.append(f"signal {name}")

    def restore() -> None:
        for sig, old in previous.items():
            with contextlib.suppress(OSError, ValueError, TypeError):
                signal.signal(sig, old if old is not None else signal.SIG_DFL)

    return mechanisms, restore


def prevent_idle_sleep() -> Optional[str]:
    """Windows: keep the system awake while this thread runs (the counterpart of caffeinate)."""
    if not IS_WINDOWS:
        return None
    try:
        return "SetThreadExecutionState" if _win32().keep_system_awake() else None
    except (OSError, ImportError):
        return None


# ----------------------------------------------------------------------- CPUs
def available_cpus() -> tuple:
    """(logical CPUs this process may run on, source of the count)."""
    counter = getattr(os, "process_cpu_count", None)
    if counter is not None:
        count = counter()
        if count:
            return int(count), "os.process_cpu_count"
    affinity = getattr(os, "sched_getaffinity", None)
    if affinity is not None:
        with contextlib.suppress(OSError):
            count = len(affinity(0))
            if count:
                return count, "sched_getaffinity"
    if IS_WINDOWS:
        with contextlib.suppress(OSError, ImportError):
            count = _win32().process_affinity_count()
            if count:
                return count, "GetProcessAffinityMask"
    return max(1, os.cpu_count() or 1), "os.cpu_count"
