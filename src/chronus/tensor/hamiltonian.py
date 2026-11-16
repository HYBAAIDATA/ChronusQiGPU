"""Section 4: Hamiltonians as MPOs with Range-Aware Chi Bounds.

Enforces honest refusal on long-range terms requiring uncertifiable bond dimensions.
Owner: Quantum chemistry & lattice gauge theory leads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List
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
    if type(n_nodes) is not int or n_nodes < 1:
        raise ValueError("n_nodes must be a positive integer")
    if type(chi_mpo_max) is not int or chi_mpo_max < 1:
        raise ValueError("chi_mpo_max must be a positive integer")
    if group != "none":
        raise UnsupportedHamiltonian("symmetry-resolved MPO construction is not implemented")
    identity = np.eye(2, dtype=np.complex128)
    pauli = {
        "I": identity,
        "X": np.array([[0, 1], [1, 0]], dtype=np.complex128),
        "Y": np.array([[0, -1j], [1j, 0]], dtype=np.complex128),
        "Z": np.diag([1, -1]).astype(np.complex128),
    }
    for term in terms:
        if (len(term.sites) != len(term.operators) or len(set(term.sites)) != len(term.sites)
                or any(type(site) is not int or not 0 <= site < n_nodes for site in term.sites)
                or any(op not in pauli for op in term.operators)):
            raise ValueError("Hamiltonian term has invalid sites or Pauli operators")
        if not np.isfinite(term.coefficient) or np.iscomplexobj(term.coefficient):
            raise ValueError("Hermitian Pauli Hamiltonians require finite real coefficients")
        required_chi = 2 ** term.support_length()
        if required_chi > chi_mpo_max:
            raise UnsupportedHamiltonian(
                f"term {term} needs chi_MPO={required_chi} > cap {chi_mpo_max}. "
                "Compressing this term is an approximation; no certified approximation is implemented."
            )

    # Nearest-neighbour ZZ plus arbitrary on-site X: exact, nonuniform D=3 MPO.
    tfim = all((len(t.sites) == 1 and t.operators == ["X"])
               or (len(t.sites) == 2 and t.operators == ["Z", "Z"]
                   and abs(t.sites[1] - t.sites[0]) == 1) for t in terms)
    blocks = []
    if tfim and n_nodes > 1 and chi_mpo_max >= 3:
        fields = np.zeros(n_nodes)
        couplings = np.zeros(n_nodes - 1)
        for term in terms:
            if len(term.sites) == 1:
                fields[term.sites[0]] += term.coefficient
            else:
                couplings[min(term.sites)] += term.coefficient
        for i in range(n_nodes):
            w = np.zeros((3, 2, 2, 3), dtype=np.complex128)
            w[0, :, :, 0] = identity
            w[1, :, :, 0] = pauli["Z"]
            w[2, :, :, 0] = fields[i] * pauli["X"]
            if i < n_nodes - 1:
                w[2, :, :, 1] = couplings[i] * pauli["Z"]
            w[2, :, :, 2] = identity
            if i == 0:
                w = w[2:3]
            if i == n_nodes - 1:
                w = w[:, :, :, 0:1]
            blocks.append(w)
    else:
        # Exact sum of product operators; each term has its own virtual channel.
        count = max(1, len(terms))
        if n_nodes > 1 and count > chi_mpo_max:
            raise UnsupportedHamiltonian("exact sum-of-products MPO exceeds bond budget")
        products = []
        for term in terms:
            local = [identity.copy() for _ in range(n_nodes)]
            for site, operator in zip(term.sites, term.operators):
                local[site] = pauli[operator]
            local[0] = term.coefficient * local[0]
            products.append(local)
        if not products:
            products = [[np.zeros((2, 2), dtype=np.complex128)] + [identity] * (n_nodes - 1)]
        for i in range(n_nodes):
            left, right = (1 if i == 0 else count), (1 if i == n_nodes - 1 else count)
            w = np.zeros((left, 2, 2, right), dtype=np.complex128)
            for k, product in enumerate(products):
                w[0 if i == 0 else k, :, :, 0 if i == n_nodes - 1 else k] += product[i]
            blocks.append(w)

    mpo = TensorNetwork(topology="MPO", chi_max=chi_mpo_max, gauge_group=group)
    for i, w in enumerate(blocks):
        p_in = Leg(id=i, dim=2, direction=LegDirection.IN)
        p_out = Leg(id=n_nodes + i, dim=2, direction=LegDirection.OUT)
        v_in = Leg(id=2 * n_nodes + i - 1, dim=w.shape[0], direction=LegDirection.IN)
        v_out = Leg(id=2 * n_nodes + i, dim=w.shape[3], direction=LegDirection.OUT)
        tensor = SymmetricTensor(blocks={(0, 0, 0, 0): w},
                                 legs=[v_in, p_in, p_out, v_out], group="none")
        mpo.add(Node(id=i, phys_legs=[p_in, p_out], virt_legs=[v_in, v_out], tensor=tensor))
    return mpo
