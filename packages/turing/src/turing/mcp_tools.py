"""Bounded, stateless TURING mathematical tools for an existing MCP registry.

This module never starts a server or imports Chronus. Installation into an
enterprise registry is explicitly separate from deployment/authentication.
All complex values crossing the JSON boundary use [real, imaginary].
"""
from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from . import (
    CNOT, HADAMARD, IDENTITY_2, PAULI_X, PAULI_Y, PAULI_Z,
    PHASE_S, PHASE_T, LinearOperator, QuantumState,
    born_probabilities,
    tensor_operators, tensor_states,
)

MAX_DIMENSION = 64
MAX_EVOLUTION_STEPS = 16

_NAMED = {
    "I": IDENTITY_2, "X": PAULI_X, "Y": PAULI_Y, "Z": PAULI_Z,
    "H": HADAMARD, "S": PHASE_S, "T": PHASE_T, "CNOT": CNOT,
}


def _number(value: Any) -> float:
    if type(value) not in (int, float):
        raise ValueError("numeric values must be JSON numbers, not booleans")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError("numeric value exceeds representable range") from exc
    if not math.isfinite(result):
        raise ValueError("non-finite numbers are forbidden")
    return result


def _complex(value: Any) -> complex:
    if type(value) in (int, float):
        return complex(_number(value))
    if type(value) in (tuple, list) and len(value) == 2:
        return complex(_number(value[0]), _number(value[1]))
    raise ValueError("complex values must be a number or [real, imaginary]")


def _encode(value: complex) -> list[float]:
    if not math.isfinite(value.real) or not math.isfinite(value.imag):
        raise ValueError("computed complex value is not finite")
    return [float(value.real), float(value.imag)]


def _state(values: list[Any]) -> QuantumState:
    if not isinstance(values, list) or not 1 <= len(values) <= MAX_DIMENSION:
        raise ValueError("state dimension must be between 1 and 64")
    return QuantumState(tuple(_complex(v) for v in values))


def _operator(value: Any) -> LinearOperator:
    if isinstance(value, str):
        try:
            return _NAMED[value.upper()]
        except KeyError as exc:
            raise ValueError("unknown TURING operator") from exc
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_DIMENSION:
        raise ValueError("operator dimension must be between 1 and 64")
    dimension = len(value)
    if any(not isinstance(row, list) or len(row) != dimension for row in value):
        raise ValueError("operator must be a square JSON matrix")
    return LinearOperator.from_rows([[_complex(v) for v in row] for row in value])


def _matrix(value: LinearOperator) -> list[list[list[float]]]:
    return [[_encode(x) for x in row] for row in value.matrix]


def _state_result(value: QuantumState) -> dict[str, Any]:
    return {
        "dimension": value.dimension,
        "amplitudes": [_encode(x) for x in value.amplitudes],
        "probabilities": list(born_probabilities(value)),
    }


def turing_basis(dimension: int, index: int) -> dict[str, Any]:
    """Construct a mathematical basis state without a hardware backend."""
    if type(dimension) is not int or not 1 <= dimension <= MAX_DIMENSION:
        raise ValueError("dimension must be an integer in [1, 64]")
    return _state_result(QuantumState.basis(dimension, index))


def turing_normalize(amplitudes: list[Any]) -> dict[str, Any]:
    """Explicitly normalize a nonzero complex vector into a ket."""
    if not isinstance(amplitudes, list) or not 1 <= len(amplitudes) <= MAX_DIMENSION:
        raise ValueError("state dimension must be between 1 and 64")
    values = [_complex(x) for x in amplitudes]
    scale = max(abs(v) for v in values)
    if scale == 0:
        raise ValueError("the zero vector cannot be normalized")
    scaled = [v / scale for v in values]
    return _state_result(QuantumState.normalized(scaled))


def turing_operator(operator: Any) -> dict[str, Any]:
    """Construct/validate a named or JSON-matrix operator."""
    op = _operator(operator)
    return {
        "dimension": op.dimension, "matrix": _matrix(op),
        "unitary": op.is_unitary(), "hermitian": op.is_hermitian(),
    }


def turing_compose(left: Any, right: Any) -> dict[str, Any]:
    """Compose operators: the right-hand operator acts first."""
    return turing_operator(_matrix(_operator(left).compose(_operator(right))))


def turing_tensor(left: Any, right: Any, kind: str) -> dict[str, Any]:
    """Compute an ordered tensor product of two states or operators."""
    if kind == "state":
        a, b = _state(left), _state(right)
        if a.dimension * b.dimension > MAX_DIMENSION:
            raise ValueError("tensor result exceeds maximum dimension")
        return _state_result(tensor_states(a, b))
    if kind == "operator":
        a, b = _operator(left), _operator(right)
        if a.dimension * b.dimension > MAX_DIMENSION:
            raise ValueError("tensor result exceeds maximum dimension")
        return turing_operator(_matrix(tensor_operators(a, b)))
    raise ValueError("kind must be 'state' or 'operator'")


def turing_apply(operator: Any, amplitudes: list[Any]) -> dict[str, Any]:
    """Apply any linear map, retaining unnormalised mathematical results."""
    op, state = _operator(operator), _state(amplitudes)
    output = op.apply_amplitudes(state.amplitudes)
    norm_squared = _number(sum(abs(x) ** 2 for x in output))
    return {
        "dimension": len(output), "amplitudes": [_encode(x) for x in output],
        "norm_squared": norm_squared, "unitary": op.is_unitary(),
    }


def turing_evolve(operators: list[Any], amplitudes: list[Any]) -> dict[str, Any]:
    """Evolve under an ordered sequence of unitary mathematical operators."""
    if not isinstance(operators, list) or not 1 <= len(operators) <= MAX_EVOLUTION_STEPS:
        raise ValueError("provide 1 to 16 evolution operators")
    state = _state(amplitudes)
    for item in operators:
        op = _operator(item)
        if not op.is_unitary():
            raise ValueError("evolution operators must be unitary")
        state = op.apply(state)
    return _state_result(state)


def turing_expectation(operator: Any, amplitudes: list[Any]) -> dict[str, Any]:
    """Evaluate the expectation <psi|A|psi>; distinguish observables."""
    op, state = _operator(operator), _state(amplitudes)
    return {
        "expectation": _encode(op.expectation_value(state)),
        "hermitian_observable": op.is_hermitian(),
    }


def turing_measure(amplitudes: list[Any], outcome: int = -1) -> dict[str, Any]:
    """Return exact input-derived Born probabilities; optionally condition."""
    state = _state(amplitudes)
    result: dict[str, Any] = {"probabilities": list(born_probabilities(state))}
    if type(outcome) is not int:
        raise ValueError("outcome must be an integer")
    if outcome != -1:
        if not 0 <= outcome < state.dimension:
            raise ValueError("outcome index is out of range")
        probability = result["probabilities"][outcome]
        if probability == 0.0:
            raise ValueError("cannot condition on a zero-probability outcome")
        amplitude = state.amplitudes[outcome] / math.sqrt(probability)
        collapsed = QuantumState(tuple(
            amplitude if i == outcome else 0.0j for i in range(state.dimension)
        ))
        result["collapsed_state"] = _state_result(collapsed)
    return result


def turing_decompose_pauli(operator: Any) -> dict[str, Any]:
    """Decompose a 2x2 operator in the Pauli basis, with numerical coefficients."""
    op = _operator(operator)
    if op.dimension != 2:
        raise ValueError("Pauli decomposition currently supports 2x2 operators only")
    terms: dict[str, list[float]] = {}
    for name in ("I", "X", "Y", "Z"):
        basis = _NAMED[name]
        coefficient = sum(
            basis.matrix[i][j] * op.matrix[j][i] / 2
            for i in range(2) for j in range(2)
        )
        if not math.isfinite(coefficient.real) or not math.isfinite(coefficient.imag):
            raise ValueError("Pauli coefficients must be finite complex numbers")
        terms[name] = _encode(coefficient)
    return {"basis": "I,X,Y,Z", "coefficients": terms}


TURING_MCP_TOOLS: dict[str, Callable[..., dict[str, Any]]] = {
    function.__name__: function
    for function in (
        turing_basis, turing_normalize, turing_operator, turing_compose,
        turing_tensor, turing_apply, turing_evolve, turing_expectation,
        turing_measure, turing_decompose_pauli,
    )
}


def register_turing_tools(server: Any) -> tuple[str, ...]:
    """Add tools to an EXISTING MCP registry. Never starts a separate server.

    Supports a FastMCP-compatible .tool(name=...) decorator or an explicit
    .register_tool(name, handler) API. No guessed private registry mutation.
    Raises before mutation if neither contract is offered.
    """
    decorate = getattr(server, "tool", None)
    register = getattr(server, "register_tool", None)
    if not callable(decorate) and not callable(register):
        raise TypeError("MCP server lacks tool(name=...) or register_tool(name, handler)")
    for name, handler in TURING_MCP_TOOLS.items():
        if callable(decorate):
            decorate(name=name)(handler)
        else:
            register(name, handler)
    return tuple(TURING_MCP_TOOLS)
