"""Hardware counters — absent backends are stated, never fabricated.

Invariants:
    CNT1: counter values come from a hardware counter source or are unknown.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .._common import unavailable
from ..system.clinfo import OpenCLDevice


@dataclass
class CounterReport:
    counters: Dict[str, Any]
    available: bool
    reason: str
    unknown: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "counters": dict(self.counters),
            "available": self.available,
            "reason": self.reason,
            "unknown": list(self.unknown),
        }


def read_counters(device: OpenCLDevice) -> CounterReport:
    """No counter surface is exposed through the census backends — say so."""
    return CounterReport(
        counters=unavailable("no hardware counter source on detected backends"),
        available=False,
        reason="no hardware counter source on detected backends",
        unknown=["hardware_counters"],
    )
