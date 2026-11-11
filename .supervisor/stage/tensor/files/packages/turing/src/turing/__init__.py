"""TURING: first-principles finite-dimensional quantum mathematics for HYBA Data.

This is a mathematical library over complex Hilbert spaces, not a hardware SDK
or physical-device simulator. See the package README for scope and limits.
"""

from .gates import (
    CNOT,
    HADAMARD,
    IDENTITY_2,
    PAULI_X,
    PAULI_Y,
    PAULI_Z,
    PHASE_S,
    PHASE_T,
)
from .measurement import (
    ProjectiveMeasurement,
    born_probabilities,
    computational_basis_measurement,
)
from .operator import LinearOperator
from .state import QuantumState
from .kronecker import tensor_operators, tensor_states

__all__ = [
    "CNOT",
    "HADAMARD",
    "IDENTITY_2",
    "LinearOperator",
    "PAULI_X",
    "PAULI_Y",
    "PAULI_Z",
    "PHASE_S",
    "PHASE_T",
    "ProjectiveMeasurement",
    "QuantumState",
    "born_probabilities",
    "computational_basis_measurement",
    "tensor_operators",
    "tensor_states",
]

__version__ = "0.2.0.dev0"
