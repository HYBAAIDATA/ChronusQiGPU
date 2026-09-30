"""Distribution boundary tests for the first-class iGPU and L-HRAS packages."""

from __future__ import annotations

import importlib
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _project():
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_igpu_and_l_hras_are_explicit_distribution_packages():
    packages = set(_project()["tool"]["setuptools"]["packages"])
    assert {"igpu", "igpu.seam", "l_hras", "l_hras.foundations"} <= packages


def test_package_roots_and_typing_markers_exist():
    for package in ("igpu", "l_hras"):
        root = ROOT / package
        assert (root / "__init__.py").is_file()
        assert (root / "README.md").is_file()
        assert (root / "py.typed").is_file()


def test_igpu_import_is_lazy_and_hardware_independent():
    sys.modules.pop("igpu.detect", None)
    module = importlib.import_module("igpu")
    assert "detect_all" in module.__all__
    assert "igpu.detect" not in sys.modules, "root import must not trigger probing"


def test_runtime_resources_are_declared_as_package_data():
    data = _project()["tool"]["setuptools"]["package-data"]
    assert "kernels/*.cl" in data["igpu"]
    assert "deploy/*.yml" in data["igpu"]
    assert "config.example.toml" in data["l_hras"]
