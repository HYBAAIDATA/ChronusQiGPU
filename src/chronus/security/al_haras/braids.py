"""Exact Fibonacci-anyon braid representation over Z[zeta_5].

The fusion space of three tau anyons with total charge tau is two-dimensional.
With R-symbols R1 = zeta^3 = e^{-4 pi i/5} and Rtau = -zeta^4 = e^{3 pi i/5}, and
the F-move written in the gauge

    F = [[phi^-1, 1], [phi^-1, -phi^-1]],

every matrix entry lies in Z[zeta_5]. The braid generators are
sigma_1 = R and sigma_2 = F R F. This module verifies, exactly:

* F^2 = I (the F-move is an involution in this gauge),
* R^10 = I,
* the Artin relation sigma_1 sigma_2 sigma_1 = sigma_2 sigma_1 sigma_2,
* phi^2 = phi + 1 and phi * phi^-1 = 1 inside Z[zeta_5].

The gauge is related to the textbook unitary gauge by a diagonal similarity,
which conjugates both generators and therefore preserves every relation
checked here. These are algebraic identities of a mathematical model; they do
not describe physical hardware or noise behaviour.
"""

from typing import Any, Dict, List, Optional

from chronus.security.al_haras.cyclotomic import (
    ONE,
    PHI,
    PHI_INVERSE,
    ZERO,
    CyclotomicZ5,
    Matrix2,
    mat2_coeffs,
    mat2_identity,
    mat2_mul,
)

R_MATRIX: Matrix2 = [[CyclotomicZ5.zeta_power(3), ZERO], [ZERO, -CyclotomicZ5.zeta_power(4)]]
R_INVERSE: Matrix2 = [[CyclotomicZ5.zeta_power(2), ZERO], [ZERO, -CyclotomicZ5.zeta_power(1)]]
F_MATRIX: Matrix2 = [[PHI_INVERSE, ONE], [PHI_INVERSE, -PHI_INVERSE]]


def _power(m: Matrix2, k: int) -> Matrix2:
    out = mat2_identity()
    for _ in range(k):
        out = mat2_mul(out, m)
    return out


def generators() -> Dict[str, Matrix2]:
    sigma_1 = R_MATRIX
    sigma_1_inv = R_INVERSE
    sigma_2 = mat2_mul(mat2_mul(F_MATRIX, R_MATRIX), F_MATRIX)
    sigma_2_inv = mat2_mul(mat2_mul(F_MATRIX, R_INVERSE), F_MATRIX)
    return {
        "sigma_1": sigma_1,
        "sigma_1^-1": sigma_1_inv,
        "sigma_2": sigma_2,
        "sigma_2^-1": sigma_2_inv,
    }


def verify_relations() -> Dict[str, bool]:
    gens = generators()
    s1, s2 = gens["sigma_1"], gens["sigma_2"]
    ident = mat2_identity()
    zeta = CyclotomicZ5.zeta_power(1)
    cyclotomic_relation = (zeta**4 + zeta**3 + zeta**2 + zeta + ONE).is_zero()
    return {
        "cyclotomic_relation": cyclotomic_relation,
        "golden_ratio_identity": PHI * PHI == PHI + ONE and PHI * PHI_INVERSE == ONE,
        "f_move_involution": mat2_mul(F_MATRIX, F_MATRIX) == ident,
        "r_matrix_order_10": _power(R_MATRIX, 10) == ident and _power(R_MATRIX, 5) != ident,
        "inverses": mat2_mul(s1, gens["sigma_1^-1"]) == ident and mat2_mul(s2, gens["sigma_2^-1"]) == ident,
        "artin_relation": mat2_mul(mat2_mul(s1, s2), s1) == mat2_mul(mat2_mul(s2, s1), s2),
    }


def compile_braid_word(word: Optional[List[str]]) -> Dict[str, Any]:
    """Multiply out a braid word exactly; unknown generators are rejected."""
    gens = generators()
    sequence = list(word or [])
    unknown = [g for g in sequence if g not in gens]
    if unknown:
        raise ValueError(f"unknown braid generators: {sorted(set(unknown))}; allowed: {sorted(gens)}")
    product = mat2_identity()
    for g in sequence:
        product = mat2_mul(product, gens[g])
    return {"braid_word": sequence, "matrix_z5": mat2_coeffs(product)}
