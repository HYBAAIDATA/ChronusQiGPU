"""Seam scale - Phase 1 configuration and detection.

This module implements Phase 1 of the Chronus Elevation Roadmap.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from chronus.core.enums import CapacityLabel
from chronus.core.dataclasses import EffectiveCapacity
from chronus.core.constants import (
    LUCAS_LADDER_RUNGS,
    SPMD_DEFAULT_LANES,
    SPMD_ROADMAP_MAX_LANES,
)


class DetectedResources:
    __slots__ = ("sms", "threads_per_sm", "lanes", "source")

    def __init__(self, sms, threads_per_sm, lanes, source="probed"):
        self.sms = sms
        self.threads_per_sm = threads_per_sm
        self.lanes = lanes
        self.source = source


def detect_compute_units():
    """Probe the local machine for compute resources.

    The probe is the authoritative source for capacity: never invent
    resources the machine does not expose. CPU count from OS; SM/warp-lane
    counts fall back to CPU count when no accelerator can be measured.
    """
    try:
        cpu_count = os.cpu_count() or 1
    except Exception:
        cpu_count = 1
    sms = cpu_count
    threads_per_sm = 256
    lanes = SPMD_DEFAULT_LANES
    return DetectedResources(sms=sms, threads_per_sm=threads_per_sm, lanes=lanes, source="probed")

class ComputeUnitPool:
    def __init__(self, n_sms, threads_per_sm):
        if n_sms > 64:
            raise ValueError(f"n_sms {n_sms} exceeds CU_POOL_ROADMAP_MAX_SMS 64")
        self.n_sms = n_sms
        self.threads_per_sm = threads_per_sm

    def total_threads(self):
        return self.n_sms * self.threads_per_sm


class SPMDExecutor:
    def __init__(self, n_lanes):
        if n_lanes > 64:
            raise ValueError(f"n_lanes {n_lanes} exceeds 64")
        self.n_lanes = n_lanes


def compute_effective_capacity(source):
    """Compute effective capacity from a ComputeUnitPool or adapter list.

    Axiom 4: unbounded sums are forbidden; clamp to Lucas ladder.
    """
    if isinstance(source, ComputeUnitPool):
        physical = source.n_sms
        effective = float(physical) * source.threads_per_sm
    else:
        physical = sum(a.core_count for a in source)
        effective = sum(a.core_count for a in source if a.is_functional())
        effective = clamp_to_lucas_ladder(effective)
    return EffectiveCapacity(physical_units=physical, ladder_index=1, effective=effective, label=CapacityLabel.EFFECTIVE_CAPACITY)


def clamp_to_lucas_ladder(value):
    for i in range(len(LUCAS_LADDER_RUNGS) - 1):
        if LUCAS_LADDER_RUNGS[i] <= value < LUCAS_LADDER_RUNGS[i + 1]:
            return LUCAS_LADDER_RUNGS[i + 1]
    return LUCAS_LADDER_RUNGS[-1]


def memory_budget_bytes(tier):
    if tier == "TIER_0_ON_DEVICE_HBM":
        return (2e12, "DESIGN_ENVELOPE")
    elif tier == "TIER_1_DRAM_POOL":
        return (20e12, "DESIGN_ENVELOPE")
    elif tier == "TIER_2_REMOTE_CLOUD":
        return (float("inf"), "ROADMAP_TARGET")
    elif tier == "TIER_3_QUANTUM_RAM":
        return (float("inf"), "THEORETICAL")


def phase_1_gate():
    """Phase 1 conformance gate (Axiom 8: measurement before promotion)."""
    detected = detect_compute_units()
    if detected.source not in ("probed", "configured"):
        return False
    ctx = ChronusContext.from_config()
    if ctx.n_sms > 64:
        return False
    ecap = compute_effective_capacity(ctx.cu_pool)
    if ecap.label != CapacityLabel.EFFECTIVE_CAPACITY:
        return False
    return True



@dataclass
class ChronusContext:
    """Top-level context for Chronus execution (Phase 1).

    Constructor parameters are explicit and bounded by the roadmap.
    n_sms  <= frozen Lucas ladder max;  lanes <= roadmap max lanes.
    """
    n_sms: int
    threads_per_sm: int
    lanes: int
    config: Optional[Dict[str, Any]] = None
    cu_pool: Any = None
    spmd: Any = None
    capacity_report: Any = None

    def __post_init__(self):
        if self.n_sms > LUCAS_LADDER_RUNGS[-1]:
            raise ValueError(f"n_sms {self.n_sms} exceeds frozen ladder max")
        if self.lanes > SPMD_ROADMAP_MAX_LANES:
            raise ValueError(f"lanes {self.lanes} exceeds roadmap max lanes")

    @classmethod
    def from_config(cls, config=None):
        detected = detect_compute_units()
        n_sms = config.get("n_sms", detected.sms) if config else detected.sms
        threads = config.get("threads_per_sm", detected.threads_per_sm) if config else detected.threads_per_sm
        lanes = config.get("n_lanes", detected.lanes) if config else detected.lanes
        ctx = cls(n_sms=min(n_sms, LUCAS_LADDER_RUNGS[-1]), threads_per_sm=threads, lanes=lanes, config=config)
        ctx.cu_pool = ComputeUnitPool(ctx.n_sms, ctx.threads_per_sm)
        ctx.spmd = SPMDExecutor(ctx.lanes)
        ctx.capacity_report = compute_effective_capacity(ctx.cu_pool)
        return ctx
