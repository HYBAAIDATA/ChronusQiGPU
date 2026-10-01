# l_hras/substrate/cassini.py

from l_hras.experimental.blueprint.substrate.lucas import lucas

def cassini(n: int) -> int:
    """Cassini: L_{n-1}·L_{n+1} − L_n² = 5·(−1)^n."""
    return lucas(n - 1) * lucas(n + 1) - lucas(n) ** 2

# The supplied sign was reversed. For Lucas numbers the identity is
# L_(n-1)L_(n+1)-L_n^2 = 5(-1)^(n+1).
def run_invariants() -> None:
    for n in range(1, 20):
        assert cassini(n) == 5 * ((-1) ** (n + 1)), f"Cassini failed at n={n}"
