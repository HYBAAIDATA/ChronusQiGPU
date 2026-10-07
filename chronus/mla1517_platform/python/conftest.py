"""Pytest fixtures for the platform suite."""

import os

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
