"""The tensor itself -- implicit, never materialized."""
from __future__ import annotations
import math
from typing import Sequence, Tuple, Optional
from .dimensions import TensorDimension, default_dimensions, AXIS_NAMES
from .generator import PhiCharacterRule
from .network import MPSNetwork


class HYBAQuantumTensorXInfinity:
    """Rank-6 implicit tensor with each axis of length L(scaling_exp).

    Default: scaling_exp = 37 -> per-axis length = 54,018,521 = round(phi^37).
    Total elements: L(37)^6 (exact bigint).

    Never materialized. Elements are computed lazily via generative rules.
    """

    def __init__(self, scaling_exp: int = 37,
                 rule: Optional[PhiCharacterRule] = None,
                 mps_bond_dim: int = 128) -> None:
        if scaling_exp < 2:
            raise ValueError("scaling_exp must be >= 2")
        self.scaling_exp = scaling_exp
        self.dimensions: Tuple[TensorDimension, ...] = default_dimensions(scaling_exp)
        self._per_axis = self.dimensions[0].size
        self.rule = rule or PhiCharacterRule(N=self._per_axis, rank=len(self.dimensions))
        self.mps = MPSNetwork(physical_dim=self._per_axis,
                              rank=len(self.dimensions),
                              bond_dim=mps_bond_dim)

    # ---- shape / rank ----
    @property
    def rank(self) -> int:
        return len(self.dimensions)

    @property
    def shape(self) -> Tuple[int, ...]:
        return tuple(d.size for d in self.dimensions)

    def total_elements(self) -> int:
        """Exact bigint: L(scaling_exp)^rank."""
        return self._per_axis ** self.rank

    def log10_elements(self) -> float:
        return self.rank * math.log10(self._per_axis)

    # ---- element access (O(rank)) ----
    def __getitem__(self, indices: Sequence[int]) -> complex:
        idx = tuple(indices)
        if len(idx) != self.rank:
            raise IndexError(f"expected {self.rank} indices")
        return self.rule.element(idx)

    def get(self, *indices: int) -> complex:
        return self.__getitem__(indices)

    # ---- memory (would-be, if materialized) ----
    def memory_bytes_if_materialized(self, bytes_per_element: int = 16) -> int:
        return self.total_elements() * bytes_per_element

    def memory_bytes_actual(self) -> int:
        """Actual storage of the substrate representation (MPS)."""
        return self.mps.memory_bytes()

    def compression_log10(self) -> float:
        """log10(actual bytes / materialized bytes). Negative = compressed."""
        return math.log10(self.memory_bytes_actual() / self.memory_bytes_if_materialized())

    # ---- description ----
    def describe(self) -> dict:
        return {
            "name": "HYBA Quantum Tensor X-Infinity",
            "scaling_exp": self.scaling_exp,
            "rank": self.rank,
            "shape": self.shape,
            "axis_names": AXIS_NAMES,
            "per_axis": self._per_axis,
            "total_elements": self.total_elements(),
            "log10_elements": self.log10_elements(),
            "memory_if_materialized_bytes": self.memory_bytes_if_materialized(),
            "memory_actual_bytes": self.memory_bytes_actual(),
            "compression_log10": self.compression_log10(),
            "mps_bond_dim": self.mps.bond_dim,
            "rule": type(self.rule).__name__,
        }

    def to_string(self) -> str:
        d = self.describe()
        lines = [
            "=" * 78,
            "HYBA QUANTUM TENSOR X-INFINITY",
            "Implicit rank-6 tensor at phi^{exp} scale".format(exp=self.scaling_exp),
            "=" * 78,
            f"Rank:            {d['rank']}",
            f"Shape:           {d['shape']}",
            f"Per axis (L({self.scaling_exp})): {d['per_axis']:,}",
            f"Total elements:  L({self.scaling_exp})^{self.rank} = {d['total_elements']:.3e}",
            f"log10 elements:  {d['log10_elements']:.4f}",
            "",
            f"Materialized:    {d['memory_if_materialized_bytes']:.3e} bytes",
            f"                 ({d['memory_if_materialized_bytes'] / 1e24:.3e} yottabytes)",
            f"Substrate (MPS): {d['memory_actual_bytes']:,} bytes with bond={d['mps_bond_dim']}",
            f"Compression:     10^{d['compression_log10']:.2f} (negative = compressed)",
            "",
            "Rule:            " + d["rule"],
            "=" * 78,
        ]
        return chr(10).join(lines)


def make_default_tensor() -> HYBAQuantumTensorXInfinity:
    return HYBAQuantumTensorXInfinity(scaling_exp=37, mps_bond_dim=128)
