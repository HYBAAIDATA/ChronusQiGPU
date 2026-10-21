"""Test suite for the Golden-Fourier transform.
Run with: python -m pytest tests/ -v
"""

import sys
import os
import math
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from golden_quantum.constants import PHI_F
from golden_quantum.golden_fourier import (
    golden_fourier_forward,
    golden_fourier_inverse,
    golden_fourier_reduction,
    detect_phi_structure,
)


def test_forward_stability():
    np.random.seed(42)
    N = 50
    f = np.random.randn(N)

    phi = float(PHI_F)
    for k in range(N):
        f[k] *= phi ** (-k)

    n_values = np.arange(0, 10, dtype=float)
    omega_values = np.linspace(0, np.pi, 10, endpoint=False)
    GF = golden_fourier_forward(f, n_values, omega_values)

    has_nan = np.any(np.isnan(GF))
    has_inf = np.any(np.isinf(GF))
    total_energy = np.sum(np.abs(GF) ** 2)
    stable = not (has_nan or has_inf or math.isinf(total_energy) or total_energy > 1e10)

    assert stable, "Forward transform should be stable"


def test_inverse_with_regularization():
    np.random.seed(42)
    N = 30
    f_original = np.random.randn(N)

    n_values = np.arange(0, 5, dtype=float)
    omega_values = np.linspace(0, 2 * math.pi, 5, endpoint=False)
    GF = golden_fourier_forward(f_original, n_values, omega_values)

    # N must be passed explicitly: n_values only names which phi-rows GF was
    # sampled at (5 of them), not the original signal's length (30).
    damping = 1.0 / float(PHI_F)  # alpha = 1/PHI ~= 0.618
    f_reconstructed = golden_fourier_inverse(GF, n_values, omega_values, damping=damping, N=N)

    mse = np.mean((f_original - f_reconstructed) ** 2)
    rmse = np.sqrt(mse)
    rel_error = rmse / np.linalg.norm(f_original)

    assert rel_error < 0.5, f"Inverse transform reconstruction error too high: {rel_error}"


def test_phi_structure_detection():
    np.random.seed(0)
    test_data = np.sin(np.arange(100) * 0.1) + 0.1 * np.random.randn(100)
    detection = detect_phi_structure(test_data, n_max=10, omega_max=20)

    assert "is_phi_structured" in detection
    assert "phi_energy_ratio" in detection
    assert "fourier_energy_ratio" in detection
    # The two edges are disjoint by construction (see detect_phi_structure's
    # docstring on the double-counting fix) so they must sum to 1.
    assert math.isclose(
        detection["phi_energy_ratio"] + detection["fourier_energy_ratio"], 1.0, abs_tol=1e-9
    )


def test_reduction():
    # Build a real GF from an actual signal -- the fourier reduction can't
    # operate on an arbitrary complex array (phi isn't a slice-able axis of
    # GF; the phi->1 limit requires recomputing from the original signal).
    np.random.seed(7)
    f_sample = np.random.randn(20)
    n_sample = np.arange(0, 5, dtype=float)
    omega_sample = np.linspace(0, 2 * math.pi, 5, endpoint=False)
    GF_sample = golden_fourier_forward(f_sample, n_sample, omega_sample)

    # Fourier reduction (phi -> 1): recomputed as a plain DFT of f_sample,
    # so it should match a directly computed DFT at the same frequencies.
    GF_fourier = golden_fourier_reduction(GF_sample, to="fourier", f=f_sample, omega_values=omega_sample)
    assert GF_fourier.shape == (len(omega_sample),)
    expected_dft = np.array(
        [sum(f_sample[k] * np.exp(-1j * w * k) for k in range(len(f_sample))) for w in omega_sample]
    )
    assert np.allclose(GF_fourier, expected_dft, atol=1e-8), "Fourier reduction should match a plain DFT"

    # Golden reduction (omega -> 0)
    GF_golden = golden_fourier_reduction(GF_sample, to="golden")
    assert GF_golden.shape == (len(n_sample),)
    assert np.allclose(GF_golden, GF_sample[0, :])
