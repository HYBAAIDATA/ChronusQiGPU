"""
Part 5: Tensor Networks (MPS)
==============================
Exponential memory compression via Matrix Product States.
"""

import numpy as np
from typing import List


class MatrixProductStateProcessor:
    """Part 5: Exponential memory compression via MPS."""

    def __init__(self, num_sites: int = 4096, bond_dim: int = 128):
        self.num_sites = min(num_sites, 16)  # Practical limit for testing
        self.bond_dim = min(bond_dim, 32)   # Practical limit
        self.target_num_sites = num_sites
        self.target_bond_dim = bond_dim
        self.tensors = self.initialize_mps()

    def initialize_mps(self) -> List[np.ndarray]:
        """Initialize MPS with given bond dimension."""
        tensors = []
        for i in range(self.num_sites):
            if i == 0:
                shape = (1, min(self.bond_dim, 2), 2)
            elif i == self.num_sites - 1:
                shape = (min(self.bond_dim, 2), 1, 2)
            else:
                shape = (min(self.bond_dim, 2), min(self.bond_dim, 2), 2)

            tensor = np.random.randn(*shape) + 1j * np.random.randn(*shape)
            tensor = tensor / np.linalg.norm(tensor)
            tensors.append(tensor)

        return tensors

    def compress_state(self, full_state: np.ndarray) -> List[np.ndarray]:
        """Compress full state to MPS via sequential SVD."""
        psi = full_state.reshape(-1, 1).astype(np.complex128)
        tensors = []
        n_sites = int(np.log2(len(full_state))) if len(full_state) > 0 else 0

        for i in range(min(n_sites, self.num_sites) - 1):
            psi = psi.reshape(-1, psi.shape[1])
            if psi.shape[0] < 2:
                break
            U, S, Vh = np.linalg.svd(psi, full_matrices=False)
            trunc = min(len(S), self.bond_dim, U.shape[0] // 2)
            if trunc < 1:
                break
            U = U[:, :trunc]
            S = S[:trunc]
            Vh = Vh[:trunc, :]

            tensor = U.reshape(U.shape[0] // 2, 2, trunc)
            tensors.append(tensor)
            psi = np.diag(S) @ Vh

        if psi.size > 0 and psi.ndim >= 2:
            tensor = psi.reshape(psi.shape[0], 1, psi.shape[1])
            tensors.append(tensor)
        elif psi.size > 0:
            tensor = psi.reshape(max(psi.shape[0], 1), 1, 1)
            tensors.append(tensor)

        return tensors

    def contract_mps(self) -> np.ndarray:
        """Contract MPS to full state vector."""
        if not self.tensors:
            return np.array([1.0])
        result = self.tensors[0]
        for i in range(1, len(self.tensors)):
            result = np.tensordot(result, self.tensors[i], axes=([-1], [0]))
        # Flatten all but the physical (last) indices
        while result.ndim > 1:
            result = result.reshape(-1, result.shape[-1]) if result.ndim > 2 else result.reshape(-1)
        return result.reshape(-1)

    def apply_local_operator(self, operator: np.ndarray, site: int):
        """Apply local operator to a specific site."""
        if site < 0 or site >= len(self.tensors):
            return
        self.tensors[site] = np.tensordot(operator, self.tensors[site], axes=([1], [2]))
        self.tensors[site] = np.transpose(self.tensors[site], (1, 2, 0))

        if self.tensors[site].shape[1] > self.bond_dim:
            self.renormalize()

    def renormalize(self):
        """Renormalize MPS maintaining bond dimension."""
        for i in range(len(self.tensors) - 1):
            shape = self.tensors[i].shape
            combined = np.tensordot(self.tensors[i], self.tensors[i + 1], axes=([-1], [0]))
            combined = combined.reshape(-1, combined.shape[-1])

            U, S, Vh = np.linalg.svd(combined, full_matrices=False)
            trunc = min(len(S), self.bond_dim)
            U = U[:, :trunc]
            S = S[:trunc]
            Vh = Vh[:trunc, :]

            self.tensors[i] = U.reshape(shape[0], shape[1], trunc)
            next_shape = self.tensors[i + 1].shape
            self.tensors[i + 1] = (np.diag(S) @ Vh).reshape(trunc, next_shape[1], next_shape[2])

    def memory_savings(self) -> float:
        """Calculate memory compression ratio: MPS memory / full state memory.
        Returns a value between 0 and 1 (fraction of full memory used by MPS).
        Uses logarithms to avoid overflow for large num_sites.
        """
        import math
        log_full = self.target_num_sites * math.log(2)
        log_mps = math.log(self.target_num_sites * self.target_bond_dim ** 2 * 2 + 1)
        # Return the ratio as exp(log_mps - log_full) if it's representable, else 0
        log_ratio = log_mps - log_full
        if log_ratio < -700:
            return 0.0  # Underflow to zero
        return math.exp(log_ratio)

    def get_specs(self) -> dict:
        """Return MPS specifications."""
        return {
            "num_sites": self.num_sites,
            "bond_dim": self.bond_dim,
            "target_num_sites": self.target_num_sites,
            "target_bond_dim": self.target_bond_dim,
            "memory_savings_ratio": self.memory_savings(),
            "num_tensors": len(self.tensors),
        }
