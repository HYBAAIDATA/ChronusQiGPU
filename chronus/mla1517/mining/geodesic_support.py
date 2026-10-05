"""PYTHIA production search, geodesic ordering and accelerator seam.

The production composition is intentionally layered:

* PYTHIA owns mining cognition, search topology, planning context and learning.
* The canonical search architecture is precomputed before pool work starts:
  dodecahedron/icosahedron dual overlay -> 11D manifold -> 600 dual vertices
  -> 11-qubit Hilbert addresses.
* Chronus owns physical execution and consumes the exact nonce batches PYTHIA
  authorises. Vendor runtimes may exist beneath Chronus only after their normal
  capability/self-check gate; they do not define the Chronus architecture.
* EUCLID remains the wider enterprise-intelligence orchestrator and a bounded
  advisory layer inherited by this coordinator; it is not the mining identity.
* SHA256d, target comparison, freshness and literal pool acknowledgement remain
  external truth authorities. Search geometry never becomes proof authority.

The canonical PYTHIA lattice uses the first-class ``chronus_batch`` execution
route whenever the bound Chronus substrate can consume explicit nonce batches.
The physical backend remains separate provenance and is never used as the
architectural identity of Chronus.
"""
from __future__ import annotations

import os
from dataclasses import replace
from typing import Any

from python_backend.core_modules.geodesic_tensor_engine import GeodesicNoncePlanner
from .euclid_support import EuclidProductionMiningCoordinator
from .execution_router import (
    ExecutionRouter,
    FallbackReason,
    NONCE_ORDER_HENDRIX,
    NONCE_ORDER_M32,
    NONCE_ORDER_POINCARE_11D,
    RouteDecision,
)
from .pythia_search import (
    SEARCH_ARCHITECTURE_ID,
    PythiaSearchPrecompute,
    precompute_pythia_search,
    pythia_hilbert_600_nonces,
)
from .search_plan import ExecutionRoute

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
    """Canonical router with exact PYTHIA itinerary and Chronus batch execution."""

    def __init__(
        self,
        hasher: Any,
        *args: Any,
        pythia_precompute: PythiaSearchPrecompute | None = None,
        **kwargs: Any,
    ) -> None:
        _bind_native_route_markers(hasher)
        self._pythia_precompute = pythia_precompute or precompute_pythia_search()
        self._pythia_order_cache: dict[str, list[int]] = {}
        kwargs["nonce_order"] = lambda plan: plan.nonce_order
        super().__init__(hasher, *args, **kwargs)

    @staticmethod
    def _is_pythia_lattice(plan) -> bool:
        return plan.evidence_refs.get("search_architecture") == SEARCH_ARCHITECTURE_ID

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
        """Execute the exact 600-vertex itinerary on CPU or Chronus batch execution."""
        if not self._is_pythia_lattice(plan):
            return super()._run_chunk(plan, header, target, chunk, decision)

        order = self._pythia_order_cache.get(plan.plan_id)
        if order is None:
            order = pythia_hilbert_600_nonces(
                header,
                plan.base_step,
                plan.window,
                precompute=self._pythia_precompute,
                preferred_face=plan.preferred_face,
            )
            self._pythia_order_cache[plan.plan_id] = order
        position = (chunk.start - plan.base_step) & 0xFFFFFFFF
        nonces = order[position : position + chunk.count]
        if len(nonces) != chunk.count:
            raise RuntimeError("PYTHIA itinerary chunk does not match the leased window")

        if decision.executed_route is ExecutionRoute.cpu_reference:
            return self._cpu_nonces(header, target, nonces)
        batch = getattr(self._hasher, "grind_target_batch", None)
        if not callable(batch):
            raise RuntimeError("selected Chronus route cannot execute explicit nonce batches")
        return batch(header, bytes(target)[::-1], nonces)

    def _build_record(self, plan, decision, requested_order, **kwargs):
        """Make the executed search identity literal in the evidence record."""
        record = super()._build_record(plan, decision, requested_order, **kwargs)
        if not self._is_pythia_lattice(plan):
            return record
        executed = None if record.executed_nonce_order is None else SEARCH_ARCHITECTURE_ID
        return replace(
            record,
            requested_nonce_order=SEARCH_ARCHITECTURE_ID,
            executed_nonce_order=executed,
        )


class PythiaProductionMiningCoordinator(EuclidProductionMiningCoordinator):
    """Canonical production composition root for PYTHIA's agentic mining workforce."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Static topology/Hilbert work is complete before the inherited runtime
        # can connect to Stratum. Failure is therefore a startup failure, not a
        # half-live miner constructing its search substrate after mining.notify.
        self.pythia_search_precompute = precompute_pythia_search()
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
        self.geodesic_planner = GeodesicNoncePlanner(
            fold_depth=max(0, min(depth, 32))
        )
        self._geodesic_state: dict[str, Any] = {
            "state": "ENABLED" if self.geodesic_enabled else "DISABLED",
            "consensus_authority": False,
            "claim_boundary": "candidate ordering advice only",
            "last_error": None,
            "last_report": None,
        }

    def _observed_candidate_window(self) -> list[int]:
        baseline = super()._observed_candidate_window()
        if not self.geodesic_enabled or len(baseline) < 2:
            return baseline
        try:
            ordered = self.geodesic_planner.order_window(
                baseline,
                anchor=self._base_step,
            )
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
        """Select an executable route from measured capability, never a label."""
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

    def _pythia_batch_route(self) -> str:
        """Chronus route for the exact 600-vertex itinerary, or explicit CPU fallback."""
        hasher = self.execution_hasher
        backend = _backend_name(hasher)
        if backend in ("", "cpu", "cpu_reference") or not callable(
            getattr(hasher, "grind_target_batch", None)
        ):
            return "cpu_reference"
        return "chronus_batch"

    def _bind_plan_execution_intent(self, plan):
        """Seal PYTHIA's precomputed search architecture into every immutable plan."""
        decision = getattr(self, "last_mining_decision", None)
        refs = dict(plan.evidence_refs)
        refs["search_architecture"] = SEARCH_ARCHITECTURE_ID
        refs["search_precompute_digest"] = self.pythia_search_precompute.digest
        refs["configured_traversal_refinement"] = self._nonce_order
        refs["technology_intent"] = {
            "composition_root": "PYTHIA",
            "execution_authority": "CHRONUS",
            "execution_contract": "chronus_batch",
            "search_architecture": SEARCH_ARCHITECTURE_ID,
            "coarse_overlay": "dodecahedron_12_plus_icosahedron_20",
            "manifold": "phi_weighted_11d_poincare_ball",
            "dual_vertices": 600,
            "hilbert_space": "11_qubits_C^2048",
            "preferred_face": plan.preferred_face,
            "mining_policy": getattr(decision, "lead", None),
            "candidate_ordering_advice": (
                getattr(
                    getattr(decision, "policy", None),
                    "candidate_ordering",
                    None,
                )
                if decision is not None
                else None
            ),
            "geodesic_advice_enabled": bool(self.geodesic_enabled),
            "proof_authority": (
                "sha256d_target_freshness_and_literal_pool_response_only"
            ),
        }
        # M32 remains only the inherited ordering carrier. Physical execution
        # is the vendor-neutral Chronus batch route when that contract is bound.
        return replace(
            plan,
            nonce_order=NONCE_ORDER_M32,
            executor_route=self._pythia_batch_route(),
            evidence_refs=refs,
        )

    def _baseline_plan(self, identity, lease, window, reason):
        return self._bind_plan_execution_intent(
            super()._baseline_plan(identity, lease, window, reason)
        )

    def _build_plan(self, identity):
        plan = super()._build_plan(identity)
        return None if plan is None else self._bind_plan_execution_intent(plan)

    def _router_for(self, plan):
        """Preserve the parent's proof oracle and replace only production routing."""
        base = super()._router_for(plan)
        return ProductionExecutionRouter(
            self.execution_hasher,
            base._cpu,
            freshness=base._freshness,
            cpu_nonce_executor=base._cpu_nonces,
            pythia_precompute=self.pythia_search_precompute,
        )

    def _technology_utilization_snapshot(self) -> dict[str, Any]:
        audit = self.policy_audit.snapshot()
        backend = _backend_name(self.execution_hasher)
        return {
            "schema": "pythia.mining_technology_utilization/3",
            "composition_root": "PYTHIA",
            "execution_authority": "CHRONUS",
            "enterprise_intelligence_orchestrator": "EUCLID",
            "truth_boundary": (
                "PYTHIA directs the mining workforce and search architecture; "
                "Chronus executes; Salamander heals/optimises; SHA256d/Stratum "
                "establish proof and pool truth"
            ),
            "canonical_search": self.pythia_search_precompute.summary(),
            "execution": {
                "route": self._pythia_batch_route(),
                "contract": "ordered_explicit_nonce_batch",
                "physical_backend": backend or None,
                "vendor_runtime_is_adapter_only": True,
            },
            "discoveries": {
                "dodecahedron_icosahedron_overlay": {
                    "state": "ACTIVE_CANONICAL_ROOT",
                    "authority": "32 coarse search directions",
                },
                "poincare_phi_11d_manifold": {
                    "state": "ACTIVE_CANONICAL_ROOT",
                    "authority": "search geometry / ranking only",
                },
                "h4_dual_600_vertices": {
                    "state": "ACTIVE_PRECOMPUTED",
                    "authority": "600 high-resolution search vertices",
                },
                "hilbert_11_qubit_address_space": {
                    "state": "ACTIVE_PRECOMPUTED",
                    "authority": "injective 600-vertex itinerary in C^2048",
                },
                "cassini_affine_coverage": {
                    "state": "ACTIVE",
                    "authority": "coverage-preserving local shard permutation",
                },
                "hendrix_coprime_search": {
                    "state": "AVAILABLE_REFINEMENT",
                    "authority": (
                        "legacy/alternative traversal refinement, not search identity"
                    ),
                },
                "m32_dual_solid_lane_topology": {
                    "state": "ACTIVE_SUPPORTING_TOPOLOGY",
                    "authority": (
                        "coarse lane/accelerator compatibility, not canonical search identity"
                    ),
                },
                "geodesic_candidate_advice": {
                    "state": self._geodesic_state.get("state", "Unavailable"),
                    "authority": "bounded chooser advice; membership preserving",
                },
                "toe_causal_steering": {
                    "state": (
                        "ACTIVE"
                        if self.last_toe_frame is not None
                        else "AVAILABLE_UNBOUND"
                    ),
                    "authority": "advisory face bias / throttle only",
                },
                "turing_vqc_policy_audit": {
                    "state": (
                        "ACTIVE_AUDITING"
                        if audit.get("audits", 0) > 0
                        else (
                            "AVAILABLE_AWAITING_AUDIT_INTERVAL"
                            if audit.get("vqc_available")
                            else "UNAVAILABLE"
                        )
                    ),
                    "authority": "independent policy cross-check; disagreement never acts",
                },
                "lucas_scale_ladder": {
                    "state": "ACTIVE",
                    "authority": "bounded window ceiling / rung budget",
                },
                "agentic_mining_workforce": {
                    "state": "ACTIVE",
                    "authority": "PYTHIA composition; bounded role-specific agents",
                },
                "closed_loop_optimizer": {
                    "state": "ACTIVE_MEASURED_GATE",
                    "authority": "bounded mining-window retain/rollback",
                },
                "salamander_recovery": {
                    "state": "ACTIVE_MONITORING",
                    "authority": "bounded recovery / reprobe / fail-closed return",
                },
                "native_cuda_execution": {
                    "state": (
                        "ACTIVE" if backend == "cuda" else "GATED_BY_CAPABILITY_PROBE"
                    ),
                    "authority": (
                        "physical SHA256d execution beneath the Chronus batch contract"
                    ),
                },
                "native_metal_execution": {
                    "state": (
                        "ACTIVE" if backend == "metal" else "GATED_BY_CAPABILITY_PROBE"
                    ),
                    "authority": (
                        "physical SHA256d execution beneath the Chronus batch contract"
                    ),
                },
            },
        }

    def evidence_snapshot(self) -> dict[str, Any]:
        snapshot = super().evidence_snapshot()
        snapshot["pythia_search_precompute"] = self.pythia_search_precompute.summary()
        snapshot["pythia_agentic_workforce"] = (
            self.pythia_search_precompute.workforce_manifest()
        )
        snapshot["geodesic_ordering"] = dict(self._geodesic_state)
        snapshot["technology_utilization"] = self._technology_utilization_snapshot()
        snapshot["chronus_execution"] = {
            "authority": "CHRONUS",
            "route": self._pythia_batch_route(),
            "physical_backend": _backend_name(self.execution_hasher) or None,
            "canonical_search_consumption": "explicit_nonce_batch",
            "vendor_runtime_is_adapter_only": True,
            "hardware_evidence_rule": (
                "HARDWARE_EXECUTED only after measured kernel_launch_count > 0 "
                "and completed_work_items > 0"
            ),
        }
        return snapshot


# Compatibility name for existing imports and old tests. The class identity is
# PYTHIA; new code should import PythiaProductionMiningCoordinator directly.
GeodesicProductionMiningCoordinator = PythiaProductionMiningCoordinator

__all__ = [
    "PythiaProductionMiningCoordinator",
    "GeodesicProductionMiningCoordinator",
    "ProductionExecutionRouter",
]
