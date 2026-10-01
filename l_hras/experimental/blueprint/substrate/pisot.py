# l_hras/substrate/pisot.py

import numpy as np
from l_hras.experimental.blueprint.substrate.phi_rotation import PHI, PSI

def is_pisot(alpha: complex, conjugate: complex) -> bool:
    """Pisot: alpha > 1, |conjugate| < 1."""
    return abs(alpha) > 1 and abs(conjugate) < 1

def pisot_decay(n: int) -> float:
    """|ψ|^n → 0."""
    return abs(PSI) ** n

# The supplied bound cannot hold at n=1. Test monotonic decay and the
# asymptotic threshold at n=100 instead.
def run_invariants() -> None:
    assert is_pisot(PHI, PSI)
    values = [pisot_decay(n) for n in range(1, 101)]
    assert all(a > b for a, b in zip(values, values[1:]))
    assert values[-1] < 1e-10
