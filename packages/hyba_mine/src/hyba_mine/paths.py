# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Where HYBA Mine keeps its local state, logs and launch agent.

Everything lives on the operator's machine, outside any source checkout:

* state, ledger, approval and control files: ``HYBA_MINE_HOME`` or, on macOS,
  ``~/Library/Application Support/HYBA-Mine`` (``~/.local/share/hyba-mine``
  elsewhere);
* logs: ``HYBA_MINE_LOG_DIR`` or, on macOS, ``~/Library/Logs/HYBA-Mine``;
* the launchd agent: ``~/Library/LaunchAgents/ae.hybadata.mine.plist``.

Directories are created with mode 0700 and files with 0600. Paths inside a git
work tree are refused for anything that can hold a credential.
"""

from __future__ import annotations

import os
import tempfile
import sys
from pathlib import Path
from typing import Optional

APP_DIR_NAME = "HYBA-Mine"
LAUNCH_AGENT_LABEL = "ae.hybadata.mine"


def is_macos() -> bool:
    return sys.platform == "darwin"


def home_dir() -> Path:
    override = os.environ.get("HYBA_MINE_HOME")
    if override:
        return Path(override).expanduser()
    if is_macos():
        return Path.home() / "Library" / "Application Support" / APP_DIR_NAME
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home).expanduser() if data_home else Path.home() / ".local" / "share"
    return base / "hyba-mine"


def log_dir() -> Path:
    override = os.environ.get("HYBA_MINE_LOG_DIR")
    if override:
        return Path(override).expanduser()
    if is_macos():
        return Path.home() / "Library" / "Logs" / APP_DIR_NAME
    return home_dir() / "logs"


def launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def ensure_private_dir(path: Path) -> Path:
    """Create ``path`` (and parents) and restrict it to the current user."""
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)
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
    """Atomically replace ``path`` with ``data``; the file is created 0600."""
    ensure_private_dir(path.parent)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


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
    def console_token(self) -> Path:
        return self.home / "console.token"

    @property
    def log_file(self) -> Path:
        return self.logs / "hyba-mine.log"

    def prepare(self) -> "Layout":
        ensure_private_dir(self.home)
        ensure_private_dir(self.logs)
        return self
