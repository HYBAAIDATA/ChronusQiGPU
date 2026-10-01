"""Claude Shannon (1916-2001).

Information entropy H(X) = - sum_x p(x) log2 p(x), mutual information I(X;Y),
and the quantum analogue: Holevo bound on classical information extractable
from quantum states.

    chi = S(sum p_i rho_i) - sum p_i S(rho_i) >= I(X;Y_accessible)
"""
from __future__ import annotations
import numpy as np
from typing import Sequence
from .von_neumann import von_neumann_entropy, density_matrix


def shannon_entropy(p: Sequence[float]) -> float:
    p = np.asarray(p, dtype=float)
    p = p[p > 1e-15]
    return float(-np.sum(p * np.log2(p)))


def mutual_information(joint: np.ndarray) -> float:
    """I(X;Y) from a joint distribution p(x,y)."""
    joint = np.asarray(joint, dtype=float)
    px = joint.sum(axis=1)
    py = joint.sum(axis=0)
    Hx = shannon_entropy(px)
    Hy = shannon_entropy(py)
    Hxy = shannon_entropy(joint.reshape(-1))
    return Hx + Hy - Hxy


def holevo_bound(probs: Sequence[float], states: Sequence[np.ndarray]) -> float:
    """chi = S(rho_avg) - sum p_i S(rho_i) where rho_i = |psi_i><psi_i|."""
    probs = np.asarray(probs, dtype=float)
    if abs(probs.sum() - 1.0) > 1e-9:
        raise ValueError("probs must sum to 1")
    dim = states[0].shape[0]
    rho_avg = np.zeros((dim, dim), dtype=complex)
    entropy_sum = 0.0
    for p, s in zip(probs, states):
        rho_i = density_matrix(s)
        rho_avg = rho_avg + p * rho_i
        entropy_sum += p * von_neumann_entropy(rho_i)
    return von_neumann_entropy(rho_avg) - entropy_sum


def channel_capacity_binary_symmetric(p_flip: float) -> float:
    """C = 1 - H(p) for a binary symmetric channel."""
    if p_flip <= 0 or p_flip >= 1:
        return 1.0 if p_flip == 0 else 0.0
    return 1.0 - shannon_entropy([p_flip, 1 - p_flip])
