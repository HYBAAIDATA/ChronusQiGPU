#!/usr/bin/env python3
"""Build standalone enterprise distribution wheel for unified EUCLID.

Stages euclid, Intelligence, hyba_substrate, toe, kellogg, and legacy compatibility shims
into a standalone enterprise distribution (euclid-engine), self-contained and offline-ready.
"""
from __future__ import annotations

from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO = Path(__file__).resolve().parent.parent
DIST = REPO / "dist"
DIST.mkdir(exist_ok=True)
WHEELHOUSE = REPO / "packaging" / "wheelhouse"


def stage_and_build() -> Path:
    with tempfile.TemporaryDirectory(prefix="euclid-standalone-") as tmp:
        tmp_path = Path(tmp)
        src_path = tmp_path / "src"
        src_path.mkdir(parents=True, exist_ok=True)

        ignore = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "var")

        # 1. Stage core enterprise and consolidated packages
        packages_to_stage = [
            "euclid",
            "Intelligence",
            "al_haras",
            "hyba_substrate",
            "resonance_intelligence",
            "toe",
            "kellogg",
            "aethel",
            "lucas",
            "hyba_toe_intelligence",
            "hyba_euclid_intelligence",
        ]
        for pkg in packages_to_stage:
            pkg_path = REPO / pkg
            if pkg_path.is_dir():
                shutil.copytree(pkg_path, src_path / pkg, ignore=ignore)

        # Stage turing_core and pythia_turing_math packages
        chronus_py = REPO / "chronus" / "mla1517_platform" / "python"
        if chronus_py.is_dir():
            turing_pkg = src_path / "turing_core"
            turing_pkg.mkdir(exist_ok=True)
            shutil.copy2(chronus_py / "turing_core.py", turing_pkg / "__init__.py")

            math_pkg = src_path / "pythia_turing_math"
            math_pkg.mkdir(exist_ok=True)
            shutil.copy2(chronus_py / "pythia_turing_math.py", math_pkg / "__init__.py")

        # 2. Create pyproject.toml
        pyproject_content = """[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "euclid-engine"
version = "1.0.0"
description = "EUCLID Enterprise Engine — unified autonomous adaptive intelligence substrate"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "numpy>=1.26,<3",
]

[tool.setuptools]
include-package-data = false

[tool.setuptools.packages.find]
where = ["src"]
include = [
    "euclid*",
    "Intelligence*",
    "al_haras*",
    "hyba_substrate*",
    "resonance_intelligence*",
    "toe*",
    "kellogg*",
    "aethel*",
    "lucas*",
    "turing_core*",
    "pythia_turing_math*",
    "hyba_toe_intelligence*",
    "hyba_euclid_intelligence*",
]
exclude = ["*.tests*", "tests*"]
"""
        (tmp_path / "pyproject.toml").write_text(pyproject_content, encoding="utf-8")

        readme_content = """# EUCLID Enterprise Engine

Unified autonomous adaptive intelligence substrate.
"""
        (tmp_path / "README.md").write_text(readme_content, encoding="utf-8")
        if (REPO / "LICENSE").exists():
            shutil.copy2(REPO / "LICENSE", tmp_path / "LICENSE")

        # 3. Build wheel via build module
        print(f"[*] Building enterprise wheel from {tmp_path}...")
        cmd = [
            sys.executable,
            "-m",
            "build",
            "--wheel",
            "--no-isolation",
            "--outdir",
            str(DIST),
            str(tmp_path),
        ]
        print("$", " ".join(cmd), flush=True)
        subprocess.run(cmd, check=True)

    # 4. Copy wheelhouse artifacts into dist if available
    if WHEELHOUSE.is_dir():
        for whl in WHEELHOUSE.glob("*.whl"):
            target = DIST / whl.name
            if not target.exists():
                shutil.copy2(whl, target)

    wheels = sorted(DIST.glob("euclid_engine-*.whl"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not wheels:
        raise RuntimeError("Failed to produce euclid_engine wheel in dist/")

    built_wheel = wheels[0]
    print(f"[+] Enterprise wheel built successfully: {built_wheel}")
    return built_wheel


if __name__ == "__main__":
    stage_and_build()
