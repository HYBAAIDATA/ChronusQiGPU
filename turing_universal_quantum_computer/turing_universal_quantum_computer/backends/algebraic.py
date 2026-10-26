"""The exact algebraic backend: universal Clifford+T, materialised, exact.

Wraps :class:`~.reference.ExactStatevector` as a registry backend.  This is the
only backend in the package that is simultaneously *universal in gate set* and
*exact in arithmetic*, and it pays for both with a hard materialisation budget.
"""

from __future__ import annotations

from typing import Any

from .base import (
    Admission,
    Capability,
    ExecutionClass,
    ExecutionResult,
    Program,
    TruthClass,
)
from .reference import (
    DEFAULT_MAX_AMPLITUDES,
    DomainError,
    ExactStatevector,
    GATES,
    StatevectorTooLargeError,
)

__all__ = ["ExactFieldBackend", "SUPPORTED_GATES"]

#: One- and two-qubit operations this backend implements.
SUPPORTED_GATES = frozenset(GATES) | {"cx", "cnot", "cz", "swap"}

_TWO_QUBIT = frozenset({"cx", "cnot", "cz", "swap"})


class ExactFieldBackend:
    """Universal Clifford+T over ``Q(sqrt(2)) + i*Q(sqrt(2))``."""

    name = "exact_algebraic"

    def __init__(self, max_amplitudes: int = DEFAULT_MAX_AMPLITUDES) -> None:
        self.max_amplitudes = int(max_amplitudes)

    def capability(self) -> Capability:
        return Capability(
            name=self.name,
            execution_class=ExecutionClass.EXACT_ALGEBRAIC,
            materialises_state=True,
            gate_set="clifford+t",
            state_classes=("arbitrary",),
            max_qubits=(self.max_amplitudes.bit_length() - 1),
            requires=(),
            notes=(
                "Universal gate set with amplitudes in a closed algebraic "
                "field: every amplitude, norm and Born probability is exact, "
                "with no tolerance anywhere. Materialised, so the qubit count "
                "is bounded by max_amplitudes and refused fail-closed beyond it."
            ),
        )

    def available(self) -> tuple[bool, str]:
        return True, "pure-Python exact algebraic field; no optional dependency"

    def admit(self, program: Program) -> Admission:
        unknown = sorted(program.gates() - SUPPORTED_GATES)
        if unknown:
            return Admission(
                False,
                self.name,
                f"gate(s) {unknown} are outside the Clifford+T set {sorted(SUPPORTED_GATES)}",
                ExecutionClass.EXACT_ALGEBRAIC,
            )
        for operation in program.operations:
            arity = len(operation.qubits)
            if operation.gate in _TWO_QUBIT and arity != 2:
                return Admission(
                    False,
                    self.name,
                    f"gate {operation.gate!r} takes 2 qubits, got {arity}",
                    ExecutionClass.EXACT_ALGEBRAIC,
                )
            if operation.gate not in _TWO_QUBIT and arity != 1:
                return Admission(
                    False,
                    self.name,
                    f"gate {operation.gate!r} takes 1 qubit, got {arity}",
                    ExecutionClass.EXACT_ALGEBRAIC,
                )
        dimension = 1 << program.n_qubits
        if dimension > self.max_amplitudes:
            return Admission(
                False,
                self.name,
                (
                    f"{program.n_qubits} qubits needs {dimension} exact amplitudes, "
                    f"exceeding max_amplitudes={self.max_amplitudes}; this backend "
                    "refuses rather than truncate or approximate"
                ),
                ExecutionClass.EXACT_ALGEBRAIC,
            )
        return Admission(
            True,
            self.name,
            "universal Clifford+T program within the materialisation budget",
            ExecutionClass.EXACT_ALGEBRAIC,
        )

    def execute(self, program: Program, **options: Any) -> ExecutionResult:
        exact_payload = options.get("exact_payload", False)
        if type(exact_payload) is not bool:
            raise ValueError("exact_payload must be boolean")
        admission = self.admit(program)
        if not admission.admitted:
            raise StatevectorTooLargeError(
                f"program refused by {self.name}: {admission.reason}"
            )
        state = ExactStatevector(program.n_qubits, max_amplitudes=self.max_amplitudes)
        for operation in program.operations:
            gate, qubits = operation.gate, operation.qubits
            if gate in ("cx", "cnot"):
                state.apply_controlled("x", qubits[0], qubits[1])
            elif gate == "cz":
                state.apply_controlled("z", qubits[0], qubits[1])
            elif gate == "swap":
                state.swap(qubits[0], qubits[1])
            else:
                state.apply(gate, qubits[0])
        if not state.is_normalised():
            # Unitarity is exact, so this is a defect in the gate table or an
            # unsupported operation, never floating-point drift.
            raise DomainError(
                f"exact evolution left the state unnormalised: ||psi||^2 = "
                f"{state.norm_sq()} (expected exactly 1)"
            )
        payload: dict[str, Any] = {
            "state": state,
            "amplitudes": state.amplitude_table(include_approximation=not exact_payload),
            "dirac": state.dirac(),
            "norm_sq_exact": repr(state.norm_sq()),
            "support": len(state.support()),
            "field": "Q(sqrt(2)) + i*Q(sqrt(2))",
        }
        if options.get("shots"):
            readout = options.get("readout")
            if readout:
                payload["readout_qubits"] = [int(q) for q in readout]
                payload["counts"] = state.sample_marginal(
                    int(options["shots"]), readout, seed=options.get("seed")
                )
            else:
                payload["counts"] = state.sample(
                    int(options["shots"]), seed=options.get("seed")
                )
        if options.get("entropy_of") is not None:
            payload["entanglement_entropy_bits"] = state.entropy_bits(options["entropy_of"])
        return ExecutionResult(
            backend=self.name,
            execution_class=ExecutionClass.EXACT_ALGEBRAIC,
            truth_class=TruthClass.EXACT,
            n_qubits=program.n_qubits,
            program_digest=program.digest(),
            materialised=True,
            payload=payload,
        )
