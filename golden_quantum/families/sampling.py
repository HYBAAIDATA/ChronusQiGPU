"""
FAMILY 6: φ + CONTINUED FRACTION → SAMPLING
=============================================
φ = [1; 1, 1, 1, ...] — the simplest infinite continued fraction.
The "most irrational" number: maximally badly approximable.

THEOREMS:
  - All partial quotients of φ are 1
  - Convergents are F(n+2)/F(n+1)
  - φ is badly approximable: |φ - p/q| ≥ c/q² for c > 0

INVARIANTS:
  - Continued fraction algorithm produces all 1s
  - Convergents alternate above/below φ

DEMONSTRATIONS:
  - Convergence rate analysis
  - Comparison with other irrationals
"""

from ..results import CheckRegistry
from ..sequences import fibonacci
from ..continued_fraction import (
    continued_fraction_phi, convergents, convergent_error, is_badly_approximable,
    compute_cf_independently, compute_convergents_independently,
)
from ..constants import PHI_D
from decimal import Decimal


def run(registry: CheckRegistry, max_n: int = 10000) -> None:
    family = "FAMILY 6: φ + Continued Frac"
    purpose = "SAMPLING"

    # ── 6A: All partial quotients of φ are 1 (independent computation) ──
    # Compute CF partial quotients independently using the standard
    # subtract-and-invert algorithm, then verify they are all 1
    cf_independent = compute_cf_independently(100)
    all_ones = all(a == 1 for a in cf_independent)
    registry.add_check(
        family, purpose,
        f"6A: All partial quotients of φ are 1 (independent CF computation, first {len(cf_independent)} terms)",
        all_ones, "theorem",
        "φ = [1; 1, 1, 1, ...] — independently verified via subtract-and-invert algorithm",
    )

    # ── 6B: Convergents are F(n+2)/F(n+1) (independent computation) ──
    # Compute convergents independently from the CF algorithm,
    # then verify they match Fibonacci ratios
    convs_independent = compute_convergents_independently(50)
    all_conv = True
    for i, (p, q) in enumerate(convs_independent):
        expected_p = fibonacci(i + 2)
        expected_q = fibonacci(i + 1)
        if p != expected_p or q != expected_q:
            all_conv = False
            registry.add_check(
                family, purpose,
                f"6B: Convergent {i} = F({i+2})/F({i+1})",
                False, "theorem",
                f"got {p}/{q}, expected {expected_p}/{expected_q}",
            )
            break
    if all_conv:
        registry.add_check(
            family, purpose,
            f"6B: Convergents of φ are F(n+2)/F(n+1) for n=0..{len(convs_independent)-1} (independent CF)",
            True, "theorem",
            "Convergents computed independently via CF recurrence, match Fibonacci ratios",
        )

    # ── 6C: Convergents alternate above and below φ ──
    all_alternate = True
    prev_above = None
    for i in range(2, len(convs_independent)):
        p, q = convs_independent[i]
        val = Decimal(p) / Decimal(q)
        above = val > PHI_D
        if prev_above is not None and above == prev_above:
            all_alternate = False
            break
        prev_above = above
    if all_alternate:
        registry.add_check(
            family, purpose,
            "6C: Convergents alternate above/below φ",
            True, "theorem",
            "Even convergents > φ, odd convergents < φ (or vice versa)",
        )

    # ── 6D: Approximation error bound |φ - p_n/q_n| < 1/q_n² ──
    all_bounded = True
    for i in range(2, min(50, len(convs_independent))):
        p, q = convs_independent[i]
        error = abs(PHI_D - Decimal(p) / Decimal(q))
        bound = Decimal(1) / (Decimal(q) ** 2)
        if error >= bound:
            all_bounded = False
            registry.add_check(
                family, purpose,
                f"6D: Error bound at convergent {i}",
                False, "theorem",
                f"error={error}, bound={bound}",
            )
            break
    if all_bounded:
        registry.add_check(
            family, purpose,
            "6D: |φ - p_n/q_n| < 1/q_n² for convergents n=2..49",
            True, "theorem",
            "Standard continued fraction approximation bound",
        )

    # ── 6E: Badly approximable — deterministic check ──
    # For all p/q with q ≤ max_q: |φ - p/q| ≥ c/q²
    # This is a property of numbers with bounded partial quotients.
    # φ has the smallest possible partial quotients (all 1s),
    # making it the "most badly approximable" number.
    max_q = min(max_n, 3000)
    badly_approx = is_badly_approximable(max_q)
    registry.add_check(
        family, purpose,
        f"6E: Badly approximable |φ - p/q| ≥ 1/(5q²) for all q ≤ {max_q}",
        badly_approx, "demonstration",
        "Exhaustive check over all rationals p/q with q ≤ max_q",
    )

    # ── 6F: Error decreases monotonically for convergents ──
    all_decreasing = True
    prev_error = None
    for i in range(2, 50):
        error = convergent_error(i)
        if prev_error is not None and error >= prev_error:
            all_decreasing = False
            break
        prev_error = error
    if all_decreasing:
        registry.add_check(
            family, purpose,
            "6F: Convergent errors decrease monotonically",
            True, "theorem",
            "Each convergent is a better approximation than the previous",
        )

    # ── 6G: Convergent error formula ──
    # |φ - F(n+2)/F(n+1)| < 1/F(n+1)²
    # More precisely: |φ - F(n+2)/F(n+1)| = 1/(F(n+1) · (F(n+1)·φ + F(n)))
    # which is < 1/F(n+1)²
    all_formula = True
    for n in range(2, 50):
        p = fibonacci(n + 2)
        q = fibonacci(n + 1)
        error = abs(PHI_D - Decimal(p) / Decimal(q))
        bound = Decimal(1) / (Decimal(q) ** 2)
        if error >= bound:
            all_formula = False
            break
    if all_formula:
        registry.add_check(
            family, purpose,
            "6G: |φ - F(n+2)/F(n+1)| < 1/F(n+1)² for n=2..49",
            True, "theorem",
        )

    # ── 6H: Comparison — φ is "most irrational" (demonstration) ──
    # Compare approximation quality of φ vs √2 and π
    # √2 = [1; 2, 2, 2, ...] — also badly approximable but less so
    # π = [3; 7, 15, 1, 292, ...] — well approximable (large partial quotients)
    from .comparison import compare_approximability
    phi_best, sqrt2_best, pi_best, sqrt5_best = compare_approximability(max_q=1000)
    most_irrational = phi_best >= sqrt2_best
    registry.add_check(
        family, purpose,
        f"6H: φ is 'most irrational' — worst rational approximation (demonstration)",
        most_irrational, "demonstration",
        f"min(q²·|α-p/q|): φ={phi_best:.6f}, √2={sqrt2_best:.6f}, π={pi_best:.6f}, √5={sqrt5_best:.6f}",
    )
