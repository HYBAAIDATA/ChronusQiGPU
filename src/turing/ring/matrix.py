"""
Turing Exact Quantum Library — Matrices over Cyclotomic Ring Z[zeta_p]
"""

from __future__ import annotations
from typing import List
from turing.errors import RingError, DimensionMismatchError
from turing.ring.zeta import ZetaP
from turing.ring.utils import bareiss_det


class MatrixZetaP:
    """
    Exact matrix over the parameterized cyclotomic integer ring Z[zeta_p].
    Zero floating point drift; closed under ring addition, multiplication,
    Hermitian adjoint, Bareiss fraction-free determinant, and adjugate.
    """
    __slots__ = ('rows', 'cols', 'p', 'entries')

    def __init__(self, rows: int, cols: int, entries: List[List[ZetaP]], p: int):
        if len(entries) != rows or any(len(r) != cols for r in entries):
            raise DimensionMismatchError(f"Matrix dimension mismatch: expected ({rows}, {cols}), got shape ({len(entries)}, {[len(r) for r in entries]})")
        for row in entries:
            for e in row:
                if not isinstance(e, ZetaP) or e.p != p:
                    raise RingError(f"All matrix entries must belong to ring Z[zeta_{p}]")
        self.rows = rows
        self.cols = cols
        self.p = p
        self.entries = [[e for e in row] for row in entries]

    @classmethod
    def identity(cls, n: int, p: int) -> 'MatrixZetaP':
        entries = [[ZetaP.zero(p) for _ in range(n)] for _ in range(n)]
        for i in range(n):
            entries[i][i] = ZetaP.one(p)
        return cls(n, n, entries, p)

    @classmethod
    def zero(cls, rows: int, cols: int, p: int) -> 'MatrixZetaP':
        return cls(rows, cols, [[ZetaP.zero(p) for _ in range(cols)] for _ in range(rows)], p)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MatrixZetaP):
            return False
        return (self.rows == other.rows and self.cols == other.cols and
                self.p == other.p and self.entries == other.entries)

    def __add__(self, other: 'MatrixZetaP') -> 'MatrixZetaP':
        if not isinstance(other, MatrixZetaP):
            return NotImplemented
        if self.rows != other.rows or self.cols != other.cols:
            raise DimensionMismatchError(f"Matrix addition shape mismatch: ({self.rows}, {self.cols}) != ({other.rows}, {other.cols})")
        if self.p != other.p:
            raise RingError(f"Matrix addition prime mismatch: {self.p} != {other.p}")
        return MatrixZetaP(self.rows, self.cols,
                           [[self.entries[i][j] + other.entries[i][j] for j in range(self.cols)]
                            for i in range(self.rows)], self.p)

    def __mul__(self, other: 'MatrixZetaP') -> 'MatrixZetaP':
        if not isinstance(other, MatrixZetaP):
            return NotImplemented
        if self.cols != other.rows:
            raise DimensionMismatchError(f"Matrix multiplication shape mismatch: cols {self.cols} != rows {other.rows}")
        if self.p != other.p:
            raise RingError(f"Matrix multiplication prime mismatch: {self.p} != {other.p}")
        res = [[ZetaP.zero(self.p) for _ in range(other.cols)] for _ in range(self.rows)]
        for i in range(self.rows):
            for k in range(self.cols):
                aik = self.entries[i][k]
                if aik != ZetaP.zero(self.p):
                    for j in range(other.cols):
                        res[i][j] = res[i][j] + (aik * other.entries[k][j])
        return MatrixZetaP(self.rows, other.cols, res, self.p)

    def apply_to_vector(self, v: List[ZetaP]) -> List[ZetaP]:
        if self.cols != len(v):
            raise DimensionMismatchError(f"Matrix cols ({self.cols}) does not match vector dim ({len(v)})")
        for e in v:
            if not isinstance(e, ZetaP) or e.p != self.p:
                raise RingError(f"Vector elements must belong to ring Z[zeta_{self.p}]")
        out = []
        for i in range(self.rows):
            s = ZetaP.zero(self.p)
            for j in range(self.cols):
                s = s + (self.entries[i][j] * v[j])
            out.append(s)
        return out

    def kron(self, other: 'MatrixZetaP') -> 'MatrixZetaP':
        if not isinstance(other, MatrixZetaP) or self.p != other.p:
            raise RingError("Ring prime mismatch on Kronecker product")
        r = self.rows * other.rows
        c = self.cols * other.cols
        entries = [[ZetaP.zero(self.p) for _ in range(c)] for _ in range(r)]
        for i in range(self.rows):
            for j in range(self.cols):
                for k in range(other.rows):
                    for l in range(other.cols):
                        entries[i * other.rows + k][j * other.cols + l] = self.entries[i][j] * other.entries[k][l]
        return MatrixZetaP(r, c, entries, self.p)

    def transpose(self) -> 'MatrixZetaP':
        return MatrixZetaP(self.cols, self.rows,
                           [[self.entries[j][i] for j in range(self.rows)] for i in range(self.cols)], self.p)

    def dagger(self) -> 'MatrixZetaP':
        return MatrixZetaP(self.cols, self.rows,
                           [[self.entries[j][i].conjugate() for j in range(self.rows)] for i in range(self.cols)], self.p)

    def det(self) -> ZetaP:
        if self.rows != self.cols:
            raise DimensionMismatchError("Determinant requires a square matrix")
        return bareiss_det(self.entries)

    def is_unitary(self) -> bool:
        if self.rows != self.cols:
            return False
        prod = self.dagger() * self
        return prod == MatrixZetaP.identity(self.cols, self.p)

    def trace(self) -> ZetaP:
        if self.rows != self.cols:
            raise DimensionMismatchError("Trace requires a square matrix")
        s = ZetaP.zero(self.p)
        for i in range(self.rows):
            s = s + self.entries[i][i]
        return s

    def pow(self, k: int) -> 'MatrixZetaP':
        if self.rows != self.cols:
            raise DimensionMismatchError("Matrix power requires a square matrix")
        if k < 0:
            raise ValueError("Non-negative power required")
        res = MatrixZetaP.identity(self.rows, self.p)
        base = self
        while k > 0:
            if k % 2 == 1:
                res = res * base
            base = base * base
            k //= 2
        return res

    def adjugate(self) -> 'MatrixZetaP':
        """
        Exact cofactor matrix adj(A) satisfying A * adj(A) = det(A) * I.
        Computed using Bareiss minor determinants over Z[zeta_p].
        """
        if self.rows != self.cols:
            raise DimensionMismatchError("Adjugate requires a square matrix")
        n = self.rows
        if n == 1:
            return MatrixZetaP(1, 1, [[ZetaP.one(self.p)]], self.p)
        adj_entries = [[ZetaP.zero(self.p) for _ in range(n)] for _ in range(n)]
        for i in range(n):
            for j in range(n):
                sub = [[self.entries[r][c] for c in range(n) if c != j] for r in range(n) if r != i]
                sub_det = bareiss_det(sub)
                sign = 1 if (i + j) % 2 == 0 else -1
                entry = sub_det if sign == 1 else -sub_det
                adj_entries[j][i] = entry
        return MatrixZetaP(n, n, adj_entries, self.p)

    def __repr__(self) -> str:
        return f"MatrixZetaP({self.rows}x{self.cols}, p={self.p})"
