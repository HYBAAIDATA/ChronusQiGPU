"""Distribution boundary tests for the first-class iGPU and L-HRAS packages."""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _project():
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_chronus_and_l_hras_are_explicit_distribution_packages():
    packages = set(_project()["tool"]["setuptools"]["packages"])
    assert {
        "gpu",
        "gpu.backends",
        "hyba",
        "hyba.hybrid",
        "hyba.math_ir",
        "hyba.operating_model",
        "chronus",
        "chronus.seam",
        "l_hras",
        "l_hras.foundations",
    } <= packages


def test_package_roots_and_typing_markers_exist():
    for package in ("gpu", "chronus", "l_hras"):
        root = ROOT / package
        assert (root / "__init__.py").is_file()
        assert (root / "README.md").is_file()
        assert (root / "py.typed").is_file()


def test_chronus_import_is_lazy_and_hardware_independent():
    code = (
        "import sys, chronus; "
        "assert 'detect_all' in chronus.__all__; "
        "assert 'chronus.detect' not in sys.modules"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_runtime_resources_are_declared_as_package_data():
    data = _project()["tool"]["setuptools"]["package-data"]
    assert "BLUEPRINT_AUDIT.md" in data["gpu"]
    assert "kernels/*.cl" in data["chronus"]
    assert "deploy/*.yml" in data["chronus"]
    assert "config.example.toml" in data["l_hras"]
