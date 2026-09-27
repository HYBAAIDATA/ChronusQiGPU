"""Lucas pool battery — exact arithmetic and kernel sanity.

Deterministic, no randomness, no heuristics.
"""

import numpy as np
import pytest

from lucas import core, cassini, trace, pool
from lucas import ladder
from lucas.bound import bound, paths

# Reference Lucas numbers L_0..L_20
LUCAS_REF = [
    2,
    1,
    3,
    4,
    7,
    11,
    18,
    29,
    47,
    76,
    123,
    199,
    322,
    521,
    843,
    1364,
    2207,
    3571,
    5778,
    9349,
    15127,
]
FIB_REF = [
    0,
    1,
    1,
    2,
    3,
    5,
    8,
    13,
    21,
    34,
    55,
    89,
    144,
    233,
    377,
    610,
    987,
    1597,
    2584,
    4181,
    6765,
]


def test_lucas_exact_0_20():
    for n, expected in enumerate(LUCAS_REF):
        assert core.lucas(n) == expected


def test_fibonacci_exact_0_20():
    for n, expected in enumerate(FIB_REF):
        assert core.fibonacci(n) == expected


def test_cassini_exact_0_20():
    for n in range(21):
        witness = cassini.verify(n)
        assert witness["valid"]
        assert witness["lhs"] == witness["rhs"]


def test_trace_q_matrix_lucas():
    for n in range(1, 21):
        w = trace.verify_lucas_trace(n)
        assert w["valid"]
        assert w["Q_power_trace"] == core.lucas(n)


def test_trace_verify_generic():
    Q = np.array([[1, 1], [1, 0]], dtype=object)
    for n in range(1, 21):
        assert trace.verify(Q, n)["valid"]


def test_ladder_full_ladder_and_climb():
    assert ladder.FULL_LADDER == [10, 12, 15, 18, 20]
    assert ladder.verify_ladder()["valid"]
    assert ladder.ladder_values() == [123, 322, 1364, 5778, 15127]
    assert ladder.climb(10) == 12
    assert ladder.climb(18) == 20
    assert ladder.climb(20) == 20


def test_bound_ge_paths_1_20():
    for n in range(1, 21):
        assert bound(n) >= paths(n)


def test_pool_rejects_duplicates():
    with pytest.raises(ValueError):
        pool.register("mining_kernel", lambda *a: {})


def test_pool_kernels_return_honest_dict():
    for name in pool.available():
        kernel = pool.get(name)
        if name == "trace_kernel":
            Q = np.array([[1, 1], [1, 0]], dtype=object)
            result = kernel(Q, 10)
        elif name == "path_kernel":
            result = kernel(np.array([[0, 1], [1, 0]], dtype=np.int64), 5)
        elif name == "gap_kernel":
            result = kernel(np.diag([0.0, 1.0, 3.0]), 10)
        elif name == "amplitude_kernel":
            result = kernel([1.0, 0.5], 5)
        elif name == "step_kernel":
            result = kernel({"states": 2}, 10)
        elif name == "mining_kernel":
            result = kernel(100, 10)
        elif name == "folded_kernel":
            result = kernel(b"\x00" * 64, 10)
        else:
            raise ValueError(name)
        assert isinstance(result, dict)
        assert "lucas_bound" in result
        assert "theorem_proven" in result
        assert result["theorem_proven"] is False


def test_pool_unknown_kernel_raises():
    with pytest.raises(KeyError):
        pool.get("nonexistent_kernel")
