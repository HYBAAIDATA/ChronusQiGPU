# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Pool logins: macOS Keychain, Windows Credential Manager, or a private file outside any repository.

A login never leaves the operator's machine. It is entered at the terminal
(``hyba-mine login <pool>``), stored in the login keychain (service
``HYBA-Mine``, account ``pool:<pool id>``) or in a 0600 JSON file under the
HYBA Mine home, and read only when a pool connection is opened. Nothing here
logs a value or puts one in an exception message; ``PoolLogin`` hides both
fields from ``repr``.

On Windows the login is a generic credential (target ``HYBA-Mine:pool:<pool id>``,
persisted for this user on this machine) written and read through the Win32
Credential Manager API in-process, so it never appears in a command line.

The keychain is driven through ``/usr/bin/security -i``. Writes pass an
encoded command on standard input, keeping credentials out of process arguments.
See Apple's SecurityTool/macOS/security.1 and security.c (interactive mode).
"""

from __future__ import annotations

import json
import subprocess
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Protocol

from hyba_mine.control import _locked
from hyba_mine.logsafe import login_fingerprint, register_login, worker_label
from hyba_mine.paths import Layout, is_macos, is_windows, refuse_inside_repository, write_private_file
from hyba_mine.portable import describe_access
from hyba_mine.pools import get_pool, validate_password, validate_username

KEYCHAIN_SERVICE = "HYBA-Mine"
SECURITY_TOOL = "/usr/bin/security"


class CredentialMissing(RuntimeError):
    """No login is stored for the pool; mining must not start."""


class CredentialStoreError(RuntimeError):
    """The store could not be read or written."""


@dataclass(frozen=True)
class PoolLogin:
    username: str
    password: str

    def __repr__(self) -> str:
        return f"PoolLogin(fingerprint={self.fingerprint}, worker={self.worker!r})"

    __str__ = __repr__

    @property
    def fingerprint(self) -> str:
        return login_fingerprint(self.username)

    @property
    def worker(self) -> Optional[str]:
        return worker_label(self.username)

    def public(self) -> dict:
        return {"login_fingerprint": self.fingerprint, "worker": self.worker}


class CredentialStore(Protocol):
    backend: str

    def get(self, pool_id: str) -> Optional[PoolLogin]: ...

    def put(self, pool_id: str, login: PoolLogin) -> None: ...

    def delete(self, pool_id: str) -> bool: ...


def _encode(login: PoolLogin) -> str:
    return json.dumps({"username": login.username, "password": login.password}, separators=(",", ":"))


def _decode(raw: str) -> PoolLogin:
    text = raw.strip("\n")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        try:
            data = json.loads(bytes.fromhex(text.strip()).decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise CredentialStoreError("stored login is not readable") from exc
    if not isinstance(data, dict) or not isinstance(data.get("username"), str) or not isinstance(data.get("password"), str):
        raise CredentialStoreError("stored login has an unexpected shape")
    return PoolLogin(data["username"], data["password"])


class KeychainStore:
    """Login keychain items, one per pool."""

    backend = "keychain"

    def __init__(self, command: tuple = (SECURITY_TOOL,)) -> None:
        if not command or not Path(command[0]).exists():
            raise CredentialStoreError("macOS 'security' tool not found; use the file store")
        self.command = tuple(command)

    @staticmethod
    def _account(pool_id: str) -> str:
        return f"pool:{get_pool(pool_id).pool_id}"

    def _run(self, args: list[str], *, private_input: bool = False) -> subprocess.CompletedProcess:
        command = [*self.command, "-i"] if private_input else [*self.command, *args]
        # Hex encoding keeps the value a single unquoted word in Apple's parser.
        input_text = shlex.join(args) + "\n" if private_input else None
        if input_text is not None and len(input_text.encode("utf-8")) >= 4096:
            raise CredentialStoreError("encoded login exceeds the keychain command limit")
        try:
            return subprocess.run(command, input=input_text, capture_output=True,
                                  text=True, timeout=30, check=False)
        except subprocess.TimeoutExpired:
            raise CredentialStoreError("keychain command timed out") from None

    def get(self, pool_id: str) -> Optional[PoolLogin]:
        done = self._run(["find-generic-password", "-s", KEYCHAIN_SERVICE, "-a", self._account(pool_id), "-w"])
        if done.returncode != 0:
            return None
        login = _decode(done.stdout)
        register_login(login.username, login.password)
        return login

    def put(self, pool_id: str, login: PoolLogin) -> None:
        profile = get_pool(pool_id)
        register_login(login.username, login.password)
        done = self._run(
            [
                "add-generic-password", "-U",
                "-s", KEYCHAIN_SERVICE,
                "-a", self._account(pool_id),
                "-l", f"HYBA Mine pool login ({profile.name})",
                "-j", "HYBA Mine treasury mining; local only",
                "-w", _encode(login).encode("utf-8").hex(),
            ], private_input=True
        )
        if done.returncode != 0:
            raise CredentialStoreError(f"keychain refused the login (security exit {done.returncode})")
        stored = self.get(pool_id)
        if stored != login:
            raise CredentialStoreError("keychain read-back did not match the login just stored")

    def delete(self, pool_id: str) -> bool:
        done = self._run(["delete-generic-password", "-s", KEYCHAIN_SERVICE, "-a", self._account(pool_id)])
        return done.returncode == 0


class FileStore:
    """0600 JSON file under the HYBA Mine home; refused inside a git work tree."""

    backend = "file"

    def __init__(self, path: Path) -> None:
        refuse_inside_repository(path, "pool credentials")
        self.path = path

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        access = describe_access(self.path)
        if not access.private:
            fix = "run: chmod 600" if access.mechanism == "posix_mode" else "restrict its access list to your account, or run: hyba-mine login again"
            raise CredentialStoreError(
                f"{self.path} is accessible to other accounts ({', '.join(access.foreign_trustees) or access.error}); {fix}"
            )
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CredentialStoreError("credential file is not valid JSON") from exc
        if not isinstance(data, dict):
            raise CredentialStoreError("credential file has an unexpected shape")
        return data

    def get(self, pool_id: str) -> Optional[PoolLogin]:
        entry = self._load().get(get_pool(pool_id).pool_id)
        if entry is None:
            return None
        login = _decode(json.dumps(entry))
        register_login(login.username, login.password)
        return login

    def put(self, pool_id: str, login: PoolLogin) -> None:
        register_login(login.username, login.password)
        with _locked(self.path):
            data = self._load()
            data[get_pool(pool_id).pool_id] = json.loads(_encode(login))
            self._write(data)

    def _write(self, data: dict) -> None:
        write_private_file(self.path, (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8"))
        if not describe_access(self.path).private:
            self.path.unlink()
            raise CredentialStoreError(
                f"the filesystem holding {self.path.parent} does not keep access restrictions; "
                "use the system credential store or set HYBA_MINE_HOME on a local disk"
            )

    def delete(self, pool_id: str) -> bool:
        with _locked(self.path):
            data = self._load()
            removed = data.pop(get_pool(pool_id).pool_id, None) is not None
            if removed:
                self._write(data)
            return removed


class WindowsCredentialStore:
    """Windows Credential Manager, generic credential per pool, this user on this machine."""

    backend = "wincred"
    TARGET_PREFIX = f"{KEYCHAIN_SERVICE}:pool:"

    def __init__(self, api=None) -> None:
        if api is None:
            from hyba_mine import _win32 as api  # Windows only; imported lazily
        self._api = api

    def _target(self, pool_id: str) -> str:
        return self.TARGET_PREFIX + get_pool(pool_id).pool_id

    def get(self, pool_id: str) -> Optional[PoolLogin]:
        try:
            record = self._api.cred_read(self._target(pool_id))
        except OSError as exc:
            raise CredentialStoreError(f"Credential Manager read failed (error {getattr(exc, 'winerror', '?')})") from None
        if record is None:
            return None
        try:
            login = _decode(record.blob.decode("utf-8"))
        except UnicodeDecodeError:
            raise CredentialStoreError("stored login is not readable") from None
        register_login(login.username, login.password)
        return login

    def put(self, pool_id: str, login: PoolLogin) -> None:
        register_login(login.username, login.password)
        try:
            self._api.cred_write(self._target(pool_id), f"pool:{get_pool(pool_id).pool_id}",
                                 "HYBA Mine pool login", _encode(login).encode("utf-8"))
        except OSError as exc:
            raise CredentialStoreError(f"Credential Manager write failed (error {getattr(exc, 'winerror', '?')})") from None

    def delete(self, pool_id: str) -> bool:
        try:
            return bool(self._api.cred_delete(self._target(pool_id)))
        except OSError as exc:
            raise CredentialStoreError(f"Credential Manager delete failed (error {getattr(exc, 'winerror', '?')})") from None


STORE_BACKENDS = ("keychain", "wincred", "file")


def default_backend() -> str:
    if is_macos() and Path(SECURITY_TOOL).exists():
        return "keychain"
    if is_windows():
        return "wincred"
    return "file"


def open_store(backend: Optional[str], layout: Layout) -> CredentialStore:
    chosen = backend or default_backend()
    if chosen == "keychain":
        if not is_macos():
            raise ValueError("the keychain store is macOS only; use 'wincred' on Windows or 'file'")
        return KeychainStore()
    if chosen == "wincred":
        if not is_windows():
            raise ValueError("the wincred store is Windows only; use 'keychain' on macOS or 'file'")
        return WindowsCredentialStore()
    if chosen == "file":
        return FileStore(layout.credentials)
    raise ValueError(f"credential store must be one of {', '.join(STORE_BACKENDS)}")


def make_login(pool_id: str, username: str, password: str) -> PoolLogin:
    validate_username(pool_id, username)
    validate_password(password)
    return PoolLogin(username, password)


def require_login(store: CredentialStore, pool_id: str) -> PoolLogin:
    """Fail closed: return the stored login or raise CredentialMissing."""
    try:
        login = store.get(pool_id)
    except CredentialStoreError as exc:
        raise CredentialMissing(f"the {get_pool(pool_id).name} login could not be read: {exc}") from exc
    if login is None or not login.username or not login.password:
        raise CredentialMissing(
            f"no {get_pool(pool_id).name} login is stored on this machine; run: hyba-mine login {pool_id}"
        )
    return login
