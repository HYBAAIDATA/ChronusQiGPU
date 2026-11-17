# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Where HYBA Mine keeps its local state, logs and auto-start definition.

Everything lives on the operator's machine, outside any source checkout.
``HYBA_MINE_HOME`` and ``HYBA_MINE_LOG_DIR`` override the defaults on every OS.

=========  ==================================================  ==========================================
OS         state, ledger, approval and control files           logs
=========  ==================================================  ==========================================
macOS      ``~/Library/Application Support/HYBA-Mine``          ``~/Library/Logs/HYBA-Mine``
Windows    ``%LOCALAPPDATA%\\HYBA-Mine``                        ``%LOCALAPPDATA%\\HYBA-Mine\\Logs``
Linux      ``$XDG_DATA_HOME/hyba-mine`` (``~/.local/share``)    ``$XDG_STATE_HOME/hyba-mine/logs``
=========  ==================================================  ==========================================

On Linux the logs stay in ``<home>/logs`` when only ``HYBA_MINE_HOME`` is set.
Auto-start: the launchd agent ``~/Library/LaunchAgents/ae.hybadata.mine.plist``
(macOS), the Task Scheduler task ``HYBA-Mine`` (Windows) or the systemd user
unit ``$XDG_CONFIG_HOME/systemd/user/hyba-mine.service`` (Linux).

Directories and files are private to this account: mode 0700/0600 on POSIX;
on Windows a protected access list granting only this account and LocalSystem
(the profile folder alone is not enough: it can be readable by other local
accounts). Paths inside a git work tree are refused for anything that can
hold a credential.
"""

from __future__ import annotations

import logging
import os
import tempfile
import sys
from pathlib import Path
from typing import Mapping, Optional, Tuple

from hyba_mine import portable

APP_DIR_NAME = "HYBA-Mine"
LAUNCH_AGENT_LABEL = "ae.hybadata.mine"
WINDOWS_TASK_NAME = "HYBA-Mine"
SYSTEMD_UNIT_NAME = "hyba-mine.service"
log = logging.getLogger("hyba_mine.paths")


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_windows() -> bool:
    return sys.platform == "win32"


def is_linux() -> bool:
    return sys.platform.startswith("linux")


def default_dirs(platform_id: Optional[str] = None, env: Optional[Mapping[str, str]] = None,
                 user_home: Optional[Path] = None) -> Tuple[Path, Path]:
    """(home, logs) for ``platform_id`` (default: this OS); overrides in ``env`` always win."""
    platform_id = platform_id or portable.platform_id()
    env = os.environ if env is None else env
    user_home = Path(user_home) if user_home is not None else Path.home()
    home_override = env.get("HYBA_MINE_HOME")
    logs_override = env.get("HYBA_MINE_LOG_DIR")
    home_env = Path(home_override).expanduser() if home_override else None
    logs_env = Path(logs_override).expanduser() if logs_override else None
    if platform_id == "macos":
        home = home_env or user_home / "Library" / "Application Support" / APP_DIR_NAME
        logs = logs_env or user_home / "Library" / "Logs" / APP_DIR_NAME
        return home, logs
    if platform_id == "windows":
        local = env.get("LOCALAPPDATA")
        base = Path(local) if local and Path(local).is_absolute() else user_home / "AppData" / "Local"
        home = home_env or base / APP_DIR_NAME
        return home, logs_env or home / "Logs"
    data_home = env.get("XDG_DATA_HOME")
    home = home_env or (Path(data_home).expanduser() if data_home else user_home / ".local" / "share") / "hyba-mine"
    if logs_env is not None:
        return home, logs_env
    if home_env is not None:
        return home, home / "logs"
    state_home = env.get("XDG_STATE_HOME")
    base = Path(state_home).expanduser() if state_home else user_home / ".local" / "state"
    return home, base / "hyba-mine" / "logs"


def home_dir() -> Path:
    return default_dirs()[0]


def log_dir() -> Path:
    return default_dirs()[1]


def launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def systemd_user_unit_path(env: Optional[Mapping[str, str]] = None, user_home: Optional[Path] = None) -> Path:
    env = os.environ if env is None else env
    config = env.get("XDG_CONFIG_HOME")
    base = Path(config).expanduser() if config else (Path(user_home) if user_home else Path.home()) / ".config"
    return base / "systemd" / "user" / SYSTEMD_UNIT_NAME


_restricted: set = set()


def ensure_private_dir(path: Path) -> Path:
    """Create ``path`` (and parents) and restrict it to the current user.

    POSIX: mode 0700. Windows: a protected owner-only DACL, applied once per process per path.
    """
    path.mkdir(parents=True, exist_ok=True)
    if not portable.IS_WINDOWS:
        os.chmod(path, 0o700)
        return path
    key = os.path.normcase(str(path.resolve()))
    if key in _restricted:
        return path
    report = portable.describe_access(path)
    if not (report.private and report.protected):
        try:
            portable.restrict_to_current_user(path, directory=True)
        except OSError as exc:
            # Credential files verify their own access list and fail closed.
            log.warning("could not restrict %s to this account (%s)", path, exc)
            return path
    _restricted.add(key)
    return path


def git_worktree_root(path: Path) -> Optional[Path]:
    """Return the git work tree containing ``path``, or None."""
    current = path.expanduser().resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def refuse_inside_repository(path: Path, what: str) -> None:
    root = git_worktree_root(path)
    if root is not None:
        raise ValueError(
            f"refusing to keep {what} inside the git work tree {root}; "
            "set HYBA_MINE_HOME to a directory outside any repository"
        )


def write_private_file(path: Path, data: bytes) -> None:
    """Atomically replace ``path`` with ``data``; the file is private (0600 or an owner-only DACL)."""
    ensure_private_dir(path.parent)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(temporary)
    try:
        if portable.IS_WINDOWS:
            # Owner-only before any byte is written; os.replace keeps the access list.
            try:
                portable.restrict_to_current_user(tmp, directory=False)
            except BaseException:
                os.close(fd)
                raise
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        portable.replace_file(tmp, path)
    finally:
        if tmp.exists():
            portable.unlink_file(tmp)


class Layout:
    """Resolved file locations for one HYBA Mine home."""

    def __init__(self, home: Optional[Path] = None, logs: Optional[Path] = None) -> None:
        self.home = (home or home_dir()).expanduser()
        self.logs = (logs or log_dir()).expanduser()

    @property
    def ledger(self) -> Path:
        return self.home / "ledger.jsonl"

    @property
    def ledger_lock(self) -> Path:
        return self.home / "ledger.lock"

    @property
    def state(self) -> Path:
        return self.home / "state.json"

    @property
    def approval(self) -> Path:
        return self.home / "approval.json"

    @property
    def control(self) -> Path:
        return self.home / "control.json"

    @property
    def credentials(self) -> Path:
        return self.home / "credentials.json"

    @property
    def pid(self) -> Path:
        return self.home / "miner.pid"

    @property
    def instance_lock(self) -> Path:
        return self.home / "miner.lock"

    @property
    def stop_request(self) -> Path:
        return self.home / "stop.json"

    @property
    def autostart_dir(self) -> Path:
        return self.home / "autostart"

    @property
    def console_token(self) -> Path:
        return self.home / "console.token"

    @property
    def log_file(self) -> Path:
        return self.logs / "hyba-mine.log"

    def prepare(self) -> "Layout":
        ensure_private_dir(self.home)
        ensure_private_dir(self.logs)
        return self
