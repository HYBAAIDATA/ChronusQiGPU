"""
FAMILY 4: φ + CASSINI → SIGNAL
================================
Cassini's identity: F(n-1)·F(n+1) - F(n)² = (-1)^n.
Provides parity signals, orientation checks, and integrity verification.

THEOREMS:
  - Cassini's identity (exact)
  - Matrix determinant signal: det(Q^n) = (-1)^n
  - Matrix trace signal: tr(Q^n) = L(n)
  - Fibonacci parity period 3

INVARIANTS:
  - Integrity check detects single-entry mutation

DEMONSTRATIONS:
  - Parity pattern verification
"""

from ..results import CheckRegistry
from ..sequences import fibonacci, lucas
from ..matrices import matrix_power, matrix_det, matrix_trace, matrix_mult, matrix_equal


def run(registry: CheckRegistry, max_n: int = 10000) -> None:
    family = "FAMILY 4: φ + Cassini"
    purpose = "SIGNAL"

    test_range = range(1, min(max_n, 5001))

    # ── 4A: Cassini's identity F(n-1)·F(n+1) - F(n)² = (-1)^n ──
    all_cassini = True
    for n in test_range:
        lhs = fibonacci(n - 1) * fibonacci(n + 1) - fibonacci(n) ** 2
        expected = (-1) ** n
        if lhs != expected:
            all_cassini = False
            registry.add_check(
                family, purpose,
                f"4A: Cassini at n={n}",
                False, "theorem",
                f"F({n-1})·F({n+1}) - F({n})² = {lhs}, expected {expected}",
            )
            break
    if all_cassini:
        registry.add_check(
            family, purpose,
            f"4A: Cassini's identity F(n-1)·F(n+1) - F(n)² = (-1)^n for n=1..{min(max_n,5000)}",
            True, "theorem",
        )

    # ── 4B: Matrix determinant signal det(Q^n) = (-1)^n ──
    all_det = True
    for n in range(0, min(max_n, 2001)):
        m = matrix_power(n)
        det = matrix_det(m)
        expected = (-1) ** n
        if det != expected:
            all_det = False
            registry.add_check(
                family, purpose,
                f"4B: det(Q^{n}) = (-1)^{n}",
                False, "theorem",
            )
            break
    if all_det:
        registry.add_check(
            family, purpose,
            f"4B: Matrix determinant det(Q^n) = (-1)^n for n=0..{min(max_n,2000)}",
            True, "theorem",
            "This is Cassini's identity in matrix form",
        )

    # ── 4C: Matrix trace signal tr(Q^n) = L(n) ──
    all_trace = True
    for n in range(0, min(max_n, 2001)):
        m = matrix_power(n)
        tr = matrix_trace(m)
        ln = lucas(n)
        if tr != ln:
            all_trace = False
            registry.add_check(
                family, purpose,
                f"4C: tr(Q^{n}) = L({n})",
                False, "theorem",
            )
            break
    if all_trace:
        registry.add_check(
            family, purpose,
            f"4C: Matrix trace tr(Q^n) = L(n) for n=0..{min(max_n,2000)}",
            True, "theorem",
        )

    # ── 4D: Fibonacci parity period 3 ──
    # F(n) is even ⟺ n ≡ 0 (mod 3)
    all_parity = True
    for n in range(1, 1000):
        is_even = fibonacci(n) % 2 == 0
        expected_even = (n % 3 == 0)
        if is_even != expected_even:
            all_parity = False
            registry.add_check(
                family, purpose,
                f"4D: Parity at n={n}",
                False, "theorem",
            )
            break
    if all_parity:
        registry.add_check(
            family, purpose,
            "4D: Fibonacci parity period 3: F(n) even ⟺ n ≡ 0 (mod 3) for n=1..999",
            True, "theorem",
        )

    # ── 4E: Lucas parity pattern ──
    # L(n) is even ⟺ n ≡ 0 (mod 3)
    # Actually: L(n) mod 2: 0, 1, 1, 0, 1, 1, 0, 1, 1, ... period 3
    all_lucas_parity = True
    for n in range(0, 1000):
        is_even = lucas(n) % 2 == 0
        expected_even = (n % 3 == 0)
        if is_even != expected_even:
            all_lucas_parity = False
            break
    if all_lucas_parity:
        registry.add_check(
            family, purpose,
            "4E: Lucas parity period 3: L(n) even ⟺ n ≡ 0 (mod 3) for n=0..999",
            True, "theorem",
        )

    # ── 4F: Integrity check — mutation detection ──
    # Mutate one entry of Q^n and verify Cassini check fails
    n_test = 100
    m = matrix_power(n_test)
    original_det = matrix_det(m)
    expected_det = (-1) ** n_test

    # Mutate: add 1 to one entry
    m_mutated = [row[:] for row in m]
    m_mutated[0][0] += 1
    mutated_det = matrix_det(m_mutated)

    integrity_ok = (original_det == expected_det) and (mutated_det != expected_det)
    registry.add_check(
        family, purpose,
        f"4F: Integrity check detects single-entry mutation (Q^{n_test})",
        integrity_ok, "invariant",
        f"Original det={original_det} (expected {expected_det}), mutated det={mutated_det}",
    )

    # ── 4G: Matrix semigroup property Q^m · Q^n = Q^(m+n) ──
    test_pairs = [(1, 1), (2, 3), (5, 7), (10, 20), (50, 100), (100, 200)]
    all_semigroup = True
    for m_val, n_val in test_pairs:
        if m_val + n_val > min(max_n, 1000):
            continue
        qm = matrix_power(m_val)
        qn = matrix_power(n_val)
        product = matrix_mult(qm, qn)
        expected = matrix_power(m_val + n_val)
        if not matrix_equal(product, expected):
            all_semigroup = False
            registry.add_check(
                family, purpose,
                f"4G: Q^{m_val} · Q^{n_val} = Q^{m_val + n_val}",
                False, "theorem",
            )
            break
    if all_semigroup:
        registry.add_check(
            family, purpose,
            f"4G: Matrix semigroup Q^m·Q^n = Q^(m+n) for tested pairs",
            True, "theorem",
        )

    # ── 4H: Cassini generalization (Catalan's identity) ──
    # F(n)² - F(n-r)·F(n+r) = (-1)^(n-r) · F(r)²
    all_catalan = True
    for n in range(5, 200):
        for r in range(1, min(n, 10)):
            lhs = fibonacci(n) ** 2 - fibonacci(n - r) * fibonacci(n + r)
            expected = (-1) ** (n - r) * fibonacci(r) ** 2
            if lhs != expected:
                all_catalan = False
                break
        if not all_catalan:
            break
    if all_catalan:
        registry.add_check(
            family, purpose,
            "4H: Catalan's identity F(n)² - F(n-r)·F(n+r) = (-1)^(n-r)·F(r)²",
            True, "theorem",
            "Generalization of Cassini's identity",
        )
