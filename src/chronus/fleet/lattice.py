# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""The resident virtual-unit scheduling lattice (80, 800 or 8,000 virtual units).

A virtual unit is a logical tile slot in a scheduling lattice. It is not a
physical core, die or GPU lane: 8,000 virtual units means a work unit may be
striped into at most 8,000 tiles, which the fleet then leases to whatever real
silicon has joined. The striping itself is the repository's existing
``ResidentLogicalScheduler`` (``chronus.execution.native_simd``): tiles are
disjoint, contiguous, cover every item exactly once and hold at least one
warp's worth (32) of items unless the work unit is smaller than that.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from chronus.fleet.errors import LatticeError
from chronus.fleet.phase import WARP_LANES, lattice_footprint

RESIDENT_RUNGS = (80, 800, 8000)
DEFAULT_VIRTUAL_UNITS = 8000
LATTICE_LABEL = "scheduling lattice: logical virtual units, not physical cores"


def require_rung(virtual_units: Any) -> int:
    if virtual_units not in RESIDENT_RUNGS or isinstance(virtual_units, bool):
        raise LatticeError(
            f"virtual_units must be one of {RESIDENT_RUNGS} (a scheduling lattice rung), not {virtual_units!r}"
        )
    return int(virtual_units)


def resident_config(virtual_units: int = DEFAULT_VIRTUAL_UNITS):
    """The repository's ResidentConfig, restricted to the three resident rungs."""
    from chronus.execution.native_simd import ResidentConfig

    return ResidentConfig(virtual_units=require_rung(virtual_units))


@dataclass(frozen=True)
class Tile:
    """Items [start, stop) of a work unit, assigned to one virtual unit."""

    index: int
    start: int
    stop: int

    @property
    def items(self) -> int:
        return self.stop - self.start


class SchedulingLattice:
    """Stripes bounded work across the logical tiles of a resident rung."""

    label = LATTICE_LABEL

    def __init__(self, virtual_units: int = DEFAULT_VIRTUAL_UNITS) -> None:
        from chronus.execution.native_simd import ResidentLogicalScheduler

        self.config = resident_config(virtual_units)
        self._scheduler = ResidentLogicalScheduler(self.config)

    @property
    def virtual_units(self) -> int:
        return self.config.virtual_units

    def plan(self, item_count: int) -> list[Tile]:
        if not isinstance(item_count, int) or item_count < 1:
            raise LatticeError("a work unit must hold at least one item")
        intervals = self._scheduler.partition_workload(item_count)
        tiles = [Tile(i, start, stop) for i, (start, stop) in enumerate(intervals) if stop > start]
        if sum(t.items for t in tiles) != item_count or tiles[0].start != 0 or tiles[-1].stop != item_count:
            raise LatticeError("lattice partition does not cover the work unit exactly")
        for left, right in zip(tiles, tiles[1:]):
            if left.stop != right.start:
                raise LatticeError("lattice tiles are not contiguous")
        return tiles

    def describe(self) -> dict[str, Any]:
        warps, lanes = lattice_footprint(self.virtual_units)
        return {
            "virtual_units": self.virtual_units,
            "logical_warps": warps,
            "logical_lanes": lanes,
            "warp_lanes": WARP_LANES,
            "min_items_per_tile": WARP_LANES,
            "label": LATTICE_LABEL,
            "physical_cores_claimed": 0,
        }
