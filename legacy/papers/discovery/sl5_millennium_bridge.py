"""
hyba/research/sl5_millennium_bridge.py
========================================
SL(5, Z) Generalized Topological Coupling — research exploration module.

PURPOSE
-------
This module constructs a fully coupled 5×5 unimodular operator whose diagonal
blocks are drawn from the verified HYBA mathematical substrate:

    ┌ M^{2n}   C  ┐
    │             │    where  det(M^{2n}) = 1  and  det(B3) = 1
    └  0       B3 ┘          ⟹ det(A5) = 1  (block-triangular determinant rule)

and interrogates its exact algebraic spectrum for two Millennium Prize
invariants:

  YANG-MILLS TRACK — discrete spectral gap (lower-bounded away from zero)
  RIEMANN TRACK   — palindromic / reciprocal-root symmetry of char. poly.

EPISTEMOLOGICAL GUARDRAILS (Doctrine §4 & §11)
-----------------------------------------------
  ┌─────────────────────────────────────────────────────────────────────┐
  │  RESEARCH CANDIDATE                                                 │
  │                                                                     │
  │  Finding a palindromic characteristic polynomial is a NECESSARY    │
  │  condition (trivially guaranteed by unimodularity — see Note A     │
  │  below) but is NOT SUFFICIENT to constitute any connection to the  │
  │  Riemann Hypothesis.                                               │
  │                                                                     │
  │  Finding a positive spectral gap in a finite-dimensional discrete  │
  │  Laplacian is also EXPECTED and does NOT constitute a proof of     │
  │  the Yang-Mills mass gap (which is an infinite-dimensional QFT     │
  │  result).                                                           │
  │                                                                     │
  │  These probes are STRUCTURAL CHARACTERISATION tools. They produce  │
  │  exact algebraic invariants of the HYBA substrate, not proofs of   │
  │  Millennium Problems.                                               │
  └─────────────────────────────────────────────────────────────────────┘

Note A — Palindrome property is structural, not Riemann-connected
-----------------------------------------------------------------
For any M ∈ SL(n, Z) (det = 1), the characteristic polynomial p_M(λ)
satisfies the reciprocal symmetry:

    p_M(λ) = (-1)^n · λ^n · p_M(1/λ)

This follows immediately from det(M - λI) and the identity det(M) = 1.
It is a standard result of linear algebra, independent of number theory.
The HYBA matrices are in SL(5, Z), so their char. poly. WILL be palindromic
for every (n, k) — this is guaranteed by construction, not a discovery.
"""

from __future__ import annotations

import sympy as sp
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Module-level SymPy symbols
# ---------------------------------------------------------------------------

_LAM = sp.Symbol("lambda")


# ---------------------------------------------------------------------------
# Generator catalogue — canonical SL(3, Z) substrate generators
# (from the verified commit: discrete_unimodular_3d.py)
# ---------------------------------------------------------------------------

_B3_GENERATORS: List[sp.Matrix] = [
    # Generator 0: Companion matrix of the cubic x^3 - x^2 + x - 1 = 0
    sp.Matrix([[0, 1, 0], [0, 0, 1], [1, -1, 1]]),
    # Generator 1: Upper-unitriangular elementary matrix
    sp.Matrix([[1, 1, 0], [0, 1, 1], [0, 0, 1]]),
    # Generator 2: Lower-unitriangular elementary matrix
    sp.Matrix([[1, 0, 0], [1, 1, 0], [0, 1, 1]]),
]

# Canonical 2×2 Fibonacci generator (Golden ratio minimal polynomial root)
_M2: sp.Matrix = sp.Matrix([[1, 1], [1, 0]])

# Cross-coupling block C (2×3) — non-trivial entanglement between the two sub-manifolds
_C_DEFAULT: sp.Matrix = sp.Matrix([[1, 0, -1], [0, 1, 1]])


# ---------------------------------------------------------------------------
# Core class
# ---------------------------------------------------------------------------


class SL5_GeneralizedTopologicalCoupling:
    """
    Exact algebraic 5D operator from the HYBA SL(3,Z) substrate.

    Constructs the block-triangular matrix:

        A5(n, k) = ┌ M^{2n}    C  ┐  ∈  SL(5, Z)
                   └   0      B3_k ┘

    and extracts its exact SymPy characteristic polynomial for spectral
    invariant analysis.

    All arithmetic is exact integer / rational — no floats at any stage.

    Parameters
    ----------
    b3_generators : list[sp.Matrix], optional
        SL(3,Z) substrate generators.  Defaults to the three canonical
        generators from the verified HYBA native kernels.
    coupling_block : sp.Matrix, optional
        The 2×3 cross-coupling matrix C.  Defaults to ``_C_DEFAULT``.
    """

    def __init__(
        self,
        b3_generators: Optional[List[sp.Matrix]] = None,
        coupling_block: Optional[sp.Matrix] = None,
    ) -> None:
        self.b3_generators: List[sp.Matrix] = b3_generators or _B3_GENERATORS
        self.coupling_block: sp.Matrix = coupling_block or _C_DEFAULT

        # Verify every generator is unimodular before accepting
        for i, gen in enumerate(self.b3_generators):
            d = gen.det()
            assert d == 1, (
                f"B3 generator {i} is not unimodular: det = {d}. "
                "SL(3,Z) membership requires det = 1."
            )

    # ------------------------------------------------------------------
    # Operator construction
    # ------------------------------------------------------------------

    def construct_coupled_operator(self, n: int, k_idx: int) -> sp.Matrix:
        """
        Build the exact 5×5 coupled operator A5(n, k).

        Parameters
        ----------
        n : int ≥ 1
            Power applied to the 2×2 Fibonacci block: M^{2n}.
        k_idx : int
            Index selecting the B3 generator (wraps modulo len(generators)).

        Returns
        -------
        sp.Matrix
            5×5 exact integer matrix in SL(5, Z).

        Raises
        ------
        AssertionError
            If the resulting determinant ≠ 1 (should never fire for valid
            inputs — present as a doctrine guardrail).
        """
        if n < 1:
            raise ValueError(f"n must be ≥ 1, got {n}")

        m2n: sp.Matrix = _M2 ** (2 * n)
        b3: sp.Matrix = self.b3_generators[k_idx % len(self.b3_generators)]

        # Construct 5×5 block-triangular matrix from exact integer blocks
        a5 = sp.zeros(5, 5)
        a5[:2, :2] = m2n
        a5[2:, 2:] = b3
        a5[:2, 2:] = self.coupling_block

        # DOCTRINE GUARDRAIL — strict SL(5,Z) membership
        # For a block-triangular matrix: det = det(M^{2n}) × det(B3) = 1 × 1 = 1
        determinant = a5.det()
        assert determinant == sp.Integer(1), (
            f"A5({n}, {k_idx}) determinant = {determinant} ≠ 1. "
            "SL(5,Z) unimodularity breached — coupling construction is invalid."
        )

        return a5

    # ------------------------------------------------------------------
    # Characteristic polynomial
    # ------------------------------------------------------------------

    def extract_characteristic_polynomial(self, a5: sp.Matrix, simplify: bool = True) -> sp.Expr:
        """
        Compute det(A5 - λ·I₅) exactly using SymPy's algebraic engine.

        Returns
        -------
        sp.Expr
            Characteristic polynomial as an exact sympy expression in λ.
            All coefficients are exact integers (no floats, no approximations).
        """
        i5 = sp.eye(5)
        char_poly = (a5 - _LAM * i5).det()
        return sp.expand(char_poly) if simplify else char_poly

    def get_integer_coefficients(self, char_poly: sp.Expr) -> List[sp.Integer]:
        """
        Extract the ordered list of exact integer coefficients from the
        characteristic polynomial, highest degree first.

        Parameters
        ----------
        char_poly : sp.Expr
            Output of ``extract_characteristic_polynomial``.

        Returns
        -------
        list[sp.Integer]
            Coefficients [c₅, c₄, c₃, c₂, c₁, c₀] where
            p(λ) = c₅λ⁵ + c₄λ⁴ + ... + c₀.
        """
        poly = sp.Poly(char_poly, _LAM)
        return poly.all_coeffs()

    # ------------------------------------------------------------------
    # Probe: Reciprocal / palindromic symmetry  (Riemann track)
    # ------------------------------------------------------------------

    def probe_reciprocal_root_symmetry(
        self, char_poly: sp.Expr
    ) -> Tuple[bool, List[sp.Integer], str]:
        """
        Test whether the characteristic polynomial is palindromic (reciprocal).

        For any M ∈ SL(n, Z), the char. poly. satisfies:
            p(λ) = (-1)^n · λ^n · p(1/λ)
        This is guaranteed by unimodularity alone (see module docstring Note A).

        Returns
        -------
        (is_palindromic, coefficients, explanation)
        is_palindromic : bool
            True if |c_i| == |c_{n-i}| for all i.
        coefficients : list[sp.Integer]
            Exact integer coefficients (highest degree first).
        explanation : str
            Human-readable statement with doctrine classification.

        Evidence classification
        -----------------------
        A True result is a STRUCTURAL PROPERTY of SL(5,Z), not a connection
        to the Riemann Hypothesis.  Do not record as a Millennium discovery.
        """
        coeffs = self.get_integer_coefficients(char_poly)
        n = len(coeffs) - 1

        is_palindromic = all(abs(coeffs[i]) == abs(coeffs[n - i]) for i in range(len(coeffs) // 2))

        if is_palindromic:
            explanation = (
                "PALINDROMIC: |c_i| == |c_{n-i}| for all i. "
                "This is a STRUCTURAL CONSEQUENCE of det(A5) = 1 (unimodularity), "
                "not a connection to the Riemann Hypothesis. "
                "[Evidence class: VERIFIED STRUCTURAL PROPERTY — not Millennium-tier]"
            )
        else:
            explanation = (
                "NON-PALINDROMIC: Symmetry broken at one or more coefficient pairs. "
                "This would indicate a construction error since SL(5,Z) unimodularity "
                "guarantees palindromic char. poly. — investigate coupling block C."
            )

        return is_palindromic, coeffs, explanation

    # ------------------------------------------------------------------
    # Probe: Discrete spectral gap  (Yang-Mills track)
    # ------------------------------------------------------------------

    def probe_discrete_spectral_gap(
        self, a5: sp.Matrix
    ) -> Tuple[Optional[sp.Expr], List[sp.Expr], str]:
        """
        Compute the spectral gap of the discrete symmetrised Laplacian:

            L = I₅ - (A5 + A5⁻¹) / 2

        For M ∈ SL(5,Z) with det = 1, A5⁻¹ = adjugate(A5) (exact integer matrix).
        L is the discrete analogue of a graph Laplacian on the Cayley graph
        of the SL(5,Z) action.

        Returns
        -------
        (spectral_gap, all_eigenvalues, explanation)
        spectral_gap : sp.Expr or None
            The smallest non-zero eigenvalue (exact algebraic number), or None
            if all eigenvalues are zero (degenerate case).
        all_eigenvalues : list[sp.Expr]
            All eigenvalues of L (exact, with multiplicities flattened).
        explanation : str
            Doctrine classification of the result.

        Evidence classification
        -----------------------
        A positive spectral gap in a FINITE-DIMENSIONAL discrete Laplacian is
        expected and does NOT constitute a proof of the Yang-Mills mass gap,
        which is an INFINITE-DIMENSIONAL quantum field theory result requiring
        a fundamentally different mathematical framework.
        """
        # Since det(A5) = 1, the inverse is the adjugate (exact integer matrix)
        a5_inv = a5.adjugate()  # = A5^{-1} when det = 1

        l_mat = sp.eye(5) - (a5 + a5_inv) * sp.Rational(1, 2)

        # Compute exact eigenvalues (may involve algebraic numbers)
        eigenval_dict = l_mat.eigenvals()
        all_eigenvals: List[sp.Expr] = []
        for val, mult in eigenval_dict.items():
            all_eigenvals.extend([val] * mult)

        # Filter zero eigenvalues (trivial invariant state)
        non_zero = [v for v in all_eigenvals if v != sp.Integer(0)]

        if not non_zero:
            return None, all_eigenvals, "Degenerate Laplacian — all eigenvalues are zero."

        # Spectral gap = eigenvalue of smallest absolute value among non-zeros
        spectral_gap = min(non_zero, key=lambda v: abs(sp.re(v.evalf())))

        explanation = (
            f"Spectral gap = {spectral_gap} (exact algebraic number). "
            f"All eigenvalues: {[str(v) for v in all_eigenvals]}. "
            "A positive gap in this FINITE-DIMENSIONAL discrete Laplacian is a "
            "structural property of the SL(5,Z) Cayley graph, not a proof of "
            "the Yang-Mills mass gap (infinite-dimensional QFT). "
            "[Evidence class: RESEARCH CANDIDATE — not Millennium-tier]"
        )

        return spectral_gap, all_eigenvals, explanation

    # ------------------------------------------------------------------
    # Sweep
    # ------------------------------------------------------------------

    def run_sweep(
        self,
        n_range: range,
        k_indices: Optional[List[int]] = None,
    ) -> List[Dict]:
        """
        Sweep over (n, k) parameter pairs and record structural invariants.

        Parameters
        ----------
        n_range : range
            Range of n values to sweep (e.g. ``range(1, 6)``).
        k_indices : list[int], optional
            Generator indices to sweep.  Defaults to all registered generators.

        Returns
        -------
        list[dict]
            One record per (n, k) pair with keys:
            n, k_idx, coefficients, is_palindromic, spectral_gap, explanation.
        """
        if k_indices is None:
            k_indices = list(range(len(self.b3_generators)))

        records = []
        for n in n_range:
            for k in k_indices:
                a5 = self.construct_coupled_operator(n, k)
                char_poly = self.extract_characteristic_polynomial(a5)

                is_pal, coeffs, pal_expl = self.probe_reciprocal_root_symmetry(char_poly)
                gap, evals, gap_expl = self.probe_discrete_spectral_gap(a5)

                records.append(
                    {
                        "n": n,
                        "k_idx": k,
                        "coefficients": [int(c) for c in coeffs],
                        "is_palindromic": is_pal,
                        "spectral_gap": gap,
                        "all_eigenvalues": evals,
                        "palindrome_note": pal_expl,
                        "spectral_gap_note": gap_expl,
                    }
                )

        return records


def generate_a3_matrix(n: int = 1, k: int = 1):
    """
    Generate an exact 3x3 integer matrix in SL(3, Z).

    Pulls from the canonical SL(3, Z) substrate generators or companion
    powers, guaranteeing unimodularity det(A) == 1 and preserving primitive
    lattice directions.

    Parameters
    ----------
    n : int
        Unused power index kept for API consistency.
    k : int
        Power or index applied to the SL(3, Z) generator.

    Returns
    -------
    numpy.ndarray
        3x3 integer matrix with det == 1.
    """
    import numpy as np
    from python_backend.hyba.native_kernels.discrete_unimodular_3d import sl3_matrix_power

    mat = sl3_matrix_power(k)
    return np.array(mat, dtype=np.int64)
