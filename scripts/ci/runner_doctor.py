#!/usr/bin/env python3
"""Fail fast on a misconfigured critical-path self-hosted runner.

Checks: usable Python, git on PATH, and that the runner work directory is
not under OneDrive (sync locks break builds and import benchmarks).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# Critical-path workflow pins 3.13 via actions/setup-python.
CI_PYTHON = (3, 13)
LOCAL_MIN_PYTHON = (3, 10)
ONEDRIVE_MARKERS = ("onedrive",)


def _fail(message: str) -> int:
    print(f"runner-doctor: FAIL — {message}", file=sys.stderr)
    return 1


def _ok(message: str) -> None:
    print(f"runner-doctor: ok — {message}")


def _work_roots() -> list[Path]:
    roots: list[Path] = []
    for key in ("RUNNER_WORKSPACE", "GITHUB_WORKSPACE", "RUNNER_TEMP"):
        value = os.environ.get(key)
        if value:
            roots.append(Path(value).resolve())
    # Fall back to cwd (usually the checked-out workspace under _work).
    roots.append(Path.cwd().resolve())
    return roots


def _under_onedrive(path: Path) -> bool:
    """True if any path component is OneDrive or ``OneDrive - <org>``."""
    for part in path.parts:
        lowered = part.lower()
        if lowered == "onedrive" or lowered.startswith("onedrive "):
            return True
        if lowered.startswith("onedrive-"):  # rare compacted forms
            return True
    return False


def main() -> int:
    version = sys.version_info[:2]
    on_actions = os.environ.get("GITHUB_ACTIONS") == "true"
    if on_actions and version != CI_PYTHON:
        return _fail(
            f"critical-path CI pins Python {CI_PYTHON[0]}.{CI_PYTHON[1]} "
            f"(got {sys.version.split()[0]}); fix setup-python"
        )
    if version < LOCAL_MIN_PYTHON:
        return _fail(
            f"need Python {LOCAL_MIN_PYTHON[0]}.{LOCAL_MIN_PYTHON[1]}+ "
            f"(got {sys.version.split()[0]})"
        )
    _ok(f"python {sys.version.split()[0]}")

    git = shutil.which("git")
    if not git:
        return _fail("git is not on PATH; install Git for Windows and re-open the shell")
    _ok(f"git at {git}")

    for root in _work_roots():
        if _under_onedrive(root):
            return _fail(
                f"work path {root} is under OneDrive; re-register the runner with "
                r"config.cmd --work C:\actions-runner\_work (outside OneDrive)"
            )
    _ok("work path is outside OneDrive markers")
    print("runner-doctor: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
