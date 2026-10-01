"""HYBA super-GPU facade — the composition surface over the measured census.

The implementation is :class:`chronus.fabric.ChronusFabric` — post-consolidation
"the GPU" is Chronus, so ``SuperGPU`` is the same class under the name the
elevation spec uses. ``SuperGPU.compose(inventory)`` composes every device in
a :class:`hyba.inventory.ClusterInventory` (Σ compute units, capability union
keyed to the best device) and ``route(op, workload)`` returns a
:class:`chronus.fabric.RouteDecision` carrying the spec's dispatch record —
``(device_name, capability, backend, lucas_dispatch)`` with per-device
ladder rung/chunk snap, ``workgroup_size <= max_workgroup``, and
``grover_depth`` for search ops.

LUCAS WIRING: coordinator module — re-exports only; adds no algorithm.
"""

from __future__ import annotations

from chronus.fabric import ChronusFabric, RouteDecision

SuperGPU = ChronusFabric

__all__ = [
    "RouteDecision",
    "SuperGPU",
]
