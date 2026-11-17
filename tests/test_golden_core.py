"""Canonical golden core (Layer 0): exact identities and agreement with the existing canonical owners."""

import decimal
import os
from fractions import Fraction

import pytest

from chronus.math import golden_core as g
from chronus.math.binet_lucas import fibonacci_fast, lucas_fast

pytestmark = pytest.mark.real


def test_fibonacci_and_lucas_match_the_canonical_engines():
    for n in range(0, 300):
        assert g.fibonacci(n) == fibonacci_fast(n)
        assert g.lucas(n) == lucas_fast(n)
    assert g.lucas(n) == g.fibonacci(n - 1) + g.fibonacci(n + 1)


@pytest.mark.parametrize("n", range(1, 60))
def test_negative_indices_follow_the_exact_identities(n):
    assert g.fibonacci(-n) == (-1) ** (n + 1) * g.fibonacci(n)
    assert g.lucas(-n) == (-1) ** n * g.lucas(n)
    # The recurrence F(k) + F(k+1) == F(k+2) holds across zero.
    assert g.fibonacci(-n) + g.fibonacci(-n + 1) == g.fibonacci(-n + 2)


def test_cassini_holds_for_negative_zero_and_large_indices():
    assert all(g.cassini_check(n) for n in list(range(-40, 41)) + [500, 1001])


def test_zeckendorf_round_trip_and_uniqueness():
    for n in list(range(0, 3000)) + [10 ** 30 + 7]:
        ks = g.zeckendorf_encode(n)
        assert g.zeckendorf_decode(ks) == n
        assert all(a - b >= 2 for a, b in zip(ks, ks[1:]))
        assert all(k >= 2 for k in ks)


def test_zeckendorf_rejects_invalid_input():
    with pytest.raises(ValueError):
        g.zeckendorf_encode(-1)
    with pytest.raises(ValueError):
        g.zeckendorf_decode([5, 4])  # consecutive
    with pytest.raises(ValueError):
        g.zeckendorf_decode([1])


@pytest.mark.parametrize("family", list(g.FAMILY_COEFFS))
def test_pisot_roots_are_certified_and_pisot(family):
    root = g.family_root(family, precision=40)
    coeffs = g.FAMILY_COEFFS[family]
    assert root.low < Fraction(root.value) < root.high
    assert root.width == Fraction(2, 10 ** 40)
    f_low = sum(c * root.low ** (len(coeffs) - 1 - i) for i, c in enumerate(coeffs))
    f_high = sum(c * root.high ** (len(coeffs) - 1 - i) for i, c in enumerate(coeffs))
    assert (f_low > 0) != (f_high > 0)
    assert root.low > 1
    assert g.family_pisot_modulus(family).high < 1


@pytest.mark.parametrize("family", ["plastic", "supergolden", "tribonacci"])
def test_cubic_conjugates_are_a_complex_pair(family):
    # Deflate by the dominant root: x^3 + a x^2 + b x + c = (x - r)(x^2 + p x + q).
    _, a, b, c = g.FAMILY_COEFFS[family]
    r = Fraction(g.family_root(family, 40).value)
    p = a + r
    q = b + r * p
    assert p * p - 4 * q < 0  # complex pair, so |mu|^2 = q = |c| / r
    assert abs(q - Fraction(abs(c)) / r) < Fraction(1, 10 ** 30)


@pytest.mark.parametrize("family", list(g.FAMILY_COEFFS))
def test_pisot_modulus_is_a_certified_enclosure(family):
    # |mu|^p * alpha == |c0| exactly (p = 1 for quadratics, 2 for cubics), so the certified bracket
    # of |mu| must satisfy low^p * alpha_low <= |c0| <= high^p * alpha_high.
    precision = 40
    m = g.family_pisot_modulus(family, precision)
    root = g.family_root(family, precision)
    power = 1 if len(g.FAMILY_COEFFS[family]) == 3 else 2
    c0 = abs(g.FAMILY_COEFFS[family][-1])
    assert m.low < m.high < 1
    assert m.width < Fraction(1, 10 ** 12)
    assert m.low ** power * root.low <= c0 <= m.high ** power * root.high
    assert m.low <= Fraction(m.value) <= m.high


def test_known_constants():
    golden = g.family_root("golden", 30).value
    assert str(golden).startswith("1.61803398874989484820458683436")
    assert str(g.family_root("silver", 20).value).startswith("2.4142135623730950488")


def test_root_finding_leaves_the_global_decimal_context_alone():
    before = decimal.getcontext().prec
    g.family_root("tribonacci", precision=120)
    g.family_pisot_modulus("plastic", precision=90)
    assert decimal.getcontext().prec == before


def test_fold_has_determinant_minus_one_and_inverts():
    (a, b), (c, d) = g.M15
    assert (a * d - b * c) % 256 == 255
    for size in (0, 1, 2, 3, 17, 256):
        raw = os.urandom(size)
        folded = g.t_phi_fold(raw)
        assert len(folded) == size + (size & 1)
        assert g.t_phi_unfold(folded, size) == raw


def test_fold_is_byte_identical_to_the_folded_state_tables():
    pytest.importorskip("numpy")
    from chronus.tensor.folded_state import ExactFoldState, _pair_luts

    forward, _ = _pair_luts()
    pairs = bytes(v for i in range(65536) for v in (i >> 8, i & 255))
    ours = g.t_phi_fold(pairs)
    # Compare per pair through integers to stay independent of numpy byte order.
    mine = [(ours[2 * i] << 8) | ours[2 * i + 1] for i in range(65536)]
    assert mine == [int(v) for v in forward]
    for raw in (b"x", b"HYBA", bytes(range(255))):
        assert g.t_phi_fold(raw) == ExactFoldState.from_bytes(raw).folded


def test_unfold_detects_a_wrong_length_or_altered_pad():
    folded = g.t_phi_fold(b"abc")
    with pytest.raises(ValueError):
        g.t_phi_unfold(folded, 1)
    tampered = bytearray(folded)
    tampered[-1] ^= 1
    with pytest.raises(ValueError):
        g.t_phi_unfold(bytes(tampered), 3)
