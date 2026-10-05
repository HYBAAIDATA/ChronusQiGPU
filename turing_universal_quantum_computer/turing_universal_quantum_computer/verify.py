"""Exact program-unitary verification for the TURING VQC.

A program is verified by computing every column of its unitary ``U`` — the
state produced from each computational-basis input — and checking
``U^dagger U = I`` in exact arithmetic (``Q(sqrt(2)) + i*Q(sqrt(2))``).
No floating point and no tolerance is involved anywhere in the check.

This is the reconciled form of the pre-baseline Pythagoras ``circuit_domain``
capability (see ``docs/TURING_PYTHAGORAS_RECONCILIATION.md``): the capability
was judged valid, and is MODIFIED into Turing as exact-field verification on
the canonical ``Program`` object rather than Pythagoras's private QASM +
floating-point unitarity test.  Width is capped because the check materialises
``2**n`` columns; beyond the cap the verdict is REFUSED, not approximated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .backends.base import Program
from .backends.exact_algebra import ONE, ZERO
from .backends.reference import GATES, DomainError, ExactStatevector

__all__ = [
    "UnitarityReport",
    "apply_operation_to_state",
    "program_unitary_columns",
    "verify_program_unitarity",
    "DEFAULT_VERIFY_WIDTH",
]

#: Width cap for exhaustive column verification (2**4 = 16 columns,
#: 256 inner products — cheap; 2**20 would not be).
DEFAULT_VERIFY_WIDTH = 4

_TWO_QUBIT = {
    "cx": "cnot",
    "cnot": "cnot",
    "cz": "cz",
    "swap": "swap",
}


def apply_operation_to_state(state: ExactStatevector, gate: str, qubits: tuple[int, ...]) -> None:
    """Apply one ``Program`` operation to an ``ExactStatevector``.

    Raises ``DomainError`` for any gate outside the exact gate table — the
    verifier fails closed rather than approximating an unknown operator.
    """
    if gate in _TWO_QUBIT:
        if len(qubits) != 2:
            raise DomainError(f"gate {gate!r} requires two qubits")
        getattr(state, _TWO_QUBIT[gate])(qubits[0], qubits[1])
        return
    if gate not in GATES:
        raise DomainError(f"gate {gate!r} has no exact algebraic form")
    if len(qubits) != 1:
        raise DomainError(f"gate {gate!r} requires one qubit")
    state.apply(gate, qubits[0])


def program_unitary_columns(
    program: Program,
    *,
    max_width: int = DEFAULT_VERIFY_WIDTH,
) -> list[list[Any]]:
    """The columns of the program's unitary, each an exact amplitude list."""
    if program.n_qubits < 1 or program.n_qubits > max_width:
        raise DomainError(
            f"verification refused: n_qubits={program.n_qubits} outside "
            f"1..{max_width} (columns would be {1 << program.n_qubits})"
        )
    dimension = 1 << program.n_qubits
    columns: list[list[Any]] = []
    for basis in range(dimension):
        state = ExactStatevector.from_basis(program.n_qubits, basis)
        for operation in program.operations:
            apply_operation_to_state(state, operation.gate, operation.qubits)
        columns.append(list(state.amplitudes))
    return columns


@dataclass(frozen=True)
class UnitarityReport:
    """Verdict of an exact ``U^dagger U = I`` check."""

    verified: bool
    state: str  # PASS / FAIL / REFUSED / UNAVAILABLE
    program_digest: str
    n_qubits: int
    checked_pairs: int
    failing_pairs: tuple[str, ...]
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "verified": self.verified,
            "state": self.state,
            "program_digest": self.program_digest,
            "n_qubits": self.n_qubits,
            "checked_pairs": self.checked_pairs,
            "failing_pairs": list(self.failing_pairs),
            "reason": self.reason,
        }


def verify_program_unitarity(
    program: Program,
    *,
    max_width: int = DEFAULT_VERIFY_WIDTH,
) -> UnitarityReport:
    """Prove or refute ``U^dagger U = I`` for ``program`` in exact arithmetic."""
    digest = program.digest()
    try:
        columns = program_unitary_columns(program, max_width=max_width)
    except DomainError as exc:
        return UnitarityReport(
            verified=False,
            state="REFUSED",
            program_digest=digest,
            n_qubits=program.n_qubits,
            checked_pairs=0,
            failing_pairs=(),
            reason=str(exc),
        )
    dimension = len(columns)
    checked = 0
    failing: list[str] = []
    for i in range(dimension):
        ci = columns[i]
        for j in range(i, dimension):
            cj = columns[j]
            inner = ZERO
            for a, b in zip(ci, cj):
                inner = inner + a.conjugate() * b
            expected = ONE if i == j else ZERO
            checked += 1
            if inner != expected:
                failing.append(f"({i},{j})={inner}")
    if failing:
        return UnitarityReport(
            verified=False,
            state="FAIL",
            program_digest=digest,
            n_qubits=program.n_qubits,
            checked_pairs=checked,
            failing_pairs=tuple(failing[:8]),
            reason=f"U^dagger U != I in exact arithmetic ({len(failing)} bad pairs)",
        )
    return UnitarityReport(
        verified=True,
        state="PASS",
        program_digest=digest,
        n_qubits=program.n_qubits,
        checked_pairs=checked,
        failing_pairs=(),
        reason="U^dagger U = I verified exactly over the algebraic field",
    )
