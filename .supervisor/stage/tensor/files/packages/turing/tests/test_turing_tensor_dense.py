import sys
from fractions import Fraction
from itertools import product
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

from turing.tensor import MAX_DENSE_ENTRIES, QQ, ExactTensor, cyclotomic  # noqa: E402

F8 = cyclotomic(8)
ONE, TWO = 1, 2


def _raises(exception, function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except exception as error:
        return error
    raise AssertionError(f"{function!r} did not raise {exception.__name__}")


def _value(field, *index):
    """A deterministic exact entry depending on the index (rational or cyclotomic)."""
    weight = sum((k + 3) * i for k, i in enumerate(index))
    rational = Fraction(weight % 7 - 3, 1 + weight % 3)
    if field is QQ:
        return rational
    return field.add(field.coerce(rational), field.mul(field.coerce(weight % 2), field.zeta(weight % 8)))


def _tensor(field, shape):
    return ExactTensor.from_function(field, shape, lambda *index: _value(field, *index))


def _naive_contract(a, b, axes_a, axes_b):
    """Reference tensordot by explicit index loops."""
    free_a = [k for k in range(a.order) if k not in axes_a]
    free_b = [k for k in range(b.order) if k not in axes_b]
    field = a.field
    out = {}
    for left in product(*(range(a.shape[k]) for k in free_a)):
        for right in product(*(range(b.shape[k]) for k in free_b)):
            total = field.zero
            for inner in product(*(range(a.shape[k]) for k in axes_a)):
                index_a = [0] * a.order
                index_b = [0] * b.order
                for k, i in zip(free_a, left):
                    index_a[k] = i
                for k, i in zip(axes_a, inner):
                    index_a[k] = i
                for k, i in zip(free_b, right):
                    index_b[k] = i
                for k, i in zip(axes_b, inner):
                    index_b[k] = i
                total = field.add(total, field.mul(a[tuple(index_a)], b[tuple(index_b)]))
            out[left + right] = total
    return out


def test_nested_round_trip_and_row_major_layout():
    nested = [[[1, 2], [3, 4], [5, 6]], [[7, 8], [9, 10], [11, Fraction(1, 2)]]]
    tensor = ExactTensor.from_nested(QQ, nested)
    assert tensor.shape == (2, 3, 2) and tensor.size == 12 and tensor.order == 3
    assert tensor.entries[:4] == (1, 2, 3, 4)
    assert tensor[1, 2, 1] == Fraction(1, 2)
    assert tensor.to_nested() == nested
    assert ExactTensor.from_nested(QQ, 5).shape == ()
    assert ExactTensor.from_nested(QQ, [[], []]).shape == (2, 0)
    assert ExactTensor.zeros(QQ, (2, 0, 3)).size == 0


def test_reshape_keeps_row_major_entries():
    tensor = _tensor(QQ, (2, 3, 4))
    flat = tensor.reshape((24,))
    assert flat.entries == tensor.entries
    matrix = tensor.reshape((6, 4))
    for i, j, k in product(range(2), range(3), range(4)):
        assert matrix[i * 3 + j, k] == tensor[i, j, k]
    assert matrix.reshape((2, 3, 4)) == tensor
    _raises(ValueError, tensor.reshape, (5, 5))


def test_transpose_matches_index_permutation():
    for field in (QQ, F8):
        tensor = _tensor(field, (2, 3, 4))
        for permutation in ((0, 1, 2), (2, 0, 1), (1, 2, 0), (2, 1, 0), (0, 2, 1)):
            moved = tensor.transpose(permutation)
            assert moved.shape == tuple(tensor.shape[p] for p in permutation)
            for index in product(*(range(d) for d in tensor.shape)):
                assert field.eq(moved[tuple(index[p] for p in permutation)], tensor[index])
            inverse = tuple(permutation.index(axis) for axis in range(3))
            assert moved.transpose(inverse) == tensor
        assert tensor.transpose() == tensor.transpose((2, 1, 0))
    _raises(ValueError, _tensor(QQ, (2, 2)).transpose, (0, 0))
    _raises(ValueError, _tensor(QQ, (2, 2)).transpose, (0,))


def test_contraction_matches_explicit_sums():
    cases = [
        ((2, 3), (3, 4), (1,), (0,)),
        ((2, 3, 4), (4, 3, 2), (1, 2), (1, 0)),
        ((3, 2, 2), (2, 3), (0,), (1,)),
        ((2, 2), (2, 2), (), ()),
        ((2, 3), (2, 3), (0, 1), (0, 1)),
        ((2, 0, 3), (0, 2), (1,), (0,)),
    ]
    for field in (QQ, F8):
        for shape_a, shape_b, axes_a, axes_b in cases:
            a = _tensor(field, shape_a)
            b = _tensor(field, shape_b).conj()
            result = a.contract(b, axes_a, axes_b)
            expected = _naive_contract(a, b, axes_a, axes_b)
            assert result.size == len(expected)
            for index, value in expected.items():
                assert field.eq(result[index], value)
    a = _tensor(QQ, (2, 3))
    assert a.matmul(ExactTensor.identity(QQ, 3)) == a
    _raises(ValueError, a.contract, _tensor(QQ, (2, 3)), (1,), (0,))
    _raises(ValueError, a.contract, _tensor(QQ, (3,)), (1, 0), (0,))
    _raises(ValueError, a.contract, _tensor(F8, (3,)), (1,), (0,))


def test_outer_conjugate_norm_and_algebra():
    a = _tensor(F8, (2, 2))
    b = _tensor(F8, (3,))
    outer = a.outer(b)
    assert outer.shape == (2, 2, 3)
    for i, j, k in product(range(2), range(2), range(3)):
        assert F8.eq(outer[i, j, k], F8.mul(a[i, j], b[k]))
    total = F8.zero
    for value in a.entries:
        total = F8.add(total, F8.mul(value, F8.conj(value)))
    assert F8.eq(a.norm_squared(), total)
    assert F8.eq(F8.conj(total), total)
    assert a.conj().conj() == a
    assert F8.eq(a.conj()[1, 0], F8.conj(a[1, 0]))
    assert (a + a) == a.scale(2)
    assert (a - a).is_zero()
    assert (-a) == a.scale(-1)
    assert outer.norm_squared() == F8.mul(a.norm_squared(), b.norm_squared())


def test_equality_and_hash():
    a = _tensor(QQ, (2, 3))
    b = ExactTensor(QQ, (2, 3), list(a.entries))
    assert a == b and hash(a) == hash(b)
    assert a != a.reshape((3, 2))
    c = ExactTensor(QQ, (2, 3), [a.entries[0] + 1] + list(a.entries[1:]))
    assert a != c
    assert ExactTensor.zeros(QQ, (2,)) != ExactTensor.zeros(F8, (2,))


def test_validation_and_dense_bound():
    runtime_float = ONE / TWO
    _raises(TypeError, ExactTensor, QQ, (2,), [1, runtime_float])
    _raises(ValueError, ExactTensor, QQ, (2, 2), [1, 2, 3])
    _raises(ValueError, ExactTensor, QQ, (2, 2), [1, 2, 3, 4, 5])
    _raises(ValueError, ExactTensor, QQ, (2, -1), [])
    _raises(ValueError, ExactTensor, QQ, (2, True), [1, 2])
    _raises(TypeError, ExactTensor, object(), (1,), [1])
    _raises(ValueError, ExactTensor.from_nested, QQ, [[1, 2], [3]])
    _raises(ValueError, ExactTensor.from_nested, QQ, [[1, 2], [3, [4]]])
    _raises(IndexError, _tensor(QQ, (2, 2)).__getitem__, (2, 0))
    assert MAX_DENSE_ENTRIES == 1 << 20
    error = _raises(ValueError, ExactTensor.zeros, QQ, (2,) * 21)
    assert "MAX_DENSE_ENTRIES" in str(error)
    _raises(ValueError, ExactTensor.zeros, QQ, (1 << 10, 1 << 10, 2))
    assert ExactTensor.zeros(QQ, (1 << 20, 0, 1 << 20)).size == 0
    big = ExactTensor.zeros(QQ, (1 << 10, 1 << 10))
    _raises(ValueError, big.outer, ExactTensor.zeros(QQ, (2,)))
