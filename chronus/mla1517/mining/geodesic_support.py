"""PYTHIA production search, topology, intelligence and accelerator seam.

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
* PULVINI/HYBA Data is not a mining dependency. Geometric/topological mining
  reasoning is composed through PYTHIA and the mining-local canonical search
  architecture, not through the HYBA Data geodesic tensor engine.
* SHA256d, target comparison, freshness and literal pool acknowledgement remain
  external truth authorities. Search geometry never becomes proof authority.

The historical M32 route token remains a compatibility detail for accelerator
selection. When the canonical PYTHIA lattice is active the kernel provenance
explicitly states that ``grind_target_batch`` executed the 600-vertex itinerary;
it is never relabelled as an M32 traversal.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Any, Mapping

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
from .pythia_agentic_cycle import PythiaAgenticMiningAuthority
from .pythia_search import (
    SEARCH_ARCHITECTURE_ID,
    PythiaSearchPrecompute,
    precompute_pythia_search,
    pythia_hendrix_nonces,
)
from .search_plan import ExecutionRoute, PoolOutcome

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
        self._pythia_order_cache: dict[str, list[int]] = {}
        # The base router has a built-in pure-Hendrix branch. PYTHIA's
        # production route executes Hendrix over the complete structured
        # itinerary instead, so use an internal composite marker to reach
        # _run_chunk while the immutable SearchPlan remains Hendrix.
        kwargs["nonce_order"] = lambda plan: (
            _PYTHIA_HENDRIX_COMPOSED
            if self._is_pythia_lattice(plan)
            else plan.nonce_order
        )
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
        """Execute PYTHIA's canonical Hendrix traversal on CPU or hardware."""
        if not self._is_pythia_lattice(plan):
            return super()._run_chunk(plan, header, target, chunk, decision)

        if plan.nonce_order != NONCE_ORDER_HENDRIX:
            raise RuntimeError(
                "PYTHIA canonical search requires the Hendrix plan-bound order"
            )
        order = self._pythia_order_cache.get(plan.plan_id)
        if order is None:
            order = pythia_hendrix_nonces(
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
            raise RuntimeError("PYTHIA Hendrix chunk does not match the leased window")

        if decision.executed_route is ExecutionRoute.cpu_reference:
            return self._cpu_nonces(header, target, nonces)
        batch = getattr(self._hasher, "grind_target_batch", None)
        if not callable(batch):
            raise RuntimeError("selected hardware route cannot execute explicit nonce batches")
        return batch(header, bytes(target)[::-1], nonces)

    def _build_record(self, plan, decision, requested_order, **kwargs):
        """Record Hendrix literally while retaining structure in plan evidence."""
        record = super()._build_record(plan, decision, requested_order, **kwargs)
        if not self._is_pythia_lattice(plan):
            return record
        executed = None if record.executed_nonce_order is None else plan.nonce_order
        return replace(
            record,
            requested_nonce_order=plan.nonce_order,
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
        # -> exact-Hilbert itinerary. The donor enhancement is physical
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
        self.pythia_authority = pythia_authority or PythiaAgenticMiningAuthority()
        self.pythia_authority.bind_backend_registry(self.backend_registry)

        # Mining may use geometric/topological intelligence, but it must not
        # import PULVINI/HYBA Data's geodesic tensor engine. The canonical
        # mining-local 32 -> 11D -> 600 -> Hilbert architecture remains intact;
        # any additional geometric/topological bias is composed through PYTHIA.
        self._geodesic_state: dict[str, Any] = {
            "state": "DELEGATED_TO_PYTHIA",
            "consensus_authority": False,
            "data_authority": False,
            "direct_pulvini_dependency": False,
            "claim_boundary": (
                "geometric/topological mining intelligence is composed by PYTHIA; "
                "PULVINI/HYBA Data transforms are not imported by mining"
            ),
            "last_error": None,
            "last_report": None,
        }

    def _observed_candidate_window(self) -> list[int]:
        """Return the untouched canonical observed window to PYTHIA.

        The old direct HYBA Data geodesic ordering step is intentionally absent.
        The production agentic/PYTHIA planning layer may bias the canonical
        mining-local topology without crossing the PULVINI data boundary.
        """
        return super()._observed_candidate_window()

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

    @staticmethod
    def _upstream_agentic_plan(plan) -> dict[str, Any]:
        return {
            "plan_id": plan.plan_id,
            "source": getattr(plan.source, "value", str(plan.source)),
            "policy_id": plan.policy_id,
            "executor_route": plan.executor_route,
            "dispatch_breadth": plan.dispatch_breadth,
            "preferred_face": plan.preferred_face,
            "lane_order": list(plan.lane_order),
            "schedule_count": len(plan.schedule),
            "schedule_head": list(plan.schedule[:32]),
            "fallback_reason": plan.plan_fallback_reason,
            "toe_frame_id": plan.toe_frame_id,
        }

    def _apply_pythia_authority(self, plan, identity):
        """Run every production/fallback plan through PYTHIA without replacing the canonical itinerary."""
        client = self.client
        adapter = getattr(client, "proof_adapter", None) if client is not None else None
        job = getattr(adapter, "current_job", None) if adapter is not None else None
        if job is None or job.job_id != identity.job_id:
            raise RuntimeError("PYTHIA planning requires the current authoritative Stratum job")
        header = adapter.build_header(job.job_id, plan.extranonce2, job.ntime, 0)
        upstream_agentic = self._upstream_agentic_plan(plan)
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
                "upstream_agentic_plan": upstream_agentic,
                "chronus_search_fabric": dict(self._chronus_fabric_state),
                "geometric_topological_planning": dict(self._geodesic_state),
            },
        )
        refs = dict(plan.evidence_refs)
        refs["upstream_agentic_plan"] = upstream_agentic
        refs["pythia_authority"] = directive.as_evidence()
        refs["pythia_planning_authority"] = True
        refs["chronus_search_fabric"] = dict(self._chronus_fabric_state)
        refs["pulvini_data_boundary"] = {
            "mining_imports_pulvini": False,
            "geometric_topological_owner": "PYTHIA",
        }
        agentic_cycle = self.pythia_authority.snapshot().get("agentic_mining")
        if agentic_cycle is not None:
            refs["pythia_agentic_cycle"] = agentic_cycle
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
        refs["search_algorithm"] = NONCE_ORDER_HENDRIX
        refs["configured_traversal_refinement"] = self._nonce_order
        refs["chronus_search_fabric"] = dict(self._chronus_fabric_state)
        refs["pulvini_data_boundary"] = {
            "mining_imports_pulvini": False,
            "generic_exact_golden_math_allowed": True,
        }
        refs["technology_intent"] = {
            "composition_root": "PYTHIA",
            "search_algorithm": NONCE_ORDER_HENDRIX,
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
            "geometric_topological_planning": "PYTHIA",
            "direct_pulvini_dependency": False,
            "proof_authority": (
                "sha256d_target_freshness_and_literal_pool_response_only"
            ),
        }
        # Hendrix is the canonical production search algorithm. PYTHIA's
        # 32 -> 11D -> 600/Turing structure supplies the complete itinerary
        # that Hendrix traverses; it does not replace Hendrix.
        return replace(
            plan,
            nonce_order=NONCE_ORDER_HENDRIX,
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
            agentic_cycle = self.pythia_authority.snapshot().get("agentic_mining")
            if agentic_cycle is not None:
                self.last_execution = {
                    **(self.last_execution or {}),
                    "pythia_agentic_cycle_id": agentic_cycle.get("cycle_id"),
                }
        except Exception as exc:
            self.last_execution = {
                **(self.last_execution or {}),
                "pythia_learning_error": f"{type(exc).__name__}: {exc}",
            }

    def record_salamander_autonomy(self, autonomy: Mapping[str, Any]) -> None:
        """Correlate already-produced Salamander evidence with the current PYTHIA cycle."""
        cycle = getattr(self.pythia_authority, "last_agentic_cycle", None)
        if not isinstance(cycle, dict):
            return
        stages = dict(cycle.get("stages") or {})
        classification = autonomy.get("classification") if isinstance(autonomy, Mapping) else None
        wired = bool(classification.get("WIRED")) if isinstance(classification, Mapping) else False
        stages["HEAL_OPTIMISE"] = {
            "state": "COMPLETE" if wired else "UNAVAILABLE",
            "authority": "Salamander",
            "evidence": dict(autonomy),
        }
        updated = dict(cycle)
        updated["stages"] = stages
        updated["salamander_evidence_head"] = autonomy.get("evidence_head")
        self.pythia_authority.last_agentic_cycle = updated
        if isinstance(self.last_execution, dict):
            self.last_execution = {
                **self.last_execution,
                "salamander_evidence_head": autonomy.get("evidence_head"),
                "salamander_health": autonomy.get("health"),
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
                    "state": "ACTIVE_CANONICAL_SEARCH",
                    "authority": (
                        "default complete structured traversal; supporting intelligence "
                        "may order its itinerary but may not replace it"
                    ),
                },
                "m32_dual_solid_lane_topology": {
                    "state": "ACTIVE_SUPPORTING_TOPOLOGY",
                    "authority": (
                        "coarse lane/accelerator compatibility, not canonical search identity"
                    ),
                },
                "geometric_topological_planning": {
                    "state": self._geodesic_state.get("state", "Unavailable"),
                    "authority": "PYTHIA; no direct PULVINI/HYBA Data dependency",
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
        authority = self.pythia_authority.snapshot()
        snapshot["pythia_authority"] = authority
        snapshot["agentic_mining"] = authority.get("agentic_mining")
        snapshot["chronus_search_fabric"] = dict(self._chronus_fabric_state)
        snapshot["geometric_topological_planning"] = dict(self._geodesic_state)
        snapshot["pulvini_data_boundary"] = {
            "mining_imports_pulvini": False,
            "generic_exact_golden_math_allowed": True,
        }
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