"""Chronus Virtual iGPU public surface; heavy runtime imports stay lazy."""
from __future__ import annotations

from importlib import import_module

_EXPORTS = {
    "ABI_VERSION": ("chronus.virtual_igpu.abi", "ABI_VERSION"),
    "AdapterKind": ("chronus.virtual_igpu.abi", "AdapterKind"),
    "Capability": ("chronus.virtual_igpu.abi", "Capability"),
    "Workload": ("chronus.virtual_igpu.abi", "Workload"),
    "WorkloadKind": ("chronus.virtual_igpu.abi", "WorkloadKind"),
    "WorkloadResult": ("chronus.virtual_igpu.abi", "WorkloadResult"),
    "VirtualIGPUClient": ("chronus.virtual_igpu.client", "VirtualIGPUClient"),
    "RuntimeConfig": ("chronus.virtual_igpu.runtime", "RuntimeConfig"),
    "RuntimeDaemon": ("chronus.virtual_igpu.runtime", "RuntimeDaemon"),
    "RuntimeInvariantError": ("chronus.virtual_igpu.runtime", "RuntimeInvariantError"),
}
__all__ = sorted(_EXPORTS)


def __getattr__(name):
    try:
        module, attribute = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(module), attribute)
    globals()[name] = value
    return value