"""Execution-only router for PYTHIA-issued resident Hendrix plans.

Extracted from geodesic_support without moving planning authority. This module
has no coordinator, Stratum client, learner or autonomous recovery policy.
"""

from __future__ import annotations
from dataclasses import replace
from collections import OrderedDict
from typing import Any
from chronus.resident_hendrix import ResidentHendrix, seal
from .execution_router import ExecutionRouter, FallbackReason, NONCE_ORDER_HENDRIX, RouteDecision
from .pythia_search import SEARCH_ARCHITECTURE_ID, PythiaSearchPrecompute
from .exact_search import precompute_exact_search as precompute_pythia_search
from .search_plan import ExecutionRoute

_PYTHIA_HENDRIX_COMPOSED = "pythia_hendrix_structured_composed"
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
            setattr(hasher, marker, method)


class ProductionExecutionRouter(ExecutionRouter):
    """Canonical router with exact PYTHIA itinerary and native GPU compatibility."""

    def __init__(
        self,
        hasher: Any,
        *args: Any,
        pythia_precompute: PythiaSearchPrecompute | None = None,
        **kwargs: Any,
    ) -> None:
        _bind_native_route_markers(hasher)
        self._pythia_precompute = pythia_precompute or precompute_pythia_search()
        self._resident_cache = OrderedDict()
        # The base router has a built-in pure-Hendrix branch. PYTHIA's
        # production route executes Hendrix over the complete structured
        # itinerary instead, so use an internal composite marker to reach
        # _run_chunk while the immutable SearchPlan remains Hendrix.
        kwargs["nonce_order"] = lambda plan: (
            _PYTHIA_HENDRIX_COMPOSED if self._is_pythia_lattice(plan) else plan.nonce_order
        )
        super().__init__(hasher, *args, **kwargs)

    @staticmethod
    def _is_pythia_lattice(plan) -> bool:
        return plan.evidence_refs.get("search_architecture") == SEARCH_ARCHITECTURE_ID

    def execute_plan(self, plan, header, target, **kwargs):
        """Clear prior fabric evidence before any freshness or lease gate can refuse work."""
        if self._is_pythia_lattice(plan) and hasattr(self._hasher, "last_batch_evidence"):
            self._hasher.last_batch_evidence = None
        fresh = kwargs.get("is_still_fresh")
        import time

        kwargs["is_still_fresh"] = lambda: (
            (plan.expires_at is None or time.monotonic() < plan.expires_at)
            and (fresh is None or fresh())
        )
        lease = kwargs.get("lease")
        if lease is not None and (lease.start != plan.base_step or lease.count != plan.window):
            raise ValueError("plan and nonce lease bounds differ")
        return super().execute_plan(plan, header, target, **kwargs)

    def _opencl_bound(self) -> bool:
        if _backend_name(self._hasher) in _NATIVE_BACKENDS:
            return True
        return super()._opencl_bound()

    def decide_route(self, plan):
        """Select physical execution while preserving Chronus as route authority."""
        backend = _backend_name(self._hasher)

        if (
            self._is_pythia_lattice(plan)
            and plan.executor_route == ExecutionRoute.chronus_batch.value
        ):
            if not callable(getattr(self._hasher,"grind_target_hendrix_plan",None)):
                raise RuntimeError("canonical Hendrix executor UNAVAILABLE; no authorised substitute")
            prov = self._device_provenance()
            batch = getattr(self._hasher, "grind_target_batch", None)
            cap = max(1, int(getattr(self._hasher, "grind_batch", 1) or 1))
            requested = ExecutionRoute.chronus_batch
            if backend in ("", "cpu", "cpu_reference") or not callable(batch):
                return RouteDecision(
                    requested_route=requested,
                    executed_route=ExecutionRoute.cpu_reference,
                    fallback_reason=FallbackReason.CHRONUS_BATCH_UNAVAILABLE,
                    device_backend="cpu_reference",
                    device_name=prov["device_name"],
                    device_vendor=prov["device_vendor"],
                    kernel_identity="hashlib_sha256d",
                    kernel_build_status="chronus_batch_unbound",
                    launch_cap=cap,
                )
            return RouteDecision(
                requested_route=requested,
                executed_route=requested,
                device_backend=prov["device_backend"],
                device_name=prov["device_name"],
                device_vendor=prov["device_vendor"],
                kernel_identity=f"chronus_ordered_batch_v1:{SEARCH_ARCHITECTURE_ID}",
                kernel_build_status="bound_contract_after_backend_self_check",
                launch_cap=cap,
            )

        decision = super().decide_route(plan)

        if (
            self._is_pythia_lattice(plan)
            and decision.executed_route is not ExecutionRoute.cpu_reference
        ):
            batch = getattr(self._hasher, "grind_target_batch", None)
            if callable(batch):
                return replace(
                    decision,
                    kernel_identity=(
                        f"pythia_explicit_nonce_batch:{backend or decision.device_backend}:"
                        f"{SEARCH_ARCHITECTURE_ID}"
                    ),
                    kernel_build_status="explicit_nonce_batch_bound_after_backend_self_check",
                    launch_cap=max(
                        1,
                        int(getattr(self._hasher, "grind_batch", 1) or 1),
                    ),
                )
            return RouteDecision(
                requested_route=decision.requested_route,
                executed_route=ExecutionRoute.cpu_reference,
                fallback_reason=FallbackReason.KERNEL_UNAVAILABLE,
                device_backend="cpu_reference",
                device_name=decision.device_name,
                device_vendor=decision.device_vendor,
                kernel_identity="hashlib_sha256d",
                kernel_build_status="explicit_nonce_batch_unavailable",
                launch_cap=max(
                    1,
                    int(getattr(self._hasher, "grind_batch", 1) or 1),
                ),
            )

        if (
            backend not in _NATIVE_BACKENDS
            or decision.executed_route is ExecutionRoute.cpu_reference
        ):
            return decision
        return replace(
            decision,
            kernel_identity=f"chronus_native_sha256d:{backend}:{decision.executed_route.value}",
            kernel_build_status="native_method_bound_after_backend_self_check",
        )

    def _run_chunk(self, plan, header, target, chunk, decision):
        """Execute PYTHIA's canonical Hendrix traversal on CPU or hardware."""
        if not self._is_pythia_lattice(plan):
            return super()._run_chunk(plan, header, target, chunk, decision)

        if plan.nonce_order != NONCE_ORDER_HENDRIX:
            raise RuntimeError("PYTHIA canonical search requires the Hendrix plan-bound order")
        raw = plan.evidence_refs.get("resident_hendrix")
        if raw is None:
            raise RuntimeError("PYTHIA must seal the resident Hendrix plan before dispatch")
        key = seal(raw)
        artifact = self._resident_cache.get(key)
        if artifact is None:
            artifact = ResidentHendrix.from_dict(raw)
            self._resident_cache[key] = artifact
            if len(self._resident_cache) > 4:
                self._resident_cache.popitem(last=False)
        artifact.require_context(plan, header, bytes(target)[::-1])
        position = chunk.start - plan.base_step
        if (
            callable(getattr(self._hasher, "grind_target_hendrix_plan", None))
            and decision.executed_route is not ExecutionRoute.cpu_reference
        ):
            result = self._hasher.grind_target_hendrix_plan(
                header, bytes(target)[::-1], artifact.as_dict(), position, chunk.count
            )
            return self._validate_ordered_result(artifact, position, chunk.count, result)
        raise RuntimeError("plan-bound Hendrix implementation UNAVAILABLE; no algorithm substitution")

    @staticmethod
    def _validate_ordered_result(artifact, position, count, result):
        nonce, digest, completed = result
        if type(completed) is not int or not 0 <= completed <= count:
            raise RuntimeError("invalid resident completed hash count")
        if nonce is None:
            if completed != count or digest is not None:
                raise RuntimeError("incomplete negative resident batch")
        elif type(nonce) is not int or nonce not in artifact.batch(position, completed)[0]:
            raise RuntimeError("candidate escaped the completed authorised order")
        return nonce, digest, completed

    def _build_record(self, plan, decision, requested_order, **kwargs):
        """Record Hendrix literally while retaining structure in plan evidence."""
        record = super()._build_record(plan, decision, requested_order, **kwargs)
        if not self._is_pythia_lattice(plan):
            return record
        executed = None if record.executed_nonce_order is None else plan.nonce_order
        observed=getattr(self._hasher,"last_batch_evidence",None)or {}
        contract=(plan.evidence_refs.get("resident_hendrix")or {}).get("execution_contract",{})
        return replace(
            record,
            candidate_nonce=kwargs.get("winner_nonce"),
            candidate_host_verified=bool(kwargs.get("locally_valid")),
            requested_nonce_order=plan.nonce_order,
            executed_nonce_order=executed,
            plan_digest=(plan.evidence_refs.get("resident_hendrix") or {}).get("plan_digest"),
            resident_execution_digest=(plan.evidence_refs.get("resident_hendrix") or {}).get(
                "digest"
            ),
            geometry_digest=(
                (plan.evidence_refs.get("resident_hendrix") or {}).get("geometry") or {}
            ).get("digest"),
            requested_algorithm=contract.get("requested_algorithm"),
            planned_algorithm=contract.get("planned_algorithm"),
            executed_algorithm=observed.get("executed_algorithm"),
            implementation_module=observed.get("implementation_module"),
            implementation_digest=observed.get("implementation_digest"),
            execution_mode=observed.get("execution_mode"),
            substrate=observed.get("substrate"),
            iterations_work_performed=observed.get("iterations_work_performed"),
            fallback_used=bool(observed.get("fallback_used")),
            execution_receipt_digest=observed.get("receipt_digest"),
        )
