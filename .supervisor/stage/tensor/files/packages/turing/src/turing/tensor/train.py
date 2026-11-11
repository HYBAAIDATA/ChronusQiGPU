"""Exact tensor trains (matrix product states) built by CR factorisations.

A :class:`TensorTrain` of order d stores cores G_k of shape (r_(k-1), n_k, r_k)
with boundary ranks r_0 = r_d = 1. The represented tensor is

    T[i_1, ..., i_d] = G_1[:, i_1, :] @ G_2[:, i_2, :] @ ... @ G_d[:, i_d, :].

:meth:`TensorTrain.from_dense` factorises a dense tensor by sequential exact
CR factorisations. Every bond rank it produces is the exact rank of the
corresponding unfolding of the tensor, which is the smallest possible rank of
any tensor-train representation. :meth:`TensorTrain.compress` brings any
tensor train to those minimal ranks with two exact sweeps. Nothing is
truncated: every operation is lossless, so ``to_dense`` after ``compress``
returns the original tensor exactly.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from .dense import ExactTensor, _size
from .field import Field
from .linalg import _cr_rows, _matmul_rows

__all__ = ["TensorTrain"]


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _slices(core: ExactTensor) -> list[list[list[Any]]]:
    """Core (r_left, n, r_right) as n matrices of r_left rows and r_right columns."""
    left, modes, right = core.shape
    entries = core.entries
    return [[list(entries[(a * modes + s) * right:(a * modes + s + 1) * right]) for a in range(left)]
            for s in range(modes)]


def _core_from_slices(field: Field, slices: Sequence[Sequence[Sequence[Any]]], left: int, right: int) -> ExactTensor:
    modes = len(slices)
    flat = tuple(slices[s][a][b] for a in range(left) for s in range(modes) for b in range(right))
    return ExactTensor._raw(field, (left, modes, right), flat)


def _left_unfolding(core: ExactTensor) -> list[list[Any]]:
    """Rows indexed by (a, s), columns by b."""
    left, modes, right = core.shape
    entries = core.entries
    return [list(entries[row * right:(row + 1) * right]) for row in range(left * modes)]


def _right_unfolding(core: ExactTensor) -> list[list[Any]]:
    """Rows indexed by a, columns by (s, b)."""
    left, modes, right = core.shape
    width = modes * right
    entries = core.entries
    return [list(entries[a * width:(a + 1) * width]) for a in range(left)]


def _flat(rows: Iterable[Sequence[Any]]) -> tuple[Any, ...]:
    return tuple(value for row in rows for value in row)


class TensorTrain:
    """An exact tensor train: cores of shape (r_(k-1), n_k, r_k) with r_0 = r_d = 1."""

    __slots__ = ("_field", "_cores")

    def __init__(self, cores: Sequence[ExactTensor]) -> None:
        if isinstance(cores, ExactTensor) or not isinstance(cores, Iterable):
            raise TypeError("cores must be a sequence of order-3 ExactTensor objects")
        values = tuple(cores)
        if not values:
            raise ValueError("a tensor train needs at least one core")
        field = None
        previous = 1
        for k, core in enumerate(values):
            if not isinstance(core, ExactTensor):
                raise TypeError(f"core {k} is not an ExactTensor")
            if core.order != 3:
                raise ValueError(f"core {k} must have shape (r_left, n, r_right), got {core.shape!r}")
            if field is None:
                field = core.field
            elif core.field != field:
                raise ValueError(f"core {k} lives in {core.field!r}, core 0 in {field!r}")
            if core.shape[0] != previous:
                raise ValueError(f"core {k} has left rank {core.shape[0]}, expected {previous}")
            previous = core.shape[2]
        if values[0].shape[0] != 1 or previous != 1:
            raise ValueError("the boundary ranks of a tensor train must be 1")
        self._field = field
        self._cores = values

    @classmethod
    def _raw(cls, field: Field, cores: tuple[ExactTensor, ...]) -> "TensorTrain":
        train = object.__new__(cls)
        train._field = field
        train._cores = cores
        return train

    # -- construction ----------------------------------------------------------------------

    @classmethod
    def from_dense(cls, tensor: ExactTensor) -> "TensorTrain":
        """Exact tensor train of a dense tensor by sequential CR factorisations.

        Bond k is the exact rank of the unfolding that groups axes 1..k against
        axes k+1..d, which is the minimal tensor-train rank.
        """
        if not isinstance(tensor, ExactTensor):
            raise TypeError("from_dense needs an ExactTensor")
        dims = tensor.shape
        if not dims:
            raise ValueError("a tensor train needs a tensor with at least one axis")
        field = tensor.field
        cores = []
        remaining: Sequence[Any] = tensor.entries
        left = 1
        for k in range(len(dims) - 1):
            height = left * dims[k]
            width = _size(dims[k + 1:])
            rows = [remaining[i * width:(i + 1) * width] for i in range(height)]
            c_rows, r_rows, pivots = _cr_rows(field, rows, width)
            r = len(pivots)
            cores.append(ExactTensor._raw(field, (left, dims[k], r), _flat(c_rows)))
            remaining = _flat(r_rows)
            left = r
        cores.append(ExactTensor._raw(field, (left, dims[-1], 1), tuple(remaining)))
        return cls._raw(field, tuple(cores))

    # -- accessors ---------------------------------------------------------------------------

    @property
    def field(self) -> Field:
        return self._field

    @property
    def cores(self) -> tuple[ExactTensor, ...]:
        return self._cores

    @property
    def order(self) -> int:
        """Number of cores (axes of the represented tensor)."""
        return len(self._cores)

    @property
    def shape(self) -> tuple[int, ...]:
        """Shape (n_1, ..., n_d) of the represented tensor."""
        return tuple(core.shape[1] for core in self._cores)

    @property
    def ranks(self) -> tuple[int, ...]:
        """Bond ranks (r_0, r_1, ..., r_d), including the boundary ranks r_0 = r_d = 1."""
        return (1,) + tuple(core.shape[2] for core in self._cores)

    def storage(self) -> int:
        """Number of stored field elements (the sum of the core sizes)."""
        return sum(core.size for core in self._cores)

    # -- evaluation -----------------------------------------------------------------------------

    def entry(self, index: Sequence[int]) -> Any:
        """One entry, by multiplying core slices left to right: O(d r^2) field operations."""
        if _is_int(index):
            index = (index,)
        values = tuple(index)
        if len(values) != len(self._cores):
            raise IndexError(f"index {values!r} does not address a tensor of order {len(self._cores)}")
        field = self._field
        vector = [field.one]
        for k, (i, core) in enumerate(zip(values, self._cores)):
            left, modes, right = core.shape
            if not _is_int(i) or not 0 <= i < modes:
                raise IndexError(f"index {i!r} on axis {k} is outside 0 .. {modes - 1}")
            entries = core.entries
            out = [field.zero] * right
            for a in range(left):
                weight = vector[a]
                if field.is_zero(weight):
                    continue
                base = (a * modes + i) * right
                for b in range(right):
                    value = entries[base + b]
                    if not field.is_zero(value):
                        out[b] = field.add(out[b], field.mul(weight, value))
            vector = out
        return vector[0]

    def to_dense(self) -> ExactTensor:
        """The represented tensor (refused above MAX_DENSE_ENTRIES entries)."""
        field = self._field
        _size(self.shape)
        rows = 1
        current: list[Any] = [field.one]
        rank = 1
        for core in self._cores:
            _, modes, right = core.shape
            _size((rows, modes, right))
            product = _matmul_rows(field, [current[i * rank:(i + 1) * rank] for i in range(rows)],
                                   _right_unfolding(core), rank, modes * right)
            current = [value for row in product for value in row]
            rows *= modes
            rank = right
        return ExactTensor._raw(field, self.shape, tuple(current))

    def inner(self, other: "TensorTrain") -> Any:
        """<self, other> = sum conj(self[i]) * other[i], by transfer matrices: O(d n r^3)."""
        if not isinstance(other, TensorTrain):
            raise TypeError("inner needs another TensorTrain")
        if other._field != self._field:
            raise ValueError(f"tensor trains live in different fields: {self._field!r} and {other._field!r}")
        if other.shape != self.shape:
            raise ValueError(f"shapes {self.shape!r} and {other.shape!r} differ")
        field = self._field
        environment = [[field.one]]
        for mine, theirs in zip(self._cores, other._cores):
            left_mine, modes, right_mine = mine.shape
            left_theirs, _, right_theirs = theirs.shape
            update = [[field.zero] * right_theirs for _ in range(right_mine)]
            mine_slices = _slices(mine)
            theirs_slices = _slices(theirs)
            for s in range(modes):
                carried = _matmul_rows(field, environment, theirs_slices[s], left_theirs, right_theirs)
                conjugate = [[field.conj(mine_slices[s][a][b]) for a in range(left_mine)] for b in range(right_mine)]
                term = _matmul_rows(field, conjugate, carried, left_mine, right_theirs)
                for b in range(right_mine):
                    row = update[b]
                    for c in range(right_theirs):
                        if not field.is_zero(term[b][c]):
                            row[c] = field.add(row[c], term[b][c])
            environment = update
        return environment[0][0]

    def norm_squared(self) -> Any:
        """sum |T[i]|^2 exactly (an element of the real subfield)."""
        return self.inner(self)

    # -- exact algebra ----------------------------------------------------------------------------

    def scale(self, factor: object) -> "TensorTrain":
        """factor * T (the first core is scaled)."""
        first = self._cores[0].scale(factor)
        return TensorTrain._raw(self._field, (first,) + self._cores[1:])

    def __neg__(self) -> "TensorTrain":
        return TensorTrain._raw(self._field, (-self._cores[0],) + self._cores[1:])

    def __add__(self, other: "TensorTrain") -> "TensorTrain":
        """Exact sum with block cores; the ranks add (use :meth:`compress` to make them minimal)."""
        if not isinstance(other, TensorTrain):
            return NotImplemented
        if other._field != self._field:
            raise ValueError(f"tensor trains live in different fields: {self._field!r} and {other._field!r}")
        if other.shape != self.shape:
            raise ValueError(f"shapes {self.shape!r} and {other.shape!r} differ")
        field = self._field
        if len(self._cores) == 1:
            return TensorTrain._raw(field, (self._cores[0] + other._cores[0],))
        cores = []
        last = len(self._cores) - 1
        for k, (mine, theirs) in enumerate(zip(self._cores, other._cores)):
            a_left, modes, a_right = mine.shape
            b_left, _, b_right = theirs.shape
            a_slices = _slices(mine)
            b_slices = _slices(theirs)
            left = 1 if k == 0 else a_left + b_left
            right = 1 if k == last else a_right + b_right
            slices = []
            for s in range(modes):
                block = [[field.zero] * right for _ in range(left)]
                row_shift = 0 if k == 0 else a_left
                column_shift = 0 if k == last else a_right
                for a in range(a_left):
                    for b in range(a_right):
                        block[a][b] = a_slices[s][a][b]
                for a in range(b_left):
                    for b in range(b_right):
                        block[row_shift + a][column_shift + b] = b_slices[s][a][b]
                slices.append(block)
            cores.append(_core_from_slices(field, slices, left, right))
        return TensorTrain._raw(field, tuple(cores))

    def __sub__(self, other: "TensorTrain") -> "TensorTrain":
        if not isinstance(other, TensorTrain):
            return NotImplemented
        return self + (-other)

    def compress(self) -> "TensorTrain":
        """Exact rank reduction to the minimal ranks; the represented tensor is unchanged.

        A left-to-right sweep factorises each left unfolding as C @ R, keeps C
        (full column rank) and pushes R into the next core; a right-to-left
        sweep factorises each right unfolding as C @ R, keeps R (full row rank)
        and pushes C into the previous core. Afterwards every left interface has
        full column rank and every right interface full row rank, so each bond
        equals the exact rank of the corresponding unfolding. No entry is
        rounded and nothing is discarded except exact linear dependence.
        """
        field = self._field
        cores = list(self._cores)
        last = len(cores) - 1
        for k in range(last):
            left, modes, right = cores[k].shape
            c_rows, r_rows, pivots = _cr_rows(field, _left_unfolding(cores[k]), right)
            r = len(pivots)
            cores[k] = ExactTensor._raw(field, (left, modes, r), _flat(c_rows))
            _, next_modes, next_right = cores[k + 1].shape
            pushed = _matmul_rows(field, r_rows, _right_unfolding(cores[k + 1]), right, next_modes * next_right)
            cores[k + 1] = ExactTensor._raw(field, (r, next_modes, next_right), _flat(pushed))
        for k in range(last, 0, -1):
            left, modes, right = cores[k].shape
            c_rows, r_rows, pivots = _cr_rows(field, _right_unfolding(cores[k]), modes * right)
            r = len(pivots)
            cores[k] = ExactTensor._raw(field, (r, modes, right), _flat(r_rows))
            previous_left, previous_modes, _ = cores[k - 1].shape
            pulled = _matmul_rows(field, _left_unfolding(cores[k - 1]), c_rows, left, r)
            cores[k - 1] = ExactTensor._raw(field, (previous_left, previous_modes, r), _flat(pulled))
        return TensorTrain._raw(field, tuple(cores))

    def __repr__(self) -> str:
        return f"TensorTrain({self._field!r}, shape={self.shape!r}, ranks={self.ranks!r})"
