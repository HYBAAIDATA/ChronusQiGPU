"""Metallic-family search restructure: exact experiments and closed form."""

import pytest

from chronus.quantum import StateVector
from chronus.quantum.metallic_search import (
    METALLIC_COEFFICIENTS,
    QSqrt2,
    algebraic_search,
    exact_search,
    generalized_iterate,
    one_shot_phases,
    phase_iterate,
    phase_matched_sweep,
)


def test_qsqrt2_exact_arithmetic_and_sign():
    half = QSqrt2(0, 1, 1)  # sqrt(2)/2 = 1/sqrt(2)
    # (sqrt(2)/2)^2 computed manually: (b^2 * 2, 2ab, 2e) = (2, 0, 2) = 2/4 = 1/2
    product = QSqrt2(half.b * half.b * 2, 2 * half.a * half.b, half.e * 2)
    assert product.a == 2 and product.b == 0 and product.e == 2
    assert QSqrt2(1, 0, 1).add(QSqrt2(0, 1, 2)).sign() > 0
    assert QSqrt2(-3, 2, 0).sign() < 0  # -3 + 2*sqrt2 < 0
    assert QSqrt2(3, -2, 0).sign() > 0  # 3 - 2*sqrt2 > 0
    with pytest.raises(ValueError):
        QSqrt2(1, 0, 0).scale(__import__("fractions").Fraction(1, 3))


def test_generalized_iterate_c2_reproduces_grover():
    for n in (1, 2, 3):
        state = StateVector(n)
        for q in range(n):
            state.apply("H", q)
        generalized_iterate(state, 0, METALLIC_COEFFICIENTS["grover"])
        reference = StateVector(n)
        for q in range(n):
            reference.apply("H", q)
        from chronus.quantum import grover_iterate
        grover_iterate(reference, 0)
        assert state.equivalent(reference)


def test_algebraic_grover_reproduces_sqrt_n_iteration_counts():
    counts = [algebraic_search("grover", n)[0] for n in range(2, 13)]
    assert counts == [1, 2, 3, 4, 6, 8, 12, 17, 25, 35, 50]


def test_overshoot_is_detected_not_hidden():
    # Metallic reflection coefficients c > 2 overshoot: no clean first peak
    # within the iteration cap, which the harness reports honestly.
    peak, history = algebraic_search("silver", 6, max_iterations=400)
    assert len(history) == 401  # never settled


def test_one_shot_phases_match_exhaustive_sweep():
    for n in (1, 2, 3):
        sweep = phase_matched_sweep(n, (1 << n) - 1, max_iterations=4)
        assert sweep["minimal_iterations"] == 1
        assert set(one_shot_phases(n)) == set(sweep["phase_pairs_at_minimum"])


def test_exact_search_converges_in_one_iteration_for_all_marks():
    for n in (1, 2, 3, 4, 6, 8, 10):
        for marked in range(1 << n) if n <= 4 else (0, 5, (1 << n) - 1):
            state = exact_search(n, marked)
            assert state.amplitudes[marked] in (1, 256)
            assert all(a == 0 for i, a in enumerate(state.amplitudes) if i != marked)


def test_phase_iterate_validates_inputs():
    with pytest.raises(ValueError):
        phase_iterate(StateVector(1), 0, 257, 1)
    with pytest.raises(ValueError):
        phase_iterate(StateVector(1), 7, 1, 1)
    with pytest.raises(ValueError):
        one_shot_phases(0)
