# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Shared helpers for the fleet tests (not a test module)."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent


def package_pythonpath() -> str:
    """PYTHONPATH for a child process: the same chronus package plus the repository root (for tests.*)."""
    import chronus

    roots = [str(Path(entry).resolve().parent) for entry in chronus.__path__]
    existing = [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p]
    ordered = []
    for entry in existing + roots + [str(TESTS_DIR.parent)]:
        if entry not in ordered:
            ordered.append(entry)
    return os.pathsep.join(ordered)


def child_env(**extra: str) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = package_pythonpath()
    env["PYTHONUNBUFFERED"] = "1"
    env.update(extra)
    return env


def filesystem_keeps_modes(directory: str | Path) -> bool:
    if os.name != "posix":
        return False
    probe = Path(directory) / ".mode-probe"
    probe.write_text("x")
    os.chmod(probe, 0o600)
    kept = (probe.stat().st_mode & 0o777) == 0o600
    probe.unlink()
    return kept


def state_dir() -> tempfile.TemporaryDirectory:
    return tempfile.TemporaryDirectory(prefix="chronus-fleet-test-", ignore_cleanup_errors=True)


PYTHON = sys.executable

PLUGIN_MODULE = "tests.fleet_test_kernels"
