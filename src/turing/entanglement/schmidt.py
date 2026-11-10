"""
Turing Exact Quantum Library — Exact Entanglement Monotones & Schmidt Spectrum
"""

from __future__ import annotations
from typing import List, Tuple
from turing.errors import StateNormError, DimensionMismatchError
from turing.ring.utils import gcd
from turing.ring.zeta import ZetaP
from turing.ring.matrix import MatrixZetaP
from turing.core.state import StateZetaP
from turing.core.obstruction import Obstruction


def matrix_rank_over_field(M: List[List[ZetaP]], p: int) -> int:
    """
    Computes exact matrix rank over the fraction field Q(zeta_p)
    using Bareiss fraction-free Gaussian elimination.
    Elimination divides each 2x2 minor by prev_pivot, bounding coefficient growth.
    Resets prev_pivot to one if a column has no non-zero pivot.
    """
    R = len(M)
    if R == 0:
        return 0
    C = len(M[0])
    if C == 0:
        return 0
    A = [[M[i][j] for j in range(C)] for i in range(R)]
    rank = 0
    row = 0
    prev_pivot = ZetaP.one(p)

    for col in range(C):
        pivot = -1
        for r in range(row, R):
            if A[r][col] != ZetaP.zero(p):
                pivot = r
                break
        if pivot == -1:
            prev_pivot = ZetaP.one(p)
            continue
        A[row], A[pivot] = A[pivot], A[row]
        pivot_val = A[row][col]

        for r in range(row + 1, R):
            factor = A[r][col]
            for c in range(col, C):
                num = (A[r][c] * pivot_val) - (A[row][c] * factor)
                A[r][c] = num.exact_div(prev_pivot)
        prev_pivot = pivot_val
        rank += 1
        row += 1
        if row == R:
            break
    return rank


def schmidt_rank(state: StateZetaP, bipartition: Tuple[int, int]) -> int:
    """
    Computes exact Schmidt rank across a bipartite split (dim_a, dim_b).
    Algebraic rank is invariant under local basis changes.
    """
    dim_a, dim_b = bipartition
    if dim_a * dim_b != state.dimension:
        raise DimensionMismatchError(f"Bipartition dimensions {dim_a}x{dim_b}={dim_a*dim_b} must match state dimension {state.dimension}")
    grid = [[state.vector[i * dim_b + j] for j in range(dim_b)] for i in range(dim_a)]
    return matrix_rank_over_field(grid, state.p)


def normalized_schmidt_coefficients(state: StateZetaP, bipartition: Tuple[int, int]) -> Obstruction:
    """Formal obstruction: normalized Schmidt coefficients require non-integral roots."""
    r = schmidt_rank(state, bipartition)
    return Obstruction(
        primitive="schmidt_coefficients",
        value=f"1/sqrt({r})",
        ring=f"the ring containing sqrt({r})",
        message="normalized Schmidt coefficients require non-integral roots; rank is the exact primitive"
    )


def reduced_density_gram(state: StateZetaP, d_a: int, d_b: int) -> MatrixZetaP:
    """
    Computes the unnormalized Hermitian Gram matrix rho_A = Psi * Psi† over Z[zeta_p].
    Bypasses square roots by representing the entanglement state in the ring.
    """
    if d_a * d_b != state.dimension:
        raise DimensionMismatchError(f"Bipartition dimensions {d_a}x{d_b} must match total state dimension {state.dimension}")
    grid = [[state.vector[i * d_b + j] for j in range(d_b)] for i in range(d_a)]
    Psi = MatrixZetaP(d_a, d_b, grid, state.p)
    return Psi * Psi.dagger()


def exact_renyi_purity(state: StateZetaP, d_a: int, d_b: int, k: int = 2) -> Tuple[int, int]:
    """
    Computes exact rational k-th Renyi purity Tr(rho_A^k) / (Tr(rho_A))^k in Q.
    Provides an exact algebraic entanglement monotone without square roots.
    """
    rho_A = reduced_density_gram(state, d_a, d_b)
    tr_rho = rho_A.trace()
    if tr_rho == ZetaP.zero(state.p):
        raise StateNormError("State has zero norm")
    rho_k = rho_A.pow(k)
    tr_rho_k = rho_k.trace()
    den_zeta = tr_rho.pow(k)

    if all(c == 0 for c in tr_rho_k.coeffs[1:]) and all(c == 0 for c in den_zeta.coeffs[1:]):
        n_val = tr_rho_k.coeffs[0]
        d_val = den_zeta.coeffs[0]
        g = gcd(n_val, d_val)
        return (n_val // g, d_val // g)

    rat = den_zeta.field_inverse() * tr_rho_k
    n_val = rat.num.coeffs[0]
    d_val = rat.den
    g = gcd(n_val, d_val)
    return (n_val // g, d_val // g)
