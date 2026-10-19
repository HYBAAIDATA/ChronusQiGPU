"""Tests for the Golden-Fourier bridge extensions: metallic_fourier.py,
golden_czt.py, and golden_wavelet.py. Each test captures a numeric claim
made in those modules' docstrings, so the claim stays checked rather than
asserted-and-forgotten.
"""

import sys
import os
import math
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from golden_quantum.golden_fourier import golden_fourier_forward
from golden_quantum.metallic_fourier import metallic_mean, metallic_fourier_forward
from golden_quantum.golden_czt import golden_czt_plane, golden_czt_forward
from golden_quantum.golden_wavelet import (
    golden_wavelet_decompose,
    golden_wavelet_reconstruct,
    verify_tight_frame,
    psi_hat_sq,
)


# --- metallic_fourier.py ----------------------------------------------------

def test_metallic_mean_closed_forms():
    assert math.isclose(float(metallic_mean(1)), (1 + 5**0.5) / 2, rel_tol=1e-12)  # golden
    assert math.isclose(float(metallic_mean(2)), 1 + 2**0.5, rel_tol=1e-12)  # silver
    assert math.isclose(float(metallic_mean(3)), (3 + 13**0.5) / 2, rel_tol=1e-12)  # bronze


def test_mf1_matches_golden_fourier_forward_exactly():
    np.random.seed(0)
    f = np.random.randn(20)
    n_values = np.arange(0, 5, dtype=float)
    omega_values = np.linspace(0, 2 * np.pi, 6, endpoint=False)

    GF = golden_fourier_forward(f, n_values, omega_values)
    MF1 = metallic_fourier_forward(f, n_values, omega_values, p=1)

    assert np.max(np.abs(GF - MF1)) == 0.0


# --- golden_czt.py -----------------------------------------------------------

def test_czt_matches_golden_fourier_forward():
    np.random.seed(3)
    f = np.random.randn(40)
    N = len(f)
    n_values = [0, 1, 4, 10]
    omega_k = 2 * np.pi * np.arange(N) / N

    GF_direct = golden_fourier_forward(f, np.array(n_values, dtype=float), omega_k)
    GF_czt = golden_czt_forward(f, np.array(n_values), N=N)

    assert np.max(np.abs(GF_direct - GF_czt)) < 1e-11


def test_czt_survives_the_overflow_case_that_breaks_naive_exponentiation():
    # phi**n as a bare float overflows around n~1475 (confirmed: phi**1450
    # survives, phi**1475 raises OverflowError). golden_czt.py exists to
    # avoid ever forming that intermediate value.
    np.random.seed(5)
    f = np.random.randn(40)
    out = golden_czt_plane(f, n=1500, N=len(f))

    assert not np.any(np.isnan(out))
    assert not np.any(np.isinf(out))


# --- golden_wavelet.py --------------------------------------------------------

def test_wavelet_tight_frame_tiling_identity():
    bounds = verify_tight_frame()
    assert math.isclose(bounds["A"], 1.0, abs_tol=1e-12)
    assert math.isclose(bounds["B"], 1.0, abs_tol=1e-12)
    assert bounds["max_deviation_from_1"] < 1e-13


def test_wavelet_lossless_reconstruction():
    np.random.seed(11)
    N = 256
    f = np.random.randn(N) + 0.5 * np.sin(np.arange(N) * 0.3)

    decomp = golden_wavelet_decompose(f, range(-8, 9))
    recon = golden_wavelet_reconstruct(decomp, N)

    assert np.max(np.abs(f - recon.real)) < 1e-12
    assert np.max(np.abs(recon.imag)) < 1e-12


def test_wavelet_parseval_energy_conservation():
    np.random.seed(11)
    N = 256
    f = np.random.randn(N) + 0.5 * np.sin(np.arange(N) * 0.3)

    decomp = golden_wavelet_decompose(f, range(-8, 9))

    energy_f = np.sum(np.abs(f) ** 2)
    energy_out = sum(np.sum(np.abs(d) ** 2) for d in decomp["subbands"].values())
    energy_out += np.sum(np.abs(decomp["residual"]) ** 2)

    assert math.isclose(energy_f, energy_out, rel_tol=1e-12)


def test_wavelet_survives_n_that_overflows_bare_phi_power():
    # phi**1500 raises OverflowError as a bare float; psi_hat_sq(omega,
    # shift=n) computes log_phi(omega)+n instead of forming phi**n, so
    # this must not crash even with n far past that threshold.
    np.random.seed(1)
    f = np.random.randn(64)
    decomp = golden_wavelet_decompose(f, range(-1500, 1501, 500))
    recon = golden_wavelet_reconstruct(decomp, 64)

    assert np.max(np.abs(f - recon.real)) < 1e-12


def test_wavelet_dc_is_carried_entirely_by_the_residual_channel():
    # No wavelet band centered on [1, phi^2] can reach omega=0
    # (log_phi(0) = -inf); the residual channel exists specifically to
    # carry whatever a finite n_range can't cover.
    assert psi_hat_sq(np.array([0.0]))[0] == 0.0

    np.random.seed(11)
    N = 256
    f = np.ones(N) * 5.0  # pure DC signal
    decomp = golden_wavelet_decompose(f, range(-8, 9))

    assert decomp["coverage"][0] == 0.0
    assert math.isclose(decomp["residual_filter"][0] ** 2, 1.0, abs_tol=1e-12)
