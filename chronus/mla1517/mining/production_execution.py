"""Production execution compatibility for non-OpenCL accelerator lanes.

The historical route enum is named ``opencl_*`` because OpenCL was the first
accelerator substrate. Native CUDA and Metal now implement the same physical
M32/range method contracts, but the canonical router still keys availability
and its top evidence tier to OpenCL markers.

This module wires those native implementations into the production coordinator
without lying about their substrate:

* CUDA/Metal are eligible only after BackendRegistry has already constructed
  and self-checked the real hasher.
* route markers are bound to the hasher's actual callable methods; no marker is
  synthesized for an unimplemented arm.
* ``device_backend`` remains literally ``cuda`` or ``metal``.
* because ``ExecutionRecord.HARDWARE_EXECUTED`` is currently constrained to
  OpenCL/remote/ASIC evidence, native execution stays conservatively
  ``SOFTWARE_VERIFIED`` while retaining measured kernel launch count/time.
  A later evidence-schema migration may promote native lanes once that
  invariant is substrate-general; this adapter never mislabels CUDA/Metal as
  OpenCL merely to obtain a stronger-looking evidence class.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from chronus.mla1517.mining.execution_router import (
    ExecutionRouter,
    NONCE_ORDER_POINCARE_11D,
)
from chronus.mla1517.mining.geodesic_support import GeodesicProductionMiningCoordinator

_NATIVE_BACKENDS = frozenset({"cuda", "metal"})
_NATIVE_ROUTE_METHODS = {
    "k_gold": "grind_target_gold",
    "k_m32": "grind_target_m32",
    "k_range": "grind_target_range",
}


def _backend_name(hasher: Any) -> str:
    return str(getattr(hasher, "backend", "") or "").split(":", 1)[0].lower()


def _bind_native_route_markers(hasher: Any) -> None:
    """Expose only accelerator arms the native hasher can actually execute."""
    if _backend_name(hasher) not in _NATIVE_BACKENDS:
        return
    for marker, method_name in _NATIVE_ROUTE_METHODS.items():
        if getattr(hasher, marker, None) is not None:
            continue
        method = getattr(hasher, method_name, None)
        if callable(method):
            # ExecutionRouter uses marker presence as an availability proof;
            # binding the actual method keeps that proof executable.
            setattr(hasher, marker, method)


class ProductionExecutionRouter(ExecutionRouter):
    """ExecutionRouter that understands capability-proven native GPU lanes."""

    def __init__(self, hasher: Any, *args: Any, **kwargs: Any) -> None:
        _bind_native_route_markers(hasher)
        super().__init__(hasher, *args, **kwargs)

    def _opencl_bound(self) -> bool:
        # The inherited name is historical. CUDA/Metal have independent
        # runtimes and are *not* OpenCL; this merely admits them to the common
        # accelerator route contract after their constructor self-check.
        if _backend_name(self._hasher) in _NATIVE_BACKENDS:
            return True
        return super()._opencl_bound()

    def _build_record(self, *args: Any, **kwargs: Any):
        """Keep native hardware provenance truthful without evidence inflation.

        Parent ``_build_record`` promotes any non-CPU completed device route
        with launches to HARDWARE_EXECUTED. ``ExecutionRecord`` presently
        allows that tier only for OpenCL/remote/ASIC labels, so a truthful
        ``cuda``/``metal`` backend would be rejected. Build the record with a
        zero launch count to select the conservative software tier, then put
        the measured native launch count back. No physical work is hidden;
        only the assurance tier stays conservative.
        """
        launches = int(kwargs.get("launches", 0) or 0)
        if _backend_name(self._hasher) not in _NATIVE_BACKENDS or launches <= 0:
            return super()._build_record(*args, **kwargs)
        conservative = dict(kwargs)
        conservative["launches"] = 0
        record = super()._build_record(*args, **conservative)
        return replace(record, kernel_launch_count=launches)


class ProductionMiningCoordinator(GeodesicProductionMiningCoordinator):
    """Canonical coordinator with truthful native accelerator routing."""

    def _execution_route(self) -> str:
        # Poincare-11D has no accelerator kernel contract; preserve the
        # canonical CPU-only truth boundary from the parent coordinator.
        if self._nonce_order == NONCE_ORDER_POINCARE_11D:
            return super()._execution_route()
        hasher = self.execution_hasher
        if _backend_name(hasher) in _NATIVE_BACKENDS:
            _bind_native_route_markers(hasher)
            if getattr(hasher, "k_m32", None) is not None:
                return "opencl_m32"
            if getattr(hasher, "k_range", None) is not None:
                return "opencl_range"
            return "cpu_reference"
        return super()._execution_route()

    def _router_for(self, plan):
        """Reuse the parent's proof-correct CPU oracle with the production router."""
        base = super()._router_for(plan)
        return ProductionExecutionRouter(
            self.execution_hasher,
            base._cpu,
            freshness=base._freshness,
            nonce_order=base._nonce_order,
            cpu_nonce_executor=base._cpu_nonces,
        )
