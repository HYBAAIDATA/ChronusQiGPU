"""Aethel phi-fold — numeric PhiRecursiveOperator-style fold on arrays.

A fold is a REPRESENTATION change, not a compression claim. Each fold level
splits the retained segment at the Fibonacci ratio ``1/(phi+1) = 1/phi^2``:
the dominant part (fraction ``1/phi``) is kept and the complement
(``1/phi^2``) is stored alongside so reconstruction is bit-exact.

After ``depth`` levels the retained working set is ``phi^-depth`` of the
original — measured, never asserted: :func:`working_set_ratio` returns the
actual ratio of element counts, matching the documented depth-3 value of
~phi^3 = 4.236x.

Honest limitations (evidence quality):
  * ``unfold_partial`` currently performs a full reconstruction and then
    slices the requested ``KernelBoundary``. True partial unfold —
    addressing a single fold level without reconstructing the rest — is a
    research target, not a shipped capability.
  * The fold runs in software (NumPy). Any "effective bandwidth" number
    derived by multiplying a physical bandwidth by the working-set ratio
    is accounting arithmetic, not a measured device property.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Tuple

import numpy as np

logger = logging.getLogger("aethel.phi_fold")

PHI = (1.0 + np.sqrt(5.0)) / 2.0
PHI_SQ = PHI + 1.0  # phi^2 = phi + 1


class PhiFoldError(ValueError):
    """A fold or unfold contract was violated."""


@dataclass(frozen=True)
class KernelBoundary:
    """A contiguous slice of the flat logical array a kernel may touch.

    ``offset`` and ``length`` index into the unfolded (logical) element
    space. ``slice`` is the equivalent Python slice.
    """

    offset: int
    length: int

    def __post_init__(self) -> None:
        if self.offset < 0:
            raise PhiFoldError(f"KernelBoundary offset must be >= 0, got {self.offset}")
        if self.length < 1:
            raise PhiFoldError(f"KernelBoundary length must be >= 1, got {self.length}")

    @property
    def stop(self) -> int:
        return self.offset + self.length

    @property
    def slice(self) -> slice:
        return slice(self.offset, self.stop)


@dataclass(frozen=True)
class NumericFoldState:
    """The folded representation of a numeric array plus its complements.

    ``retained`` is the depth-folded dominant segment; ``complements[i]``
    is the segment split off at fold level ``i + 1``. Reconstruction is
    ``concat(retained, complements[d-1], ..., complements[0])``.
    """

    retained: np.ndarray
    complements: Tuple[np.ndarray, ...] = field(default_factory=tuple)
    depth: int = 0
    original_shape: Tuple[int, ...] = ()
    original_size: int = 0

    @property
    def retained_size(self) -> int:
        return int(self.retained.size)


def _fibonacci_split(dim: int) -> int:
    """Dominant-segment length for one fold level: ~dim/phi.

    The complement is ~dim/phi^2, mirroring the PULVINI split
    ``dim_n2 = round(dim / (phi + 1))``.
    """
    if dim < 2:
        raise PhiFoldError(f"cannot fold a segment of {dim} elements")
    complement = max(1, int(np.rint(dim / PHI_SQ)))
    return dim - complement


def phi_fold(array: np.ndarray, depth: int = 1) -> NumericFoldState:
    """Fold a numeric array ``depth`` levels, retaining every complement.

    Precondition: ``depth >= 0`` and the array is non-empty; each level
    requires at least 2 elements in the retained segment.
    Postcondition: ``phi_unfold(phi_fold(x, d)) == x`` element-exact, and
    ``state.depth == d``.
    """
    flat = np.asarray(array, dtype=np.float64).ravel()
    if flat.size == 0:
        raise PhiFoldError("phi_fold requires a non-empty array")
    if depth < 0:
        raise PhiFoldError(f"depth must be >= 0, got {depth}")
    retained = flat
    complements = []
    for level in range(depth):
        dominant = _fibonacci_split(retained.size)
        retained, complement = retained[:dominant], retained[dominant:]
        complements.append(complement)
        logger.debug(
            "phi_fold level %d: retained %d, complement %d",
            level + 1,
            retained.size,
            complement.size,
        )
    return NumericFoldState(
        retained=retained,
        complements=tuple(complements),
        depth=depth,
        original_shape=tuple(np.asarray(array).shape),
        original_size=int(flat.size),
    )


def phi_unfold(state: NumericFoldState) -> np.ndarray:
    """Reconstruct the original array element-exactly.

    Precondition: ``state`` came from :func:`phi_fold` (complement count
    equals depth). Postcondition: output shape is ``original_shape``.
    """
    if not isinstance(state, NumericFoldState):
        raise PhiFoldError("phi_unfold requires a NumericFoldState")
    if len(state.complements) != state.depth:
        raise PhiFoldError(
            f"fold state has {len(state.complements)} complements for depth {state.depth}"
        )
    flat = state.retained
    for level in range(state.depth - 1, -1, -1):
        flat = np.concatenate([flat, state.complements[level]])
    if flat.size != state.original_size:
        raise PhiFoldError(f"unfold produced {flat.size} elements; expected {state.original_size}")
    return flat.reshape(state.original_shape)


def unfold_partial(state: NumericFoldState, boundary: KernelBoundary) -> np.ndarray:
    """Return ``boundary`` of the unfolded array.

    LIMITATION: this reconstructs the full array and then slices — the
    boundary defines the region returned, not the work performed. True
    partial unfold is declared research scope, not shipped.
    """
    if not isinstance(boundary, KernelBoundary):
        raise PhiFoldError("unfold_partial requires a KernelBoundary")
    flat = phi_unfold(state).ravel()
    if boundary.stop > flat.size:
        raise PhiFoldError(
            f"boundary [{boundary.offset}, {boundary.stop}) exceeds unfolded size {flat.size}"
        )
    return flat[boundary.slice]


def working_set_ratio(state: NumericFoldState) -> float:
    """Measured original/retained element ratio (``~phi^depth``)."""
    if state.retained_size == 0:
        raise PhiFoldError("fold state has an empty retained segment")
    return state.original_size / state.retained_size


def reconstruction_error(original: np.ndarray, state: NumericFoldState) -> float:
    """Measured max-abs error between ``original`` and ``phi_unfold(state)``.

    The value is always computed against the supplied original, never
    assumed — an exact fold reports 0.0 and any corruption in the retained
    or complement segments shows up directly.
    """
    expected = np.asarray(original, dtype=np.float64).ravel()
    got = phi_unfold(state).ravel()
    if expected.size != got.size:
        raise PhiFoldError(f"original has {expected.size} elements; unfolded state has {got.size}")
    return float(np.max(np.abs(expected - got)))


__all__ = [
    "PHI",
    "PHI_SQ",
    "KernelBoundary",
    "NumericFoldState",
    "PhiFoldError",
    "phi_fold",
    "phi_unfold",
    "reconstruction_error",
    "unfold_partial",
    "working_set_ratio",
]
