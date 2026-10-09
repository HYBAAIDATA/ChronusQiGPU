"""Chronus Seam — the vendor-neutral contract above Chronus device execution.

Turing remains compute. Chronus owns the iGPU offering and this seam prevents
Kellogg, TOE, Aethel and other consumers from depending on vendor SDK handles.

Public functions return Result[T]. Errors are values. Fail closed.

Scale surface (Lucas/Pisot): offering-level ladder stops and effective-capacity
envelopes live on ``chronus.seam.scale`` and are re-exported here. Rule 7 —
ladder stops are never measured hashrate.

Exports are lazy (PEP 562): importing ``chronus.seam`` does not eagerly load
the fleet/hybrid/store submodules, so the leaf surfaces (``scale``, ``types``,
``buffer``) resolve without the orchestrator-only dependencies.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any, Sequence

if TYPE_CHECKING:
    from .fleet import JobResult
    from .probe import Capability
    from .types import Result

_EXPORTS = {
    "AccessPolicy": ("chronus.seam.buffer", "AccessPolicy"),
    "Buffer": ("chronus.seam.buffer", "Buffer"),
    "allocate": ("chronus.seam.buffer", "allocate"),
    "read": ("chronus.seam.buffer", "read"),
    "release": ("chronus.seam.buffer", "release"),
    "write": ("chronus.seam.buffer", "write"),
    "Bid": ("chronus.seam.fleet", "Bid"),
    "DeviceAssignment": ("chronus.seam.fleet", "DeviceAssignment"),
    "JobResult": ("chronus.seam.fleet", "JobResult"),
    "bid": ("chronus.seam.fleet", "bid"),
    "coordinate": ("chronus.seam.fleet", "coordinate"),
    "execute": ("chronus.seam.fleet", "execute"),
    "route": ("chronus.seam.fleet", "route"),
    "run_hybrid_stratum": ("chronus.seam.fleet", "run_hybrid_stratum"),
    "Window": ("chronus.seam.hybrid", "Window"),
    "fallback_candidates": ("chronus.seam.hybrid", "fallback_candidates"),
    "kernel_class": ("chronus.seam.hybrid", "kernel_class"),
    "partition": ("chronus.seam.hybrid", "partition"),
    "supports_class": ("chronus.seam.hybrid", "supports_class"),
    "audit_chronus": ("chronus.seam.invariants", "audit_chronus"),
    "audit_hyba_hybrid": ("chronus.seam.invariants", "audit_hyba_hybrid"),
    "KernelHandle": ("chronus.seam.kernel", "KernelHandle"),
    "KernelResult": ("chronus.seam.kernel", "KernelResult"),
    "cancel": ("chronus.seam.kernel", "cancel"),
    "dispatch": ("chronus.seam.kernel", "dispatch"),
    "poll": ("chronus.seam.kernel", "poll"),
    "Capability": ("chronus.seam.probe", "Capability"),
    "lifecycle": ("chronus.seam.probe", "lifecycle"),
    "probe_devices": ("chronus.seam.probe", "probe_devices"),
    "QueueState": ("chronus.seam.queue", "QueueState"),
    "WorkItem": ("chronus.seam.queue", "WorkItem"),
    "dequeue": ("chronus.seam.queue", "dequeue"),
    "enqueue": ("chronus.seam.queue", "enqueue"),
    "peek": ("chronus.seam.queue", "peek"),
    "queue_state": ("chronus.seam.queue", "queue_state"),
    "store": ("chronus.seam.store", None),
    "CHRONUS_SCALE_RUNGS": ("chronus.seam.scale", "CHRONUS_SCALE_RUNGS"),
    "REF_LUCAS_N": ("chronus.seam.scale", "REF_LUCAS_N"),
    "RULE7_NOTE": ("chronus.seam.scale", "RULE7_NOTE"),
    "ChronusScale": ("chronus.seam.scale", "ChronusScale"),
    "EffectiveCapacity": ("chronus.seam.scale", "EffectiveCapacity"),
    "compute_effective_capacity": ("chronus.seam.scale", "compute_effective_capacity"),
    "effective_capacity": ("chronus.seam.scale", "effective_capacity"),
    "memory_budget_bytes": ("chronus.seam.scale", "memory_budget_bytes"),
    "scale_job": ("chronus.seam.scale", "scale_job"),
    "scale_report": ("chronus.seam.scale", "scale_report"),
    "snap_work_items": ("chronus.seam.scale", "snap_work_items"),
    "BufferBacking": ("chronus.seam.types", "BufferBacking"),
    "DeviceClass": ("chronus.seam.types", "DeviceClass"),
    "DeviceState": ("chronus.seam.types", "DeviceState"),
    "Distribution": ("chronus.seam.types", "Distribution"),
    "Err": ("chronus.seam.types", "Err"),
    "KernelClass": ("chronus.seam.types", "KernelClass"),
    "KernelName": ("chronus.seam.types", "KernelName"),
    "Ok": ("chronus.seam.types", "Ok"),
    "PrivacyMode": ("chronus.seam.types", "PrivacyMode"),
    "Result": ("chronus.seam.types", "Result"),
    "SeamError": ("chronus.seam.types", "SeamError"),
}


class Seam:
    """Top-level Chronus contract object bound to one process-local store."""

    @staticmethod
    def for_device(device: Any) -> "Seam":
        probe_devices = __getattr__("probe_devices")
        probe_devices()
        return Seam()

    def run(
        self,
        job: dict,
        fleet: "Sequence[Capability] | None" = None,
    ) -> "Result[JobResult]":
        if fleet is None:
            probed = __getattr__("probe_devices")()
            err_type = __getattr__("Err")
            if isinstance(probed, err_type):
                return probed
            fleet = probed.value
        return __getattr__("coordinate")("seam", job, fleet)


def run(
    job: dict,
    fleet: "Sequence[Capability] | None" = None,
) -> "Result[JobResult]":
    return Seam().run(job, fleet)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    module = import_module(module_name)
    value = module if attribute is None else getattr(module, attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))


__all__ = sorted(_EXPORTS) + ["Seam", "run"]
