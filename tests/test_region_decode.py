"""Arbitrary-region decode + measured dependency sets, both planes."""

import numpy as np
import pytest
from fractions import Fraction

from aethel.phi_fold import (
    KernelBoundary,
    PhiFoldError,
    phi_fold,
    region_flat_boundaries,
    unfold_region,
)
from python_backend.core_modules.geodesic_tensor_engine import (
    KernelBoundary as ExactBoundary,
    fold_exact,
    unfold_region as unfold_region_exact,
    unfold_values_at,
)


def test_region_flat_boundaries_minimal_intervals():
    shape = (8, 8)
    # A sub-block rows 2:4 cols 1:5 → two contiguous runs of 4.
    boundaries, region_shape = region_flat_boundaries(
        shape, (slice(2, 4), slice(1, 5))
    )
    assert region_shape == (2, 4)
    assert boundaries == (KernelBoundary(17, 4), KernelBoundary(25, 4))
    # Full trailing axis → one contiguous run.
    boundaries, region_shape = region_flat_boundaries(shape, (slice(2, 4), slice(0, 8)))
    assert boundaries == (KernelBoundary(16, 16),)
    # Single coordinate.
    boundaries, region_shape = region_flat_boundaries(shape, (3, 5))
    assert region_shape == (1, 1)
    assert boundaries == (KernelBoundary(29, 1),)


def test_region_flat_boundaries_fail_closed():
    with pytest.raises(PhiFoldError, match="unit-step"):
        region_flat_boundaries((8, 8), (slice(None), slice(0, 8, 2)))
    with pytest.raises(PhiFoldError, match="outside"):
        region_flat_boundaries((8, 8), (slice(0, 9), slice(None)))
    with pytest.raises(PhiFoldError, match="rank-2"):
        region_flat_boundaries((8, 8), (slice(None),))
    with pytest.raises(PhiFoldError, match="empty"):
        region_flat_boundaries((8, 8), (slice(4, 4), slice(None)))


def test_unfold_region_matches_full_unfold():
    data = np.arange(64, dtype=np.float64).reshape(8, 8)
    state = phi_fold(data, depth=2)
    region, stats = unfold_region(state, (slice(2, 5), slice(1, 6)))
    np.testing.assert_array_equal(region, data[2:5, 1:6])
    assert stats.requested_values == 15
    assert stats.boundaries  # decomposed, not whole-tensor
    assert stats.source_values_read == 15  # partition fold: cone == request
    assert stats.decoded_bytes == 15 * 8
    # Whole-tensor region merges to one boundary.
    _, stats_full = unfold_region(state, (slice(None), slice(None)))
    assert stats_full.source_values_read == 64
    assert len(stats_full.boundaries) == 1


def test_unfold_region_preserves_dtype_and_is_bounded():
    data = np.arange(64, dtype=np.float32).reshape(4, 16)
    state = phi_fold(data, depth=3)
    region, stats = unfold_region(state, (slice(1, 3), slice(4, 8)))
    assert region.dtype == np.float32
    np.testing.assert_array_equal(region, data[1:3, 4:8])
    assert stats.source_values_read < stats.full_length


def test_exact_unfold_values_at_exposes_cone():
    # 16 values, depth 2 — PULVINI cones are non-trivial.
    values = tuple(Fraction(i) for i in range(16))
    state = fold_exact(values, depth=2, shape=(16,))
    result, stats = unfold_values_at(state, [0, 15])
    assert result == (Fraction(0), Fraction(15))
    assert stats.cone_indices
    assert all(0 <= i < 16 for i in stats.cone_indices)
    # Cone is a real dependency set: decoding [0,15] reads a strict
    # subset-or-equal of the source positions; at depth 2 corners spread.
    assert stats.source_values_read == len(stats.cone_indices)


def test_exact_unfold_region_shaped():
    values = tuple(Fraction(i) for i in range(16))
    state = fold_exact(values, depth=1, shape=(4, 4))
    got, stats, region_shape = unfold_region_exact(
        state, (slice(1, 3), slice(0, 2))
    )
    assert region_shape == (2, 2)
    assert got == (Fraction(4), Fraction(5), Fraction(8), Fraction(9))
    assert stats.requested_values == 4


def test_exact_unfold_region_fail_closed():
    state = fold_exact(tuple(range(16)), depth=1, shape=(4, 4))
    with pytest.raises(ValueError, match="unit-step"):
        unfold_region_exact(state, (slice(0, 4, 2), slice(None)))
    with pytest.raises(ValueError, match="rank"):
        unfold_region_exact(state, (slice(None),))


def test_exact_partial_stats_carry_cone():
    state = fold_exact(tuple(range(8)), depth=2, shape=(8,))
    from python_backend.core_modules.geodesic_tensor_engine import (
        unfold_partial_with_stats,
    )

    _, stats = unfold_partial_with_stats(state, ExactBoundary(0, 2))
    assert stats.dependency_cone == stats.cone_indices
    assert stats.cone_indices  # populated, not empty default
