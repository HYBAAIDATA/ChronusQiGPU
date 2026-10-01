"""Cache hierarchy — declared unknown unless a backend reports it.

Invariants:
    CACHE1: every unreported cache level is listed in ``unknown``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..system.clinfo import OpenCLDevice

_LEVELS = ("l1_instruction", "l1_data", "l2", "l3")


@dataclass
class CacheHierarchy:
    levels: Dict[str, Optional[int]]
    unknown: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {"levels": dict(self.levels), "unknown": list(self.unknown)}


def measure_cache_hierarchy(device: OpenCLDevice) -> CacheHierarchy:
    """No backend on this census reports cache sizes — all levels unknown."""
    return CacheHierarchy(levels={level: None for level in _LEVELS}, unknown=list(_LEVELS))
