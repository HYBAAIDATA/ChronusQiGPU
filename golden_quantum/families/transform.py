"""
FAMILY 5: φ + EIGENSTRUCTURE → TRANSFORM
==========================================
The Fibonacci Q-matrix and its spectral properties.

THEOREMS:
  - Q-matrix form: Q^n = [[F(n+1), F(n)], [F(n), F(n-1)]]
  - Characteristic polynomial: λ² - λ - 1 = 0
  - Eigenvalues: φ and ψ (= 1 - φ)
  - Eigenvectors: [φ, 1] and [ψ, 1]

INVARIANTS:
  - Q matrix entries match Fibonacci numbers
  - Q satisfies its own characteristic polynomial (Cayley-Hamilton)

DEMONSTRATIONS:
  - Spectral reconstruction of Q^n from eigenvalues
  - Golden ratio as spectral basis
"""

from ..results import CheckRegistry
from ..sequences import fibonacci, fib_pair
from ..matrices import matrix_power, matrix_mult, matrix_det, matrix_trace
from ..constants import PHI_D, PSI_D, SQRT5_D
from decimal import Decimal, ROUND_HALF_EVEN


def run(registry: CheckRegistry, max_n: int = 10000) -> None:
    family = "FAMILY 5: φ + Eigenstructure"
    purpose = "TRANSFORM"

    # ── 5A: Q-matrix form Q^n = [[F(n+1), F(n)], [F(n), F(n-1)]] ──
    all_form = True
    for n in range(1, min(max_n, 2001)):
        m = matrix_power(n)
        fn, fn1 = fib_pair(n)
        fn_1 = fn1 - fn
        if m[0][0] != fn1 or m[0][1] != fn or m[1][0] != fn or m[1][1] != fn_1:
            all_form = False
            registry.add_check(
                family, purpose,
                f"5A: Q-matrix form at n={n}",
                False, "theorem",
            )
            break
    if all_form:
        registry.add_check(
            family, purpose,
            f"5A: Q^n = [[F(n+1),F(n)],[F(n),F(n-1)]] for n=1..{min(max_n,2000)}",
            True, "theorem",
        )

    # ── 5B: Characteristic polynomial λ² - λ - 1 = 0 ──
    # The characteristic polynomial of Q = [[1,1],[1,0]] is:
    # det(Q - λI) = (1-λ)(-λ) - 1 = λ² - λ - 1
    # Roots: λ = (1 ± √5)/2 = φ, ψ
    # Verify: φ² - φ - 1 = 0 and ψ² - ψ - 1 = 0
    phi_check = PHI_D ** 2 - PHI_D - 1
    psi_check = PSI_D ** 2 - PSI_D - 1
    poly_ok = abs(phi_check) < Decimal("1e-100") and abs(psi_check) < Decimal("1e-100")
    registry.add_check(
        family, purpose,
        "5B: Characteristic polynomial λ² - λ - 1 = 0 has roots φ, ψ",
        poly_ok, "theorem",
        f"φ²-φ-1={phi_check}, ψ²-ψ-1={psi_check}",
    )

    # ── 5C: Eigenvalues are φ and ψ ──
    # Verify: Q · [φ, 1]^T = φ · [φ, 1]^T
    # Q = [[1,1],[1,0]], so Q·[φ,1] = [φ+1, φ] = [φ², φ] = φ·[φ, 1] ✓
    # (since φ² = φ + 1)
    # Use tolerance since PHI_D is a Decimal approximation, not exact φ
    tol = Decimal("1e-100")
    eigen_phi_ok = abs(PHI_D + 1 - PHI_D ** 2) < tol  # φ + 1 = φ²
    eigen_psi_ok = abs(PSI_D + 1 - PSI_D ** 2) < tol  # ψ + 1 = ψ²
    registry.add_check(
        family, purpose,
        "5C: Eigenvalues of Q are φ and ψ (Q·[φ,1]ᵀ = φ·[φ,1]ᵀ)",
        eigen_phi_ok and eigen_psi_ok, "theorem",
        "Q·[φ,1]ᵀ = [φ+1, φ]ᵀ = [φ², φ]ᵀ = φ·[φ,1]ᵀ",
    )

    # ── 5D: Eigenvalue sum = trace = 1, product = determinant = -1 ──
    # tr(Q) = 1 + 0 = 1 = φ + ψ
    # det(Q) = 0 - 1 = -1 = φ · ψ
    # Use tolerance since PHI_D/PSI_D are Decimal approximations
    tol = Decimal("1e-100")
    trace_ok = abs(PHI_D + PSI_D - 1) < tol  # φ + ψ = 1
    det_ok = abs(PHI_D * PSI_D + 1) < tol    # φ · ψ = -1
    registry.add_check(
        family, purpose,
        "5D: Eigenvalue sum = tr(Q) = 1, product = det(Q) = -1",
        trace_ok and det_ok, "theorem",
        "φ + ψ = 1, φ · ψ = -1 (Vieta's formulas)",
    )

    # ── 5E: Cayley-Hamilton theorem Q² = Q + I ──
    # Characteristic polynomial λ² - λ - 1 = 0
    # Cayley-Hamilton: Q² - Q - I = 0 → Q² = Q + I
    Q = [[1, 1], [1, 0]]
    I = [[1, 0], [0, 1]]
    Q2 = matrix_mult(Q, Q)
    Q_plus_I = [[Q[0][0] + 1, Q[0][1]], [Q[1][0], Q[1][1] + 1]]
    cayley_ok = (Q2[0] == Q_plus_I[0]) and (Q2[1] == Q_plus_I[1])
    registry.add_check(
        family, purpose,
        "5E: Cayley-Hamilton Q² = Q + I (characteristic polynomial satisfied)",
        cayley_ok, "theorem",
    )

    # ── 5F: Q^2 entries ──
    # Q^2 = [[F(3), F(2)], [F(2), F(1)]] = [[2, 1], [1, 1]]
    Q2_check = matrix_power(2)
    q2_ok = (Q2_check == [[2, 1], [1, 1]])
    registry.add_check(
        family, purpose,
        "5F: Q² = [[2,1],[1,1]] = [[F(3),F(2)],[F(2),F(1)]]",
        q2_ok, "theorem",
    )

    # ── 5G: Spectral reconstruction (demonstration) ──
    # Q^n can be reconstructed from its spectral decomposition:
    # Q^n = (φ^n / (φ-ψ)) · [[φ,1],[1,-1]]·... (projection formula)
    # More precisely, using the eigenvalue decomposition:
    # Q^n = P · D^n · P^(-1) where P = [[φ, ψ],[1, 1]], D = diag(φ, ψ)
    # This gives Q^n = (1/√5) · [[φ^(n+1)-ψ^(n+1), φ^n-ψ^n], [φ^n-ψ^n, φ^(n-1)-ψ^(n-1)]]
    # which is exactly Binet's formula in matrix form.
    test_ns = [1, 5, 10, 50, 100]
    all_spectral = True
    for n in test_ns:
        if n > max_n:
            continue
        m = matrix_power(n)
        # Reconstruct via Binet
        from ..sequences import binet_f
        fn1 = binet_f(n + 1)
        fn = binet_f(n)
        fn_1 = binet_f(n - 1)
        reconstructed = [[fn1, fn], [fn, fn_1]]
        if m != reconstructed:
            all_spectral = False
            registry.add_check(
                family, purpose,
                f"5G: Spectral reconstruction at n={n}",
                False, "demonstration",
            )
            break
    if all_spectral:
        registry.add_check(
            family, purpose,
            f"5G: Spectral reconstruction Q^n = Binet matrix for n ∈ {test_ns}",
            True, "demonstration",
            "Q^n reconstructed from eigenvalue decomposition matches direct computation",
        )

    # ── 5H: Q^n determinant from eigenvalues ──
    # det(Q^n) = φ^n · ψ^n = (φψ)^n = (-1)^n
    all_det_eigen = True
    for n in range(0, 200):
        det_val = matrix_det(matrix_power(n))
        eigen_det = (-1) ** n
        if det_val != eigen_det:
            all_det_eigen = False
            break
    if all_det_eigen:
        registry.add_check(
            family, purpose,
            "5H: det(Q^n) = (φ·ψ)^n = (-1)^n for n=0..199",
            True, "theorem",
            "Determinant from eigenvalues: det(Q^n) = φ^n · ψ^n = (-1)^n",
        )
