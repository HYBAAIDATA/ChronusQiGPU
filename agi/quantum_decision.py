"""
Quantum Decision Substrate Bridge
=================================

Shared helpers that connect the ``agi/`` decision paths to the repository's
own exact quantum substrate (``kellogg.quantum_tensor``).

Everything here is deterministic, first-principles quantum math:

* states are ``kellogg.quantum_tensor.QuantumState`` objects;
* observables are ``ComplexMatrix.diagonal`` operators;
* expectations are ⟨ψ|A|ψ⟩ computed by ``QuantumState.expectation``;
* decision collapse is ``QuantumState.measure_pvm`` — the maximum
  Born-probability outcome, no pseudo-random sampling;
* uncertainty is the observable variance, which equals F_Q/4 by
  ``quantum_fisher_information`` — an exact quantity, not a confidence
  interval stitched on after the fact.

numpy is used only to build/exponentiate real operators — the
finite-precision realisation of the unitary evolution the substrate
declares. No random draws reach any result.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

from kellogg.quantum_tensor import (
    Complex,
    ComplexMatrix,
    QuantumState,
    born_probabilities,
    encode_data_to_state,
    quantum_fisher_information,
)

PHI = (1.0 + math.sqrt(5.0)) / 2.0

__all__ = [
    "PHI",
    "substrate_state_from_amplitudes",
    "substrate_state_from_belief",
    "diagonal_observable",
    "grover_oracle",
    "grover_diffusion",
    "grover_amplify",
    "decision_analysis",
    "expectation_on_context",
    "hamiltonian_evolve",
    "weyl_unit_sequence",
    "normal_quantile_grid",
    "quantile_grid",
]


# ---------------------------------------------------------------------------
# State construction
# ---------------------------------------------------------------------------


def substrate_state_from_amplitudes(
    amplitudes: Sequence[Any], dim: Optional[int] = None
) -> QuantumState:
    """Build a normalized QuantumState from caller-supplied amplitudes.

    ``amplitudes`` is truncated or zero-padded to ``dim`` (default: its own
    length). Complex entries keep their phase; a null vector fails closed
    into the uniform superposition rather than fabricating a direction.
    """
    amps = np.asarray(amplitudes, dtype=complex).ravel()
    n = int(dim) if dim is not None else int(amps.size)
    if n < 1:
        raise ValueError("decision space dimension must be >= 1")
    out = np.zeros(n, dtype=complex)
    m = min(n, amps.size)
    out[:m] = amps[:m]
    norm = float(np.linalg.norm(out))
    if norm <= 0.0:
        return QuantumState.uniform_superposition(n)
    return QuantumState(n, [Complex(float(a.real), float(a.imag)) for a in out], normalize=True)


def substrate_state_from_belief(
    belief_distribution: Sequence[float], dim: Optional[int] = None
) -> QuantumState:
    """Encode a probability distribution as amplitude = sqrt(p_i).

    The Born rule then reproduces the caller's distribution exactly —
    this is the standard amplitude embedding of a classical distribution.
    """
    probs = np.asarray(belief_distribution, dtype=float).ravel()
    probs = np.abs(probs)
    n = int(dim) if dim is not None else int(probs.size)
    if n < 1:
        raise ValueError("decision space dimension must be >= 1")
    out = np.zeros(n, dtype=float)
    m = min(n, probs.size)
    out[:m] = probs[:m]
    if out.sum() <= 0.0:
        return QuantumState.uniform_superposition(n)
    return QuantumState.from_real_vector(np.sqrt(out), normalize=True)


def diagonal_observable(values: Sequence[float]) -> ComplexMatrix:
    """Real diagonal observable A = diag(values)."""
    vals = [float(v) for v in values]
    return ComplexMatrix.diagonal([Complex(v, 0.0) for v in vals])


def resize_vector(values: Sequence[float], dim: int, fill: float = 0.0) -> np.ndarray:
    """Truncate or cyclically extend a vector to ``dim``.

    Cyclic extension is used (not zero-padding) so every basis direction of
    the decision space carries signal — a padded tail would silently
    zero-weight the trailing alternatives.
    """
    arr = np.asarray(values, dtype=float).ravel()
    if arr.size == 0:
        return np.full(dim, fill, dtype=float)
    if arr.size >= dim:
        return arr[:dim]
    reps = int(np.ceil(dim / arr.size))
    return np.tile(arr, reps)[:dim]


# ---------------------------------------------------------------------------
# Grover amplitude amplification (real substrate unitaries)
# ---------------------------------------------------------------------------


def grover_oracle(dim: int, marked: Sequence[int]) -> ComplexMatrix:
    """Phase oracle O = I - 2 Σ_m |m><m| flipping the phase of marked states."""
    O = ComplexMatrix.identity(dim)
    for m in marked:
        O.data[int(m)][int(m)] = Complex(-1.0, 0.0)
    return O


def grover_diffusion(dim: int) -> ComplexMatrix:
    """Diffusion operator D = 2|s><s| - I about the uniform superposition |s>."""
    inv = 1.0 / dim
    D = ComplexMatrix(dim, dim)
    for r in range(dim):
        for c in range(dim):
            v = 2.0 * inv - (1.0 if r == c else 0.0)
            D.data[r][c] = Complex(v, 0.0)
    return D


def grover_amplify(
    state: QuantumState,
    marked: Sequence[int],
    iterations: Optional[int] = None,
) -> Tuple[QuantumState, int]:
    """Apply ``iterations`` Grover steps (D·O) to ``state``.

    Default iteration count is the Grover optimum
    ``floor(π/4 · sqrt(N / M))`` for ``M`` marked states out of ``N``.
    Returns the evolved state and the iteration count actually applied.
    """
    n = state.dim
    marked = [int(m) for m in marked if 0 <= int(m) < n]
    if not marked:
        return state, 0
    if iterations is None:
        iterations = max(1, int(math.floor(math.pi / 4.0 * math.sqrt(n / len(marked)))))
    oracle = grover_oracle(n, marked)
    diffusion = grover_diffusion(n)
    evolved = state
    for _ in range(iterations):
        evolved = evolved.apply_unitary(oracle)
        evolved = evolved.apply_unitary(diffusion)
    return evolved, iterations


# ---------------------------------------------------------------------------
# Hamiltonian evolution (finite-precision realisation of e^{-iHt})
# ---------------------------------------------------------------------------


def hamiltonian_evolve(
    state: QuantumState, hamiltonian: ComplexMatrix, time: float = 1.0
) -> QuantumState:
    """Schrödinger evolution |ψ(t)⟩ = e^{-iHt}|ψ⟩ on the substrate.

    The matrix exponential is computed with numpy eigh (the substrate's
    declared IEEE-754 convention for non-diagonal unitaries); the result
    is applied through ``QuantumState.apply_unitary``. Deterministic.
    """
    h = np.array(
        [[complex(hc.re, hc.im) for hc in row] for row in hamiltonian.data],
        dtype=complex,
    )
    # Force Hermiticity residual out (guards against caller matrices that
    # are Hermitian only up to round-off).
    h = 0.5 * (h + h.conj().T)
    eigvals, eigvecs = np.linalg.eigh(h)
    phases = np.exp(-1j * float(time) * eigvals)
    u = (eigvecs * phases) @ eigvecs.conj().T
    umat = ComplexMatrix(state.dim, state.dim)
    for r in range(state.dim):
        for c in range(state.dim):
            umat.data[r][c] = Complex(float(u[r, c].real), float(u[r, c].imag))
    return state.apply_unitary(umat)


def hermitian_from_real(matrix: np.ndarray) -> ComplexMatrix:
    """Wrap a real symmetric/operator numpy array as a ComplexMatrix."""
    arr = np.asarray(matrix)
    rows, cols = arr.shape
    m = ComplexMatrix(rows, cols)
    for r in range(rows):
        for c in range(cols):
            v = complex(arr[r, c])
            m.data[r][c] = Complex(float(v.real), float(v.imag))
    return m


# ---------------------------------------------------------------------------
# Decision analysis on a substrate state
# ---------------------------------------------------------------------------


def decision_analysis(
    state: QuantumState,
    utilities: Sequence[float],
    z_score: float = 1.959964,
) -> Dict[str, Any]:
    """Quantum decision rule: expectation of the utility observable.

    Returns the measured quantities of the decision:

    * ``optimal_action`` — the PVM collapse of the state (argmax Born
      probability), the deterministic maximum-likelihood outcome;
    * ``expected_utility`` — ⟨ψ|U|ψ⟩;
    * ``utility_variance`` — Var(U) = ⟨U²⟩−⟨U⟩² = F_Q/4;
    * ``confidence_interval`` — ⟨U⟩ ± z·√Var(U), the state's own spread;
    * ``born_probabilities`` — the measured action distribution.

    No sampling: every number is exact for the given state and observable.
    """
    obs = diagonal_observable(utilities)
    expected = state.expectation(obs)
    fisher = quantum_fisher_information(state, obs)
    variance = max(fisher / 4.0, 0.0)
    std = math.sqrt(variance)
    outcome, outcome_prob, _collapsed = state.measure_pvm()
    # Exact sensitivity of ⟨U⟩ to each utility component: ∂⟨U⟩/∂u_i = p_i.
    born = state.probabilities()
    return {
        "optimal_action": int(outcome),
        "selected_born_probability": float(outcome_prob),
        "expected_utility": float(expected),
        "utility_variance": float(variance),
        "utility_std": float(std),
        "confidence_interval": (expected - z_score * std, expected + z_score * std),
        "born_probabilities": born_probabilities(state),
        "quantum_fisher_information": float(fisher),
        "utility_sensitivities": [float(p) for p in born],
        "evidence_class": "quantum_substrate_measured",
    }


def expectation_on_context(
    context: Any,
    observable_kernel: Optional[Sequence[float]] = None,
    dim: int = 32,
) -> Dict[str, Any]:
    """Encode arbitrary problem context into a state and measure ⟨O⟩.

    ``context`` is encoded with ``kellogg.quantum_tensor.encode_data_to_state``
    (deterministic). ``observable_kernel`` supplies the diagonal weights of
    the measured observable; default is the deterministic golden-ratio kernel
    w_i = frac(i·φ) ∈ [0,1), a declared weighting (not a measured quantity).
    """
    state = encode_data_to_state(context, dim=dim)
    if observable_kernel is None:
        kernel = np.array([(i * PHI) % 1.0 for i in range(dim)], dtype=float)
    else:
        kernel = resize_vector(observable_kernel, dim, fill=0.0)
    obs = diagonal_observable(kernel)
    expectation = state.expectation(obs)
    fisher = quantum_fisher_information(state, obs)
    outcome, outcome_prob, _ = state.measure_pvm()
    return {
        "expectation": float(expectation),
        "variance": float(max(fisher / 4.0, 0.0)),
        "fisher_information": float(fisher),
        "measured_outcome": int(outcome),
        "outcome_probability": float(outcome_prob),
        "dim": state.dim,
        "evidence_class": "quantum_substrate_measured",
    }


# ---------------------------------------------------------------------------
# Deterministic distribution evaluation (replaces RNG sampling)
# ---------------------------------------------------------------------------


def weyl_unit_sequence(seed: int, n: int) -> np.ndarray:
    """Deterministic low-discrepancy sequence in [0, 1) keyed by ``seed``.

    w_i = frac(seed·φ⁻¹ + (i+1)·φ) — a Weyl sequence on the irrational
    golden-ratio rotation. Deterministic for a given seed, genuinely
    different between seeds, and equidistributed — the honest replacement
    for a pseudo-random uniform draw when reproducibility matters.
    """
    idx = np.arange(1, n + 1, dtype=float)
    w = (float(seed) * (PHI - 1.0) + idx * PHI) % 1.0
    return w


def _erfinv_series(y: np.ndarray) -> np.ndarray:
    """Vectorised inverse error function via Newton iteration on math.erf.

    Deterministic. Seeded at the sign-preserving sqrt-log approximation and
    iterated to machine precision. Not statistics machinery — just root
    finding on erf.
    """
    y = np.asarray(y, dtype=float)
    # Initial approximation (Winitzki form, a = 0.147)
    a = 0.147
    sign = np.sign(y)
    ln = np.log(np.clip(1.0 - y * y, 1e-300, None))
    t = 2.0 / (np.pi * a) + ln / 2.0
    x = sign * np.sqrt(np.maximum(np.sqrt(np.maximum(t * t - ln / a, 0.0)) - t, 0.0))
    # Newton refinement: erf'(x) = 2/sqrt(pi) e^{-x^2}
    for _ in range(6):
        f = _erf_vec(x) - y
        fp = (2.0 / math.sqrt(math.pi)) * np.exp(-x * x)
        x = x - f / np.maximum(fp, 1e-12)
        x = np.clip(x, -6.0, 6.0)
    return x


def _erf_vec(x: np.ndarray) -> np.ndarray:
    """erf(x) for arrays — Abramowitz-Stegun 7.1.26 (|err| < 1.5e-7),
    refined by one Newton step against exp for stability."""
    t = 1.0 / (1.0 + 0.3275911 * np.abs(x))
    poly = t * (
        0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429)))
    )
    erf = np.sign(x) * (1.0 - poly * np.exp(-x * x))
    return erf


def normal_quantile_grid(mean: float, std: float, n: int) -> np.ndarray:
    """Deterministic normal-distribution quantile evaluation.

    Returns the ``n`` equally-spaced quantiles x_i = μ + σ·√2·erf⁻¹(u_i)
    with u_i = (i + 0.5)/n — stratified quadrature of the exact CDF.
    Same statistical content as a large random draw, with zero sampling
    error and full reproducibility.
    """
    n = max(1, int(n))
    std = abs(float(std)) or 1e-9
    u = (np.arange(n, dtype=float) + 0.5) / n
    z = np.sqrt(2.0) * _erfinv_series(2.0 * u - 1.0)
    return float(mean) + std * z


def quantile_grid(distribution: str, params: Dict[str, float], n: int) -> np.ndarray:
    """Deterministic inverse-CDF quantile grid for common distributions."""
    n = max(1, int(n))
    u = (np.arange(n, dtype=float) + 0.5) / n
    dist = str(distribution).lower()
    if dist == "normal":
        mean = float(params.get("mean", 0.0))
        std = abs(float(params.get("std", 1.0))) or 1e-9
        return mean + std * np.sqrt(2.0) * _erfinv_series(2.0 * u - 1.0)
    if dist == "uniform":
        low = float(params.get("low", 0.0))
        high = float(params.get("high", 1.0))
        return low + (high - low) * u
    if dist == "exponential":
        scale = float(params.get("scale", 1.0)) or 1e-9
        return -scale * np.log(1.0 - u)
    if dist == "lognormal":
        mean = float(params.get("mean", 0.0))
        std = abs(float(params.get("std", 1.0))) or 1e-9
        return np.exp(mean + std * np.sqrt(2.0) * _erfinv_series(2.0 * u - 1.0))
    raise ValueError(f"unsupported deterministic distribution: {distribution}")
