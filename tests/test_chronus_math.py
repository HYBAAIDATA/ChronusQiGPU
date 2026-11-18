"""Tests for exact mathematical field engines: binet_lucas and f257_search."""

import pytest
from fractions import Fraction
from chronus.math.binet_lucas import QSqrt5, unfold, lucas_binet, lucas_recurrence
from chronus.math.f257_search import f257_phases, f257_phases_multi

pytestmark = pytest.mark.real


def test_qsqrt5_exact_ring_arithmetic():
    x = QSqrt5(Fraction(2), Fraction(3))   # 2 + 3*sqrt(5)
    y = QSqrt5(Fraction(2), Fraction(-3))  # 2 - 3*sqrt(5)

    prod = x * y  # (4 - 45) = -41
    assert prod.a == Fraction(-41)
    assert prod.b == Fraction(0)
    assert prod.is_rational()

    # Division / inversion
    inv_x = ~x
    identity = x * inv_x
    assert identity.a == Fraction(1)
    assert identity.b == Fraction(0)


def test_lucas_binet_exact_matches_recurrence():
    for n in range(15):
        binet_val = lucas_binet(n)
        rec_val = lucas_recurrence(n)
        assert binet_val.is_rational()
        assert unfold(binet_val) == rec_val


def test_f257_single_and_multi_mark_phases():
    u = 30  # 1/sqrt(2) mod 257
    N = 16  # 4 qubits

    # Single mark
    alpha, mu, beta = f257_phases(u=u, N=N, M=1)
    assert 0 <= alpha < 257
    assert 0 <= mu < 257
    assert 0 <= beta < 257

    # Multi mark (M = 3) via multi-mark closed form
    alpha_m, mu_m, beta_m = f257_phases_multi(u=u, N=N, M=3)
    assert 0 <= alpha_m < 257
    assert 0 <= mu_m < 257
    assert 0 <= beta_m < 257

    # Verify single-mark raises NotImplementedError on M >= 2 per Module 1.1 spec
    with pytest.raises(NotImplementedError):
        f257_phases(u=u, N=N, M=3)
