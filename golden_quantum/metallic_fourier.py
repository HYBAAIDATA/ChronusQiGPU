"""METALLIC-FOURIER TRANSFORM
==============================

Generalizes the Golden-Fourier bridge (golden_fourier.py) from the golden
ratio to the full Metallic Means family. sigma_p is the positive root of

    x^2 - p*x - 1 = 0   =>   sigma_p = (p + sqrt(p^2 + 4)) / 2

  p=1 -> golden ratio  phi = (1+sqrt(5))/2      ~ 1.618
  p=2 -> silver ratio  1+sqrt(2)                ~ 2.414
  p=3 -> bronze ratio  (3+sqrt(13))/2            ~ 3.303

    MF_p(omega, n) = Sum_k f(k) sigma_p^(-nk) e^(-i*omega*k)

MF_1 is exactly the Golden-Fourier transform in golden_fourier.py — see
tests/test_golden_fourier_extensions.py for a direct numerical
cross-check between the two.

Physical grounding (why p matters, not just an abstract knob): MF_1
(golden) is the natural transform for detecting 5-fold/10-fold symmetry
in Penrose tilings and icosahedral quasicrystals; MF_2 (silver) is the
transform associated with Ammann-Beenker (octagonal, 8-fold) quasicrystal
structures. Different p targets different real quasicrystal symmetry
classes — it isn't a free parameter chosen for its own sake.
"""
from __future__ import annotations
import math
import numpy as np
from decimal import Decimal, getcontext


def metallic_mean(p: int) -> Decimal:
    """sigma_p = (p + sqrt(p^2 + 4)) / 2, the positive root of x^2 - p*x - 1 = 0."""
    if p < 1:
        raise ValueError("p must be a positive integer (p=1 is the golden ratio)")
    getcontext().prec = max(getcontext().prec, 50)
    pd = Decimal(p)
    return (pd + (pd * pd + Decimal(4)).sqrt()) / Decimal(2)


def _ensure_precision(prec: int = 50) -> None:
    getcontext().prec = max(prec, 50)


def metallic_fourier_forward(
    f: np.ndarray,
    n_values: np.ndarray,
    omega_values: np.ndarray,
    p: int = 1,
    prec: int = 50,
) -> np.ndarray:
    """Forward Metallic-Fourier transform MF_p(omega, n).

    Direct O(N * L * M) summation — same stability profile as
    golden_fourier_forward (decays for n*k > 0, since sigma_p > 1 for all
    p >= 1). For large N this inherits the same exponential-overflow risk
    the CZT-based transform (golden_czt.py) avoids; use that instead for
    signals where n*k gets large.
    """
    _ensure_precision(prec)
    sigma = metallic_mean(p)
    sigma_inv = Decimal(1) / sigma

    N = len(f)
    L = len(omega_values)
    M = len(n_values)
    MF = np.zeros((L, M), dtype=complex)

    for l in range(L):
        omega = float(omega_values[l])
        for m in range(M):
            n = int(n_values[m])
            total = complex(0, 0)
            for k in range(N):
                fk = float(f[k]) if k < len(f) else 0
                exp = n * k
                if exp == 0:
                    sigma_factor = 1.0
                else:
                    sigma_factor = float(sigma_inv ** exp)
                wk = omega * k
                ce = math.cos(wk)
                se = math.sin(wk)
                total += fk * sigma_factor * complex(ce, -se)
            MF[l, m] = total
    return MF


def metallic_reduction_to_fourier(
    f: np.ndarray,
    omega_values: np.ndarray,
) -> np.ndarray:
    """The p-independent reduction: every MF_p collapses to the same
    ordinary Fourier transform Sum_k f(k) e^(-i*omega*k) in the sigma_p ->
    1 limit, since that limit only depends on removing the sigma-decay
    term, not on which metallic mean it came from."""
    N = len(f)
    F = np.zeros(len(omega_values), dtype=complex)
    for l, omega in enumerate(omega_values):
        omega = float(omega)
        total = complex(0, 0)
        for k in range(N):
            wk = omega * k
            total += float(f[k]) * complex(math.cos(wk), -math.sin(wk))
        F[l] = total
    return F
