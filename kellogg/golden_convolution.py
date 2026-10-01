"""Kellogg golden convolution — scale-domain interaction on Z[phi].

Fourier convolution is the interaction native to translation symmetry; the
golden convolution defined here is the interaction native to the DphiT
scaling symmetry:

    golden_convolution(A, B) = idphi_transform(dphi(A) * dphi(B))

so ``dphi(A *phi B) == dphi(A) * dphi(B)`` holds by construction up to
floating-point roundoff.  The transform is linear, so the product is
O(N) — the cost is the two forward transforms and one inverse, not an
N-squared shift-sum.

``golden_shift`` performs the "scale-step" the pseudocode calls ``S_phi``:
multiplication by phi on the integer lattice, ``a + b*phi -> b + (a+b)*phi``.
On signal indices this is realised exactly through Zeckendorf arithmetic —
shifting every Fibonacci index up by one multiplies the represented integer
by phi (up to the Zeckendorf renormalisation the codec already enforces).

``structural_convolution_sum`` is the direct O(N^2) sum over scale-shifts.
It is the reference definition; ``golden_convolution`` must agree with it
only to the extent the DphiT diagonalises the scale operator — measured in
``convolution_theorem_error``, never asserted.
"""

from __future__ import annotations

import numpy as np

from .dphi_transform import (
    dphi_transform,
    get_golden_grading_vector,
    idphi_transform,
)
from .scales import fibonacci, zeckendorf


class GoldenConvolutionError(ValueError):
    """A golden-convolution shape or depth contract was violated."""


def golden_convolution(
    signal_a: np.ndarray, signal_b: np.ndarray, depth: int = 1
) -> np.ndarray:
    """``idphi(dphi(A) * dphi(B))`` — pointwise product in the scale domain.

    Both signals must have equal length.  The coefficient product is element-
    wise, so the identity ``dphi(A *phi B) = dphi(A) * dphi(B)`` holds
    exactly in the transform domain by construction.
    """
    a = np.asarray(signal_a).ravel()
    b = np.asarray(signal_b).ravel()
    if a.size != b.size:
        raise GoldenConvolutionError(
            f"golden_convolution requires equal lengths: {a.size} vs {b.size}"
        )
    coeff_a = dphi_transform(a, depth)
    coeff_b = dphi_transform(b, depth)
    return idphi_transform(coeff_a * coeff_b, depth)


def golden_scale_filter(
    signal: np.ndarray, scale_mask: np.ndarray, depth: int = 1
) -> np.ndarray:
    """Zero selected scale grades of a signal.

    ``scale_mask`` is a length-N vector of keep/discard weights aligned with
    the DphiT coefficient layout; use :func:`get_golden_grading_vector` to
    build it (e.g. ``(grades < cut).astype(float)`` keeps only coarse scales).
    """
    flat = np.asarray(signal).ravel()
    mask = np.asarray(scale_mask).ravel()
    if flat.size != mask.size:
        raise GoldenConvolutionError(
            f"scale mask length {mask.size} != signal length {flat.size}"
        )
    coeffs = dphi_transform(flat, depth)
    return idphi_transform(coeffs * mask, depth)


def zeckendorf_scale(n: int, steps: int = 1) -> int:
    """Multiply an integer by ``phi**steps`` on the lattice, exactly.

    Zeckendorf ``n = sum F_{k_i}`` maps to ``sum F_{k_i + steps}``: each
    Fibonacci index shifts up ``steps`` slots.  The result stays a legal
    Zeckendorf representation because source indices were non-adjacent and
    remain so after a uniform shift.
    """
    if n < 0:
        raise GoldenConvolutionError("zeckendorf_scale is defined for n >= 0")
    indices = zeckendorf(n)
    return sum(fibonacci(k + steps) for k in indices)


def golden_shift(signal: np.ndarray, steps: int = 1) -> np.ndarray:
    """Scale-shift a signal on the Z[phi] lattice.

    Index ``i`` moves to ``zeckendorf_scale(i, steps)``; indices that would
    leave the array wrap modulo N (the lattice is treated as cyclic for the
    shift, matching modular arithmetic in Z[phi]/N).

    Zeckendorf scaling is generally *not* injective modulo N — colliding
    targets overwrite earlier writes, so the map is a deterministic
    rearrangement, not a permutation.  ``structural_convolution_sum``
    inherits that lossy behaviour; it is a measured comparator, not a
    theorem.
    """
    flat = np.asarray(signal).ravel()
    n = int(flat.size)
    shifted = np.zeros_like(flat)
    for i in range(n):
        j = zeckendorf_scale(i, steps) % n
        shifted[j] = flat[i]
    return shifted


def structural_convolution_sum(
    x: np.ndarray, y: np.ndarray, depth: int = 1
) -> np.ndarray:
    """Direct O(N^2) reference convolution on golden shifts.

    ``out[k] = sum_j x[j] * golden_shift(y, grade(j))[k]`` where ``grade`` is
    the coefficient's scale grade — each coefficient of ``x`` contributes ``y``
    shifted to that scale.  This is the definition the fast path approximates;
    agreement is measured by :func:`convolution_theorem_error`.
    """
    flat_x = np.asarray(x).ravel()
    flat_y = np.asarray(y).ravel()
    if flat_x.size != flat_y.size:
        raise GoldenConvolutionError(
            f"structural_convolution_sum requires equal lengths: "
            f"{flat_x.size} vs {flat_y.size}"
        )
    n = int(flat_x.size)
    grades = get_golden_grading_vector(n, depth)
    output = np.zeros(n, dtype=np.result_type(flat_x, flat_y, np.float64))
    shift_cache: dict[int, np.ndarray] = {}
    for k in range(n):
        grade = int(grades[k])
        if grade not in shift_cache:
            shift_cache[grade] = golden_shift(flat_y, grade)
        output += flat_x[k] * shift_cache[grade]
    return output


def convolution_theorem_error(
    signal_a: np.ndarray, signal_b: np.ndarray, depth: int = 1
) -> float:
    """Measured RMS of ``dphi(A *phi B) - dphi(A) * dphi(B)``.

    The identity holds by construction, so this is a regression check on the
    transform pair (inverse consistency), returning the measured residual.
    """
    conv = golden_convolution(signal_a, signal_b, depth)
    left = dphi_transform(conv, depth)
    right = dphi_transform(signal_a, depth) * dphi_transform(signal_b, depth)
    return float(np.sqrt(np.mean(np.abs(left - right) ** 2)))


def structural_vs_transform_error(
    signal_a: np.ndarray, signal_b: np.ndarray, depth: int = 1
) -> float:
    """Measured RMS between the O(N^2) structural sum and the DphiT path.

    The two constructions agree only when the DphiT eigenbasis diagonalises
    the golden shift — an empirical property of the signals, not a theorem.
    """
    fast = golden_convolution(signal_a, signal_b, depth)
    direct = structural_convolution_sum(signal_a, signal_b, depth)
    return float(np.sqrt(np.mean(np.abs(fast - direct) ** 2)))


__all__ = [
    "GoldenConvolutionError",
    "convolution_theorem_error",
    "golden_convolution",
    "golden_scale_filter",
    "golden_shift",
    "structural_convolution_sum",
    "structural_vs_transform_error",
    "zeckendorf_scale",
]
