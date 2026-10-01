# l_hras/substrate/phi_rotation.py

import numpy as np
from dataclasses import dataclass
from typing import List, Tuple

PHI = (1 + np.sqrt(5)) / 2
PSI = (1 - np.sqrt(5)) / 2  # conjugate

@dataclass(frozen=True)
class ZPhi:
    """An element of Z[φ]: a + b·φ."""
    a: int
    b: int

    def __add__(self, other: 'ZPhi') -> 'ZPhi':
        return ZPhi(self.a + other.a, self.b + other.b)

    def __mul__(self, other: 'ZPhi') -> 'ZPhi':
        # (a + bφ)(c + dφ) = (ac + bd) + (ad + bc + bd)φ
        return ZPhi(
            self.a * other.a + self.b * other.b,
            self.a * other.b + self.b * other.a + self.b * other.b,
        )

    def conjugate(self) -> 'ZPhi':
        return ZPhi(self.a + self.b, -self.b)

    def norm(self) -> int:
        return self.a * self.a + self.a * self.b - self.b * self.b

    def trace(self) -> int:
        return 2 * self.a + self.b

# Constants
PHI_ELEMENT = ZPhi(0, 1)
PSI_ELEMENT = ZPhi(1, -1)

# Rotation matrix R = [[0, 1], [1, 1]]
R_MATRIX = np.array([[0, 1], [1, 1]], dtype=int)

def rotate_n(n: int) -> np.ndarray:
    """R^n via matrix exponentiation."""
    if n == 0:
        return np.eye(2, dtype=int)
    if n == 1:
        return R_MATRIX
    if n % 2 == 0:
        half = rotate_n(n // 2)
        return half @ half
    return R_MATRIX @ rotate_n(n - 1)

# Invariants

def run_invariants() -> None:
    """Execute the blueprint assertions; failures are evidence."""
    assert round(float(np.linalg.det(R_MATRIX))) == -1
    assert np.trace(R_MATRIX) == 1
    assert (PHI_ELEMENT * PHI_ELEMENT) == PHI_ELEMENT + ZPhi(1, 0)
    assert PHI_ELEMENT.norm() == -1
    assert PHI_ELEMENT.trace() == 1
