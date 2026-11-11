"""Standard finite-dimensional gate operators, defined as complex matrices."""

from math import sqrt

from .operator import LinearOperator

IDENTITY_2 = LinearOperator.from_rows(((1, 0), (0, 1)))
PAULI_X = LinearOperator.from_rows(((0, 1), (1, 0)))
PAULI_Y = LinearOperator.from_rows(((0, -1j), (1j, 0)))
PAULI_Z = LinearOperator.from_rows(((1, 0), (0, -1)))
HADAMARD = LinearOperator.from_rows(((1 / sqrt(2), 1 / sqrt(2)),
                                     (1 / sqrt(2), -1 / sqrt(2))))
PHASE_S = LinearOperator.from_rows(((1, 0), (0, 1j)))
PHASE_T = LinearOperator.from_rows(((1, 0), (0, (1 + 1j) / sqrt(2))))

# Basis order: |00>, |01>, |10>, |11>; first qubit is the control.
CNOT = LinearOperator.from_rows((
    (1, 0, 0, 0),
    (0, 1, 0, 0),
    (0, 0, 0, 1),
    (0, 0, 1, 0),
))
