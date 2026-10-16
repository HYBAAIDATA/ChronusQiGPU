"""GOLDEN WAVELET FRAME
========================

Solves the ill-posedness of the naive Golden-Fourier inverse (golden_fourier.py's
golden_fourier_inverse needs a "damping" hack because phi^(nk) is unbounded)
by replacing scalar damping with a genuine wavelet frame: n is reframed as a
dilation scale (phi^n), analogous to dyadic scales (2^-j) in a standard
Continuous Wavelet Transform, instead of an exponent that needs cancelling.

What's proven vs. what's verified numerically
-----------------------------------------------
The mother wavelet psi_hat (frequency domain) is constructed, not guessed:
it's a band-limited bump on [1, phi^2] built from a smoothstep nu(x) with
nu(0)=0, nu(1)=1, split at phi into a rising sin(pi/2 . nu(x)) half and a
falling cos(pi/2 . nu(x)) half. This is the standard Littlewood-Paley /
Meyer-wavelet construction with the dilation base generalized from 2 to
phi — nothing about the proof depends on the base being 2. Because
sin(pi/2 . t)^2 + cos(pi/2 . t)^2 == 1 identically, adjacent dilates of
this bump telescope exactly:

    Sum_{n=-inf}^{inf} |psi_hat(phi^n * omega)|^2 == 1   for all omega > 0

i.e. A = B = 1 exactly — a tight frame — PROVABLE from the construction,
not just observed. What IS a numerical claim (verified in
tests/test_golden_fourier_extensions.py, not proven here) is that summing
over a *finite* truncated n range plus an explicit low-pass residual
channel (residual_weight = 1 - coverage, capturing whatever a finite
n-range misses — chiefly DC, which no band centered on [1, phi^2] can
reach since log_phi(0) = -inf) reconstructs a *finite, discretely sampled*
signal losslessly. That's verified to reconstruct to ~1e-15 (float
precision) on test signals, which is the real, checkable claim — not an
assertion that this holds for every f in L^2(R) for every truncation.

Discrete realization
---------------------
The document this is built from describes psi_{n,k}(t) = phi^(-n/2)
psi(phi^-n t - k*b0) — an explicit continuous-time, explicitly-translated
wavelet family. What's implemented here is the standard discrete
equivalent: rather than sampling explicit time-domain translates, each
scale n is realized as an FFT filter bank channel (analysis: multiply the
spectrum by psi_hat_n = sqrt(weight_n); synthesis: re-multiply by the same
filter and sum). This is how Meyer-style wavelet frames are actually
computed in practice, and it sidesteps needing to choose a translation
step b0 or verify Nyquist/oversampling conditions on it — the tiling
identity above is exactly what guarantees perfect reconstruction for this
realization, with no separate translation-density argument needed.

psi_hat itself is bounded in [0, 1] by construction, and evaluating
psi_hat(phi^n * omega) is done via psi_hat_sq(omega, shift=n), which
shifts log_phi(omega) by the integer n directly — phi^n is never formed
as a multiplicative factor at all, avoiding the same overflow class fixed
in golden_czt.py (phi**n as a bare float overflows past n~1475, which is
well inside plausible n_range choices for a wide frequency sweep).
"""
from __future__ import annotations
import numpy as np
from .constants import PHI_F

LOG_PHI = float(np.log(PHI_F))


def _smoothstep(x: np.ndarray) -> np.ndarray:
    """Standard C^2 smoothstep on [0,1]: nu(0)=0, nu(1)=1, nu'(0)=nu'(1)=0."""
    x = np.clip(x, 0.0, 1.0)
    return 6 * x**5 - 15 * x**4 + 10 * x**3


def psi_hat_sq(omega: np.ndarray, shift: int = 0) -> np.ndarray:
    """|psi_hat(phi^shift * omega)|^2 — band-limited on [1, phi^2], split
    at phi. shift=0 evaluates psi_hat(omega) itself; shift=n evaluates the
    n-th phi-dilate, computed as log_phi(omega) + n rather than by forming
    phi**n and multiplying (which overflows for |n| large — see module
    docstring).

    Built so that sin(pi/2.nu)^2 + cos(pi/2.nu)^2 == 1 makes adjacent
    phi-dilates of this function tile the frequency axis exactly. Verified:
    max deviation of Sum_n psi_hat_sq(omega, shift=n) from 1.0, over a
    dense omega grid in [1, phi) and n in [-30, 30], is ~1.5e-15 (float
    precision) — tests/test_golden_fourier_extensions.py.
    """
    omega = np.abs(np.asarray(omega, dtype=float))
    out = np.zeros_like(omega)
    with np.errstate(divide="ignore"):
        log_w = np.log(np.maximum(omega, 1e-300)) / LOG_PHI + shift

    rising = (log_w >= 0) & (log_w <= 1)
    out[rising] = np.sin(np.pi / 2 * _smoothstep(log_w[rising])) ** 2

    falling = (log_w > 1) & (log_w <= 2)
    out[falling] = np.cos(np.pi / 2 * _smoothstep(log_w[falling] - 1)) ** 2

    return out


def golden_wavelet_decompose(f: np.ndarray, n_range: range) -> dict:
    """Analysis: decompose f into golden-dilated wavelet subbands plus an
    explicit low-pass residual covering whatever the finite n_range misses.

    Returns
    -------
    dict with keys:
        subbands: {n: d_n} — time-domain detail signal per scale n
        filters: {n: psi_hat_n} — the frequency-domain filter used per scale
                 (needed by golden_wavelet_reconstruct)
        residual: time-domain low-pass residual (chiefly captures DC)
        residual_filter: the frequency-domain residual filter
        coverage: Sum_n |psi_hat(phi^n * omega)|^2 actually achieved over
                  n_range, at each DFT bin — how close to the ideal
                  tight-frame value of 1.0 this truncation gets
    """
    f = np.asarray(f)
    N = len(f)
    F = np.fft.fft(f)
    freqs = 2 * np.pi * np.fft.fftfreq(N, d=1.0)

    filters, subbands = {}, {}
    coverage = np.zeros(N)
    for n in n_range:
        weight = psi_hat_sq(np.abs(freqs), shift=n)
        coverage += weight
        psi_n = np.sqrt(weight)
        filters[n] = psi_n
        subbands[n] = np.fft.ifft(F * psi_n)

    residual_weight = np.clip(1.0 - coverage, 0.0, None)
    residual_filter = np.sqrt(residual_weight)
    residual = np.fft.ifft(F * residual_filter)

    return {
        "subbands": subbands,
        "filters": filters,
        "residual": residual,
        "residual_filter": residual_filter,
        "coverage": coverage,
    }


def golden_wavelet_reconstruct(decomposition: dict, N: int) -> np.ndarray:
    """Synthesis (dual-frame reconstruction): re-apply each scale's filter
    to its subband and sum — the tight-frame identity (A=B=1, up to the
    coverage achieved by the truncated n_range) makes this exact rather
    than requiring a separate dual-frame operator S^-1 to be computed."""
    freq_sum = np.zeros(N, dtype=complex)
    for n, d_n in decomposition["subbands"].items():
        freq_sum += np.fft.fft(d_n) * decomposition["filters"][n]
    freq_sum += np.fft.fft(decomposition["residual"]) * decomposition["residual_filter"]
    return np.fft.ifft(freq_sum)


def verify_tight_frame(n_range: range = range(-30, 31), n_omega_samples: int = 2000) -> dict:
    """Numerically check the frequency-tiling identity Sum_n |psi_hat(phi^n
    omega)|^2 == 1 over the fundamental domain omega in [1, phi), for the
    given (possibly truncated) n_range. Returns the observed A (min sum)
    and B (max sum) — for n_range wide enough, both should be ~1.0."""
    test_omegas = np.linspace(1.0001, PHI_F - 0.0001, n_omega_samples)
    sums = np.array(
        [sum(psi_hat_sq(np.array([w]), shift=n)[0] for n in n_range) for w in test_omegas]
    )
    return {"A": float(sums.min()), "B": float(sums.max()), "max_deviation_from_1": float(np.max(np.abs(sums - 1.0)))}
