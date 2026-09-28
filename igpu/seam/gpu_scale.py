"""Lucas/Pisot iGPU scale. The batch size is a ladder stop. H/s is not L_n."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, List, Tuple

from Intelligence.lucas_scales import (
    IGPU_SCALE_RUNGS,
    PISOT_EXACT_N,
    ladder_multiples_of,
    nearest_ladder_index,
)
from kellogg.scales import lucas, pisot_wind

DIM = 11
MAX_WORK_ITEMS = 65536


@dataclass(frozen=True)
class GpuScale:
    requested: int
    work_items: int
    rungs: List[int]
    lucas_L: int
    t11: Tuple[float, ...]

    @property
    def ladder_index(self) -> int:
        """The snapped ladder stop (``nearest_ladder_index`` of the request)."""
        return self.work_items

    def as_dict(self) -> Dict[str, object]:
        return {
            "requested": self.requested,
            "work_items": self.work_items,
            "rungs": self.rungs,
            "lucas_L": self.lucas_L,
            "t11": list(self.t11),
            "dim": DIM,
            "note": "work_items is the ladder stop; not an EH/s claim",
        }


def snap_work_items(requested: int, lo: int = 1, hi: int = MAX_WORK_ITEMS) -> int:
    return nearest_ladder_index(int(requested), lo=lo, hi=hi)


def digest_t11(job_id: str, payload: str = "") -> Tuple[float, ...]:
    seed = hashlib.sha256(f"{job_id}|{payload}".encode("utf-8")).digest()
    return tuple(seed[i] / 255.0 for i in range(DIM))


def scale_job(job_id: str, requested: int, payload: str = "") -> GpuScale:
    n = snap_work_items(requested or PISOT_EXACT_N)
    wind = pisot_wind(digest_t11(job_id, payload), n)
    return GpuScale(int(requested), n, ladder_multiples_of(n), lucas(n), wind)


def toe_t4_lucas_pisot(n: int) -> bool:
    """TOE T4: L_{n+1} − L_n = L_{n-1}."""
    if n < 1:
        return False
    return lucas(n + 1) - lucas(n) == lucas(n - 1)


def rungs() -> Tuple[int, ...]:
    return IGPU_SCALE_RUNGS
