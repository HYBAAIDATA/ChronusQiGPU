"""Modern quantum machine learning: data re-uploading and projected kernels."""
from __future__ import annotations
import numpy as np


def _feature_map(x: np.ndarray, layers: int = 2) -> np.ndarray:
    """Data re-uploading feature map (Perez-Salinas et al. 2020).

    Encodes x with alternating rotations. Returns a normalised complex vector.
    """
    x = np.asarray(x, dtype=float)
    n_qubits_needed = max(1, int(np.ceil(np.log2(max(2, len(x) + 1)))))
    dim = 2 ** n_qubits_needed
    v = np.zeros(dim, dtype=complex)
    v[0] = 1.0
    for layer in range(layers):
        phase = np.exp(1j * (layer + 1) * np.linspace(0, 2 * np.pi, dim, endpoint=False))
        amps = np.zeros(dim, dtype=complex)
        for k, xi in enumerate(x):
            amps[k % dim] += np.cos((layer + 1) * xi) + 1j * np.sin((layer + 1) * xi)
        # constant term to keep it non-zero
        amps[0] += 1.0
        v = v * phase + amps
        v = v / np.linalg.norm(v)
    return v


def quantum_kernel_matrix(X: np.ndarray, layers: int = 2) -> np.ndarray:
    """Fidelity kernel: K_ij = |<phi(x_i) | phi(x_j)>|^2. Symmetric PSD, K_ii=1."""
    X = np.asarray(X, dtype=float)
    features = [_feature_map(x, layers=layers) for x in X]
    n = len(features)
    K = np.empty((n, n), dtype=float)
    for i in range(n):
        for j in range(i, n):
            fid = float(np.abs(np.vdot(features[i], features[j])) ** 2)
            K[i, j] = fid
            K[j, i] = fid
    return K


def projected_quantum_kernel(X: np.ndarray, layers: int = 2,
                             gamma: float = 1.0) -> np.ndarray:
    """Projected quantum kernel (Huang et al. 2021).

    K_ij = exp(-gamma * || rho_i^(1) - rho_j^(1) ||_F^2 ) where rho^(1) is the
    single-body reduced density from the encoded state.
    """
    X = np.asarray(X, dtype=float)
    features = [_feature_map(x, layers=layers) for x in X]
    # Reduced density on the first "qubit" (two-block partition).

    def rho1(psi: np.ndarray) -> np.ndarray:
        d = psi.shape[0]
        half = d // 2
        mat = psi.reshape(2, half)
        return mat @ mat.conj().T
    rhos = [rho1(f) for f in features]
    n = len(rhos)
    K = np.empty((n, n), dtype=float)
    for i in range(n):
        for j in range(i, n):
            d = float(np.linalg.norm(rhos[i] - rhos[j], ord="fro"))
            v = float(np.exp(-gamma * d * d))
            K[i, j] = v
            K[j, i] = v
    return K


class ModernQML:
    def __init__(self, num_qubits: int, num_features: int) -> None:
        self.num_qubits = num_qubits
        self.num_features = num_features

    def fit_kernel_ridge(self, X: np.ndarray, y: np.ndarray,
                         reg: float = 1e-4, layers: int = 2) -> np.ndarray:
        K = quantum_kernel_matrix(X, layers=layers)
        A = K + reg * np.eye(K.shape[0])
        return np.linalg.solve(A, y.astype(float))
