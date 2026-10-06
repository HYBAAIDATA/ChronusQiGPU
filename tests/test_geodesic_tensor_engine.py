from fractions import Fraction

import pytest

from chronus.mla1517.mining.geodesic_nonce_planner import GeodesicNoncePlanner
from python_backend.core_modules.geodesic_tensor_engine import (
    GeodesicTensorEngine,
    ManifoldType,
    MemoryTier,
    MetricTensor,
    fold_exact,
)


def test_recursive_exact_fold_roundtrip():
    values = tuple(Fraction(i, i + 1) for i in range(1, 17))
    state = fold_exact(values, depth=8)
    assert state.unfold() == values
    assert state.depth == 8


def test_tensor_fma_and_matmul_are_exact():
    engine = GeodesicTensorEngine()
    a = engine.fold([1, 2, 3, 4], depth=3)
    b = engine.fold([2, 3, 4, 5], depth=2)
    c = engine.fold([1, 1, 1, 1], depth=1)
    out = engine.core.fma(a, b, c)
    assert out.unfold() == (Fraction(3), Fraction(7), Fraction(13), Fraction(21))

    left = engine.fold([1, 2, 3, 4], depth=2, shape=(2, 2))
    right = engine.fold([5, 6, 7, 8], depth=2, shape=(2, 2))
    product = engine.core.matmul(left, right)
    assert product.unfold() == (
        Fraction(19), Fraction(22), Fraction(43), Fraction(50)
    )


def test_memory_tiers_refold_without_changing_values():
    engine = GeodesicTensorEngine()
    state = engine.fold([3, 1, 4, 1, 5, 9], depth=3)
    engine.memory.put("x", state)
    for tier in (MemoryTier.REGISTER, MemoryTier.SRAM, MemoryTier.L2, MemoryTier.HBM):
        moved = engine.memory.move("x", tier)
        assert moved.unfold() == tuple(Fraction(v) for v in [3, 1, 4, 1, 5, 9])


def test_geodesic_planner_preserves_candidate_membership_without_pulvini_dependency():
    planner = GeodesicNoncePlanner(
        MetricTensor(ManifoldType.HYPERBOLIC), fold_depth=5
    )
    window = [100, 50, 75, 125, 25]
    ordered = planner.order_window(window, anchor=80)
    assert sorted(ordered) == sorted(window)
    assert len(ordered) == len(window)
    assert planner.last_report["membership_verified"] is True
    assert planner.last_report["permutation_preserved"] is True
    assert planner.last_report["consensus_authority"] is False
    assert planner.last_report["proof_authority"] is False
    assert planner.last_report["pulvini_dependency"] is False
    assert planner.last_report["folding_used"] is False


def test_geodesic_planner_rejects_invalid_or_duplicate_nonces():
    planner = GeodesicNoncePlanner()
    with pytest.raises(ValueError):
        planner.order_window([1, 1])
    with pytest.raises(ValueError):
        planner.order_window([0, -1])
    with pytest.raises(ValueError):
        planner.order_window([0, 0x1_0000_0000])
    with pytest.raises(TypeError):
        planner.order_window([0, 1.5])


def test_float_tensor_input_is_rejected_by_exact_contract():
    with pytest.raises(TypeError):
        fold_exact([1.0, 2.0], depth=1)
