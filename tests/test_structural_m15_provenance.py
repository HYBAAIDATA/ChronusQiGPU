"""Provenance tests for the M15 byte map over Z/256Z.

The map's matrix is M15 = ((219, 98), (98, 121)) and its derived inverse is
M15_INV = ((135, 98), (98, 37)) = -adj(M15): det = 16895 = -1 (mod 256), so
det^-1 = -1 and the inverse is exactly -adj.

Provenance claim: "M15 = M^15 in GL(2, Z/256)". Resolved by exhaustive
2-adic Hensel search (scripts/dev/m15_provenance.py): exactly 9 roots exist
in GL(2, Z/256); one witness is M = ((167, 226), (226, 197)). The circulant
witness proposed in review - M = ((15, 198), (198, 15)) - is refuted
structurally: every power of a circulant matrix ((a, b), (b, a)) remains
circulant ((x, y), (y, x)), and M15 is not circulant (219 != 121); its
15th power is ((219, 98), (98, 219)), differing from M15 only at [1][1].
"""
import pytest

from chronus.execution.structural import fold_pair, unfold_pair

M15 = ((219, 98), (98, 121))
M15_INV = ((135, 98), (98, 37))
WITNESS = ((167, 226), (226, 197))


def mul(a, b):
    return tuple(
        tuple(sum(a[i][k] * b[k][j] for k in range(2)) % 256 for j in range(2))
        for i in range(2)
    )


def mat_pow(base, exponent):
    result = ((1, 0), (0, 1))
    while exponent:
        if exponent & 1:
            result = mul(result, base)
        base = mul(base, base)
        exponent >>= 1
    return result


def test_matrix_matches_fold_pair_exhaustively():
    for first in range(256):
        for second in range(256):
            assert fold_pair(first, second) == (
                (M15[0][0] * first + M15[0][1] * second) % 256,
                (M15[1][0] * first + M15[1][1] * second) % 256,
            )


def test_determinant_is_minus_one():
    det = (M15[0][0] * M15[1][1] - M15[0][1] * M15[1][0]) % 256
    assert det == 255  # -1 mod 256: odd, so the pair map is a bijection


def test_inverse_is_derived_and_involutive():
    assert mul(M15, M15_INV) == ((1, 0), (0, 1))
    assert mul(M15_INV, M15) == ((1, 0), (0, 1))


def test_exhaustive_roundtrip():
    for first in range(256):
        for second in range(256):
            assert unfold_pair(*fold_pair(first, second)) == (first, second)


def test_m15_is_a_fifteenth_power():
    assert mat_pow(WITNESS, 15) == M15


def test_reviewed_circulant_witness_is_refuted():
    """The review-proposed witness fails at [1][1]: powers of a circulant
    matrix remain circulant, and M15 is not circulant."""
    witness = ((15, 198), (198, 15))
    power = mat_pow(witness, 15)
    assert power == ((219, 98), (98, 219))
    assert power != M15
