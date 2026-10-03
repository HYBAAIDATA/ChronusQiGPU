"""Exact universal statevector backend over ``Q(sqrt(2)) + i*Q(sqrt(2))``.

This is the reference substrate for the TURING VQC backend layer, and the
cross-check target every other backend is parity-tested against.

Why it exists
-------------
The consolidated package already ships exact backends for restricted state
classes (Clifford/stabilizer, free-fermion closed form, bounded-support
sparse).  None of them is a *universal* gate-set evaluator with an exact
arithmetic witness.  This backend is: it implements a universal Clifford+T
gate set with amplitudes in a closed algebraic field, so

* every amplitude is an exact element of ``Q(sqrt(2)) + i*Q(sqrt(2))``;
* ``||psi||^2`` is computed exactly and is exactly 1 after every gate;
* unitarity is checkable by exact ``Fraction`` comparison, not a tolerance;
* Born probabilities are exact ``Q(sqrt(2))`` values and are ordered exactly.

Honest boundary
---------------
This is an exact *classical* evaluation of the algebra of a universal gate
set.  It is not quantum hardware and it confers none of the runtime advantage
of quantum hardware: the state is materialised, so the qubit count is bounded
by memory exactly as it must be.  ``max_amplitudes`` is enforced fail-closed;
an oversized register is refused, never truncated, sampled down, or faked.

Qubit indexing
--------------
Qubit ``k`` is bit ``k`` of the basis index (qubit 0 is the least significant
bit).  ``|0...0>`` has index 0.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Iterable, Sequence

from .exact_algebra import ZERO, Exact, Q2

__all__ = [
    "Gate2",
    "GATES",
    "StatevectorTooLargeError",
    "DomainError",
    "ExactStatevector",
    "gate_matrix",
    "gate_names",
    "DEFAULT_MAX_AMPLITUDES",
]

#: Hard fail-closed ceiling on materialised amplitude count (2**20 = 20 qubits).
DEFAULT_MAX_AMPLITUDES = 1 << 20

_HALF = Q2(0, Fraction(1, 2))  # 1/sqrt(2)


class StatevectorTooLargeError(MemoryError):
    """Refusal: the requested register would exceed the materialisation budget."""


class DomainError(ValueError):
    """Refusal: the requested operation is outside this backend's domain."""


# A 2x2 complex matrix in row-major order.
Gate2 = tuple[Exact, Exact, Exact, Exact]

_ONE = Exact(Q2(1))
_IUNIT = Exact(Q2(0), Q2(1))
_H = Exact(_HALF)  # 1/sqrt(2) as an Exact entry

#: The universal Clifford+T gate set.  Every entry lies in Q(sqrt(2)) + i*Q(sqrt(2)).
GATES: dict[str, Gate2] = {
    "i": (_ONE, ZERO, ZERO, _ONE),
    "x": (ZERO, _ONE, _ONE, ZERO),
    "y": (ZERO, Exact(Q2(0), Q2(-1)), Exact(Q2(0), Q2(1)), ZERO),
    "z": (_ONE, ZERO, ZERO, Exact(Q2(-1))),
    "h": (_H, _H, _H, -_H),
    "s": (_ONE, ZERO, ZERO, _IUNIT),
    "sdg": (_ONE, ZERO, ZERO, -_IUNIT),
    # T = diag(1, e^{i*pi/4}) and e^{i*pi/4} = (1 + i)/sqrt(2)
    "t": (_ONE, ZERO, ZERO, Exact(_HALF, _HALF)),
    "tdg": (_ONE, ZERO, ZERO, Exact(_HALF, -_HALF)),
}


def gate_names() -> tuple[str, ...]:
    return tuple(GATES)


def gate_matrix(name: str) -> Gate2:
    key = name.strip().lower()
    if key not in GATES:
        raise DomainError(
            f"unknown gate {name!r}; this backend implements the universal "
            f"Clifford+T set {sorted(GATES)}"
        )
    return tuple(e if isinstance(e, Exact) else Exact(e) for e in GATES[key])  # type: ignore[return-value]


def _gate_is_unitary(gate: Gate2) -> bool:
    """Exact unitarity check: ``G^dagger G == I`` over the algebraic field."""
    a, b, c, d = gate
    ac = a.conjugate()
    bc = b.conjugate()
    cc = c.conjugate()
    dc = d.conjugate()
    m00 = ac * a + cc * c
    m01 = ac * b + cc * d
    m10 = bc * a + dc * c
    m11 = bc * b + dc * d
    return m00 == _ONE and m11 == _ONE and m01.is_zero() and m10.is_zero()


def _check_gate_table() -> None:
    bad = [name for name, gate in GATES.items() if not _gate_is_unitary(gate)]
    if bad:  # pragma: no cover - guards against a bad edit to GATES
        raise AssertionError(f"non-unitary entries in the gate table: {bad}")


_check_gate_table()


@dataclass(frozen=True)
class MeasurementOutcome:
    """One exact measurement result."""

    basis_state: int
    probability: Q2
    bitstring: str


class ExactStatevector:
    """An exact, materialised ``n``-qubit statevector over the algebraic field."""

    __slots__ = ("n_qubits", "amplitudes")

    def __init__(
        self,
        n_qubits: int,
        amplitudes: Sequence[Exact] | None = None,
        *,
        max_amplitudes: int = DEFAULT_MAX_AMPLITUDES,
    ) -> None:
        if not isinstance(n_qubits, int) or n_qubits < 1:
            raise DomainError("n_qubits must be a positive integer")
        self.n_qubits = n_qubits
        dimension = 1 << n_qubits
        if dimension > max_amplitudes:
            raise StatevectorTooLargeError(
                f"refused: {n_qubits} qubits needs {dimension} exact amplitudes, "
                f"exceeding the materialisation budget of {max_amplitudes}. "
                "This backend never truncates or approximates a state; use a "
                "restricted exact backend (stabilizer / closed_form) for larger "
                "registers, or raise max_amplitudes explicitly."
            )
        if amplitudes is None:
            self.amplitudes: list[Exact] = [ZERO] * dimension
            self.amplitudes[0] = _ONE
            return
        if len(amplitudes) != dimension:
            raise DomainError(
                f"amplitude count {len(amplitudes)} does not match 2**{n_qubits}"
            )
        self.amplitudes = list(amplitudes)

    # -- construction -------------------------------------------------------
    @classmethod
    def zero_state(cls, n_qubits: int, **kwargs: Any) -> "ExactStatevector":
        return cls(n_qubits, **kwargs)

    @classmethod
    def from_basis(cls, n_qubits: int, index: int, **kwargs: Any) -> "ExactStatevector":
        state = cls(n_qubits, **kwargs)
        if not 0 <= index < (1 << n_qubits):
            raise DomainError(f"basis index {index} out of range")
        state.amplitudes = [ZERO] * (1 << n_qubits)
        state.amplitudes[index] = _ONE
        return state

    @classmethod
    def uniform_superposition(cls, n_qubits: int, **kwargs: Any) -> "ExactStatevector":
        """``|+>^n``.  For n >= 2 the 1/sqrt(2)**n factor leaves the field.

        ``Q(sqrt(2))`` contains ``1/sqrt(2)`` but not ``1/sqrt(2)**3``, so a
        uniform superposition is prepared by applying H to each qubit rather
        than by assigning amplitudes directly.  That keeps every intermediate
        amplitude inside the field, which is the point of this backend.
        """
        state = cls.zero_state(n_qubits, **kwargs)
        for qubit in range(n_qubits):
            state.apply("h", qubit)
        return state

    # -- gates --------------------------------------------------------------
    def _validate_qubit(self, qubit: int) -> None:
        if not isinstance(qubit, int) or not 0 <= qubit < self.n_qubits:
            raise DomainError(f"qubit index {qubit!r} outside 0..{self.n_qubits - 1}")

    def apply(self, gate: str | Gate2, target: int) -> "ExactStatevector":
        """Apply a one-qubit gate in place.  Returns ``self`` for chaining."""
        self._validate_qubit(target)
        matrix = gate_matrix(gate) if isinstance(gate, str) else gate
        m00, m01, m10, m11 = matrix
        bit = 1 << target
        amps = self.amplitudes
        for lo in range(len(amps)):
            if lo & bit:
                continue
            hi = lo | bit
            a_lo, a_hi = amps[lo], amps[hi]
            amps[lo] = m00 * a_lo + m01 * a_hi
            amps[hi] = m10 * a_lo + m11 * a_hi
        return self

    def apply_controlled(
        self, gate: str | Gate2, control: int, target: int
    ) -> "ExactStatevector":
        """Apply ``gate`` to ``target`` when ``control`` is ``|1>``."""
        self._validate_qubit(control)
        self._validate_qubit(target)
        if control == target:
            raise DomainError("control and target must differ")
        matrix = gate_matrix(gate) if isinstance(gate, str) else gate
        m00, m01, m10, m11 = matrix
        c_bit, t_bit = 1 << control, 1 << target
        amps = self.amplitudes
        for lo in range(len(amps)):
            if not (lo & c_bit) or (lo & t_bit):
                continue
            hi = lo | t_bit
            a_lo, a_hi = amps[lo], amps[hi]
            amps[lo] = m00 * a_lo + m01 * a_hi
            amps[hi] = m10 * a_lo + m11 * a_hi
        return self

    def swap(self, a: int, b: int) -> "ExactStatevector":
        self._validate_qubit(a)
        self._validate_qubit(b)
        if a == b:
            return self
        a_bit, b_bit = 1 << a, 1 << b
        amps = self.amplitudes
        for lo in range(len(amps)):
            if (lo & a_bit) or not (lo & b_bit):
                continue
            hi = lo ^ (a_bit | b_bit)
            amps[lo], amps[hi] = amps[hi], amps[lo]
        return self

    def cz(self, a: int, b: int) -> "ExactStatevector":
        """Controlled-Z, the canonical two-qubit Clifford entangler."""
        return self.apply_controlled("z", a, b)

    def cnot(self, control: int, target: int) -> "ExactStatevector":
        return self.apply_controlled("x", control, target)

    # -- readout ------------------------------------------------------------
    def norm_sq(self) -> Q2:
        """Exact ``||psi||^2``."""
        total = Q2()
        for amplitude in self.amplitudes:
            total = total + amplitude.norm_sq()
        return total

    def is_normalised(self) -> bool:
        """Exact check that ``||psi||^2 == 1`` with no tolerance."""
        return self.norm_sq() == Q2(1)

    def probabilities(self) -> list[Q2]:
        """Exact Born probabilities ``|a_i|^2 / ||psi||^2``."""
        total = self.norm_sq()
        if total.is_zero():
            raise DomainError("the null state has no Born distribution")
        return [amplitude.norm_sq() / total for amplitude in self.amplitudes]

    def support(self) -> list[int]:
        """Indices with a non-zero amplitude."""
        return [i for i, amplitude in enumerate(self.amplitudes) if not amplitude.is_zero()]

    def dirac(self, *, max_terms: int = 8) -> str:
        """A human-readable Dirac form, exact, truncated for display only."""
        terms = []
        for index in self.support():
            if len(terms) >= max_terms:
                terms.append("…")
                break
            terms.append(f"({self.amplitudes[index]})|{self.bitstring(index)}⟩")
        return " + ".join(terms) if terms else "0"

    def bitstring(self, index: int) -> str:
        """``|q_{n-1} ... q_1 q_0>`` — qubit 0 printed rightmost."""
        return format(index, f"0{self.n_qubits}b")[::-1]

    def amplitude_table(self) -> list[dict[str, Any]]:
        """Exact amplitudes with a display-only float for rendering."""
        return [
            {
                "basis_state": index,
                "bitstring": self.bitstring(index),
                "amplitude_exact": repr(self.amplitudes[index]),
                "amplitude_approx": self.amplitudes[index].approx(),
                "probability_exact": repr(prob),
                "probability_approx": prob.approx(),
            }
            for index, prob in enumerate(self.probabilities())
        ]

    # -- measurement --------------------------------------------------------
    def sample(self, shots: int, *, seed: int | None = None) -> dict[str, int]:
        """Deterministic exact-Born sampling.

        Thresholds are compared exactly against cumulative ``Q(sqrt(2))``
        probabilities, so the sampling decision never rounds.  A fixed ``seed``
        replays identically on any platform.
        """
        if shots < 1:
            raise DomainError("shots must be >= 1")
        import random

        rng = random.Random(seed)
        probabilities = self.probabilities()
        cumulative: list[Q2] = []
        running = Q2()
        for probability in probabilities:
            running = running + probability
            cumulative.append(running)
        counts: dict[str, int] = {}
        resolution = 1 << 32
        for _ in range(shots):
            draw = Q2(Fraction(rng.randrange(resolution), resolution))
            chosen = len(probabilities) - 1
            for index, bound in enumerate(cumulative):
                if (bound - draw).sign() > 0:
                    chosen = index
                    break
            key = self.bitstring(chosen)
            counts[key] = counts.get(key, 0) + 1
        return counts

    def sample_marginal(
        self, shots: int, qubits: Sequence[int], *, seed: int | None = None
    ) -> dict[str, int]:
        """Sample only the listed qubits from their exact marginal.

        This is a projective readout of a chosen subset, which is what a
        device does when you wire a subset of qubits to detectors.  It is
        exact and costs O(dimension), not O(dimension x qubits).
        """
        if shots < 1:
            raise DomainError("shots must be >= 1")
        import random

        rng = random.Random(seed)
        marginal = self.marginal_probabilities(qubits)
        keys = sorted(marginal)
        cumulative: list[Q2] = []
        running = Q2()
        for key in keys:
            running = running + marginal[key]
            cumulative.append(running)
        counts: dict[str, int] = {}
        resolution = 1 << 32
        for _ in range(shots):
            draw = Q2(Fraction(rng.randrange(resolution), resolution))
            chosen = keys[-1]
            for index, bound in enumerate(cumulative):
                if (bound - draw).sign() > 0:
                    chosen = keys[index]
                    break
            counts[chosen] = counts.get(chosen, 0) + 1
        return counts

    def measure(self, qubit: int, *, seed: int | None = None) -> tuple[int, "ExactStatevector"]:
        """Projectively measure one qubit and collapse, exactly.

        Returns ``(outcome, collapsed_state)``.  The collapsed state is
        renormalised by dividing out an exact ``Q(sqrt(2))`` factor.
        """
        self._validate_qubit(qubit)
        import random

        rng = random.Random(seed)
        bit = 1 << qubit
        zero_mass = Q2()
        one_mass = Q2()
        for index, amplitude in enumerate(self.amplitudes):
            mass = amplitude.norm_sq()
            if index & bit:
                one_mass = one_mass + mass
            else:
                zero_mass = zero_mass + mass
        total = zero_mass + one_mass
        if total.is_zero():
            raise DomainError("the null state has no Born distribution")
        draw = Q2(Fraction(rng.randrange(1 << 32), 1 << 32)) * total
        outcome = 1 if (one_mass - draw).sign() > 0 else 0
        kept_mass = one_mass if outcome else zero_mass
        if kept_mass.is_zero():
            raise DomainError("measured outcome has zero probability; nothing to collapse")
        collapsed = list(self.amplitudes)
        for index in range(len(collapsed)):
            if bool(index & bit) != bool(outcome):
                collapsed[index] = ZERO
            else:
                collapsed[index] = Exact(collapsed[index].re / kept_mass, collapsed[index].im / kept_mass)
        return outcome, ExactStatevector(self.n_qubits, collapsed)

    # -- entanglement -------------------------------------------------------
    def marginal_probabilities(self, qubits: Iterable[int]) -> dict[str, Q2]:
        """Exact marginal distribution over a subsystem."""
        subset = sorted(set(qubits))
        for qubit in subset:
            self._validate_qubit(qubit)
        mask = 0
        for qubit in subset:
            mask |= 1 << qubit
        probabilities = self.probabilities()
        marginal: dict[str, Q2] = {}
        for index, probability in enumerate(probabilities):
            key = format(index & mask, f"0{self.n_qubits}b")[::-1]
            key = "".join(key[q] for q in subset)
            marginal[key] = marginal.get(key, Q2()) + probability
        return marginal

    def entropy_bits(self, qubits: Iterable[int]) -> float:
        """Von Neumann entropy in bits — **display only, floats involved**.

        The exact marginal probabilities are available from
        :meth:`marginal_probabilities`; this helper exists purely so an
        operator can see the number.  It is never used to certify exactness.
        """
        import math

        entropy = 0.0
        for probability in self.marginal_probabilities(qubits).values():
            value = probability.approx()
            if value > 0.0:
                entropy -= value * math.log2(value)
        return entropy

    def is_product_state(self, qubits: Sequence[int]) -> bool:
        """Exact separability test: is the subsystem marginal a product state?"""
        subset = sorted(set(qubits))
        if len(subset) < 2:
            return True
        marginal = self.marginal_probabilities(subset)
        marginals = {q: self.marginal_probabilities([q]) for q in subset}
        for key, probability in marginal.items():
            expected = Q2(1)
            for position, qubit in enumerate(subset):
                expected = expected * marginals[qubit][key[position]]
            if not (probability - expected).is_zero():
                return False
        return True

    # -- serialization ------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "turing.vqc.exact_statevector.v1",
            "n_qubits": self.n_qubits,
            "amplitudes": [
                {"re_p": str(a.re.p), "re_q": str(a.re.q), "im_p": str(a.im.p), "im_q": str(a.im.q)}
                for a in self.amplitudes
            ],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any], **kwargs: Any) -> "ExactStatevector":
        if payload.get("schema") != "turing.vqc.exact_statevector.v1":
            raise DomainError(f"unsupported statevector schema {payload.get('schema')!r}")
        amplitudes = [
            Exact(Q2(Fraction(e["re_p"]), Fraction(e["re_q"])), Q2(Fraction(e["im_p"]), Fraction(e["im_q"])))
            for e in payload["amplitudes"]
        ]
        return cls(int(payload["n_qubits"]), amplitudes, **kwargs)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    @classmethod
    def from_json(cls, text: str, **kwargs: Any) -> "ExactStatevector":
        return cls.from_dict(json.loads(text), **kwargs)
