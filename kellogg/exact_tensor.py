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
``chronus.mla1517.quantum`` surface and is importable by every subsystem.
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
    """(a,b,c,d) = (a+b*sqrt(2)) + i(c+d*sqrt(2)).

    The four channels are the declared basis of Q(sqrt(2))+iQ(sqrt(2)).
    The public exact_linear fit path populates only channel a. sign_sigma
    is defined only on the real channel; 1+i raises TypeError, which the
    public predictor surfaces as PlaneViolation. See
    docs/kellogg/exact_linear_field_audit.md.
    """

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
        """Sign in the declared sigma order, real channel only.

        A non-zero imaginary channel, including 1+i, raises TypeError.
        When channels b, c, and d are zero, as on the public exact_linear
        path, the result is the sign of the rational channel a. See
        docs/kellogg/exact_linear_field_audit.md.
        """
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


class NotInF4(NotImplementedError):
    """Operation requires an element outside F4 = Q(zeta_8).

    The exact branch refuses rather than approximates: arbitrary-angle
    rotations, QFT beyond n=3, and post-states whose normalization needs a
    square root absent from Q(sqrt(2)) all land here."""


def phase_gate(eighth_turns: int) -> ExactGate:
    """diag(1, zeta_8^k) — the exact phase-rotation grid Clifford+T supports."""
    if not isinstance(eighth_turns, int):
        raise TypeError("eighth_turns must be an integer")
    return ((ONE, ZERO), (ZERO, _zeta8_power(eighth_turns)))


def rz(pi_fraction: Fraction) -> ExactGate:
    """R_z(pi * pi_fraction) = diag(1, exp(i*pi*pi_fraction)) — exact iff
    the angle is an integer number of eighth-turns (pi_fraction in Z/4? no:
    the phase exp(i*theta) lands in <zeta_8> exactly when theta/pi in Z/4).

    Anything else (e.g. pi/7) raises NotInF4 — no silent approximation.
    """
    theta = Fraction(pi_fraction)
    eighths = 4 * theta  # exp(i*pi*f) = zeta_8^{4f}
    if eighths.denominator != 1:
        raise NotInF4(
            f"R_z(pi*{theta}) has phase exp(i*pi*{theta}); only eighth-turn "
            "multiples (theta/pi in Z/4) are representable in F4"
        )
    return phase_gate(int(eighths))


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
            else int(
                os.getenv("KELLOGG_MAX_AMPLITUDES")
                or os.getenv("MLA1517_MAX_AMPLITUDES")
                or str(1 << 20)
            )
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
            raise NotInF4(
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

    def measure_pvm(
        self,
        projectors: Sequence[Sequence[Sequence[F4]]],
        rng: Any = None,
    ) -> tuple[int, Qsqrt2, "ExactStateVector"]:
        """Exact projective measurement: {P_k} complete orthogonal family.

        Validates the PVM axioms exactly — each P_k is Hermitian and
        idempotent, distinct projectors annihilate, and sum_k P_k = I —
        then returns (outcome, exact Born weight p_k, post-measurement
        state P_k psi / sqrt(p_k)).

        With ``rng=None`` the outcome is the deterministic argmax (lowest
        index on ties). With a seeded ``rng`` the outcome is a Born sample:
        the exact Q(sqrt(2)) CDF meets one float threshold — the declared
        sampling boundary. Post-state normalization needs sqrt(p_k) in F4;
        when it is not representable the call fails closed with NotInF4.
        """
        dim = len(self.amplitudes)
        if not projectors:
            raise ValueError("a PVM requires at least one projector")
        mats = [tuple(tuple(row) for row in p) for p in projectors]
        for p in mats:
            if len(p) != dim or any(len(row) != dim for row in p):
                raise ValueError("projector dimension does not match the state")
            if any(not isinstance(v, F4) for row in p for v in row):
                raise TypeError("PVM projectors must be matrices over F4")
        ident = [
            [ONE if r == c else ZERO for c in range(dim)] for r in range(dim)
        ]
        total = [[ZERO] * dim for _ in range(dim)]
        for p in mats:
            for r in range(dim):
                for c in range(dim):
                    total[r][c] = total[r][c] + p[r][c]
        if total != ident:
            raise ValueError("projectors do not resolve the identity")
        for p in mats:
            for r in range(dim):
                for c in range(dim):
                    if p[r][c] != p[c][r].conjugate():
                        raise ValueError("projector is not Hermitian")

        def _matmul(a, b):
            return [
                [
                    sum((a[r][k] * b[k][c] for k in range(dim)), ZERO)
                    for c in range(dim)
                ]
                for r in range(dim)
            ]
        zero_m = [[ZERO] * dim for _ in range(dim)]
        for p in mats:
            if _matmul(p, p) != [list(row) for row in p]:
                raise ValueError("projector is not idempotent")
        for x in range(len(mats)):
            for y in range(x + 1, len(mats)):
                if _matmul(mats[x], mats[y]) != zero_m:
                    raise ValueError("projectors are not pairwise orthogonal")

        weights: list[Qsqrt2] = []
        images: list[tuple[F4, ...]] = []
        for p in mats:
            image = tuple(
                sum((p[r][c] * self.amplitudes[c] for c in range(dim)), ZERO)
                for r in range(dim)
            )
            weight = _inner(image, self.amplitudes)
            if weight.imag != _QZERO:
                raise ArithmeticError("Born weight unexpectedly non-real")
            weights.append(weight.real)
            images.append(image)
        if rng is None:
            selected = 0
            for k in range(1, len(weights)):
                if weights[k].compare(weights[selected]) > 0:
                    selected = k
        else:
            draw = float(rng.random())
            cumulative = 0.0
            selected = len(weights) - 1
            for k, w in enumerate(weights):
                cumulative += w.to_float()
                if draw < cumulative:
                    selected = k
                    break
        p_k = weights[selected]
        if p_k.sign() <= 0:
            raise ValueError("measured outcome has zero Born weight")
        from .exact_field import sqrt_f

        try:
            root = sqrt_f(F4(p_k.a, p_k.b))
        except ValueError as exc:
            raise NotInF4(
                f"post-state normalization needs sqrt({p_k}) outside Q(sqrt(2))"
            ) from exc
        inv = root.inverse()
        post = tuple(a * inv for a in images[selected])
        return (selected, p_k, ExactStateVector(self.num_qubits, post, max_amplitudes=self.max_amplitudes))

    def evolve_hamiltonian(
        self, hamiltonian: str, quarter_turns: int, qubit: int = 0
    ) -> "ExactStateVector":
        """Exact Pauli-axis rotation by ``quarter_turns`` quarter-turns on ``qubit``.

        Z applies diag(1, i^k) directly. X and Y conjugate the same rotation
        by Clifford gates exact in F4: X^k = H Z^k H and Y^k = (S H) Z^k (H S^dag).
        Non-Pauli axes and non-integer turns fail closed.
        """
        if not isinstance(quarter_turns, int):
            raise TypeError("quarter_turns must be an integer")
        if not 0 <= qubit < self.num_qubits:
            raise ValueError("qubit out of range")
        if hamiltonian == "Z":
            return self.evolve_pauli_z(quarter_turns, qubit)
        if hamiltonian == "X":
            return (
                self.apply_single(qubit, GATE_H)
                .evolve_pauli_z(quarter_turns, qubit)
                .apply_single(qubit, GATE_H)
            )
        if hamiltonian == "Y":
            return (
                self.apply_single(qubit, GATE_S_DG)
                .apply_single(qubit, GATE_H)
                .evolve_pauli_z(quarter_turns, qubit)
                .apply_single(qubit, GATE_H)
                .apply_single(qubit, GATE_S)
            )
        raise NotInF4(
            "exact evolution is limited to declared Pauli-axis quarter-turns; "
            "arbitrary matrix exponentials fail closed"
        )


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


def _jacobi_eigenvalues_real(matrix: Sequence[Sequence[float]], *, tol: float = 1e-12, max_sweeps: int = 100) -> list[float]:
    """Eigenvalues of a real symmetric matrix by cyclic Jacobi rotation.

    DECLARED FLOAT BOUNDARY: this is IEEE-754 linear algebra. It exists to
    evaluate spectra (e.g. for entropy) of density operators whose exact
    eigenvalues are algebraic but whose logarithms are transcendental.
    """
    n = len(matrix)
    a = [[float(matrix[r][c]) for c in range(n)] for r in range(n)]
    for _ in range(max_sweeps):
        off = math.sqrt(sum(a[r][c] ** 2 for r in range(n) for c in range(n) if r != c))
        if off < tol:
            break
        for p in range(n):
            for q in range(p + 1, n):
                if abs(a[p][q]) < 1e-300:
                    continue
                theta = (a[q][q] - a[p][p]) / (2.0 * a[p][q])
                t = (1.0 if theta >= 0 else -1.0) / (abs(theta) + math.sqrt(theta * theta + 1.0))
                c = 1.0 / math.sqrt(t * t + 1.0)
                s = t * c
                for k in range(n):
                    akp, akq = a[k][p], a[k][q]
                    a[k][p] = c * akp - s * akq
                    a[k][q] = s * akp + c * akq
                for k in range(n):
                    apk, aqk = a[p][k], a[q][k]
                    a[p][k] = c * apk - s * aqk
                    a[q][k] = s * apk + c * aqk
    return sorted(a[i][i] for i in range(n))


def _f4_to_float(value: F4) -> float:
    """One-way exact -> float projection of a single amplitude."""
    rt2 = math.sqrt(2.0)
    real = float(value.a) + float(value.b) * rt2
    imag = float(value.c) + float(value.d) * rt2
    return complex(real, imag)


def hermitian_eigenvalues(rho: Sequence[Sequence[F4]], *, tol: float = 1e-12) -> list[float]:
    """Spectrum of a Hermitian F4 density matrix — DECLARED FLOAT OUTPUT.

    The Hermitian matrix is embedded as the real symmetric block
    [[Re rho, -Im rho], [Im rho, Re rho]], whose eigenvalues are exactly
    rho's eigenvalues each duplicated once; consecutive sorted pairs are
    averaged. Verified Hermiticity (exact) is enforced before the float
    projection.
    """
    n = len(rho)
    for r in range(n):
        if len(rho[r]) != n:
            raise ValueError("density matrix must be square")
        for c in range(n):
            if rho[r][c] != rho[c][r].conjugate():
                raise ValueError("density matrix is not Hermitian over F4")
    embed = [[0.0] * (2 * n) for _ in range(2 * n)]
    for r in range(n):
        for c in range(n):
            z = _f4_to_float(rho[r][c])
            embed[r][c] = z.real
            embed[r + n][c + n] = z.real
            embed[r][c + n] = -z.imag
            embed[r + n][c] = z.imag
    eig = _jacobi_eigenvalues_real(embed, tol=tol)
    return [(eig[2 * i] + eig[2 * i + 1]) / 2.0 for i in range(n)]


def von_neumann_entropy(
    rho: Sequence[Sequence[F4]], *, tol: float = 1e-12
) -> float:
    """S(rho) = -Tr(rho log2 rho) — the one permitted LAYER-4 float output.

    The density operator's eigenvalues are algebraic (exact verifiable
    inputs); their logarithms are transcendental, so the entropy is
    returned at declared IEEE-754 precision. Eigenvalues outside
    [-tol, 1+tol] raise — a non-physical spectrum is a bug, not data.
    """
    spectrum = hermitian_eigenvalues(rho, tol=tol)
    entropy = 0.0
    for lam in spectrum:
        if lam < -tol or lam > 1.0 + tol:
            raise ArithmeticError(f"non-physical eigenvalue {lam} in density matrix")
        if lam > tol:
            entropy -= lam * math.log2(lam)
    return entropy


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
    "NotInF4",
    "ExactStateVector",
    "ExactGate",
    "phase_gate",
    "rz",
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
    "hermitian_eigenvalues",
    "von_neumann_entropy",
]
