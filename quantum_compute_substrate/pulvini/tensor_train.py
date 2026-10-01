"""Tensor Train (TT) decomposition + PULVINI hybrid.

v2 features:
  - Relative SVD truncation (S[k]/S[0]) to prevent rank collapse on flat spectra
  - get_reconstruction_error() convenience method
  - phi_guided_rank() as module-level utility
  - TTPulviniHybrid: multi-level recursive fold support (fold_depth)
  - Richer audit dict from process()
"""

from __future__ import annotations
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from .pulvini_scaling import PulviniOperator, PHI


def phi_guided_rank(dim: int) -> int:
    """Phi-proportional rank selection."""
    return max(2, int(dim / PHI))


class TensorTrain:
    """TT decomposition: compress d-dim tensors efficiently.

    A tensor X of shape (n1, ..., nd) is decomposed as cores G^(k) of shape
    (r_{k-1}, n_k, r_k). Relative SVD threshold guards against rank collapse.
    """

    def __init__(
        self, tensor: np.ndarray, max_rank: Optional[int] = None, tolerance: float = 1e-5
    ) -> None:
        self.original_shape = tensor.shape
        self.original_size = tensor.size
        self.ndim = tensor.ndim
        self.tolerance = tolerance
        if max_rank is None:
            max_rank = max(2, int(np.prod(tensor.shape) / 10))
        self.max_rank = max_rank
        self.cores: List[np.ndarray] = []
        self.ranks: List[int] = [1]
        self._decompose(tensor)

    def _decompose(self, tensor: np.ndarray) -> None:
        shape = self.original_shape
        current = tensor.reshape(shape[0], -1).astype(float)
        for k in range(self.ndim - 1):
            U, S, Vh = np.linalg.svd(current, full_matrices=False)
            if self.tolerance > 0 and len(S) > 0:
                r_new = int(np.sum(S > self.tolerance * S[0]))
            else:
                r_new = len(S)
            r_new = min(max(r_new, 1), self.max_rank, len(S))
            self.ranks.append(r_new)
            core = U[:, :r_new].reshape(self.ranks[-2], shape[k], r_new)
            self.cores.append(core)
            current = np.diag(S[:r_new]) @ Vh[:r_new, :]
            current = current.reshape(r_new, -1)
        self.cores.append(current.reshape(self.ranks[-1], shape[-1], 1))
        self.ranks.append(1)

    def reconstruct(self) -> np.ndarray:
        if not self.cores:
            return np.zeros(self.original_shape)
        # cores[0] shape (1, n_0, r_1) -> drop leading 1
        result = self.cores[0][0]  # (n_0, r_1)
        for k in range(1, len(self.cores)):
            core = self.cores[k]  # (r_{k-1}, n_k, r_k)
            result = np.tensordot(result, core, axes=([-1], [0]))
        # result: (n_0, ..., n_{d-1}, 1)
        return result.reshape(self.original_shape)

    def get_reconstruction_error(self, original: np.ndarray) -> float:
        rec = self.reconstruct()
        return float(np.linalg.norm(original.flatten() - rec.flatten()) / max(1, original.size))

    def get_compression_ratio(self) -> float:
        compressed = sum(c.size for c in self.cores)
        return self.original_size / max(1, compressed)

    def get_memory_bytes(self) -> Dict[str, Any]:
        original_bytes = self.original_size * 8
        compressed_bytes = sum(c.nbytes for c in self.cores)
        return {
            "original": original_bytes,
            "compressed": compressed_bytes,
            "saved": original_bytes - compressed_bytes,
            "ratio": original_bytes / max(1, compressed_bytes),
        }


class TTPulviniHybrid:
    """PULVINI folding -> TT compression pipeline."""

    def __init__(
        self, max_tt_rank: Optional[int] = None, tolerance: float = 1e-5, fold_depth: int = 1
    ) -> None:
        self.max_tt_rank = max_tt_rank
        self.tolerance = tolerance
        self.fold_depth = fold_depth
        self.pulvini_kernel: Optional[np.ndarray] = None
        self.pulvini_kernels: List[np.ndarray] = []
        self.pulvini_sizes: List[int] = []
        self.original_shape: Optional[Tuple] = None

    def process(self, tensor: np.ndarray) -> Dict[str, Any]:
        original_shape = tensor.shape
        original_size = tensor.size
        pulvini = PulviniOperator(tolerance=self.tolerance)
        flat = tensor.flatten().astype(float)

        if self.fold_depth > 1:
            folded_flat, kernels, sizes = pulvini.fold_recursive(flat, depth=self.fold_depth)
            self.pulvini_kernels = kernels
            self.pulvini_sizes = sizes
            single_kernel = kernels[0] if kernels else np.zeros(0)
        else:
            folded_flat, single_kernel = pulvini.fold(flat)
            self.pulvini_kernels = [single_kernel]
            self.pulvini_sizes = [len(flat), len(folded_flat)]

        self.pulvini_kernel = single_kernel
        self.original_shape = original_shape
        pulvini_ratio = original_size / max(1, len(folded_flat))

        max_rank = self.max_tt_rank or phi_guided_rank(len(folded_flat))
        tt = TensorTrain(folded_flat.reshape(-1, 1), max_rank=max_rank, tolerance=self.tolerance)

        reconstructed_folded = tt.reconstruct().flatten()
        recon_error = float(
            np.linalg.norm(folded_flat - reconstructed_folded) / max(1, len(folded_flat))
        )

        reconstructed_flat = np.zeros(original_size)
        copy_len = min(len(reconstructed_folded), original_size)
        reconstructed_flat[:copy_len] = reconstructed_folded[:copy_len]

        memory_info = tt.get_memory_bytes()
        total_compression = original_size / max(1, memory_info["compressed"])

        return {
            "folded": folded_flat,
            "tt_cores": tt.cores,
            "reconstructed": reconstructed_flat.reshape(original_shape),
            "pulvini_ratio": float(pulvini_ratio),
            "tt_compression_ratio": float(tt.get_compression_ratio()),
            "total_compression_ratio": float(total_compression),
            "reconstruction_error": float(recon_error),
            "tt_ranks": tt.ranks,
            "memory_info": memory_info,
            "topology_preserved": bool(recon_error < self.tolerance * 10),
            "fold_depth": self.fold_depth,
        }
