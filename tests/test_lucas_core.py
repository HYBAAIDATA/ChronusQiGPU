from __future__ import annotations

import pytest
from scripts.lucas_core import (
    compose_add,
    compose_mul,
    compose_sub,
    exact_lucas_fibonacci,
    fast_doubling_call_count,
    lucas_period,
    lucas_rank,
    pisano_period,
)


def test_known_extended_values():
    expected = {0: 2, 1: 1, 7: 29, 10: 123, 12: 322, 15: 1364,
                18: 5778, 20: 15127, 31: 3010349, 50: 28143753123,
                76: 7639424778862807}
    for n, value in expected.items():
        assert exact_lucas_fibonacci(n)[0] == value


def test_fast_doubling_has_logarithmic_state_count():
    counts = [fast_doubling_call_count((1 << bits) - 1) for bits in range(1, 1025)]
    huge_index = (1 << 1024) - 1
    assert counts[-1] == huge_index.bit_length() + 1
    assert counts[-1] < huge_index


def test_compositions():
    for a in range(0, 20):
        for b in range(0, 20):
            assert compose_add(a, b) == exact_lucas_fibonacci(a + b)[0]
            assert compose_mul(a, b) == exact_lucas_fibonacci(a)[0] * exact_lucas_fibonacci(b)[0]
            if a >= b:
                assert compose_sub(a, b) == exact_lucas_fibonacci(a - b)[0]


def test_negative_rejected():
    with pytest.raises(ValueError):
        exact_lucas_fibonacci(-1)


def test_periodicity_and_rank_examples():
    assert pisano_period(10) == 60
    assert lucas_period(10) == 12
    assert pisano_period(7) == 16
    assert lucas_period(7) == 16
    assert lucas_rank(3) == 2
    assert lucas_rank(5) is None
