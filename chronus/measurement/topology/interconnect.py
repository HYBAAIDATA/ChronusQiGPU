"""Interconnect enumeration — PCI ids when the census saw them, else unknown.

Invariants:
    LINK1: unknown link properties are listed, not guessed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..system.clinfo import OpenCLDevice


@dataclass
class Interconnect:
    kind: Optional[str]
    pci_ids: List[str]
    link_width: Optional[int]
    link_gen: Optional[int]
    unknown: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "pci_ids": list(self.pci_ids),
            "link_width": self.link_width,
            "link_gen": self.link_gen,
            "unknown": list(self.unknown),
        }


def measure_interconnect(device: OpenCLDevice) -> Interconnect:
    """UMA-integrated devices ride the memory fabric; lanes are not asserted."""
    unknown = []
    kind: Optional[str] = None
    if device.host_unified_memory:
        kind = "host_unified_memory"
    elif device.pci_ids:
        kind = "pcie"
    else:
        unknown.append("kind")
    if not device.pci_ids:
        unknown.append("pci_ids")
    unknown.extend(["link_width", "link_gen"])
    return Interconnect(
        kind=kind,
        pci_ids=list(device.pci_ids),
        link_width=None,
        link_gen=None,
        unknown=unknown,
    )
