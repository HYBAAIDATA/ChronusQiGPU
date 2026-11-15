"""Tensor products for finite-dimensional states and operators."""

from __future__ import annotations

from .operator import LinearOperator
from .state import QuantumState


def tensor_states(*states: QuantumState) -> QuantumState:
    """Return the ordered Kronecker product of normalized state vectors."""
    if not states:
        raise ValueError("at least one state is required")
    amplitudes = (1.0 + 0.0j,)
    for state in states:
        if not isinstance(state, QuantumState):
            raise TypeError("all arguments must be QuantumState instances")
        amplitudes = tuple(a * b for a in amplitudes for b in state.amplitudes)
    return QuantumState(amplitudes)


def tensor_operators(*operators: LinearOperator) -> LinearOperator:
    """Return the ordered Kronecker product of square operators."""
    if not operators:
        raise ValueError("at least one operator is required")
    matrix = ((1.0 + 0.0j,),)
    for operator in operators:
        if not isinstance(operator, LinearOperator):
            raise TypeError("all arguments must be LinearOperator instances")
        rows_a, cols_a = len(matrix), len(matrix[0])
        rows_b, cols_b = operator.dimension, operator.dimension
        matrix = tuple(
            tuple(matrix[i][j] * operator.matrix[k][ell]
                  for j in range(cols_a) for ell in range(cols_b))
            for i in range(rows_a) for k in range(rows_b)
        )
    return LinearOperator(matrix)
