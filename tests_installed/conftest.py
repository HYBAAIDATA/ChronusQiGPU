"""Fixtures for tests that run the *installed wheel* in a clean virtual environment.

These tests are deliberately outside ``tests/`` (the source-tree suite). They
prove production execution paths: console scripts and a real server process
from a wheel installed into a venv with no access to the repository sources.

CI sets CHRONUS_INSTALLED_VENV to a venv where the wheel built by the
"Lint, compile and package" job was installed. Locally, when the variable is
unset, the fixture builds the wheel and creates that venv itself (needs network
access for dependencies).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _bin(venv: Path, name: str) -> Path:
    return venv / ("Scripts" if os.name == "nt" else "bin") / (name + (".exe" if os.name == "nt" else ""))


def clean_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "CHRONUS_", "VIRTUAL_ENV"))}
    env["PYTHONNOUSERSITE"] = "1"
    return env


@pytest.fixture(scope="session")
def installed_venv(tmp_path_factory) -> Path:
    configured = os.environ.get("CHRONUS_INSTALLED_VENV")
    if configured:
        venv = Path(configured).resolve()
        if not _bin(venv, "python").exists():
            raise RuntimeError(f"CHRONUS_INSTALLED_VENV={configured} has no python")
        return venv
    work = tmp_path_factory.mktemp("installed")
    dist = work / "dist"
    subprocess.run([sys.executable, "-m", "pip", "wheel", "--no-deps", "-w", str(dist), str(ROOT)],
                   check=True, capture_output=True)
    wheel = next(dist.glob("hyba_chronus-*.whl"))
    venv = work / "venv"
    subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
    subprocess.run([str(_bin(venv, "python")), "-m", "pip", "install", "-q", str(wheel)],
                   check=True, env=clean_env())
    return venv


@pytest.fixture(scope="session")
def venv_bin(installed_venv):
    return lambda name: _bin(installed_venv, name)
