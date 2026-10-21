"""Numerically stable Tensor-Train decomposition and PULVINI hybrid."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .pulvini_scaling import PulviniOperator


class TensorTrain:
    """TT-SVD representation with explicit rank/error accounting."""

    def __init__(
        self,
        tensor: np.ndarray,
        max_rank: Optional[int] = None,
        tolerance: float = 1e-5,
    ):
        value = np.asarray(tensor)
        if value.ndim < 1:
            raise ValueError("tensor must have at least one dimension")
        if tolerance < 0 or not np.isfinite(tolerance):
            raise ValueError("tolerance must be finite and non-negative")
        if max_rank is not None and max_rank < 1:
            raise ValueError("max_rank must be positive")
        self.original_shape = tuple(value.shape)
        self.original_size = int(value.size)
        self.ndim = value.ndim
        self.tolerance = float(tolerance)
        self.max_rank = max_rank
        self.cores: List[np.ndarray] = []
        self.ranks: List[int] = [1]
        self._decompose(value)

    def _choose_rank(self, singular_values: np.ndarray) -> int:
        available = len(singular_values)
        if self.tolerance == 0:
            rank = available
        else:
            # Retain the smallest rank whose discarded relative energy is <= tol.
            tail_energy = np.cumsum((singular_values[::-1] ** 2))[::-1]
            total = max(float(tail_energy[0]), np.finfo(float).eps)
            rank = available
            for candidate in range(1, available + 1):
                discarded = float(tail_energy[candidate]) if candidate < available else 0.0
                if discarded <= (self.tolerance ** 2) * total:
                    rank = candidate
                    break
        if self.max_rank is not None:
            rank = min(rank, self.max_rank)
        return max(1, min(rank, available))

    def _decompose(self, tensor: np.ndarray) -> None:
        current = tensor
        rank_left = 1
        for site, physical_dim in enumerate(self.original_shape[:-1]):
            matrix = current.reshape(rank_left * physical_dim, -1)
            u, singular_values, vh = np.linalg.svd(matrix, full_matrices=False)
            rank = self._choose_rank(singular_values)
            self.cores.append(u[:, :rank].reshape(rank_left, physical_dim, rank))
            self.ranks.append(rank)
            current = singular_values[:rank, None] * vh[:rank, :]
            rank_left = rank
        self.cores.append(current.reshape(rank_left, self.original_shape[-1], 1))
        self.ranks.append(1)

    def reconstruct(self) -> np.ndarray:
        result = self.cores[0]
        for core in self.cores[1:]:
            result = np.tensordot(result, core, axes=([-1], [0]))
        return np.asarray(result).reshape(self.original_shape)

    def reconstruction_error(self, tensor: Optional[np.ndarray] = None) -> float:
        target = np.asarray(tensor) if tensor is not None else self.reconstruct()
        if tensor is None:
            return 0.0
        denom = max(1.0, float(np.linalg.norm(target)))
        return float(np.linalg.norm(np.asarray(tensor) - self.reconstruct()) / denom)

    def get_compression_ratio(self) -> float:
        compressed = sum(core.size for core in self.cores)
        return self.original_size / max(1, compressed)

    def get_memory_bytes(self) -> Dict[str, float]:
        original_bytes = int(self.original_size * np.asarray(self.cores[0]).dtype.itemsize)
        compressed_bytes = int(sum(core.nbytes for core in self.cores))
        return {
            "original": original_bytes,
            "compressed": compressed_bytes,
            "saved": original_bytes - compressed_bytes,
            "ratio": original_bytes / max(1, compressed_bytes),
        }


class TTPulviniHybrid:
    """Fold, TT-compress, then exactly unfold using the retained complement."""

    def __init__(self, max_tt_rank: Optional[int] = None, tolerance: float = 1e-5):
        self.max_tt_rank = max_tt_rank
        self.tolerance = tolerance
        self.pulvini_kernel: Optional[np.ndarray] = None
        self.original_shape: Optional[Tuple[int, ...]] = None

    def phi_guided_rank(self, dim: int) -> int:
        # Deterministic policy; this is a budget, not a speedup claim.
        phi = (1.0 + np.sqrt(5.0)) / 2.0
        return max(1, int(np.ceil(dim / phi)))

    def process(self, tensor: np.ndarray) -> Dict[str, Any]:
        value = np.asarray(tensor)
        if value.ndim < 1:
            raise ValueError("tensor must have at least one dimension")
        flat = value.reshape(-1)
        pulvini = PulviniOperator(tolerance=self.tolerance)
        folded, kernel = pulvini.fold(flat)
        self.pulvini_kernel = kernel.copy()
        self.original_shape = tuple(value.shape)

        rank = self.max_tt_rank or self.phi_guided_rank(folded.size)
        tt = TensorTrain(folded.reshape(-1, 1), max_rank=rank, tolerance=self.tolerance)
        folded_restored = tt.reconstruct().reshape(-1)
        restored = pulvini.unfold(folded_restored, kernel, flat.size)
        error = float(np.linalg.norm(flat - restored) / max(1.0, np.linalg.norm(flat)))
        memory = tt.get_memory_bytes()
        return {
            "folded": folded,
            "tt_cores": tt.cores,
            "reconstructed": restored.reshape(value.shape),
            "pulvini_kernel": kernel,
            "pulvini_ratio": float(flat.size / max(1, folded.size)),
            "tt_compression_ratio": float(tt.get_compression_ratio()),
            "total_compression_ratio": float(flat.size / max(1, memory["compressed"] / max(1, value.dtype.itemsize))),
            "reconstruction_error": error,
            "tt_ranks": tt.ranks,
            "memory_info": memory,
            "topology_preserved": bool(error <= self.tolerance),
        }
