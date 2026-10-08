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

import os
import sys
from pathlib import Path

try:
    import pytest
except (
    ImportError
):  # only pytest loads a conftest; keeps DS02 from reading it as a runtime dependency
    pytest = None

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PLATFORM = _REPO_ROOT / "chronus/mla1517_platform" / "python"
_TURING = _REPO_ROOT / "turing_universal_quantum_computer"

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

_TURING_PATH = str(_TURING)
while _TURING_PATH in sys.path:
    sys.path.remove(_TURING_PATH)
sys.path.insert(0, _TURING_PATH)

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


if pytest is not None:

    @pytest.fixture(autouse=True)
    def _hermetic_runtime_config(monkeypatch, tmp_path):
        """Keep the control plane off the repo's real ``data/runtime_config.json``.

        ``runtime_config.config_path()`` falls back to that file when
        ``PYTHIA_RUNTIME_CONFIG`` is unset, so any test that drives the control API
        or the coordinator without overriding it persisted its config there and
        changed what every later test (and run) observed, e.g. a leaked 3 H/s
        hashrate target throttling an unrelated mining voyage. A test or operator
        that sets the variable itself still wins.
        """
        if not os.environ.get("PYTHIA_RUNTIME_CONFIG", "").strip():
            monkeypatch.setenv("PYTHIA_RUNTIME_CONFIG", str(tmp_path / "runtime_config.json"))


    # Every operator-facing Chronus vIGPU variable. A value in the developer's
    # shell (for example ``CHRONUS_VIGPU_ENDPOINT`` left over from running a
    # sidecar) must not change the delivery contract a test asserts.
    _CHRONUS_VIGPU_AMBIENT = (
        "CHRONUS_VIGPU_ENDPOINT",
        "CHRONUS_VIGPU_TOKEN",
        "CHRONUS_VIGPU_HMAC_KEY",
        "CHRONUS_VIGPU_PRODUCTION",
        "CHRONUS_VIGPU_THESEUS",
        "CHRONUS_VIGPU_BUILD",
        "CHRONUS_VIGPU_HOST",
        "CHRONUS_VIGPU_PORT",
        "CHRONUS_VIGPU_TIMEOUT",
    )

    @pytest.fixture(scope="session")
    def _chronus_vigpu_session_store(tmp_path_factory):
        return tmp_path_factory.mktemp("chronus-vigpu")

    @pytest.fixture(autouse=True)
    def _hermetic_chronus_vigpu(monkeypatch, _chronus_vigpu_session_store):
        """Keep the Chronus virtual iGPU off the developer's shell and real store.

        Without ``CHRONUS_VIGPU_STORE`` the embedded daemon writes its evidence
        ledger to ``.chronus-virtual-igpu`` in the working directory, so tests
        inherited (and extended) whatever ledger a previous run or a local
        operator left there. The store is per session because the embedded
        daemon is process-global; a test that sets its own store still wins.
        """
        for name in _CHRONUS_VIGPU_AMBIENT:
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("CHRONUS_VIGPU_STORE", str(_chronus_vigpu_session_store))
