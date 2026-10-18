"""Pytest fixtures for the platform suite."""

import os
import sys
from pathlib import Path

_PLATFORM_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PLATFORM_DIR.parents[2]
_TURING = _REPO_ROOT / "turing_universal_quantum_computer"
_CHRONOS_IGPU = _REPO_ROOT / "packages" / "chronos-one-igpu" / "src"
_PYTHIA_CONSUMER = _REPO_ROOT / "packages" / "pythia-consumer" / "src"

for _p in [str(_REPO_ROOT), str(_PLATFORM_DIR), str(_TURING), str(_CHRONOS_IGPU), str(_PYTHIA_CONSUMER)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    import pytest
except (
    ImportError
):  # only pytest loads a conftest; keeps DS02 from reading it as a runtime dependency
    pytest = None


if pytest is not None:

    @pytest.fixture(autouse=True)
    def _hermetic_runtime_config(monkeypatch, tmp_path):
        """Keep platform tests off the repo's real ``data/runtime_config.json``.

        ``runtime_config.config_path()`` falls back to that file when
        ``PYTHIA_RUNTIME_CONFIG`` is unset, so state persisted by an earlier test or
        run (for example a 3 H/s hashrate target) changed what unrelated mining
        voyages observed. A test or operator that sets the variable still wins.
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
