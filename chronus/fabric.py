"""Chronus measured-device fabric.

Chronus composes every measured execution device in :class:`ClusterInventory`
into one product/runtime routing surface. TURING remains an independent
VQC authority; this module decides where Chronus-executed operations run and
attests what actually ran.

Nothing here simulates hardware. The fabric reports only measured members and
routes to explicit CPU reference execution only when the operation contract
permits it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from Intelligence.lucas_scales import (
    CHRONUS_SCALE_RUNGS,
    LUCAS_SCALE_LADDER,
    is_ladder_index,
    nearest_ladder_index,
)
from hyba.inventory import ClusterInventory, DeviceInfo

_DEFAULT_WORK_ITEMS = 1 << 20
_M32_LANES = 32


@dataclass(frozen=True)
class RouteDecision:
    """One Chronus route: selected device, capability and dispatch metadata."""

    op: str
    device_name: str
    backend: str
    capability: Optional[str]
    lucas_dispatch: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "op": self.op,
            "device_name": self.device_name,
            "backend": self.backend,
            "capability": self.capability,
            "lucas_dispatch": dict(self.lucas_dispatch),
            "reason": self.reason,
        }


class ChronusFabric:
    """Measured multi-device execution fabric for the Chronus offering."""

    def __init__(self, inventory: ClusterInventory) -> None:
        self.inventory = inventory
        self.devices: List[DeviceInfo] = list(inventory.devices)

    @classmethod
    def compose(cls, inventory: Optional[ClusterInventory] = None) -> "ChronusFabric":
        """Compose the measured census, collecting it when omitted."""
        return cls(inventory if inventory is not None else ClusterInventory.collect())

    @property
    def compute_units(self) -> int:
        return sum(d.compute_units or 0 for d in self.devices)

    @property
    def global_mem_mb(self) -> int:
        return sum(d.global_mem_mb or 0 for d in self.devices)

    def capability_map(self) -> Dict[str, str]:
        """Capability -> measured device best able to serve that capability."""
        out: Dict[str, str] = {}
        merit: Dict[str, int] = {}
        for device in self.devices:
            for key in dict(device.capabilities):
                score = device.compute_units or 0
                if key not in out or score > merit[key]:
                    out[key] = device.name
                    merit[key] = score
        return out

    def _best_gpu(self, *, required: Optional[str] = None) -> Optional[DeviceInfo]:
        pool = [
            d
            for d in self.devices
            if d.type in ("gpu", "chronus") and d.backend != "rtl"
        ]
        if required is not None:
            pool = [d for d in pool if d.capability(required) not in (None, False, 0)]
        if not pool:
            return None
        return max(pool, key=lambda d: d.compute_units or 0)

    def _cpu(self) -> DeviceInfo:
        """The inventory's CPU member; the fabric cannot route without one.

        Every route falls back to CPU reference execution, so a census with
        no CPU is a broken inventory — fail loudly instead of letting a
        stripped ``assert`` (``python -O``) turn it into a silent ``None``.
        """
        for device in self.devices:
            if device.backend == "cpu":
                return device
        raise RuntimeError(
            "ClusterInventory contains no CPU device; Chronus fabric cannot route"
        )

    def _lucas_dispatch(
        self,
        device: DeviceInfo,
        *,
        work_items: int,
        chunk_cap: int,
    ) -> Dict[str, Any]:
        items = max(1, int(work_items))
        chunk = nearest_ladder_index(min(items, chunk_cap), 1, max(1, chunk_cap))
        rung = next(
            (r for r in sorted(CHRONUS_SCALE_RUNGS, reverse=True) if chunk % r == 0),
            None,
        )
        max_wg = int(device.capability("max_workgroup", 0) or 0)
        workgroup = min(256, max_wg) if max_wg else 1
        return {
            "work_items": items,
            "chunk_size": chunk,
            "on_ladder": is_ladder_index(chunk),
            "lucas_rung": rung,
            "workgroup_size": workgroup,
        }

    def route(self, op: str, workload: Optional[Dict[str, Any]] = None) -> RouteDecision:
        """Route an operation by measured device capability."""
        work = dict(workload or {})
        items = int(work.get("work_items") or _DEFAULT_WORK_ITEMS)
        try:
            from hyba.math_ir.specs import get_spec

            discipline = get_spec(op).lucas_dispatch
        except KeyError:
            discipline = "ladder"

        def decide(
            device: DeviceInfo,
            capability: Optional[str],
            reason: str,
            cap_chunk: int = _DEFAULT_WORK_ITEMS,
        ) -> RouteDecision:
            if discipline == "serial":
                lucas = {}
            else:
                lucas = self._lucas_dispatch(
                    device, work_items=items, chunk_cap=cap_chunk
                )
                if discipline == "epoch32":
                    epochs = nearest_ladder_index(
                        max(1, items // _M32_LANES),
                        1,
                        max(1, cap_chunk // _M32_LANES),
                    )
                    lucas["chunk_size"] = _M32_LANES * epochs
                    lucas["on_ladder"] = is_ladder_index(epochs)
                    lucas["lucas_rung"] = next(
                        (
                            r
                            for r in sorted(CHRONUS_SCALE_RUNGS, reverse=True)
                            if epochs % r == 0
                        ),
                        None,
                    )
            return RouteDecision(
                op=op,
                device_name=device.name,
                backend=device.backend,
                capability=capability,
                lucas_dispatch=lucas,
                reason=reason,
            )

        if op in ("sha256d_grind", "sha256d_scan", "sha256d_window"):
            for device in self.devices:
                if device.type == "asic" and device.capability("mmio"):
                    return decide(device, "sha256d_fixed", "asic mmio first")
            device = self._best_gpu(required="m32_lane_kernel")
            if device is not None:
                return decide(
                    device,
                    "m32_lane_kernel",
                    "largest-CU OpenCL device with m32 kernel",
                )
            device = self._best_gpu()
            if device is not None:
                return decide(device, "sha256d_grind", "best measured GPU")
            return decide(self._cpu(), "hashlib_sha256d", "cpu fallback (no measured GPU)")

        if op == "m32_grind":
            device = self._best_gpu(required="m32_lane_kernel")
            if device is not None:
                return decide(device, "m32_lane_kernel", "m32 lane kernel present")
            return decide(
                self._cpu(), "hashlib_sha256d", "cpu fallback — serial m32 order"
            )

        punch_family = False
        try:
            punch_family = get_spec(op).executor == "unified_punch_host"
        except Exception:
            punch_family = False
        if op in ("unified_punch", "unified_punch_score", "score") or punch_family:
            device = self._best_gpu(required="fp64") or self._best_gpu()
            if device is not None:
                capability = "fp64" if device.capability("fp64") else "float"
                return decide(device, capability, "best float-capable device")
            return decide(self._cpu(), "numpy", "cpu fallback")

        if op == "unified_resident_state":
            for key in ("host_unified_memory", "opencl2_svm", "unified_memory"):
                candidates = self.inventory.by_capability(key)
                if candidates:
                    device = max(candidates, key=lambda d: d.compute_units or 0)
                    return decide(device, key, f"resident state needs {key}")
            return decide(
                self._cpu(), "host_memory", "cpu fallback — host buffer resident"
            )

        if op == "lucas_pisot_scale":
            device = self._best_gpu(required="lucas_ladder_kernel")
            if device is not None:
                return decide(device, "lucas_ladder_kernel", "ladder executor device")
            return decide(
                self._cpu(), "exact_math", "exact CPU ladder (Q[sqrt5] substrate)"
            )

        if op in ("grover_search", "search", "grover_iterate"):
            marked = int(work.get("marked") or 1)
            space = int(work.get("space") or items)
            scale_index = work.get("scale_index")
            lucas_value = 1
            if scale_index is not None:
                idx = int(scale_index)
                if idx not in LUCAS_SCALE_LADDER:
                    raise ValueError(
                        f"Lucas scale index {scale_index!r} is not a Chronus "
                        f"routing rung (one of {', '.join(str(r) for r in LUCAS_SCALE_LADDER)})"
                    )
                lucas_value = LUCAS_SCALE_LADDER[idx]
                space *= lucas_value
            depth = max(
                1,
                int(math.floor(math.pi / 4.0 * math.sqrt(space / max(marked, 1)))),
            )
            device = self._best_gpu() or self._cpu()
            decision = decide(device, "search", "largest compute for the sweep")
            decision.lucas_dispatch["grover_depth"] = depth
            if scale_index is not None:
                decision.lucas_dispatch["scale_index"] = int(scale_index)
                decision.lucas_dispatch["lucas_value"] = lucas_value
                decision.lucas_dispatch["scaled_space"] = space
            return decision

        return decide(self._cpu(), None, f"unrouted op {op!r} — cpu default")

    def execute(
        self,
        op: str,
        inputs: Optional[Dict[str, Any]] = None,
        workload: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Route and dispatch one operation, retaining full provenance."""
        from hyba.math_ir.executor import IRExecutor

        decision = self.route(op, workload)
        device = next(
            (d for d in self.devices if d.name == decision.device_name),
            self._cpu(),
        )
        executor = IRExecutor(device, op).compile()
        dispatch = dict(workload or {})
        dispatch["lucas_dispatch"] = dict(decision.lucas_dispatch)
        dispatch["capability_used"] = decision.capability
        result = executor.run(dict(inputs or {}), dispatch)
        if decision.reason.startswith("unrouted") or not decision.lucas_dispatch.get(
            "on_ladder"
        ):
            result.truth_class = "unconfigured"

        from hyba.attestation import attest_dispatch

        result.attestation = attest_dispatch(op=op, result=result, route=decision)
        return result

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": "chronus-fabric",
            "product": "Chronus",
            "compute_substrate": "chronus_execution_plane",
            "compute_units": self.compute_units,
            "global_mem_mb": self.global_mem_mb,
            "device_count": len(self.devices),
            "capability_map": self.capability_map(),
            "devices": [d.as_dict() for d in self.devices],
            "errors": dict(self.inventory.errors),
        }


__all__ = ["RouteDecision", "ChronusFabric"]
