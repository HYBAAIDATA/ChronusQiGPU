# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
"""Optional launchd agent that starts HYBA Mine at login on macOS.

The agent (``~/Library/LaunchAgents/ae.hybadata.mine.plist``) runs
``scripts/mine/run.sh``, which always runs the pre-flight before mining.
``KeepAlive.SuccessfulExit = false`` restarts the miner after a crash or a
failed pre-flight (no sooner than every two minutes) but not after a clean
stop, so ``hyba-mine stop`` stays stopped until the next login or
``hyba-mine autostart enable``.
"""

from __future__ import annotations

import os
import plistlib
import subprocess
from pathlib import Path

from hyba_mine.paths import LAUNCH_AGENT_LABEL, Layout, is_macos, launch_agent_path

LAUNCHCTL = "/bin/launchctl"
DEFAULT_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


def plist_payload(run_script: Path, layout: Layout) -> dict:
    return {
        "Label": LAUNCH_AGENT_LABEL,
        "ProgramArguments": ["/bin/bash", str(run_script)],
        "WorkingDirectory": str(run_script.resolve().parent.parent.parent),
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "ThrottleInterval": 120,
        "StandardOutPath": str(layout.logs / "launchd.out.log"),
        "StandardErrorPath": str(layout.logs / "launchd.err.log"),
        "EnvironmentVariables": {
            "PATH": DEFAULT_PATH,
            "HYBA_MINE_HOME": str(layout.home),
            "HYBA_MINE_LOG_DIR": str(layout.logs),
            "HYBA_MINE_VENV": os.environ.get("HYBA_MINE_VENV", str(Path.home() / ".hyba-mine" / "venv")),
        },
    }


def _domain() -> str:
    return f"gui/{os.getuid()}"


def _launchctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([LAUNCHCTL, *args], capture_output=True, text=True, timeout=30, check=False)


def enable(run_script: Path, layout: Layout, *, start: bool = True) -> Path:
    if not is_macos():
        raise RuntimeError("launchd auto-start is available on macOS only")
    if not run_script.exists():
        raise FileNotFoundError(f"run script not found: {run_script}")
    layout.prepare()
    path = launch_agent_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(plistlib.dumps(plist_payload(run_script, layout)))
    os.chmod(path, 0o644)
    if not start:
        return path
    _launchctl("bootout", f"{_domain()}/{LAUNCH_AGENT_LABEL}")
    done = _launchctl("bootstrap", _domain(), str(path))
    if done.returncode != 0:
        raise RuntimeError(f"launchctl bootstrap failed: {done.stderr.strip() or done.returncode}")
    return path


def disable() -> bool:
    if not is_macos():
        return False
    _launchctl("bootout", f"{_domain()}/{LAUNCH_AGENT_LABEL}")
    path = launch_agent_path()
    if path.exists():
        path.unlink()
        return True
    return False


def status() -> dict:
    path = launch_agent_path()
    loaded = is_macos() and _launchctl("print", f"{_domain()}/{LAUNCH_AGENT_LABEL}").returncode == 0
    return {"label": LAUNCH_AGENT_LABEL, "plist": str(path), "installed": path.exists(), "loaded": bool(loaded)}
