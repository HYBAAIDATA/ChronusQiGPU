"""
Turing Exact Quantum Library — Exact Unitary and Projective Unitary Operators
"""

from __future__ import annotations
from typing import TYPE_CHECKING
from turing.exact.errors import RingError, DimensionMismatchError
from turing.exact.ring.matrix import MatrixZetaP
from turing.exact.ring.zeta import ZetaP

if TYPE_CHECKING:
    from turing.exact.core.state import StateZetaP


class UnitaryZetaP:
    """
    Exact unitary operator U satisfying U† * U = I in Z[zeta_p].
    Preserves inner products and unit algebraic norms.
    """
    __slots__ = ('matrix', 'dimension', 'p')

    def __init__(self, matrix: MatrixZetaP):
        if not matrix.is_unitary():
            raise RingError("Matrix must be algebraically unitary (U†U = I)")
        self.matrix = matrix
        self.dimension = matrix.rows
        self.p = matrix.p

    @classmethod
    def identity(cls, n: int, p: int) -> 'UnitaryZetaP':
        return cls(MatrixZetaP.identity(n, p))

    def compose(self, other: 'UnitaryZetaP') -> 'UnitaryZetaP':
        if self.dimension != other.dimension:
            raise DimensionMismatchError(f"Dimension mismatch in unitary composition: {self.dimension} != {other.dimension}")
        if self.p != other.p:
            raise RingError(f"Ring prime mismatch in unitary composition: {self.p} != {other.p}")
        return UnitaryZetaP(self.matrix * other.matrix)

    def dagger(self) -> 'UnitaryZetaP':
        return UnitaryZetaP(self.matrix.dagger())

    def apply(self, state: 'StateZetaP') -> 'StateZetaP':
        from turing.exact.core.state import StateZetaP
        if self.dimension != state.dimension:
            raise DimensionMismatchError(f"Operator dimension ({self.dimension}) does not match state dimension ({state.dimension})")
        if self.p != state.p:
            raise RingError(f"Ring prime mismatch: operator p={self.p} != state p={state.p}")
        return StateZetaP(self.matrix.apply_to_vector(state.vector), self.p)

    def __repr__(self) -> str:
        return f"UnitaryZetaP(dim={self.dimension}, p={self.p})"


class ProjectiveUnitaryZetaP:
    """
    Projective unitary operator over P(H).
    Satisfies matrix.dagger() * matrix == scale_norm * I with scale_norm in Z \\ {0}.
    Global scalar factors cancel identically in projective Born measurements.
    """
    __slots__ = ('matrix', 'scale_norm', 'dimension', 'p')

    def __init__(self, matrix: MatrixZetaP, scale_norm: int):
        if scale_norm == 0:
            raise ValueError("Projective unitary scale norm must be non-zero")
        if matrix.rows != matrix.cols:
            raise DimensionMismatchError("Projective unitary matrix must be square")
        self.matrix = matrix
        self.scale_norm = scale_norm
        self.dimension = matrix.rows
        self.p = matrix.p

        prod = matrix.dagger() * matrix
        expected_diag = ZetaP.from_int(scale_norm, self.p)
        for i in range(self.dimension):
            for j in range(self.dimension):
                if i == j:
                    if prod.entries[i][j] != expected_diag:
                        raise RingError("Diagonal entry does not match scale_norm * I")
                else:
                    if prod.entries[i][j] != ZetaP.zero(self.p):
                        raise RingError("Off-diagonal entry in U†U must be zero")

    def compose(self, other: 'ProjectiveUnitaryZetaP') -> 'ProjectiveUnitaryZetaP':
        if self.dimension != other.dimension:
            raise DimensionMismatchError(f"Dimension mismatch in projective composition: {self.dimension} != {other.dimension}")
        if self.p != other.p:
            raise RingError(f"Ring prime mismatch: {self.p} != {other.p}")
        return ProjectiveUnitaryZetaP(self.matrix * other.matrix, self.scale_norm * other.scale_norm)

    def dagger(self) -> 'ProjectiveUnitaryZetaP':
        return ProjectiveUnitaryZetaP(self.matrix.dagger(), self.scale_norm)

    def apply(self, state: 'StateZetaP') -> 'StateZetaP':
        from turing.exact.core.state import StateZetaP
        if self.dimension != state.dimension:
            raise DimensionMismatchError(f"Operator dimension ({self.dimension}) does not match state dimension ({state.dimension})")
        if self.p != state.p:
            raise RingError(f"Ring prime mismatch: operator p={self.p} != state p={state.p}")
        return StateZetaP(self.matrix.apply_to_vector(state.vector), self.p)

    def __repr__(self) -> str:
        return f"ProjectiveUnitaryZetaP(dim={self.dimension}, scale_norm={self.scale_norm}, p={self.p})"
