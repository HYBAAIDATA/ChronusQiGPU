"""Tests for visualization module."""
import math

import numpy as np

from quantum_compute_substrate.visualization import (
    StateVisualizer,
    ascii_amplitude_bar,
)


class TestVisualization:
    def test_ascii_bar_produces_lines(self):
        state = np.array([0.6, 0.8, 0.0, 0.0], dtype=np.complex128)
        state /= np.linalg.norm(state)
        out = ascii_amplitude_bar(state, width=10)
        assert "|000>" in out and "|003>" in out

    def test_bloch_vector_computed(self):
        v = StateVisualizer()
        state = np.array([1.0, 0.0], dtype=np.complex128)
        b = v.bloch_vector(state)
        assert math.isclose(b.z, 1.0, abs_tol=1e-9)

    def test_entropy_pure_zero_mixed_ln2(self):
        v = StateVisualizer()
        rho_pure = np.array([[1, 0], [0, 0]], dtype=complex)
        rho_mixed = np.eye(2, dtype=complex) / 2
        assert abs(v.entanglement_entropy(rho_pure)) < 1e-9
        assert abs(v.entanglement_entropy(rho_mixed) - math.log(2.0)) < 1e-9

    def test_probability_distribution_sums_to_one(self):
        v = StateVisualizer()
        state = np.array([1, 1, 1, 1], dtype=np.complex128) / 2
        p = v.probability_distribution(state)
        assert abs(float(p.sum()) - 1.0) < 1e-12
