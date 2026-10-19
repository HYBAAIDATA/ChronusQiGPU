"""
FAMILY 10: MATHEMATICAL IDENTITIES
=====================================
Extended golden-ratio family members: d'Ocagne's identity, Honsberger's
identity, Fibonacci polynomials, and Lucas polynomials.

THEOREMS:
  - d'Ocagne's identity: F_m*F_{n+1} - F_{m+1}*F_n = (-1)^n * F_{m-n}
  - Honsberger's identity: F_{n-1}*F_k + F_n*F_{k+1} = F_{n+k}
  - Fibonacci polynomial recurrence: F_n(x) = x*F_{n-1}(x) + F_{n-2}(x)
  - Lucas polynomial recurrence: L_n(x) = x*L_{n-1}(x) + L_{n-2}(x)

INVARIANTS:
  - d'Ocagne distance matches direct F_{m-n} computation
  - Honsberger composition produces correct (n+k, F_{n+k}, F_{n+k+1})

DEMONSTRATIONS:
  - F_n(1) = F_n specialization (polynomial → standard Fibonacci)
  - L_n(1) = L_n specialization (polynomial → standard Lucas)
  - L_n(x) = F_{n-1}(x) + F_{n+1}(x) relation
  - d'Ocagne signed Fibonacci extension F_{-k} = (-1)^{k+1}*F_k
"""

from ..results import CheckRegistry
from ..sequences import fibonacci, lucas
from ..math_identities import (
    docagne_identity, docagne_distance, fib_signed,
    honsberger_identity, honsberger_compose,
    fib_poly_coeffs, lucas_poly_coeffs,
    fib_poly_eval, lucas_poly_eval,
    fib_poly_specialization, lucas_poly_specialization,
    lucas_fib_relation,
)


def run(registry: CheckRegistry, max_n: int = 5000) -> None:
    family = "FAMILY 10: Mathematical Identities"
    purpose = "IDENTITIES"

    # ═══════════════════════════════════════════════════════════════════
    #  10A: D'OCAGNE'S IDENTITY
    # ═══════════════════════════════════════════════════════════════════

    # ── 10A-1: Identity holds for m > n across a grid ──
    test_grid = [(m, n) for m in range(1, 200) for n in range(1, m)]
    all_pass = True
    for m, n in test_grid:
        if not docagne_identity(m, n):
            all_pass = False
            registry.add_check(family, purpose,
                f"10A-1: d'Ocagne fails at m={m}, n={n}", False, "theorem")
            break
    if all_pass:
        registry.add_check(family, purpose,
            f"10A-1: d'Ocagne holds for all m>n (19,701 pairs, m,n ∈ [1,199])",
            True, "theorem",
            "F_m*F_{n+1} - F_{m+1}*F_n = (-1)^n * F_{m-n}")

    # ── 10A-2: Identity holds for m < n (signed Fibonacci) ──
    test_grid_lt = [(m, n) for m in range(1, 100) for n in range(m + 1, m + 50)]
    all_pass = True
    for m, n in test_grid_lt:
        if not docagne_identity(m, n):
            all_pass = False
            registry.add_check(family, purpose,
                f"10A-2: d'Ocagne fails at m={m}, n={n} (m<n)", False, "theorem")
            break
    if all_pass:
        registry.add_check(family, purpose,
            f"10A-2: d'Ocagne holds for m<n via signed Fibonacci (4,850 pairs)",
            True, "theorem",
            "Uses F_{-k} = (-1)^{k+1} * F_k extension")

    # ── 10A-3: Identity holds for m = n ──
    all_pass = True
    for n in range(0, 500):
        if not docagne_identity(n, n):
            all_pass = False
            break
    registry.add_check(family, purpose,
        f"10A-3: d'Ocagne holds for m=n (F_m*F_{n+1} - F_{m+1}*F_n = 0)",
        all_pass, "theorem",
        "When m=n, both sides equal 0 since F_0 = 0")

    # ── 10A-4: Distance matches direct computation ──
    all_match = True
    for m in range(0, 300):
        for n in range(0, 300):
            direct = fib_signed(m - n)
            via_docagne = docagne_distance(m, n)
            if direct != via_docagne:
                all_match = False
                registry.add_check(family, purpose,
                    f"10A-4: Distance mismatch at m={m}, n={n}", False, "invariant")
                break
        if not all_match:
            break
    if all_match:
        registry.add_check(family, purpose,
            f"10A-4: d'Ocagne distance == direct F_{{m-n}} for all m,n ∈ [0,299]",
            True, "invariant",
            "90,000 pairs verified — exact integer match")

    # ── 10A-5: Large-index stress test ──
    large_pass = True
    for m in [1000, 5000, 10000]:
        for n in [500, m // 2, m - 1]:
            if not docagne_identity(m, n):
                large_pass = False
                break
    registry.add_check(family, purpose,
        f"10A-5: d'Ocagne holds at large indices (m up to 10,000)",
        large_pass, "theorem",
        "Tests with Fibonacci numbers having thousands of digits")

    # ═══════════════════════════════════════════════════════════════════
    #  10B: HONSBERGER'S IDENTITY
    # ═══════════════════════════════════════════════════════════════════

    # ── 10B-1: Identity holds across a grid ──
    test_grid = [(n, k) for n in range(1, 200) for k in range(0, 200)]
    all_pass = True
    for n, k in test_grid:
        if not honsberger_identity(n, k):
            all_pass = False
            registry.add_check(family, purpose,
                f"10B-1: Honsberger fails at n={n}, k={k}", False, "theorem")
            break
    if all_pass:
        registry.add_check(family, purpose,
            f"10B-1: Honsberger holds for all n,k ∈ [1,199] × [0,199] (39,800 pairs)",
            True, "theorem",
            "F_{n-1}*F_k + F_n*F_{k+1} = F_{n+k}")

    # ── 10B-2: Composition produces correct F_{n+k} and F_{n+k+1} ──
    all_pass = True
    for n in range(1, 200):
        for k in range(0, 200):
            result = honsberger_compose(n, k)
            expected_nk = fibonacci(n + k)
            expected_nk1 = fibonacci(n + k + 1)
            if result[1] != expected_nk or result[2] != expected_nk1:
                all_pass = False
                registry.add_check(family, purpose,
                    f"10B-2: Composition mismatch at n={n}, k={k}", False, "invariant")
                break
        if not all_pass:
            break
    if all_pass:
        registry.add_check(family, purpose,
            f"10B-2: Honsberger compose returns correct F_{{n+k}} and F_{{n+k+1}}",
            True, "invariant",
            "Both F_{n+k} and F_{n+k+1} verified against direct computation")

    # ── 10B-3: Large-index stress test ──
    large_pass = True
    for n in [1000, 5000, 10000]:
        for k in [500, n // 2, n - 1]:
            if not honsberger_identity(n, k):
                large_pass = False
                break
    registry.add_check(family, purpose,
        f"10B-3: Honsberger holds at large indices (n up to 10,000)",
        large_pass, "theorem",
        "F_{n+k} with thousands of digits, verified via identity")

    # ═══════════════════════════════════════════════════════════════════
    #  10C: FIBONACCI POLYNOMIALS
    # ═══════════════════════════════════════════════════════════════════

    # ── 10C-1: Recurrence F_n(x) = x*F_{n-1}(x) + F_{n-2}(x) ──
    all_pass = True
    for n in range(2, 100):
        # Verify at multiple evaluation points
        for x in [0, 1, 2, 3, 5, 10, -1, -2]:
            fn = fib_poly_eval(n, x)
            fnm1 = fib_poly_eval(n - 1, x)
            fnm2 = fib_poly_eval(n - 2, x)
            if fn != x * fnm1 + fnm2:
                all_pass = False
                registry.add_check(family, purpose,
                    f"10C-1: Fibonacci poly recurrence fails at n={n}, x={x}",
                    False, "theorem")
                break
        if not all_pass:
            break
    if all_pass:
        registry.add_check(family, purpose,
            f"10C-1: Fibonacci polynomial recurrence holds (n=2..99, 8 eval points)",
            True, "theorem",
            "F_n(x) = x*F_{n-1}(x) + F_{n-2}(x)")

    # ── 10C-2: Specialization F_n(1) = F_n ──
    all_pass = True
    for n in range(0, 200):
        if not fib_poly_specialization(n):
            all_pass = False
            registry.add_check(family, purpose,
                f"10C-2: F_n(1) != F_n at n={n}", False, "demonstration")
            break
    if all_pass:
        registry.add_check(family, purpose,
            f"10C-2: Fibonacci polynomial specialization F_n(1) = F_n (n=0..199)",
            True, "demonstration",
            "Polynomial at x=1 recovers standard Fibonacci numbers")

    # ── 10C-3: Coefficient structure ──
    # F_n(x) has degree n-1, and coefficients are binomial-like
    # F_2(x) = x, F_3(x) = x^2+1, F_4(x) = x^3+2x, F_5(x) = x^4+3x^2+1
    expected_coeffs = {
        0: [0], 1: [1], 2: [0, 1], 3: [1, 0, 1],
        4: [0, 2, 0, 1], 5: [1, 0, 3, 0, 1],
    }
    coeff_pass = True
    for n, expected in expected_coeffs.items():
        if fib_poly_coeffs(n) != expected:
            coeff_pass = False
            break
    registry.add_check(family, purpose,
        f"10C-3: Fibonacci polynomial coefficient structure (n=0..5)",
        coeff_pass, "theorem",
        "F_0=0, F_1=1, F_2=x, F_3=x²+1, F_4=x³+2x, F_5=x⁴+3x²+1")

    # ═══════════════════════════════════════════════════════════════════
    #  10D: LUCAS POLYNOMIALS
    # ═══════════════════════════════════════════════════════════════════

    # ── 10D-1: Recurrence L_n(x) = x*L_{n-1}(x) + L_{n-2}(x) ──
    all_pass = True
    for n in range(2, 100):
        for x in [0, 1, 2, 3, 5, 10, -1, -2]:
            ln = lucas_poly_eval(n, x)
            lnm1 = lucas_poly_eval(n - 1, x)
            lnm2 = lucas_poly_eval(n - 2, x)
            if ln != x * lnm1 + lnm2:
                all_pass = False
                registry.add_check(family, purpose,
                    f"10D-1: Lucas poly recurrence fails at n={n}, x={x}",
                    False, "theorem")
                break
        if not all_pass:
            break
    if all_pass:
        registry.add_check(family, purpose,
            f"10D-1: Lucas polynomial recurrence holds (n=2..99, 8 eval points)",
            True, "theorem",
            "L_n(x) = x*L_{n-1}(x) + L_{n-2}(x)")

    # ── 10D-2: Specialization L_n(1) = L_n ──
    all_pass = True
    for n in range(0, 200):
        if not lucas_poly_specialization(n):
            all_pass = False
            registry.add_check(family, purpose,
                f"10D-2: L_n(1) != L_n at n={n}", False, "demonstration")
            break
    if all_pass:
        registry.add_check(family, purpose,
            f"10D-2: Lucas polynomial specialization L_n(1) = L_n (n=0..199)",
            True, "demonstration",
            "Polynomial at x=1 recovers standard Lucas numbers")

    # ── 10D-3: Coefficient structure ──
    expected_l_coeffs = {
        0: [2], 1: [0, 1], 2: [2, 0, 1],
        3: [0, 3, 0, 1], 4: [2, 0, 4, 0, 1],
    }
    coeff_pass = True
    for n, expected in expected_l_coeffs.items():
        if lucas_poly_coeffs(n) != expected:
            coeff_pass = False
            break
    registry.add_check(family, purpose,
        f"10D-3: Lucas polynomial coefficient structure (n=0..4)",
        coeff_pass, "theorem",
        "L_0=2, L_1=x, L_2=x²+2, L_3=x³+3x, L_4=x⁴+4x²+2")

    # ═══════════════════════════════════════════════════════════════════
    #  10E: LUCAS-FIBONACCI POLYNOMIAL RELATION
    # ═══════════════════════════════════════════════════════════════════

    # ── 10E-1: L_n(x) = F_{n-1}(x) + F_{n+1}(x) ──
    all_pass = True
    for n in range(1, 200):
        if not lucas_fib_relation(n):
            all_pass = False
            registry.add_check(family, purpose,
                f"10E-1: L_n(x) != F_{{n-1}}(x) + F_{{n+1}}(x) at n={n}",
                False, "theorem")
            break
    if all_pass:
        registry.add_check(family, purpose,
            f"10E-1: L_n(x) = F_{{n-1}}(x) + F_{{n+1}}(x) holds (n=1..199)",
            True, "theorem",
            "Polynomial generalization of L_n = F_{n-1} + F_{n+1}")

    # ═══════════════════════════════════════════════════════════════════
    #  10F: SIGNED FIBONACCI EXTENSION
    # ═══════════════════════════════════════════════════════════════════

    # ── 10F-1: F_{-k} = (-1)^{k+1} * F_k ──
    all_pass = True
    for k in range(1, 200):
        expected = (1 if k % 2 == 1 else -1) * fibonacci(k)
        if fib_signed(-k) != expected:
            all_pass = False
            registry.add_check(family, purpose,
                f"10F-1: F_{{-{k}}} mismatch", False, "theorem")
            break
    if all_pass:
        registry.add_check(family, purpose,
            f"10F-1: Signed Fibonacci F_{{-k}} = (-1)^{{k+1}} * F_k (k=1..199)",
            True, "theorem",
            "Enables d'Ocagne identity for m < n")

    # ── 10F-2: F_0 = 0 via signed extension ──
    registry.add_check(family, purpose,
        f"10F-2: F_0 = 0 via signed extension",
        fib_signed(0) == 0, "theorem",
        "Boundary case for signed Fibonacci")
