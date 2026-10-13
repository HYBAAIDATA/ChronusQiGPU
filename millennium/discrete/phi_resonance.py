"""Phi-resonance observable for discrete gauge configurations.

This module implements the discrete phi-norm ratio and the R_phi
functional on a finite lattice. It is a computational observable.
It is not a continuum Yang-Mills mass gap and does not claim one.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np

PHI: Final[float] = (1 + math.sqrt(5)) / 2


def icosahedron_vertices() -> np.ndarray:
    """12 vertices of a regular icosahedron, unit-normalised."""
    v = []
    for x in (-1, 1):
        for z in (-PHI, PHI):
            v.append(np.array([0.0, x, z]))
            v.append(np.array([z, 0.0, x]))
            v.append(np.array([x, z, 0.0]))
    arr = np.array(v)
    return arr / np.linalg.norm(arr, axis=1, keepdims=True)


def construct_T_tensor() -> np.ndarray:
    """Discrete approximation of the I_h-invariant tensor T on R^3."""
    vertices = icosahedron_vertices()
    T = np.zeros((3, 3))
    for vec in vertices:
        T += np.outer(vec, vec)
    return T / len(vertices)


def phi_norm_ratio(F_spatial: list[np.ndarray], T: np.ndarray) -> float:
    """sigma(F) = ||F||_phi / ||F||_2 for three spatial field-strength matrices."""
    norm2 = sum(np.real(np.trace(f @ f.conj().T)) for f in F_spatial)
    if norm2 < 1e-12:
        return PHI
    phi_norm = 0.0
    for i in range(3):
        for j in range(3):
            tr = np.real(np.trace(F_spatial[i] @ F_spatial[j].conj().T))
            phi_norm += T[i, j] * tr
    return math.sqrt(max(phi_norm, 0.0) / norm2)


def r_phi(F_list: list[list[np.ndarray]], T: np.ndarray, Lambda: float = 0.1) -> float:
    """Average R_phi weight over a list of local field strengths.

    Discrete observable only. Not a continuum mass gap.
    """
    if not F_list:
        return 0.0
    total = 0.0
    for F_spatial in F_list:
        sigma = phi_norm_ratio(F_spatial, T)
        total += math.exp(-((PHI - sigma) ** 2) / (Lambda ** 2))
    return total / len(F_list)
