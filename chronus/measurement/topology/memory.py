"""Memory hierarchy — contract-declared fields plus host-observable sizes.

Invariants:
    MEM1: unknown memory properties are listed, not guessed.
    MEM2: every measured bandwidth is tied to a measurement method.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ... import spec as _spec
from ..system.clinfo import OpenCLDevice


@dataclass
class MemoryHierarchy:
    global_bytes: Optional[int]
    global_bandwidth_gbps: Optional[float]
    local_bytes: Optional[int]
    local_bandwidth_gbps: Optional[float]
    l2_bytes: Optional[int]
    l2_bandwidth_gbps: Optional[float]
    l1_bytes: Optional[int]
    l1_bandwidth_gbps: Optional[float]
    registers_bytes: Optional[int]
    unified_memory: Optional[bool]
    memory_address_space: str
    unknown: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "global_bytes": self.global_bytes,
            "global_bandwidth_gbps": self.global_bandwidth_gbps,
            "local_bytes": self.local_bytes,
            "local_bandwidth_gbps": self.local_bandwidth_gbps,
            "l2_bytes": self.l2_bytes,
            "l2_bandwidth_gbps": self.l2_bandwidth_gbps,
            "l1_bytes": self.l1_bytes,
            "l1_bandwidth_gbps": self.l1_bandwidth_gbps,
            "registers_bytes": self.registers_bytes,
            "unified_memory": self.unified_memory,
            "memory_address_space": self.memory_address_space,
            "unknown": list(self.unknown),
        }


def measure_memory_hierarchy(device: OpenCLDevice) -> MemoryHierarchy:
    """Contract memory model + whatever the census observed; rest is unknown."""
    contract = _spec.memory_system()
    topo = _spec.topology()
    unknown: List[str] = []

    def known(name: str, value: Optional[int]) -> Optional[int]:
        if value is None:
            unknown.append(name)
        return value

    hierarchy = MemoryHierarchy(
        global_bytes=known("global_memory_bytes", device.global_memory_bytes),
        global_bandwidth_gbps=None,
        local_bytes=known("local_memory_bytes", device.local_memory_bytes),
        local_bandwidth_gbps=None,
        l2_bytes=None,
        l2_bandwidth_gbps=None,
        l1_bytes=None,
        l1_bandwidth_gbps=None,
        registers_bytes=None,
        unified_memory=device.host_unified_memory,
        memory_address_space=str(topo.get("memory_address_space", "")),
        unknown=unknown,
    )
    for prop in ("l2_bytes", "l1_bytes", "registers_bytes"):
        unknown.append(prop)
    for prop in ("global_bandwidth_gbps", "local_bandwidth_gbps"):
        unknown.append(prop)
    nodes = contract.get("dodecahedral_memory_nodes") or topo.get("dodecahedral_memory_nodes")
    if nodes is not None:
        hierarchy.memory_address_space = hierarchy.memory_address_space or "UMA"
    return hierarchy
