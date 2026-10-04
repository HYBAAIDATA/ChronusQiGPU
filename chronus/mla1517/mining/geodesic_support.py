"""Geodesic ordering and production accelerator seam.

The geodesic planner is deliberately downstream of real solver coverage and
upstream of chooser ordering. It can only return a permutation of the candidate
window already produced by the canonical solver. On any error the exact
baseline window is returned unchanged.

This module is also the final production coordinator composition seam. Native
CUDA and Metal hashers implement the same M32/range callable contract as the
historical OpenCL routes, but the route enum and top evidence tier still carry
OpenCL-era names. The compatibility below executes those native methods without
mislabeling their physical substrate or inflating their assurance class.
"""
from __future__ import annotations

import os
from dataclasses import replace
from typing import Any

from python_backend.core_modules.geodesic_tensor_engine import GeodesicNoncePlanner
from .euclid_support import EuclidProductionMiningCoordinator
from .execution_router import ExecutionRouter, NONCE_ORDER_POINCARE_11D

_NATIVE_BACKENDS = frozenset({"cuda", "metal"})
_NATIVE_ROUTE_METHODS = {
    "k_gold": "grind_target_gold",
    "k_m32": "grind_target_m32",
    "k_range": "grind_target_range",
}


def _backend_name(hasher: Any) -> str:
    return str(getattr(hasher, "backend", "") or "").split(":", 1)[0].lower()


def _bind_native_route_markers(hasher: Any) -> None:
    """Expose only route arms the capability-proven native hasher can run."""
    if _backend_name(hasher) not in _NATIVE_BACKENDS:
        return
    for marker, method_name in _NATIVE_ROUTE_METHODS.items():
        if getattr(hasher, marker, None) is not None:
            continue
        method = getattr(hasher, method_name, None)
        if callable(method):
            # ExecutionRouter uses marker presence as route availability.
            # Bind the actual method rather than inventing a dummy capability.
            setattr(hasher, marker, method)


class ProductionExecutionRouter(ExecutionRouter):
    """Canonical router with truthful native CUDA/Metal route compatibility."""

    def __init__(self, hasher: Any, *args: Any, **kwargs: Any) -> None:
        _bind_native_route_markers(hasher)
        super().__init__(hasher, *args, **kwargs)

    def _opencl_bound(self) -> bool:
        # The inherited method name is historical. CUDA/Metal are independent
        # runtimes and are never reported as OpenCL; this only admits them to
        # the shared accelerator-method contract after constructor self-check.
        if _backend_name(self._hasher) in _NATIVE_BACKENDS:
            return True
        return super()._opencl_bound()

    def _build_record(self, *args: Any, **kwargs: Any):
        """Keep native provenance truthful without abusing an OpenCL-only tier.

        ExecutionRecord currently permits HARDWARE_EXECUTED only for its
        OpenCL/remote/ASIC backend set. A truthful ``cuda`` or ``metal`` label
        would therefore be rejected after a real launch. Build the record at
        the conservative SOFTWARE_VERIFIED tier, then restore the *measured*
        native launch count. The backend label, kernel time and work counters
        remain literal; only the assurance tier is deliberately under-claimed
        until the evidence schema is made substrate-general.
        """
        launches = int(kwargs.get("launches", 0) or 0)
        if _backend_name(self._hasher) not in _NATIVE_BACKENDS or launches <= 0:
            return super()._build_record(*args, **kwargs)
        conservative = dict(kwargs)
        conservative["launches"] = 0
        record = super()._build_record(*args, **conservative)
        return replace(record, kernel_launch_count=launches)


class GeodesicProductionMiningCoordinator(EuclidProductionMiningCoordinator):
    """EUCLID production coordinator with geodesic and native-GPU routing."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.geodesic_enabled = os.getenv("PYTHIA_GEODESIC_ORDERING", "1").strip() not in {
            "0",
            "false",
            "False",
            "off",
            "OFF",
        }
        try:
            depth = int(os.getenv("PYTHIA_GEODESIC_FOLD_DEPTH", "3"))
        except ValueError:
            depth = 3
        self.geodesic_planner = GeodesicNoncePlanner(fold_depth=max(0, min(depth, 32)))
        self._geodesic_state: dict[str, Any] = {
            "state": "ENABLED" if self.geodesic_enabled else "DISABLED",
            "consensus_authority": False,
            "claim_boundary": "candidate ordering only",
            "last_error": None,
            "last_report": None,
        }

    def _observed_candidate_window(self) -> list[int]:
        baseline = super()._observed_candidate_window()
        if not self.geodesic_enabled or len(baseline) < 2:
            return baseline
        try:
            ordered = self.geodesic_planner.order_window(baseline, anchor=self._base_step)
        except Exception as exc:
            self._geodesic_state = {
                **self._geodesic_state,
                "state": "DEGRADED_BASELINE",
                "last_error": f"{type(exc).__name__}: {exc}",
                "last_report": None,
            }
            return baseline
        if len(ordered) != len(baseline) or sorted(ordered) != sorted(baseline):
            self._geodesic_state = {
                **self._geodesic_state,
                "state": "DEGRADED_BASELINE",
                "last_error": "planner did not preserve candidate membership",
                "last_report": None,
            }
            return baseline
        self._geodesic_state = {
            **self._geodesic_state,
            "state": "ACTIVE",
            "last_error": None,
            "last_report": self.geodesic_planner.last_report,
        }
        return ordered

    def _execution_route(self) -> str:
        """Select an executable route from the hasher's measured capability."""
        if self._nonce_order == NONCE_ORDER_POINCARE_11D:
            # No accelerator implements the canonical 11D face-ranked order.
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
        """Preserve the parent's CPU proof oracle; replace only the router seam."""
        base = super()._router_for(plan)
        return ProductionExecutionRouter(
            self.execution_hasher,
            base._cpu,
            freshness=base._freshness,
            nonce_order=base._nonce_order,
            cpu_nonce_executor=base._cpu_nonces,
        )

    def evidence_snapshot(self) -> dict[str, Any]:
        snapshot = super().evidence_snapshot()
        snapshot["geodesic_ordering"] = dict(self._geodesic_state)
        backend = _backend_name(self.execution_hasher)
        if backend in _NATIVE_BACKENDS:
            snapshot["native_execution"] = {
                "backend": backend,
                "route": self._execution_route(),
                "physical_backend_truthful": True,
                "hardware_evidence_class": "SOFTWARE_VERIFIED_PENDING_SCHEMA_GENERALISATION",
            }
        return snapshot


__all__ = ["GeodesicProductionMiningCoordinator", "ProductionExecutionRouter"]
