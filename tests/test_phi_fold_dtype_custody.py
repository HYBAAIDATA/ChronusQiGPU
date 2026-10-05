"""dtype/complex custody for aethel folded state (Phase 2)."""

import numpy as np
import pytest

from aethel.phi_fold import (
    KernelBoundary,
    NumericFoldState,
    PhiFoldError,
    fold_result,
    phi_fold,
    phi_unfold,
    unfold_partial,
)
from aethel.phi_memory import MemoryTier, PhiMemoryHierarchy


@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.complex64, np.complex128])
def test_roundtrip_is_bit_exact_for_every_numeric_dtype(dtype):
    rng = np.random.default_rng(7)
    if np.issubdtype(dtype, np.complexfloating):
        data = rng.standard_normal((4, 8)).astype(dtype) + 1j * rng.standard_normal(
            (4, 8)
        ).astype(dtype)
    else:
        data = rng.standard_normal((4, 8)).astype(dtype)
    state = phi_fold(data, depth=3)
    restored = phi_unfold(state)
    assert restored.dtype == data.dtype
    assert np.array_equal(restored.view(np.uint8), data.view(np.uint8))
    assert state.dtype == data.dtype


def test_int_dtype_preserved():
    data = np.arange(64, dtype=np.int64).reshape(8, 8)
    state = phi_fold(data, depth=2)
    assert state.dtype == np.dtype(np.int64)
    assert np.array_equal(phi_unfold(state), data)


def test_partial_unfold_returns_original_dtype():
    data = np.arange(64, dtype=np.float32)
    state = phi_fold(data, depth=3)
    piece = unfold_partial(state, KernelBoundary(10, 20))
    assert piece.dtype == np.dtype(np.float32)
    np.testing.assert_array_equal(piece, data[10:30])


def test_content_hash_identifies_state():
    data = np.linspace(0, 1, 32)
    state = phi_fold(data, depth=2)
    assert state.content_hash
    assert state.verify_content_hash()
    same = phi_fold(data.copy(), depth=2)
    assert same.content_hash == state.content_hash


def test_tampered_segment_fails_content_verification():
    state = phi_fold(np.linspace(0, 1, 32), depth=2)
    tampered = NumericFoldState(
        retained=state.retained,
        complements=(state.complements[0] + 1.0, state.complements[1]),
        depth=state.depth,
        original_shape=state.original_shape,
        original_size=state.original_size,
        dtype=state.dtype,
        layout=state.layout,
        content_hash=state.content_hash,
    )
    assert not tampered.verify_content_hash()


def test_mixed_segment_dtypes_rejected():
    data = np.arange(32, dtype=np.float64)
    state = phi_fold(data, depth=2)
    bad = NumericFoldState(
        retained=state.retained,
        complements=(state.complements[0].astype(np.float32), state.complements[1]),
        depth=state.depth,
        original_shape=state.original_shape,
        original_size=state.original_size,
        dtype=state.dtype,
    )
    with pytest.raises(PhiFoldError, match="segment dtypes"):
        phi_unfold(bad)


def test_non_numeric_dtype_rejected_at_fold():
    with pytest.raises(PhiFoldError, match="numeric dtype"):
        phi_fold(np.array(["a", "b", "c", "d"]))
    with pytest.raises(PhiFoldError, match="numeric dtype"):
        phi_fold(np.array([object(), object()], dtype=object))


def test_fold_result_requires_matching_dtype():
    data = np.arange(32, dtype=np.float32)
    state = phi_fold(data, depth=2)
    with pytest.raises(PhiFoldError, match="dtype"):
        fold_result(
            np.arange(8, dtype=np.float64), KernelBoundary(0, 8), state
        )
    updated = fold_result(
        np.arange(8, dtype=np.float32) + 100.0, KernelBoundary(0, 8), state
    )
    assert updated.dtype == np.dtype(np.float32)
    np.testing.assert_array_equal(phi_unfold(updated)[:8], np.arange(8) + 100.0)


def test_memory_hierarchy_records_dtype_layout_and_content_identity():
    hierarchy = PhiMemoryHierarchy()
    data = (np.arange(16, dtype=np.float32) + 1j).astype(np.complex64)
    resident = hierarchy.store("weights", data, MemoryTier.L2)
    assert resident.dtype == np.dtype(np.complex64)
    assert resident.layout == "C"
    assert resident.content_hash
    assert resident.verify_integrity()
    report = hierarchy.get_memory_report()
    entry = report["residents"]["weights"]
    assert entry["dtype"] == "complex64"
    assert entry["layout"] == "C"
    assert entry["integrity_verified"] is True
    restored = hierarchy.read("weights")
    assert restored.dtype == np.dtype(np.complex64)
    assert np.array_equal(restored, data)


def test_tier_transition_preserves_dtype():
    hierarchy = PhiMemoryHierarchy()
    data = np.linspace(0, 1, 512).astype(np.float32)
    hierarchy.store("x", data, MemoryTier.HBM)
    hierarchy.promote("x", MemoryTier.REGISTER)
    assert hierarchy.read("x").dtype == np.dtype(np.float32)
    np.testing.assert_array_equal(hierarchy.read("x"), data)
