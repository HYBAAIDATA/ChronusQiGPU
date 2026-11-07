"""Metallic means family: exact Z[sigma_m] arithmetic tests."""

import json
from fractions import Fraction

import pytest

from chronus.backends.lattice import phi_power
from chronus.backends.metallic import MetallicElement, metallic_power, metallic_sequence
from chronus.execution import ExecutionRouter


def test_m1_reproduces_golden_ratio_engine():
    for order in (0, 1, 2, 10, 90, 92):
        golden = phi_power(order)
        metallic = metallic_power(1, order)
        assert (metallic.a, metallic.b) == (golden.a, golden.b)
        assert metallic.norm() == golden.norm()
    assert metallic_sequence(1, 90) == 6440026026380244498  # L_90


def test_silver_ratio_matches_pell_arithmetic():
    # sigma_2 = 1 + sqrt(2); sigma_2^3 = 7 + 5*sqrt(2) = 2 + 5*sigma_2.
    cube = metallic_power(2, 3)
    assert (cube.a, cube.b) == (2, 5)
    assert cube.norm() == Fraction(-1)     # N(sigma_2) = -1, so N(sigma_2^3) = -1
    # Trace sequence for m=2: companion Pell numbers 2, 2, 6, 14, 34, ...
    assert [metallic_sequence(2, n) for n in range(5)] == [2, 2, 6, 14, 34]


def test_bronze_ratio_trace_sequence():
    # sigma_3 = (3 + sqrt(13)) / 2; T_n = 3*T_{n-1} + T_{n-2}: 2, 3, 11, 36, ...
    assert [metallic_sequence(3, n) for n in range(5)] == [2, 3, 11, 36, 119]


def test_trace_recurrence_holds_for_all_m():
    for m in (1, 2, 3, 7, 21):
        seq = [metallic_sequence(m, n) for n in range(8)]
        for n in range(2, 8):
            assert seq[n] == m * seq[n - 1] + seq[n - 2]


def test_norm_multiplicativity_and_conjugate_contraction():
    for m in (1, 2, 5):
        for n in (0, 1, 5, 17):
            power = metallic_power(m, n)
            assert power.norm() == Fraction((-1) ** n)  # N(sigma_m) = -1


def test_ring_operations_and_validation():
    x = MetallicElement(2, 3, 4)
    y = MetallicElement(2, -1, 2)
    product = x.multiply(y)
    # (3 + 4s)(-1 + 2s) = (3*-1 + 4*2) + (3*2 + 4*-1 + 2*4*2)*s = 5 + 18s
    assert (product.a, product.b) == (5, 18)
    assert product.trace() == 2 * 5 + 2 * 18
    with pytest.raises(ValueError):
        x.multiply(MetallicElement(1, 0, 1))  # different rings
    with pytest.raises(ValueError):
        MetallicElement(0, 1, 1)
    with pytest.raises(ValueError):
        metallic_power(1, -1)


def test_metallic_scale_workload_via_router():
    payload = json.dumps({"m": 2, "index": 3}).encode()
    receipt = ExecutionRouter().execute(payload, "METALLIC_SCALE")
    result = receipt.result
    assert result["family"] == "silver"
    assert result["a"] == "2" and result["b"] == "5"
    assert result["trace"] == "14"
    assert result["norm"] == "-1"
    with pytest.raises(ValueError, match="between 1 and 64"):
        ExecutionRouter().execute(json.dumps({"m": 0, "index": 1}).encode(), "METALLIC_SCALE")
    with pytest.raises(ValueError, match="exceeds"):
        ExecutionRouter().execute(
            json.dumps({"m": 1, "index": 100001}).encode(), "METALLIC_SCALE"
        )
