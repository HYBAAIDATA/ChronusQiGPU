"""PYTHIA production search, geodesic ordering and accelerator seam.

The production composition is intentionally layered:

* PYTHIA owns mining cognition, search topology, planning context and learning.
* The canonical search architecture is precomputed before pool work starts:
  dodecahedron/icosahedron dual overlay -> 11D manifold -> 600 dual vertices
  -> 11-qubit Hilbert addresses.
* Chronus owns physical execution and consumes the exact nonce batches PYTHIA
  authorises. OpenCL, CUDA, Metal, remote GPU and composite lanes may execute
  the same explicit batch only after their normal capability/self-check gate.
* EUCLID remains the wider enterprise-intelligence orchestrator and a bounded
  advisory layer inherited by this coordinator; it is not the mining identity.
* SHA256d, target comparison, freshness and literal pool acknowledgement remain
  external truth authorities. Search geometry never becomes proof authority.

The historical M32 route token remains a compatibility detail for accelerator
selection. When the canonical PYTHIA lattice is active the kernel provenance
explicitly states that ``grind_target_batch`` executed the 600-vertex itinerary;
it is never relabelled as an M32 traversal.
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
from .h4_600_execution import promote_execution_hasher
from .pythia_authority import PythiaMiningAuthority
from .pythia_search import (
    SEARCH_ARCHITECTURE_ID,
    PythiaSearchPrecompute,
    precompute_pythia_search,
    pythia_hilbert_600_nonces,
)
from .search_plan import ExecutionRoute, PoolOutcome

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
        """Select physical execution while preserving literal substrate provenance."""
        decision = super().decide_route(plan)
        backend = _backend_name(self._hasher)

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
        """Execute the exact 600-vertex itinerary on CPU or explicit-nonce hardware."""
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
            raise RuntimeError("selected hardware route cannot execute explicit nonce batches")
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
        pythia_authority = kwargs.pop("pythia_authority", None)
        # Static topology/Hilbert work is complete before the inherited runtime
        # can connect to Stratum. Failure is therefore a startup failure, not a
        # half-live miner constructing its search substrate after mining.notify.
        self.pythia_search_precompute = precompute_pythia_search()
        super().__init__(*args, **kwargs)

        # The current PhiMiner route already owns the canonical 32 -> 11D -> 600
        # -> exact-Hilbert itinerary. PR #130's missing enhancement is physical
        # promotion of the already-bound joined Chronus composite underneath it.
        # No device is re-probed and no non-composite route is relabelled.
        self.execution_hasher = promote_execution_hasher(self.execution_hasher)
        raw_factory = getattr(self, "_execution_hasher_factory", None)
        if raw_factory is not None:
            self._execution_hasher_factory = (
                lambda raw_factory=raw_factory: promote_execution_hasher(raw_factory())
            )
        backend_raw = str(getattr(self.execution_hasher, "backend", "") or "")
        topology_id = getattr(self.execution_hasher, "topology_id", None)
        self._chronus_fabric_state: dict[str, Any] = {
            "schema": "pythia.chronus_search_fabric/2",
            "canonical_topology": "chronus_h4_600_11d",
            "logical_vertices": 600,
            "execution_backend": backend_raw or "Unavailable",
            "state": "ACTIVE" if topology_id == "chronus_h4_600_11d" else "NOT_BOUND",
            "physical_fanout": topology_id == "chronus_h4_600_11d",
            "reason": (
                None
                if topology_id == "chronus_h4_600_11d"
                else "physical H4/600 fan-out requires the joined super_asic Chronus lane"
            ),
            "hashrate_claim": "measured completed physical SHA256d work / elapsed time only",
            "target_hashrate_hs": 10_000_000_000_000_000_000,
            "target_measured": False,
        }
        self.pythia_authority = pythia_authority or PythiaMiningAuthority()
        self.pythia_authority.bind_backend_registry(self.backend_registry)

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
        """Route token that can faithfully consume the explicit 600-vertex batch."""
        hasher = self.execution_hasher
        backend = _backend_name(hasher)
        if backend in ("", "cpu", "cpu_reference") or not callable(
            getattr(hasher, "grind_target_batch", None)
        ):
            return "cpu_reference"
        _bind_native_route_markers(hasher)
        if getattr(hasher, "k_m32", None) is not None:
            return "opencl_m32"
        if getattr(hasher, "k_range", None) is not None:
            return "opencl_range"
        return "cpu_reference"

    def _apply_pythia_authority(self, plan, identity):
        """Run every production/fallback plan through PYTHIA without replacing the canonical itinerary."""
        client = self.client
        adapter = getattr(client, "proof_adapter", None) if client is not None else None
        job = getattr(adapter, "current_job", None) if adapter is not None else None
        if job is None or job.job_id != identity.job_id:
            raise RuntimeError("PYTHIA planning requires the current authoritative Stratum job")
        header = adapter.build_header(job.job_id, plan.extranonce2, job.ntime, 0)
        directive = self.pythia_authority.plan(
            header=header,
            target_be=int(job.target).to_bytes(32, "big"),
            base_step=plan.base_step,
            window=plan.window,
            block_context={
                "job_id": identity.job_id,
                "pool_session_id": identity.pool_session_id,
                "generation": identity.generation,
                "target_generation": identity.target_generation,
                "clean_jobs": identity.clean_jobs,
                "chronus_search_fabric": dict(self._chronus_fabric_state),
            },
        )
        refs = dict(plan.evidence_refs)
        refs["pythia_authority"] = directive.as_evidence()
        refs["pythia_planning_authority"] = True
        refs["chronus_search_fabric"] = dict(self._chronus_fabric_state)
        # PYTHIA's coarse lane intelligence biases the existing exact-Hilbert
        # 600-vertex itinerary; it does not replace, prune or expand the lease.
        preferred_face = directive.lane_order[0] if directive.lane_order else plan.preferred_face
        return replace(
            plan,
            lane_order=directive.lane_order,
            preferred_face=preferred_face,
            evidence_refs=refs,
        )

    def _bind_plan_execution_intent(self, plan):
        """Seal PYTHIA's precomputed search architecture into every immutable plan."""
        decision = getattr(self, "last_mining_decision", None)
        refs = dict(plan.evidence_refs)
        refs["search_architecture"] = SEARCH_ARCHITECTURE_ID
        refs["search_precompute_digest"] = self.pythia_search_precompute.digest
        refs["configured_traversal_refinement"] = self._nonce_order
        refs["chronus_search_fabric"] = dict(self._chronus_fabric_state)
        refs["technology_intent"] = {
            "composition_root": "PYTHIA",
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
        # M32 is only a compatibility carrier to avoid the inherited router's
        # separate Hendrix/Poincare special cases. The production router emits
        # the literal 600-vertex architecture as requested/executed order.
        return replace(
            plan,
            nonce_order=NONCE_ORDER_M32,
            executor_route=self._pythia_batch_route(),
            evidence_refs=refs,
        )

    def _baseline_plan(self, identity, lease, window, reason):
        plan = super()._baseline_plan(identity, lease, window, reason)
        return self._bind_plan_execution_intent(
            self._apply_pythia_authority(plan, identity)
        )

    def _build_plan(self, identity):
        plan = super()._build_plan(identity)
        if plan is None:
            return None
        try:
            plan = self._apply_pythia_authority(plan, identity)
            return self._bind_plan_execution_intent(plan)
        except Exception:
            self.agentic.release_lease(plan.plan_id)
            raise

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

    def _record_execution(self, identity, plan, lease, record, outcome, coordinate):
        """Persist canonical execution first, then feed only measured outcome back to PYTHIA."""
        super()._record_execution(identity, plan, lease, record, outcome, coordinate)
        try:
            client = self.client
            adapter = getattr(client, "proof_adapter", None) if client is not None else None
            job = getattr(adapter, "current_job", None) if adapter is not None else None
            if job is None or job.job_id != identity.job_id:
                return
            header = adapter.build_header(job.job_id, lease.extranonce2, job.ntime, 0)
            accepted = (
                True
                if outcome is PoolOutcome.ACCEPTED
                else (False if outcome is PoolOutcome.REJECTED else None)
            )
            self.pythia_authority.learn_execution(
                header=header,
                nonce=getattr(record, "candidate_nonce", None),
                pool_accepted=accepted,
                execution=self.last_execution or {},
            )
        except Exception as exc:
            self.last_execution = {
                **(self.last_execution or {}),
                "pythia_learning_error": f"{type(exc).__name__}: {exc}",
            }

    def _technology_utilization_snapshot(self) -> dict[str, Any]:
        audit = self.policy_audit.snapshot()
        backend = _backend_name(self.execution_hasher)
        return {
            "schema": "pythia.mining_technology_utilization/2",
            "composition_root": "PYTHIA",
            "enterprise_intelligence_orchestrator": "EUCLID",
            "truth_boundary": (
                "PYTHIA directs the mining workforce and search architecture; "
                "Chronus executes; Salamander heals/optimises; SHA256d/Stratum "
                "establish proof and pool truth"
            ),
            "canonical_search": self.pythia_search_precompute.summary(),
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
                "chronus_h4_600_physical_fabric": {
                    "state": self._chronus_fabric_state["state"],
                    "authority": "logical 600-shard physical dispatch on joined Chronus composite only",
                },
                "native_cuda_execution": {
                    "state": (
                        "ACTIVE" if backend == "cuda" else "GATED_BY_CAPABILITY_PROBE"
                    ),
                    "authority": (
                        "physical SHA256d execution of authorised explicit batches"
                    ),
                },
                "native_metal_execution": {
                    "state": (
                        "ACTIVE" if backend == "metal" else "GATED_BY_CAPABILITY_PROBE"
                    ),
                    "authority": (
                        "physical SHA256d execution of authorised explicit batches"
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
        snapshot["pythia_authority"] = self.pythia_authority.snapshot()
        snapshot["chronus_search_fabric"] = dict(self._chronus_fabric_state)
        snapshot["geodesic_ordering"] = dict(self._geodesic_state)
        snapshot["technology_utilization"] = self._technology_utilization_snapshot()
        backend = _backend_name(self.execution_hasher)
        if backend in _NATIVE_BACKENDS:
            snapshot["native_execution"] = {
                "backend": backend,
                "route": self._pythia_batch_route(),
                "physical_backend_truthful": True,
                "canonical_search_consumption": "explicit_nonce_batch",
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
