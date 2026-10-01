"""Compute topology — contract execution units; peaks marked theoretical.

Invariants:
    COMP1: unknown compute properties are listed.
    COMP2: theoretical peaks are clearly distinguished from measured peaks —
           contract/theoretical numbers live in ``theoretical``, measured
           numbers live in ``measured``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ... import spec as _spec
from ..system.clinfo import OpenCLDevice


@dataclass
class ComputeTopology:
    compute_units: Optional[int]
    warp_width: Optional[int]
    max_clock_mhz: Optional[int]
    max_work_group_size: Optional[int]
    execution_nodes: Optional[int]
    memory_nodes: Optional[int]
    logical_partitions: Optional[int]
    theoretical: Dict[str, Any]
    unknown: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "compute_units": self.compute_units,
            "warp_width": self.warp_width,
            "max_clock_mhz": self.max_clock_mhz,
            "max_work_group_size": self.max_work_group_size,
            "execution_nodes": self.execution_nodes,
            "memory_nodes": self.memory_nodes,
            "logical_partitions": self.logical_partitions,
            "theoretical": dict(self.theoretical),
            "unknown": list(self.unknown),
        }


def measure_compute_topology(device: OpenCLDevice) -> ComputeTopology:
    """Execution units come from the device contract; clocks are not asserted."""
    topo = _spec.topology()
    units = _spec.execution_units()
    unknown: List[str] = []

    def known(name: str, value: Any) -> Any:
        if value is None:
            unknown.append(name)
        return value

    warp = topo.get("warp_width")
    nodes = topo.get("icosahedral_execution_nodes")
    mem_nodes = topo.get("dodecahedral_memory_nodes")
    partitions = topo.get("logical_partitions")
    compute_units = device.max_compute_units
    if compute_units is None and isinstance(units, dict):
        compute_units = units.get("compute_units")

    clock = device.max_clock_mhz
    theoretical: Dict[str, Any] = {"source": "device_contract"}
    if warp is not None and clock is not None:
        theoretical["fp32_tflops"] = 2.0 * warp * clock * 1e6 / 1e12
    else:
        theoretical["fp32_tflops"] = None
        unknown.append("fp32_tflops_theoretical(no clock)")

    return ComputeTopology(
        compute_units=known("compute_units", compute_units),
        warp_width=known("warp_width", warp),
        max_clock_mhz=known("max_clock_mhz", clock),
        max_work_group_size=known("max_work_group_size", device.max_work_group_size),
        execution_nodes=known("execution_nodes", nodes),
        memory_nodes=mem_nodes,
        logical_partitions=partitions,
        theoretical=theoretical,
        unknown=unknown,
    )
