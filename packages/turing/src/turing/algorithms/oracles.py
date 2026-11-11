"""The oracle protocol and validated oracle implementations.

An oracle is any object with an int attribute ``domain_size`` and a method
``__call__(x: int) -> int`` defined for 0 <= x < domain_size. A Boolean oracle
returns 0 or 1. The algorithms accept any object satisfying this protocol
(duck typing); subclassing is never required.

Dense algorithms evaluate an oracle on its whole domain (exactly the inputs
on which the corresponding unitary acts), so they refuse domains larger than
``MAX_DENSE_DOMAIN``. :class:`AffineOracle` and :class:`LinearOracle` expose
their GF(2) structure so that :mod:`turing.algorithms.structured` can
evaluate the corresponding stabilizer circuits at thousands of qubits.
"""

from __future__ import annotations

from typing import Callable, Iterable, Mapping, Protocol, Sequence, runtime_checkable

__all__ = [
    "AffineOracle",
    "BooleanOracle",
    "FunctionOracle",
    "LinearOracle",
    "MAX_DENSE_DOMAIN",
    "Oracle",
    "boolean_table",
    "function_table",
    "qubits_for_domain",
    "require_affine",
    "require_constant_or_balanced",
    "require_qubit_domain",
    "require_simon_promise",
]

MAX_DENSE_DOMAIN = 1 << 20


@runtime_checkable
class Oracle(Protocol):
    """Structural type of an oracle: ``domain_size`` plus ``__call__(x) -> int``."""

    domain_size: int

    def __call__(self, x: int) -> int:
        ...


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parity(value: int) -> int:
    return value.bit_count() & 1


def _domain_size_of(oracle: object) -> int:
    if not callable(oracle) or not hasattr(oracle, "domain_size"):
        raise TypeError("an oracle needs an int attribute domain_size and a method __call__(x) -> int")
    size = getattr(oracle, "domain_size")
    if not _is_int(size) or size < 1:
        raise ValueError(f"oracle domain_size must be a positive int, got {size!r}")
    return size


def qubits_for_domain(domain_size: int) -> int:
    """Return n with domain_size == 2**n, or raise ValueError."""
    if not _is_int(domain_size) or domain_size < 1:
        raise ValueError(f"domain size must be a positive int, got {domain_size!r}")
    n = domain_size.bit_length() - 1
    if 1 << n != domain_size:
        raise ValueError(f"domain size {domain_size} is not a power of two")
    return n


def require_qubit_domain(oracle: object, n: int) -> int:
    """Check that ``oracle`` acts on n-bit inputs (domain_size == 2**n)."""
    if not _is_int(n) or n < 0:
        raise ValueError(f"number of input bits must be a non-negative int, got {n!r}")
    size = _domain_size_of(oracle)
    if size != 1 << n:
        raise ValueError(f"oracle domain_size is {size}, expected 2**{n} = {1 << n}")
    return size


def function_table(oracle: object) -> tuple[int, ...]:
    """Evaluate an oracle on every input 0 .. domain_size - 1 (each input exactly once)."""
    size = _domain_size_of(oracle)
    if size > MAX_DENSE_DOMAIN:
        raise ValueError(f"domain of size {size} exceeds MAX_DENSE_DOMAIN = {MAX_DENSE_DOMAIN} for dense exact "
                         f"evaluation; use turing.algorithms.structured for affine or linear oracles")
    values = []
    for x in range(size):
        value = oracle(x)  # type: ignore[operator]
        if isinstance(value, bool):
            value = 1 if value else 0
        if not _is_int(value):
            raise ValueError(f"oracle returned {value!r} at x = {x}; values must be ints")
        values.append(value)
    return tuple(values)


def boolean_table(oracle: object) -> tuple[int, ...]:
    """Evaluate a Boolean oracle on its whole domain, checking every value is 0 or 1."""
    values = function_table(oracle)
    for x, value in enumerate(values):
        if value not in (0, 1):
            raise ValueError(f"Boolean oracle returned {value} at x = {x}; expected 0 or 1")
    return values


def require_constant_or_balanced(table: Sequence[int]) -> str:
    """Return 'constant' or 'balanced'; raise ValueError if the Deutsch-Jozsa promise fails."""
    size = len(table)
    ones = sum(table)
    if ones in (0, size):
        return "constant"
    if 2 * ones == size:
        return "balanced"
    raise ValueError(f"Deutsch-Jozsa promise violated: the oracle has {ones} ones among {size} inputs, "
                     f"so it is neither constant nor balanced")


def require_affine(table: Sequence[int], n: int) -> tuple[int, int]:
    """Return (s, b) with f(x) = s.x xor b for all x; raise ValueError otherwise."""
    if len(table) != 1 << n:
        raise ValueError(f"table has {len(table)} entries, expected 2**{n}")
    b = table[0]
    s = 0
    for i in range(n):
        s |= (table[1 << i] ^ b) << i
    for x, value in enumerate(table):
        if value != _parity(s & x) ^ b:
            raise ValueError(f"oracle is not of the form x -> s.x xor b: f({x}) = {value} but s.x xor b = "
                             f"{_parity(s & x) ^ b} for s = {s}, b = {b}")
    return s, b


def require_simon_promise(table: Sequence[int], n: int) -> int:
    """Return s with f(x) = f(y) iff y in {x, x xor s}; raise ValueError otherwise."""
    if len(table) != 1 << n:
        raise ValueError(f"table has {len(table)} entries, expected 2**{n}")
    classes: dict[int, list[int]] = {}
    for x, value in enumerate(table):
        classes.setdefault(value, []).append(x)
    if all(len(members) == 1 for members in classes.values()):
        return 0
    partner = classes[table[0]]
    if len(partner) != 2:
        raise ValueError(f"Simon promise violated: f(0) is shared by {len(partner)} inputs {partner[:4]}...")
    s = partner[1]
    for value, members in classes.items():
        if len(members) != 2 or members[0] ^ members[1] != s:
            raise ValueError(f"Simon promise violated: inputs {members[:4]} share the value {value}, "
                             f"which is not a pair {{x, x xor {s}}}")
    return s


class FunctionOracle:
    """A finite oracle given by its table of integer values (validated at construction)."""

    __slots__ = ("_table",)

    def __init__(self, values: Iterable[int]) -> None:
        table = []
        for x, value in enumerate(values):
            if isinstance(value, bool):
                value = 1 if value else 0
            if not _is_int(value):
                raise ValueError(f"oracle value at x = {x} must be an int, got {value!r}")
            table.append(value)
        if not table:
            raise ValueError("an oracle needs a non-empty domain")
        self._table = tuple(table)
        self._validate()

    def _validate(self) -> None:
        return None

    @classmethod
    def from_function(cls, domain_size: int, function: Callable[[int], int]) -> "FunctionOracle":
        if not _is_int(domain_size) or domain_size < 1:
            raise ValueError(f"domain_size must be a positive int, got {domain_size!r}")
        return cls(function(x) for x in range(domain_size))

    @classmethod
    def from_dict(cls, mapping: Mapping[int, int]) -> "FunctionOracle":
        keys = sorted(mapping)
        if keys != list(range(len(keys))):
            raise ValueError("dict oracle keys must be exactly 0 .. domain_size - 1")
        return cls(mapping[x] for x in keys)

    @classmethod
    def from_list(cls, values: Sequence[int]) -> "FunctionOracle":
        return cls(values)

    @property
    def domain_size(self) -> int:
        return len(self._table)

    @property
    def table(self) -> tuple[int, ...]:
        return self._table

    def __call__(self, x: int) -> int:
        if not _is_int(x) or not 0 <= x < len(self._table):
            raise ValueError(f"oracle input {x!r} outside 0 .. {len(self._table) - 1}")
        return self._table[x]

    def __repr__(self) -> str:
        return f"{type(self).__name__}(domain_size={len(self._table)})"


class BooleanOracle(FunctionOracle):
    """A finite oracle whose values are 0 or 1."""

    __slots__ = ()

    def _validate(self) -> None:
        for x, value in enumerate(self._table):
            if value not in (0, 1):
                raise ValueError(f"Boolean oracle value at x = {x} is {value}; expected 0 or 1")

    @classmethod
    def from_predicate(cls, domain_size: int, predicate: Callable[[int], object]) -> "BooleanOracle":
        if not _is_int(domain_size) or domain_size < 1:
            raise ValueError(f"domain_size must be a positive int, got {domain_size!r}")
        values = []
        for x in range(domain_size):
            result = predicate(x)
            if not isinstance(result, bool) and result not in (0, 1):
                raise ValueError(f"predicate returned {result!r} at x = {x}; expected a bool, 0 or 1")
            values.append(1 if result else 0)
        return cls(values)

    @classmethod
    def from_marked(cls, domain_size: int, marked: Iterable[int]) -> "BooleanOracle":
        if not _is_int(domain_size) or domain_size < 1:
            raise ValueError(f"domain_size must be a positive int, got {domain_size!r}")
        values = [0] * domain_size
        for x in marked:
            if not _is_int(x) or not 0 <= x < domain_size:
                raise ValueError(f"marked item {x!r} outside 0 .. {domain_size - 1}")
            values[x] = 1
        return cls(values)


class AffineOracle:
    """Boolean oracle f(x) = a.x xor b on n-bit inputs, with its GF(2) structure exposed."""

    __slots__ = ("_n", "_a", "_b")

    def __init__(self, num_inputs: int, a: int, b: int = 0) -> None:
        if not _is_int(num_inputs) or num_inputs < 1:
            raise ValueError(f"num_inputs must be a positive int, got {num_inputs!r}")
        if not _is_int(a) or a < 0 or a.bit_length() > num_inputs:
            raise ValueError(f"a must be a non-negative int with at most {num_inputs} bits")
        if b not in (0, 1) or isinstance(b, bool):
            raise ValueError(f"b must be 0 or 1, got {b!r}")
        self._n = num_inputs
        self._a = a
        self._b = b

    @property
    def num_inputs(self) -> int:
        return self._n

    @property
    def a(self) -> int:
        return self._a

    @property
    def b(self) -> int:
        return self._b

    @property
    def domain_size(self) -> int:
        return 1 << self._n

    def is_constant(self) -> bool:
        return self._a == 0

    def __call__(self, x: int) -> int:
        if not _is_int(x) or not 0 <= x < 1 << self._n:
            raise ValueError(f"oracle input outside 0 .. 2**{self._n} - 1")
        return _parity(self._a & x) ^ self._b

    def __repr__(self) -> str:
        return f"AffineOracle(num_inputs={self._n})"


class LinearOracle:
    """Oracle f(x) = A x over GF(2); output bit j is the parity of rows[j] & x."""

    __slots__ = ("_n", "_rows")

    def __init__(self, num_inputs: int, rows: Sequence[int]) -> None:
        if not _is_int(num_inputs) or num_inputs < 1:
            raise ValueError(f"num_inputs must be a positive int, got {num_inputs!r}")
        checked = []
        for j, row in enumerate(rows):
            if not _is_int(row) or row < 0 or row.bit_length() > num_inputs:
                raise ValueError(f"row {j} must be a non-negative int with at most {num_inputs} bits")
            checked.append(row)
        if not checked:
            raise ValueError("a linear oracle needs at least one output row")
        self._n = num_inputs
        self._rows = tuple(checked)

    @property
    def num_inputs(self) -> int:
        return self._n

    @property
    def num_outputs(self) -> int:
        return len(self._rows)

    @property
    def rows(self) -> tuple[int, ...]:
        return self._rows

    @property
    def domain_size(self) -> int:
        return 1 << self._n

    def __call__(self, x: int) -> int:
        if not _is_int(x) or not 0 <= x < 1 << self._n:
            raise ValueError(f"oracle input outside 0 .. 2**{self._n} - 1")
        value = 0
        for j, row in enumerate(self._rows):
            value |= _parity(row & x) << j
        return value

    def __repr__(self) -> str:
        return f"LinearOracle(num_inputs={self._n}, num_outputs={len(self._rows)})"
