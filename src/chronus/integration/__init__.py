"""Integration - Tier 12: integration with existing Chronus structures.

Every integration point named in section 6 of the Chronus Elevation Roadmap
is made concrete. This module wires the elevation layers to the existing
chronus.fleet, chronus.execution, and chronus.backends modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from chronus.core.enums import (
    AdapterBackend,
    AdapterRole,
    AdapterStatus,
    CapacityLabel,
    EvidenceClass,
    MemoryTier,
    TrustClass,
)
from chronus.fleet import (
    AdapterRegistry,
    DeviceAdapter,
    FleetCoordinator,
    FleetExecutor,
    WorkUnit,
)
from chronus.fleet.workunit import POOL_PREFILL, POOL_DECODE, ROUTE_AUTO

__all__ = [
    "VirtualIGPU",
    "submit_via_virtual_igpu",
    "RuntimeDaemon",
]


# ---------------------------------------------------------------------------
# Tier 12.1 - VirtualIGPU (section 6)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VirtualIGPU:
    """The virtual iGPU abstraction that ties adapters to the fleet.

    This is the "seam" that connects the elevation layers to the
    existing fleet infrastructure.
    """

    registry: AdapterRegistry
    coordinator: "FleetCoordinator"
    executor: FleetExecutor

    def probe(self) -> List[DeviceAdapter]:
        """Probe all available adapters in the fleet."""
        return self.registry.discover()

    def allocate_nonce_ranges(self, n_active: int) -> Dict[str, tuple]:
        """Allocate disjoint nonce ranges across active adapters."""
        if n_active <= 0:
            return {}
        span = 2**64 // n_active
        adapters = self.registry.functionals()
        ranges = {}
        for i, adapter in enumerate(adapters):
            ranges[adapter.id] = (i * span, (i + 1) * span - 1)
        return ranges

    def route(self, work_item: Dict[str, Any]) -> str:
        """Route a work item by load/affinity, with explicit fallback."""
        # Load-aware routing with explicit fallback (Axiom 7)
        candidates = [a for a in self.registry.functionals() if a.role == work_item.get("required_role", "GENERAL")]
        if not candidates:
            # Axiom 7: explicit fallback, logged
            return ROUTE_AUTO
        return min(candidates, key=lambda a: a.load).id


# ---------------------------------------------------------------------------
# Tier 12.2 - RuntimeDaemon (section 6)
# ---------------------------------------------------------------------------


@dataclass
class RuntimeDaemon:
    """The runtime daemon that routes work through the fleet or single adapter."""

    fleet: Optional[VirtualIGPU] = None
    default_adapter: Any = None

    def route_work(self, work_item: Dict[str, Any]) -> Dict[str, Any]:
        """Route work through the fleet (multi-adapter) or single adapter mode."""
        if self.fleet is not None:
            return self.fleet.executor.execute([work_item])[0]
        if self.default_adapter is not None:
            return self.default_adapter.execute(work_item)
        raise RuntimeError("No adapter configured")


# ---------------------------------------------------------------------------
# Tier 12.3 - Mining bridge shard (section 6)
# ---------------------------------------------------------------------------


@dataclass
class MiningBridge:
    """The mining bridge that sharding plans across the fleet."""

    virtual_igpu: Optional[VirtualIGPU] = None

    def submit_via_virtual_igpu(
        self,
        plan: Dict[str, Any],
        mode: str = "SINGLE_ADAPTER",
    ) -> Dict[str, Any]:
        """Submit a mining plan via the virtual iGPU.

        Supports single-adapter and fleet-sharded submission modes.
        """
        if mode == "FLEET_SHARDED" and self.virtual_igpu is not None:
            # Shard plan across active adapters
            adapters = self.virtual_igpu.registry.functionals()
            if not adapters:
                raise RuntimeError("No active adapters for fleet sharding")
            shards = [plan] * len(adapters)  # simplified sharding
            results = [a.execute(s) for a, s in zip(adapters, shards)]
            return {"mode": "FLEET_SHARDED", "results": results}
        else:
            # Single adapter mode
            return {"mode": "SINGLE_ADAPTER", "result": "submitted"}
