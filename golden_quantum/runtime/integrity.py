"""
Cassini integrity validation for unknown 2×2 integer matrices.

Given an arbitrary 2×2 integer matrix, determine whether it is a valid
M_φ^n state (the n-th power of the Fibonacci Q-matrix Q = [[1,1],[1,0]]).

Properties of Q^n = [[F(n+1), F(n)], [F(n), F(n-1)]]:
  - Symmetric: m[0][1] == m[1][0]
  - Structural: m[0][0] - m[1][1] == m[0][1]  (since F(n+1) - F(n-1) = F(n))
  - Determinant: det = (-1)^n  (Cassini's identity)
  - Non-negative entries for n >= 0

The validator checks structural properties and attempts to recover n.
"""

from ..sequences import fibonacci, fib_pair


def is_valid_mphi_matrix(m: list[list[int]]) -> bool:
    """Check whether m is a valid Q^n = M_φ^n matrix for some n >= 0.

    Validates:
      1. Shape is 2×2
      2. Symmetric (m[0][1] == m[1][0])
      3. Structural property: m[0][0] - m[1][1] == m[0][1]
      4. Determinant is ±1 (Cassini invariant)
      5. Non-negative entries (canonical form for n >= 0)

    Returns True only if ALL checks pass.
    """
    # Shape check
    if len(m) != 2 or len(m[0]) != 2 or len(m[1]) != 2:
        return False

    a, b = m[0][0], m[0][1]
    c, d = m[1][0], m[1][1]

    # Symmetry
    if b != c:
        return False

    # Structural: F(n+1) - F(n-1) = F(n), so a - d = b
    if a - d != b:
        return False

    # Determinant must be ±1
    det = a * d - b * c
    if det not in (-1, 1):
        return False

    # Non-negative entries for canonical n >= 0
    if a < 0 or b < 0 or c < 0 or d < 0:
        return False

    return True


def recover_exponent(m: list[list[int]]) -> int | None:
    """Attempt to recover n such that m = Q^n.

    Uses the fact that m[0][1] = F(n) to find candidate n values,
    then verifies the full matrix matches.

    Handles the ambiguity F(1) = F(2) = 1 by checking both.

    Returns n if found, None if m is not a valid M_φ^n.
    """
    if not is_valid_mphi_matrix(m):
        return None

    b = m[0][1]  # This should be F(n)

    # Find all n where F(n) == b
    candidates = []
    if b == 0:
        candidates = [0]  # F(0) = 0, but Q^0 = I = [[1,0],[0,1]], b=0
    elif b == 1:
        candidates = [1, 2]  # F(1) = F(2) = 1
    else:
        # Search for n where F(n) == b
        n = 2
        while fibonacci(n) <= b:
            if fibonacci(n) == b:
                candidates.append(n)
            n += 1

    # Verify each candidate
    for n in candidates:
        if matrix_power(n) == m:
            return n

    return None


def matrix_power(n: int) -> list[list[int]]:
    """Q^n = [[F(n+1), F(n)], [F(n), F(n-1)]]. Local import to avoid circular deps."""
    fn, fn1 = fib_pair(n)
    fn_1 = fn1 - fn
    return [[fn1, fn], [fn, fn_1]]
