"""Exact-value controls for performance repairs; no approximate comparisons."""

import sympy as sp

from turing_universal_quantum_computer.quantum_walk import HypercubeWalk
from turing_universal_quantum_computer.stabilizer import _row_str


def test_sparse_pauli_rendering_matches_every_four_wire_row():
    for x in range(16):
        for z in range(16):
            expected = "".join(
                (
                    "Y"
                    if x & (1 << q) and z & (1 << q)
                    else "X" if x & (1 << q) else "Z" if z & (1 << q) else "I"
                )
                for q in range(4)
            )
            assert _row_str(x, z, 4) == expected


def test_exact_binomial_recurrence_conserves_probability():
    walk = HypercubeWalk(12)
    for t in (0, sp.pi / 2, sp.pi / 3):
        distribution = walk.hamming_distribution(t)
        assert sum(distribution.values()) == 1
        for w, value in distribution.items():
            expected = sp.binomial(12, w) * sp.cos(t) ** (2 * (12 - w)) * sp.sin(t) ** (2 * w)
            assert sp.simplify(value - expected) == 0
