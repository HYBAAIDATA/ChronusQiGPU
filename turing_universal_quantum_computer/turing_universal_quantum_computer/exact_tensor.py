"""Kellogg exact tensor substrate — the canonical Q(sqrt(2)) + i Q(sqrt(2)) witness.

This module is the project's canonical exact-algebra substrate for finite
state vectors.  It hosts:

* ``Qsqrt2`` — the real ordered field Q(sqrt(2)), exact ``Fraction``
  coefficients, exact sign without floats.
* ``F4`` — the field Q(sqrt(2)) + i Q(sqrt(2)) = Q(zeta_8), stored as four
  ``Fraction`` coefficients on {1, sqrt(2), i, i*sqrt(2)}.
* ``ExactStateVector`` — the exact 2^n state vector with fail-closed
  resource bounds, exact Born weights, deterministic measurement, and
  declared Clifford+T gates.  Unsupported Hamiltonian exponentials fail
  closed; no floating amplitudes, truncation, or Monte-Carlo sampling.
* ``ExactTOETensor`` — the TOE exact-witness adapter: observations are bound
  to a canonical digest, encoded as an exact basis state, and evolved only
  through declared operations.

It is the canonical in-repo replacement for the platform's
``mla1517.quantum`` surface and is importable by every subsystem.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Iterable, Mapping, Sequence

THEOREM_PROVEN = False


# ---------------------------------------------------------------------------
# Real ordered field Q(sqrt(2)): a + b*sqrt(2) with exact rational sign.


@dataclass(frozen=True)
class Qsqrt2:
    a: Fraction = Fraction(0)
    b: Fraction = Fraction(0)

    def __init__(self, a: int | Fraction = 0, b: int | Fraction = 0):
        object.__setattr__(self, "a", Fraction(a))
        object.__setattr__(self, "b", Fraction(b))

    def __add__(self, other: "Qsqrt2") -> "Qsqrt2":
        return Qsqrt2(self.a + other.a, self.b + other.b)

    def __radd__(self, other: object) -> "Qsqrt2":
        return self if other == 0 else NotImplemented

    def __sub__(self, other: "Qsqrt2") -> "Qsqrt2":
        return Qsqrt2(self.a - other.a, self.b - other.b)

    def __neg__(self) -> "Qsqrt2":
        return Qsqrt2(-self.a, -self.b)

    def __mul__(self, other: "Qsqrt2") -> "Qsqrt2":
        return Qsqrt2(self.a * other.a + 2 * self.b * other.b, self.a * other.b + self.b * other.a)

    def __truediv__(self, other: "Qsqrt2") -> "Qsqrt2":
        denominator = other.a * other.a - 2 * other.b * other.b
        if denominator == 0:
            raise ZeroDivisionError("Q(sqrt(2)) division by zero")
        return Qsqrt2(
            (self.a * other.a - 2 * self.b * other.b) / denominator,
            (self.b * other.a - self.a * other.b) / denominator,
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Qsqrt2) and self.a == other.a and self.b == other.b

    def sign(self) -> int:
        """Sign under the canonical embedding a + b*sqrt(2), exactly."""
        if self.a == 0 and self.b == 0:
            return 0
        if self.b == 0:
            return 1 if self.a > 0 else -1
        if self.a == 0:
            return 1 if self.b > 0 else -1
        if self.a > 0 and self.b > 0:
            return 1
        if self.a < 0 and self.b < 0:
            return -1
        # Opposite signs: compare |a|^2 and 2|b|^2 without a float.
        left = self.a * self.a
        right = 2 * self.b * self.b
        if left == right:
            return 0
        if self.a > 0:
            return 1 if left > right else -1
        return -1 if left > right else 1

    def compare(self, other: "Qsqrt2") -> int:
        """Exact three-way comparison in the ordered real embedding."""
        return (self - other).sign()

    def to_float(self) -> float:
        """Project to IEEE-754. Explicit exact→float boundary crossing; the
        result can never be promoted back into the exact plane."""
        return float(self.a) + float(self.b) * math.sqrt(2.0)


# ---------------------------------------------------------------------------
# Field F4 = Q(sqrt(2)) + i Q(sqrt(2)): (a,b,c,d) = (a+b*sqrt(2)) + i(c+d*sqrt(2)).


@dataclass(frozen=True)
class F4:
    """(a,b,c,d) = (a+b*sqrt(2)) + i(c+d*sqrt(2))."""

    a: Fraction = Fraction(0)
    b: Fraction = Fraction(0)
    c: Fraction = Fraction(0)
    d: Fraction = Fraction(0)

    def __init__(self, a=0, b=0, c=0, d=0):
        object.__setattr__(self, "a", Fraction(a))
        object.__setattr__(self, "b", Fraction(b))
        object.__setattr__(self, "c", Fraction(c))
        object.__setattr__(self, "d", Fraction(d))

    @property
    def real(self) -> Qsqrt2:
        return Qsqrt2(self.a, self.b)

    @property
    def imag(self) -> Qsqrt2:
        return Qsqrt2(self.c, self.d)

    def __add__(self, other: "F4") -> "F4":
        return F4(self.a + other.a, self.b + other.b, self.c + other.c, self.d + other.d)

    def __radd__(self, other: object) -> "F4":
        return self if other == 0 else NotImplemented

    def __sub__(self, other: "F4") -> "F4":
        return F4(self.a - other.a, self.b - other.b, self.c - other.c, self.d - other.d)

    def __neg__(self) -> "F4":
        return F4(-self.a, -self.b, -self.c, -self.d)

    def __mul__(self, other: "F4") -> "F4":
        uu = self.real * other.real
        vv = self.imag * other.imag
        uv = self.real * other.imag
        vu = self.imag * other.real
        real = uu - vv
        imag = uv + vu
        return F4(real.a, real.b, imag.a, imag.b)

    def __truediv__(self, other: "F4") -> "F4":
        return self * other.inverse()

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, F4)
            and self.a == other.a
            and self.b == other.b
            and self.c == other.c
            and self.d == other.d
        )

    def conjugate(self) -> "F4":
        return F4(self.a, self.b, -self.c, -self.d)

    def norm2(self) -> Qsqrt2:
        value = self * self.conjugate()
        if value.c != 0 or value.d != 0:
            raise ValueError("complex norm unexpectedly has an imaginary component")
        return value.real

    def inverse(self) -> "F4":
        norm = self.norm2()
        denominator = norm.a * norm.a - 2 * norm.b * norm.b
        if denominator == 0:
            raise ZeroDivisionError("F4 division by zero")
        reciprocal = Qsqrt2(norm.a / denominator, -norm.b / denominator)
        return F4(
            self.conjugate().real.a * reciprocal.a + 2 * self.conjugate().real.b * reciprocal.b,
            self.conjugate().real.a * reciprocal.b + self.conjugate().real.b * reciprocal.a,
            self.conjugate().imag.a * reciprocal.a + 2 * self.conjugate().imag.b * reciprocal.b,
            self.conjugate().imag.a * reciprocal.b + self.conjugate().imag.b * reciprocal.a,
        )

    def sign_sigma(self) -> int:
        if self.c != 0 or self.d != 0:
            raise TypeError("sigma order is declared for real-channel values only")
        return self.real.sign()

    def to_json(self) -> list[list[int]]:
        return [_fraction_json(v) for v in (self.a, self.b, self.c, self.d)]

    @classmethod
    def from_json(cls, value: Sequence[Sequence[int]]) -> "F4":
        return cls(*(_fraction_from_json(v) for v in value))


ZERO = F4()
ONE = F4(1)
MINUS_ONE = F4(-1)
I_UNIT = F4(0, 0, 1)
SQRT2 = F4(0, 1)
ZETA8 = F4(0, Fraction(1, 2), 0, Fraction(1, 2))  # exp(i*pi/4) = (1+i)/sqrt(2)

_QZERO = Qsqrt2()
_QONE = Qsqrt2(1)
_SQRT2_INV = Qsqrt2(0, Fraction(1, 2))


def _fraction_json(value: Fraction) -> list[int]:
    return [value.numerator, value.denominator]


def _fraction_from_json(value: Sequence[int]) -> Fraction:
    return Fraction(int(value[0]), int(value[1]))


# ---------------------------------------------------------------------------
# Exact finite state-vector algebra over F4.


class ExactResourceError(MemoryError):
    """Exact state-vector resource bound exceeded; no degraded path is allowed."""


ExactGate = tuple[tuple[F4, F4], tuple[F4, F4]]
GATE_I: ExactGate = ((ONE, ZERO), (ZERO, ONE))
GATE_X: ExactGate = ((ZERO, ONE), (ONE, ZERO))
GATE_Y: ExactGate = ((ZERO, -I_UNIT), (I_UNIT, ZERO))
GATE_Z: ExactGate = ((ONE, ZERO), (ZERO, -ONE))
GATE_H: ExactGate = (
    (F4(0, Fraction(1, 2)), F4(0, Fraction(1, 2))),
    (F4(0, Fraction(1, 2)), F4(0, -Fraction(1, 2))),
)
GATE_S: ExactGate = ((ONE, ZERO), (ZERO, I_UNIT))
GATE_T: ExactGate = ((ONE, ZERO), (ZERO, ZETA8))
GATE_S_DG: ExactGate = ((ONE, ZERO), (ZERO, F4(0, 0, -1)))  # S† = diag(1, -i)
GATE_T_DG: ExactGate = ((ONE, ZERO), (ZERO, F4(0, Fraction(1, 2), 0, -Fraction(1, 2))))  # T†

GATES: Mapping[str, ExactGate] = {
    "I": GATE_I,
    "X": GATE_X,
    "Y": GATE_Y,
    "Z": GATE_Z,
    "H": GATE_H,
    "S": GATE_S,
    "T": GATE_T,
    "Sdg": GATE_S_DG,
    "Tdg": GATE_T_DG,
}

# Powers of the primitive 8th root of unity zeta_8 = exp(i*pi/4). Every
# phase rotation by k*pi/4 is exact in F4 — this is the full set of phases
# Clifford+T can express on a diagonal.
_ZETA8_POWERS: tuple[F4, ...] = (
    ONE,
    ZETA8,
    I_UNIT,
    F4(0, -Fraction(1, 2), 0, Fraction(1, 2)),
    MINUS_ONE,
    F4(0, -Fraction(1, 2), 0, -Fraction(1, 2)),
    F4(0, 0, -1),
    F4(0, Fraction(1, 2), 0, -Fraction(1, 2)),
)


def _zeta8_power(k: int) -> F4:
    return _ZETA8_POWERS[k % 8]


def _inner(left: Iterable[F4], right: Iterable[F4]) -> F4:
    return sum((a.conjugate() * b for a, b in zip(left, right)), ZERO)


def _validate_gate(gate: ExactGate) -> None:
    if len(gate) != 2 or any(len(row) != 2 for row in gate):
        raise ValueError("gate must be 2x2")
    cols = ((gate[0][0], gate[1][0]), (gate[0][1], gate[1][1]))
    if (
        _inner(cols[0], cols[0]) != ONE
        or _inner(cols[1], cols[1]) != ONE
        or _inner(cols[0], cols[1]) != ZERO
    ):
        raise ValueError("gate is not exactly unitary")


def _phase_power(k: int) -> F4:
    return (ONE, I_UNIT, -ONE, -I_UNIT)[k % 4]


class ExactStateVector:
    """Exact 2^n-amplitude state vector with fail-closed resource bounds."""

    def __init__(
        self,
        num_qubits: int,
        amplitudes: tuple[F4, ...],
        *,
        max_amplitudes: int | None = None,
    ):
        if num_qubits < 0 or num_qubits >= 63:
            raise ValueError("num_qubits must be in [0, 62]")
        expected = 1 << num_qubits
        limit = (
            max_amplitudes
            if max_amplitudes is not None
            else int(os.getenv("MLA1517_MAX_AMPLITUDES", str(1 << 20)))
        )
        if expected > limit:
            raise ExactResourceError(
                f"exact state vector requires {expected} amplitudes; configured limit is {limit}"
            )
        if len(amplitudes) != expected:
            raise ValueError("amplitude count does not match qubit count")
        self.num_qubits = num_qubits
        self.amplitudes = amplitudes
        self.max_amplitudes = limit

    @classmethod
    def basis(
        cls, num_qubits: int, index: int = 0, *, max_amplitudes: int | None = None
    ) -> "ExactStateVector":
        size = 1 << num_qubits
        if index < 0 or index >= size:
            raise ValueError("basis index out of range")
        return cls(
            num_qubits,
            tuple(ONE if i == index else ZERO for i in range(size)),
            max_amplitudes=max_amplitudes,
        )

    def norm_squared(self) -> F4:
        return _inner(self.amplitudes, self.amplitudes)

    def normalized_exact(self) -> bool:
        return self.norm_squared() == ONE

    def probabilities_exact(self) -> tuple[Qsqrt2, ...]:
        """Return exact Born weights in the ordered real field Q(sqrt(2)).

        No random sampling is performed. The result is an algebraic witness
        whose entries sum exactly to one for a normalized state.
        """
        probabilities: list[Qsqrt2] = []
        for amplitude in self.amplitudes:
            weight = amplitude.conjugate() * amplitude
            if weight.imag != _QZERO or weight.real.sign() < 0:
                raise ArithmeticError("invalid exact Born weight")
            probabilities.append(weight.real)
        if sum(probabilities, _QZERO) != _QONE:
            raise ArithmeticError("Born weights do not sum to one")
        return tuple(probabilities)

    def measure_deterministic(self) -> int:
        """Select the maximum exact Born weight; ties choose the lowest index.

        This is a deterministic mathematical selector, not a physical
        measurement and not a Monte-Carlo sample.
        """
        probabilities = self.probabilities_exact()
        best = 0
        for index in range(1, len(probabilities)):
            if probabilities[index].compare(probabilities[best]) > 0:
                best = index
        return best

    def collapse(self, index: int) -> "ExactStateVector":
        """Return the exact computational-basis projection for ``index``."""
        if index < 0 or index >= len(self.amplitudes):
            raise ValueError("measurement index out of range")
        if self.amplitudes[index] == ZERO:
            raise ValueError("cannot collapse onto a zero-amplitude outcome")
        return ExactStateVector.basis(self.num_qubits, index, max_amplitudes=self.max_amplitudes)

    def expectation_z_exact(self) -> Qsqrt2:
        """Exact Z expectation on the least-significant computational qubit."""
        probabilities = self.probabilities_exact()
        return sum(
            (weight if (index & 1) == 0 else -weight for index, weight in enumerate(probabilities)),
            _QZERO,
        )

    def tensor(self, other: "ExactStateVector") -> "ExactStateVector":
        return ExactStateVector(
            self.num_qubits + other.num_qubits,
            tuple(a * b for a in self.amplitudes for b in other.amplitudes),
            max_amplitudes=min(self.max_amplitudes, other.max_amplitudes),
        )

    def apply_single(self, qubit: int, gate: ExactGate) -> "ExactStateVector":
        if not 0 <= qubit < self.num_qubits:
            raise ValueError("qubit out of range")
        _validate_gate(gate)
        out = list(self.amplitudes)
        bit = 1 << qubit
        for base in range(len(out)):
            if base & bit:
                continue
            one = base | bit
            a0, a1 = self.amplitudes[base], self.amplitudes[one]
            out[base] = gate[0][0] * a0 + gate[0][1] * a1
            out[one] = gate[1][0] * a0 + gate[1][1] * a1
        return ExactStateVector(self.num_qubits, tuple(out), max_amplitudes=self.max_amplitudes)

    def apply_cnot(self, control: int, target: int) -> "ExactStateVector":
        if control == target or not (
            0 <= control < self.num_qubits and 0 <= target < self.num_qubits
        ):
            raise ValueError("invalid CNOT")
        out = list(self.amplitudes)
        cbit, tbit = 1 << control, 1 << target
        for i in range(len(out)):
            if i & cbit and not i & tbit:
                j = i | tbit
                out[i], out[j] = self.amplitudes[j], self.amplitudes[i]
        return ExactStateVector(self.num_qubits, tuple(out), max_amplitudes=self.max_amplitudes)

    def evolve_pauli_z(self, quarter_turns: int, qubit: int = 0) -> "ExactStateVector":
        if not 0 <= qubit < self.num_qubits:
            raise ValueError("qubit out of range")
        phase = _phase_power(quarter_turns)
        bit = 1 << qubit
        return ExactStateVector(
            self.num_qubits,
            tuple(a if (i & bit) == 0 else phase * a for i, a in enumerate(self.amplitudes)),
            max_amplitudes=self.max_amplitudes,
        )

    def z_eighths(self, eighth_turns: int, qubit: int = 0) -> "ExactStateVector":
        """R_z(k*pi/4) on ``qubit``: phase zeta_8^k on the |1> component.

        Every eighth-turn phase is a power of zeta_8 and therefore exact in
        F4. This is the finest Z-rotation grid the field supports.
        """
        if not isinstance(eighth_turns, int):
            raise TypeError("eighth_turns must be an integer")
        if not 0 <= qubit < self.num_qubits:
            raise ValueError("qubit out of range")
        phase = _zeta8_power(eighth_turns)
        bit = 1 << qubit
        return ExactStateVector(
            self.num_qubits,
            tuple(a if (i & bit) == 0 else phase * a for i, a in enumerate(self.amplitudes)),
            max_amplitudes=self.max_amplitudes,
        )

    def apply_controlled(self, control: int, target: int, gate: ExactGate) -> "ExactStateVector":
        """Apply a controlled single-qubit gate: gate fires on ``target``
        only where the ``control`` bit is set."""
        if control == target or not (
            0 <= control < self.num_qubits and 0 <= target < self.num_qubits
        ):
            raise ValueError("invalid controlled gate")
        _validate_gate(gate)
        out = list(self.amplitudes)
        cbit, tbit = 1 << control, 1 << target
        for i in range(len(out)):
            if i & cbit and not i & tbit:
                j = i | tbit
                a0, a1 = self.amplitudes[i], self.amplitudes[j]
                out[i] = gate[0][0] * a0 + gate[0][1] * a1
                out[j] = gate[1][0] * a0 + gate[1][1] * a1
        return ExactStateVector(self.num_qubits, tuple(out), max_amplitudes=self.max_amplitudes)

    def apply_cz(self, control: int, target: int) -> "ExactStateVector":
        """Controlled-Z: phase -1 on joint |11>. Symmetric in its operands."""
        return self.apply_controlled(control, target, GATE_Z)

    def apply_swap(self, a: int, b: int) -> "ExactStateVector":
        """SWAP two qubits — exact permutation, no phases involved."""
        if a == b or not (0 <= a < self.num_qubits and 0 <= b < self.num_qubits):
            raise ValueError("invalid SWAP")
        abit, bbit = 1 << a, 1 << b
        out = list(self.amplitudes)
        for i in range(len(out)):
            if not i & abit and i & bbit:
                j = (i | abit) & ~bbit
                out[i], out[j] = self.amplitudes[j], self.amplitudes[i]
        return ExactStateVector(self.num_qubits, tuple(out), max_amplitudes=self.max_amplitudes)

    def apply_toffoli(self, control_a: int, control_b: int, target: int) -> "ExactStateVector":
        """CCNOT: flip ``target`` only where both controls are set."""
        qubits = {control_a, control_b, target}
        if len(qubits) != 3 or any(not 0 <= q < self.num_qubits for q in qubits):
            raise ValueError("invalid Toffoli")
        cmask = (1 << control_a) | (1 << control_b)
        tbit = 1 << target
        out = list(self.amplitudes)
        for i in range(len(out)):
            if (i & cmask) == cmask and not i & tbit:
                j = i | tbit
                out[i], out[j] = self.amplitudes[j], self.amplitudes[i]
        return ExactStateVector(self.num_qubits, tuple(out), max_amplitudes=self.max_amplitudes)

    def inner(self, other: "ExactStateVector") -> F4:
        """Exact inner product <other | this>."""
        if self.num_qubits != other.num_qubits:
            raise ValueError("state spaces have different qubit counts")
        return _inner(self.amplitudes, other.amplitudes)

    def fidelity_squared(self, other: "ExactStateVector") -> Qsqrt2:
        """|<other|this>|^2 in the ordered real field — exact fidelity."""
        overlap = self.inner(other)
        weight = overlap.conjugate() * overlap
        if weight.imag != _QZERO:
            raise ArithmeticError("exact fidelity unexpectedly non-real")
        return weight.real

    def expectation_pauli(self, qubit: int, axis: str) -> Qsqrt2:
        """Exact <P> for P in {X, Y, Z} on ``qubit`` — real tomography data.

        The result is provably real for Hermitian P; a nonzero imaginary
        residue raises instead of being silently dropped.
        """
        if axis not in ("X", "Y", "Z"):
            raise ValueError("axis must be X, Y, or Z")
        if not 0 <= qubit < self.num_qubits:
            raise ValueError("qubit out of range")
        bit = 1 << qubit
        total = ZERO
        for i, amp in enumerate(self.amplitudes):
            if axis == "Z":
                weight = amp.conjugate() * amp
                total = total + (weight if (i & bit) == 0 else -weight)
            else:
                j = i ^ bit
                if i & bit:
                    continue
                a0, a1 = amp, self.amplitudes[j]
                if axis == "X":
                    # <psi|X|psi> = conj(a0)*a1 + conj(a1)*a0 = 2 Re(conj(a0) a1)
                    total = total + amp.conjugate() * a1 + a1.conjugate() * a0
                else:
                    # <psi|Y|psi> = i(conj(a1)*a0 - conj(a0)*a1)
                    total = total + (a1.conjugate() * a0 - a0.conjugate() * a1) * I_UNIT
        if total.imag != _QZERO:
            raise ArithmeticError("exact Pauli expectation unexpectedly non-real")
        return total.real

    def reduced_density(self, keep: Sequence[int]) -> tuple[tuple[F4, ...], ...]:
        """Exact reduced density matrix rho_A = Tr_B |psi><psi|.

        ``keep`` is the sorted subset of qubit indices retained in A; all
        other qubits are traced out. Entry rho[a][a'] = sum_b psi(a,b) *
        conj(psi(a',b)) — a genuine partial trace, not a projection.
        """
        keep = tuple(sorted({int(q) for q in keep}))
        if any(q < 0 or q >= self.num_qubits for q in keep):
            raise ValueError("partial-trace keep index out of range")
        traced = [q for q in range(self.num_qubits) if q not in keep]
        keep_pos = {q: p for p, q in enumerate(keep)}
        traced_pos = {q: p for p, q in enumerate(traced)}
        dk = 1 << len(keep)
        buckets: dict[int, list[tuple[int, F4]]] = {}
        for i, amp in enumerate(self.amplitudes):
            if amp == ZERO:
                continue
            ki = 0
            for q in keep:
                if i & (1 << q):
                    ki |= 1 << keep_pos[q]
            ti = 0
            for q in traced:
                if i & (1 << q):
                    ti |= 1 << traced_pos[q]
            buckets.setdefault(ti, []).append((ki, amp))
        rho = [[ZERO] * dk for _ in range(dk)]
        for entries in buckets.values():
            for a_idx, amp_a in entries:
                for ap_idx, amp_ap in entries:
                    rho[a_idx][ap_idx] = rho[a_idx][ap_idx] + amp_a * amp_ap.conjugate()
        return tuple(tuple(row) for row in rho)

    def schmidt_rank(self, keep: Sequence[int]) -> int:
        """Exact Schmidt rank across the keep/complement bipartition.

        The coefficient matrix M[a][b] is row-reduced over F4 by exact
        Gaussian elimination; its rank is the Schmidt rank. Rank 1 is the
        exact separability witness — no thresholds, no tolerances.
        """
        keep = tuple(sorted({int(q) for q in keep}))
        if any(q < 0 or q >= self.num_qubits for q in keep):
            raise ValueError("Schmidt keep index out of range")
        traced = [q for q in range(self.num_qubits) if q not in keep]
        keep_pos = {q: p for p, q in enumerate(keep)}
        traced_pos = {q: p for p, q in enumerate(traced)}
        dk, dt = 1 << len(keep), 1 << len(traced)
        matrix = [[ZERO] * dt for _ in range(dk)]
        for i, amp in enumerate(self.amplitudes):
            if amp == ZERO:
                continue
            ki = ti = 0
            for q in keep:
                if i & (1 << q):
                    ki |= 1 << keep_pos[q]
            for q in traced:
                if i & (1 << q):
                    ti |= 1 << traced_pos[q]
            matrix[ki][ti] = amp
        # Exact Gaussian elimination over the field F4. Row swaps are exact;
        # each pivot row is normalized then eliminated from every other row.
        rank = 0
        for col in range(dt):
            pivot = next(
                (r for r in range(rank, dk) if matrix[r][col] != ZERO),
                None,
            )
            if pivot is None:
                continue
            matrix[rank], matrix[pivot] = matrix[pivot], matrix[rank]
            inv = matrix[rank][col].inverse()
            matrix[rank] = [v * inv for v in matrix[rank]]
            for r in range(dk):
                if r != rank and matrix[r][col] != ZERO:
                    factor = matrix[r][col]
                    matrix[r] = [v - factor * p for v, p in zip(matrix[r], matrix[rank])]
            rank += 1
            if rank == dk:
                break
        return rank

    def sample_born(self, rng: Any) -> int:
        """Born-rule sampling against exact weights.

        The exact Q(sqrt(2)) cumulative distribution is compared to the
        caller-supplied PRNG draw — the single, explicitly documented point
        where the exact plane meets a float threshold. For a deterministic
        selector without sampling, use :meth:`measure_deterministic`.
        """
        weights = self.probabilities_exact()
        draw = float(rng.random())
        cumulative = 0.0
        for index, weight in enumerate(weights):
            cumulative += weight.to_float()
            if draw < cumulative:
                return index
        return len(weights) - 1

    def qft(self, inverse: bool = False) -> "ExactStateVector":
        """Exact quantum Fourier transform for registers of n <= 3 qubits.

        QFT needs omega = exp(2 pi i / 2^n). For n <= 3 that is a power of
        zeta_8 and exact in F4. Larger n requires the cyclotomic extension
        Q(zeta_{2^n}) and fails closed here rather than approximating.
        Output convention: |x> -> (1/sqrt(N)) sum_k omega^{xk} |k>.
        """
        n = self.num_qubits
        if n > 3:
            raise NotImplementedError(
                "exact QFT requires zeta_{2^n} in F4; representable for n <= 3 "
                "(zeta_8). Extend the scalar field to Q(zeta_16)+ for n = 4."
            )
        size = 1 << n
        scale = (ONE, F4(0, Fraction(1, 2)), F4(Fraction(1, 2)), F4(0, Fraction(1, 4)))[n]
        shift = 8 >> n if n else 0
        out = []
        for k in range(size):
            acc = ZERO
            for j, amp in enumerate(self.amplitudes):
                power = j * k * shift
                acc = acc + _zeta8_power(-power if inverse else power) * amp
            out.append(acc * scale)
        return ExactStateVector(n, tuple(out), max_amplitudes=self.max_amplitudes)

    def evolve_hamiltonian(self, hamiltonian: str, quarter_turns: int) -> "ExactStateVector":
        if hamiltonian != "Z":
            raise NotImplementedError(
                "exact evolution is limited to declared Pauli-Z quarter-turns; arbitrary matrix exponentials fail closed"
            )
        if not isinstance(quarter_turns, int):
            raise TypeError("quarter_turns must be an integer")
        return self.evolve_pauli_z(quarter_turns)


def density_trace(rho: Sequence[Sequence[F4]]) -> F4:
    """Tr(rho) — exact; equals ONE for a normalized reduced state."""
    return sum((rho[i][i] for i in range(len(rho))), ZERO)


def density_purity(rho: Sequence[Sequence[F4]]) -> F4:
    """Tr(rho^2) — exact purity; ONE iff the reduced state is pure."""
    n = len(rho)
    total = ZERO
    for i in range(n):
        for j in range(n):
            total = total + rho[i][j] * rho[j][i]
    return total


def density_is_pure(rho: Sequence[Sequence[F4]]) -> bool:
    """Exact purity test: Tr(rho^2) == Tr(rho) == 1."""
    return density_purity(rho) == ONE and density_trace(rho) == ONE


# ---------------------------------------------------------------------------
# TOE exact-witness adapter: canonical digest, basis-state encoding, and
# declared-operations-only evolution.


def _jsonable(value: Any) -> Any:
    if isinstance(value, (bytes, bytearray)):
        return {"__bytes__": bytes(value).hex()}
    if isinstance(value, Mapping):
        return {str(k): _jsonable(value[k]) for k in sorted(value, key=lambda x: str(x))}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite value cannot enter exact TOE tensor")
        return value
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    return str(value)


def canonical_digest(value: Any) -> str:
    payload = json.dumps(
        _jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _fraction(value: Fraction) -> str:
    return f"{value.numerator}/{value.denominator}"


def _amplitude_token(amplitude: F4) -> str:
    return "|".join(
        (
            _fraction(amplitude.real.a),
            _fraction(amplitude.real.b),
            _fraction(amplitude.imag.a),
            _fraction(amplitude.imag.b),
        )
    )


class ExactTOETensor:
    """Exact state witness used by the TOE envelope."""

    def __init__(self, num_qubits: int = 5, max_amplitudes: int | None = None):
        if num_qubits < 0:
            raise ValueError("num_qubits must be non-negative")
        self.num_qubits = num_qubits
        self.max_amplitudes = max_amplitudes

    def encode(self, data: Any) -> tuple[ExactStateVector, str]:
        digest = canonical_digest(data)
        index = int(digest[:16], 16) % (1 << self.num_qubits)
        state = ExactStateVector.basis(self.num_qubits, index, max_amplitudes=self.max_amplitudes)
        return state, digest

    @staticmethod
    def commitment(state: ExactStateVector) -> str:
        payload = ";".join(_amplitude_token(amplitude) for amplitude in state.amplitudes)
        return hashlib.sha256(payload.encode("ascii")).hexdigest()

    def evaluate(self, data: Any, *, quarter_turns: int = 0) -> dict[str, Any]:
        state, digest = self.encode(data)
        evolved = state.evolve_hamiltonian("Z", quarter_turns)
        return {
            "available": True,
            "exact": True,
            "field": "Q(sqrt(2)) + iQ(sqrt(2))",
            "backend": "exact_cpu_reference",
            "num_qubits": evolved.num_qubits,
            "amplitude_count": len(evolved.amplitudes),
            "input_digest": digest,
            "state_commitment": self.commitment(evolved),
            "normalized_exact": evolved.normalized_exact(),
            "operation": {"hamiltonian": "Z", "quarter_turns": quarter_turns},
            "theorem_proven": False,
            "unsupported_operation_policy": "fail_closed",
        }


__all__ = [
    "Qsqrt2",
    "F4",
    "ZERO",
    "ONE",
    "MINUS_ONE",
    "I_UNIT",
    "SQRT2",
    "ZETA8",
    "ExactResourceError",
    "ExactStateVector",
    "ExactGate",
    "GATES",
    "GATE_I",
    "GATE_X",
    "GATE_Y",
    "GATE_Z",
    "GATE_H",
    "GATE_S",
    "GATE_T",
    "GATE_S_DG",
    "GATE_T_DG",
    "ExactTOETensor",
    "canonical_digest",
    "density_trace",
    "density_purity",
    "density_is_pure",
]
