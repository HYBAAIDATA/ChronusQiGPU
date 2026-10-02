"""The software revision stamped on every agentic evidence record.

Every decision the autonomous runtime emits must name the software that
made it. The revision is resolved once at construction from, in order:

* ``PYTHIA_SOFTWARE_REVISION`` — an explicit deployment stamp (CI builds
  and packaged releases set this when no VCS checkout exists);
* ``git rev-parse HEAD`` at the repository containing this package;
* ``"unavailable"`` — never an invented value. When no revision can be
  established the record says so, which is itself evidence.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]


def software_revision() -> str:
    configured = os.getenv("PYTHIA_SOFTWARE_REVISION", "").strip()
    if configured:
        return configured
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unavailable"
    head = result.stdout.strip()
    if result.returncode == 0 and len(head) >= 7:
        return head
    return "unavailable"
