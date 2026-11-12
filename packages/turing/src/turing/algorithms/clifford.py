"""Exact stabilizer-circuit evaluation: the Aaronson-Gottesman tableau over GF(2).

An n-qubit stabilizer state is described by 2n Pauli generators: destabilizers
D_0 .. D_(n-1) (rows 0 .. n-1) and stabilizers S_0 .. S_(n-1) (rows n .. 2n-1).
Each row is a signed Hermitian Pauli (-1)^r i^|x & z| X^x Z^z, with x and z bit
vectors over the qubits (Y = i X Z). The tableau is bit-packed in Python ints:

* for every qubit q, column bitsets X[q] and Z[q] over the 2n rows (bit j is
  row j), so every gate costs a constant number of big-int operations;
* the phase bits of all rows form one int bitset;
* row bitsets x_j and z_j over the qubits are extracted on demand (and cached
  until the next gate) to multiply generators. The product phase uses popcounts:
  P(x1, z1) P(x2, z2) = i^e P(x1 ^ x2, z1 ^ z2) with
  e = |x1 & z1| + |x2 & z2| + 2 |z1 & x2| - |(x1 ^ x2) & (z1 ^ z2)|  (mod 4).

The tableau occupies 2n(2n + 1) bits (about 3 MiB at n = 2,500). A Z-basis
measurement is classified exactly as deterministic (probability 1) or uniform
(probability 1/2 each). Nothing is random: for a uniform outcome the caller
passes choose=0 or choose=1 and the state collapses to that branch. The number
of qubits is always the size of the register the circuit allocates.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping, Optional, Sequence

from .gf2 import AffineSubspace, rank, solve_affine

__all__ = [
    "CliffordCircuit",
    "MeasurementOutcome",
    "PauliOperator",
    "StabilizerTableau",
    "ghz_circuit",
    "paulis_commute",
]


def _check_int(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an int")
    return value


def _product_exponent(x1: int, z1: int, x2: int, z2: int) -> int:
    """e (mod 4) with P(x1, z1) P(x2, z2) = i^e P(x1 ^ x2, z1 ^ z2)."""
    x3 = x1 ^ x2
    z3 = z1 ^ z2
    return ((x1 & z1).bit_count() + (x2 & z2).bit_count() + 2 * (z1 & x2).bit_count()
            - (x3 & z3).bit_count()) & 3


@dataclass(frozen=True)
class PauliOperator:
    """The Hermitian Pauli (-1)^sign i^|x & z| X^x Z^z; bit q of x and z refers to qubit q."""

    num_qubits: int
    x: int
    z: int
    sign: int = 0

    def __post_init__(self) -> None:
        for name in ("num_qubits", "x", "z", "sign"):
            _check_int(getattr(self, name), name)
        if self.num_qubits < 1:
            raise ValueError("num_qubits must be positive")
        limit = 1 << self.num_qubits
        if not 0 <= self.x < limit or not 0 <= self.z < limit:
            raise ValueError("x and z must be bit vectors over num_qubits qubits")
        if self.sign not in (0, 1):
            raise ValueError("sign must be 0 (+) or 1 (-)")

    @classmethod
    def from_label(cls, label: str) -> "PauliOperator":
        """Parse labels such as '+XZI' or '-YY'; character q acts on qubit q."""
        sign = 0
        body = label
        if body[:1] in ("+", "-"):
            sign = 1 if body[0] == "-" else 0
            body = body[1:]
        if not body:
            raise ValueError("empty Pauli label")
        x = z = 0
        for q, symbol in enumerate(body):
            if symbol in ("X", "Y"):
                x |= 1 << q
            if symbol in ("Z", "Y"):
                z |= 1 << q
            if symbol not in ("I", "X", "Y", "Z"):
                raise ValueError(f"invalid Pauli symbol {symbol!r}")
        return cls(len(body), x, z, sign)

    @classmethod
    def from_sparse(cls, num_qubits: int, terms: Mapping[int, str], sign: int = 0) -> "PauliOperator":
        """Build a Pauli from {qubit: 'X' | 'Y' | 'Z'} without materialising a label."""
        x = z = 0
        for q, symbol in terms.items():
            _check_int(q, "qubit")
            if not 0 <= q < num_qubits:
                raise ValueError(f"qubit {q} outside 0 .. {num_qubits - 1}")
            if symbol not in ("X", "Y", "Z"):
                raise ValueError(f"invalid Pauli symbol {symbol!r}")
            if symbol in ("X", "Y"):
                x |= 1 << q
            if symbol in ("Z", "Y"):
                z |= 1 << q
        return cls(num_qubits, x, z, sign)

    def label(self) -> str:
        symbols = []
        for q in range(self.num_qubits):
            bx = (self.x >> q) & 1
            bz = (self.z >> q) & 1
            symbols.append("Y" if bx and bz else "X" if bx else "Z" if bz else "I")
        return ("-" if self.sign else "+") + "".join(symbols)

    @property
    def weight(self) -> int:
        return (self.x | self.z).bit_count()

    def commutes_with(self, other: "PauliOperator") -> bool:
        return paulis_commute(self, other)

    def __mul__(self, other: "PauliOperator") -> "PauliOperator":
        if not isinstance(other, PauliOperator) or other.num_qubits != self.num_qubits:
            return NotImplemented
        e = _product_exponent(self.x, self.z, other.x, other.z)
        if e & 1:
            raise ValueError("the product of anticommuting Paulis is not Hermitian")
        return PauliOperator(self.num_qubits, self.x ^ other.x, self.z ^ other.z,
                             self.sign ^ other.sign ^ (e >> 1))


def paulis_commute(p: PauliOperator, q: PauliOperator) -> bool:
    """Exact commutation test: the symplectic product parity is 0."""
    return not (((p.x & q.z) ^ (p.z & q.x)).bit_count() & 1)


@dataclass(frozen=True)
class MeasurementOutcome:
    qubit: int
    outcome: int
    probability: Fraction
    deterministic: bool


class StabilizerTableau:
    """Bit-packed stabilizer tableau of a register of qubits, initialised to |0...0>."""

    __slots__ = ("_x", "_z", "_r", "_rows_cache")

    def __init__(self, num_qubits: int) -> None:
        _check_int(num_qubits, "num_qubits")
        if num_qubits < 1:
            raise ValueError("a register needs at least one qubit")
        n = num_qubits
        self._x = [1 << q for q in range(n)]
        self._z = [1 << (n + q) for q in range(n)]
        self._r = 0
        self._rows_cache = None

    @property
    def num_qubits(self) -> int:
        """Number of qubits, read from the allocated tableau columns."""
        return len(self._x)

    @property
    def tableau_bits(self) -> int:
        """Size of the tableau, 2n(2n + 1) bits (x, z and phase for 2n rows)."""
        n = len(self._x)
        return 2 * n * (2 * n + 1)

    def copy(self) -> "StabilizerTableau":
        clone = object.__new__(StabilizerTableau)
        clone._x = list(self._x)
        clone._z = list(self._z)
        clone._r = self._r
        clone._rows_cache = self._rows_cache
        return clone

    def _qubit(self, qubit: int) -> int:
        _check_int(qubit, "qubit")
        if not 0 <= qubit < len(self._x):
            raise ValueError(f"qubit {qubit} outside the register 0 .. {len(self._x) - 1}")
        return qubit

    # -- gates (Heisenberg update of every generator, constant big-int work) ------

    def h(self, qubit: int) -> "StabilizerTableau":
        q = self._qubit(qubit)
        xc, zc = self._x[q], self._z[q]
        self._r ^= xc & zc
        self._x[q], self._z[q] = zc, xc
        self._rows_cache = None
        return self

    def s(self, qubit: int) -> "StabilizerTableau":
        q = self._qubit(qubit)
        xc = self._x[q]
        self._r ^= xc & self._z[q]
        self._z[q] ^= xc
        self._rows_cache = None
        return self

    def x(self, qubit: int) -> "StabilizerTableau":
        q = self._qubit(qubit)
        self._r ^= self._z[q]
        self._rows_cache = None
        return self

    def z(self, qubit: int) -> "StabilizerTableau":
        q = self._qubit(qubit)
        self._r ^= self._x[q]
        self._rows_cache = None
        return self

    def y(self, qubit: int) -> "StabilizerTableau":
        q = self._qubit(qubit)
        self._r ^= self._x[q] ^ self._z[q]
        self._rows_cache = None
        return self

    def cnot(self, control: int, target: int) -> "StabilizerTableau":
        c = self._qubit(control)
        t = self._qubit(target)
        if c == t:
            raise ValueError("CNOT needs distinct control and target qubits")
        xa, za, xb, zb = self._x[c], self._z[c], self._x[t], self._z[t]
        self._r ^= xa & zb & ~(xb ^ za)
        self._x[t] = xb ^ xa
        self._z[c] = za ^ zb
        self._rows_cache = None
        return self

    def apply(self, circuit: "CliffordCircuit") -> "StabilizerTableau":
        if not isinstance(circuit, CliffordCircuit):
            raise TypeError("circuit must be a CliffordCircuit")
        if circuit.num_qubits != self.num_qubits:
            raise ValueError(f"circuit allocates {circuit.num_qubits} qubits, tableau has {self.num_qubits}")
        for name, qubits in circuit.operations:
            getattr(self, name)(*qubits)
        return self

    # -- row access ------------------------------------------------------------------

    def _extract_rows(self, start: int) -> tuple[tuple[int, ...], tuple[int, ...], int]:
        n = len(self._x)
        window = ((1 << n) - 1) << start
        xs = [0] * n
        zs = [0] * n
        for columns, rows in ((self._x, xs), (self._z, zs)):
            for q, column in enumerate(columns):
                bits = (column & window) >> start
                if not bits:
                    continue
                qubit_bit = 1 << q
                while bits:
                    low = bits & -bits
                    rows[low.bit_length() - 1] |= qubit_bit
                    bits ^= low
        return tuple(xs), tuple(zs), (self._r & window) >> start

    def _stabilizer_rows(self) -> tuple[tuple[int, ...], tuple[int, ...], int]:
        cached = self._rows_cache
        if cached is None:
            cached = self._extract_rows(len(self._x))
            self._rows_cache = cached
        return cached

    def _stabilizer_product(self, selected: int) -> tuple[int, int, int]:
        """(sign, x, z) of the product of the stabilizer rows indexed by the bits of ``selected``."""
        xs, zs, signs = self._stabilizer_rows()
        sign = x = z = 0
        while selected:
            low = selected & -selected
            j = low.bit_length() - 1
            selected ^= low
            xj, zj = xs[j], zs[j]
            e = _product_exponent(x, z, xj, zj)
            if e & 1:
                raise ArithmeticError("stabilizer generators must commute")
            sign ^= ((signs >> j) & 1) ^ (e >> 1)
            x ^= xj
            z ^= zj
        return sign, x, z

    def stabilizer_generators(self) -> tuple[PauliOperator, ...]:
        n = len(self._x)
        xs, zs, signs = self._stabilizer_rows()
        return tuple(PauliOperator(n, xs[j], zs[j], (signs >> j) & 1) for j in range(n))

    def destabilizer_generators(self) -> tuple[PauliOperator, ...]:
        n = len(self._x)
        xs, zs, signs = self._extract_rows(0)
        return tuple(PauliOperator(n, xs[j], zs[j], (signs >> j) & 1) for j in range(n))

    # -- exact checks ---------------------------------------------------------------

    def _anticommutation_mask(self, x: int, z: int) -> int:
        """Bit j set iff row j anticommutes with P(x, z); constant work per qubit in the support."""
        mask = 0
        bits = z
        while bits:
            low = bits & -bits
            mask ^= self._x[low.bit_length() - 1]
            bits ^= low
        bits = x
        while bits:
            low = bits & -bits
            mask ^= self._z[low.bit_length() - 1]
            bits ^= low
        return mask

    def stabilizers_commute(self) -> bool:
        """True iff the n stabilizer generators pairwise commute (symplectic Gram matrix is 0)."""
        n = len(self._x)
        xs, zs, _ = self._stabilizer_rows()
        for j in range(n):
            if self._anticommutation_mask(xs[j], zs[j]) >> n:
                return False
        return True

    def is_valid(self) -> bool:
        """Full symplectic check: D_j anticommutes with S_j only; every other pair commutes."""
        n = len(self._x)
        for start in (0, n):
            xs, zs, _ = self._extract_rows(start)
            for j in range(n):
                expected = 1 << (j + n - start)
                if self._anticommutation_mask(xs[j], zs[j]) != expected:
                    return False
        return True

    def stabilizer_rank(self) -> int:
        """GF(2) rank of the n x 2n stabilizer matrix [x | z]."""
        n = len(self._x)
        xs, zs, _ = self._stabilizer_rows()
        return rank(x | (z << n) for x, z in zip(xs, zs))

    def stabilizer_sign(self, pauli: PauliOperator) -> Optional[int]:
        """Return s with (-1)^s P(x, z) in the stabilizer group, or None if neither sign is.

        P commutes with every stabilizer exactly when it lies in the group up to
        sign; it is then the product of the stabilizers S_j whose destabilizers
        D_j anticommute with P.
        """
        n = len(self._x)
        if not isinstance(pauli, PauliOperator) or pauli.num_qubits != n:
            raise ValueError(f"expected a PauliOperator on {n} qubits")
        mask = self._anticommutation_mask(pauli.x, pauli.z)
        if mask >> n:
            return None
        sign, x, z = self._stabilizer_product(mask)
        if x != pauli.x or z != pauli.z:
            raise ArithmeticError("tableau invariant violated: product does not reproduce the Pauli")
        return sign

    def contains(self, pauli: PauliOperator) -> bool:
        """True iff the signed Pauli itself belongs to the stabilizer group."""
        sign = self.stabilizer_sign(pauli)
        return sign is not None and sign == pauli.sign

    # -- measurement ------------------------------------------------------------------

    def is_deterministic(self, qubit: int) -> bool:
        """True iff no stabilizer has X or Y on the qubit (the Z outcome has probability 1)."""
        q = self._qubit(qubit)
        return not (self._x[q] >> len(self._x))

    def _deterministic_outcome(self, q: int) -> int:
        n = len(self._x)
        selected = self._x[q] & ((1 << n) - 1)
        sign, x, z = self._stabilizer_product(selected)
        if x or z != 1 << q:
            raise ArithmeticError("tableau invariant violated: expected +/- Z on the measured qubit")
        return sign

    def probabilities(self, qubit: int) -> dict[int, Fraction]:
        """Exact Z-basis outcome probabilities of one qubit (no collapse)."""
        q = self._qubit(qubit)
        if self._x[q] >> len(self._x):
            return {0: Fraction(1, 2), 1: Fraction(1, 2)}
        outcome = self._deterministic_outcome(q)
        return {outcome: Fraction(1), 1 - outcome: Fraction(0)}

    def measure(self, qubit: int, choose: Optional[int] = None) -> MeasurementOutcome:
        """Measure Z on a qubit; a uniform outcome requires choose=0 or choose=1."""
        q = self._qubit(qubit)
        if choose is not None and (choose not in (0, 1) or isinstance(choose, bool)):
            raise ValueError("choose must be None, 0 or 1")
        n = len(self._x)
        hits = self._x[q] >> n
        if hits:
            if choose is None:
                raise ValueError(f"the outcome of qubit {q} is uniform (probability 1/2 each); "
                                 f"pass choose=0 or choose=1 to select the branch")
            p = n + (hits & -hits).bit_length() - 1
            self._collapse(q, p, choose)
            return MeasurementOutcome(q, choose, Fraction(1, 2), False)
        outcome = self._deterministic_outcome(q)
        if choose is not None and choose != outcome:
            raise ValueError(f"outcome {choose} of qubit {q} has probability 0")
        return MeasurementOutcome(q, outcome, Fraction(1), True)

    def _collapse(self, q: int, p: int, outcome: int) -> None:
        n = len(self._x)
        xcols, zcols = self._x, self._z
        pbit = 1 << p
        targets = xcols[q] & ~pbit
        # Row i := S_p * row i for every other row with an X or Y on qubit q (Aaronson-Gottesman
        # rowsum), done for all rows at once: the per-row phase exponent sum_c g(...) is kept in
        # a bit-sliced mod-4 counter (lo, hi) over the rows.
        lo = hi = 0
        support = []
        for c in range(n):
            xp = (xcols[c] >> p) & 1
            zp = (zcols[c] >> p) & 1
            if not (xp or zp):
                continue
            support.append((c, xp, zp))
            xt = xcols[c] & targets
            zt = zcols[c] & targets
            if xp and zp:
                plus, minus = zt & ~xt, xt & ~zt
            elif xp:
                plus, minus = xt & zt, zt & ~xt
            else:
                plus, minus = xt & ~zt, xt & zt
            carry = lo & plus
            lo ^= plus
            hi ^= carry
            borrow = minus & ~lo
            lo ^= minus
            hi ^= borrow
        flips = hi & targets
        if (self._r >> p) & 1:
            flips ^= targets
        self._r ^= flips
        for c, xp, zp in support:
            if xp:
                xcols[c] ^= targets
            if zp:
                zcols[c] ^= targets
        # Destabilizer p - n := S_p; then S_p := (-1)^outcome Z_q.
        d = p - n
        dbit = 1 << d
        keep = ~(dbit | pbit)
        for c in range(n):
            xc = xcols[c]
            zc = zcols[c]
            xcols[c] = (xc & keep) | (((xc >> p) & 1) << d)
            zcols[c] = (zc & keep) | (((zc >> p) & 1) << d)
        zcols[q] |= pbit
        r = self._r
        r = (r & keep) | (((r >> p) & 1) << d)
        if outcome:
            r |= pbit
        self._r = r
        self._rows_cache = None

    def outcome_support(self, qubits: Sequence[int]) -> AffineSubspace:
        """Exact joint Z-basis outcome distribution of ``qubits``.

        The distribution is uniform over the returned affine subspace of
        GF(2)^len(qubits) (bit i of an outcome is qubit qubits[i]), with
        probability 2^-dimension for each element. The constraints are the
        stabilizer-group elements that are Z-type on ``qubits`` and the identity
        elsewhere, found by GF(2) elimination of the generators with exact
        popcount phases.
        """
        n = len(self._x)
        order = [self._qubit(q) for q in qubits]
        if len(set(order)) != len(order):
            raise ValueError("qubits must be distinct")
        position = {q: i for i, q in enumerate(order)}
        selected = 0
        for q in order:
            selected |= 1 << q
        others = ((1 << n) - 1) ^ selected
        xs, zs, signs = self._stabilizer_rows()
        pivots: dict[int, tuple[int, int, int]] = {}
        constraints = []
        for j in range(n):
            sign, x, z = (signs >> j) & 1, xs[j], zs[j]
            key = x | ((z & others) << n)
            while key:
                lead = key.bit_length() - 1
                pivot = pivots.get(lead)
                if pivot is None:
                    pivots[lead] = (sign, x, z)
                    break
                psign, px, pz = pivot
                e = _product_exponent(px, pz, x, z)
                if e & 1:
                    raise ArithmeticError("stabilizer generators must commute")
                sign ^= psign ^ (e >> 1)
                x ^= px
                z ^= pz
                key = x | ((z & others) << n)
            if not key:
                vector = 0
                bits = z
                while bits:
                    low = bits & -bits
                    vector |= 1 << position[low.bit_length() - 1]
                    bits ^= low
                constraints.append((vector, sign))
        space = solve_affine(constraints, len(order))
        if space is None:
            raise ArithmeticError("inconsistent stabilizer constraints")
        return space


class CliffordCircuit:
    """A gate list over a register allocated with :meth:`allocate`."""

    __slots__ = ("_operations", "_width")

    def __init__(self) -> None:
        self._operations: list[tuple[str, tuple[int, ...]]] = []
        self._width = 0

    def allocate(self, count: int) -> range:
        """Allocate ``count`` new qubits and return their indices."""
        _check_int(count, "count")
        if count < 1:
            raise ValueError("allocate at least one qubit")
        start = self._width
        self._width += count
        return range(start, self._width)

    @property
    def num_qubits(self) -> int:
        """Size of the register this circuit has allocated."""
        return self._width

    @property
    def operations(self) -> tuple[tuple[str, tuple[int, ...]], ...]:
        return tuple(self._operations)

    def __len__(self) -> int:
        return len(self._operations)

    def _check(self, qubit: int) -> int:
        _check_int(qubit, "qubit")
        if not 0 <= qubit < self._width:
            raise ValueError(f"qubit {qubit} has not been allocated (register size {self._width})")
        return qubit

    def h(self, qubit: int) -> "CliffordCircuit":
        self._operations.append(("h", (self._check(qubit),)))
        return self

    def s(self, qubit: int) -> "CliffordCircuit":
        self._operations.append(("s", (self._check(qubit),)))
        return self

    def x(self, qubit: int) -> "CliffordCircuit":
        self._operations.append(("x", (self._check(qubit),)))
        return self

    def y(self, qubit: int) -> "CliffordCircuit":
        self._operations.append(("y", (self._check(qubit),)))
        return self

    def z(self, qubit: int) -> "CliffordCircuit":
        self._operations.append(("z", (self._check(qubit),)))
        return self

    def cnot(self, control: int, target: int) -> "CliffordCircuit":
        c = self._check(control)
        t = self._check(target)
        if c == t:
            raise ValueError("CNOT needs distinct control and target qubits")
        self._operations.append(("cnot", (c, t)))
        return self

    def evaluate(self) -> StabilizerTableau:
        """Exact evaluation from |0...0> on the allocated register."""
        if self._width == 0:
            raise ValueError("allocate a register before evaluating")
        return StabilizerTableau(self._width).apply(self)


def ghz_circuit(width: int) -> CliffordCircuit:
    """GHZ preparation on a freshly allocated register: H on qubit 0, then a CNOT chain."""
    circuit = CliffordCircuit()
    register = circuit.allocate(width)
    circuit.h(register[0])
    for q in register[:-1]:
        circuit.cnot(q, q + 1)
    return circuit
