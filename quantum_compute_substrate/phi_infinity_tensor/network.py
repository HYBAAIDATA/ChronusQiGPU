"""Matrix-product-state (MPS) representation with configurable bond dimension.

An MPS with rank sites, physical dim N per site, and bond dim chi uses
    memory ~ rank * chi^2 * N
which is a compression of chi^2 / N^{rank-1} relative to the full tensor.

For phi^37 sites and bond chi = phi^k, we get astronomical compression while
keeping the entire tensor structure representable.
"""
from __future__ import annotations
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class MPSNetwork:
    physical_dim: int
    rank: int          # number of tensor legs (sites)
    bond_dim: int      # bond dimension chi

    def __post_init__(self) -> None:
        if self.physical_dim < 2:
            raise ValueError("physical_dim must be >= 2")
        if self.rank < 2:
            raise ValueError("rank must be >= 2")
        if self.bond_dim < 1:
            raise ValueError("bond_dim must be >= 1")

    def memory_bytes(self, bytes_per_element: int = 16) -> int:
        """Storage for the MPS as a whole.
        End sites have shape (physical_dim, bond_dim); interior sites
        (bond_dim, physical_dim, bond_dim). Total scalars ~ rank * chi^2 * N.
        """
        interior = max(0, self.rank - 2)
        end_scalars = 2 * (self.physical_dim * self.bond_dim)
        interior_scalars = interior * (self.bond_dim ** 2) * self.physical_dim
        return (end_scalars + interior_scalars) * bytes_per_element

    def compression_ratio(self) -> float:
        """MPS storage / full tensor storage. Ratio << 1 for chi << N^{(rank-1)/2}.
        Returned in log10 to avoid underflow for astronomical full sizes.
        """
        log_full = self.rank * math.log10(self.physical_dim)
        log_mps = math.log10(self.memory_bytes() / 16)
        return log_mps - log_full  # log10 of ratio; negative = compression

    def compression_log10(self) -> float:
        """Alias for compression_ratio (already in log10)."""
        return self.compression_ratio()

    def sites(self) -> int:
        return self.rank

    def bond_hierarchy(self) -> list:
        """Bond dims across the chain: constant chi for uniform MPS."""
        return [self.bond_dim] * (self.rank - 1)

    def represents_pure_state(self) -> bool:
        return True

    def description(self) -> dict:
        return {
            "type": "MPS",
            "physical_dim": self.physical_dim,
            "rank": self.rank,
            "bond_dim": self.bond_dim,
            "log10_compression_ratio": self.compression_ratio(),
            "memory_bytes": self.memory_bytes(),
        }
