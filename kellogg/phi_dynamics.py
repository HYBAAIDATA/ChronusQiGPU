"""Kellogg golden dynamics — evolution operators on the Z[phi] lattice.

The DphiT grading vector (:func:`kellogg.dphi_transform.get_golden_grading_vector`)
assigns every coefficient a recursive depth.  In the scale domain the role
of the Fourier eigenvalue ``k^2`` is played by ``phi**grade``: the golden
Laplacian multiplies coefficients by that spectrum, and the propagator
``exp(-1j * phi**grade * t)`` evolves them unitarily.

``golden_propagate`` applies unit-modulus phase factors in coefficient
space.  The DphiT basis is a bijection, not an isometry, so signal energy
is **not** conserved by propagation — the transcript's "strictly unitary"
reading fails here, and :func:`propagation_energy_drift` measures the
actual drift rather than asserting zero.

The fidelity benchmark compares how a Fibonacci-word signal survives
evolution under the golden Laplacian versus the standard FFT Laplacian.
The measured quantity is the count of coefficients carrying 99.9% of the
energy in the DphiT basis after each evolution; the ratio is the fidelity
delta.  It is an empirical signal property, not a theorem.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Tuple

import numpy as np

from .dphi_transform import (
    PHI,
    dphi_transform,
    fibonacci_word_signal,
    get_golden_grading_vector,
    idphi_transform,
)


class GoldenDynamicsError(ValueError):
    """A golden-dynamics shape or depth contract was violated."""


def _check_complexable(flat: np.ndarray) -> np.ndarray:
    if flat.size == 0:
        raise GoldenDynamicsError("golden dynamics requires a non-empty signal")
    return flat.astype(np.complex128) if not np.iscomplexobj(flat) else flat


def apply_golden_laplacian(signal: np.ndarray, depth: int = 1) -> np.ndarray:
    """``L_phi`` acting on ``signal``: ``idphi(dphi(f) * phi**grades)``.

    Diagonal in the DphiT basis by construction — this is the scale analogue
    of the Fourier Laplacian's ``k^2`` multiplier.
    """
    flat = np.asarray(signal).ravel()
    coeffs = dphi_transform(flat, depth)
    grades = get_golden_grading_vector(int(flat.size), depth)
    eigenvalues = PHI ** grades
    return idphi_transform(coeffs * eigenvalues, depth)


def golden_propagate(
    signal: np.ndarray, dt: float, steps: int, depth: int = 1
) -> np.ndarray:
    """Evolve ``signal`` under the golden Laplacian: ``U(t) = e^{-i L t} U_0``.

    Returns complex coefficients — phase evolution is genuinely unitary only
    on the algebraic path, so the result is complex128 even for real input.
    """
    flat = _check_complexable(np.asarray(signal).ravel())
    coeffs = dphi_transform(flat, depth)
    grades = get_golden_grading_vector(int(flat.size), depth)
    eigenvalues = PHI ** grades
    phase = np.exp(-1j * eigenvalues * dt * int(steps))
    return idphi_transform(coeffs * phase, depth)


def propagation_energy_drift(
    signal: np.ndarray, dt: float, steps: int, depth: int = 1
) -> float:
    """Measured relative energy change of :func:`golden_propagate`.

    ``(||U(t)||^2 - ||U(0)||^2) / ||U(0)||^2`` — nonzero in general because
    the DphiT basis is not orthonormal; this is a measured drift, not a
    conserved-quantity check.
    """
    flat = _check_complexable(np.asarray(signal).ravel())
    evolved = golden_propagate(flat, dt, steps, depth)
    before = float(np.sum(np.abs(flat) ** 2))
    after = float(np.sum(np.abs(evolved) ** 2))
    if before == 0.0:
        return 0.0
    return (after - before) / before


def measure_structural_fidelity(signal: np.ndarray, depth: int = 1) -> int:
    """Count of DphiT coefficients carrying 99.9% of the signal's energy.

    Smaller is sparser — the signal's structure concentrates in fewer scale
    coefficients.  This is the "Sparsity" metric of Wall 8.
    """
    flat = np.asarray(signal).ravel()
    if flat.size == 0:
        raise GoldenDynamicsError("fidelity measure requires a non-empty signal")
    coeffs = dphi_transform(flat, depth)
    energy = np.abs(coeffs) ** 2
    total = float(energy.sum())
    if total == 0.0:
        return 0
    ordered = np.sort(energy)[::-1]
    cumulative = np.cumsum(ordered) / total
    return int(np.searchsorted(cumulative, 0.999) + 1)


def standard_fft_wave_propagation(
    signal: np.ndarray, dt: float, steps: int
) -> np.ndarray:
    """Standard Fourier-domain comparator: ``e^{-i k^2 t}`` on the FFT basis."""
    flat = _check_complexable(np.asarray(signal).ravel())
    n = int(flat.size)
    coeffs = np.fft.fft(flat)
    k = np.fft.fftfreq(n) * 2.0 * np.pi
    phase = np.exp(-1j * (k ** 2) * dt * int(steps))
    return np.fft.ifft(coeffs * phase)


@dataclass(frozen=True)
class FidelityDeltaResult:
    """Measured outcome of the golden-vs-Fourier fidelity duel."""

    signal_length: int
    depth: int
    dt: float
    steps: int
    phi_coefficients: int
    std_coefficients: int
    fidelity_delta: float
    phi_energy_drift: float
    std_energy_drift: float


def run_fidelity_duel(
    signal_length: int = 987,
    depth: int = 6,
    dt: float = 0.1,
    steps: int = 50,
) -> FidelityDeltaResult:
    """Evolve a Fibonacci word under both Laplacians and compare sparsity.

    ``fidelity_delta`` is ``std_coefficients / phi_coefficients``: values
    above 1 mean the golden propagation kept the aperiodic signal sparser in
    the DphiT basis than the FFT propagation did.  A measured quantity.
    """
    initial = fibonacci_word_signal(signal_length)
    phi_evolved = golden_propagate(initial, dt=dt, steps=steps, depth=depth)
    std_evolved = standard_fft_wave_propagation(initial, dt=dt, steps=steps)

    phi_k = measure_structural_fidelity(phi_evolved, depth)
    std_k = measure_structural_fidelity(std_evolved, depth)

    initial_energy = float(np.sum(np.abs(initial) ** 2))
    std_drift = (
        (float(np.sum(np.abs(std_evolved) ** 2)) - initial_energy) / initial_energy
        if initial_energy
        else 0.0
    )

    return FidelityDeltaResult(
        signal_length=signal_length,
        depth=depth,
        dt=dt,
        steps=steps,
        phi_coefficients=phi_k,
        std_coefficients=std_k,
        fidelity_delta=float(std_k) / float(phi_k) if phi_k else math.inf,
        phi_energy_drift=propagation_energy_drift(initial, dt, steps, depth),
        std_energy_drift=std_drift,
    )


def reversible_time_step(
    state: np.ndarray, momentum: np.ndarray, dt: float, depth: int = 1
) -> Tuple[np.ndarray, np.ndarray]:
    """One bit-exact symplectic step on integer state/momentum pairs.

    ``p' = p + floor(L_phi(state) * dt + 0.5)`` then
    ``x' = x + floor(p' * dt + 0.5)`` — a kick-drift step whose rounding is a
    deterministic bijection on integer pairs, so the trajectory is
    recoverable.
    """
    s = np.asarray(state)
    p = np.asarray(momentum)
    if s.shape != p.shape:
        raise GoldenDynamicsError(
            f"state/momentum shapes must match: {s.shape} vs {p.shape}"
        )
    if not (_is_int(s) and _is_int(p)):
        raise GoldenDynamicsError(
            "reversible_time_step is defined on integer state/momentum"
        )
    force = apply_golden_laplacian(s, depth)
    new_momentum = p + np.floor(force * dt + 0.5).astype(np.int64)
    new_state = s + np.floor(new_momentum * dt + 0.5).astype(np.int64)
    return new_state, new_momentum


def _is_int(array: np.ndarray) -> bool:
    return np.issubdtype(array.dtype, np.integer)


__all__ = [
    "FidelityDeltaResult",
    "GoldenDynamicsError",
    "apply_golden_laplacian",
    "golden_propagate",
    "measure_structural_fidelity",
    "propagation_energy_drift",
    "reversible_time_step",
    "run_fidelity_duel",
    "standard_fft_wave_propagation",
]
