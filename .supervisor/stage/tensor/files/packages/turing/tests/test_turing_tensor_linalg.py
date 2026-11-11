import sys
from fractions import Fraction
from itertools import combinations, permutations
from pathlib import Path

_SRC = str(Path(__file__).resolve().parents[1] / "src")
if sys.path[:1] != [_SRC]:
    sys.path.insert(0, _SRC)

from turing.tensor import QQ, ExactTensor, TensorTrain, cr_factorization, cyclotomic, matmul, rank, rref  # noqa: E402

F8 = cyclotomic(8)
F5 = cyclotomic(5)


def _raises(exception, function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except exception as error:
        return error
    raise AssertionError(f"{function!r} did not raise {exception.__name__}")


def _entry(field, state):
    numerator = (state >> 8) % 9 - 4
    denominator = 1 + (state >> 13) % 3
    value = field.coerce(Fraction(numerator, denominator))
    if field is not QQ:
        value = field.add(value, field.mul(field.coerce((state >> 17) % 3 - 1), field.zeta((state >> 20) % 8)))
    return value


def _matrices(field, seed):
    """Deterministic matrices: full rank, rank deficient (products of thin factors), zero and empty."""
    state = seed
    found = []

    def draw(rows, columns):
        nonlocal state
        entries = []
        for _ in range(rows * columns):
            state = (state * 1103515245 + 12345) % (1 << 31)
            entries.append(_entry(field, state))
        return ExactTensor(field, (rows, columns), entries)

    for rows, columns in ((1, 1), (1, 4), (4, 1), (2, 2), (3, 3), (3, 5), (5, 3), (4, 4)):
        found.append(draw(rows, columns))
    for rows, inner, columns in ((4, 1, 4), (5, 2, 4), (4, 2, 6), (6, 3, 5), (3, 2, 3), (5, 4, 5)):
        found.append(matmul(draw(rows, inner), draw(inner, columns)))
    found.append(ExactTensor.zeros(field, (3, 4)))
    found.append(ExactTensor.zeros(field, (0, 3)))
    found.append(ExactTensor.zeros(field, (3, 0)))
    found.append(ExactTensor.identity(field, 4))
    duplicated = draw(2, 4)
    rows = [duplicated.entries[:4], duplicated.entries[4:], duplicated.entries[:4],
            tuple(field.add(a, b) for a, b in zip(duplicated.entries[:4], duplicated.entries[4:]))]
    found.append(ExactTensor(field, (4, 4), [value for row in rows for value in row]))
    return found


def _independent_rank(matrix):
    """Rank by column-oriented elimination with the last nonzero entry as pivot (independent code path)."""
    field = matrix.field
    rows, columns = matrix.shape
    work = [[matrix[i, j] for i in range(rows)] for j in range(columns)]
    found = 0
    for r in range(rows):
        pivot = None
        for c in range(found, columns):
            if not field.is_zero(work[c][r]):
                pivot = c
        if pivot is None:
            continue
        work[found], work[pivot] = work[pivot], work[found]
        base = work[found]
        for c in range(columns):
            if c != found and not field.is_zero(work[c][r]):
                ratio = field.div(work[c][r], base[r])
                work[c] = [field.sub(x, field.mul(ratio, y)) for x, y in zip(work[c], base)]
        found += 1
    return found


def _determinant(field, rows):
    """Leibniz determinant for tiny matrices."""
    size = len(rows)
    total = field.zero
    for perm in permutations(range(size)):
        inversions = sum(1 for i in range(size) for j in range(i + 1, size) if perm[i] > perm[j])
        term = field.one
        for i, p in enumerate(perm):
            term = field.mul(term, rows[i][p])
        total = field.sub(total, term) if inversions % 2 else field.add(total, term)
    return total


def _minor_rank(matrix):
    field = matrix.field
    rows, columns = matrix.shape
    best = 0
    for size in range(1, min(rows, columns) + 1):
        for chosen_rows in combinations(range(rows), size):
            for chosen_columns in combinations(range(columns), size):
                block = [[matrix[i, j] for j in chosen_columns] for i in chosen_rows]
                if not field.is_zero(_determinant(field, block)):
                    best = size
                    break
            if best == size:
                break
        if best < size:
            break
    return best


def _assert_is_rref(reduced, pivots, rank_value):
    field = reduced.field
    rows, columns = reduced.shape
    assert len(pivots) == rank_value
    assert list(pivots) == sorted(pivots)
    for i in range(rows):
        row = [reduced[i, j] for j in range(columns)]
        if i >= rank_value:
            assert all(field.is_zero(value) for value in row)
            continue
        p = pivots[i]
        assert all(field.is_zero(value) for value in row[:p])
        assert field.eq(row[p], field.one)
        for other in range(rows):
            if other != i:
                assert field.is_zero(reduced[other, p])


def _check_cr(matrix):
    field = matrix.field
    factors = cr_factorization(matrix)
    rows, columns = matrix.shape
    assert factors.C.shape == (rows, factors.rank)
    assert factors.R.shape == (factors.rank, columns)
    assert factors.product() == matrix
    assert matmul(factors.C, factors.R) == matrix
    for k, p in enumerate(factors.pivots):
        for i in range(rows):
            assert field.eq(factors.C[i, k], matrix[i, p])
    reduced, pivots = rref(matrix)
    assert pivots == factors.pivots
    _assert_is_rref(reduced, pivots, factors.rank)
    for i in range(factors.rank):
        for j in range(columns):
            assert field.eq(factors.R[i, j], reduced[i, j])
    assert rank(matrix) == factors.rank == _independent_rank(matrix)
    assert rank(matrix.transpose()) == factors.rank
    return factors.rank


def test_cr_is_exact_over_the_rationals():
    ranks = [_check_cr(matrix) for matrix in _matrices(QQ, 3)]
    assert 0 in ranks and 1 in ranks and 4 in ranks
    assert ranks[8:14] == [1, 2, 2, 3, 2, 4]


def test_cr_is_exact_over_q_zeta_8_and_q_zeta_5():
    ranks = [_check_cr(matrix) for matrix in _matrices(F8, 5)]
    assert ranks[8:14] == [1, 2, 2, 3, 2, 4]
    for matrix in _matrices(F5, 9)[:10]:
        _check_cr(matrix.reshape(matrix.shape))


def test_rank_matches_nonzero_minors():
    for field, seed in ((QQ, 21), (F8, 23)):
        for matrix in _matrices(field, seed):
            if matrix.shape[0] * matrix.shape[1] <= 16 or max(matrix.shape) <= 4:
                assert rank(matrix) == _minor_rank(matrix)


def test_rref_is_invariant_under_invertible_row_operations():
    for field, seed in ((QQ, 31), (F8, 37)):
        for matrix in _matrices(field, seed)[:14]:
            rows = matrix.shape[0]
            mixer = ExactTensor.from_function(
                field, (rows, rows),
                lambda i, j: field.from_int(1 if i == j else (i + 2 * j) % 3 if j > i else 0))
            shuffled = matmul(mixer, matrix)
            assert rref(shuffled) == rref(matrix)


def test_known_factorisation():
    matrix = ExactTensor.from_nested(QQ, [[1, 2, 3, 4], [2, 4, 6, 8], [1, 0, 1, 0]])
    factors = cr_factorization(matrix)
    assert factors.pivots == (0, 1)
    assert factors.C == ExactTensor.from_nested(QQ, [[1, 2], [2, 4], [1, 0]])
    assert factors.R == ExactTensor.from_nested(QQ, [[1, 0, 1, 0], [0, 1, 1, 2]])
    _raises(ValueError, rank, ExactTensor.zeros(QQ, (2, 2, 2)))
    _raises(TypeError, rank, [[1, 2], [3, 4]])


class PrimeField:
    """GF(p) with plain int elements; every operation reduces modulo p.

    Python's int operators do not reduce, so routines that bypassed the field
    protocol would produce wrong (unreduced) entries and fail these checks.
    """

    def __init__(self, p):
        self.p = p
        self.zero = 0
        self.one = 1

    def from_int(self, value):
        return value % self.p

    def coerce(self, value):
        if isinstance(value, Fraction):
            return value.numerator * pow(value.denominator, -1, self.p) % self.p
        if isinstance(value, int) and not isinstance(value, bool):
            return value % self.p
        raise TypeError("GF(p) elements are ints")

    def add(self, a, b):
        return (a + b) % self.p

    def sub(self, a, b):
        return (a - b) % self.p

    def neg(self, a):
        return -a % self.p

    def mul(self, a, b):
        return a * b % self.p

    def div(self, a, b):
        if b % self.p == 0:
            raise ZeroDivisionError("division by zero in GF(p)")
        return a * pow(b, -1, self.p) % self.p

    def is_zero(self, a):
        return a % self.p == 0

    def eq(self, a, b):
        return (a - b) % self.p == 0

    def conj(self, a):
        return a


def test_every_routine_uses_only_the_field_protocol():
    field = PrimeField(7)
    matrix = ExactTensor.from_function(field, (4, 5), lambda i, j: (3 * i * j + i + 5 * j) % 7)
    factors = cr_factorization(matrix)
    assert factors.product() == matrix
    assert all(0 <= value < 7 for value in factors.R.entries + factors.C.entries)
    assert rank(matrix) == _independent_rank(matrix) == _minor_rank(matrix)
    tensor = ExactTensor.from_function(field, (2, 3, 2, 2), lambda a, b, c, d: (a * b + 3 * c * d + a + 6 * d) % 7)
    train = TensorTrain.from_dense(tensor)
    assert train.to_dense() == tensor
    assert all(0 <= value < 7 for core in train.cores for value in core.entries)
    assert (train + train).compress().ranks == train.ranks
