"""Separate-build contract for PYTHIA and the Turing VQC."""

from __future__ import annotations

import ast
from pathlib import Path

from python_backend.pythia_mining.golden_constants import GOLDEN_CONSTANTS
from toe.foundation import UNIFIED_THEORY as PYTHIA_FOUNDATION
from turing_universal_quantum_computer.unified_theory import (
    UNIFIED_THEORY as TURING_FOUNDATION,
)


ROOT = Path(__file__).resolve().parents[1]
TURING_PACKAGE = (
    ROOT
    / "turing_universal_quantum_computer"
    / "turing_universal_quantum_computer"
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_both_distributions_carry_the_same_verified_foundation_contract():
    assert PYTHIA_FOUNDATION.verify()
    assert TURING_FOUNDATION.verify()
    assert PYTHIA_FOUNDATION.payload() == TURING_FOUNDATION.payload()
    assert PYTHIA_FOUNDATION.digest == TURING_FOUNDATION.digest


def test_foundation_modules_are_dependency_free_across_builds():
    pythia_imports = _imports(ROOT / "toe" / "foundation.py")
    turing_imports = _imports(TURING_PACKAGE / "unified_theory.py")

    assert not any(name.startswith("turing_universal_quantum_computer") for name in pythia_imports)
    assert not any(name.startswith(("toe", "Intelligence", "chronus")) for name in turing_imports)


def test_operational_golden_constants_exist_outside_legacy_tree():
    assert GOLDEN_CONSTANTS.version == "uci-1.0"
    assert GOLDEN_CONSTANTS.LUCAS_15 == 1364
    assert 1.618 < GOLDEN_CONSTANTS.PHI < 1.619
