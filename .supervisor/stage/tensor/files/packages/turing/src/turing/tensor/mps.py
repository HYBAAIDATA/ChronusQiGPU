"""Exact matrix product states of qubit and qudit registers over Q(zeta_m).

An :class:`ExactMPS` stores one core per site, core k holding d_k matrices
A_k[s] of shape r_k x r_(k+1) with r_0 = r_n = 1, so that the unnormalised
amplitude of the basis state |s_0 s_1 ... s_(n-1)> is the 1 x 1 product
A_0[s_0] A_1[s_1] ... A_(n-1)[s_(n-1)]. Every entry is an exact field element.

Gates are applied as exact matrices with a declared normalisation: a gate is
an exact matrix M and a positive rational ``scale`` with M M^dagger = scale * I,
and it acts as M / sqrt(scale). The register keeps the product of the scales
as an exact rational, so the normalised amplitude is value / sqrt(scale) and
every probability |value|^2 / scale is exact. The Hadamard gate is M = [[1, 1],
[1, -1]] with scale 2, a factor 2^(-1/2) per H.

A two-site gate on neighbouring sites contracts the two cores, applies the
gate, reshapes the result to a matrix and factorises it exactly as C @ R
(:mod:`turing.tensor.linalg`); the new bond dimension is the exact rank. Gates
on distant sites are routed with exact SWAP gates. Because every gate is
invertible, every bond dimension always equals the exact Schmidt rank of the
state across that cut, the smallest possible. Nothing is ever truncated: when
a bond would exceed ``max_bond`` the gate is refused with ``ValueError`` and
the register keeps its previous state.
"""

from __future__ import annotations

from fractions import Fraction
from math import lcm
from typing import Any, Iterable, Mapping, Optional, Sequence

from ..algebra.cyclotomic import CyclotomicElement
from .dense import ExactTensor, _size
from .field import Field, cyclotomic
from .linalg import _cr_rows
from .train import TensorTrain

__all__ = [
    "DEFAULT_MAX_BOND",
    "ExactAmplitude",
    "ExactMPS",
    "GATE_NAMES",
]

DEFAULT_MAX_BOND = 64
"""Default refusal threshold for bond dimensions (2^6, the largest Schmidt rank of 12 qubits)."""

GATE_NAMES = ("x", "y", "z", "h", "s", "t", "phase", "cz", "cnot", "swap", "unitary")
"""Gate names accepted by :meth:`ExactMPS.apply` and :func:`turing.tensor.evaluate_circuit`."""

Matrix = tuple  # tuple of rows, each a tuple of field elements


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _as_scale(value: object) -> Fraction:
    if isinstance(value, Fraction) or _is_int(value):
        scale = Fraction(value)
        if scale > 0:
            return scale
    raise ValueError(f"a gate scale must be a positive int or fractions.Fraction, got {value!r}")


# ---------------------------------------------------------------------------------------------
# Exact amplitudes value / sqrt(scale)
# ---------------------------------------------------------------------------------------------

class ExactAmplitude:
    """The exact complex number value / sqrt(scale), value in a field and scale a positive integer.

    A rational scale p/q is stored as the integer p*q with value multiplied by q,
    and factors of 4 are moved out of the scale into the value, so a Hadamard
    circuit keeps scale 1 or 2. Equality is exact equality of complex numbers,
    also between different scales (it uses the field's exact positive square
    roots where the field contains them).
    """

    __slots__ = ("_field", "_value", "_scale")

    def __init__(self, field: Field, value: object, scale: object = 1) -> None:
        if not isinstance(field, Field):
            raise TypeError("field must provide the turing.tensor.Field protocol")
        element = field.coerce(value)
        ratio = _as_scale(scale)
        integer = ratio.numerator * ratio.denominator
        if ratio.denominator != 1:
            element = field.mul(element, field.from_int(ratio.denominator))
        halvings = 0
        while integer % 4 == 0:
            integer //= 4
            halvings += 1
        if halvings:
            element = field.div(element, field.from_int(1 << halvings))
        self._field = field
        self._value = element
        self._scale = integer

    @property
    def field(self) -> Field:
        return self._field

    @property
    def value(self) -> Any:
        """The numerator: the amplitude is value / sqrt(scale)."""
        return self._value

    @property
    def scale(self) -> int:
        """The positive integer under the square root (not divisible by 4)."""
        return self._scale

    def is_zero(self) -> bool:
        return self._field.is_zero(self._value)

    def probability(self) -> Any:
        """|value|^2 / scale, an exact element of the field's real subfield."""
        field = self._field
        return field.div(field.mul(self._value, field.conj(self._value)), field.from_int(self._scale))

    def to_field_element(self) -> Any:
        """value / sqrt(scale) as a field element; ValueError if the field does not contain sqrt(scale)."""
        field = self._field
        if self._scale == 1:
            return self._value
        root = _positive_sqrt(field, self._scale)
        if root is None:
            raise ValueError(f"{field!r} does not contain sqrt({self._scale}); keep the exact form "
                             f"value / sqrt(scale)")
        return field.div(field.mul(self._value, root), field.from_int(self._scale))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ExactAmplitude):
            return NotImplemented
        if other._field != self._field:
            return False
        field = self._field
        if self._scale == other._scale:
            return field.eq(self._value, other._value)
        if field.is_zero(self._value) or field.is_zero(other._value):
            return field.is_zero(self._value) and field.is_zero(other._value)
        # v / sqrt(d) == w / sqrt(e)  <=>  v * sqrt(d * e) == w * d  (multiply both sides by sqrt(d) * sqrt(e))
        root = _positive_sqrt(field, self._scale * other._scale)
        if root is None:
            return False
        return field.eq(field.mul(self._value, root), field.mul(other._value, field.from_int(self._scale)))

    def __hash__(self) -> int:
        return hash(self.probability())

    def __repr__(self) -> str:
        if self._scale == 1:
            return f"ExactAmplitude({self._value!r})"
        return f"ExactAmplitude(({self._value!r}) / sqrt({self._scale}))"


def _positive_sqrt(field: Field, value: int) -> Any:
    method = getattr(field, "positive_sqrt", None)
    if method is not None:
        return method(value)
    return field.one if value == 1 else None


# ---------------------------------------------------------------------------------------------
# Matrix helpers on tuples of rows (zero entries are skipped)
# ---------------------------------------------------------------------------------------------

def _mat_mul(field: Field, left: Matrix, right: Matrix, rows: int, inner: int, columns: int) -> list:
    zero = field.zero
    is_zero = field.is_zero
    add = field.add
    mul = field.mul
    out = [[zero] * columns for _ in range(rows)]
    for i in range(rows):
        target = out[i]
        source = left[i]
        for k in range(inner):
            a = source[k]
            if is_zero(a):
                continue
            row = right[k]
            for j in range(columns):
                b = row[j]
                if not is_zero(b):
                    target[j] = add(target[j], mul(a, b))
    return out


def _combine_terms(field: Field, terms: Sequence[tuple[int, Any, int]], blocks: Mapping[int, Matrix] | Sequence[Matrix],
                   rows: int, columns: int) -> Matrix:
    """sum_t u_t * blocks[i_t] for terms (i_t, u_t, kind_t); kind 1 means u = 1 and -1 means u = -1."""
    is_zero = field.is_zero
    add = field.add
    sub = field.sub
    mul = field.mul
    neg = field.neg
    if len(terms) == 1:
        index, factor, kind = terms[0]
        block = blocks[index]
        if kind == 1:
            return block
        if kind == -1:
            return tuple(tuple(value if is_zero(value) else neg(value) for value in row) for row in block)
        return tuple(tuple(value if is_zero(value) else mul(factor, value) for value in row) for row in block)
    out = [[field.zero] * columns for _ in range(rows)]
    for index, factor, kind in terms:
        block = blocks[index]
        for a in range(rows):
            source = block[a]
            target = out[a]
            for b in range(columns):
                value = source[b]
                if is_zero(value):
                    continue
                if kind == 1:
                    target[b] = add(target[b], value)
                elif kind == -1:
                    target[b] = sub(target[b], value)
                else:
                    target[b] = add(target[b], mul(factor, value))
    return tuple(tuple(row) for row in out)


def _sparse_rows(field: Field, matrix: Sequence[Sequence[Any]]) -> tuple[tuple[tuple[int, Any, int], ...], ...]:
    """Per output row, the nonzero entries as (input index, value, kind)."""
    one = field.one
    minus_one = field.neg(one)
    rows = []
    for row in matrix:
        terms = []
        for j, value in enumerate(row):
            if field.is_zero(value):
                continue
            kind = 1 if field.eq(value, one) else -1 if field.eq(value, minus_one) else 0
            terms.append((j, value, kind))
        rows.append(tuple(terms))
    return tuple(rows)


class _Gate:
    """A validated exact gate: matrix rows over the field, its scale, and its sparse form."""

    __slots__ = ("name", "matrix", "scale", "sparse", "dims_in", "dims_out", "_reverse")

    def __init__(self, field: Field, name: str, matrix: Sequence[Sequence[Any]], scale: Fraction,
                 dims_in: tuple[int, ...], dims_out: tuple[int, ...]) -> None:
        self.name = name
        self.matrix = tuple(tuple(row) for row in matrix)
        self.scale = scale
        self.sparse = _sparse_rows(field, self.matrix)
        self.dims_in = dims_in
        self.dims_out = dims_out
        self._reverse = None

    def reversed(self, field: Field) -> "_Gate":
        """The same two-site operator with its tensor factors listed in the other order."""
        if self._reverse is None:
            first, second = self.dims_in
            self._reverse = _Gate(field, self.name, _reorder_two_site(self.matrix, first, second), self.scale,
                                  (second, first), (second, first))
        return self._reverse


def _check_unitary(field: Field, matrix: Matrix, scale: Fraction) -> None:
    size = len(matrix)
    target = field.div(field.from_int(scale.numerator), field.from_int(scale.denominator))
    for i in range(size):
        for j in range(i, size):
            total = field.zero
            for a, b in zip(matrix[i], matrix[j]):
                if not field.is_zero(a) and not field.is_zero(b):
                    total = field.add(total, field.mul(a, field.conj(b)))
            expected = target if i == j else field.zero
            if not field.eq(total, expected):
                raise ValueError(f"the gate matrix is not unitary up to its declared scale {scale}: "
                                 f"row {i} times the conjugate of row {j} is not {'scale' if i == j else '0'}")


def _coerce_matrix(field: Field, matrix: object, size: int) -> Matrix:
    if isinstance(matrix, ExactTensor):
        if matrix.shape != (size, size):
            raise ValueError(f"expected a {size} x {size} gate matrix, got shape {matrix.shape!r}")
        entries = [field.coerce(value) for value in matrix.entries]
        return tuple(tuple(entries[i * size:(i + 1) * size]) for i in range(size))
    if isinstance(matrix, (str, bytes)) or not isinstance(matrix, Sequence) or len(matrix) != size:
        raise ValueError(f"expected a {size} x {size} gate matrix")
    rows = []
    for row in matrix:
        if isinstance(row, (str, bytes)) or not isinstance(row, Sequence) or len(row) != size:
            raise ValueError(f"expected a {size} x {size} gate matrix")
        rows.append(tuple(field.coerce(value) for value in row))
    return tuple(rows)


def _swap_matrix(field: Field, first: int, second: int) -> Matrix:
    """The permutation |a b> -> |b a> from C^first (x) C^second to C^second (x) C^first."""
    size = first * second
    rows = [[field.zero] * size for _ in range(size)]
    for a in range(first):
        for b in range(second):
            rows[b * first + a][a * second + b] = field.one
    return tuple(tuple(row) for row in rows)


def _reorder_two_site(matrix: Matrix, first: int, second: int) -> Matrix:
    """The same operator with the two tensor factors listed in the other order."""
    size = first * second
    out = [[None] * size for _ in range(size)]
    for t1 in range(first):
        for t2 in range(second):
            for s1 in range(first):
                for s2 in range(second):
                    out[t2 * first + t1][s2 * first + s1] = matrix[t1 * second + t2][s1 * second + s2]
    return tuple(tuple(row) for row in out)


_NAMED_CACHE: dict = {}
_GATE_CACHE: dict = {}


def _named_gate(field: Field, name: str) -> _Gate:
    """The validated sparse form of a named gate, built once per field."""
    key = (field, name)
    gate = _GATE_CACHE.get(key)
    if gate is None:
        matrix, scale = _named_matrix(field, name)
        dims = (2,) if len(matrix) == 2 else (2, 2)
        gate = _Gate(field, name, matrix, scale, dims, dims)
        _GATE_CACHE[key] = gate
    return gate


def _swap_gate(field: Field, first: int, second: int) -> _Gate:
    """SWAP from C^first (x) C^second to C^second (x) C^first, built once per field and dimensions."""
    key = (field, "swap", first, second)
    gate = _GATE_CACHE.get(key)
    if gate is None:
        gate = _Gate(field, "swap", _swap_matrix(field, first, second), Fraction(1), (first, second),
                     (second, first))
        _GATE_CACHE[key] = gate
    return gate


def _named_matrix(field: Field, name: str) -> tuple[Matrix, Fraction]:
    key = (field, name)
    cached = _NAMED_CACHE.get(key)
    if cached is not None:
        return cached
    o, z = field.one, field.zero
    m = field.neg(o)
    if name == "x":
        matrix = ((z, o), (o, z))
    elif name == "z":
        matrix = ((o, z), (z, m))
    elif name == "h":
        matrix = ((o, o), (o, m))
    elif name in ("y", "s"):
        i = _root_of_unity(field, 4, 1)
        matrix = ((z, field.neg(i)), (i, z)) if name == "y" else ((o, z), (z, i))
    elif name == "t":
        matrix = ((o, z), (z, _root_of_unity(field, 8, 1)))
    elif name == "cz":
        matrix = ((o, z, z, z), (z, o, z, z), (z, z, o, z), (z, z, z, m))
    elif name == "cnot":
        matrix = ((o, z, z, z), (z, o, z, z), (z, z, z, o), (z, z, o, z))
    elif name == "swap":
        matrix = _swap_matrix(field, 2, 2)
    else:
        raise ValueError(f"unknown gate {name!r}")
    result = (matrix, Fraction(2) if name == "h" else Fraction(1))
    _NAMED_CACHE[key] = result
    return result


def _root_of_unity(field: Field, order: int, power: int) -> Any:
    """zeta_order ** power in the field, or ValueError if the field does not contain it."""
    method = getattr(field, "root_of_unity", None)
    if method is not None:
        return method(order, power)
    reduced = power % order
    if reduced == 0:
        return field.one
    if 2 * reduced == order:
        return field.neg(field.one)
    raise ValueError(f"{field!r} does not contain the root of unity zeta_{order}^{power}; "
                     f"use turing.tensor.cyclotomic(m) with {order} dividing m")


# ---------------------------------------------------------------------------------------------
# The register
# ---------------------------------------------------------------------------------------------

class ExactMPS:
    """An exact matrix product state of ``num_sites`` qudits, initialised to |0 ... 0>.

    ``local_dims`` is 2 (qubits), another int >= 2, or one int per site. The
    default field is Q(zeta_8), which contains every amplitude of the gates
    X, Y, Z, H, S, T, CZ, CNOT and SWAP. ``max_bond`` is the refusal threshold:
    a gate that would create a bond with exact rank above it raises ValueError
    and leaves the register unchanged.
    """

    __slots__ = ("_field", "_cores", "_dims", "_scale", "_max_bond")

    def __init__(self, num_sites: int, local_dims: int | Sequence[int] = 2, field: Optional[Field] = None,
                 max_bond: int = DEFAULT_MAX_BOND) -> None:
        if not _is_int(num_sites) or num_sites < 1:
            raise ValueError(f"num_sites must be a positive int, got {num_sites!r}")
        if _is_int(local_dims):
            dims = (local_dims,) * num_sites
        elif isinstance(local_dims, Sequence) and not isinstance(local_dims, (str, bytes)):
            dims = tuple(local_dims)
            if len(dims) != num_sites:
                raise ValueError(f"local_dims lists {len(dims)} dimensions for {num_sites} sites")
        else:
            raise TypeError("local_dims must be an int or a sequence of ints")
        for dim in dims:
            if not _is_int(dim) or dim < 2:
                raise ValueError(f"local dimensions must be ints >= 2, got {dim!r}")
        if field is None:
            field = cyclotomic(8)
        if not isinstance(field, Field):
            raise TypeError("field must provide the turing.tensor.Field protocol")
        if not _is_int(max_bond) or max_bond < 1:
            raise ValueError(f"max_bond must be a positive int, got {max_bond!r}")
        one, zero = field.one, field.zero
        cores = []
        for dim in dims:
            cores.append(tuple(((one,),) if s == 0 else ((zero,),) for s in range(dim)))
        self._field = field
        self._cores = cores
        self._dims = list(dims)
        self._scale = Fraction(1)
        self._max_bond = max_bond

    # -- accessors ------------------------------------------------------------------------------

    @property
    def field(self) -> Field:
        return self._field

    @property
    def num_sites(self) -> int:
        """Register size, read from the stored cores."""
        return len(self._cores)

    @property
    def local_dims(self) -> tuple[int, ...]:
        return tuple(self._dims)

    @property
    def max_bond(self) -> int:
        return self._max_bond

    @property
    def scale(self) -> Fraction:
        """Product of the declared gate scales: the state is (stored state) / sqrt(scale)."""
        return self._scale

    def bond_dimensions(self) -> tuple[int, ...]:
        """The n - 1 bond dimensions, read from the stored cores; entry k joins sites k and k + 1."""
        return tuple(len(core[0][0]) for core in self._cores[:-1])

    def core(self, site: int) -> ExactTensor:
        """Core ``site`` as an ExactTensor of shape (r_left, d, r_right)."""
        k = self._site(site)
        core = self._cores[k]
        left, right = len(core[0]), len(core[0][0])
        flat = tuple(core[s][a][b] for a in range(left) for s in range(len(core)) for b in range(right))
        return ExactTensor._raw(self._field, (left, len(core), right), flat)

    def as_tensor_train(self) -> TensorTrain:
        """The stored (unnormalised) state as a TensorTrain of shape (d_0, ..., d_(n-1))."""
        return TensorTrain._raw(self._field, tuple(self.core(k) for k in range(len(self._cores))))

    def to_dense(self) -> ExactTensor:
        """The stored (unnormalised) amplitudes as a dense tensor of shape (d_0, ..., d_(n-1)).

        Axis k is site k (so the row-major flat index has site 0 most significant).
        Refused with ValueError above MAX_DENSE_ENTRIES entries.
        """
        _size(tuple(self._dims))
        return self.as_tensor_train().to_dense()

    def copy(self) -> "ExactMPS":
        clone = object.__new__(ExactMPS)
        clone._field = self._field
        clone._cores = list(self._cores)
        clone._dims = list(self._dims)
        clone._scale = self._scale
        clone._max_bond = self._max_bond
        return clone

    def _site(self, site: object) -> int:
        if not _is_int(site):
            raise TypeError(f"site indices must be ints, got {type(site).__name__}")
        if not 0 <= site < len(self._cores):
            raise ValueError(f"site {site} is outside the register 0 .. {len(self._cores) - 1}")
        return site

    # -- gates --------------------------------------------------------------------------------------

    def apply(self, name: str, qubits: Sequence[int] | int, params: Sequence[Any] | Mapping[str, Any] = ()
              ) -> "ExactMPS":
        """Apply a gate by name (see GATE_NAMES); ``params`` are positional or keyword arguments."""
        if not isinstance(name, str):
            raise TypeError("the gate name must be a str")
        key = name.lower()
        if key not in GATE_NAMES:
            raise ValueError(f"unknown gate {name!r}; known gates: {', '.join(GATE_NAMES)}")
        sites = (qubits,) if _is_int(qubits) else tuple(qubits)
        if isinstance(params, Mapping):
            args: tuple = ()
            kwargs = dict(params)
        else:
            args = tuple(params)
            kwargs = {}
        if key == "unitary":
            if len(sites) == 1:
                return self.apply_one(sites[0], *args, **kwargs)
            if len(sites) == 2:
                return self.apply_two(sites[0], sites[1], *args, **kwargs)
            raise ValueError("a unitary gate acts on one or two sites")
        expected = 2 if key in ("cz", "cnot", "swap") else 1
        if len(sites) != expected:
            raise ValueError(f"gate {name!r} acts on {expected} site(s), got {sites!r}")
        if key != "phase" and (args or kwargs):
            raise ValueError(f"gate {name!r} takes no parameters")
        return getattr(self, key)(*sites, *args, **kwargs)

    def _named_one(self, name: str, site: int) -> "ExactMPS":
        k = self._site(site)
        if self._dims[k] != 2:
            raise ValueError(f"gate {name!r} acts on qubits; site {k} has dimension {self._dims[k]}")
        return self._apply_single(k, _named_gate(self._field, name))

    def x(self, site: int) -> "ExactMPS":
        return self._named_one("x", site)

    def y(self, site: int) -> "ExactMPS":
        return self._named_one("y", site)

    def z(self, site: int) -> "ExactMPS":
        return self._named_one("z", site)

    def h(self, site: int) -> "ExactMPS":
        """Hadamard as [[1, 1], [1, -1]] with scale 2 (a factor 2^(-1/2) kept symbolically)."""
        return self._named_one("h", site)

    def s(self, site: int) -> "ExactMPS":
        return self._named_one("s", site)

    def t(self, site: int) -> "ExactMPS":
        """diag(1, zeta_8)."""
        return self._named_one("t", site)

    def phase(self, site: int, power: int, order: Optional[int] = None) -> "ExactMPS":
        """diag(1, zeta_order^power); ``order`` defaults to the m of the register field Q(zeta_m)."""
        k = self._site(site)
        if self._dims[k] != 2:
            raise ValueError(f"gate 'phase' acts on qubits; site {k} has dimension {self._dims[k]}")
        if not _is_int(power):
            raise TypeError("the phase power must be an int")
        if order is None:
            order = getattr(self._field, "order", 2)
        if not _is_int(order) or order < 1:
            raise ValueError(f"the root-of-unity order must be a positive int, got {order!r}")
        field = self._field
        matrix = ((field.one, field.zero), (field.zero, _root_of_unity(field, order, power)))
        return self._apply_single(k, _Gate(field, "phase", matrix, Fraction(1), (2,), (2,)))

    def apply_one(self, site: int, matrix: object, scale: object = 1) -> "ExactMPS":
        """Apply matrix / sqrt(scale) to one site; the matrix must satisfy M M^dagger = scale * I exactly."""
        k = self._site(site)
        dim = self._dims[k]
        field = self._field
        rows = _coerce_matrix(field, matrix, dim)
        ratio = _as_scale(scale)
        _check_unitary(field, rows, ratio)
        return self._apply_single(k, _Gate(field, "unitary", rows, ratio, (dim,), (dim,)))

    def _named_two(self, name: str, first: int, second: int) -> "ExactMPS":
        a, b = self._pair(first, second)
        if self._dims[a] != 2 or self._dims[b] != 2:
            raise ValueError(f"gate {name!r} acts on qubits; sites {a} and {b} have dimensions "
                             f"{self._dims[a]} and {self._dims[b]}")
        return self._apply_pair(a, b, _named_gate(self._field, name))

    def cz(self, first: int, second: int) -> "ExactMPS":
        return self._named_two("cz", first, second)

    def cnot(self, control: int, target: int) -> "ExactMPS":
        return self._named_two("cnot", control, target)

    def swap(self, first: int, second: int) -> "ExactMPS":
        a, b = self._pair(first, second)
        if self._dims[a] != self._dims[b]:
            raise ValueError("swap exchanges two sites of the same dimension")
        return self._apply_pair(a, b, _swap_gate(self._field, self._dims[a], self._dims[b]))

    def apply_two(self, first: int, second: int, matrix: object, scale: object = 1) -> "ExactMPS":
        """Apply matrix / sqrt(scale) to two sites; basis index s_first * d_second + s_second."""
        a, b = self._pair(first, second)
        field = self._field
        rows = _coerce_matrix(field, matrix, self._dims[a] * self._dims[b])
        ratio = _as_scale(scale)
        _check_unitary(field, rows, ratio)
        dims = (self._dims[a], self._dims[b])
        return self._apply_pair(a, b, _Gate(field, "unitary", rows, ratio, dims, dims))

    def _pair(self, first: int, second: int) -> tuple[int, int]:
        a = self._site(first)
        b = self._site(second)
        if a == b:
            raise ValueError("a two-site gate needs two distinct sites")
        return a, b

    # -- core updates -----------------------------------------------------------------------------

    def _apply_single(self, k: int, gate: _Gate) -> "ExactMPS":
        field = self._field
        core = self._cores[k]
        left, right = len(core[0]), len(core[0][0])
        zero_block = None
        new = []
        for terms in gate.sparse:
            if terms:
                new.append(_combine_terms(field, terms, core, left, right))
            else:
                if zero_block is None:
                    zero_block = tuple(tuple(field.zero for _ in range(right)) for _ in range(left))
                new.append(zero_block)
        self._cores[k] = tuple(new)
        self._scale *= gate.scale
        return self

    def _apply_pair(self, a: int, b: int, gate: _Gate) -> "ExactMPS":
        """Apply a two-site gate listed in the order (a, b); routes with SWAPs when |a - b| > 1."""
        if a > b:
            gate = gate.reversed(self._field)
            a, b = b, a
        if b == a + 1:
            first, second = self._two_site(self._cores, self._dims, a, gate, gate.name)
            self._cores[a] = first
            self._cores[a + 1] = second
        else:
            cores = list(self._cores)
            work_dims = list(self._dims)
            label = f"swap routing {gate.name} on sites {a} and {b}"
            for k in range(b - 1, a, -1):
                self._swap_into(cores, work_dims, k, label)
            first, second = self._two_site(cores, work_dims, a, gate, gate.name)
            cores[a], cores[a + 1] = first, second
            for k in range(a + 1, b):
                self._swap_into(cores, work_dims, k, label)
            self._cores = cores
            self._dims = work_dims
        self._scale *= gate.scale
        return self

    def _swap_into(self, cores: list, dims: list, k: int, label: str) -> None:
        first, second = dims[k], dims[k + 1]
        cores[k], cores[k + 1] = self._two_site(cores, dims, k, _swap_gate(self._field, first, second), label)
        dims[k], dims[k + 1] = second, first

    def _two_site(self, cores: Sequence, dims: Sequence[int], k: int, gate: _Gate,
                  label: str) -> tuple[tuple, tuple]:
        """Contract sites k, k + 1, apply the gate and refactorise exactly; refuse bonds above max_bond."""
        field = self._field
        left_core, right_core = cores[k], cores[k + 1]
        d1, d2 = dims[k], dims[k + 1]
        if gate.dims_in != (d1, d2):
            raise ArithmeticError(f"gate {label!r} acts on dimensions {gate.dims_in}, sites {k} and {k + 1} have "
                                  f"{(d1, d2)}")
        e1, e2 = gate.dims_out
        r_left = len(left_core[0])
        r_mid = len(left_core[0][0])
        r_right = len(right_core[0][0])
        theta: dict[int, Matrix] = {}
        out: dict[tuple[int, int], Matrix] = {}
        for t1 in range(e1):
            for t2 in range(e2):
                terms = gate.sparse[t1 * e2 + t2]
                if not terms:
                    continue
                for index, _, _ in terms:
                    if index not in theta:
                        s1, s2 = divmod(index, d2)
                        theta[index] = _mat_mul(field, left_core[s1], right_core[s2], r_left, r_mid, r_right)
                out[(t1, t2)] = _combine_terms(field, terms, theta, r_left, r_right)
        zero = field.zero
        width = e2 * r_right
        rows = []
        for a in range(r_left):
            for t1 in range(e1):
                row = [zero] * width
                for t2 in range(e2):
                    block = out.get((t1, t2))
                    if block is not None:
                        source = block[a]
                        base = t2 * r_right
                        for c in range(r_right):
                            row[base + c] = source[c]
                rows.append(row)
        c_rows, r_rows, pivots = _cr_rows(field, rows, width)
        rank = len(pivots)
        if rank > self._max_bond:
            raise ValueError(f"the bond between sites {k} and {k + 1} (bond_dimensions()[{k}]) needs exact rank "
                             f"{rank}, above max_bond = {self._max_bond}; the gate {label!r} is refused and "
                             f"the register is unchanged (no truncation)")
        if rank == 0:
            raise ArithmeticError("a two-site update produced the zero state; gates must be invertible")
        first = tuple(tuple(tuple(c_rows[a * e1 + t1][j] for j in range(rank)) for a in range(r_left))
                      for t1 in range(e1))
        second = tuple(tuple(tuple(r_rows[j][t2 * r_right + c] for c in range(r_right)) for j in range(rank))
                       for t2 in range(e2))
        return first, second

    # -- exact evaluation -------------------------------------------------------------------------------

    def _digits(self, index: object) -> tuple[int, ...]:
        dims = self._dims
        n = len(dims)
        if _is_int(index):
            digits = []
            remaining = index
            if remaining < 0:
                raise ValueError("a basis index must be non-negative")
            for dim in dims:
                remaining, digit = divmod(remaining, dim)
                digits.append(digit)
            if remaining:
                raise ValueError(f"basis index {index} is outside the register of {n} sites")
            return tuple(digits)
        if isinstance(index, str):
            if len(index) != n or not all("0" <= ch <= "9" for ch in index):
                raise ValueError(f"a basis string needs {n} decimal digits, one per site")
            values = tuple(ord(ch) - 48 for ch in index)
        elif isinstance(index, Iterable):
            values = tuple(index)
            if len(values) != n or not all(_is_int(v) for v in values):
                raise ValueError(f"a basis label needs {n} int digits, one per site")
        else:
            raise TypeError("a basis label is an int index, a digit string or a sequence of digits")
        for k, (value, dim) in enumerate(zip(values, dims)):
            if not 0 <= value < dim:
                raise ValueError(f"digit {value} of site {k} is outside 0 .. {dim - 1}")
        return values

    def amplitude(self, index: object) -> ExactAmplitude:
        """Exact amplitude of one basis state, O(n chi^2) field operations, no state vector.

        ``index`` is a sequence (or digit string) with one digit per site, site 0
        first, or an int with TURING's convention: site k is digit k of the
        index in the mixed radix of the local dimensions (for qubits, bit k is
        qubit k, bit 0 the least significant).
        """
        digits = self._digits(index)
        field = self._field
        is_zero = field.is_zero
        add = field.add
        mul = field.mul
        vector = [field.one]
        for core, digit in zip(self._cores, digits):
            block = core[digit]
            right = len(block[0])
            out = [field.zero] * right
            for a, weight in enumerate(vector):
                if is_zero(weight):
                    continue
                row = block[a]
                for b in range(right):
                    value = row[b]
                    if not is_zero(value):
                        out[b] = add(out[b], mul(weight, value))
            vector = out
        return ExactAmplitude(field, vector[0], self._scale)

    def probability(self, index: object) -> Any:
        """Exact probability |amplitude|^2 of one basis state."""
        return self.amplitude(index).probability()

    def _environment_step(self, environment: list, core: tuple, from_left: bool) -> list:
        """One transfer-matrix step of <psi|psi> (left: sum_s A_s^H E A_s; right: sum_s conj(A_s) E A_s^T)."""
        field = self._field
        left, right = len(core[0]), len(core[0][0])
        inner, outer = (left, right) if from_left else (right, left)
        total = [[field.zero] * outer for _ in range(outer)]
        for block in core:
            if from_left:
                oriented = block
            else:
                oriented = tuple(tuple(block[a][b] for a in range(left)) for b in range(right))
            carried = _mat_mul(field, environment, oriented, inner, inner, outer)
            for b in range(outer):
                target = total[b]
                for a in range(inner):
                    value = oriented[a][b]
                    if field.is_zero(value):
                        continue
                    weight = field.conj(value)
                    source = carried[a]
                    for c in range(outer):
                        if not field.is_zero(source[c]):
                            target[c] = field.add(target[c], field.mul(weight, source[c]))
        return total

    def norm_squared(self) -> Any:
        """sum |stored amplitude|^2 by exact transfer matrices; equals ``scale`` for a valid register."""
        environment = [[self._field.one]]
        for core in self._cores:
            environment = self._environment_step(environment, core, True)
        return environment[0][0]

    def is_normalized(self) -> bool:
        """Exact check that the normalised state has norm 1 (norm_squared() == scale)."""
        field = self._field
        expected = field.div(field.from_int(self._scale.numerator), field.from_int(self._scale.denominator))
        return field.eq(self.norm_squared(), expected)

    def marginal_probabilities(self, site: int) -> tuple[Any, ...]:
        """Exact probabilities of each value of one site, by exact environment contraction."""
        k = self._site(site)
        field = self._field
        left_env = [[field.one]]
        for core in self._cores[:k]:
            left_env = self._environment_step(left_env, core, True)
        right_env = [[field.one]]
        for core in reversed(self._cores[k + 1:]):
            right_env = self._environment_step(right_env, core, False)
        core = self._cores[k]
        left, right = len(core[0]), len(core[0][0])
        denominator = field.div(field.from_int(self._scale.numerator), field.from_int(self._scale.denominator))
        results = []
        for block in core:
            carried = _mat_mul(field, left_env, block, left, left, right)
            total = field.zero
            for a in range(left):
                for b in range(right):
                    value = block[a][b]
                    if field.is_zero(value):
                        continue
                    weight = field.conj(value)
                    for c in range(right):
                        if not field.is_zero(carried[a][c]) and not field.is_zero(right_env[b][c]):
                            total = field.add(total, field.mul(weight, field.mul(carried[a][c], right_env[b][c])))
            results.append(field.div(total, denominator))
        return tuple(results)

    def marginal_probability(self, site: int, value: int) -> Any:
        """Exact probability that ``site`` holds ``value``."""
        k = self._site(site)
        if not _is_int(value) or not 0 <= value < self._dims[k]:
            raise ValueError(f"value {value!r} is outside 0 .. {self._dims[k] - 1}")
        return self.marginal_probabilities(k)[value]

    def __repr__(self) -> str:
        return (f"ExactMPS({len(self._cores)} sites, field={self._field!r}, "
                f"bonds max {max(self.bond_dimensions(), default=1)}, scale={self._scale})")


def required_order(gates: Iterable[tuple[str, Sequence[int], Any]]) -> int:
    """Smallest m such that Q(zeta_m) holds every amplitude of these gates (at least 8)."""
    order = 8
    for name, _, params in gates:
        if name == "phase":
            values = list(params.values()) if isinstance(params, Mapping) else list(params)
            if len(values) >= 2 and _is_int(values[1]) and values[1] >= 1:
                order = lcm(order, values[1])
        elif name == "unitary":
            values = list(params.values()) if isinstance(params, Mapping) else list(params)
            matrix = values[0] if values else ()
            if isinstance(matrix, ExactTensor):
                field_order = getattr(matrix.field, "order", 1)
                order = lcm(order, field_order)
            elif isinstance(matrix, Sequence):
                for row in matrix:
                    if isinstance(row, Sequence):
                        for value in row:
                            if isinstance(value, CyclotomicElement):
                                order = lcm(order, value.field.n)
    return order
