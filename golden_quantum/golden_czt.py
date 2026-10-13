"""GOLDEN CHIRP Z-TRANSFORM (Bluestein's algorithm)
======================================================

golden_fourier.py computes GF(omega, n) by direct O(N) summation per
(omega, n) pair — O(N^2) total per plane, and it materializes phi^(-nk) via
repeated Decimal exponentiation for every (n, k) pair. This module computes
the exact same per-plane transform

    GF_n(k) = Sum_{m=0}^{N-1} f(m) * phi^(-n*m) * e^(-i*2*pi*m*k/N),   k=0..N-1

via Bluestein's Chirp Z-Transform identity in O(N log N), using the
substitution  m*k = (m^2 + k^2 - (k-m)^2) / 2:

    W^(mk) = W^(m^2/2) * W^(k^2/2) * W^(-(k-m)^2/2)

which turns the sum into a linear convolution computable with two FFTs.

Numerical stability fix that isn't just a complexity win: naively
materializing A = phi^n as a bare float before combining it with other
terms overflows for n around 1450+ (phi^1450 already exceeds float64 range
— the same failure mode found and fixed in hyba/allocation_validator.py
during the HYBA_Intelligence CI work). The decay factor phi^(-n*m) is
always <= 1 for n, m >= 0 (pure decay, never growth), so it should never
overflow — but only if it's computed as a single combined exponent rather
than as (phi^n)^(-m) after phi^n has already been formed. This module
computes it directly in log-space (exp(-n*m*log(phi))), which safely
underflows to 0.0 for extreme exponents instead of raising, and never
forms the intermediate phi^n at all. Verified against the exact n=1500
case that overflows the naive approach — see
tests/test_golden_fourier_extensions.py.
"""
from __future__ import annotations
import math
import numpy as np
from .constants import PHI_F


def _safe_decay(n: int, m_indices: np.ndarray) -> np.ndarray:
    """phi^(-n*m) for each m in m_indices, computed directly in log-space
    so it never forms phi^n as an intermediate value (which overflows for
    large n even though the final decayed result is always <= 1)."""
    log_phi = math.log(PHI_F)
    exponents = -float(n) * m_indices.astype(float) * log_phi
    # np.exp underflows to 0.0 for very negative exponents rather than
    # raising — that's the mathematically correct limit (phi^-inf = 0),
    # not an error condition.
    with np.errstate(under="ignore"):
        return np.exp(exponents)


def _bluestein_convolve_and_extract(a_n: np.ndarray, N: int, M: int, W: complex) -> np.ndarray:
    """Core Bluestein machinery: given a_n = x_n * decay_n * W^(n^2/2) for
    n=0..N-1, return Sum_n a_n * W^(-(k-n)^2/2) for k=0..M-1 via FFT
    convolution (the pre-post-multiply chirp factors are applied by the
    caller)."""
    lag = np.arange(-(N - 1), M)
    h = W ** (-(lag.astype(float) ** 2) / 2.0)

    L = 1
    while L < N + len(lag) - 1:
        L *= 2

    a_pad = np.zeros(L, dtype=complex)
    a_pad[:N] = a_n
    h_pad = np.zeros(L, dtype=complex)
    h_pad[: len(lag)] = h

    conv = np.fft.ifft(np.fft.fft(a_pad) * np.fft.fft(h_pad))
    offset = N - 1
    return conv[offset : offset + M]


def golden_czt_plane(f: np.ndarray, n: int, N: int | None = None) -> np.ndarray:
    """GF_n(k) for a single golden-plane n, k=0..N-1, via Bluestein's CZT.

    Matches golden_fourier_forward(f, [n], 2*pi*arange(N)/N) to within
    float precision (~1e-15), but in O(N log N) instead of O(N^2), and
    without ever forming phi^n as an intermediate value.
    """
    f = np.asarray(f, dtype=complex)
    Nf = len(f)
    if N is None:
        N = Nf

    m = np.arange(Nf)
    decay = _safe_decay(n, m)

    W = np.exp(-2j * np.pi / N)
    a_n = f * decay * (W ** ((m.astype(float) ** 2) / 2.0))

    result = _bluestein_convolve_and_extract(a_n, Nf, N, W)

    k = np.arange(N)
    post = W ** ((k.astype(float) ** 2) / 2.0)
    return post * result


def golden_czt_forward(f: np.ndarray, n_values: np.ndarray, N: int | None = None) -> np.ndarray:
    """Forward Golden-Fourier transform over multiple planes n_values, each
    evaluated at the N standard DFT frequencies omega_k = 2*pi*k/N — the
    CZT-stable counterpart to golden_fourier_forward for large/many n.

    Returns shape (N, len(n_values)) — GF[:, m] is plane n_values[m].
    """
    f = np.asarray(f, dtype=complex)
    if N is None:
        N = len(f)
    GF = np.zeros((N, len(n_values)), dtype=complex)
    for idx, n in enumerate(n_values):
        GF[:, idx] = golden_czt_plane(f, int(n), N=N)
    return GF
