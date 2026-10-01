# l_hras/substrate/lucas.py

from l_hras.experimental.blueprint.substrate.phi_rotation import PHI, PSI

def lucas(n: int) -> int:
    """L_n = trace(R^n) = φ^n + ψ^n."""
    if n == 0: return 2
    if n == 1: return 1
    a, b = 2, 1
    for _ in range(n - 1):
        a, b = b, a + b
    return b

def lucas_fast_doubling(n: int) -> int:
    """Fast doubling: O(log n)."""
    if n == 0: return 2
    if n == 1: return 1
    # Matrix exponentiation for Lucas
    def fib_pair(n):
        if n == 0: return (0, 1)
        a, b = fib_pair(n >> 1)
        c = a * (2 * b - a)
        d = a * a + b * b
        if n & 1:
            return (d, c + d)
        return (c, d)
    return 2 * fib_pair(n - 1)[0] + fib_pair(n - 1)[1]

# Verify
for n in range(20):
    assert lucas(n) == lucas_fast_doubling(n), f"mismatch at n={n}"
