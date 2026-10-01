"""Kellogg tensor-network algebra.

This module is the canonical home for the July 2026 MPS, TT and MPO
capabilities.  Decompositions retain the input dtype (including complex
amplitudes), validate every shape/bond contract and report measured storage
and reconstruction error.  Truncation is explicitly lossy; no ratio returned
here is a physical-memory or hardware-throughput claim.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import numpy as np

PHI = (1.0 + math.sqrt(5.0)) / 2.0


class TensorNetworkError(ValueError):
    """A tensor-network shape, rank or numerical contract was violated."""


def _array(value: Any, *, min_ndim: int = 1) -> np.ndarray:
    arr = np.asarray(value)
    if arr.ndim < min_ndim or arr.size == 0:
        raise TensorNetworkError(f"expected a non-empty tensor with rank >= {min_ndim}")
    if arr.dtype.kind not in "biufc":
        raise TensorNetworkError("tensor values must be numeric")
    if not np.all(np.isfinite(arr)):
        raise TensorNetworkError("tensor values must be finite")
    return arr.astype(np.complex128 if np.iscomplexobj(arr) else np.float64, copy=False)


def _positive_int(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)) or int(value) < 1:
        raise TensorNetworkError(f"{name} must be a positive integer")
    return int(value)


def phi_guided_rank(dim: int) -> int:
    """Return a bounded phi-proportional candidate rank for ``dim``."""
    dim = _positive_int(dim, "dim")
    return min(dim, max(1, int(math.ceil(dim / PHI))))


@dataclass(frozen=True)
class TensorNetworkAudit:
    original_shape: tuple[int, ...]
    ranks: tuple[int, ...]
    original_values: int
    retained_values: int
    original_bytes: int
    retained_bytes: int
    reconstruction_error: float
    exact_roundtrip: bool
    claim_boundary: str = "representation accounting; not physical compression or throughput"

    @property
    def value_ratio(self) -> float:
        return self.original_values / max(1, self.retained_values)

    @property
    def byte_ratio(self) -> float:
        return self.original_bytes / max(1, self.retained_bytes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_shape": list(self.original_shape),
            "ranks": list(self.ranks),
            "original_values": self.original_values,
            "retained_values": self.retained_values,
            "original_bytes": self.original_bytes,
            "retained_bytes": self.retained_bytes,
            "value_ratio": self.value_ratio,
            "byte_ratio": self.byte_ratio,
            "reconstruction_error": self.reconstruction_error,
            "exact_roundtrip": self.exact_roundtrip,
            "claim_boundary": self.claim_boundary,
        }


class TensorTrain:
    """Tensor-train decomposition produced by stable sequential SVD."""

    def __init__(
        self,
        tensor: np.ndarray,
        max_rank: int | None = None,
        tolerance: float = 0.0,
    ) -> None:
        arr = _array(tensor)
        if tolerance < 0 or not math.isfinite(float(tolerance)):
            raise TensorNetworkError("tolerance must be finite and non-negative")
        if max_rank is None:
            max_rank = phi_guided_rank(max(arr.shape))
        self.max_rank = _positive_int(max_rank, "max_rank")
        self.tolerance = float(tolerance)
        self.original_shape = tuple(int(v) for v in arr.shape)
        self.original_size = int(arr.size)
        self.original_dtype = arr.dtype.str
        self.cores: list[np.ndarray] = []
        self.ranks: list[int] = [1]
        self._decompose(arr)

    def _rank(self, singular_values: np.ndarray) -> int:
        if singular_values.size == 0:
            return 1
        if self.tolerance == 0.0 or singular_values[0] == 0:
            numerical_rank = singular_values.size if singular_values[0] != 0 else 1
        else:
            threshold = self.tolerance * singular_values[0]
            numerical_rank = int(np.count_nonzero(singular_values > threshold))
        return max(1, min(numerical_rank, self.max_rank, singular_values.size))

    def _decompose(self, tensor: np.ndarray) -> None:
        if tensor.ndim == 1:
            self.cores = [tensor.reshape(1, tensor.shape[0], 1).copy()]
            self.ranks.append(1)
            return
        carry = tensor
        r_left = 1
        for mode, n_mode in enumerate(self.original_shape[:-1]):
            carry = carry.reshape(r_left * n_mode, -1)
            u, singular, vh = np.linalg.svd(carry, full_matrices=False)
            rank = self._rank(singular)
            self.cores.append(u[:, :rank].reshape(r_left, n_mode, rank))
            self.ranks.append(rank)
            carry = singular[:rank, None] * vh[:rank, :]
            r_left = rank
        self.cores.append(carry.reshape(r_left, self.original_shape[-1], 1))
        self.ranks.append(1)

    @classmethod
    def from_cores(
        cls,
        cores: Sequence[np.ndarray],
        *,
        original_shape: Sequence[int] | None = None,
        tolerance: float = 0.0,
    ) -> "TensorTrain":
        validated = _validate_tt_cores(cores)
        shape = tuple(c.shape[1] for c in validated)
        if original_shape is not None and tuple(original_shape) != shape:
            raise TensorNetworkError("declared shape does not match TT physical dimensions")
        obj = cls.__new__(cls)
        obj.max_rank = max(c.shape[-1] for c in validated)
        obj.tolerance = float(tolerance)
        obj.original_shape = shape
        obj.original_size = math.prod(shape)
        obj.original_dtype = np.result_type(*(c.dtype for c in validated)).str
        obj.cores = [c.copy() for c in validated]
        obj.ranks = [validated[0].shape[0], *(c.shape[-1] for c in validated)]
        return obj

    def reconstruct(self) -> np.ndarray:
        result = self.cores[0]
        for core in self.cores[1:]:
            result = np.tensordot(result, core, axes=([-1], [0]))
        return np.squeeze(result, axis=(0, -1)).reshape(self.original_shape)

    def relative_error(self, original: np.ndarray) -> float:
        expected = _array(original)
        if expected.shape != self.original_shape:
            raise TensorNetworkError("reference shape does not match tensor train")
        denominator = float(np.linalg.norm(expected.ravel()))
        numerator = float(np.linalg.norm((expected - self.reconstruct()).ravel()))
        return numerator / denominator if denominator else numerator

    def audit(self, original: np.ndarray | None = None) -> TensorNetworkAudit:
        retained = sum(int(core.size) for core in self.cores)
        retained_bytes = sum(int(core.nbytes) for core in self.cores)
        error = 0.0 if original is None else self.relative_error(original)
        itemsize = np.dtype(self.original_dtype).itemsize
        return TensorNetworkAudit(
            original_shape=self.original_shape,
            ranks=tuple(self.ranks),
            original_values=self.original_size,
            retained_values=retained,
            original_bytes=self.original_size * itemsize,
            retained_bytes=retained_bytes,
            reconstruction_error=error,
            exact_roundtrip=error == 0.0,
        )

    def get_reconstruction_error(self, original: np.ndarray) -> float:
        return self.relative_error(original)

    def get_compression_ratio(self) -> float:
        return self.original_size / max(1, sum(int(c.size) for c in self.cores))

    def get_memory_bytes(self) -> dict[str, Any]:
        audit = self.audit()
        return {
            "original": audit.original_bytes,
            "compressed": audit.retained_bytes,
            "saved": audit.original_bytes - audit.retained_bytes,
            "ratio": audit.byte_ratio,
            "claim_boundary": audit.claim_boundary,
        }


def _validate_tt_cores(cores: Sequence[np.ndarray]) -> list[np.ndarray]:
    if not cores:
        raise TensorNetworkError("at least one TT core is required")
    validated = [_array(core, min_ndim=3) for core in cores]
    if any(core.ndim != 3 for core in validated):
        raise TensorNetworkError("every TT core must have shape (left, physical, right)")
    if validated[0].shape[0] != 1 or validated[-1].shape[-1] != 1:
        raise TensorNetworkError("TT boundary bond dimensions must be one")
    for left, right in zip(validated, validated[1:]):
        if left.shape[-1] != right.shape[0]:
            raise TensorNetworkError("adjacent TT bond dimensions do not match")
    return validated


def tt_decompose(tensor: np.ndarray, max_rank: int, tolerance: float = 0.0) -> list[Any]:
    """Compatibility representation: ``[shape, core_0, ..., core_n]``."""
    train = TensorTrain(tensor, max_rank=max_rank, tolerance=tolerance)
    return [train.original_shape, *(core.copy() for core in train.cores)]


def tt_reconstruct(cores: Sequence[Any]) -> np.ndarray:
    if len(cores) < 2 or not isinstance(cores[0], tuple):
        raise TensorNetworkError("TT payload must start with its original shape tuple")
    return TensorTrain.from_cores(cores[1:], original_shape=cores[0]).reconstruct()


def tt_compress_with_budget(
    tensor: np.ndarray,
    max_rel_error: float,
    max_rank: int,
    *,
    tolerance: float = 0.0,
) -> tuple[list[Any], float]:
    if max_rel_error < 0 or not math.isfinite(float(max_rel_error)):
        raise TensorNetworkError("max_rel_error must be finite and non-negative")
    payload = tt_decompose(tensor, max_rank=max_rank, tolerance=tolerance)
    expected = _array(tensor)
    reconstructed = tt_reconstruct(payload)
    denominator = float(np.linalg.norm(expected.ravel()))
    error = float(np.linalg.norm((expected - reconstructed).ravel()))
    error = error / denominator if denominator else error
    if error > max_rel_error:
        raise TensorNetworkError(
            f"TT codec exceeds error budget: {error:.6g} > {max_rel_error:.6g}"
        )
    return payload, error


def mps_decompose(state: np.ndarray, n_sites: int, chi: int) -> list[np.ndarray]:
    n_sites = _positive_int(n_sites, "n_sites")
    chi = _positive_int(chi, "chi")
    vector = _array(state).reshape(-1)
    expected = 1 << n_sites
    if vector.size != expected:
        raise TensorNetworkError(f"state has {vector.size} amplitudes; expected 2**{n_sites}")
    return TensorTrain(vector.reshape((2,) * n_sites), max_rank=chi).cores


def mps_reconstruct(mps: Sequence[np.ndarray]) -> np.ndarray:
    cores = _validate_tt_cores(mps)
    if any(core.shape[1] != 2 for core in cores):
        raise TensorNetworkError("MPS physical dimensions must all equal two")
    return TensorTrain.from_cores(cores).reconstruct().reshape(-1)


class MatrixProductOperator:
    """Matrix-product operator with validated four-dimensional cores."""

    def __init__(self, mpo_cores: Sequence[np.ndarray], physical_dim: int = 2) -> None:
        self.physical_dim = _positive_int(physical_dim, "physical_dim")
        if not mpo_cores:
            raise TensorNetworkError("at least one MPO core is required")
        self.cores = [_array(core, min_ndim=4) for core in mpo_cores]
        if any(core.ndim != 4 for core in self.cores):
            raise TensorNetworkError("MPO cores must have shape (left, out, in, right)")
        if self.cores[0].shape[0] != 1 or self.cores[-1].shape[-1] != 1:
            raise TensorNetworkError("MPO boundary bond dimensions must be one")
        for core in self.cores:
            if core.shape[1:3] != (self.physical_dim, self.physical_dim):
                raise TensorNetworkError("MPO physical dimensions do not match")
        for left, right in zip(self.cores, self.cores[1:]):
            if left.shape[-1] != right.shape[0]:
                raise TensorNetworkError("adjacent MPO bond dimensions do not match")
        self.num_sites = len(self.cores)
        self.bond_dims = [self.cores[0].shape[0], *(core.shape[-1] for core in self.cores)]

    def to_full_matrix(self, *, max_elements: int = 16_777_216) -> np.ndarray:
        dimension = self.physical_dim**self.num_sites
        if dimension * dimension > max_elements:
            raise TensorNetworkError("full MPO expansion exceeds the declared element limit")
        result = self.cores[0][0]
        for core in self.cores[1:]:
            tmp = np.tensordot(result, core, axes=([-1], [0]))
            row, col, out_dim, in_dim, right = tmp.shape
            result = tmp.transpose(0, 2, 1, 3, 4).reshape(
                row * out_dim, col * in_dim, right
            )
        return result[:, :, 0]

    def apply_to_vector(self, vector: np.ndarray) -> np.ndarray:
        arr = _array(vector).reshape(-1)
        matrix = self.to_full_matrix()
        if arr.size != matrix.shape[1]:
            raise TensorNetworkError(
                f"vector length {arr.size} does not match MPO dimension {matrix.shape[1]}"
            )
        return matrix @ arr

    def apply_to_mps(self, mps_cores: Sequence[np.ndarray]) -> list[np.ndarray]:
        mps = _validate_tt_cores(mps_cores)
        if len(mps) != self.num_sites:
            raise TensorNetworkError("MPS and MPO must have the same number of sites")
        result: list[np.ndarray] = []
        for operator, state in zip(self.cores, mps):
            if state.shape[1] != self.physical_dim:
                raise TensorNetworkError("MPS physical dimension does not match MPO")
            contracted = np.einsum("aijb,cjd->acibd", operator, state, optimize=True)
            left_o, left_s, physical, right_o, right_s = contracted.shape
            result.append(
                contracted.reshape(left_o * left_s, physical, right_o * right_s)
            )
        return result

    def is_unitary(self, tolerance: float = 1e-8) -> bool:
        if tolerance <= 0:
            raise TensorNetworkError("tolerance must be positive")
        matrix = self.to_full_matrix()
        identity = np.eye(matrix.shape[0], dtype=matrix.dtype)
        return bool(np.linalg.norm(matrix.conj().T @ matrix - identity, ord="fro") <= tolerance)


class IsingHamiltonianMPO(MatrixProductOperator):
    """Open-boundary transverse-field Ising Hamiltonian MPO."""

    def __init__(self, num_sites: int, coupling: float = 1.0, field: float = 0.5):
        n = _positive_int(num_sites, "num_sites")
        if n == 1:
            sx = np.array([[0.0, 1.0], [1.0, 0.0]])
            cores = [(-field * sx).reshape(1, 2, 2, 1)]
        else:
            identity = np.eye(2)
            sx = np.array([[0.0, 1.0], [1.0, 0.0]])
            sz = np.diag([1.0, -1.0])
            first = np.zeros((1, 2, 2, 3))
            first[0, :, :, 0] = -field * sx
            first[0, :, :, 1] = -coupling * sz
            first[0, :, :, 2] = identity
            middle = []
            for _ in range(n - 2):
                core = np.zeros((3, 2, 2, 3))
                core[0, :, :, 0] = identity
                core[1, :, :, 0] = sz
                core[2, :, :, 0] = -field * sx
                core[2, :, :, 1] = -coupling * sz
                core[2, :, :, 2] = identity
                middle.append(core)
            last = np.zeros((3, 2, 2, 1))
            last[0, :, :, 0] = identity
            last[1, :, :, 0] = sz
            last[2, :, :, 0] = -field * sx
            cores = [first, *middle, last]
        self.coupling = float(coupling)
        self.field = float(field)
        super().__init__(cores)


class HeisenbergHamiltonianMPO(MatrixProductOperator):
    """Open-boundary spin-1/2 XXX Heisenberg Hamiltonian MPO."""

    def __init__(self, num_sites: int, coupling: float = 1.0):
        n = _positive_int(num_sites, "num_sites")
        sx = 0.5 * np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)
        sy = 0.5 * np.array([[0.0, -1j], [1j, 0.0]], dtype=complex)
        sz = 0.5 * np.diag([1.0, -1.0]).astype(complex)
        identity = np.eye(2, dtype=complex)
        if n == 1:
            cores = [np.zeros((1, 2, 2, 1), dtype=complex)]
        else:
            first = np.zeros((1, 2, 2, 5), dtype=complex)
            first[0, :, :, 0] = identity
            first[0, :, :, 1] = coupling * sx
            first[0, :, :, 2] = coupling * sy
            first[0, :, :, 3] = coupling * sz
            middle = []
            for _ in range(n - 2):
                core = np.zeros((5, 2, 2, 5), dtype=complex)
                core[0, :, :, 0] = identity
                core[0, :, :, 1] = coupling * sx
                core[0, :, :, 2] = coupling * sy
                core[0, :, :, 3] = coupling * sz
                core[1, :, :, 4] = sx
                core[2, :, :, 4] = sy
                core[3, :, :, 4] = sz
                core[4, :, :, 4] = identity
                middle.append(core)
            last = np.zeros((5, 2, 2, 1), dtype=complex)
            last[0, :, :, 0] = identity
            last[1, :, :, 0] = sx
            last[2, :, :, 0] = sy
            last[3, :, :, 0] = sz
            cores = [first, *middle, last]
        self.coupling = float(coupling)
        super().__init__(cores)


def hamiltonian_with_tensor_network(
    hamiltonian: np.ndarray,
    psi: np.ndarray,
    *,
    n_sites: int,
    bond_dim: int,
    time: float = 1.0,
) -> tuple[np.ndarray, list[np.ndarray]]:
    """Evolve a state by ``exp(-i H time)`` then return its bounded MPS."""
    vector = _array(psi).reshape(-1)
    matrix = _array(hamiltonian, min_ndim=2)
    if matrix.ndim != 2 or matrix.shape != (vector.size, vector.size):
        raise TensorNetworkError("Hamiltonian must be square and match the state dimension")
    if not np.allclose(matrix, matrix.conj().T, atol=1e-10):
        raise TensorNetworkError("Hamiltonian must be Hermitian")
    eigenvalues, eigenvectors = np.linalg.eigh(matrix)
    unitary = (eigenvectors * np.exp(-1j * eigenvalues * float(time))) @ eigenvectors.conj().T
    evolved = unitary @ vector
    return evolved, mps_decompose(evolved, n_sites=n_sites, chi=bond_dim)


def topology_signature(adjacency: np.ndarray) -> tuple[int, int]:
    matrix = _array(adjacency, min_ndim=2)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise TensorNetworkError("adjacency matrix must be square")
    if not np.allclose(matrix, matrix.T.conj()):
        raise TensorNetworkError("adjacency matrix must be symmetric")
    present = np.asarray(np.abs(matrix) > 0, dtype=bool)
    np.fill_diagonal(present, False)
    visited = np.zeros(present.shape[0], dtype=bool)
    components = 0
    for start in range(present.shape[0]):
        if visited[start]:
            continue
        components += 1
        stack = [start]
        visited[start] = True
        while stack:
            node = stack.pop()
            for neighbor in np.flatnonzero(present[node]):
                if not visited[neighbor]:
                    visited[neighbor] = True
                    stack.append(int(neighbor))
    edges = int(np.count_nonzero(np.triu(present, 1)))
    return components, edges - present.shape[0] + components


def topology_preserved(before: np.ndarray, after: np.ndarray) -> bool:
    return topology_signature(before) == topology_signature(after)


def persistent_homology_comparison(
    data_before: np.ndarray,
    data_after: np.ndarray,
    max_epsilon: float = 2.0,
    n_steps: int = 20,
) -> dict[str, Any]:
    before = _array(data_before).reshape(len(data_before), -1)
    after = _array(data_after).reshape(len(data_after), -1)
    if before.shape[0] != after.shape[0]:
        raise TensorNetworkError("point clouds must contain the same number of observations")
    if max_epsilon <= 0 or n_steps < 1:
        raise TensorNetworkError("max_epsilon and n_steps must be positive")

    def signatures(points: np.ndarray, epsilons: Iterable[float]) -> list[tuple[int, int]]:
        delta = points[:, None, :] - points[None, :, :]
        distances = np.linalg.norm(delta, axis=-1)
        result = []
        for epsilon in epsilons:
            adjacency = (distances <= epsilon).astype(int)
            np.fill_diagonal(adjacency, 0)
            result.append(topology_signature(adjacency))
        return result

    epsilons = np.linspace(max_epsilon / n_steps, max_epsilon, n_steps)
    before_sig = signatures(before, epsilons)
    after_sig = signatures(after, epsilons)
    matches = sum(a == b for a, b in zip(before_sig, after_sig))
    return {
        "epsilons": epsilons.tolist(),
        "betti_before": before_sig,
        "betti_after": after_sig,
        "match_fraction": matches / n_steps,
        "topology_preserved": matches == n_steps,
    }


def quantum_fisher_metric(psi: np.ndarray, dpsi: np.ndarray) -> float:
    state = _array(psi).reshape(-1).astype(complex)
    tangent = _array(dpsi).reshape(-1).astype(complex)
    if state.shape != tangent.shape:
        raise TensorNetworkError("state and tangent must have the same shape")
    norm = np.vdot(state, state).real
    if norm <= 0:
        raise TensorNetworkError("state norm must be positive")
    state = state / math.sqrt(float(norm))
    projection = np.vdot(state, tangent)
    value = 4.0 * (np.vdot(tangent, tangent).real - abs(projection) ** 2)
    return max(0.0, float(value))


def natural_gradient_step(
    psi: np.ndarray, hamiltonian: np.ndarray, eta: float
) -> np.ndarray:
    state = _array(psi).reshape(-1).astype(complex)
    matrix = _array(hamiltonian, min_ndim=2).astype(complex)
    if matrix.shape != (state.size, state.size):
        raise TensorNetworkError("Hamiltonian dimension does not match the state")
    if eta < 0 or not math.isfinite(float(eta)):
        raise TensorNetworkError("eta must be finite and non-negative")
    tangent = -1j * (matrix @ state)
    fisher = quantum_fisher_metric(state, tangent)
    energy = np.vdot(state, matrix @ state).real
    candidate = state - float(eta) * (energy / max(fisher, 1e-12)) * tangent
    norm = float(np.linalg.norm(candidate))
    if norm == 0:
        raise TensorNetworkError("natural-gradient step collapsed the state")
    return candidate / norm


__all__ = [
    "HeisenbergHamiltonianMPO",
    "IsingHamiltonianMPO",
    "MatrixProductOperator",
    "PHI",
    "TensorNetworkAudit",
    "TensorNetworkError",
    "TensorTrain",
    "hamiltonian_with_tensor_network",
    "mps_decompose",
    "mps_reconstruct",
    "natural_gradient_step",
    "persistent_homology_comparison",
    "phi_guided_rank",
    "quantum_fisher_metric",
    "topology_preserved",
    "topology_signature",
    "tt_compress_with_budget",
    "tt_decompose",
    "tt_reconstruct",
]
