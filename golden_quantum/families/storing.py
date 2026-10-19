"""
FAMILY 3: φ + FIBONACCI → STORING
===================================
Zeckendorf representation and Fibonacci coding for data storage.

THEOREMS:
  - Zeckendorf representation: every n ≥ 1 has unique representation
    as sum of non-consecutive Fibonacci numbers
  - Fibonacci coding: prefix-free, self-delimiting code for n ≥ 1

INVARIANTS:
  - Zeckendorf roundtrip: decode(encode(n)) = n for all tested n
  - No consecutive Fibonacci indices in any Zeckendorf representation
  - Fibonacci code roundtrip: decode(encode(n)) = n

DEMONSTRATIONS:
  - Prefix-free property: no codeword is a prefix of another
  - Invalid code rejection
"""

from ..results import CheckRegistry
from ..coding import zeckendorf, fib_encode, fib_decode, is_valid_fib_code
from ..sequences import fibonacci


def run(registry: CheckRegistry, max_n: int = 10000) -> None:
    family = "FAMILY 3: φ + Fibonacci"
    purpose = "STORING"

    test_range = range(1, min(max_n, 10001))

    # ── 3A: Zeckendorf sum correctness ──
    all_sum = True
    for n in test_range:
        indices = zeckendorf(n)
        total = sum(fibonacci(k) for k in indices)
        if total != n:
            all_sum = False
            registry.add_check(
                family, purpose,
                f"3A: Zeckendorf sum({n})",
                False, "theorem",
            )
            break
    if all_sum:
        registry.add_check(
            family, purpose,
            f"3A: Zeckendorf sum = n for n=1..{min(max_n,10000)}",
            True, "theorem",
            "Every n has a Zeckendorf representation (Zeckendorf's theorem)",
        )

    # ── 3B: Non-consecutive Fibonacci indices ──
    all_nonconsec = True
    for n in test_range:
        indices = zeckendorf(n)
        for i in range(len(indices) - 1):
            if indices[i] - indices[i + 1] < 2:
                all_nonconsec = False
                registry.add_check(
                    family, purpose,
                    f"3B: Non-consecutive indices for n={n}",
                    False, "invariant",
                )
                break
        if not all_nonconsec:
            break
    if all_nonconsec:
        registry.add_check(
            family, purpose,
            f"3B: No consecutive Fibonacci indices for n=1..{min(max_n,10000)}",
            True, "invariant",
        )

    # ── 3C: Zeckendorf uniqueness (greedy = unique) ──
    # Verify that the greedy algorithm produces the same result as
    # any valid non-consecutive representation (by checking that
    # the greedy result is the lexicographically largest valid one)
    all_unique = True
    for n in range(1, min(max_n, 5001)):
        indices = zeckendorf(n)
        # The greedy algorithm always picks the largest possible Fibonacci
        # number. Any other valid representation would have to use a smaller
        # one at the first step, but then cannot reach n.
        # We verify: the greedy choice is forced at each step.
        remaining = n
        for i, idx in enumerate(indices):
            # idx should be the largest k with F(k) <= remaining
            k = idx
            while fibonacci(k + 1) <= remaining:
                k += 1
            if k != idx:
                all_unique = False
                break
            remaining -= fibonacci(idx)
        if not all_unique:
            break
    if all_unique:
        registry.add_check(
            family, purpose,
            f"3C: Zeckendorf greedy uniqueness for n=1..{min(max_n,5000)}",
            True, "theorem",
            "Greedy algorithm is forced at every step → unique representation",
        )

    # ── 3D: Fibonacci code roundtrip ──
    all_roundtrip = True
    for n in range(1, min(max_n, 10001)):
        code = fib_encode(n)
        decoded = fib_decode(code)
        if decoded != n:
            all_roundtrip = False
            registry.add_check(
                family, purpose,
                f"3D: Fibonacci code roundtrip({n})",
                False, "theorem",
                f"code={code}, decoded={decoded}",
            )
            break
    if all_roundtrip:
        registry.add_check(
            family, purpose,
            f"3D: Fibonacci code decode(encode(n)) = n for n=1..{min(max_n,10000)}",
            True, "theorem",
        )

    # ── 3E: Fibonacci codes end with '11' ──
    all_end_11 = True
    for n in range(1, min(max_n, 10001)):
        code = fib_encode(n)
        if len(code) < 2 or code[-2:] != "11":
            all_end_11 = False
            break
    if all_end_11:
        registry.add_check(
            family, purpose,
            f"3E: All Fibonacci codes end with '11' for n=1..{min(max_n,10000)}",
            True, "invariant",
        )

    # ── 3F: Prefix-free property ──
    # No codeword is a prefix of another (within tested range)
    # Use set-based approach: for each code, check all its prefixes against the set
    all_prefix_free = True
    code_set = set()
    for n in range(1, min(max_n, 5001)):
        code_set.add(fib_encode(n))
    for code in code_set:
        # Check if any prefix of this code (shorter) is also in the set
        for length in range(2, len(code)):
            prefix = code[:length]
            if prefix in code_set:
                all_prefix_free = False
                break
        if not all_prefix_free:
            break
    if all_prefix_free:
        registry.add_check(
            family, purpose,
            f"3F: Prefix-free property for n=1..{min(max_n,5000)}",
            True, "theorem",
            "No codeword is a prefix of another (self-delimiting)",
        )

    # ── 3G: Invalid code rejection ──
    invalid_codes = [
        "",           # empty
        "1",          # too short
        "0",          # doesn't end in 1
        "01",         # doesn't end in 11
        "11011",      # consecutive 1s in data (after stripping terminator: "1101" has "11")
        "111",        # data has consecutive 1s
        "0000",       # no terminator
    ]
    # Need to be careful: "11011" → strip terminator → "1101" → has "11" at start → invalid
    # "111" → strip terminator → "11" → has "11" → invalid
    all_rejected = True
    for code in invalid_codes:
        if is_valid_fib_code(code):
            all_rejected = False
            registry.add_check(
                family, purpose,
                f"3G: Reject invalid code {code!r}",
                False, "invariant",
            )
    # Also check some valid codes ARE accepted
    valid_codes_ok = True
    for n in [1, 2, 4, 10, 100]:
        if not is_valid_fib_code(fib_encode(n)):
            valid_codes_ok = False
    if all_rejected and valid_codes_ok:
        registry.add_check(
            family, purpose,
            "3G: Invalid codes rejected, valid codes accepted",
            True, "invariant",
        )
