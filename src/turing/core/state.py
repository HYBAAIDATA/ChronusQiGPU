"""
Turing Exact Quantum Library — Quantum State Vectors over Z[zeta_p]
"""

from __future__ import annotations
from typing import List
from turing.errors import RingError, DimensionMismatchError
from turing.ring.zeta import ZetaP


class StateZetaP:
    """
    Exact discrete state vector over the cyclotomic integer ring Z[zeta_p].
    Zero floating-point representations; amplitudes are canonical ring elements.
    """
    __slots__ = ('vector', 'dimension', 'p')

    def __init__(self, vector: List[ZetaP], p: int):
        if len(vector) == 0:
            raise DimensionMismatchError("State vector cannot be empty")
        for e in vector:
            if not isinstance(e, ZetaP) or e.p != p:
                raise RingError(f"All amplitudes must belong to ring Z[zeta_{p}]")
        self.vector = list(vector)
        self.dimension = len(vector)
        self.p = p

    @classmethod
    def zero(cls, dimension: int, p: int) -> 'StateZetaP':
        if dimension <= 0:
            raise DimensionMismatchError("Dimension must be positive")
        return cls([ZetaP.zero(p) for _ in range(dimension)], p)

    @classmethod
    def basis(cls, index: int, dimension: int, p: int) -> 'StateZetaP':
        if not (0 <= index < dimension):
            raise DimensionMismatchError(f"Basis index {index} out of range for dimension {dimension}")
        v = [ZetaP.zero(p) for _ in range(dimension)]
        v[index] = ZetaP.one(p)
        return cls(v, p)

    def norm_squared(self) -> ZetaP:
        """Computes <psi|psi> = sum_i |a_i|^2 in Z[zeta_p]."""
        res = ZetaP.zero(self.p)
        for a in self.vector:
            res = res + (a * a.conjugate())
        return res

    def is_unit_norm(self) -> bool:
        """Returns True if the state has unit algebraic norm in the ring."""
        return self.norm_squared().is_unit()

    def __repr__(self) -> str:
        return f"StateZetaP(dim={self.dimension}, p={self.p})"


def superpose(a: StateZetaP, b: StateZetaP, alpha: ZetaP, beta: ZetaP) -> StateZetaP:
    """Computes exact linear combination alpha*|a> + beta*|b> in Z[zeta_p]."""
    if a.dimension != b.dimension:
        raise DimensionMismatchError(f"Dimension mismatch in superposition: {a.dimension} != {b.dimension}")
    if a.p != b.p or alpha.p != a.p or beta.p != a.p:
        raise RingError("Ring prime mismatch in superposition operands")
    vec = [(alpha * ai) + (beta * bi) for ai, bi in zip(a.vector, b.vector)]
    return StateZetaP(vec, a.p)


def inner_product(a: StateZetaP, b: StateZetaP) -> ZetaP:
    """Computes exact inner product <a|b> = sum_i a_i^* b_i in Z[zeta_p]."""
    if a.dimension != b.dimension:
        raise DimensionMismatchError(f"Dimension mismatch in inner product: {a.dimension} != {b.dimension}")
    if a.p != b.p:
        raise RingError(f"Ring prime mismatch in inner product: {a.p} != {b.p}")
    res = ZetaP.zero(a.p)
    for ai, bi in zip(a.vector, b.vector):
        res = res + (ai.conjugate() * bi)
    return res


def amplitude(state: StateZetaP, index: int) -> ZetaP:
    """Retrieves the exact amplitude of a state vector at basis index."""
    if not (0 <= index < state.dimension):
        raise DimensionMismatchError(f"Index {index} out of range for dimension {state.dimension}")
    return state.vector[index]
