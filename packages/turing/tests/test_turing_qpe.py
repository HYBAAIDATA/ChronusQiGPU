import sys
from fractions import Fraction
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

from turing.algebra import CyclotomicField, multiplicative_order  # noqa: E402
from turing.algorithms import qpe  # noqa: E402


def test_dyadic_phases_are_recovered_with_probability_exactly_one():
    for t in range(1, 9):
        size = 1 << t
        outcomes = range(size) if t <= 5 else (0, 1, size // 3, size // 2 + 1, size - 1)
        for y in outcomes:
            recovery = qpe.recover_phase(Fraction(y, size), t)
            assert recovery.outcome == y
            assert recovery.phase == Fraction(y, size)
            assert recovery.probability == 1


def test_dyadic_distribution_is_a_point_mass():
    for t in range(1, 7):
        size = 1 << t
        for y0 in (0, size - 1, size // 2):
            estimate = qpe.phase_estimation(Fraction(y0, size), t)
            for y, probability in enumerate(estimate.probabilities):
                assert probability == (1 if y == y0 else 0)


def test_non_dyadic_phases_give_exact_distributions_summing_to_one():
    cases = ((Fraction(1, 3), 3), (Fraction(2, 5), 4), (Fraction(1, 6), 2), (Fraction(1, 8), 2), (Fraction(5, 7), 3))
    for phase, t in cases:
        estimate = qpe.phase_estimation(phase, t)
        assert estimate.total_probability() == 1
        for probability in estimate.probabilities:
            assert probability.is_real()
        try:
            qpe.recover_phase(phase, t)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{phase} is not a multiple of 1/2^{t}")
    irrational = qpe.phase_estimation(Fraction(1, 8), 2).probabilities
    assert any(not p.is_rational() for p in irrational)
    field = CyclotomicField(8)
    root_two = field.zeta(1) - field.zeta(3)
    # |sum_{j<4} zeta_8^j|^2 = 4 + 3*sqrt(2) + 0 - sqrt(2) = 4 + 2*sqrt(2); divide by T^2 = 16.
    assert irrational[0] == (2 + root_two) / 8


def test_generator_three_has_order_256_modulo_257():
    assert multiplicative_order(3, 257) == 256
    assert multiplicative_order(2, 257) == 16
    try:
        qpe.multiply_by_generator_eigenphases(257, 2)
    except ValueError:
        pass
    else:
        raise AssertionError("2 does not generate the multiplicative group of F_257")


def test_multiply_by_three_on_f257_recovers_every_eigenphase_exactly():
    estimation = qpe.estimate_multiply_by_generator(257, 3)
    assert estimation.precision_qubits == 8
    assert estimation.generator_order == 256
    assert len(estimation.recoveries) == 256
    for k, recovery in enumerate(estimation.recoveries):
        assert recovery.outcome == k
        assert recovery.phase == Fraction(k, 256)
        assert recovery.probability == 1
    for k in (0, 1, 77, 128, 255):
        probabilities = qpe.phase_estimation(Fraction(k, 256), 8).probabilities
        assert probabilities[k] == 1
        assert sum(1 for p in probabilities if not p.is_zero()) == 1


def test_eigenvectors_checked_with_field_elements_for_p_17():
    p, g = 17, 3
    m = p - 1
    field = CyclotomicField(m)
    log = {}
    value = 1
    for e in range(m):
        log[value] = e
        value = value * g % p
    for k in range(m):
        vector = {x: field.zeta(-k * log[x]) for x in range(1, p)}
        image = {g * x % p: vector[x] for x in range(1, p)}
        for x in range(1, p):
            assert image[x] == field.zeta(k) * vector[x]
    assert qpe.multiply_by_generator_eigenphases(p, g) == tuple(Fraction(k, m) for k in range(m))


def test_non_fermat_prime_is_rejected_for_exact_recovery():
    assert len(qpe.multiply_by_generator_eigenphases(13, 2)) == 12
    try:
        qpe.estimate_multiply_by_generator(13, 2)
    except ValueError:
        pass
    else:
        raise AssertionError("eigenphases k/12 are not dyadic")
