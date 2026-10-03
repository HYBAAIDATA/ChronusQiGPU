"""Typed capability manifests and device/kernel constraint intersection."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class DeviceLimits:
    max_work_group_size: int
    max_work_item_sizes: tuple[int, ...]
    local_memory_bytes: int
    global_memory_bytes: int | None = None
    max_allocation_bytes: int | None = None
    host_unified_memory: bool | None = None

    def __post_init__(self):
        if self.max_work_group_size < 1 or self.local_memory_bytes < 0:
            raise ValueError("invalid device limits")
        if not self.max_work_item_sizes or any(v < 1 for v in self.max_work_item_sizes):
            raise ValueError("invalid per-dimension work-item limits")


@dataclass(frozen=True)
class KernelLimits:
    max_work_group_size: int
    preferred_multiple: int
    static_local_memory_bytes: int = 0

    def __post_init__(self):
        if self.max_work_group_size < 1 or self.preferred_multiple < 1:
            raise ValueError("invalid kernel limits")


@dataclass(frozen=True)
class CapabilityManifest:
    adapter_id: str
    adapter_kind: str
    operations: tuple[str, ...]
    dtypes: tuple[str, ...]
    execution_classes: tuple[str, ...]
    memory_model: dict[str, Any]
    execution_model: dict[str, Any]
    limits: dict[str, Any]
    profiling: dict[str, Any]
    verified: dict[str, Any]
    evidence: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def legal_local_size(
    requested: Iterable[int], device: DeviceLimits, kernel: KernelLimits,
    dynamic_local_memory_bytes: int = 0,
) -> tuple[int, ...]:
    dims = tuple(int(v) for v in requested)
    if not dims or len(dims) > len(device.max_work_item_sizes) or any(v < 1 for v in dims):
        raise ValueError("invalid local-size dimensionality")
    total = 1
    for used, limit in zip(dims, device.max_work_item_sizes):
        if used > limit:
            raise ValueError("local size exceeds CL_DEVICE_MAX_WORK_ITEM_SIZES")
        total *= used
    if total > min(device.max_work_group_size, kernel.max_work_group_size):
        raise ValueError("local size exceeds device/kernel work-group limit")
    if kernel.static_local_memory_bytes + int(dynamic_local_memory_bytes) > device.local_memory_bytes:
        raise ValueError("kernel local-memory requirement exceeds device capacity")
    return dims
