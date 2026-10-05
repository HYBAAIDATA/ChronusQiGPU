"""Chronus Seam — the vendor-neutral contract above Chronus device execution.

Turing remains compute. Chronus owns the iGPU offering and this seam prevents
Kellogg, TOE, Aethel and other consumers from depending on vendor SDK handles.

Public functions return Result[T]. Errors are values. Fail closed.

Scale surface (Lucas/Pisot): offering-level ladder stops and effective-capacity
envelopes live on ``chronus.seam.scale`` and are re-exported here. Rule 7 —
ladder stops are never measured hashrate.
"""

from __future__ import annotations

from typing import Any, Sequence

from .buffer import AccessPolicy, Buffer, allocate, read, release, write
from .fleet import (
    Bid,
    DeviceAssignment,
    JobResult,
    bid,
    coordinate,
    execute,
    route,
    run_hybrid_stratum,
)
from .hybrid import (
    Window,
    fallback_candidates,
    kernel_class,
    partition,
    supports_class,
)
from .invariants import audit_chronus, audit_hyba_hybrid
from .kernel import KernelHandle, KernelResult, cancel, dispatch, poll
from .probe import Capability, lifecycle, probe_devices
from .queue import QueueState, WorkItem, dequeue, enqueue, peek, queue_state
from . import store
from .scale import (
    CHRONUS_SCALE_RUNGS,
    REF_LUCAS_N,
    RULE7_NOTE,
    ChronusScale,
    EffectiveCapacity,
    compute_effective_capacity,
    effective_capacity,
    memory_budget_bytes,
    scale_job,
    scale_report,
    snap_work_items,
)
from .types import (
    BufferBacking,
    DeviceClass,
    DeviceState,
    Distribution,
    Err,
    KernelClass,
    KernelName,
    Ok,
    PrivacyMode,
    Result,
    SeamError,
)


class Seam:
    """Top-level Chronus contract object bound to one process-local store."""

    @staticmethod
    def for_device(device: Any) -> "Seam":
        probe_devices()
        return Seam()

    def run(
        self,
        job: dict,
        fleet: Sequence[Capability] | None = None,
    ) -> Result[JobResult]:
        if fleet is None:
            probed = probe_devices()
            if isinstance(probed, Err):
                return probed
            fleet = probed.value
        return coordinate("seam", job, fleet)


def run(
    job: dict,
    fleet: Sequence[Capability] | None = None,
) -> Result[JobResult]:
    return Seam().run(job, fleet)


__all__ = [
    "AccessPolicy",
    "Bid",
    "Buffer",
    "BufferBacking",
    "CHRONUS_SCALE_RUNGS",
    "Capability",
    "ChronusScale",
    "DeviceAssignment",
    "DeviceClass",
    "DeviceState",
    "Distribution",
    "EffectiveCapacity",
    "Err",
    "JobResult",
    "KernelClass",
    "KernelHandle",
    "KernelName",
    "KernelResult",
    "Ok",
    "PrivacyMode",
    "QueueState",
    "REF_LUCAS_N",
    "RULE7_NOTE",
    "Result",
    "Seam",
    "SeamError",
    "WorkItem",
    "Window",
    "allocate",
    "audit_chronus",
    "audit_hyba_hybrid",
    "bid",
    "cancel",
    "compute_effective_capacity",
    "coordinate",
    "dequeue",
    "dispatch",
    "effective_capacity",
    "enqueue",
    "execute",
    "fallback_candidates",
    "kernel_class",
    "lifecycle",
    "memory_budget_bytes",
    "partition",
    "peek",
    "poll",
    "probe_devices",
    "queue_state",
    "read",
    "release",
    "route",
    "run",
    "run_hybrid_stratum",
    "scale_job",
    "scale_report",
    "snap_work_items",
    "supports_class",
    "write",
]
