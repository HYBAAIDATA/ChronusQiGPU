"""Dense exact tensors: a shape and a flat row-major tuple of field elements.

:class:`ExactTensor` is the bounded dense building block of the exact tensor
layer. Every entry is an exact element of a :class:`~turing.tensor.field.Field`
and every operation (reshape, transpose, contraction, outer product,
conjugation, squared norm) is exact. A dense tensor larger than
:data:`MAX_DENSE_ENTRIES` entries is refused with ``ValueError`` before any
entry is allocated; the matrix-product classes in this package exist so that
large registers never need a dense tensor.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, Sequence

from .field import Field

__all__ = ["MAX_DENSE_ENTRIES", "ExactTensor"]

MAX_DENSE_ENTRIES = 1 << 20
"""Largest number of entries a dense :class:`ExactTensor` may hold (the same bound as
``turing.algorithms.oracles.MAX_DENSE_DOMAIN``)."""


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check_field(field: object) -> Field:
    if not isinstance(field, Field):
        raise TypeError(f"field must provide the turing.tensor.Field protocol, got {type(field).__name__}")
    return field


def _check_shape(shape: object) -> tuple[int, ...]:
    if isinstance(shape, (str, bytes)) or not isinstance(shape, Iterable):
        raise TypeError("shape must be a sequence of non-negative ints")
    dims = tuple(shape)
    for dim in dims:
        if not _is_int(dim) or dim < 0:
            raise ValueError(f"tensor dimensions must be non-negative ints, got {dims!r}")
    return dims


def _size(dims: tuple[int, ...]) -> int:
    """Number of entries of a tensor with these dimensions; refuses sizes above MAX_DENSE_ENTRIES."""
    size = 1
    for dim in dims:
        size *= dim
        if size > MAX_DENSE_ENTRIES:
            if 0 in dims:
                return 0
            raise ValueError(f"a dense tensor of shape {dims!r} exceeds MAX_DENSE_ENTRIES = {MAX_DENSE_ENTRIES}; "
                             f"use a TensorTrain or an ExactMPS instead")
    return size


def _strides(dims: tuple[int, ...]) -> tuple[int, ...]:
    strides = [1] * len(dims)
    for axis in range(len(dims) - 2, -1, -1):
        strides[axis] = strides[axis + 1] * dims[axis + 1]
    return tuple(strides)


def _check_axes(axes: object, order: int, name: str) -> tuple[int, ...]:
    if isinstance(axes, (str, bytes)) or not isinstance(axes, Iterable):
        raise TypeError(f"{name} must be a sequence of axis numbers")
    values = tuple(axes)
    for axis in values:
        if not _is_int(axis) or not 0 <= axis < order:
            raise ValueError(f"{name} {values!r} must contain axes 0 .. {order - 1}")
    if len(set(values)) != len(values):
        raise ValueError(f"{name} {values!r} repeats an axis")
    return values


def _matrix_product(field: Field, left: Sequence[Any], right: Sequence[Any], rows: int, inner: int,
                    columns: int) -> list[Any]:
    """Row-major (rows x inner) @ (inner x columns) with flat entry lists; zero entries are skipped."""
    zero = field.zero
    is_zero = field.is_zero
    add = field.add
    mul = field.mul
    out = [zero] * (rows * columns)
    for i in range(rows):
        base = i * inner
        target = i * columns
        for k in range(inner):
            a = left[base + k]
            if is_zero(a):
                continue
            offset = k * columns
            for j in range(columns):
                b = right[offset + j]
                if not is_zero(b):
                    out[target + j] = add(out[target + j], mul(a, b))
    return out


class ExactTensor:
    """An exact dense tensor: ``shape`` plus the flat row-major tuple ``entries``.

    The entry at index (i_0, ..., i_(d-1)) is ``entries[sum_k i_k * stride_k]``
    with row-major strides (the last axis varies fastest).
    """

    __slots__ = ("_field", "_shape", "_entries")

    def __init__(self, field: Field, shape: Sequence[int], entries: Iterable[object]) -> None:
        field = _check_field(field)
        dims = _check_shape(shape)
        size = _size(dims)
        if isinstance(entries, (str, bytes)) or not isinstance(entries, Iterable):
            raise TypeError("entries must be an iterable of field elements")
        values = []
        for value in entries:
            values.append(field.coerce(value))
            if len(values) > size:
                break
        if len(values) != size:
            raise ValueError(f"shape {dims!r} needs exactly {size} entries")
        self._field = field
        self._shape = dims
        self._entries = tuple(values)

    @classmethod
    def _raw(cls, field: Field, shape: tuple[int, ...], entries: tuple[Any, ...]) -> "ExactTensor":
        tensor = object.__new__(cls)
        tensor._field = field
        tensor._shape = shape
        tensor._entries = entries
        return tensor

    # -- constructors ----------------------------------------------------------------------

    @classmethod
    def zeros(cls, field: Field, shape: Sequence[int]) -> "ExactTensor":
        field = _check_field(field)
        dims = _check_shape(shape)
        return cls._raw(field, dims, (field.zero,) * _size(dims))

    @classmethod
    def from_nested(cls, field: Field, nested: object) -> "ExactTensor":
        """Build a tensor from nested sequences (lists or tuples); a bare scalar gives order 0."""
        field = _check_field(field)
        dims: list[int] = []
        probe = nested
        while isinstance(probe, (list, tuple)):
            dims.append(len(probe))
            if not probe:
                break
            probe = probe[0]
        shape = tuple(dims)
        _size(shape)
        flat: list[object] = []

        def walk(node: object, depth: int) -> None:
            if depth == len(shape):
                if isinstance(node, (list, tuple)):
                    raise ValueError("ragged nested sequence: too deep")
                flat.append(node)
                return
            if not isinstance(node, (list, tuple)) or len(node) != shape[depth]:
                raise ValueError(f"ragged nested sequence at depth {depth}; expected length {shape[depth]}")
            for child in node:
                walk(child, depth + 1)

        walk(nested, 0)
        return cls(field, shape, flat)

    @classmethod
    def from_function(cls, field: Field, shape: Sequence[int], function: Callable[..., object]) -> "ExactTensor":
        """Entry at index (i_0, ..., i_(d-1)) is ``function(i_0, ..., i_(d-1))``."""
        field = _check_field(field)
        dims = _check_shape(shape)
        _size(dims)
        indices: list[tuple[int, ...]] = [()]
        for dim in dims:
            indices = [index + (i,) for index in indices for i in range(dim)]
        return cls(field, dims, (function(*index) for index in indices))

    @classmethod
    def identity(cls, field: Field, dimension: int) -> "ExactTensor":
        """The dimension x dimension identity matrix."""
        field = _check_field(field)
        if not _is_int(dimension) or dimension < 0:
            raise ValueError("dimension must be a non-negative int")
        _size((dimension, dimension))
        entries = [field.zero] * (dimension * dimension)
        for i in range(dimension):
            entries[i * dimension + i] = field.one
        return cls._raw(field, (dimension, dimension), tuple(entries))

    # -- accessors --------------------------------------------------------------------------

    @property
    def field(self) -> Field:
        return self._field

    @property
    def shape(self) -> tuple[int, ...]:
        return self._shape

    @property
    def order(self) -> int:
        """Number of axes."""
        return len(self._shape)

    @property
    def size(self) -> int:
        """Number of entries (the product of the dimensions)."""
        return len(self._entries)

    @property
    def entries(self) -> tuple[Any, ...]:
        """The entries in row-major order."""
        return self._entries

    def _offset(self, index: Sequence[int]) -> int:
        if len(index) != len(self._shape):
            raise IndexError(f"index {tuple(index)!r} does not address a tensor of shape {self._shape!r}")
        offset = 0
        for i, dim in zip(index, self._shape):
            if not _is_int(i) or not 0 <= i < dim:
                raise IndexError(f"index {tuple(index)!r} is outside shape {self._shape!r}")
            offset = offset * dim + i
        return offset

    def __getitem__(self, index: object) -> Any:
        if _is_int(index):
            index = (index,)
        if not isinstance(index, tuple):
            raise TypeError("index a tensor with a tuple of ints")
        return self._entries[self._offset(index)]

    def to_nested(self) -> object:
        """The entries as nested lists (a bare element for order 0)."""
        if not self._shape:
            return self._entries[0]

        def build(axis: int, offset: int, stride: int) -> list:
            dim = self._shape[axis]
            step = stride // dim if dim else 0
            if axis == len(self._shape) - 1:
                return list(self._entries[offset:offset + dim])
            return [build(axis + 1, offset + i * step, step) for i in range(dim)]

        return build(0, 0, len(self._entries))

    # -- structural operations ----------------------------------------------------------------

    def reshape(self, shape: Sequence[int]) -> "ExactTensor":
        """The same row-major entries with a new shape of the same size."""
        dims = _check_shape(shape)
        if _size(dims) != len(self._entries):
            raise ValueError(f"cannot reshape {self._shape!r} ({len(self._entries)} entries) to {dims!r}")
        return ExactTensor._raw(self._field, dims, self._entries)

    def transpose(self, permutation: Sequence[int] | None = None) -> "ExactTensor":
        """Permute the axes: axis i of the result is axis ``permutation[i]`` of this tensor.

        Without a permutation the axes are reversed (numpy semantics).
        """
        order = len(self._shape)
        if permutation is None:
            perm = tuple(range(order - 1, -1, -1))
        else:
            perm = _check_axes(permutation, order, "permutation")
            if len(perm) != order:
                raise ValueError(f"permutation {perm!r} must list each of the {order} axes once")
        if perm == tuple(range(order)):
            return self
        old_strides = _strides(self._shape)
        new_shape = tuple(self._shape[p] for p in perm)
        moved = tuple(old_strides[p] for p in perm)
        offsets = [0]
        for dim, stride in zip(new_shape, moved):
            offsets = [base + i * stride for base in offsets for i in range(dim)]
        entries = self._entries
        return ExactTensor._raw(self._field, new_shape, tuple(entries[k] for k in offsets))

    def _require_same_field(self, other: object) -> "ExactTensor":
        if not isinstance(other, ExactTensor):
            raise TypeError("expected an ExactTensor")
        if other._field != self._field:
            raise ValueError(f"tensors live in different fields: {self._field!r} and {other._field!r}")
        return other

    def contract(self, other: "ExactTensor", axes_self: Sequence[int], axes_other: Sequence[int]) -> "ExactTensor":
        """Exact tensordot: sum over the paired axes; free axes of self, then free axes of other."""
        other = self._require_same_field(other)
        first = _check_axes(axes_self, len(self._shape), "axes_self")
        second = _check_axes(axes_other, len(other._shape), "axes_other")
        if len(first) != len(second):
            raise ValueError("axes_self and axes_other must pair the same number of axes")
        for a, b in zip(first, second):
            if self._shape[a] != other._shape[b]:
                raise ValueError(f"axis {a} of shape {self._shape!r} does not match axis {b} of {other._shape!r}")
        free_self = tuple(axis for axis in range(len(self._shape)) if axis not in first)
        free_other = tuple(axis for axis in range(len(other._shape)) if axis not in second)
        out_shape = tuple(self._shape[a] for a in free_self) + tuple(other._shape[b] for b in free_other)
        _size(out_shape)
        rows = _size(tuple(self._shape[a] for a in free_self))
        inner = _size(tuple(self._shape[a] for a in first))
        columns = _size(tuple(other._shape[b] for b in free_other))
        left = self.transpose(free_self + first)._entries
        right = other.transpose(second + free_other)._entries
        product = _matrix_product(self._field, left, right, rows, inner, columns)
        return ExactTensor._raw(self._field, out_shape, tuple(product))

    def matmul(self, other: "ExactTensor") -> "ExactTensor":
        """Matrix product of two order-2 tensors."""
        other = self._require_same_field(other)
        if len(self._shape) != 2 or len(other._shape) != 2:
            raise ValueError("matmul needs two matrices (order-2 tensors)")
        return self.contract(other, (1,), (0,))

    def outer(self, other: "ExactTensor") -> "ExactTensor":
        """Outer (tensor) product; the axes of self come first."""
        other = self._require_same_field(other)
        shape = self._shape + other._shape
        _size(shape)
        mul = self._field.mul
        return ExactTensor._raw(self._field, shape, tuple(mul(a, b) for a in self._entries for b in other._entries))

    def conj(self) -> "ExactTensor":
        """Entrywise complex conjugation."""
        conj = self._field.conj
        return ExactTensor._raw(self._field, self._shape, tuple(conj(a) for a in self._entries))

    def norm_squared(self) -> Any:
        """Exact sum of a * conj(a) over all entries (an element of the real subfield)."""
        field = self._field
        total = field.zero
        for a in self._entries:
            if not field.is_zero(a):
                total = field.add(total, field.mul(a, field.conj(a)))
        return total

    def scale(self, factor: object) -> "ExactTensor":
        """Multiply every entry by a field element."""
        field = self._field
        c = field.coerce(factor)
        return ExactTensor._raw(field, self._shape, tuple(field.mul(c, a) for a in self._entries))

    def _combine(self, other: object, operation: Callable[[Any, Any], Any]) -> "ExactTensor":
        other = self._require_same_field(other)
        if other._shape != self._shape:
            raise ValueError(f"shapes {self._shape!r} and {other._shape!r} differ")
        return ExactTensor._raw(self._field, self._shape,
                                tuple(operation(a, b) for a, b in zip(self._entries, other._entries)))

    def __add__(self, other: "ExactTensor") -> "ExactTensor":
        return self._combine(other, self._field.add)

    def __sub__(self, other: "ExactTensor") -> "ExactTensor":
        return self._combine(other, self._field.sub)

    def __neg__(self) -> "ExactTensor":
        neg = self._field.neg
        return ExactTensor._raw(self._field, self._shape, tuple(neg(a) for a in self._entries))

    def is_zero(self) -> bool:
        is_zero = self._field.is_zero
        return all(is_zero(a) for a in self._entries)

    # -- comparison ----------------------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExactTensor):
            return NotImplemented
        if other._field != self._field or other._shape != self._shape:
            return False
        eq = self._field.eq
        return all(eq(a, b) for a, b in zip(self._entries, other._entries))

    def __hash__(self) -> int:
        return hash((self._field, self._shape, self._entries))

    def __repr__(self) -> str:
        return f"ExactTensor({self._field!r}, shape={self._shape!r}, entries={self._entries!r})"
