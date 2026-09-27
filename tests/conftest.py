"""Pytest bootstrap for the consolidated repo-root packages.

``toe``, ``kellogg``, ``aethel``, ``millennium``, ``Intelligence`` and the
platform modules must resolve to THIS checkout.  A foreign editable install
on ``sys.path`` — e.g. a case-insensitive ``TOE/`` directory from another
worktree — otherwise shadows them, so tests can pass or fail against the
wrong code (retired-path contracts included).  Pytest imports this file
before collecting any test module, so the insertions below run ahead of
every test-file import.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PLATFORM = _REPO_ROOT / "mla1517_platform_v3.4" / "python"

# Re-home first so the repo root lands at sys.path[0]: the platform tree
# carries its own bare ``turing_core`` shim which must NOT shadow the root
# ``turing_core.py`` that root packages resolve against. Both paths may
# already be present via PYTHONPATH or an editable install — the
# not-in-path check alone cannot repair a wrong order, so remove before
# inserting.
for _path in (str(_PLATFORM), str(_REPO_ROOT)):
    while _path in sys.path:
        sys.path.remove(_path)
    sys.path.insert(0, _path)
