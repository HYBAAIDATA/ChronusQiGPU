"""Geodesic ordering and production accelerator seam.

The geodesic planner is deliberately downstream of real solver coverage and
upstream of chooser ordering. It can only return a permutation of the candidate
window already produced by the canonical solver. On any error the exact
baseline window is returned unchanged.

This module is also the final production coordinator composition seam. Native
CUDA and Metal hashers implement the same M32/range callable contract as the
historical OpenCL routes. The compatibility below executes those native methods
without mislabeling their physical substrate. Search-order intent is bound into
the immutable SearchPlan before dispatch, so queued work cannot be silently
reinterpreted by later coordinator state.
"""
from __future__ import annotations

import os
from dataclasses import replace
from typing import Any

from python_backend.core_modules.geodesic_tensor_engine import GeodesicNoncePlanner
from .euclid_support import EuclidProductionMiningCoordinator
from .execution_router import (
    ExecutionRouter,
    NONCE_ORDER_HENDRIX,
    NONCE_ORDER_M32,
    NONCE_ORDER_POINCARE_11D,
)

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
    """Canonical router with plan-bound ordering and native GPU compatibility."""

    def __init__(self, hasher: Any, *args: Any, **kwargs: Any) -> None:
        _bind_native_route_markers(hasher)
        # Production SearchPlans now own WHICH ORDER. Ignore mutable/global
        # coordinator callbacks at execution time and consume the immutable
        # plan field instead. Generic ExecutionRouter users retain their
        # injectable callback; this rule is specific to the production seam.
        kwargs["nonce_order"] = lambda plan: plan.nonce_order
        super().__init__(hasher, *args, **kwargs)

    def _opencl_bound(self) -> bool:
        # The inherited method name is historical. CUDA/Metal are independent
        # runtimes and are never reported as OpenCL; this only admits them to
        # the shared accelerator-method contract after constructor self-check.
        if _backend_name(self._hasher) in _NATIVE_BACKENDS:
            return True
        return super()._opencl_bound()

    def decide_route(self, plan):
        """Use the legacy route token while keeping native kernel provenance literal."""
        decision = super().decide_route(plan)
        backend = _backend_name(self._hasher)
        if backend not in _NATIVE_BACKENDS or decision.executed_route.value == "cpu_reference":
            return decision
        return replace(
            decision,
            kernel_identity=f"chronus_native_sha256d:{backend}:{decision.executed_route.value}",
            kernel_build_status="native_method_bound_after_backend_self_check",
        )


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

    def _bind_plan_execution_intent(self, plan):
        """Seal discovery/search intent into the immutable production plan.

        Intelligence and configured search policy may decide HOW to traverse a
        leased window, but neither can alter SHA256d, target comparison, Stratum
        freshness or pool truth. Binding the nonce order here makes that intent
        replayable and prevents execution from consulting mutable strategy state.
        """
        decision = getattr(self, "last_mining_decision", None)
        refs = dict(plan.evidence_refs)
        refs["requested_nonce_order"] = self._nonce_order
        refs["technology_intent"] = {
            "nonce_order": self._nonce_order,
            "mining_policy": getattr(decision, "lead", None),
            "candidate_ordering": (
                getattr(getattr(decision, "policy", None), "candidate_ordering", None)
                if decision is not None
                else None
            ),
            "geodesic_enabled": bool(self.geodesic_enabled),
            "proof_authority": "sha256d_target_and_literal_pool_response_only",
        }
        return replace(plan, nonce_order=self._nonce_order, evidence_refs=refs)

    def _baseline_plan(self, identity, lease, window, reason):
        return self._bind_plan_execution_intent(
            super()._baseline_plan(identity, lease, window, reason)
        )

    def _build_plan(self, identity):
        plan = super()._build_plan(identity)
        return None if plan is None else self._bind_plan_execution_intent(plan)

    def _router_for(self, plan):
        """Preserve the parent's CPU proof oracle; replace only the router seam."""
        base = super()._router_for(plan)
        return ProductionExecutionRouter(
            self.execution_hasher,
            base._cpu,
            freshness=base._freshness,
            cpu_nonce_executor=base._cpu_nonces,
        )

    def _technology_utilization_snapshot(self) -> dict[str, Any]:
        """Truth-labelled use of mining discoveries in the canonical runtime.

        ACTIVE means the capability is on the production path at the authority
        stated here. AVAILABLE_NOT_SELECTED and GATED states are deliberate:
        forcing unmeasured research into control would be under-governed use,
        not fuller utilisation.
        """
        selected_order = self._nonce_order
        audit = self.policy_audit.snapshot()
        backend = _backend_name(self.execution_hasher)
        return {
            "schema": "pythia.mining_technology_utilization/1",
            "scope": "canonical production mining runtime",
            "truth_boundary": (
                "discoveries may steer ordering, allocation, execution, recovery and audit; "
                "only SHA256d/target/freshness and literal pool responses establish mining truth"
            ),
            "discoveries": {
                "hendrix_coprime_search": {
                    "state": (
                        "ACTIVE" if selected_order == NONCE_ORDER_HENDRIX else "AVAILABLE_NOT_SELECTED"
                    ),
                    "authority": "nonce ordering only",
                    "evidence": "SearchPlan.nonce_order -> ExecutionRecord requested/executed_nonce_order",
                },
                "m32_dual_solid_lane_topology": {
                    "state": "ACTIVE_SUPPORTING_TOPOLOGY",
                    "authority": "lane ordering / accelerator dispatch only",
                    "evidence": "SearchPlan.lane_order + dispatch certificate + execution record",
                },
                "poincare_cassini_11d": {
                    "state": (
                        "ACTIVE_CPU_REFERENCE"
                        if selected_order == NONCE_ORDER_POINCARE_11D
                        else "AVAILABLE_NOT_SELECTED"
                    ),
                    "authority": "nonce ordering only",
                    "evidence": "plan-bound order; CPU route enforced when selected",
                },
                "geodesic_candidate_ordering": {
                    "state": self._geodesic_state.get("state", "Unavailable"),
                    "authority": "candidate permutation only",
                    "evidence": "membership-preservation gate + geodesic_ordering telemetry",
                },
                "toe_causal_steering": {
                    "state": "ACTIVE" if self.last_toe_frame is not None else "AVAILABLE_UNBOUND",
                    "authority": "advisory face bias / throttle only",
                    "evidence": "TOE frame digest + signal binding; never proof",
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
                    "evidence": "Kellogg-attested policy_audit receipt",
                },
                "lucas_scale_ladder": {
                    "state": "ACTIVE",
                    "authority": "bounded window ceiling / rung budget",
                    "evidence": "window_basis + solver rung budget",
                },
                "closed_loop_optimizer": {
                    "state": "ACTIVE_MEASURED_GATE",
                    "authority": "bounded mining-window retain/rollback",
                    "evidence": "optimization trial history",
                },
                "salamander_recovery": {
                    "state": "ACTIVE_MONITORING",
                    "authority": "bounded recovery / reprobe / fail-closed return",
                    "evidence": "RecoveryGovernor + SelfHealingAgent records",
                },
                "native_cuda_execution": {
                    "state": "ACTIVE" if backend == "cuda" else "GATED_BY_CAPABILITY_PROBE",
                    "authority": "physical SHA256d execution only",
                    "evidence": "backend self-check + measured launch/work before HARDWARE_EXECUTED",
                },
                "native_metal_execution": {
                    "state": "ACTIVE" if backend == "metal" else "GATED_BY_CAPABILITY_PROBE",
                    "authority": "physical SHA256d execution only",
                    "evidence": "backend self-check + measured launch/work before HARDWARE_EXECUTED",
                },
            },
        }

    def evidence_snapshot(self) -> dict[str, Any]:
        snapshot = super().evidence_snapshot()
        snapshot["geodesic_ordering"] = dict(self._geodesic_state)
        snapshot["technology_utilization"] = self._technology_utilization_snapshot()
        backend = _backend_name(self.execution_hasher)
        if backend in _NATIVE_BACKENDS:
            snapshot["native_execution"] = {
                "backend": backend,
                "route": self._execution_route(),
                "physical_backend_truthful": True,
                "hardware_evidence_rule": (
                    "HARDWARE_EXECUTED only after measured kernel_launch_count > 0 "
                    "and completed_work_items > 0"
                ),
            }
        return snapshot


__all__ = ["GeodesicProductionMiningCoordinator", "ProductionExecutionRouter"]
