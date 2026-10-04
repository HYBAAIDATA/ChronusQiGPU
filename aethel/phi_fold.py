"""Aethel phi-fold — numeric PhiRecursiveOperator-style fold on arrays.

A fold is a REPRESENTATION change, not a compression claim. Each fold level
splits the retained segment at the Fibonacci ratio ``1/(phi+1) = 1/phi^2``:
the dominant part (fraction ``1/phi``) is kept and the complement
(``1/phi^2``) is stored alongside so reconstruction is bit-exact.

After ``depth`` levels the retained working set is ``phi^-depth`` of the
original — measured, never asserted: :func:`working_set_ratio` returns the
actual ratio of element counts, matching the documented depth-3 value of
~phi^3 = 4.236x.

``unfold_partial`` is a true addressed reconstruction.  The logical array is
represented by the final retained segment followed by complements in reverse
fold order.  A boundary read intersects only those resident segments touched by
the requested logical interval; it does not build the complete original array
as an intermediate.  ``unfold_partial_with_stats`` exposes the amount of source
state actually visited so this property remains regression-testable.

The fold runs in software unless a caller dispatches arithmetic through the
Tensor/Chronus hardware backend. Any effective-bandwidth number derived by
multiplying a physical bandwidth by a working-set ratio is accounting
arithmetic, not a measured device property.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Tuple

import numpy as np

logger = logging.getLogger("aethel.phi_fold")

PHI = (1.0 + np.sqrt(5.0)) / 2.0
PHI_SQ = PHI + 1.0  # phi^2 = phi + 1

#: Element kinds admissible to folded custody. Bool is excluded because
#: reconstruction-error arithmetic (subtraction) is undefined on it; object
#: and structured dtypes are excluded because element identity is undefined
#: for them. Numeric dtypes — signed/unsigned int, float, complex — all
#: round-trip bit-exact through the partition.
_FOLDABLE_KINDS = frozenset("iufc")


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

    ``dtype`` records the element type held in custody — every segment
    shares it. ``layout`` records the flat-memory order the fold was taken
    over (``"C"`` today). ``content_hash`` is a SHA-256 digest over the
    dtype, shape, and every segment's raw bytes: content identity that
    survives reload and detects corruption.
    """

    retained: np.ndarray
    complements: Tuple[np.ndarray, ...] = field(default_factory=tuple)
    depth: int = 0
    original_shape: Tuple[int, ...] = ()
    original_size: int = 0
    dtype: np.dtype = np.dtype(np.float64)
    layout: str = "C"
    content_hash: str = ""

    @property
    def retained_size(self) -> int:
        return int(self.retained.size)

    def compute_content_hash(self) -> str:
        """Deterministic SHA-256 over dtype, shape, and all segment bytes."""
        digest = hashlib.sha256()
        digest.update(np.dtype(self.dtype).str.encode("utf-8"))
        digest.update(repr(tuple(self.original_shape)).encode("utf-8"))
        digest.update(int(self.original_size).to_bytes(8, "little"))
        for segment in (self.retained, *self.complements):
            digest.update(np.ascontiguousarray(segment).tobytes(order="C"))
        return digest.hexdigest()

    def verify_content_hash(self) -> bool:
        """Recompute the content digest; False means custody was altered."""
        return bool(self.content_hash) and self.content_hash == self.compute_content_hash()


@dataclass(frozen=True)
class PartialUnfoldStats:
    """Measured work performed by a selective unfold."""

    requested_values: int
    source_values_read: int
    source_segments_touched: int
    source_segments_total: int
    full_length: int
    depth: int

    @property
    def reconstructed_fraction(self) -> float:
        return self.requested_values / self.full_length if self.full_length else 0.0

    @property
    def source_fraction(self) -> float:
        return self.source_values_read / self.full_length if self.full_length else 0.0


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
    requires at least 2 elements in the retained segment. The input must be a
    numeric dtype (int, uint, float, or complex); no silent coercion happens
    — the folded segments keep the caller's dtype so reconstruction is
    bit-exact for every supported dtype, including complex64/complex128.
    Postcondition: ``phi_unfold(phi_fold(x, d)) == x`` element-exact with the
    original dtype, and ``state.depth == d``.
    """
    flat = np.ascontiguousarray(np.asarray(array)).ravel()
    if flat.size == 0:
        raise PhiFoldError("phi_fold requires a non-empty array")
    if flat.dtype.kind not in _FOLDABLE_KINDS:
        raise PhiFoldError(
            f"folded custody requires a numeric dtype (int/uint/float/complex); "
            f"got {flat.dtype}"
        )
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
    state = NumericFoldState(
        retained=retained,
        complements=tuple(complements),
        depth=depth,
        original_shape=tuple(np.asarray(array).shape),
        original_size=int(flat.size),
        dtype=flat.dtype,
        layout="C",
    )
    object.__setattr__(state, "content_hash", state.compute_content_hash())
    return state


def _validate_state(state: NumericFoldState) -> None:
    if not isinstance(state, NumericFoldState):
        raise PhiFoldError("operation requires a NumericFoldState")
    if len(state.complements) != state.depth:
        raise PhiFoldError(
            f"fold state has {len(state.complements)} complements for depth {state.depth}"
        )
    represented = state.retained_size + sum(int(part.size) for part in state.complements)
    if represented != state.original_size:
        raise PhiFoldError(
            f"fold state represents {represented} elements; expected {state.original_size}"
        )
    state_dtype = np.dtype(state.dtype)
    if state.retained.dtype != state_dtype or any(
        part.dtype != state_dtype for part in state.complements
    ):
        raise PhiFoldError(
            f"fold state mixes segment dtypes; all segments must be {state_dtype}"
        )


def phi_unfold(state: NumericFoldState) -> np.ndarray:
    """Reconstruct the original array element-exactly."""
    _validate_state(state)
    flat = state.retained
    for level in range(state.depth - 1, -1, -1):
        flat = np.concatenate([flat, state.complements[level]])
    if flat.size != state.original_size:
        raise PhiFoldError(f"unfold produced {flat.size} elements; expected {state.original_size}")
    return flat.reshape(state.original_shape)


def _logical_segments(state: NumericFoldState) -> Tuple[np.ndarray, ...]:
    """Return resident segments in their logical unfolded order.

    This returns references to the existing retained/complement arrays.  It does
    not concatenate or copy them.
    """
    _validate_state(state)
    return (state.retained,) + tuple(reversed(state.complements))


def unfold_partial_with_stats(
    state: NumericFoldState, boundary: KernelBoundary
) -> Tuple[np.ndarray, PartialUnfoldStats]:
    """Reconstruct only ``boundary`` without materialising the full tensor.

    Because the numeric fold retains every complement as a contiguous resident
    segment, the unfolded flat array is exactly ``retained + reversed(complements)``.
    The addressed read walks segment extents, copies only intersecting spans and
    concatenates at most ``depth + 1`` small pieces.
    """
    if not isinstance(boundary, KernelBoundary):
        raise PhiFoldError("unfold_partial requires a KernelBoundary")
    _validate_state(state)
    if boundary.stop > state.original_size:
        raise PhiFoldError(
            f"boundary [{boundary.offset}, {boundary.stop}) exceeds unfolded size "
            f"{state.original_size}"
        )

    requested_start = boundary.offset
    requested_stop = boundary.stop
    logical_offset = 0
    pieces = []
    source_values_read = 0
    segments_touched = 0
    segments = _logical_segments(state)

    for segment in segments:
        segment_size = int(segment.size)
        segment_start = logical_offset
        segment_stop = logical_offset + segment_size
        logical_offset = segment_stop
        if requested_stop <= segment_start:
            break
        if requested_start >= segment_stop:
            continue
        local_start = max(requested_start, segment_start) - segment_start
        local_stop = min(requested_stop, segment_stop) - segment_start
        if local_stop > local_start:
            piece = np.asarray(segment).ravel()[local_start:local_stop]
            pieces.append(piece)
            source_values_read += int(piece.size)
            segments_touched += 1

    if source_values_read != boundary.length:
        raise PhiFoldError(
            f"partial unfold reconstructed {source_values_read} values; expected {boundary.length}"
        )
    if not pieces:
        result = np.empty(0, dtype=state.dtype)
    elif len(pieces) == 1:
        result = pieces[0].copy()
    else:
        result = np.concatenate(pieces)

    stats = PartialUnfoldStats(
        requested_values=boundary.length,
        source_values_read=source_values_read,
        source_segments_touched=segments_touched,
        source_segments_total=len(segments),
        full_length=state.original_size,
        depth=state.depth,
    )
    return result, stats


def unfold_partial(state: NumericFoldState, boundary: KernelBoundary) -> np.ndarray:
    """Return ``boundary`` using the true addressed reconstruction path."""
    return unfold_partial_with_stats(state, boundary)[0]


def fold_result(
    result_slice: np.ndarray,
    boundary: KernelBoundary,
    original_state: NumericFoldState,
    *,
    depth: int | None = None,
) -> NumericFoldState:
    """Write a computed logical slice back into a folded state losslessly.

    Updating a folded resident necessarily changes the representation of the
    containing tensor, so this operation reconstructs the full logical payload,
    applies the bounded write, then re-folds at the requested/original depth.
    Reads remain truly partial; writes are explicitly full-state re-folds.
    """
    _validate_state(original_state)
    values = np.asarray(result_slice)
    if values.dtype != np.dtype(original_state.dtype):
        raise PhiFoldError(
            f"result slice dtype {values.dtype} does not match custodied "
            f"dtype {original_state.dtype}; conversion is the caller's decision"
        )
    values = values.ravel()
    if values.size != boundary.length:
        raise PhiFoldError(
            f"result slice has {values.size} values; boundary requires {boundary.length}"
        )
    if boundary.stop > original_state.original_size:
        raise PhiFoldError("result slice exceeds original tensor bounds")
    full = phi_unfold(original_state).ravel().copy()
    full[boundary.slice] = values
    target_depth = original_state.depth if depth is None else int(depth)
    return phi_fold(full.reshape(original_state.original_shape), depth=target_depth)


def working_set_ratio(state: NumericFoldState) -> float:
    """Measured original/retained element ratio (``~phi^depth``)."""
    if state.retained_size == 0:
        raise PhiFoldError("fold state has an empty retained segment")
    return state.original_size / state.retained_size


def reconstruction_error(original: np.ndarray, state: NumericFoldState) -> float:
    """Measured max-abs error between ``original`` and ``phi_unfold(state)``."""
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
    "PartialUnfoldStats",
    "PhiFoldError",
    "fold_result",
    "phi_fold",
    "phi_unfold",
    "reconstruction_error",
    "unfold_partial",
    "unfold_partial_with_stats",
    "working_set_ratio",
]
