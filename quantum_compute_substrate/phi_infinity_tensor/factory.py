"""Factories for tensor variants."""

from __future__ import annotations
from .tensor import HYBAQuantumTensorXInfinity
from .generator import PhiCharacterRule
from .phi_identities import lucas


def create_base_tensor(mps_bond_dim: int = 128) -> HYBAQuantumTensorXInfinity:
    """Default: phi^37 in each of 6 axes."""
    return HYBAQuantumTensorXInfinity(scaling_exp=37, mps_bond_dim=mps_bond_dim)


def create_scaled_tensor(scaling_exp: int, mps_bond_dim: int = 128) -> HYBAQuantumTensorXInfinity:
    return HYBAQuantumTensorXInfinity(scaling_exp=scaling_exp, mps_bond_dim=mps_bond_dim)


def create_n_dimensional_tensor(
    num_axes: int, scaling_exp: int = 37, mps_bond_dim: int = 128
) -> HYBAQuantumTensorXInfinity:
    """Tensor with custom number of axes (default rank = 6).

    We keep the same six axis labels for rank <= 6, and repeat for rank > 6.
    """
    if num_axes < 2:
        raise ValueError("num_axes must be >= 2")
    t = HYBAQuantumTensorXInfinity(scaling_exp=scaling_exp, mps_bond_dim=mps_bond_dim)
    # Rebuild dimensions to the requested count.
    from .dimensions import TensorDimension, AXIS_NAMES, AXIS_MEANINGS

    size = lucas(scaling_exp)
    dims = []
    for i in range(num_axes):
        name = AXIS_NAMES[i % len(AXIS_NAMES)]
        meaning = AXIS_MEANINGS[i % len(AXIS_MEANINGS)]
        dims.append(
            TensorDimension(
                name=f"{name}_{i}", size=size, scaling_exp=scaling_exp, physical_meaning=meaning
            )
        )
    t.dimensions = tuple(dims)
    t.rule = PhiCharacterRule(N=size, rank=num_axes)
    from .network import MPSNetwork

    t.mps = MPSNetwork(physical_dim=size, rank=num_axes, bond_dim=mps_bond_dim)
    return t


def create_quantum_state_tensor(
    num_qubits: int, mps_bond_dim: int = 128
) -> HYBAQuantumTensorXInfinity:
    """Tensor whose axes have length 2 (qubits). Rank = num_qubits.

    Total elements = 2^num_qubits (as expected for a many-qubit state).
    """
    if num_qubits < 2:
        raise ValueError("num_qubits must be >= 2")
    from .dimensions import TensorDimension

    t = HYBAQuantumTensorXInfinity(scaling_exp=2, mps_bond_dim=mps_bond_dim)
    dims = tuple(
        TensorDimension(name=f"q{i}", size=2, scaling_exp=1, physical_meaning="qubit amplitude")
        for i in range(num_qubits)
    )
    t.dimensions = dims
    t._per_axis = 2
    t.rule = PhiCharacterRule(N=2, rank=num_qubits)
    from .network import MPSNetwork

    t.mps = MPSNetwork(physical_dim=2, rank=num_qubits, bond_dim=mps_bond_dim)
    return t
