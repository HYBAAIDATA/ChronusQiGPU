"""R = [[0,1],[1,1]] ∈ GL(2,Z). det(R) = -1, trace(R) = 1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class Mat2:
    m00: int
    m01: int
    m10: int
    m11: int

    def det(self) -> int:
        return self.m00 * self.m11 - self.m01 * self.m10

    def trace(self) -> int:
        return self.m00 + self.m11

    def mul(self, other: "Mat2") -> "Mat2":
        return Mat2(
            self.m00 * other.m00 + self.m01 * other.m10,
            self.m00 * other.m01 + self.m01 * other.m11,
            self.m10 * other.m00 + self.m11 * other.m10,
            self.m10 * other.m01 + self.m11 * other.m11,
        )

    def apply(self, x: float, y: float) -> Tuple[float, float]:
        nx = self.m00 * x + self.m01 * y
        ny = self.m10 * x + self.m11 * y
        return nx - int(nx), ny - int(ny)


IDENTITY = Mat2(1, 0, 0, 1)
R = Mat2(0, 1, 1, 1)


def rotate_n(n: int) -> Mat2:
    if n == 0:
        return IDENTITY
    if n < 0:
        raise ValueError("n >= 0")
    acc = IDENTITY
    base = R
    k = n
    while k:
        if k & 1:
            acc = acc.mul(base)
        base = base.mul(base)
        k >>= 1
    return acc
