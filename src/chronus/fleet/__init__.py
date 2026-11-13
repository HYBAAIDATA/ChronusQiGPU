# Copyright (c) 2026 HYBA Software Ltd. All rights reserved.
# Chronus is a HYBA Data product.
"""Chronus iGPU fleet: many machines composed into one Chronus iGPU.

A coordinator and any number of workers (MacBook, iMac, other laptops,
servers) form one logical iGPU. Work units are striped by the resident
virtual-unit scheduling lattice (80, 800 or 8,000 virtual units; logical
tiles, not physical cores), leased by measured capability to self-tested
device routes (reference, NumPy SIMD, native C++ SIMD, Apple Metal, OpenCL),
checked against the deterministic pure-Python reference, recovered through a
blind check when a machine fails, provisioned in commercial tiers with a
signed option to scale, and closed with an ML-DSA-65 signed, ledger-anchored
receipt. Each machine detects its backends and runs the one the operator
chooses (``--backend``, ``--prefer ours|host``; ours is the Chronus iGPU).

Start with ``FleetExecutor`` (Python) or ``chronus-fleet`` (command line);
docs/fleet/FLEET.md explains the system and its honesty rules.
"""

from __future__ import annotations

import importlib
from typing import Any

_EXPORTS = {
    "FleetExecutor": "chronus.fleet.executor",
    "FleetResult": "chronus.fleet.executor",
    "WorkUnit": "chronus.fleet.workunit",
    "FleetCoordinator": "chronus.fleet.coordinator",
    "CoordinatorConfig": "chronus.fleet.coordinator",
    "FleetWorker": "chronus.fleet.worker",
    "WorkerConfig": "chronus.fleet.worker",
    "AdapterRegistry": "chronus.fleet.adapters",
    "DeviceAdapter": "chronus.fleet.adapters",
    "Kernel": "chronus.fleet.kernels",
    "KernelRegistry": "chronus.fleet.kernels",
    "KnownAnswer": "chronus.fleet.kernels",
    "default_registry": "chronus.fleet.kernels",
    "SchedulingLattice": "chronus.fleet.lattice",
    "RESIDENT_RUNGS": "chronus.fleet.lattice",
    "TIERS": "chronus.fleet.phase",
    "TIER_GATE": "chronus.fleet.phase",
    "Tier": "chronus.fleet.phase",
    "scale_tier": "chronus.fleet.phase",
    "ScaleGrant": "chronus.fleet.scale",
    "issue_grant": "chronus.fleet.scale",
    "BackendSelection": "chronus.fleet.backends",
    "select_backend": "chronus.fleet.backends",
    "verify_receipt": "chronus.fleet.receipts",
    "DeviceUnavailableError": "chronus.fleet.errors",
    "TierGateRejected": "chronus.fleet.errors",
    "ScaleGrantRejected": "chronus.fleet.errors",
    "CapacityLedger": "chronus.fleet.capacity",
    "HostCapacity": "chronus.fleet.capacity",
    "discover_host": "chronus.fleet.capacity",
}

__all__ = [
    "RESIDENT_RUNGS",
    "TIERS",
    "TIER_GATE",
    "AdapterRegistry",
    "BackendSelection",
    "CapacityLedger",
    "CoordinatorConfig",
    "DeviceAdapter",
    "DeviceUnavailableError",
    "FleetCoordinator",
    "FleetExecutor",
    "FleetResult",
    "FleetWorker",
    "HostCapacity",
    "Kernel",
    "KernelRegistry",
    "KnownAnswer",
    "ScaleGrant",
    "SchedulingLattice",
    "Tier",
    "TierGateRejected",
    "WorkUnit",
    "WorkerConfig",
    "default_registry",
    "discover_host",
    "issue_grant",
    "scale_tier",
    "select_backend",
    "verify_receipt",
]


def __getattr__(name: str) -> Any:
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(module), name)
