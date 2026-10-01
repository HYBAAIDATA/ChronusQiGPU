"""Arithmetic intensity — FLOPs per byte, division guarded.

Invariants:
    AI1: intensity is FLOPs per byte.
    AI2: bytes transferred is not zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class ArithmeticIntensity:
    flops: int
    bytes_transferred: int
    intensity: float

    def as_dict(self) -> Dict[str, Any]:
        return {
            "flops": self.flops,
            "bytes_transferred": self.bytes_transferred,
            "intensity": self.intensity,
        }


def compute_intensity(flops: int, bytes_transferred: int) -> ArithmeticIntensity:
    if not bytes_transferred:
        raise ValueError("arithmetic intensity needs nonzero bytes transferred")
    return ArithmeticIntensity(
        flops=int(flops),
        bytes_transferred=int(bytes_transferred),
        intensity=float(flops) / float(bytes_transferred),
    )
