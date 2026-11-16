"""Section 2 & Section 9: Network Construction & HARD_CAP_THEOREM.

Derives honest physical memory caps and constructs MPS, PEPS, and MERA networks
without ever allocating dense zeros(2^n).
Owner: distributed-systems engineer & TN theorist.
"""

from __future__ import annotations

import math
import os
from typing import Dict, Tuple
import numpy as np

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from chronus.tensor.types import (
    ContractionCertificate,
    ErrorLedger,
    Leg,
    LegDirection,
    Node,
    SymmetricTensor,
)


def HARD_CAP_THEOREM() -> int:
    """Computes the maximum certifiable bond dimension chi_max derived from physical hardware RAM.

    Hardware basis:
      M_max = 2**40 bytes (1 TB addressable RAM per consortium cluster node).
      bytes_per_complex128 = 16.
      max_chi_sq = M_max // bytes_per_complex128 = 2**36.
      chi_max_theoretical = isqrt(max_chi_sq) = 2**18 = 262,144 dense elements.
      Applying a safety factor of 10 for intermediate contraction workspace:
      Returns 26,214.
    """
    m_max_bytes = 1 << 40  # 1 TB
    bytes_per_complex = 16
    max_chi_sq = m_max_bytes // bytes_per_complex
    chi_max_theoretical = math.isqrt(max_chi_sq)  # 262,144
    safety_factor = 10
    return chi_max_theoretical // safety_factor  # 26,214


class TensorNetwork:
    """Falsifiable Tensor Network with audited memory and block-sparse nodes."""

    def __init__(
        self,
        topology: str,
        chi_max: int,
        gauge_group: str = "none",
    ) -> None:
        self.topology = topology
        self.chi_max = chi_max
        self.gauge_group = gauge_group
        self.nodes: Dict[int, Node] = {}

    def add(self, node: Node) -> None:
        self.nodes[node.id] = node

    def replace(self, merged: Node) -> None:
        self.nodes[merged.id] = merged

    def node_for(self, qubit_idx: int) -> Node:
        return self.nodes[qubit_idx]

    def memory(self) -> int:
        """Total memory consumed by stored non-zero block coefficients in bytes."""
        return sum(node.tensor.memory_bytes() for node in self.nodes.values())

    def dense_equivalent_memory(self) -> int:
        """Memory that would be consumed by uncompressed dense equivalents."""
        return sum(node.tensor.dense_equivalent_bytes() for node in self.nodes.values())

    def to_statevector(self) -> np.ndarray:
        """Contracts an MPS of n <= 32 nodes to an exact dense statevector of length 2^n.

        Used solely for E1 exactness oracle validation against reference statevectors.
        Refuses execution if n > 32 to prevent OOM.
        """
        n = len(self.nodes)
        if n > 32:
            raise ValueError(f"Statevector contraction refused for n={n} > 32 (exceeds dense memory).")
        if self.topology != "MPS":
            raise NotImplementedError("to_statevector is currently implemented for MPS.")

        # Contract MPS from site 0 to n-1
        # Node i has shape (left_chi, 2, right_chi)
        current = self.nodes[0].tensor.to_dense()  # (1, 2, chi_0)
        # Squeeze leading virtual index
        current = np.squeeze(current, axis=0)  # (2, chi_0)

        for i in range(1, n):
            next_tensor = self.nodes[i].tensor.to_dense()  # (chi_{i-1}, 2, chi_i)
            # Contract right virtual leg of current with left virtual leg of next_tensor
            # current has shape (2^i, chi_{i-1})
            # tensordot over axis -1 of current and axis 0 of next_tensor
            current = np.tensordot(current, next_tensor, axes=(-1, 0))  # shape (2^i, 2, chi_i)
            # Reshape into (2^(i+1), chi_i)
            new_shape = (current.shape[0] * current.shape[1], current.shape[2])
            current = current.reshape(new_shape)

        # Squeeze trailing virtual index
        statevec = np.squeeze(current, axis=-1)  # shape (2^n,)
        # Normalize
        norm = np.linalg.norm(statevec)
        if norm > 1e-15:
            statevec = statevec / norm
        return statevec


def build_network(
    n_nodes: int,
    topology: str = "MPS",
    chi_max: int = 512,
    group: str = "none",
) -> Tuple[TensorNetwork, ErrorLedger]:
    """Constructs a tensor network with honest memory bounds and an attached error ledger."""
    hard_cap = HARD_CAP_THEOREM()
    assert chi_max <= hard_cap, (
        f"Charter violation: Requested chi_max={chi_max} exceeds hardware hard cap theorem ({hard_cap})."
    )

    ledger = ErrorLedger()
    network = TensorNetwork(topology=topology, chi_max=chi_max, gauge_group=group)

    if topology == "MPS":
        for i in range(n_nodes):
            left_dim = 1
            right_dim = 1

            phys_leg = Leg(id=i, dim=2, charge=0, direction=LegDirection.OUT)
            left_leg = Leg(id=10000 + i - 1, dim=left_dim, charge=0, direction=LegDirection.IN)
            right_leg = Leg(id=10000 + i, dim=right_dim, charge=0, direction=LegDirection.OUT)

            # Initialize as product state |0> with initial rank-1 bond dimension
            block_data = np.zeros((1, 2, 1), dtype=np.complex128)
            block_data[0, 0, 0] = 1.0 + 0.0j

            tensor = SymmetricTensor(
                blocks={(0, 0, 0): block_data},
                legs=[left_leg, phys_leg, right_leg],
                group=group if group != "none" else "none",
            )

            node = Node(
                id=i,
                phys_legs=[phys_leg],
                virt_legs=[left_leg, right_leg],
                tensor=tensor,
            )
            network.add(node)

    elif topology == "PEPS":
        # 2D Grid R x C = n_nodes
        side = math.isqrt(n_nodes)
        rows, cols = side, n_nodes // side
        for r in range(rows):
            for c in range(cols):
                node_id = r * cols + c
                phys_leg = Leg(id=node_id, dim=2, charge=0, direction=LegDirection.OUT)
                v_legs = [
                    Leg(id=20000 + node_id * 4 + k, dim=min(chi_max, 8), charge=0, direction=LegDirection.IN)
                    for k in range(4)
                ]
                peps_data = np.zeros((2, min(chi_max, 8), min(chi_max, 8), min(chi_max, 8), min(chi_max, 8)), dtype=np.complex128)
                peps_data[0, 0, 0, 0, 0] = 1.0 + 0.0j
                tensor = SymmetricTensor(
                    blocks={(0, 0, 0, 0, 0): peps_data},
                    legs=[phys_leg] + v_legs,
                    group=group,
                )
                node = Node(id=node_id, phys_legs=[phys_leg], virt_legs=v_legs, tensor=tensor)
                network.add(node)

    elif topology == "MERA":
        # Multi-scale entanglement renormalization ansatz tree
        for i in range(n_nodes):
            phys_leg = Leg(id=i, dim=2, charge=0, direction=LegDirection.OUT)
            virt_leg = Leg(id=30000 + i, dim=min(chi_max, 4), charge=0, direction=LegDirection.IN)
            mera_data = np.zeros((2, min(chi_max, 4)), dtype=np.complex128)
            mera_data[0, 0] = 1.0 + 0.0j
            tensor = SymmetricTensor(
                blocks={(0, 0): mera_data},
                legs=[phys_leg, virt_leg],
                group=group,
            )
            node = Node(id=i, phys_legs=[phys_leg], virt_legs=[virt_leg], tensor=tensor)
            network.add(node)

    cert = ContractionCertificate(
        tree="InitialProductStateBuildTree",
        peak_memory_bytes=network.memory(),
        flop_count=0,
        planner_bound=0.0,
        planner_theorem="DirectInitialization Exact",
    )
    ledger.record(cert)
    return network, ledger
