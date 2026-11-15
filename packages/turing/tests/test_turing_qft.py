import sys
from fractions import Fraction
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

from turing.algebra import CyclotomicField  # noqa: E402
from turing.algorithms import qft  # noqa: E402


def _vector(size, scale=1):
    field = CyclotomicField(size)
    values = []
    for k in range(size):
        values.append(field.zeta((3 * k + 1) % size) * Fraction(k % 3 - 1, k + 2) + Fraction(k * k % 5, 3))
    return qft.ScaledVector(scale, tuple(values))


def test_qft_is_exactly_unitary():
    for size in (1, 2, 3, 4, 5, 6, 8):
        assert qft.qft_is_unitary(size)
        scale, rows = qft.qft_matrix(size)
        assert scale == size
        broken = [list(row) for row in rows]
        if size > 1:
            broken[0][0] = broken[0][0] * 2
            assert not qft.is_unitary(scale, broken)


def test_inverse_qft_undoes_qft():
    for size in (1, 2, 3, 4, 5, 6, 8):
        for scale in (1, 3, 8):
            vector = _vector(size, scale)
            assert qft.inverse_qft(qft.qft(vector)) == vector
            assert qft.qft(qft.inverse_qft(vector)) == vector


def test_qft_preserves_the_norm_and_maps_basis_states_to_uniform_states():
    for size in (2, 3, 4, 6, 8):
        vector = _vector(size)
        assert qft.qft(vector).norm_squared() == vector.norm_squared()
        field = CyclotomicField(size)
        basis = qft.ScaledVector.from_values([1] + [0] * (size - 1), field)
        transformed = qft.qft(basis)
        assert all(transformed.probability(k) == Fraction(1, size) for k in range(size))


def test_qft_squared_is_the_index_reversal():
    for size in (3, 4, 5, 8):
        vector = _vector(size)
        twice = qft.qft(qft.qft(vector))
        expected = qft.ScaledVector(vector.scale, tuple(vector.values[-k % size] for k in range(size)))
        assert twice == expected


def test_scaled_vectors_are_canonical():
    field = CyclotomicField(4)
    assert qft.ScaledVector.from_values([2, 0], field, scale=4) == qft.ScaledVector.from_values([1, 0], field)
    assert qft.ScaledVector.from_values([3, 6], field, scale=18).scale == 2
    try:
        qft.ScaledVector(0, (field.one,))
    except ValueError:
        pass
    else:
        raise AssertionError("scale must be positive")
