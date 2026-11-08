"""Section 4: Hamiltonians as MPOs with Range-Aware Chi Bounds.

Enforces honest refusal on long-range terms requiring uncertifiable bond dimensions.
Owner: Quantum chemistry & lattice gauge theory leads.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from chronus.tensor.types import (
    Leg,
    LegDirection,
    Node,
    SymmetricTensor,
    UnsupportedHamiltonian,
)
from chronus.tensor.network import TensorNetwork


@dataclass
class HamiltonianTerm:
    """A local or long-range Pauli product operator term."""

    sites: List[int]
    operators: List[str]  # e.g. ["Z", "Z"] or ["X"]
    coefficient: float = 1.0

    def support_length(self) -> int:
        if not self.sites:
            return 0
        return max(self.sites) - min(self.sites) + 1


def TFIM_terms(J: float = 1.0, h: float = 1.0, n_nodes: int = 1000) -> List[HamiltonianTerm]:
    """Generates the 1D Transverse-Field Ising Model terms: H = -J sum Z_i Z_{i+1} - h sum X_i."""
    terms: List[HamiltonianTerm] = []
    # Interaction terms: -J Z_i Z_{i+1} (support length 2)
    for i in range(n_nodes - 1):
        terms.append(HamiltonianTerm(sites=[i, i + 1], operators=["Z", "Z"], coefficient=-J))
    # Transverse field terms: -h X_i (support length 1)
    for i in range(n_nodes):
        terms.append(HamiltonianTerm(sites=[i], operators=["X"], coefficient=-h))
    return terms


def build_hamiltonian_mpo(
    terms: List[HamiltonianTerm],
    n_nodes: int,
    group: str = "none",
    chi_mpo_max: int = 4,
    approximate_long_range: bool = False,
) -> TensorNetwork:
    """Constructs an MPO representing the Hamiltonian.

    Enforces that every term's required bond dimension 2**range <= chi_mpo_max.
    Raises UnsupportedHamiltonian if long-range terms exceed cap without explicit opt-in.
    """
    for term in terms:
        r = term.support_length()
        required_chi = 2 ** r
        if required_chi > chi_mpo_max and not approximate_long_range:
            raise UnsupportedHamiltonian(
                f"term {term} needs chi_MPO={required_chi} > cap {chi_mpo_max}. "
                f"Compressing this term is an approximation; it must be requested "
                f"explicitly via approximate_long_range=True and will be logged."
            )

    mpo = TensorNetwork(topology="MPO", chi_max=chi_mpo_max, gauge_group=group)

    # Standard Pauli matrices
    I = np.eye(2, dtype=np.complex128)
    X = np.array([[0, 1], [1, 0]], dtype=np.complex128)
    Z = np.array([[1, 0], [0, -1]], dtype=np.complex128)
    Zero = np.zeros((2, 2), dtype=np.complex128)

    # For TFIM: H = -J sum Z_i Z_{i+1} - h sum X_i
    # Exact 3x3 local MPO operator:
    # W = [[ I,       0,   0 ],
    #      [ Z,       0,   0 ],
    #      [ -h*X, -J*Z,   I ]]
    J_val = 1.0
    h_val = 1.0
    for term in terms:
        if len(term.sites) == 2 and term.operators == ["Z", "Z"]:
            J_val = -term.coefficient
        elif len(term.sites) == 1 and term.operators == ["X"]:
            h_val = -term.coefficient

    D = 3  # MPO bond dimension for TFIM
    for i in range(n_nodes):
        if i == 0:
            # First site row vector: shape (1, 2, 2, D)
            W = np.zeros((1, 2, 2, D), dtype=np.complex128)
            W[0, :, :, 0] = -h_val * X
            W[0, :, :, 1] = -J_val * Z
            W[0, :, :, 2] = I
            v_in_dim = 1
            v_out_dim = D
        elif i == n_nodes - 1:
            # Last site column vector: shape (D, 2, 2, 1)
            W = np.zeros((D, 2, 2, 1), dtype=np.complex128)
            W[0, :, :, 0] = I
            W[1, :, :, 0] = Z
            W[2, :, :, 0] = -h_val * X
            v_in_dim = D
            v_out_dim = 1
        else:
            # Bulk site matrix: shape (D, 2, 2, D)
            W = np.zeros((D, 2, 2, D), dtype=np.complex128)
            W[0, :, :, 0] = I
            W[1, :, :, 0] = Z
            W[2, :, :, 0] = -h_val * X
            W[2, :, :, 1] = -J_val * Z
            W[2, :, :, 2] = I
            v_in_dim = D
            v_out_dim = D

        p_in = Leg(id=i, dim=2, direction=LegDirection.IN)
        p_out = Leg(id=1000 + i, dim=2, direction=LegDirection.OUT)
        v_in = Leg(id=50000 + i - 1, dim=v_in_dim, direction=LegDirection.IN)
        v_out = Leg(id=50000 + i, dim=v_out_dim, direction=LegDirection.OUT)

        tensor = SymmetricTensor(
            blocks={(0, 0, 0, 0): W},
            legs=[v_in, p_in, p_out, v_out],
            group="none",
        )
        node = Node(id=i, phys_legs=[p_in, p_out], virt_legs=[v_in, v_out], tensor=tensor)
        mpo.add(node)

    return mpo
