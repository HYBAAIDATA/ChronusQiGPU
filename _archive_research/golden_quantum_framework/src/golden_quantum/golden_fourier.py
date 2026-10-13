"""GOLDEN-FOURIER TRANSFORM
============================

The Golden-Fourier transform bridges Fourier and Golden ontologies:

  GF(ω, n) = Σ f(k) φ^(-nk) e^(-iωk)

Forward transform:  Stable (φ^(-nk) decays exponentially)
Inverse transform:  Requires regularization (φ^(nk) grows exponentially)

Reductions:
  - Fourier (φ → 1):    GF(ω, n) → F(ω) = Σ f(k) e^(-iωk)
  - Golden (ω → 0):     GF(ω, n) → G(n) = Σ f(k) φ^(-nk)

Property: "Fourier analysis is the shadow of Golden analysis when the φ-structure is averaged out."
"""
from __future__ import annotations
import math
import numpy as np
from decimal import Decimal, getcontext
from .constants import PHI_D, PHI_F
from .sequences import phi_power


def _ensure_precision(prec: int = 50) -> None:
    getcontext().prec = max(prec, 50)


def golden_fourier_forward(
    f: np.ndarray,
    n_values: np.ndarray,
    omega_values: np.ndarray,
    damping: float | None = None,
    prec: int = 50,
) -> np.ndarray:
    _ensure_precision(prec)
    N = len(f)
    L = len(omega_values)
    M = len(n_values)
    GF = np.zeros((L, M), dtype=complex)
    phi_inv = Decimal(1) / PHI_D  # φ^(-1)
    for l in range(L):
        omega = float(omega_values[l])
        for m in range(M):
            n = int(n_values[m])
            total = complex(0, 0)
            for k in range(N):
                fk = float(f[k]) if k < len(f) else 0
                exp = n * k
                if exp == 0:
                    phi_factor = 1.0
                else:
                    phi_factor = float(phi_inv ** exp)
                wk = omega * k
                ce = math.cos(wk)
                se = math.sin(wk)
                complex_factor = complex(ce, -se)  # e^(-iωk)
                total += fk * phi_factor * complex_factor
            GF[l, m] = total
    return GF


def golden_fourier_inverse(
    GF: np.ndarray,
    n_values: np.ndarray,
    omega_values: np.ndarray | None = None,
    damping: float = 0.5,
    prec: int = 50,
    N: int | None = None,
) -> np.ndarray:
    """Compute the inverse Golden-Fourier transform with regularization.

    The inverse transform is unstable because φ^(nk) grows exponentially.
    We apply damping: use α^(nk) where α ∈ (0, 1) dampens the growth.

    Effective term: (αφ)^(nk) which grows if αφ > 1, decays if αφ < 1.
    Choosing α = 1/PHI = φ^(-1) ≈ 0.618 gives (αφ)^(nk) = 1 exactly!

    Parameters
    ----------
    GF : np.ndarray of shape (L, M)
        Golden-Fourier transform values.
    n_values : np.ndarray of shape (M,)
        Row indices n.
    omega_values : np.ndarray, optional
        Column indices ω. If None, uses default values.
    damping : float
        Damping factor α ∈ (0, 1). Defaults to 1/PHI for exact cancellation.
    prec : int
        Decimal precision.
    N : int, optional
        Length of the reconstructed signal. This is independent of
        len(n_values)/max(n_values) — n_values only names which φ-domain
        rows GF was sampled at; it says nothing about how many time-domain
        samples the original signal had. Forgetting this previously made
        the "reconstructed" signal silently truncate to max(n_values)+1
        samples regardless of the true signal length. Defaults to
        max(n_values)+1 only when N isn't given, which is still just a
        guess — pass the real original length explicitly whenever you have
        it.

    Returns
    -------
    f : np.ndarray of shape (N,)
        Reconstructed signal.
    """
    _ensure_precision(prec)
    L, M = GF.shape

    if N is None:
        N = int(max(n_values)) + 1

    if omega_values is None:
        omega_values = np.linspace(0, 2 * math.pi, N, endpoint=False)

    # Default damping: α = 1/PHI = φ^(-1) ≈ 0.618
    # This makes (αφ)^(nk) = 1, exactly canceling the φ^(nk) growth
    alpha = damping

    # Compute reconstruction for each k
    f = np.zeros(N, dtype=complex)

    for k in range(N):
        total = complex(0, 0)
        for l in range(L):
            omega = float(omega_values[l])
            for m in range(M):
                GF_lm = complex(GF[l, m])
                n = int(n_values[m])

                # φ^(n*k) grows exponentially - needs damping
                exp = n * k
                if exp == 0:
                    phi_pow = 1.0
                else:
                    # Use dampened form: (alpha * PHI)^exp
                    dampened_base = alpha * float(PHI_D)
                    if dampened_base <= 0:
                        phi_pow = 1.0
                    else:
                        phi_pow = dampened_base ** exp

                # e^(iωk) = cos(ωk) + i*sin(ωk)
                wk = omega * k
                ce = math.cos(wk)
                se = math.sin(wk)
                complex_factor = complex(ce, se)  # e^(iωk)

                total += GF_lm * phi_pow * complex_factor
        f[k] = total / (L * M)

    # Return real part (should be real for valid inputs)
    return np.real(f)


def golden_fourier_reduction(
    GF: np.ndarray,
    to: str = "fourier",
    f: np.ndarray | None = None,
    omega_values: np.ndarray | None = None,
) -> np.ndarray:
    """Reduce Golden-Fourier transform to its Fourier or Golden limit.

    φ never appears as its own axis of GF — it's a fixed scalar baked into
    every entry via phi_inv**exp during the forward pass, unlike ω and n
    which are genuine array axes. That means the ω → 0 (golden) limit is a
    real slice of an already-computed GF (evaluating at the ω=0 row is
    exactly what "ω → 0" means on a discretized grid), but the φ → 1
    (fourier) limit is NOT recoverable from GF alone: GF's n-dependence has
    already mixed real φ-decay into every entry, and there's no way to
    subtract that back out without knowing the original signal. So
    to="fourier" requires the original signal f and the omega_values GF was
    computed with, and recomputes a plain DFT (phi_factor forced to 1 for
    all n, which collapses the n-dependence entirely — matching the
    docstring's G(ω,n) → F(ω) = Σ f(k) e^(-iωk)).

    Parameters
    ----------
    GF : np.ndarray of shape (L, M)
        Golden-Fourier transform (only used for to="golden").
    to : str
        "fourier" -> limit φ → 1 (keep ω structure); requires f, omega_values.
        "golden" -> limit ω → 0 (keep φ structure); slices GF directly.
    f : np.ndarray, optional
        Original signal — required when to="fourier".
    omega_values : np.ndarray, optional
        ω grid GF was computed with — required when to="fourier".

    Returns
    -------
    reduced : np.ndarray
        Reduced transform: shape (L,) for "fourier", (M,) for "golden".
    """
    if to == "fourier":
        if f is None or omega_values is None:
            raise ValueError(
                "to='fourier' needs the original signal f and omega_values — "
                "the phi -> 1 limit can't be recovered from GF alone, since "
                "phi's n-dependence is already baked into every GF entry and "
                "isn't a separate array axis to slice away."
            )
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
    elif to == "golden":
        if GF.shape[0] > 1:
            return GF[0, :].copy()
        else:
            return GF.copy()
    else:
        raise ValueError(f"Unknown reduction target: {to}. Use 'fourier' or 'golden'.")


def detect_phi_structure(
    data: np.ndarray,
    n_max: int | None = None,
    omega_max: int | None = None,
    threshold: float = 0.1,
) -> dict:
    """Detect φ-structured patterns in data using Golden-Fourier transform.

    Parameters
    ----------
    data : np.ndarray
        Input data signal.
    n_max : int, optional
        Maximum n parameter for φ-folding. Default: len(data)//2.
    omega_max : int, optional
        Maximum ω parameter for Fourier. Default: len(data)//2.
    threshold : float
        Energy ratio threshold for φ-structure detection.

    Returns
    -------
    result : dict
        {
            "is_phi_structured": bool,
            "phi_energy": float,
            "fourier_energy": float,
            "phi_energy_ratio": float,
            "fourier_energy_ratio": float,
            "total_energy": float,
            "GF": np.ndarray,
        }
    """
    N = len(data)
    if n_max is None:
        n_max = N // 2
    if omega_max is None:
        omega_max = N // 2

    n_values = np.arange(0, n_max + 1, dtype=float)
    omega_values = np.arange(0, omega_max + 1, dtype=float)

    GF = golden_fourier_forward(data, n_values, omega_values)

    # GF[0, :] is the ω=0 row (pure-golden edge, n varying) and GF[:, 0] is
    # the n=0 column (pure-fourier edge, ω varying). They share the single
    # cell GF[0, 0] (ω=0 AND n=0 simultaneously — just Σ f(k), no phi decay,
    # no oscillation). Counting it in both edges double-counts it and made
    # phi_energy_ratio + fourier_energy_ratio sum to >1. Drop it from one
    # side so the two edges are disjoint, and normalize the ratio against
    # their combined energy (not the full L×M grid's total_energy, most of
    # which is neither pure-golden nor pure-fourier — it's mixed (ω,n)
    # structure that this ratio was never actually measuring).
    G = GF[0, 1:] if GF.shape[1] > 1 else np.array([])  # pure-golden edge, excl. shared origin
    F = GF[:, 0] if GF.shape[0] > 0 else np.array([])   # pure-fourier edge, incl. shared origin

    phi_energy = float(np.sum(np.abs(G) ** 2))
    fourier_energy = float(np.sum(np.abs(F) ** 2))
    total_energy = float(np.sum(np.abs(GF) ** 2))
    edge_energy = phi_energy + fourier_energy

    if edge_energy > 0:
        phi_energy_ratio = phi_energy / edge_energy
        fourier_energy_ratio = fourier_energy / edge_energy
    else:
        phi_energy_ratio = 0.0
        fourier_energy_ratio = 0.0

    is_phi_structured = phi_energy_ratio > fourier_energy_ratio

    return {
        "is_phi_structured": bool(is_phi_structured),
        "phi_energy": phi_energy,
        "fourier_energy": fourier_energy,
        "phi_energy_ratio": phi_energy_ratio,
        "fourier_energy_ratio": fourier_energy_ratio,
        "total_energy": total_energy,
        "edge_energy_fraction_of_total": (edge_energy / total_energy) if total_energy > 0 else 0.0,
        "GF": GF,
    }


def test_forward_stability() -> dict:
    """Test that the forward Golden-Fourier transform is numerically stable.

    Returns
    -------
    result : dict
        Stability test results.
    """
    # Generate test data: random + known φ-structured component
    np.random.seed(42)
    N = 50
    f = np.random.randn(N)

    # Add a φ-structured component: f(k) *= φ^(-k)
    phi = float(PHI_F)
    for k in range(N):
        f[k] *= phi ** (-k)

    # Compute Golden-Fourier transform
    n_values = np.arange(0, 10, dtype=float)
    omega_values = np.linspace(0, np.pi, 10, endpoint=False)
    GF = golden_fourier_forward(f, n_values, omega_values)

    # Check for NaN or Inf
    has_nan = np.any(np.isnan(GF))
    has_inf = np.any(np.isinf(GF))

    # Check that values are reasonable (not overflowing)
    max_abs = np.max(np.abs(GF))
    total_energy = np.sum(np.abs(GF) ** 2)

    stable = not (has_nan or has_inf or np.isinf(total_energy) or total_energy > 1e10)

    return {
        "stable": stable,
        "has_nan": bool(has_nan),
        "has_inf": bool(has_inf),
        "max_abs": float(max_abs),
        "total_energy": float(total_energy),
        "N": N,
    }


def test_inverse_with_regularization() -> dict:
    """Test the inverse Golden-Fourier transform with damping regularization.

    Returns
    -------
    result : dict
        Inverse transform test results.
    """
    # Generate test data
    np.random.seed(42)
    N = 30
    f_original = np.random.randn(N)

    # Compute forward transform
    n_values = np.arange(0, 5, dtype=float)
    omega_values = np.linspace(0, 2 * math.pi, 5, endpoint=False)
    GF = golden_fourier_forward(f_original, n_values, omega_values)

    # Compute inverse with regularization. N must be passed explicitly —
    # n_values only names which phi-rows GF was sampled at (5 of them
    # here), not the original signal's length (30); leaving N unset would
    # silently reconstruct only 5 samples and fail to compare against
    # f_original at all.
    damping = 1.0 / float(PHI_F)  # α = 1/PHI ≈ 0.618
    f_reconstructed = golden_fourier_inverse(GF, n_values, omega_values, damping=damping, N=N)

    # Compare original vs reconstructed
    mse = np.mean((f_original - f_reconstructed) ** 2)
    rmse = np.sqrt(mse)
    rel_error = rmse / np.linalg.norm(f_original)

    # Check reconstruction quality
    success = rel_error < 0.5  # reasonable threshold for truncated transform

    return {
        "success": success,
        "rel_error": float(rel_error),
        "mse": float(mse),
        "rmse": float(rmse),
        "N": N,
        "damping": float(damping),
    }


def main() -> None:
    """Run tests when module is executed directly."""
    print("=" * 60)
    print("GOLDEN-FOURIER TRANSFORM TESTS")
    print("=" * 60)

    print("\n1. Forward Stability Test")
    forward_result = test_forward_stability()
    print(f"   Stable: {forward_result['stable']}")
    print(f"   Max |GF|: {forward_result['max_abs']:.4f}")
    print(f"   Total energy: {forward_result['total_energy']:.4f}")

    print("\n2. Inverse with Regularization Test")
    inverse_result = test_inverse_with_regularization()
    print(f"   Success: {inverse_result['success']}")
    print(f"   Relative error: {inverse_result['rel_error']:.4f}")
    print(f"   MSE: {inverse_result['mse']:.6f}")

    print("\n3. Phi Structure Detection Test")
    test_data = np.sin(np.arange(100) * 0.1) + 0.1 * np.random.randn(100)
    detection = detect_phi_structure(test_data, n_max=10, omega_max=20)
    print(f"   Phi-structured: {detection['is_phi_structured']}")
    print(f"   φ-energy ratio: {detection['phi_energy_ratio']:.4f}")
    print(f"   Fourier-energy ratio: {detection['fourier_energy_ratio']:.4f}")

    print("\n" + "=" * 60)
    print("TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
