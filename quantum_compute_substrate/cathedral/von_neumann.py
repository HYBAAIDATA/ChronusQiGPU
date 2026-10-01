"""John von Neumann (1903-1957).

Density matrix rho = |psi><psi| for pure states, sum_i p_i |psi_i><psi_i| for
mixed. Von Neumann entropy:

    S(rho) = - Tr(rho log2 rho)

And projective measurement.
"""

from __future__ import annotations
import numpy as np
from typing import Sequence, Tuple


def density_matrix(psi: np.ndarray) -> np.ndarray:
    v = psi.reshape(-1, 1)
    return v @ v.conj().T


def mixed_state(probabilities: Sequence[float], states: Sequence[np.ndarray]) -> np.ndarray:
    if abs(sum(probabilities) - 1.0) > 1e-9:
        raise ValueError("probabilities must sum to 1")
    dim = states[0].shape[0]
    rho = np.zeros((dim, dim), dtype=complex)
    for p, s in zip(probabilities, states):
        rho = rho + p * density_matrix(s)
    return rho


def von_neumann_entropy(rho: np.ndarray) -> float:
    w = np.linalg.eigvalsh(rho)
    w = w[w > 1e-15]
    return float(-np.sum(w * np.log2(w)))


def partial_trace(rho: np.ndarray, keep: int, dims: Tuple[int, int]) -> np.ndarray:
    """Trace out the OTHER subsystem, keeping subsystem `keep` (0 or 1).

    dims = (dA, dB) with rho of shape (dA*dB, dA*dB).
    """
    dA, dB = dims
    rho_r = rho.reshape(dA, dB, dA, dB)
    if keep == 0:
        return np.einsum("ijkj->ik", rho_r)
    if keep == 1:
        return np.einsum("ijil->jl", rho_r)
    raise ValueError("keep must be 0 or 1")


def projective_measurement(rho: np.ndarray, projector: np.ndarray) -> Tuple[float, np.ndarray]:
    """Return (prob, post_state) for measurement outcome given by projector P."""
    prob = float(np.real(np.trace(projector @ rho)))
    if prob < 1e-15:
        return 0.0, np.zeros_like(rho)
    post = projector @ rho @ projector / prob
    return prob, post


def purity(rho: np.ndarray) -> float:
    return float(np.real(np.trace(rho @ rho)))
