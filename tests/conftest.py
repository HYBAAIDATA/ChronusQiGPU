"""Pytest bootstrap for the consolidated repo-root packages.

``toe``, ``kellogg``, ``aethel``, ``millennium``, ``Intelligence`` and the
platform modules must resolve to THIS checkout.  A foreign editable install
on ``sys.path`` — e.g. a case-insensitive ``TOE/`` directory from another
worktree — otherwise shadows them, so tests can pass or fail against the
wrong code (retired-path contracts included).  Pytest imports this file
before collecting any test module, so the insertions below run ahead of
every test-file import.

The same bootstrap installs the ``hyba_compat`` shim, which maps the
pre-consolidation ``hyba_backend`` / ``hyba_platform`` / ``src`` import roots
onto their canonical implementations in this repository.  It must run before
any intelligence module is imported.
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

# ``tests/test_agentic_mining.py`` appends ``<repo>/Intelligence`` to
# ``sys.path`` so its fallback ``import agentic_mining`` can resolve. That makes
# ``Intelligence/`` a source root, and its ``asi/`` subpackage then shadows the
# top-level ``asi`` package this repo also ships — so a later
# ``import asi.asi_core`` resolves to ``Intelligence.asi`` and fails. Drop that
# entry again and re-homing the repo root, so the top-level ``asi`` wins
# deterministically regardless of test execution order.
_INTELLIGENCE_DIR = str(_REPO_ROOT / "Intelligence")
while _INTELLIGENCE_DIR in sys.path:
    sys.path.remove(_INTELLIGENCE_DIR)

# Legacy-namespace compatibility: must precede every intelligence import.
import hyba_compat  # noqa: E402

hyba_compat.install()

