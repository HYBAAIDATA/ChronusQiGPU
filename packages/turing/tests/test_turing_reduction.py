import sys
from fractions import Fraction
from math import isqrt
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

from turing.algebra import (  # noqa: E402
    CyclotomicField,
    CyclotomicResidueMap,
    cyclotomic_polynomial,
    f257_residue_map,
    inverse_mod,
    multiplicative_order,
    pairwise_difference_counts,
)
from turing.algorithms import qft, qpe, shor  # noqa: E402

P = 257


def _power(base, exponent, modulus):
    result = 1
    for _ in range(exponent):
        result = result * base % modulus
    return result


def _samples():
    field = CyclotomicField(256)
    return [
        field.one,
        field.zeta(1),
        field.zeta(77) + Fraction(5, 7),
        field.element([Fraction((k * k + 3) % 11 - 5, k % 6 + 1) for k in range(128)]),
        field.element([Fraction(1, 3) if k % 5 == 0 else Fraction(0) for k in range(128)]),
        field.zeta(200) * Fraction(-4, 9) + field.zeta(3),
    ]


def test_phi_256_vanishes_at_3_modulo_257():
    value = 0
    for coefficient in reversed(cyclotomic_polynomial(256)):
        value = (value * 3 + coefficient) % P
    assert value == 0
    assert _power(3, 128, P) == P - 1
    roots = [r for r in range(P) if (_power(r, 128, P) + 1) % P == 0]
    assert len(roots) == 128
    assert sorted(roots) == sorted(_power(3, k, P) for k in range(1, 256, 2))


def test_orders_modulo_257():
    assert multiplicative_order(3, P) == 256
    assert _power(3, 8, P) == 136 and multiplicative_order(136, P) == 32
    assert _power(3, 16, P) == 249 == P - 8 and multiplicative_order(249, P) == 16
    assert multiplicative_order(2, P) == 16
    assert inverse_mod(3, P) == 86


def test_reduction_is_a_ring_homomorphism():
    checksum = f257_residue_map()
    assert checksum.root == 3 and checksum.prime == P
    field = CyclotomicField(256)
    assert checksum.reduce(field.one) == 1
    assert checksum.reduce(field.zeta(1)) == 3
    samples = _samples()
    for a in samples:
        assert checksum.reduce(-a) == (-checksum.reduce(a)) % P
        for b in samples:
            assert checksum.reduce(a + b) == (checksum.reduce(a) + checksum.reduce(b)) % P
            assert checksum.reduce(a * b) == checksum.reduce(a) * checksum.reduce(b) % P


def test_conjugation_corresponds_to_the_inverse_root():
    checksum = f257_residue_map()
    conjugate = checksum.conjugate_map()
    assert conjugate.root == 86
    for a in _samples():
        assert checksum.reduce(a.conjugate()) == conjugate.reduce(a)


def test_subfields_reduce_through_the_lift():
    checksum = f257_residue_map()
    assert checksum.image_of_zeta(32) == 136
    assert checksum.image_of_zeta(16) == 249
    assert checksum.reduce(CyclotomicField(32).zeta(1)) == 136
    assert checksum.reduce(CyclotomicField(16).zeta(1)) == 249
    assert checksum.reduce(Fraction(1, 4)) == inverse_mod(4, P)
    two_map = CyclotomicResidueMap(16, P, 2)
    assert two_map.reduce(CyclotomicField(16).zeta(1)) == 2


def test_residues_are_checksums_not_amplitudes():
    checksum = f257_residue_map()
    field = CyclotomicField(256)
    a = field.zeta(5) + Fraction(1, 2)
    b = a + 257
    assert a != b
    assert checksum.reduce(a) == checksum.reduce(b)


def test_invalid_reductions_fail_clearly():
    checksum = f257_residue_map()
    for bad in (CyclotomicField(256).from_rational(Fraction(1, 257)), CyclotomicField(3).zeta(1)):
        try:
            checksum.reduce(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("reduction must refuse this element")
    for n, prime, root in ((256, P, 2), (256, 255, 3), (8, P, 3)):
        try:
            CyclotomicResidueMap(n, prime, root)
        except ValueError:
            pass
        else:
            raise AssertionError(f"zeta_{n} -> {root} mod {prime} is not a homomorphism")


def test_qft_checksum_in_f257():
    checksum = f257_residue_map()
    conjugate = checksum.conjugate_map()
    for size in (1, 2, 4, 8, 16):
        scale, rows = qft.qft_matrix(size)
        residues = [[checksum.reduce(entry) for entry in row] for row in rows]
        conjugates = [[conjugate.reduce(entry) for entry in row] for row in rows]
        for j in range(size):
            for l in range(size):
                total = sum(residues[j][k] * conjugates[l][k] for k in range(size)) % P
                assert total == (scale % P if j == l else 0)
    field = CyclotomicField(8)
    vector = qft.ScaledVector.from_values([1, field.zeta(3), 0, Fraction(-2, 3), 5, field.zeta(1), 7, 0], field)
    transformed = qft.qft(vector)
    _, rows = qft.qft_matrix(8)
    inputs = [checksum.reduce(v) for v in vector.values]
    # The canonical form moved the square factor of D * Q into the stored values.
    factor = isqrt(vector.scale * 8 // transformed.scale)
    assert factor * factor * transformed.scale == vector.scale * 8
    for j, value in enumerate(transformed.values):
        expected = sum(checksum.reduce(rows[j][k]) * inputs[k] for k in range(8)) % P
        assert checksum.reduce(value * factor) == expected


def test_shor_distribution_checksum():
    checksum = f257_residue_map()
    modulus, base, t = 13, 2, 8
    size = 1 << t
    probabilities = shor.order_distribution(modulus, base, t)
    assert any(not p.is_rational() for p in probabilities)
    classes = {}
    for x in range(size):
        classes.setdefault(shor.modexp(base, x, modulus), []).append(x)
    profile = {}
    for members in classes.values():
        for d, count in pairwise_difference_counts(members, size).items():
            profile[d] = profile.get(d, 0) + count
    inverse_q2 = inverse_mod(size * size % P, P)
    total = 0
    for y, probability in enumerate(probabilities):
        residue = checksum.reduce(probability)
        direct = sum(count * _power(3, d * y % size, P) for d, count in profile.items()) * inverse_q2 % P
        assert residue == direct
        total += residue
    assert total % P == 1


def test_qpe_distribution_checksum():
    checksum = f257_residue_map()
    t = 4
    size = 1 << t
    phase = Fraction(1, 256)
    estimate = qpe.phase_estimation(phase, t)
    assert estimate.field.n == 256
    inverse_t2 = inverse_mod(size * size, P)
    total = 0
    for y, probability in enumerate(estimate.probabilities):
        step = (phase.numerator * (256 // phase.denominator) - y * (256 // size)) % 256
        direct = size
        for d in range(1, size):
            direct += (size - d) * (_power(3, d * step % 256, P) + _power(3, -d * step % 256, P))
        assert checksum.reduce(probability) == direct * inverse_t2 % P
        total += checksum.reduce(probability)
    assert total % P == 1
