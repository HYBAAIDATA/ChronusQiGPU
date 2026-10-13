"""Tests for the Lucas scale model and coprimality guard."""
from chronus.lucas.scale_model import (
    DECLARED_RUNGS,
    capacity_bits,
    scale_ratio,
    stride_is_bijective,
    assert_stride_bijective,
)


def test_scale_ratio_near_one():
    for n in DECLARED_RUNGS:
        r = scale_ratio(n)
        assert abs(r - 1.0) < 1e-4


def test_coprimality():
    assert stride_is_bijective(8)
    assert stride_is_bijective(13)
    assert not stride_is_bijective(9)   # shares factor 3
    assert not stride_is_bijective(12)


def test_assert_raises():
    try:
        assert_stride_bijective(9)
        assert False, "should have raised"
    except ValueError:
        pass
