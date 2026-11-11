import sys
from fractions import Fraction
from itertools import product
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

from turing.tensor import QQ, ExactTensor, TensorTrain, cyclotomic, rank  # noqa: E402

F8 = cyclotomic(8)
SHAPES = ((1,), (5,), (2, 2), (2, 3), (3, 2), (1, 4), (4, 1), (1, 1, 1), (2, 2, 2), (2, 3, 4), (3, 1, 2),
          (4, 2, 3), (2, 2, 2, 2), (3, 3, 3), (2, 1, 3, 2), (2, 2, 2, 2, 2), (3, 2, 2, 3), (2, 3, 2, 3, 2))


def _raises(exception, function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except exception as error:
        return error
    raise AssertionError(f"{function!r} did not raise {exception.__name__}")


def _element(field, state):
    value = field.coerce(Fraction((state >> 9) % 9 - 4, 1 + (state >> 14) % 3))
    if field is not QQ:
        value = field.add(value, field.mul(field.coerce((state >> 18) % 3 - 1), field.zeta((state >> 21) % 8)))
    return value


def _generic(field, shape, seed):
    state = seed

    def entry(*index):
        nonlocal state
        state = (state * 1103515245 + 12345) % (1 << 31)
        return _element(field, state)

    return ExactTensor.from_function(field, shape, entry)


def _low_rank(field, shape, terms, seed):
    """A sum of ``terms`` outer products of vectors: every unfolding rank is at most ``terms``."""
    total = ExactTensor.zeros(field, shape)
    for t in range(terms):
        piece = None
        for k, dim in enumerate(shape):
            vector = _generic(field, (dim,), seed + 97 * t + 13 * k)
            piece = vector if piece is None else piece.outer(vector)
        total = total + piece
    return total


def _cases(field):
    found = []
    for k, shape in enumerate(SHAPES):
        found.append(_generic(field, shape, 101 + k))
        found.append(_low_rank(field, shape, 1 + k % 3, 211 + k))
        found.append(ExactTensor.zeros(field, shape))
    sliced = _generic(field, (3, 2, 3), 5)
    entries = list(sliced.entries)
    for index in range(6, 12):
        entries[index] = field.zero
    found.append(ExactTensor(field, (3, 2, 3), entries))
    return found


def _unfolding_ranks(tensor):
    dims = tensor.shape
    ranks = [1]
    for k in range(1, len(dims)):
        rows = 1
        for dim in dims[:k]:
            rows *= dim
        ranks.append(rank(tensor.reshape((rows, tensor.size // rows if rows else 0))))
    ranks.append(1)
    return tuple(ranks)


def test_round_trip_is_exact_for_many_shapes():
    for field in (QQ, F8):
        for tensor in _cases(field):
            train = TensorTrain.from_dense(tensor)
            assert train.shape == tensor.shape
            assert train.to_dense() == tensor


def test_bond_ranks_equal_unfolding_ranks():
    seen = set()
    for field in (QQ, F8):
        for tensor in _cases(field):
            train = TensorTrain.from_dense(tensor)
            assert train.ranks == _unfolding_ranks(tensor)
            seen.update(train.ranks)
    assert {0, 1, 2, 3, 4} <= seen


def test_entries_inner_products_and_norms():
    for field in (QQ, F8):
        cases = _cases(field)
        for left, right in zip(cases[0::3], cases[1::3]):
            a = TensorTrain.from_dense(left)
            b = TensorTrain.from_dense(right)
            for index in product(*(range(d) for d in left.shape)):
                assert field.eq(a.entry(index), left[index])
            expected = field.zero
            for x, y in zip(left.entries, right.entries):
                expected = field.add(expected, field.mul(field.conj(x), y))
            assert field.eq(a.inner(b), expected)
            assert field.eq(b.inner(a), field.conj(expected))
            assert field.eq(a.norm_squared(), left.norm_squared())


def test_compress_is_lossless_and_minimal():
    for field in (QQ, F8):
        cases = _cases(field)
        for first, second in zip(cases[0::3], cases[1::3]):
            a = TensorTrain.from_dense(first)
            b = TensorTrain.from_dense(second)
            doubled = a + a
            assert doubled.ranks == tuple(r if k in (0, len(a.ranks) - 1) else 2 * r for k, r in enumerate(a.ranks))
            compressed = doubled.compress()
            assert compressed.to_dense() == first.scale(2)
            assert compressed.ranks == a.ranks
            difference = (a - a).compress()
            assert difference.to_dense() == ExactTensor.zeros(field, first.shape)
            assert difference.ranks == (1,) + (0,) * (len(first.shape) - 1) + (1,)
            mixed = (a + b.scale(3) - a.scale(Fraction(1, 2))).compress()
            target = first.scale(Fraction(1, 2)) + second.scale(3)
            assert mixed.to_dense() == target
            assert mixed.ranks == _unfolding_ranks(target)
            assert mixed.compress().ranks == mixed.ranks


def test_compress_reduces_redundant_cores():
    state = 77
    for field in (QQ, F8):
        for shape, ranks in (((2, 2, 2, 2), (1, 3, 5, 3, 1)), ((3, 2, 3), (1, 4, 4, 1)), ((2, 3), (1, 5, 1))):
            cores = []
            for k, dim in enumerate(shape):
                entries = []
                for _ in range(ranks[k] * dim * ranks[k + 1]):
                    state = (state * 1103515245 + 12345) % (1 << 31)
                    entries.append(_element(field, state))
                cores.append(ExactTensor(field, (ranks[k], dim, ranks[k + 1]), entries))
            train = TensorTrain(cores)
            dense = train.to_dense()
            compressed = train.compress()
            assert compressed.to_dense() == dense
            assert compressed.ranks == _unfolding_ranks(dense)
            assert all(r <= q for r, q in zip(compressed.ranks, ranks))
            assert compressed.storage() < train.storage()


def test_validation():
    good = ExactTensor.zeros(QQ, (1, 2, 1))
    _raises(ValueError, TensorTrain, [])
    _raises(ValueError, TensorTrain, [ExactTensor.zeros(QQ, (2, 2, 1))])
    _raises(ValueError, TensorTrain, [ExactTensor.zeros(QQ, (1, 2, 2)), ExactTensor.zeros(QQ, (3, 2, 1))])
    _raises(ValueError, TensorTrain, [good, ExactTensor.zeros(F8, (1, 2, 1))])
    _raises(ValueError, TensorTrain, [ExactTensor.zeros(QQ, (1, 2))])
    _raises(TypeError, TensorTrain, good)
    _raises(ValueError, TensorTrain.from_dense, ExactTensor.from_nested(QQ, 3))
    train = TensorTrain([good, good])
    _raises(IndexError, train.entry, (0, 2))
    _raises(IndexError, train.entry, (0,))
    _raises(ValueError, train.inner, TensorTrain([good]))
    wide = TensorTrain([ExactTensor.zeros(QQ, (1, 2, 1))] * 21)
    error = _raises(ValueError, wide.to_dense)
    assert "MAX_DENSE_ENTRIES" in str(error)
    assert wide.entry((1,) * 21) == 0
