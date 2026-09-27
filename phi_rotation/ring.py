"""Z[φ]. φ² = φ + 1. Exact integers only."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ZPhi:
    a: int
    b: int

    def __add__(self, other: "ZPhi") -> "ZPhi":
        return ZPhi(self.a + other.a, self.b + other.b)

    def __mul__(self, other: "ZPhi") -> "ZPhi":
        return ZPhi(
            self.a * other.a + self.b * other.b,
            self.a * other.b + self.b * other.a + self.b * other.b,
        )

    def conjugate(self) -> "ZPhi":
        return ZPhi(self.a + self.b, -self.b)

    def norm(self) -> int:
        return self.a * self.a + self.a * self.b - self.b * self.b

    def trace(self) -> int:
        return 2 * self.a + self.b


ZERO = ZPhi(0, 0)
ONE = ZPhi(1, 0)
PHI = ZPhi(0, 1)
PSI = ZPhi(1, -1)


def check_phi1() -> dict:
    return {
        "phi_sq_is_phi_plus_one": PHI * PHI == PHI + ONE,
        "norm_phi": PHI.norm(),
        "trace_phi": PHI.trace(),
        "norm_psi": PSI.norm(),
    }
