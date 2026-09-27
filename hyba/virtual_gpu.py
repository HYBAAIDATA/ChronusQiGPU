"""HYBA virtual-GPU composition — the "Super-GPU" view of the inventory.

``SuperGPU.compose`` folds a :class:`~hyba.inventory.ClusterInventory` into
one composite device record: aggregate compute units, the union of measured
capabilities keyed to the best device for each, and an explicit route map.
Nothing here simulates hardware — a composite device reports only what its
members measured, and ``route`` returns an honest fallback device (the CPU)
when no member satisfies an op's requirements.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from Intelligence.lucas_scales import IGPU_SCALE_RUNGS, is_ladder_index, nearest_ladder_index
from hyba.inventory import ClusterInventory, DeviceInfo

# Default work-item quantum used when a caller supplies no workload size.
_DEFAULT_WORK_ITEMS = 1 << 20
# M32 lane count — dispatch chunks on the m32 path stay whole-epoch.
_M32_LANES = 32


@dataclass(frozen=True)
class RouteDecision:
    """One routed op: the device, the capability exercised, the dispatch."""

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


class SuperGPU:
    """A virtual device composed from every member of the inventory."""

    def __init__(self, inventory: ClusterInventory) -> None:
        self.inventory = inventory
        self.devices: List[DeviceInfo] = list(inventory.devices)

    @classmethod
    def compose(cls, inventory: Optional[ClusterInventory] = None) -> "SuperGPU":
        """Compose the measured census (collecting it when omitted)."""
        return cls(inventory if inventory is not None else ClusterInventory.collect())

    # -- composite view ----------------------------------------------------

    @property
    def compute_units(self) -> int:
        return sum(d.compute_units or 0 for d in self.devices)

    @property
    def global_mem_mb(self) -> int:
        return sum(d.global_mem_mb or 0 for d in self.devices)

    def capability_map(self) -> Dict[str, str]:
        """Capability -> device name that best serves it (union by merit).

        "Best" = most compute units among members holding the capability.
        """
        out: Dict[str, str] = {}
        merit: Dict[str, int] = {}
        for d in self.devices:
            for key in dict(d.capabilities):
                score = d.compute_units or 0
                if key not in out or score > merit[key]:
                    out[key] = d.name
                    merit[key] = score
        return out

    # -- routing ------------------------------------------------------------

    def _best_gpu(self, *, required: Optional[str] = None) -> Optional[DeviceInfo]:
        pool = [d for d in self.devices if d.type in ("gpu", "igpu") and d.backend != "rtl"]
        if required is not None:
            pool = [d for d in pool if d.capability(required) not in (None, False, 0)]
        if not pool:
            return None
        return max(pool, key=lambda d: d.compute_units or 0)

    def _cpu(self) -> Optional[DeviceInfo]:
        for d in self.devices:
            if d.backend == "cpu":
                return d
        return None

    def _lucas_dispatch(
        self,
        device: DeviceInfo,
        *,
        work_items: int,
        chunk_cap: int,
    ) -> Dict[str, Any]:
        """Derive the Lucas dispatch for one routed op.

        ``chunk_size`` snaps to a ladder index within the device/policy
        bound; ``workgroup_size`` never exceeds the measured max_workgroup;
        m32 chunks are multiples of 32 whole epochs. ``lucas_rung`` is the
        largest rung dividing the chunk (or None when off-ladder — callers
        must then mark the dispatch unconfigured).
        """
        items = max(1, int(work_items))
        chunk = nearest_ladder_index(min(items, chunk_cap), 1, max(1, chunk_cap))
        rung = next(
            (r for r in sorted(IGPU_SCALE_RUNGS, reverse=True) if chunk % r == 0),
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
        """Route ``op`` to the best member device by measured capability.

        ``workload`` may carry ``work_items`` / ``window_bits`` / ``marked``
        (for search ops). The decision names the capability exercised so the
        attestation layer can stamp it.
        """
        work = dict(workload or {})
        items = int(work.get("work_items") or _DEFAULT_WORK_ITEMS)
        try:
            from hyba.math_ir.specs import get_spec

            discipline = get_spec(op).lucas_dispatch
        except KeyError:
            discipline = "ladder"

        def decide(dev: DeviceInfo, cap: str, reason: str, cap_chunk: int = _DEFAULT_WORK_ITEMS) -> RouteDecision:
            # Serial ops derive no chunk config — honestly unconfigured.
            if discipline == "serial":
                lucas = {}
            else:
                lucas = self._lucas_dispatch(dev, work_items=items, chunk_cap=cap_chunk)
                if discipline == "epoch32":
                    # Chunk = whole 32-lane epochs; the epoch count itself
                    # snaps to the ladder (same convention as BitcoinHasher).
                    epochs = nearest_ladder_index(
                        max(1, items // _M32_LANES), 1, max(1, cap_chunk // _M32_LANES)
                    )
                    lucas["chunk_size"] = _M32_LANES * epochs
                    lucas["on_ladder"] = is_ladder_index(epochs)
                    lucas["lucas_rung"] = next(
                        (r for r in sorted(IGPU_SCALE_RUNGS, reverse=True) if epochs % r == 0),
                        None,
                    )
            return RouteDecision(
                op=op,
                device_name=dev.name,
                backend=dev.backend,
                capability=cap,
                lucas_dispatch=lucas,
                reason=reason,
            )

        if op in ("sha256d_grind", "sha256d_scan", "sha256d_window"):
            for dev in self.devices:
                if dev.type == "asic" and dev.capability("mmio"):
                    return decide(dev, "sha256d_fixed", "asic mmio first")
            dev = self._best_gpu(required="m32_lane_kernel")
            if dev is not None:
                return decide(dev, "m32_lane_kernel", "largest-CU OpenCL with m32 kernel")
            dev = self._best_gpu()
            if dev is not None:
                return decide(dev, "sha256d_grind", "best measured GPU")
            cpu = self._cpu()
            assert cpu is not None
            return decide(cpu, "hashlib_sha256d", "cpu fallback (no measured GPU)")

        if op == "m32_grind":
            dev = self._best_gpu(required="m32_lane_kernel")
            if dev is not None:
                return decide(dev, "m32_lane_kernel", "m32 lane kernel present")
            cpu = self._cpu()
            assert cpu is not None
            return decide(cpu, "hashlib_sha256d", "cpu fallback — serial m32 order")

        punch_family = False
        try:
            punch_family = get_spec(op).executor == "unified_punch_host"
        except Exception:
            punch_family = False
        if op in ("unified_punch", "unified_punch_score", "score") or punch_family:
            dev = self._best_gpu(required="fp64") or self._best_gpu()
            if dev is not None:
                cap = "fp64" if dev.capability("fp64") else "float"
                return decide(dev, cap, "best float-capable device")
            cpu = self._cpu()
            assert cpu is not None
            return decide(cpu, "numpy", "cpu fallback")

        if op == "unified_resident_state":
            for key in ("host_unified_memory", "opencl2_svm", "unified_memory"):
                cands = self.inventory.by_capability(key)
                if cands:
                    dev = max(cands, key=lambda d: d.compute_units or 0)
                    return decide(dev, key, f"resident state needs {key}")
            cpu = self._cpu()
            assert cpu is not None
            return decide(cpu, "host_memory", "cpu fallback — host buffer resident")

        if op == "lucas_pisot_scale":
            dev = self._best_gpu(required="lucas_ladder_kernel")
            if dev is not None:
                return decide(dev, "lucas_ladder_kernel", "ladder executor device")
            cpu = self._cpu()
            assert cpu is not None
            return decide(cpu, "exact_math", "exact CPU ladder (Q[sqrt5] substrate)")

        if op in ("grover_search", "search", "grover_iterate"):
            marked = int(work.get("marked") or 1)
            space = int(work.get("space") or items)
            depth = max(1, int(math.floor(math.pi / 4.0 * math.sqrt(space / max(marked, 1)))))
            dev = self._best_gpu() or self._cpu()
            assert dev is not None
            decision = decide(dev, "search", "largest compute for the sweep")
            decision.lucas_dispatch["grover_depth"] = depth
            return decision

        cpu = self._cpu()
        assert cpu is not None
        return decide(cpu, None, f"unrouted op {op!r} — cpu default")

    def execute(
        self,
        op: str,
        inputs: Optional[Dict[str, Any]] = None,
        workload: Optional[Dict[str, Any]] = None,
    ) -> "Any":
        """Route ``op`` and dispatch it on the selected member device.

        This is the substrate's composition dispatch: ``route`` picks the
        device by measured capability, ``IRExecutor`` binds the spec to
        that device (failing explicitly when it lacks a required
        capability), and the returned :class:`OpResult` carries the full
        dispatch provenance including the derived Lucas configuration —
        or ``truth_class == "unconfigured"`` when no Lucas dispatch was
        derivable.
        """
        from hyba.math_ir.executor import IRExecutor

        decision = self.route(op, workload)
        device = next(
            (d for d in self.devices if d.name == decision.device_name),
            self._cpu(),
        )
        assert device is not None
        executor = IRExecutor(device, op).compile()
        dispatch = dict(workload or {})
        dispatch["lucas_dispatch"] = dict(decision.lucas_dispatch)
        dispatch["capability_used"] = decision.capability
        result = executor.run(dict(inputs or {}), dispatch)
        # A dispatch that never derived a Lucas chunk config — unrouted op
        # or off-ladder chunk — is honestly unconfigured, not "measured".
        if decision.reason.startswith("unrouted") or not decision.lucas_dispatch.get(
            "on_ladder"
        ):
            result.truth_class = "unconfigured"
        # Every dispatched op attests — the receipt layer of the substrate.
        from hyba.attestation import attest_dispatch

        result.attestation = attest_dispatch(op=op, result=result, route=decision)
        return result

    # -- report --------------------------------------------------------------

    def as_dict(self) -> Dict[str, Any]:
        return {
            "name": "hyba-super-gpu",
            "compute_units": self.compute_units,
            "global_mem_mb": self.global_mem_mb,
            "device_count": len(self.devices),
            "capability_map": self.capability_map(),
            "devices": [d.as_dict() for d in self.devices],
            "errors": dict(self.inventory.errors),
        }


__all__ = ["RouteDecision", "SuperGPU"]
