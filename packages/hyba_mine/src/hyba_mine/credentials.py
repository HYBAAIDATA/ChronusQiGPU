# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Pool logins: macOS Keychain, or a 0600 file outside any repository.

A login never leaves the operator's machine. It is entered at the terminal
(``hyba-mine login <pool>``), stored in the login keychain (service
``HYBA-Mine``, account ``pool:<pool id>``) or in a 0600 JSON file under the
HYBA Mine home, and read only when a pool connection is opened. Nothing here
logs a value or puts one in an exception message; ``PoolLogin`` hides both
fields from ``repr``.

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
from hyba_mine.paths import Layout, is_macos, refuse_inside_repository, write_private_file
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
        mode = self.path.stat().st_mode & 0o777
        if mode & 0o077:
            raise CredentialStoreError(
                f"{self.path} is readable by other users (mode {mode:o}); run: chmod 600 '{self.path}'"
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
        if self.path.stat().st_mode & 0o077:
            self.path.unlink()
            raise CredentialStoreError(
                f"the filesystem holding {self.path.parent} does not keep file permissions; "
                "use the macOS Keychain or set HYBA_MINE_HOME on a local disk"
            )

    def delete(self, pool_id: str) -> bool:
        with _locked(self.path):
            data = self._load()
            removed = data.pop(get_pool(pool_id).pool_id, None) is not None
            if removed:
                self._write(data)
            return removed


def default_backend() -> str:
    return "keychain" if is_macos() and Path(SECURITY_TOOL).exists() else "file"


def open_store(backend: Optional[str], layout: Layout) -> CredentialStore:
    chosen = backend or default_backend()
    if chosen == "keychain":
        return KeychainStore()
    if chosen == "file":
        return FileStore(layout.credentials)
    raise ValueError("credential store must be 'keychain' or 'file'")


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
