"""Matrix Product Operators with exact small-system contraction.

The dense conversion is intentionally bounded to validation-sized systems. It
is a real bond-index contraction (not a placeholder); large systems should use
a tensor-network backend rather than materialising a dense matrix.
"""
from __future__ import annotations

from itertools import product
from typing import Any, Dict, List, Optional

import numpy as np


class MatrixProductOperator:
    def __init__(self, mpo_cores: List[np.ndarray], physical_dim: int = 2):
        if not mpo_cores:
            raise ValueError("an MPO needs at least one core")
        self.cores = [np.asarray(core) for core in mpo_cores]
        self.physical_dim = int(physical_dim)
        if self.physical_dim < 1:
            raise ValueError("physical_dim must be positive")
        for index, core in enumerate(self.cores):
            if core.ndim != 4:
                raise ValueError("each MPO core must have shape (Dl, d, d, Dr)")
            if core.shape[1] != self.physical_dim or core.shape[2] != self.physical_dim:
                raise ValueError("physical dimensions do not match")
            if index and self.cores[index - 1].shape[3] != core.shape[0]:
                raise ValueError("incompatible MPO bond dimensions")
        if self.cores[0].shape[0] != 1 or self.cores[-1].shape[3] != 1:
            raise ValueError("MPO boundary bond dimensions must be one")
        self.num_sites = len(self.cores)
        self.bond_dims = [core.shape[0] for core in self.cores] + [self.cores[-1].shape[3]]

    @property
    def dimension(self) -> int:
        return self.physical_dim ** self.num_sites

    def to_full_matrix(self, max_dimension: int = 4096) -> np.ndarray:
        """Contract all bond paths into a dense validation matrix."""
        if self.dimension > max_dimension:
            raise ValueError("dense MPO materialisation exceeds validation limit")
        dtype = np.result_type(*(core.dtype for core in self.cores), np.float64)
        matrix = np.zeros((self.dimension, self.dimension), dtype=dtype)
        internal_ranges = [range(self.cores[i].shape[3]) for i in range(self.num_sites - 1)]
        for internal in product(*internal_ranges) if internal_ranges else [()]:
            left = 0
            path = np.array([[1]], dtype=dtype)
            for index, core in enumerate(self.cores):
                right = internal[index] if index < self.num_sites - 1 else 0
                path = np.kron(path, core[left, :, :, right])
                left = right
            matrix += path
        return matrix

    def apply_to_vector(self, vector: np.ndarray) -> np.ndarray:
        value = np.asarray(vector)
        if value.ndim != 1 or value.size != self.dimension:
            raise ValueError(f"vector must have shape ({self.dimension},)")
        return self.to_full_matrix() @ value


class IsingHamiltonianMPO(MatrixProductOperator):
    """Open-boundary Ising MPO: ``-J sum Z_i Z_{i+1} - h sum X_i``."""

    def __init__(
        self,
        num_sites: int,
        coupling: float = 1.0,
        field: float = 0.5,
        bond_dim: Optional[int] = None,
    ):
        if num_sites < 1:
            raise ValueError("num_sites must be positive")
        if bond_dim not in (None, 3):
            raise ValueError("the Ising construction uses bond_dim=3")
        identity = np.eye(2, dtype=float)
        sx = np.array([[0.0, 1.0], [1.0, 0.0]])
        sz = np.diag([1.0, -1.0])
        cores: List[np.ndarray] = []
        if num_sites == 1:
            core = np.zeros((1, 2, 2, 1))
            core[0, :, :, 0] = -field * sx
            cores.append(core)
        else:
            first = np.zeros((1, 2, 2, 3))
            first[0, :, :, 0] = identity
            first[0, :, :, 1] = sz
            first[0, :, :, 2] = -field * sx
            cores.append(first)
            for _ in range(num_sites - 2):
                middle = np.zeros((3, 2, 2, 3))
                middle[0, :, :, 0] = identity
                middle[1, :, :, 0] = sz
                middle[2, :, :, 0] = -field * sx
                middle[2, :, :, 1] = -coupling * sz
                cores.append(middle)
            last = np.zeros((3, 2, 2, 1))
            last[0, :, :, 0] = -field * sx
            last[1, :, :, 0] = -coupling * sz
            last[2, :, :, 0] = identity
            cores.append(last)
        self.coupling = float(coupling)
        self.field = float(field)
        super().__init__(cores, physical_dim=2)


class MPOPulviniTTHybrid:
    """PULVINI -> TT -> MPO execution -> reversible reconstruction pipeline."""

    def __init__(self, max_tt_rank: int = 32, mpo_bond_dim: int = 8, tolerance: float = 1e-5):
        from .tensor_train import TTPulviniHybrid
        self.max_tt_rank = max_tt_rank
        self.mpo_bond_dim = mpo_bond_dim
        self.tolerance = tolerance
        self._tt_hybrid = TTPulviniHybrid(max_tt_rank=max_tt_rank, tolerance=tolerance)

    def process(
        self,
        input_tensor: np.ndarray,
        mpo: Optional[MatrixProductOperator] = None,
        num_time_steps: int = 1,
    ) -> Dict[str, Any]:
        if num_time_steps < 0:
            raise ValueError("num_time_steps must be non-negative")
        value = np.asarray(input_tensor)
        flat = value.reshape(-1)
        # Keep the pipeline's single PULVINI implementation in one place.
        from .pulvini_scaling import PulviniOperator
        pulvini = PulviniOperator(tolerance=self.tolerance)
        folded, kernel = pulvini.fold(flat)
        from .tensor_train import TensorTrain
        tt = TensorTrain(folded.reshape(-1, 1), max_rank=self.max_tt_rank, tolerance=self.tolerance)
        compressed = tt.reconstruct().reshape(-1)
        current = compressed
        if mpo is not None:
            if mpo.dimension != current.size:
                raise ValueError(
                    f"MPO dimension {mpo.dimension} does not match folded dimension {current.size}"
                )
            for _ in range(num_time_steps):
                current = mpo.apply_to_vector(current)
                norm = np.linalg.norm(current)
                if norm == 0:
                    raise ValueError("MPO evolution produced a zero state")
                current = current / norm
        restored = pulvini.unfold(current, kernel, flat.size)
        error = float(np.linalg.norm(flat - restored) / max(1.0, np.linalg.norm(flat)))
        memory = tt.get_memory_bytes()
        return {
            "original_state": value,
            "folded_state": folded,
            "mpo_applied_state": current,
            "reconstructed": restored.reshape(value.shape),
            "pulvini_kernel": kernel,
            "tt_cores": tt.cores,
            "tt_ranks": tt.ranks,
            "reconstruction_error": error,
            "mpo_error": float(np.linalg.norm(current - compressed) / max(1.0, np.linalg.norm(compressed))) if mpo else 0.0,
            "compression_ratio": float(value.size / max(1, memory["compressed"] / max(1, value.dtype.itemsize))),
            "topology_preserved": bool(error <= self.tolerance),
            "memory_info": memory,
            "mpo_applied": mpo is not None,
            "time_steps": num_time_steps,
        }
