"""Smoke tests for the Lucas/Pisot scaling benchmark."""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent / "turing_universal_quantum_computer"),
)

from benchmarks.lucas_pisot_scaling import _order, pisot_damp


def test_pisot_damp_values():
    assert abs(pisot_damp(1) - (1 - 1 / 1.618033988749895)) < 1e-12
    assert pisot_damp(6) > pisot_damp(3)
    assert all(0 < pisot_damp(n) < 1 for n in (3, 4, 5, 6))


def test_order_is_permutation():
    n = 1024
    order = _order(n)
    assert sorted(order) == list(range(n))


def test_restriction_subset_size():
    n, damp_n = 4096, 4
    order = _order(n)
    subset = set(order[: math.ceil(n * pisot_damp(damp_n))])
    assert len(subset) == math.ceil(n * pisot_damp(damp_n))
    assert subset.issubset(set(order))
