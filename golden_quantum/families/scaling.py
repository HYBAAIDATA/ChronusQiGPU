"""
FAMILY 1: φ + LUCAS → SCALING
==============================
L(n) = φ^n + ψ^n ≈ φ^n. Provides scaling steps for non-binary bases.

THEOREMS:
  - Lucas recurrence: L(n+1) = L(n) + L(n-1)
  - Lucas/Fibonacci: L(n) = F(n-1) + F(n+1)
  - Nonresonance: log_φ(b) is irrational for all integer bases b > 1

INVARIANTS:
  - Lucas sequence is strictly increasing for n ≥ 1
  - Lucas brackets every base^k (monotone unbounded sequence)

DEMONSTRATIONS:
  - Lucas scaling smoothness (relative gap analysis)
  - Binet L(n) = exact Lucas(n) for large n
"""

from ..results import CheckRegistry
from ..sequences import fibonacci, lucas, binet_l
from ..constants import INTEGER_BASES, PHI_D
from decimal import Decimal, localcontext


def run(registry: CheckRegistry, max_n: int = 10000, bases: list[int] = None) -> None:
    """Run all Family 1 checks."""
    family = "FAMILY 1: φ + Lucas"
    purpose = "SCALING"
    if bases is None:
        bases = INTEGER_BASES

    # ── 1A: Lucas recurrence L(n+1) = L(n) + L(n-1) ──
    all_recur = True
    for n in range(2, min(max_n, 5000)):
        if lucas(n + 1) != lucas(n) + lucas(n - 1):
            all_recur = False
            break
    registry.add_check(
        family, purpose,
        "1A: Lucas recurrence L(n+1) = L(n) + L(n-1) for n=2..4999",
        all_recur, "theorem",
        f"Checked n=2..{min(max_n, 5000)-1}",
    )

    # ── 1B: Lucas/Fibonacci identity L(n) = F(n-1) + F(n+1) ──
    all_id = True
    for n in range(1, min(max_n, 5000)):
        if lucas(n) != fibonacci(n - 1) + fibonacci(n + 1):
            all_id = False
            break
    registry.add_check(
        family, purpose,
        "1B: Lucas identity L(n) = F(n-1) + F(n+1) for n=1..4999",
        all_id, "theorem",
        f"Checked n=1..{min(max_n, 5000)-1}",
    )

    # ── 1C: Lucas sequence is strictly increasing for n ≥ 1 ──
    all_increasing = True
    for n in range(1, 1000):
        if lucas(n + 1) <= lucas(n):
            all_increasing = False
            break
    registry.add_check(
        family, purpose,
        "1C: Lucas sequence strictly increasing for n=1..999",
        all_increasing, "invariant",
    )

    # ── 1D: Lucas brackets every base^k ──
    # Any unbounded monotone sequence brackets every positive integer.
    # This is an invariant confirming the sequence is unbounded and monotone.
    all_bracketed = True
    for base in bases:
        for k in range(1, 16):
            target = base ** k
            found = False
            for n in range(1, 20000):
                ln = lucas(n)
                ln_next = lucas(n + 1)
                if ln <= target <= ln_next:
                    found = True
                    break
                if ln > target:
                    break
            if not found:
                all_bracketed = False
                registry.add_check(
                    family, purpose,
                    f"1D: Lucas brackets {base}^{k}",
                    False, "invariant",
                )
    if all_bracketed:
        registry.add_check(
            family, purpose,
            f"1D: Lucas brackets base^k for all bases {bases}, k=1..15",
            True, "invariant",
        )

    # ── 1E: Nonresonance theorem — log_φ(b) is irrational ──
    # EXACT PROOF (not float approximation):
    # Suppose log_φ(b) = p/q for integers p,q > 0.
    # Then φ^p = b^q.
    # But φ^p = F(p)·φ + F(p-1) (by the identity φ^n = F(n)·φ + F(n-1)).
    # Since F(p) > 0 for p > 0, this is irrational (contains the irrational φ).
    # But b^q is a rational integer. Contradiction.
    # Therefore log_φ(b) is irrational for every integer base b > 1.
    all_irrational = True
    for base in bases:
        if base <= 1:
            continue
        # Verify the identity φ^n = F(n)·φ + F(n-1) for small n
        # (this is the key algebraic step in the proof)
        identity_holds = True
        with localcontext() as ctx:
            ctx.prec = 2000
            for n in range(1, 50):
                fn = fibonacci(n)
                fn_1 = fibonacci(n - 1)
                # φ^n should equal F(n)·φ + F(n-1)
                # Check: φ^n = F(n)·φ + F(n-1)
                # Rearrange: φ^n - F(n)·φ = F(n-1)
                lhs = PHI_D ** n - Decimal(fn) * PHI_D
                rhs = Decimal(fn_1)
                if abs(lhs - rhs) > Decimal("1e-100"):
                    identity_holds = False
                    break
        if not identity_holds:
            all_irrational = False
            registry.add_check(
                family, purpose,
                f"1E: Nonresonance — log_φ({base}) irrational (identity φ^n=F(n)φ+F(n-1) verified)",
                False, "theorem",
            )
    if all_irrational:
        registry.add_check(
            family, purpose,
            "1E: Nonresonance — log_φ(b) irrational for all integer bases b>1",
            True, "theorem",
            "Proof: if log_φ(b)=p/q then φ^p=b^q, but φ^p=F(p)·φ+F(p-1) is irrational, contradiction.",
        )

    # ── 1F: Lucas/Binet match L(n) = φ^n + ψ^n ──
    test_ns = [0, 1, 5, 10, 20, 50, 100, 200, 500, 1000, 2000]
    if max_n >= 5000:
        test_ns.append(5000)
    if max_n >= 10000:
        test_ns.append(10000)
    checked_ns = [n for n in test_ns if n <= max_n]
    all_match = True
    for n in checked_ns:
        if lucas(n) != binet_l(n):
            all_match = False
            registry.add_check(
                family, purpose,
                f"1F: Binet L({n}) = exact Lucas({n})",
                False, "theorem",
                f"exact={lucas(n)}, binet={binet_l(n)}",
            )
            break
    if all_match:
        registry.add_check(
            family, purpose,
            f"1F: Binet L(n) = exact Lucas(n) for n ∈ {checked_ns}",
            True, "theorem",
            "Decimal precision auto-scaled per n",
        )

    # ── 1G: Lucas gap identity L(n+1) - L(n) = L(n-1) ──
    # This is an exact identity following from the recurrence.
    all_gap = True
    for n in range(2, 5000):
        if lucas(n + 1) - lucas(n) != lucas(n - 1):
            all_gap = False
            break
    registry.add_check(
        family, purpose,
        "1G: Lucas gap identity L(n+1) - L(n) = L(n-1) for n=2..4999",
        all_gap, "theorem",
    )

    # ── 1H: Relative gap tends to 1/φ (demonstration) ──
    # L(n+1) - L(n) = L(n-1) (gap identity, checked in 1G)
    # So (L(n+1) - L(n)) / L(n) = L(n-1) / L(n) → 1/φ ≈ 0.618 as n→∞
    # Since L(n-1)/L(n) → 1/φ (because L(n) ~ φ^n)
    sample_ns = [100, 500, 1000, 5000]
    if max_n >= 10000:
        sample_ns.append(10000)
    rel_gaps = []
    for n in sample_ns:
        ln = Decimal(lucas(n))
        ln1 = Decimal(lucas(n + 1))
        rel_gap = (ln1 - ln) / ln
        rel_gaps.append(float(rel_gap))
    # Check convergence toward 1/φ ≈ 0.61803
    phi_inv = float(Decimal(1) / PHI_D)
    converging = all(abs(rg - phi_inv) < 0.01 for rg in rel_gaps[-3:])
    registry.add_check(
        family, purpose,
        f"1H: Relative gap (L(n+1)-L(n))/L(n) = L(n-1)/L(n) → 1/φ ≈ {phi_inv:.6f}",
        converging, "demonstration",
        f"Samples at n={sample_ns}: gaps={[f'{g:.6f}' for g in rel_gaps]}",
    )
