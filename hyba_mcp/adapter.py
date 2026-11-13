"""Thin wrapper that turns a gate list into TURING operators and states.

Contract: ``U = build_operator(spec)`` when the register is small enough to
store the dense unitary, then ``psi = U.apply(zero_state)``. Above that limit
each gate is still a TURING operator — ``tensor_operators`` and ``turing.CNOT``,
including non-adjacent CNOT via Hadamard conjugation and SWAP — and is applied
with ``LinearOperator.apply``. Caller observables are
``operator.expectation_value(psi)`` on that same state.

Hardware answer: there is no second path. A ``qpu:`` backend is denied.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Mapping

from .policy import (
    AMPLITUDE_RETURN_MAX_QUBITS,
    COST_REPORT_MAX_QUBITS,
    EXECUTE_MAX_QUBITS,
    MAX_GATES,
    STATEVECTOR,
    UNITARY_BUILD_MAX_QUBITS,
    check_request,
)

_TURING_SRC = Path(__file__).resolve().parents[1] / "packages" / "turing" / "src"
if _TURING_SRC.is_dir() and str(_TURING_SRC) not in sys.path:
    sys.path.insert(0, str(_TURING_SRC))

from turing import (  # noqa: E402
    CNOT,
    HADAMARD,
    IDENTITY_2,
    PAULI_X,
    PAULI_Y,
    PAULI_Z,
    PHASE_S,
    PHASE_T,
    LinearOperator,
    QuantumState,
    born_probabilities,
    tensor_operators,
)
from turing.state import DEFAULT_TOLERANCE  # noqa: E402

SINGLE_QUBIT_GATES = {
    "I": IDENTITY_2,
    "H": HADAMARD,
    "X": PAULI_X,
    "Y": PAULI_Y,
    "Z": PAULI_Z,
    "S": PHASE_S,
    "T": PHASE_T,
}
ROTATIONS = ("RX", "RY", "RZ")
GATE_NAMES = tuple(SINGLE_QUBIT_GATES) + ROTATIONS + ("CNOT",)
PAULI_FACTORS = {"I": IDENTITY_2, "X": PAULI_X, "Y": PAULI_Y, "Z": PAULI_Z}
BASIS_CONVENTION = "qubit 0 is the most-significant bit; tensor order is left to right"


class ToolInputError(ValueError):
    """A caller-correctable adapter or tool argument error."""


def _require_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ToolInputError(
            f"{field} must be an integer between {minimum} and {maximum}"
        )
    return value


def _require_finite_float(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ToolInputError(f"{field} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ToolInputError(f"{field} must be a finite number")
    return number


def rotation(name: str, theta: float) -> LinearOperator:
    """Return RX, RY, or RZ as a 2x2 complex matrix. Angle is radians."""
    half = theta / 2.0
    cosine = math.cos(half)
    sine = math.sin(half)
    if name == "RX":
        rows = ((cosine, -1j * sine), (-1j * sine, cosine))
    elif name == "RY":
        rows = ((cosine, -sine), (sine, cosine))
    elif name == "RZ":
        phase = complex(math.cos(half), math.sin(half))
        rows = ((phase.conjugate(), 0.0), (0.0, phase))
    else:
        raise ToolInputError(f"unknown rotation: {name}")
    return LinearOperator.from_rows(rows)


def _gate_operator(
    spec: Mapping[str, Any],
) -> tuple[str, tuple[int, ...], LinearOperator | None]:
    if not isinstance(spec, Mapping):
        raise ToolInputError("each gate must be an object")
    extra = set(spec) - {"name", "qubits", "theta"}
    if extra:
        raise ToolInputError("gate contains unsupported fields")
    name = spec.get("name")
    if not isinstance(name, str) or name not in GATE_NAMES:
        raise ToolInputError(f"gate name must be one of {list(GATE_NAMES)}")
    qubits = spec.get("qubits")
    if not isinstance(qubits, list) or any(type(qubit) is not int for qubit in qubits):
        raise ToolInputError("qubits must be an array of integers")
    theta = spec.get("theta")
    operator: LinearOperator | None
    if name == "CNOT":
        if theta is not None:
            raise ToolInputError("CNOT does not take theta")
        if len(qubits) != 2 or qubits[0] == qubits[1]:
            raise ToolInputError("CNOT requires two distinct qubits")
        operator = None
    elif name in ROTATIONS:
        if len(qubits) != 1:
            raise ToolInputError(f"{name} requires one qubit")
        if theta is None:
            raise ToolInputError(f"{name} requires theta")
        operator = rotation(name, _require_finite_float(theta, "theta"))
    else:
        if theta is not None:
            raise ToolInputError(f"{name} does not take theta")
        if len(qubits) != 1:
            raise ToolInputError(f"{name} requires one qubit")
        operator = SINGLE_QUBIT_GATES[name]
    return name, tuple(qubits), operator


def parse_circuit(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a circuit object without allocating a 2^n state."""
    if not isinstance(spec, Mapping):
        raise ToolInputError("spec must be an object")
    extra = set(spec) - {"n_qubits", "gates", "observables"}
    if extra:
        raise ToolInputError("spec contains unsupported fields")
    n_qubits = _require_int(spec.get("n_qubits"), "n_qubits", 1, 30)
    gates = spec.get("gates")
    if not isinstance(gates, list):
        raise ToolInputError("gates must be an array")
    if len(gates) > MAX_GATES:
        raise ToolInputError(f"gates exceeds the maximum of {MAX_GATES}")
    parsed = []
    for gate in gates:
        name, qubits, operator = _gate_operator(gate)
        if any(qubit < 0 or qubit >= n_qubits for qubit in qubits):
            raise ToolInputError("qubit index is outside the register")
        parsed.append(
            {
                "name": name,
                "qubits": qubits,
                "operator": operator,
                "theta": gate.get("theta"),
            }
        )
    observables = _parse_observables(spec.get("observables", []), n_qubits)
    return {"n_qubits": n_qubits, "gates": parsed, "observables": observables}


def _parse_observables(observables: Any, n_qubits: int) -> tuple[str, ...]:
    if not isinstance(observables, list):
        raise ToolInputError("observables must be an array of Pauli strings")
    if len(observables) > 16:
        raise ToolInputError("observables exceeds the maximum of 16")
    parsed: list[str] = []
    for text in observables:
        if not isinstance(text, str) or len(text) != n_qubits or any(
            char not in PAULI_FACTORS for char in text
        ):
            raise ToolInputError(
                "each observable must be a Pauli string of length n_qubits"
            )
        parsed.append(text)
    return tuple(parsed)


def _compose_all(operators: list[LinearOperator]) -> LinearOperator:
    composed = operators[0]
    for operator in operators[1:]:
        composed = operator.compose(composed)
    return composed


def _embed_block(n_qubits: int, left: int, block: LinearOperator) -> LinearOperator:
    """Place a 2-qubit block on qubits ``left`` and ``left + 1``."""
    factors = [IDENTITY_2] * left + [block] + [IDENTITY_2] * (n_qubits - left - 2)
    if len(factors) == 1:
        return block
    return tensor_operators(*factors)


def reversed_cnot() -> LinearOperator:
    """CNOT with control on the low bit, from ``turing.CNOT`` and Hadamard."""
    both = tensor_operators(HADAMARD, HADAMARD)
    return both.compose(CNOT.compose(both))


def swap_2() -> LinearOperator:
    """Adjacent SWAP from ``turing.CNOT`` and its Hadamard conjugate."""
    reversed_gate = reversed_cnot()
    return CNOT.compose(reversed_gate.compose(CNOT))


def embed_swap(n_qubits: int, qubit: int) -> LinearOperator:
    return _embed_block(n_qubits, qubit, swap_2())


def embed_cnot(n_qubits: int, control: int, target: int) -> LinearOperator:
    """Embed CNOT using ``turing.CNOT``. Non-adjacent pairs are swapped adjacent."""
    if abs(control - target) == 1:
        block = CNOT if control < target else reversed_cnot()
        return _embed_block(n_qubits, min(control, target), block)
    steps: list[LinearOperator] = []
    if control < target:
        for qubit in range(target - 1, control, -1):
            steps.append(embed_swap(n_qubits, qubit))
        steps.append(_embed_block(n_qubits, control, CNOT))
        for qubit in range(control + 1, target):
            steps.append(embed_swap(n_qubits, qubit))
    else:
        for qubit in range(control - 1, target, -1):
            steps.append(embed_swap(n_qubits, qubit))
        steps.append(_embed_block(n_qubits, target, reversed_cnot()))
        for qubit in range(target + 1, control):
            steps.append(embed_swap(n_qubits, qubit))
    return _compose_all(steps)


def embed_operator(n_qubits: int, gate: Mapping[str, Any]) -> LinearOperator:
    """Materialize one gate as a TURING operator on the full register."""
    if gate["name"] == "CNOT":
        control, target = gate["qubits"]
        return embed_cnot(n_qubits, control, target)
    factors = [IDENTITY_2] * n_qubits
    factors[gate["qubits"][0]] = gate["operator"]
    if n_qubits == 1:
        return gate["operator"]
    return tensor_operators(*factors)


def zero_state(n_qubits: int) -> QuantumState:
    return QuantumState.basis(1 << n_qubits, 0)


def run_circuit(circuit: Mapping[str, Any]) -> tuple[str, QuantumState, LinearOperator | None]:
    """Return ``(build_mode, psi, U)``. ``U`` is set only for the dense build."""
    n_qubits = circuit["n_qubits"]
    vacuum = zero_state(n_qubits)
    if n_qubits <= UNITARY_BUILD_MAX_QUBITS:
        operator = build_operator(circuit)
        return "dense_operator", operator.apply(vacuum), operator
    amplitudes = vacuum.amplitudes
    for gate in circuit["gates"]:
        amplitudes = _apply_gate_to_amplitudes(amplitudes, n_qubits, gate)
    return "sequential_gate_apply", QuantumState(amplitudes), None


def _bit_mask(n_qubits: int, qubit: int) -> int:
    """Index bit for ``qubit``; qubit 0 is the most-significant bit."""
    return 1 << (n_qubits - 1 - qubit)


def _apply_gate_to_amplitudes(
    amplitudes: tuple[complex, ...], n_qubits: int, gate: Mapping[str, Any]
) -> tuple[complex, ...]:
    """Apply one gate to a state vector by updating amplitude pairs in place."""
    values = list(amplitudes)
    dimension = len(values)
    if gate["name"] == "CNOT":
        control, target = gate["qubits"]
        control_mask = _bit_mask(n_qubits, control)
        target_mask = _bit_mask(n_qubits, target)
        for index in range(dimension):
            if index & control_mask and not index & target_mask:
                partner = index | target_mask
                values[index], values[partner] = values[partner], values[index]
        return tuple(values)
    (a, b), (c, d) = gate["operator"].matrix
    mask = _bit_mask(n_qubits, gate["qubits"][0])
    for index in range(dimension):
        if not index & mask:
            low = values[index]
            high = values[index | mask]
            values[index] = a * low + b * high
            values[index | mask] = c * low + d * high
    return tuple(values)


def _pauli_expectation(
    amplitudes: tuple[complex, ...], n_qubits: int, text: str
) -> complex:
    """Return <psi|P|psi> for a Pauli string without building P as a matrix.

    P|j> = phase_j |j XOR flip>, where X/Y flip the qubit bit, Z contributes
    (-1)^bit, and Y contributes +i for bit 0 and -i for bit 1.
    """
    flip = 0
    for qubit, char in enumerate(text):
        if char in "XY":
            flip |= _bit_mask(n_qubits, qubit)
    total = 0j
    for index, amplitude in enumerate(amplitudes):
        phase = 1 + 0j
        for qubit, char in enumerate(text):
            bit = 1 if index & _bit_mask(n_qubits, qubit) else 0
            if char == "Z" and bit:
                phase = -phase
            elif char == "Y":
                phase *= -1j if bit else 1j
        total += amplitudes[index ^ flip].conjugate() * phase * amplitude
    return total


def build_operator(circuit: Mapping[str, Any]) -> LinearOperator:
    """Compose the circuit into one operator. The first gate is applied first."""
    n_qubits = circuit["n_qubits"]
    if n_qubits > UNITARY_BUILD_MAX_QUBITS:
        raise ToolInputError(
            f"dense operator build is limited to {UNITARY_BUILD_MAX_QUBITS} qubits"
        )
    composed = LinearOperator.identity(1 << n_qubits)
    for gate in circuit["gates"]:
        composed = embed_operator(n_qubits, gate).compose(composed)
    return composed


def _complex_record(value: complex) -> dict[str, float]:
    return {"re": float(value.real), "im": float(value.imag)}


def _state_record(state: QuantumState, *, include_amplitudes: bool) -> dict[str, Any]:
    record: dict[str, Any] = {
        "dimension": state.dimension,
        "probabilities": [float(value) for value in born_probabilities(state)],
        "norm_squared": state.norm_squared,
    }
    if include_amplitudes:
        record["amplitudes"] = [_complex_record(value) for value in state.amplitudes]
    return record


def expectation_records(state: QuantumState, observables: tuple[str, ...] | list[str]) -> list[dict[str, Any]]:
    n_qubits = state.dimension.bit_length() - 1
    records = []
    for text in observables:
        _require_pauli(text)
        value = _pauli_expectation(state.amplitudes, n_qubits, text)
        records.append(
            {
                "observable": text,
                # A tensor product of Hermitian Pauli factors is Hermitian.
                "hermitian": True,
                "expectation": _complex_record(value),
            }
        )
    return records


def _require_pauli(text: str) -> None:
    if not isinstance(text, str) or not text or any(char not in PAULI_FACTORS for char in text):
        raise ToolInputError("observable must be a non-empty string of I, X, Y, Z")


def pauli_observable(text: str) -> LinearOperator:
    _require_pauli(text)
    return tensor_operators(*(PAULI_FACTORS[char] for char in text))


class TuringAdapter:
    """MCP-facing shim over TURING state vectors, operators, and the Born rule."""

    def list_backends(self) -> dict[str, Any]:
        return {
            "backends": [
                {
                    "id": STATEVECTOR,
                    "exact": True,
                    "sampling": False,
                    "hardware": False,
                    "max_qubits_execute": EXECUTE_MAX_QUBITS,
                    "max_qubits_dense_unitary": UNITARY_BUILD_MAX_QUBITS,
                    "max_qubits_cost_report": COST_REPORT_MAX_QUBITS,
                    "semantics": (
                        "finite-dimensional complex Hilbert space; "
                        "Python complex values, tolerance-checked, not symbolic"
                    ),
                }
            ],
            "not_implemented": ["density", "qpu"],
            "basis_convention": BASIS_CONVENTION,
        }

    def validate_math(
        self,
        spec: Mapping[str, Any],
        backend: str = STATEVECTOR,
    ) -> dict[str, Any]:
        circuit = parse_circuit(spec)
        decision = check_request(backend, circuit["n_qubits"], operation="validate")
        report: dict[str, Any] = {
            **decision,
            "gate_count": len(circuit["gates"]),
            "basis_convention": BASIS_CONVENTION,
            "unitarity": {
                "dense_check": False,
                "supported_gates_are_unitary": True,
            },
        }
        if not decision["execute_allowed"]:
            return report
        if circuit["n_qubits"] <= UNITARY_BUILD_MAX_QUBITS:
            operator = build_operator(circuit)
            unitary = operator.is_unitary()
            report["unitarity"] = {
                "dense_check": True,
                "ok": unitary,
                "tolerance": DEFAULT_TOLERANCE,
                "supported_gates_are_unitary": True,
            }
            if not unitary:
                report["decision"] = "deny"
                report["execute_allowed"] = False
                report["reason"] = "built operator is not unitary"
        else:
            report["unitarity"] = {
                "dense_check": False,
                "reason": (
                    "dense unitary is only built at or below "
                    f"{UNITARY_BUILD_MAX_QUBITS} qubits"
                ),
                "supported_gates_are_unitary": True,
            }
        return report

    def execute_circuit(
        self,
        spec: Mapping[str, Any],
        backend: str = STATEVECTOR,
        include_amplitudes: bool | None = None,
    ) -> dict[str, Any]:
        circuit = parse_circuit(spec)
        decision = check_request(backend, circuit["n_qubits"], operation="execute")
        if not decision["execute_allowed"]:
            return {**decision, "executed": False}
        validation = self.validate_math(spec, backend)
        if validation["decision"] != "allow":
            return {**validation, "executed": False}
        want_amplitudes = (
            circuit["n_qubits"] <= AMPLITUDE_RETURN_MAX_QUBITS
            if include_amplitudes is None
            else include_amplitudes
        )
        if want_amplitudes and circuit["n_qubits"] > AMPLITUDE_RETURN_MAX_QUBITS:
            raise ToolInputError(
                "amplitudes are returned only at or below "
                f"{AMPLITUDE_RETURN_MAX_QUBITS} qubits"
            )
        build_mode, state, _operator = run_circuit(circuit)
        return {
            **decision,
            "executed": True,
            "exact": True,
            "numerical": "python-complex",
            "build": build_mode,
            "basis_convention": BASIS_CONVENTION,
            "state": _state_record(state, include_amplitudes=want_amplitudes),
            "expectations": expectation_records(state, circuit["observables"]),
            "unitarity": validation["unitarity"],
        }

    def compute_expectation(
        self,
        spec: Mapping[str, Any],
        observable: str,
        backend: str = STATEVECTOR,
    ) -> dict[str, Any]:
        if not isinstance(observable, str):
            raise ToolInputError("observable must be a Pauli string")
        merged = dict(spec)
        merged["observables"] = [observable]
        result = self.execute_circuit(merged, backend, include_amplitudes=False)
        if not result.get("executed"):
            return result
        record = result["expectations"][0]
        return {
            "decision": result["decision"],
            "execute_allowed": result["execute_allowed"],
            "backend": result["backend"],
            "n_qubits": result["n_qubits"],
            "memory": result["memory"],
            "hardware": False,
            "sampling": False,
            "reason": result["reason"],
            "executed": True,
            "build": result["build"],
            "observable": observable,
            "hermitian": record["hermitian"],
            "expectation": record["expectation"],
            "basis_convention": BASIS_CONVENTION,
        }
