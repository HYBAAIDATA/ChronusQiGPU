"""Parameterized quantum programs for variational algorithms (VQE, QAOA).

This module extends :class:`~turing_universal_quantum_computer.backends.base.Program`
with parameter vectors, binding, and variational circuit construction.  Parameters
are exact symbolic objects (values in a closed algebraic field); binding materialises
a concrete ``Program`` with no free parameters.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Sequence

from .backends.base import Operation, Program

__all__ = [
    "Parameter",
    "ParameterSet",
    "ParameterizedProgram",
    "VariationalLayer",
]


def _is_finite_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    return False


@dataclass(frozen=True)
class Parameter:
    """One variational parameter, identified by name and index."""
    name: str
    index: int

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise ValueError("parameter name must be a non-empty string")
        if not isinstance(self.index, int) or self.index < 0:
            raise ValueError("parameter index must be a non-negative integer")


@dataclass(frozen=True)
class ParameterSet:
    """Ordered collection of parameters.  Order is part of the identity of the set."""
    parameters: tuple[Parameter, ...] = ()

    def __post_init__(self) -> None:
        seen: set[str] = set()
        for param in self.parameters:
            if param.name in seen:
                raise ValueError(f"duplicate parameter name: {param.name!r}")
            seen.add(param.name)

    @classmethod
    def from_values(
        cls, names: Sequence[str], values: Sequence[float]
    ) -> tuple["ParameterSet", dict[str, float]]:
        if len(names) != len(values):
            raise ValueError(f"parameter names count {len(names)} does not match values count {len(values)}")
        parameters = tuple(Parameter(name, idx) for idx, name in enumerate(names))
        value_map = {name: float(value) for name, value in zip(names, values)}
        return ParameterSet(parameters), value_map

    def validate(self, values: Sequence[float]) -> None:
        if len(values) != len(self.parameters):
            raise ValueError(f"expected {len(self.parameters)} parameter values, got {len(values)}")
        for value in values:
            if not _is_finite_number(value):
                raise ValueError(f"parameter value {value!r} is not a finite number")

@dataclass(frozen=True)
class VariationalLayer:
    """One variational layer: rotation gates on every qubit, then entangling gates."""
    rotations: tuple[tuple[int, str, int], ...]
    entanglers: tuple[tuple[int, int, int], ...]

    def __post_init__(self) -> None:
        for item in self.rotations:
            qubit, gate, param_index = item
            if not isinstance(qubit, int) or qubit < 0:
                raise ValueError(f"rotation qubit {qubit!r} is invalid")
            if not isinstance(param_index, int) or param_index < 0:
                raise ValueError(f"rotation param index {param_index!r} is invalid")
        for item in self.entanglers:
            control, target, param_index = item
            if not isinstance(control, int) or control < 0:
                raise ValueError(f"entangler control {control!r} is invalid")
            if not isinstance(target, int) or target < 0:
                raise ValueError(f"entangler target {target!r} is invalid")
            if not isinstance(param_index, int) or param_index < 0:
                raise ValueError(f"entangler param index {param_index!r} is invalid")


    def lookup(self, name: str) -> int:
        for param in self.parameters:
            if param.name == name:
                return param.index
        raise KeyError(f"unknown parameter: {name!r}")

class ParameterizedProgram:
    """A quantum program with free symbolic parameters."""

    def __init__(self, n_qubits: int) -> None:
        if not isinstance(n_qubits, int) or n_qubits < 1:
            raise ValueError("n_qubits must be a positive integer")
        self.n_qubits = n_qubits
        self.parameters: list[Parameter] = []
        self.operations: list[Operation] = []

    def h(self, qubit: int) -> "ParameterizedProgram":
        """Apply Hadamard gate (concrete, no parameter)."""
        self._check_qubit(qubit)
        self.operations.append(Operation("h", (qubit,)))
        return self

    def x(self, qubit: int) -> "ParameterizedProgram":
        """Apply Pauli-X gate (concrete, no parameter)."""
        self._check_qubit(qubit)
        self.operations.append(Operation("x", (qubit,)))
        return self

    def y(self, qubit: int) -> "ParameterizedProgram":
        """Apply Pauli-Y gate (concrete, no parameter)."""
        self._check_qubit(qubit)
        self.operations.append(Operation("y", (qubit,)))
        return self

    def z(self, qubit: int) -> "ParameterizedProgram":
        """Apply Pauli-Z gate (concrete, no parameter)."""
        self._check_qubit(qubit)
        self.operations.append(Operation("z", (qubit,)))
        return self

    def ry(self, qubit: int, param_name: str) -> "ParameterizedProgram":
        """Apply Y-rotation with a named parameter."""
        self._check_qubit(qubit)
        param = Parameter(param_name, len(self.parameters))
        self.parameters.append(param)
        self.operations.append(Operation("ry", (qubit,)))
        return self

    def rz(self, qubit: int, param_name: str) -> "ParameterizedProgram":
        """Apply Z-rotation with a named parameter."""
        self._check_qubit(qubit)
        param = Parameter(param_name, len(self.parameters))
        self.parameters.append(param)
        self.operations.append(Operation("rz", (qubit,)))
        return self

    def cx(self, control: int, target: int) -> "ParameterizedProgram":
        """Apply CNOT gate (concrete, no parameter)."""
        self._check_qubit_pair(control, target)
        self.operations.append(Operation("cx", (control, target)))
        return self

    def cz(self, control: int, target: int) -> "ParameterizedProgram":
        """Apply CZ gate (concrete, no parameter)."""
        self._check_qubit_pair(control, target)
        self.operations.append(Operation("cz", (control, target)))
        return self

    def swap(self, q0: int, q1: int) -> "ParameterizedProgram":
        """Apply SWAP gate (concrete, no parameter)."""
        self._check_qubit_pair(q0, q1)
        self.operations.append(Operation("swap", (q0, q1)))
        return self

    def layer(self, rotations, entanglers=()) -> "ParameterizedProgram":
        """Append a variational layer."""
        for item in rotations:
            qubit, gate, param_index = item
            self._check_qubit(qubit)
            if param_index >= len(self.parameters):
                raise IndexError(f"rotation parameter index {param_index} is out of range (program has {len(self.parameters)} parameters)")
        for item in entanglers:
            control, target, param_index = item
            self._check_qubit_pair(control, target)
            if param_index >= len(self.parameters):
                raise IndexError(f"entangler parameter index {param_index} is out of range (program has {len(self.parameters)} parameters)")
        for qubit, gate, _ in rotations:
            self.operations.append(Operation(gate, (qubit,)))
        for control, target, _ in entanglers:
            self.operations.append(Operation("cx", (control, target)))
        return self

    def add_parameter(self, name: str, index=None) -> None:
        """Add a parameter explicitly."""
        if index is None:
            index = len(self.parameters)
        param = Parameter(name, index)
        if param in self.parameters:
            return
        self.parameters.append(param)

    def parameter_names(self) -> list:
        """Return the ordered parameter names."""
        return [param.name for param in self.parameters]

    def parameter_count(self) -> int:
        """Return the number of free parameters."""
        return len(self.parameters)


    def bind(self, values) -> Program:
        """Bind parameters to concrete values and return a Program.

        Both a positional sequence and a keyword dict are accepted.  Binding is
        fail-closed: out-of-range or non-finite values raise before any gate is
        emitted.

        Returns
        -------
        Program
            A concrete program with all parameters resolved to literal gate
            arguments.
        """
        if isinstance(values, dict):
            value_map = {}
            for param in self.parameters:
                if param.name not in values:
                    raise KeyError(f"binding dict is missing parameter: {param.name!r}")
                value_map[param.name] = float(values[param.name])
        else:
            self.parameters.validate(values)
            value_map = {param.name: float(value) for param, value in zip(self.parameters, values)}

        program = Program(self.n_qubits)
        for operation in self.operations:
            gate = operation.gate
            qubits = operation.qubits
            if gate == "ry":
                param_index = qubits[0]
                param = self.parameters[param_index]
                value = value_map[param.name]
                encoded = int(round(value * 1000) % 1000)
                program = program.then("ry", qubits[0], encoded)
            elif gate == "rz":
                param_index = qubits[0]
                param = self.parameters[param_index]
                value = value_map[param.name]
                encoded = int(round(value * 1000) % 1000)
                program = program.then("rz", qubits[0], encoded)
            else:
                program = program.then(gate, *qubits)
        return program

    def to_program(self) -> Program:
        """Return a concrete Program with no parameters."""
        return Program(self.n_qubits, tuple(self.operations))

    def __str__(self) -> str:
        lines = [f"ParameterizedProgram(n_qubits={self.n_qubits}, parameters={self.parameter_names()})"]
        for operation in self.operations:
            lines.append(f"  {operation.gate} {operation.qubits}")
        return "\n".join(lines)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ParameterizedProgram):
            return NotImplemented
        return (
            self.n_qubits == other.n_qubits
            and self.parameters == other.parameters
            and self.operations == other.operations
        )

    def __post_init__(self) -> None:
        for operation in self.operations:
            for qubit in operation.qubits:
                if qubit >= self.n_qubits:
                    raise ValueError(f"operation {operation.gate!r} addresses qubit {qubit}, outside a {self.n_qubits}-qubit register")

    def _check_qubit(self, qubit: int) -> None:
        if not isinstance(qubit, int) or qubit < 0 or qubit >= self.n_qubits:
            raise IndexError(f"qubit {qubit} out of range for {self.n_qubits}-qubit register")

    def _check_qubit_pair(self, q0: int, q1: int) -> None:
        self._check_qubit(q0)
        self._check_qubit(q1)
        if q0 == q1:
            raise ValueError(f"entangler {q0}-{q1} is a self-loop")

