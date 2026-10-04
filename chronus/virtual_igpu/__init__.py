"""Chronus Virtual iGPU public surface; heavy runtime imports stay lazy."""
from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORTS = {
    "ABI_VERSION": ("chronus.virtual_igpu.abi", "ABI_VERSION"),
    "Workload": ("chronus.virtual_igpu.abi", "Workload"),
    "WorkloadKind": ("chronus.virtual_igpu.abi", "WorkloadKind"),
    "WorkloadResult": ("chronus.virtual_igpu.abi", "WorkloadResult"),
    "ExecutionPolicy": ("chronus.virtual_igpu.abi", "ExecutionPolicy"),
    "DeliveryMode": ("chronus.virtual_igpu.abi", "DeliveryMode"),
    "TrustClass": ("chronus.virtual_igpu.abi", "TrustClass"),
    "RuntimeState": ("chronus.virtual_igpu.abi", "RuntimeState"),
    "ExecutionReceipt": ("chronus.virtual_igpu.abi", "ExecutionReceipt"),
    "PortablePackage": ("chronus.virtual_igpu.abi", "PortablePackage"),
    "CapabilityManifest": ("chronus.virtual_igpu.abi", "CapabilityManifest"),
    "ChronusClient": ("chronus.virtual_igpu.client", "ChronusClient"),
    "RuntimeDaemon": ("chronus.virtual_igpu.runtime", "RuntimeDaemon"),
    "EvidenceLedger": ("chronus.virtual_igpu.evidence", "EvidenceLedger"),
    "validate_receipt": ("chronus.virtual_igpu.evidence", "validate_receipt"),
    "default_adapters": ("chronus.virtual_igpu.adapters", "default_adapters"),
    "CPUEmulatorAdapter": ("chronus.virtual_igpu.adapters", "CPUEmulatorAdapter"),
    "AdapterUnavailable": ("chronus.virtual_igpu.adapters", "AdapterUnavailable"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    if name not in _EXPORTS:
        raise AttributeError(name)
    mod_name, attr = _EXPORTS[name]
    value = getattr(import_module(mod_name), attr)
    globals()[name] = value
    return value
