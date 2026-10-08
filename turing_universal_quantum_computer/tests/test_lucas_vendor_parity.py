"""Drift guard for the vendored ``turing_universal_quantum_computer.lucas`` package.

Every module shared between the vendored copy and the canonical top-level
``lucas/`` package must stay byte-identical. A silent fork of the
exact-algebra substrate would let TURING and the rest of the repo disagree
about Fibonacci/Lucas arithmetic without any gate noticing.
"""

from __future__ import annotations

import importlib
from pathlib import Path

DIST_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]
VENDORED = DIST_ROOT / "turing_universal_quantum_computer" / "lucas"
CANONICAL = REPO_ROOT / "lucas"

SHARED_MODULES = [
    "__init__.py",
    "algebra.py",
    "bound.py",
    "core.py",
    "ladder.py",
    "pool.py",
    "trace.py",
]

# Vendored-only module kept for grover_exact_scale; it is byte-identical to
# the historical copy in legacy/lucas/cassini.py.
VENDORED_ONLY = ["cassini.py"]


def test_vendored_lucas_file_manifest() -> None:
    vendored = sorted(
        p.name for p in VENDORED.iterdir() if p.is_file() and not p.name.endswith(".pyc")
    )
    assert vendored == sorted(SHARED_MODULES + VENDORED_ONLY), (
        "vendored lucas package gained or lost files; update the parity "
        "contract or move the change through both trees deliberately"
    )


def test_vendored_lucas_modules_byte_identical() -> None:
    for name in SHARED_MODULES:
        vendored = (VENDORED / name).read_bytes()
        canonical = (CANONICAL / name).read_bytes()
        assert vendored == canonical, (
            f"vendored turing_universal_quantum_computer/lucas/{name} has "
            f"drifted from canonical lucas/{name}"
        )


def test_vendored_cassini_tracks_legacy_source() -> None:
    legacy = REPO_ROOT / "legacy" / "lucas" / "cassini.py"
    if legacy.exists():
        assert (VENDORED / "cassini.py").read_bytes() == legacy.read_bytes(), (
            "vendored lucas/cassini.py no longer matches its historical "
            "source legacy/lucas/cassini.py"
        )


def test_vendored_lucas_modules_import() -> None:
    for mod in ("algebra", "bound", "core", "ladder", "pool", "trace", "cassini"):
        importlib.import_module(f"turing_universal_quantum_computer.lucas.{mod}")
