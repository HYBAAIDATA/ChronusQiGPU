"""Direct partial reconstruction of a PULVINI fold without full unfolding.

This uses the protected PhiRecursiveOperator weights and Fibonacci chronology
read-only. It reconstructs only requested flattened indices, at bounded cost
O(requested_values * fold_depth), without rebuilding unselected values.

Partial results cannot verify the full original source hash. An authenticated
THESEUS/AL HARAS custody record is required for adversarial integrity claims.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import prod
import numpy as np
from chronus.pulvini.formal import FoldState, PhiRecursiveOperator, ValidationError

_MAX_SELECT = 65536
_MAX_ELEMENTS = 1_000_000


@dataclass(frozen=True)
class SelectiveUnfoldResult:
    values: np.ndarray
    start: int
    stop: int
    touched_folded_indices: int
    touched_kernel_entries: int
    full_original_digest_verified: bool = False
    classification: str = "PARTIAL_NUMERICAL_RECONSTRUCTION_NO_FULL_DIGEST"


def unfold_partial_recursive(state: FoldState, start: int, stop: int) -> SelectiveUnfoldResult:
    """Reconstruct a contiguous range from a flat PULVINI state, no full unfold.

    Selection requires a separately trusted immutable state/receipt. A partial
    numerical result is not a full-file SHA-256 verification or bytewise proof.
    """
    if not isinstance(state, FoldState):
        raise ValidationError("PULVINI FoldState required")
    if (type(start) is not int or type(stop) is not int or start < 0
            or stop < start or stop - start > _MAX_SELECT):
        raise ValidationError("bounded flat interval required")
    if not state.original_shape or any(type(v) is not int or v < 1 for v in state.original_shape):
        raise ValidationError("original shape invalid")
    length = prod(state.original_shape)
    if not 1 <= length <= _MAX_ELEMENTS or stop > length:
        raise ValidationError("original length or request outside policy")
    operator = PhiRecursiveOperator(normalization=state.normalization)
    if len(state.sizes) != len(state.kernels) + 1 or state.sizes[0] != length:
        raise ValidationError("invalid PULVINI chronology")
    if state.folded.ndim != 1 or state.folded.size != state.sizes[-1]:
        raise ValidationError("invalid deepest folded channel")
    for level, (before, after) in enumerate(zip(state.sizes[:-1], state.sizes[1:])):
        if type(before) is not int or type(after) is not int:
            raise ValidationError("chronology must have integer dimensions")
        n1, _ = operator.fibonacci_split(before)
        k = state.kernels[level]
        if after != n1 or k.ndim != 1 or k.size != n1:
            raise ValidationError("kernel/chronology mismatch")
    w1, w2, norm_sq = operator._weights()
    dtype = np.complex128 if np.iscomplexobj(state.folded) else np.float64
    result = np.empty(stop - start, dtype=dtype)
    deepest_touched: set[int] = set()
    kernel_touched: set[tuple[int, int]] = set()
    for offset, source_idx in enumerate(range(start, stop)):
        path = []
        idx = source_idx
        for level, before in enumerate(state.sizes[:-1]):
            n1 = state.sizes[level + 1]
            left = idx < n1
            idx = idx if left else idx - n1
            path.append((level, idx, left))
        deepest_touched.add(idx)
        value = state.folded[idx]
        if not np.isfinite(value):
            raise ValidationError("nonfinite selected folded value")
        for level, part_idx, left in reversed(path):
            kernel_touched.add((level, part_idx))
            kernel_value = state.kernels[level][part_idx]
            if not np.isfinite(kernel_value):
                raise ValidationError("nonfinite selected kernel value")
            value = ((w1 * value + w2 * kernel_value) / norm_sq if left
                     else (w2 * value - w1 * kernel_value) / norm_sq)
        result[offset] = value
    if not np.all(np.isfinite(result)):
        raise ValidationError("nonfinite partial reconstruction")
    return SelectiveUnfoldResult(
        values=result,
        start=start,
        stop=stop,
        touched_folded_indices=len(deepest_touched),
        touched_kernel_entries=len(kernel_touched),
    )
