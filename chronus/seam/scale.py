"""Lucas/Pisot Chronus scale contract.

The batch size is a ladder stop. It is not a hashrate multiplier and is never
reported as measured throughput. Chronus owns the offering-level scale policy.

Lucas/Pisot scales EVERYTHING in Chronus: work envelopes, memory budgets, and
logical capacity contracts — not intelligence alone. Effective capacity is a
maths-bounded scale-contract envelope (Rule 7), never a fake GPU count or TH/s.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Any, Dict, List, Tuple

from Intelligence.lucas_scales import (
    CHRONUS_SCALE_RUNGS,
    PISOT_EXACT_N,
    ladder_multiples_of,
    nearest_ladder_index,
)
from kellogg.scales import lucas, pisot_wind

DIM = 11
MAX_WORK_ITEMS = 65536

# Reference Lucas rung for capacity/memory multipliers (L_10 = 123).
REF_LUCAS_N = 10

RULE7_NOTE = (
    "Rule 7: effective_capacity is a scale-contract envelope from Lucas integer "
    "ratios; not measured hashrate, not fake GPU count. Ladder stops are never TH/s."
)


@dataclass(frozen=True)
class ChronusScale:
    requested: int
    work_items: int
    rungs: List[int]
    lucas_L: int
    # Exact Z[phi] coordinates for the 11-dimensional state vector.
    # Each coordinate is a (a, b) integer pair representing a + b*phi.
    t11: Tuple[Tuple[int, int], ...]

    # Backward-compat float view (never used in production path). Deprecated.
    @property
    def t11_floats(self) -> Tuple[float, ...]:
        """Float projections of the exact t11 coordinates — legacy access only."""
        return tuple(math.sqrt(a * a + a * b - b * b + 2 * b) for a, b in self.t11)

    @property
    def ladder_index(self) -> int:
        return self.work_items

    def as_dict(self) -> Dict[str, Any]:
        return {
            "product": "Chronus",
            "compute_substrate": "chronus_execution_plane",
            "requested": self.requested,
            "work_items": self.work_items,
            "rungs": self.rungs,
            "lucas_L": self.lucas_L,
            "t11": list(self.t11),
            "dim": DIM,
            "note": "work_items is a ladder stop; not a throughput claim",
        }


@dataclass(frozen=True)
class EffectiveCapacity:
    """Maths-bounded logical work envelope over physical units.

    physical stays physical. effective is a Lucas-ratio scale-contract envelope
    (Rule 7 Strict Honest Measurement) — never report it as measured hashrate.
    """

    physical: int
    ladder_index: int
    lucas_L: int
    effective: int
    note: str = RULE7_NOTE
    ref_index: int = REF_LUCAS_N
    ref_L: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return {
            "physical": self.physical,
            "ladder_index": self.ladder_index,
            "lucas_L": self.lucas_L,
            "ref_index": self.ref_index,
            "ref_L": self.ref_L,
            "effective": self.effective,
            "note": self.note,
            "rule": "Rule 7 Strict Honest Measurement",
            "kind": "scale_contract_envelope",
        }


def snap_work_items(
    requested: int,
    lo: int = 1,
    hi: int = MAX_WORK_ITEMS,
) -> int:
    """Snap requested work to the nearest Lucas ladder stop in [lo, hi].

    Rule 7: the result is a ladder stop (scale contract), never a throughput claim.
    """
    return int(nearest_ladder_index(int(requested), lo=lo, hi=hi))


def digest_t11(job_id: str, payload: str = "") -> Tuple[Tuple[int, int], ...]:
    """Return the exact Z[phi]-valued 11D initial state for a job.

    Each of the 11 coordinates is an exact pair (a, b) representing
    a + b*phi in the ring Z[phi]. The seed is deterministic (SHA-256 of
    ``job_id|payload``); floats never appear here. They appear once, at the
    single declared one-way projection boundary in :func:`kellogg.scales.pisot_wind`.

    Replacement for the legacy floating-point ``digest_t11`` (which returned
    bytes/255.0 — a numerical approximation, never an exact state coordinate).
    """
    seed = hashlib.sha256(f"{job_id}|{payload}".encode("utf-8")).digest()
    coords: List[Tuple[int, int]] = []
    for i in range(DIM):
        # Deterministic exact mapping from the SHA-256 digest (32 bytes) to
        # an exact Z[phi] element for each of the 11 coordinates. Each
        # coordinate is seeded from 2 bytes with magnitude < 2**15, keeping
        # all downstream operations in the exact integer ring — no floats.
        # i*2 + 1 <= 10*2 + 1 = 21 < 32, so all offsets stay in-bounds.
        byte0 = seed[2 * i]
        byte1 = seed[2 * i + 1]
        # Combine two bytes into a signed-ish 15-bit value with sign bit
        # at position 14 (mask 0x7FFF keeps it < 2**15).
        a = ((byte0 << 7) | (byte1 >> 1)) & 0x7FFF
        b = ((byte1 << 7) | (seed[2 * i + 2] >> 1)) & 0x7FFF if i < DIM - 1 else (
            (byte1 << 7) | (seed[2 * i + 2] >> 1)
        ) if 2 * i + 2 < len(seed) else (byte1 << 7) & 0x7FFF
        # Fallback for i=10 (last coordinate): seed from the last byte(s).
        if i == DIM - 1 and 2 * i < len(seed):
            a = (byte0 << 7) & 0x7FFF
            b = (byte1 << 8 | seed[2 * i + 1]) & 0x7FFF if 2 * i + 1 < len(seed) else 0
        coords.append((a, b))
    return tuple(coords)


def _t11_to_floats(t11: Tuple[Tuple[int, int], ...]) -> Tuple[float, ...]:
    """Project exact Z[phi] coordinates to floats at the one-way boundary."""
    return tuple(a + b * ((1.0 + 5.0**0.5) / 2.0) for a, b in t11)


def scale_job(job_id: str, requested: int, payload: str = "") -> ChronusScale:
    work_items = snap_work_items(requested)
    # Exact Z[phi] coordinates for the 11D state vector. These are the
    # canonical exact representation; the floating-point torus state used
    # by the Pisot drift is a separate observational reading that is only
    # generated at the one-way projection boundary inside pisot_wind().
    t11_exact = digest_t11(job_id, payload)
    return ChronusScale(
        int(requested),
        work_items,
        list(ladder_multiples_of(work_items)),
        int(lucas(work_items)),
        t11_exact,
    )


def toe_t4_lucas_pisot(n: int) -> bool:
    """TOE T4: L_{n+1} - L_n = L_{n-1}."""
    if n < 1:
        return False
    return lucas(n + 1) - lucas(n) == lucas(n - 1)


def rungs() -> Tuple[int, ...]:
    return CHRONUS_SCALE_RUNGS


def _resolve_ladder_index(ladder_index: int | None) -> int:
    if ladder_index is None:
        return int(PISOT_EXACT_N)
    n = int(ladder_index)
    if n < 1:
        return int(PISOT_EXACT_N)
    return n


def compute_effective_capacity(
    physical_units: int,
    ladder_index: int | None = None,
    *,
    ref_index: int = REF_LUCAS_N,
) -> EffectiveCapacity:
    """Return EffectiveCapacity for physical_units at a Lucas ladder stop.

    effective = physical_units * L_n // L_ref  (integer ratio envelope).
    Physical count is unchanged; effective is the logical work envelope only.
    """
    physical = max(0, int(physical_units))
    n = _resolve_ladder_index(ladder_index)
    ref_n = max(1, int(ref_index))
    L = int(lucas(n))
    ref_L = int(lucas(ref_n))
    if ref_L < 1:
        ref_L = 1
    # max(1, L // ref) style via integer multiply-divide keeps physical=0 at 0
    effective = physical * max(1, L) // ref_L if physical else 0
    # Ensure effective is at least physical when L >= ref (normal case)
    if physical and L >= ref_L and effective < physical:
        effective = physical
    return EffectiveCapacity(
        physical=physical,
        ladder_index=n,
        lucas_L=L,
        effective=int(effective),
        note=RULE7_NOTE,
        ref_index=ref_n,
        ref_L=ref_L,
    )


def effective_capacity(
    physical_units: int,
    ladder_index: int | None = None,
) -> Dict[str, Any]:
    """Scale-contract effective capacity envelope (Rule 7 — not hashrate).

    M3 witness class: physical 80 at a mid ladder can yield ~800-class effective
    without inventing GPUs. Never report ladder stops as measured TH/s.
    """
    return compute_effective_capacity(physical_units, ladder_index).as_dict()


def memory_budget_bytes(base_bytes: int, ladder_index: int) -> int:
    """Lucas-scaled memory budget from a base allocation.

    budget = base_bytes * L_n // L_ref  (at least base_bytes when L_n >= L_ref).
    """
    base = max(0, int(base_bytes))
    n = max(1, int(ladder_index))
    L = int(lucas(n))
    ref_L = int(lucas(REF_LUCAS_N))
    if ref_L < 1:
        ref_L = 1
    if base == 0:
        return 0
    budget = base * max(1, L) // ref_L
    return int(max(base, budget))


def scale_report(
    physical_gpus: int = 1,
    ladder_index: int | None = None,
) -> Dict[str, Any]:
    """Combine ChronusScale + EffectiveCapacity into one honest status dict."""
    n = _resolve_ladder_index(ladder_index)
    # Request work envelope near the ladder index (clamped by snap).
    scale = scale_job("chronus-scale-report", max(1, min(n, MAX_WORK_ITEMS)))
    capacity = compute_effective_capacity(physical_gpus, n)
    return {
        "product": "Chronus",
        "compute_substrate": "chronus_execution_plane",
        "physical_gpus": int(physical_gpus),
        "ladder_index": n,
        "scale": scale.as_dict(),
        "capacity": capacity.as_dict(),
        "memory_budget_example": memory_budget_bytes(1 << 20, n),
        "note": RULE7_NOTE,
    }


__all__ = [
    "CHRONUS_SCALE_RUNGS",
    "DIM",
    "MAX_WORK_ITEMS",
    "PISOT_EXACT_N",
    "REF_LUCAS_N",
    "RULE7_NOTE",
    "ChronusScale",
    "EffectiveCapacity",
    "compute_effective_capacity",
    "digest_t11",
    "effective_capacity",
    "memory_budget_bytes",
    "rungs",
    "scale_job",
    "scale_report",
    "snap_work_items",
    "toe_t4_lucas_pisot",
]
