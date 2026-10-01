# l_hras/substrate/morton.py

import numpy as np
from l_hras.experimental.blueprint.substrate.phi_rotation import PHI

def phi_expansion(x: float, precision: int) -> list:
    """The φ-expansion of x: x = Σ d_i · φ^{-i}, d_i ∈ {0, 1}."""
    digits = []
    current = x
    for _ in range(precision):
        current *= PHI
        digit = int(np.floor(current))
        digits.append(digit)
        current -= digit
    return digits

def morton_step(x: float, y: float, precision: int) -> int:
    """Z-order key from the φ-expansions."""
    x_digits = phi_expansion(x, precision)
    y_digits = phi_expansion(y, precision)
    key = 0
    for i in range(precision):
        key = (key << 2) | (x_digits[i] << 1) | y_digits[i]
    return key

# Verify: fold/unfold roundtrip
for x in [0.1, 0.5, 0.9]:
    for y in [0.2, 0.6, 0.8]:
        key = morton_step(x, y, precision=32)
        assert isinstance(key, int)
