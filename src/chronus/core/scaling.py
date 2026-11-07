"""The universal scaling operator: Lucas/PV scales everything.

PVScale is the single canonical scaling primitive of the substrate. Any
subsystem — storage lineage, execution factors, search strides — scales by
advancing an exact Pisot-Vijayaraghavan index, not by materializing
coefficients. The conjugate contraction |psi| = 1/phi < 1 is what makes the
index an exact anchor: the trace L_n = phi^n + psi^n is an integer at every
order, and the index composes by addition.

Materialization (phi^index coefficients) happens only at a consumer boundary
that explicitly requests it.
"""

from dataclasses import dataclass

from chronus.backends.lattice import PhiElement, phi_power
from chronus.backends.metallic import metallic_power, metallic_sequence
from chronus.config import runtime_bounds


@dataclass(frozen=True)
class PVScale:
    """An exact PV scale index; the substrate's unit of scaling."""

    index: int = 0
    m: int = 1  # metallic family; m=1 is the golden/Lucas anchor

    def __post_init__(self) -> None:
        max_index = runtime_bounds()["max_trinity_index"]
        if not isinstance(self.index, int) or isinstance(self.index, bool) \
                or not 0 <= self.index <= max_index:
            raise ValueError(f"index must be an integer in [0, {max_index}]")
        if not isinstance(self.m, int) or isinstance(self.m, bool) or self.m < 1:
            raise ValueError("m must be a positive integer")

    def advance(self, increment: int) -> "PVScale":
        """Scale further by index addition; no coefficients are materialized."""
        return PVScale(self.index + increment, self.m)

    def trace(self) -> int:
        """The exact integer anchor T_index = sigma_m^index + psi_m^index."""
        return metallic_sequence(self.m, self.index)

    def cassini_parity(self) -> int:
        """(-1)^index: the determinant sign of the companion matrix."""
        return -1 if self.index % 2 else 1

    def factor(self) -> PhiElement:
        """Materialize phi^index (m must be 1); only at a consumer boundary."""
        if self.m != 1:
            raise ValueError("factor() materializes the golden anchor; use metallic_power for m > 1")
        return phi_power(self.index)

    def metallic_factor(self) -> "object":
        """Materialize sigma_m^index as exact coefficients."""
        return metallic_power(self.m, self.index)
