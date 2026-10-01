"""The six named axes of the tensor."""
from __future__ import annotations
from dataclasses import dataclass
from decimal import Decimal
from typing import Tuple
from .phi_identities import lucas


@dataclass(frozen=True)
class TensorDimension:
    name: str
    size: int              # length along this axis
    scaling_exp: int       # this axis carries phi^scaling_exp scale
    physical_meaning: str

    def log10_size(self) -> Decimal:
        return Decimal(self.size).ln() / Decimal(10).ln()


AXIS_NAMES: Tuple[str, ...] = (
    "Time", "Space", "QuantumState", "Entanglement", "Coherence", "Topology",
)

AXIS_MEANINGS: Tuple[str, ...] = (
    "Temporal evolution",
    "Spatial configuration",
    "Amplitude distribution",
    "Quantum correlations",
    "Phase relationships",
    "Invariant structure",
)


def default_dimensions(scaling_exp: int = 37) -> Tuple[TensorDimension, ...]:
    """Six dimensions each of size L(scaling_exp) = round(phi^scaling_exp)."""
    size = lucas(scaling_exp)
    return tuple(
        TensorDimension(name=n, size=size, scaling_exp=scaling_exp, physical_meaning=m)
        for n, m in zip(AXIS_NAMES, AXIS_MEANINGS)
    )
