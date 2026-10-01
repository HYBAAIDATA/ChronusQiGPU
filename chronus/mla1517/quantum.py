"""Exact finite state-vector algebra for MLA1517.

The runtime stores amplitudes in the exact field Q(sqrt(2)) + i Q(sqrt(2)).
No floating amplitudes, truncation, Monte-Carlo sampling, tensor shortcuts, or
heuristic gates are used.  Unsupported Hamiltonian exponentials fail closed.
"""

from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
import os
from typing import Any, Iterable

# Provenance class of every quantum-circuit result computed in this runtime:
# state-vector algebra evaluated on the host CPU. It is a classical
# simulation (exact where exact arithmetic is used), never quantum hardware
# and never a cloud quantum service.
CLASSICAL_SIMULATION = "CLASSICAL_SIMULATION"


def classical_simulation_provenance(
    backend: str, *, arithmetic: str, sampling: str
) -> dict[str, Any]:
    """The provenance record attached to a classically simulated quantum result."""
    return {
        "execution": CLASSICAL_SIMULATION,
        "backend": backend,
        "arithmetic": arithmetic,
        "sampling": sampling,
        "quantum_hardware": False,
        "cloud_quantum": False,
    }


@dataclass(frozen=True)
class Qsqrt2:
    a: Fraction = Fraction(0)
    b: Fraction = Fraction(0)

    def __init__(self, a: int | Fraction = 0, b: int | Fraction = 0):
        object.__setattr__(self, "a", Fraction(a))
        object.__setattr__(self, "b", Fraction(b))

    def __add__(self, o: "Qsqrt2") -> "Qsqrt2":
        return Qsqrt2(self.a + o.a, self.b + o.b)

    def __radd__(self, o: object) -> "Qsqrt2":
        return self if o == 0 else NotImplemented

    def __sub__(self, o: "Qsqrt2") -> "Qsqrt2":
        return Qsqrt2(self.a - o.a, self.b - o.b)

    def __neg__(self) -> "Qsqrt2":
        return Qsqrt2(-self.a, -self.b)

    def __mul__(self, o: "Qsqrt2") -> "Qsqrt2":
        return Qsqrt2(self.a * o.a + 2 * self.b * o.b, self.a * o.b + self.b * o.a)

    def __truediv__(self, o: "Qsqrt2") -> "Qsqrt2":
        den = o.a * o.a - 2 * o.b * o.b
        if den == 0:
            raise ZeroDivisionError
        return Qsqrt2((self.a * o.a - 2 * self.b * o.b) / den, (self.b * o.a - self.a * o.b) / den)

    def __eq__(self, o: object) -> bool:
        return isinstance(o, Qsqrt2) and self.a == o.a and self.b == o.b

    def sign(self) -> int:
        """Return the exact sign of ``a + b*sqrt(2)`` without floats."""
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
        # The coefficients have opposite signs. Compare |a| with |b|sqrt(2)
        # by squaring rational quantities; no approximation is introduced.
        lhs = self.a * self.a
        rhs = 2 * self.b * self.b
        if lhs == rhs:
            raise ArithmeticError("non-zero rational solution to a^2 = 2b^2")
        dominant = self.a if lhs > rhs else self.b
        return 1 if dominant > 0 else -1

    def compare(self, other: "Qsqrt2") -> int:
        """Exact three-way comparison in the ordered real embedding."""
        return (self - other).sign()


ZERO = Qsqrt2()
ONE = Qsqrt2(1)
SQRT2_INV = Qsqrt2(0, Fraction(1, 2))


@dataclass(frozen=True)
class ExactComplex:
    real: Qsqrt2 = ZERO
    imag: Qsqrt2 = ZERO

    def __add__(self, o: "ExactComplex") -> "ExactComplex":
        return ExactComplex(self.real + o.real, self.imag + o.imag)

    def __radd__(self, o: object) -> "ExactComplex":
        return self if o == 0 else NotImplemented

    def __sub__(self, o: "ExactComplex") -> "ExactComplex":
        return ExactComplex(self.real - o.real, self.imag - o.imag)

    def __neg__(self) -> "ExactComplex":
        return ExactComplex(-self.real, -self.imag)

    def __mul__(self, o: "ExactComplex") -> "ExactComplex":
        return ExactComplex(
            self.real * o.real - self.imag * o.imag, self.real * o.imag + self.imag * o.real
        )

    def conjugate(self) -> "ExactComplex":
        return ExactComplex(self.real, -self.imag)

    def __eq__(self, o: object) -> bool:
        return isinstance(o, ExactComplex) and self.real == o.real and self.imag == o.imag


class ExactResourceError(MemoryError):
    """Exact state-vector resource bound exceeded; no degraded path is allowed."""


C0 = ExactComplex()
C1 = ExactComplex(ONE)
CI = ExactComplex(ZERO, ONE)

Gate = tuple[tuple[ExactComplex, ExactComplex], tuple[ExactComplex, ExactComplex]]
I: Gate = ((C1, C0), (C0, C1))
X: Gate = ((C0, C1), (C1, C0))
Y: Gate = ((C0, -CI), (CI, C0))
Z: Gate = ((C1, C0), (C0, -C1))
H: Gate = (
    (ExactComplex(SQRT2_INV), ExactComplex(SQRT2_INV)),
    (ExactComplex(SQRT2_INV), ExactComplex(-SQRT2_INV)),
)
S: Gate = ((C1, C0), (C0, CI))
S_DG: Gate = ((C1, C0), (C0, -CI))
T: Gate = ((C1, C0), (C0, ExactComplex(SQRT2_INV, SQRT2_INV)))


def _inner(left: Iterable[ExactComplex], right: Iterable[ExactComplex]) -> ExactComplex:
    return sum((a.conjugate() * b for a, b in zip(left, right)), C0)


def _validate_gate(gate: Gate) -> None:
    if len(gate) != 2 or any(len(row) != 2 for row in gate):
        raise ValueError("gate must be 2x2")
    cols = ((gate[0][0], gate[1][0]), (gate[0][1], gate[1][1]))
    if (
        _inner(cols[0], cols[0]) != C1
        or _inner(cols[1], cols[1]) != C1
        or _inner(cols[0], cols[1]) != C0
    ):
        raise ValueError("gate is not exactly unitary")


def _phase_power(k: int) -> ExactComplex:
    return (C1, CI, -C1, -CI)[k % 4]


class ExactStateVector:
    """Exact 2^n-amplitude state vector with fail-closed resource bounds."""

    def __init__(
        self,
        num_qubits: int,
        amplitudes: tuple[ExactComplex, ...],
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

    @staticmethod
    def provenance() -> dict[str, Any]:
        """Every state and weight here is exact classical simulation."""
        return classical_simulation_provenance(
            "mla1517.quantum.ExactStateVector",
            arithmetic="exact Q(sqrt2) + iQ(sqrt2)",
            sampling="none: deterministic exact Born weights",
        )

    @classmethod
    def basis(
        cls, num_qubits: int, index: int = 0, *, max_amplitudes: int | None = None
    ) -> "ExactStateVector":
        size = 1 << num_qubits
        if index < 0 or index >= size:
            raise ValueError("basis index out of range")
        return cls(
            num_qubits,
            tuple(C1 if i == index else C0 for i in range(size)),
            max_amplitudes=max_amplitudes,
        )

    def norm_squared(self) -> ExactComplex:
        return _inner(self.amplitudes, self.amplitudes)

    def normalized_exact(self) -> bool:
        return self.norm_squared() == C1

    def probabilities_exact(self) -> tuple[Qsqrt2, ...]:
        """Return exact Born weights in the ordered real field Q(sqrt(2)).

        No random sampling is performed. The result is an algebraic witness
        whose entries sum exactly to one for a normalized state.
        """
        probabilities: list[Qsqrt2] = []
        for amplitude in self.amplitudes:
            weight = amplitude.conjugate() * amplitude
            if weight.imag != ZERO or weight.real.sign() < 0:
                raise ArithmeticError("invalid exact Born weight")
            probabilities.append(weight.real)
        if sum(probabilities, ZERO) != Qsqrt2(1):
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
        if self.amplitudes[index] == C0:
            raise ValueError("cannot collapse onto a zero-amplitude outcome")
        return ExactStateVector.basis(self.num_qubits, index, max_amplitudes=self.max_amplitudes)

    def expectation_z_exact(self) -> Qsqrt2:
        """Exact Z expectation on the least-significant computational qubit."""
        probabilities = self.probabilities_exact()
        return sum(
            (weight if (index & 1) == 0 else -weight for index, weight in enumerate(probabilities)),
            ZERO,
        )

    def tensor(self, other: "ExactStateVector") -> "ExactStateVector":
        return ExactStateVector(
            self.num_qubits + other.num_qubits,
            tuple(a * b for a in self.amplitudes for b in other.amplitudes),
            max_amplitudes=min(self.max_amplitudes, other.max_amplitudes),
        )

    def apply_single(self, qubit: int, gate: Gate) -> "ExactStateVector":
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

    def evolve_pauli_z(self, quarter_turns: int) -> "ExactStateVector":
        phase = _phase_power(quarter_turns)
        return ExactStateVector(
            self.num_qubits,
            tuple(a if (i & 1) == 0 else phase * a for i, a in enumerate(self.amplitudes)),
            max_amplitudes=self.max_amplitudes,
        )

    def evolve_hamiltonian(self, hamiltonian: str, quarter_turns: int) -> "ExactStateVector":
        """Exact Pauli-axis rotation by ``quarter_turns`` quarter-turns (pi/2 each).

        Z applies diag(1, i^k) to the least-significant qubit directly.
        X and Y are conjugations of that same rotation by Clifford gates that
        are exact in Q(sqrt(2)) + i Q(sqrt(2)):  X^k = H Z^k H (H maps the
        z-axis to x), and Y^k = (S H) Z^k (H S^dag) (S*H maps z to y).
        Non-Pauli axes and non-integer turns still fail closed.
        """
        if not isinstance(quarter_turns, int):
            raise TypeError("quarter_turns must be an integer")
        if hamiltonian == "Z":
            return self.evolve_pauli_z(quarter_turns)
        if hamiltonian == "X":
            return self.apply_single(0, H).evolve_pauli_z(quarter_turns).apply_single(0, H)
        if hamiltonian == "Y":
            return (
                self.apply_single(0, S_DG)
                .apply_single(0, H)
                .evolve_pauli_z(quarter_turns)
                .apply_single(0, H)
                .apply_single(0, S)
            )
        raise NotImplementedError(
            "exact evolution supports declared Pauli X/Y/Z quarter-turns; "
            "arbitrary matrix exponentials fail closed"
        )
