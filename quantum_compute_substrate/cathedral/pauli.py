"""Wolfgang Pauli (1900-1958).

Pauli matrices, spin-1/2 algebra, and the exclusion principle.

    {sigma_i, sigma_j} = 2 delta_ij I
    [sigma_i, sigma_j] = 2i epsilon_ijk sigma_k

The entire Pauli group P_1 = {+/- I, +/- iI, +/- X, +/- iX, ...} lives here.
"""

from __future__ import annotations
import numpy as np
from typing import List, Tuple

I = np.eye(2, dtype=complex)
X = np.array([[0, 1], [1, 0]], dtype=complex)
Y = np.array([[0, -1j], [1j, 0]], dtype=complex)
Z = np.array([[1, 0], [0, -1]], dtype=complex)
PAULIS = (I, X, Y, Z)
PAULI_NAMES = ("I", "X", "Y", "Z")


def commutator(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    return A @ B - B @ A


def anticommutator(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    return A @ B + B @ A


def pauli_string(word: str) -> np.ndarray:
    """Tensor product of Pauli operators, e.g. pauli_string("XZI")."""
    lookup = {"I": I, "X": X, "Y": Y, "Z": Z}
    if not word:
        raise ValueError("empty word")
    m = lookup[word[0]]
    for c in word[1:]:
        m = np.kron(m, lookup[c])
    return m


def pauli_group_generators() -> List[Tuple[str, np.ndarray]]:
    """Generators of the 1-qubit Pauli group: X, Y, Z (and phases)."""
    return [("X", X), ("Y", Y), ("Z", Z)]


def exclusion_projector(num_particles: int) -> np.ndarray:
    """Antisymmetrizer for a two-fermion state in a 2^num_particles Hilbert space.

    Returns A = (I - SWAP) / 2 on the 2-particle sector.
    Fermionic states satisfy A |psi> = |psi>.
    """
    if num_particles != 2:
        raise NotImplementedError("only 2-particle exclusion is exposed here")
    swap = np.zeros((4, 4), dtype=complex)
    swap[0, 0] = 1
    swap[3, 3] = 1
    swap[1, 2] = 1
    swap[2, 1] = 1
    return (np.eye(4, dtype=complex) - swap) / 2.0
