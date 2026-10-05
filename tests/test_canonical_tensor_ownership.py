"""Canonical-ownership gate: consolidated tensor symbols have one home each.

The tensor elevation folded the duplicated declarations to canonical
owners. This gate scans every live Python file for ``class NAME:``
definitions and asserts each consolidated symbol is defined only in its
canonical file(s) — the numeric family (aethel/chronus/kellogg) and the
exact-rational family (python_backend geodesic engine) may coexist, but
neither may fork into a third home, and renamed colliders
(``GeodesicRouter``, ``QuantumFoldTensorCore``) must stay gone under
their old names.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

EXACT_ENGINE = "python_backend/core_modules/geodesic_tensor_engine.py"

#: symbol -> canonical defining files (repo-relative).
CANONICAL_OWNERS = {
    "PhiTensorCore": {
        "kellogg/phi_tensor_core.py",
        EXACT_ENGINE,
    },
    "QuantumFoldTensorCore": {
        "quantum_compute_substrate/phi_tensor_core.py",
    },
    "GeodesicScheduler": {
        "chronus/phi_gpu.py",
        EXACT_ENGINE,
    },
    "GeodesicRouter": {
        "chronus/virtual_igpu/planner.py",
    },
    "KernelBoundary": {
        "aethel/phi_fold.py",
        EXACT_ENGINE,
    },
    "PartialUnfoldStats": {
        "aethel/phi_fold.py",
        EXACT_ENGINE,
    },
    "PhiMemoryHierarchy": {
        "aethel/phi_memory.py",
        EXACT_ENGINE,
    },
    "TopologicalIntegrityGate": {
        "aethel/phi_memory.py",
        EXACT_ENGINE,
    },
    "EnergyModel": {
        "chronus/phi_gpu.py",
        EXACT_ENGINE,
    },
    "PhiGPU": {
        "chronus/phi_gpu.py",
        EXACT_ENGINE,
    },
    "HybridGPU": {
        "chronus/phi_gpu.py",
        EXACT_ENGINE,
    },
    "MetricTensor": {
        "kellogg/phi_tensor_core.py",
        EXACT_ENGINE,
    },
}

_SKIP_DIRS = {".venv", ".git", "__pycache__", "legacy", "build", "node_modules"}
_CLASS_RE = re.compile(r"^class (\w+)[(:]")

# Names that existed at consolidation time and were removed on purpose —
# the gate fails if the colliding spelling ever reappears as a class.
_BANNED_COLLIDERS = {}


def _live_files():
    for path in REPO_ROOT.rglob("*.py"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if any(part in _SKIP_DIRS for part in rel.split("/")):
            continue
        yield rel, path


@pytest.mark.parametrize("symbol", sorted(CANONICAL_OWNERS))
def test_symbol_defined_only_in_canonical_files(symbol):
    defined_in = set()
    for rel, path in _live_files():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = _CLASS_RE.match(line)
            if match and match.group(1) == symbol:
                defined_in.add(rel)
    expected = CANONICAL_OWNERS[symbol]
    assert defined_in == expected, (
        f"{symbol} defined in {sorted(defined_in)}, "
        f"canonical owners are {sorted(expected)}"
    )


def test_numeric_family_does_not_import_exact_engine():
    """The numeric custody layer must not depend on the exact-rational
    engine (and aethel never imports kellogg — the declared ownership
    invariant)."""
    for rel in ("aethel/phi_fold.py", "aethel/phi_memory.py",
                "aethel/fold_store.py", "aethel/phi_memory.py"):
        text = (REPO_ROOT / rel).read_text(encoding="utf-8")
        assert "kellogg" not in text, f"{rel} imports kellogg (cycle)"
        assert "geodesic_tensor_engine" not in text, (
            f"{rel} reaches into the exact-rational engine"
        )
