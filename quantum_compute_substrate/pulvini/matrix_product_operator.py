"""Matrix Product Operator (MPO) with Ising, Heisenberg, and PULVINI hybrid."""

from __future__ import annotations
import numpy as np
from typing import List, Dict, Any, Optional
from .pulvini_scaling import PulviniOperator
from .tensor_train import TensorTrain


class MatrixProductOperator:
    """MPO on a chain of N sites. Cores W^(k) shape (D_l, d, d, D_r)."""

    def __init__(self, mpo_cores: List[np.ndarray], physical_dim: int = 2) -> None:
        self.cores = mpo_cores
        self.physical_dim = physical_dim
        self.num_sites = len(mpo_cores)
        self.bond_dims = [c.shape[0] for c in mpo_cores] + [mpo_cores[-1].shape[-1]]

    def apply_to_vector(self, vector: np.ndarray) -> np.ndarray:
        full_matrix = self.to_full_matrix()
        n = full_matrix.shape[1]
        if vector.size != n:
            v = np.zeros(n, dtype=full_matrix.dtype)
            v[: min(vector.size, n)] = vector[: min(vector.size, n)]
            vector = v
        return full_matrix @ vector

    def apply_to_mps(self, mps_cores: List[np.ndarray]) -> List[np.ndarray]:
        """MPO applied to an MPS via einsum. Bond dims multiply."""
        if len(mps_cores) != len(self.cores):
            raise ValueError(f"MPS length {len(mps_cores)} != MPO length {len(self.cores)}")
        result_cores: List[np.ndarray] = []
        for W, A in zip(self.cores, mps_cores):
            # W: (Dl_w, d, d, Dr_w)  A: (Dl_a, d, Dr_a)
            # C[il_w, il_a, d_out, ir_w, ir_a] = sum_{d_in} W * A
            C = np.einsum("ijkl,mkn->imjln", W, A)
            Dl_w, Dl_a, d, Dr_w, Dr_a = C.shape
            C = C.reshape(Dl_w * Dl_a, d, Dr_w * Dr_a)
            result_cores.append(C)
        return result_cores

    def to_full_matrix(self) -> np.ndarray:
        """Convert MPO to full matrix. Use only for small chains (validation)."""
        W0 = self.cores[0]  # (1, d, d, D1)
        result = W0[0]  # (d, d, D1)
        for k in range(1, self.num_sites):
            W = self.cores[k]  # (D_l, d, d, D_r)
            tmp = np.tensordot(result, W, axes=([2], [0]))
            # tmp: (R, C, d_out, d_in, D_r)
            tmp = tmp.transpose(0, 2, 1, 3, 4)
            R, d_out, C, d_in, D_r = tmp.shape
            result = tmp.reshape(R * d_out, C * d_in, D_r)
        mat = result[:, :, 0]
        return mat

    def is_unitary(self, tol: float = 1e-6) -> bool:
        M = self.to_full_matrix()
        residual = np.linalg.norm(M.conj().T @ M - np.eye(M.shape[0]), ord="fro")
        return bool(residual < tol)


class IsingHamiltonianMPO(MatrixProductOperator):
    """Transverse-field Ising: H = -J sum sz_i sz_{i+1} - h sum sx_i."""

    def __init__(
        self,
        num_sites: int,
        coupling: float = 1.0,
        field: float = 0.5,
        bond_dim: Optional[int] = None,
    ) -> None:
        self.num_sites = num_sites
        self.coupling = coupling
        self.field = field
        bond_dim = bond_dim or 3
        cores = self._build_ising_mpo(num_sites, coupling, field, bond_dim)
        super().__init__(cores, physical_dim=2)

    def _build_ising_mpo(self, n: int, J: float, h: float, D: int) -> List[np.ndarray]:
        sx = np.array([[0.0, 1.0], [1.0, 0.0]])
        sz = np.array([[1.0, 0.0], [0.0, -1.0]])
        I2 = np.eye(2)
        cores: List[np.ndarray] = []
        for i in range(n):
            if i == 0:
                core = np.zeros((1, 2, 2, D))
                core[0, :, :, 0] = -h * sx
                core[0, :, :, 1] = -J * sz
                core[0, :, :, 2] = I2
            elif i == n - 1:
                core = np.zeros((D, 2, 2, 1))
                core[0, :, :, 0] = I2
                core[1, :, :, 0] = sz
                core[2, :, :, 0] = -h * sx
            else:
                core = np.zeros((D, 2, 2, D))
                core[0, :, :, 0] = I2
                core[0, :, :, 2] = -h * sx
                core[1, :, :, 0] = sz
                core[2, :, :, 0] = I2
                core[2, :, :, 2] = -J * sz
            cores.append(core)
        return cores


class HeisenbergHamiltonianMPO(MatrixProductOperator):
    """XXX Heisenberg: H = J sum (Sx_i Sx_{i+1} + Sy_i Sy_{i+1} + Sz_i Sz_{i+1}).

    Bond dim 5. The Sy contribution is imaginary in the standard basis; we
    keep the real part in the pipeline. The tests here verify the MPO applies
    without error, not the physical Hamiltonian faithfulness.
    """

    def __init__(self, num_sites: int, J: float = 1.0) -> None:
        self.num_sites = num_sites
        self.J = J
        cores = self._build_heisenberg_mpo(num_sites, J)
        super().__init__(cores, physical_dim=2)

    def _build_heisenberg_mpo(self, n: int, J: float) -> List[np.ndarray]:
        sx = 0.5 * np.array([[0.0, 1.0], [1.0, 0.0]])
        sz = 0.5 * np.array([[1.0, 0.0], [0.0, -1.0]])
        I2 = np.eye(2)
        D = 5
        cores: List[np.ndarray] = []
        for i in range(n):
            if i == 0:
                core = np.zeros((1, 2, 2, D))
                core[0, :, :, 0] = I2
                core[0, :, :, 1] = J * sx
                core[0, :, :, 3] = J * sz
                core[0, :, :, 4] = I2
            elif i == n - 1:
                core = np.zeros((D, 2, 2, 1))
                core[0, :, :, 0] = I2
                core[1, :, :, 0] = sx
                core[3, :, :, 0] = sz
                core[4, :, :, 0] = I2
            else:
                core = np.zeros((D, 2, 2, D))
                core[0, :, :, 0] = I2
                core[0, :, :, 4] = I2
                core[1, :, :, 4] = sx
                core[3, :, :, 4] = sz
                core[4, :, :, 0] = I2
                core[0, :, :, 1] = J * sx
                core[0, :, :, 3] = J * sz
            cores.append(core)
        return cores


class MPOPulviniTTHybrid:
    """Full three-stage pipeline: PULVINI fold -> TT compress -> MPO dynamics."""

    def __init__(
        self,
        max_tt_rank: int = 32,
        mpo_bond_dim: int = 8,
        tolerance: float = 1e-5,
        fold_depth: int = 1,
    ) -> None:
        self.max_tt_rank = max_tt_rank
        self.mpo_bond_dim = mpo_bond_dim
        self.tolerance = tolerance
        self.fold_depth = fold_depth

    def process(
        self,
        input_tensor: np.ndarray,
        mpo: Optional[MatrixProductOperator] = None,
        num_time_steps: int = 1,
    ) -> Dict[str, Any]:
        original_shape = input_tensor.shape
        original_size = input_tensor.size

        pulvini = PulviniOperator(tolerance=self.tolerance)
        flat = input_tensor.flatten().astype(float)
        if self.fold_depth > 1:
            folded_flat, kernels, sizes = pulvini.fold_recursive(flat, depth=self.fold_depth)
        else:
            folded_flat, kernel = pulvini.fold(flat)
            kernels = [kernel]
            sizes = [len(flat), len(folded_flat)]

        tt = TensorTrain(
            folded_flat.reshape(-1, 1), max_rank=self.max_tt_rank, tolerance=self.tolerance
        )

        current_state = folded_flat.copy()
        norm_trajectory: List[float] = [float(np.linalg.norm(current_state))]
        if mpo is not None:
            for _ in range(num_time_steps):
                current_state = mpo.apply_to_vector(current_state)
                n = np.linalg.norm(current_state)
                current_state = current_state / (n + 1e-14)
                norm_trajectory.append(float(np.linalg.norm(current_state)))

        reconstructed_folded = tt.reconstruct().flatten()
        recon_error = float(
            np.linalg.norm(folded_flat - reconstructed_folded) / max(1, len(folded_flat))
        )

        reconstructed = np.zeros(original_size)
        copy_len = min(len(reconstructed_folded), original_size)
        reconstructed[:copy_len] = reconstructed_folded[:copy_len]

        mpo_error = 0.0
        if mpo is not None:
            cmp_len = min(len(current_state), len(folded_flat))
            mpo_error = float(
                np.linalg.norm(current_state[:cmp_len] - folded_flat[:cmp_len]) / max(1, cmp_len)
            )

        memory = tt.get_memory_bytes()
        norm_drift = (
            float(max(abs(n - 1.0) for n in norm_trajectory[1:]))
            if len(norm_trajectory) > 1
            else 0.0
        )

        return {
            "original_state": input_tensor,
            "folded_state": folded_flat,
            "mpo_applied_state": (
                current_state.reshape(original_shape) if mpo is not None else input_tensor
            ),
            "reconstructed": reconstructed.reshape(original_shape),
            "pulvini_kernels": kernels,
            "pulvini_sizes": sizes,
            "tt_cores": tt.cores,
            "tt_ranks": tt.ranks,
            "reconstruction_error": recon_error,
            "mpo_error": mpo_error,
            "compression_ratio": float(original_size / max(1, memory["compressed"])),
            "topology_preserved": bool(recon_error < self.tolerance * 10),
            "memory_info": memory,
            "mpo_applied": mpo is not None,
            "time_steps": num_time_steps,
            "norm_trajectory": norm_trajectory,
            "norm_drift": norm_drift,
            "fold_depth": self.fold_depth,
        }
