"""Kellogg discrete phi transform (DphiT) — recursive Z[phi] lattice folding.

A DphiT level partitions the working array into the long and short children
of the golden lattice.  Position ``n`` is a short child exactly when the
characteristic Sturmian word of slope ``1/phi^2`` marks it; the long children
carry fraction ~``1/phi`` of the samples and the short children ~``1/phi^2``,
mirroring ``1/phi + 1/phi^2 = 1``.

The two children interact through a lifting step:

    y' = y - round(phi * x)         (predict: long predicts short)
    x' = x + round(1/phi^2 * y')    (update: residual refines long)

which is a bijection on integer states — every rounding is a deterministic
map, so the inverse recovers the input bit-exactly.  On float or complex
input the rounding is dropped and the step is algebraically invertible up to
ordinary floating-point roundoff (measured, not asserted).

``dphi_transform`` returns a flat coefficient vector laid out
``[coarse..., detail_d, ..., detail_2, detail_1]``: each level writes its
detail into the tail and recurses on the long child.  The layout is shared
with :func:`get_golden_grading_vector`, which assigns every coefficient the
recursive depth that produced it.

Nothing here is a compression claim: the transform is an exact bijection on
integer input and the coefficient count equals the sample count.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0
INV_PHI = PHI - 1.0
INV_PHI_SQ = 2.0 - PHI  # 1/phi^2 = 2 - phi


class DphiTError(ValueError):
    """A DphiT shape, depth, or dtype contract was violated."""


# ---------------------------------------------------------------------------
# Z[phi] lattice partition.


def phi_lattice_mask(length: int) -> np.ndarray:
    """Characteristic-word mask: True marks short children.

    ``mask[n] = floor((n+1)/phi^2) - floor(n/phi^2)`` produces the Fibonacci
    word ``L L S L L S L S L L S L L ...`` — short children occur with
    density ``1/phi^2`` and never repeat consecutively.
    """
    if length < 1:
        raise DphiTError(f"lattice length must be >= 1, got {length}")
    beats = np.floor(np.arange(length + 1, dtype=np.float64) * INV_PHI_SQ)
    return np.diff(beats).astype(bool)


def split_phi_lattice(state: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Split ``state`` into ``(long, short)`` children of the golden lattice."""
    mask = phi_lattice_mask(int(len(state)))
    return state[~mask], state[mask]


def merge_phi_lattice(long_part: np.ndarray, short_part: np.ndarray) -> np.ndarray:
    """Inverse of :func:`split_phi_lattice`; scatters children back in order."""
    n_long = int(len(long_part))
    n_short = int(len(short_part))
    length = n_long + n_short
    mask = phi_lattice_mask(length)
    if int(mask.sum()) != n_short:
        raise DphiTError(
            f"short child has {n_short} elements; lattice of {length} expects "
            f"{int(mask.sum())}"
        )
    merged = np.empty(length, dtype=np.result_type(long_part, short_part))
    merged[~mask] = long_part
    merged[mask] = short_part
    return merged


def _short_count(length: int) -> int:
    return int(phi_lattice_mask(length).sum())


# ---------------------------------------------------------------------------
# Lifting step.


def _lift_pairs(
    x: np.ndarray, y: np.ndarray, exact: bool
) -> Tuple[np.ndarray, np.ndarray]:
    """One golden lifting step on equal-length pairs ``(x, y) -> (x', y')``."""
    if x.shape != y.shape:
        raise DphiTError(f"lifting pairs must align: {x.shape} vs {y.shape}")
    if exact:
        y_prime = y - np.floor(PHI * x + 0.5).astype(np.int64)
        x_prime = x + np.floor(INV_PHI_SQ * y_prime + 0.5).astype(np.int64)
    else:
        y_prime = y - PHI * x
        x_prime = x + INV_PHI_SQ * y_prime
    return x_prime, y_prime


def _unlift_pairs(
    x_prime: np.ndarray, y_prime: np.ndarray, exact: bool
) -> Tuple[np.ndarray, np.ndarray]:
    """Exact inverse of :func:`_lift_pairs`."""
    if exact:
        x = x_prime - np.floor(INV_PHI_SQ * y_prime + 0.5).astype(np.int64)
        y = y_prime + np.floor(PHI * x + 0.5).astype(np.int64)
    else:
        x = x_prime - INV_PHI_SQ * y_prime
        y = y_prime + PHI * x
    return x, y


def golden_lifting_step(
    x: np.ndarray, y: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Integer-exact lifting on long/short sample pairs."""
    return _lift_pairs(np.asarray(x), np.asarray(y), exact=True)


def inverse_golden_lifting_step(
    x_prime: np.ndarray, y_prime: np.ndarray
) -> Tuple[np.ndarray, np.ndarray]:
    """Exact inverse of :func:`golden_lifting_step`."""
    return _unlift_pairs(np.asarray(x_prime), np.asarray(y_prime), exact=True)


def _lift_level(
    state: np.ndarray, exact: bool
) -> Tuple[np.ndarray, np.ndarray]:
    """Split, lift all short children, return ``(coarse, detail)``.

    Long children that have no short partner (there are ``~n/phi - n/phi^2``
    of them) pass through to the coarse register unchanged.
    """
    long_part, short_part = split_phi_lattice(state)
    pairs = int(len(short_part))
    if pairs == 0:
        return state, np.empty(0, dtype=state.dtype)
    x_prime, y_prime = _lift_pairs(long_part[:pairs], short_part, exact)
    coarse = np.concatenate([x_prime, long_part[pairs:]])
    return coarse, y_prime


def _unlift_level(
    coarse: np.ndarray, detail: np.ndarray, exact: bool
) -> np.ndarray:
    """Inverse of :func:`_lift_level`."""
    pairs = int(len(detail))
    x, y = _unlift_pairs(coarse[:pairs], detail, exact)
    full_long = np.concatenate([x, coarse[pairs:]])
    return merge_phi_lattice(full_long, y)


def _is_exact_dtype(array: np.ndarray) -> bool:
    return np.issubdtype(array.dtype, np.integer) or np.issubdtype(
        array.dtype, np.bool_
    )


# ---------------------------------------------------------------------------
# The transform.


def dphi_transform(signal: np.ndarray, depth: int = 1) -> np.ndarray:
    """Forward DphiT: fold ``signal`` ``depth`` levels into coefficients.

    Integer input takes the bit-exact lifting path; float/complex input takes
    the algebraic path.  The output has the same length as the flattened
    input.  Requires 1-D input.
    """
    flat = np.asarray(signal).ravel()
    if flat.size == 0:
        raise DphiTError("dphi_transform requires a non-empty signal")
    if depth < 0:
        raise DphiTError(f"depth must be >= 0, got {depth}")
    exact = _is_exact_dtype(flat)
    if exact and flat.dtype != np.int64:
        flat = flat.astype(np.int64)

    def rec(buf: np.ndarray, d: int) -> np.ndarray:
        if d <= 0 or buf.size < 2:
            return buf
        coarse, detail = _lift_level(buf, exact)
        if detail.size == 0:
            return buf
        return np.concatenate([rec(coarse, d - 1), detail])

    return rec(flat, depth)


def idphi_transform(coeffs: np.ndarray, depth: int = 1) -> np.ndarray:
    """Inverse DphiT: rebuild the signal from its coefficient layout."""
    flat = np.asarray(coeffs).ravel()
    if flat.size == 0:
        raise DphiTError("idphi_transform requires a non-empty coefficient vector")
    if depth < 0:
        raise DphiTError(f"depth must be >= 0, got {depth}")
    exact = _is_exact_dtype(flat)
    if exact and flat.dtype != np.int64:
        flat = flat.astype(np.int64)

    def rec(buf: np.ndarray, d: int) -> np.ndarray:
        if d <= 0 or buf.size < 2:
            return buf
        n = int(buf.size)
        n_short = _short_count(n)
        if n_short == 0:
            return buf
        n_long = n - n_short
        # Recursion refines the long child first; the tail holds this level's
        # detail coefficients.
        coarse = rec(buf[:n_long], d - 1)
        return _unlift_level(coarse, buf[n_long:], exact)

    return rec(flat, depth)


def get_golden_grading_vector(length: int, depth: int) -> np.ndarray:
    """Scale grade of every coefficient position in the DphiT layout.

    Positions holding level-``d`` detail get grade ``d``; the surviving
    coarse block keeps grade 0.  Matches the transform's
    ``[coarse..., detail_d, ..., detail_1]`` layout.
    """
    if length < 1:
        raise DphiTError(f"grading vector length must be >= 1, got {length}")
    grades = np.zeros(int(length), dtype=np.float64)

    def assign(start: int, size: int, d: int) -> None:
        if d <= 0 or size < 2:
            return
        n_short = _short_count(size)
        if n_short == 0:
            return
        n_long = size - n_short
        grades[start + n_long : start + size] = float(d)
        assign(start, n_long, d - 1)

    assign(0, int(length), int(depth))
    return grades


def fibonacci_word_signal(length: int) -> np.ndarray:
    """The Fibonacci word as a 0/1 signal (1 = short lattice child)."""
    return phi_lattice_mask(length).astype(np.float64)


# ---------------------------------------------------------------------------
# Wall 6: the reversible renormalizer.


@dataclass
class ReversibleRenormalizer:
    """Coarsen a state ``depth`` levels, storing details in an aux stack.

    ``fold_system`` is the DphiT recursion with each level's detail kept on
    ``auxiliary_stacks``; ``unfold_system`` pops the stack and restores the
    micro-state bit-for-bit on integer input.
    """

    depth: int
    auxiliary_stacks: List[np.ndarray] = field(default_factory=list)
    _exact: bool = field(default=True, repr=False)

    def fold_system(self, state: np.ndarray) -> np.ndarray:
        flat = np.asarray(state).ravel()
        self._exact = _is_exact_dtype(flat)
        if self._exact and flat.dtype != np.int64:
            flat = flat.astype(np.int64)
        self.auxiliary_stacks = []
        current = flat
        for _ in range(self.depth):
            if current.size < 2:
                break
            coarse, detail = _lift_level(current, self._exact)
            if detail.size == 0:
                break
            self.auxiliary_stacks.append(detail)
            current = coarse
        return current

    def unfold_system(self, coarse_state: np.ndarray) -> np.ndarray:
        current = np.asarray(coarse_state).ravel()
        while self.auxiliary_stacks:
            detail = self.auxiliary_stacks.pop()
            current = _unlift_level(current, detail, self._exact)
        return current


# ---------------------------------------------------------------------------
# Wall 6 benchmark: entropy debt of FFT vs integer DphiT.


@dataclass(frozen=True)
class StabilityBenchmarkResult:
    """Measured outcome of the DphiT-vs-FFT stability duel."""

    iterations: int
    signal_length: int
    depth: int
    phi_bit_divergence: int
    fft_rms_error: float


def run_stability_benchmark(
    signal_length: int = 1597,
    iterations: int = 200,
    depth: int = 6,
    seed: int = 0,
) -> StabilityBenchmarkResult:
    """Repeat forward/inverse passes and measure divergence.

    The integer DphiT path is bit-exact by construction, so any nonzero
    ``phi_bit_divergence`` is a bug, not drift.  The FFT path accumulates
    ordinary floating-point roundoff — ``fft_rms_error`` is measured, not
    assumed.
    """
    rng = np.random.default_rng(seed)
    initial = rng.integers(0, 2, size=signal_length, dtype=np.int64)

    phi_state = initial.copy()
    for _ in range(iterations):
        phi_state = idphi_transform(
            dphi_transform(phi_state, depth), depth
        )
    phi_error = int(np.count_nonzero(phi_state != initial))

    fft_state = initial.astype(np.float64)
    for _ in range(iterations):
        fft_state = np.fft.ifft(np.fft.fft(fft_state)).real
    fft_error = float(np.sqrt(np.mean((fft_state - initial) ** 2)))

    return StabilityBenchmarkResult(
        iterations=iterations,
        signal_length=signal_length,
        depth=depth,
        phi_bit_divergence=phi_error,
        fft_rms_error=fft_error,
    )


__all__ = [
    "DphiTError",
    "INV_PHI",
    "INV_PHI_SQ",
    "PHI",
    "ReversibleRenormalizer",
    "StabilityBenchmarkResult",
    "dphi_transform",
    "fibonacci_word_signal",
    "get_golden_grading_vector",
    "golden_lifting_step",
    "idphi_transform",
    "inverse_golden_lifting_step",
    "merge_phi_lattice",
    "phi_lattice_mask",
    "run_stability_benchmark",
    "split_phi_lattice",
]
