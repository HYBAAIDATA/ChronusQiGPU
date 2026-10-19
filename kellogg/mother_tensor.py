"""Kellogg Mother-Tensor canonical state: [600 lanes × 8 futures × chunksize × 11D coords].

Single canonical module representing the full state space of the 600-lane solving machine:
- 600 lanes: Dodecahedron ⊕ Icosahedron overlay lifted to 11D tiling
- 8 futures: Maximum superposition width, held in LRU with literal pool probabilities
- Chunksize: Nonce estate allocation per lane for leased window W
- 11D coords: Pure algebraic embedding in Q(phi)^11

Contraction across the 9 pillars reproduces:
- {phi_method}: Golden ratio inverse phi^-1 = 0.618033988749895
- {xor_0.5625}: 0.0520 -> 0.5625 XOR irreducibility transition
- {kappa_trace}: Forman-Ricci golden flow convergence |kappa| <= 0.05 in <= 8 steps
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence, Tuple

from chronus.exact_geometry import (
    EstateChunk600,
    ExactRay,
    PartitionProof600,
    build_600_partition,
    dodeca_overlay_icosa,
    embed_11d_exact,
)
from chronus.mla1517.mining.search_plan import (
    EvidenceClass,
    ExecutionRoute,
    PlanSource,
    SearchPlan,
    WorkIdentity,
    _LANES,
)
from kellogg.ansatz_v3 import (
    ANSATZ_V3,
    FUTURES,
    LANES,
    AnsatzV3,
    RicciReconciliationTrace,
    load_ansatz,
)


@dataclass(frozen=True)
class PillarContractionResult:
    """Result of contracting the mother-tensor across foundational pillars."""

    phi_method: str | None
    xor_05625: float | None
    kappa_trace: RicciReconciliationTrace | None
    is_complete: bool
    missing_pillars: tuple[str, ...]
    contraction_hash: str


class KelloggMotherTensor:
    """Canonical mother-tensor state: [600 lanes × 8 futures × chunksize × 11D]."""

    def __init__(
        self,
        chunks: tuple[EstateChunk600, ...],
        proof: PartitionProof600,
        futures: tuple[str, ...] = ("job_primary",),
        future_probabilities: tuple[float, ...] = (1.0,),
        ansatz: AnsatzV3 | None = None,
    ) -> None:
        if len(chunks) != LANES:
            raise ValueError(f"Mother-tensor requires exactly {LANES} chunks, got {len(chunks)}")
        if len(futures) > FUTURES:
            raise ValueError(f"Futures superposition width cannot exceed {FUTURES}, got {len(futures)}")
        if len(futures) != len(future_probabilities):
            raise ValueError("Futures and future_probabilities must have matching length")

        self.chunks = chunks
        self.proof = proof
        self.futures = futures
        self.future_probabilities = future_probabilities
        self.ansatz = ansatz or load_ansatz("ansatz_v3")

        # Dimensions: [600, len(futures), max_chunk_size, 11]
        self.max_chunk_size = max((c.size for c in chunks), default=0)
        self.dims = (LANES, len(futures), self.max_chunk_size, 11)

        # Per-lane scores (initialized equally under gauge symmetry)
        self.lane_weights: list[float] = [1.0 / LANES] * LANES
        self._gauge_symmetric: bool = True

    def enforce_gauge_symmetry(self) -> bool:
        """Yang-Mills gauge symmetry enforcement: no lane gets structural privilege."""
        is_sym, var = self.ansatz.check_gauge_symmetry(self.lane_weights)
        self._gauge_symmetric = is_sym
        if not is_sym:
            # Rebalance to uniform gauge
            uniform = 1.0 / LANES
            self.lane_weights = [uniform] * LANES
            self._gauge_symmetric = True
        return self._gauge_symmetric

    def contract(self, pillars9: Sequence[str] | None = None) -> PillarContractionResult:
        """Contract mother-tensor state across pillars, verifying invariants or marking MISSING."""
        active_pillars = tuple(
            pillars9
            if pillars9 is not None
            else (
                "predictive",
                "causal",
                "counterfactual",
                "topological",
                "geometric",
                "quantum_ext",
                "yang_mills",
                "ricci_flow",
                "toe_ansatz",
            )
        )

        missing: list[str] = []

        # 1. Phi method check
        phi_val = self.ansatz.phi_inv
        if abs(phi_val - 0.6180339887498948) < 1e-9:
            phi_method_str = f"phi_inv={phi_val:.15f}"
        else:
            phi_method_str = None
            missing.append("phi_method")

        # 2. XOR 0.5625 irreducibility check
        xor_val = self.ansatz.compute_xor_transition(0xAA, 0x55)
        if abs(xor_val - 0.5625) < 1e-4:
            xor_result = xor_val
        else:
            xor_result = None
            missing.append("xor_0.5625")

        # 3. Kappa trace check (canonical Ricci flow: |kappa| <= 0.05 in <= 8 steps)
        reconcile_trace = self.ansatz.reconcile_lane(
            lane_id=0,
            initial_kappa=-0.162,
            c_pre=0.8,
            trauma_intensity=9.0,
        )
        if not reconcile_trace.is_canonical or not reconcile_trace.execution_granted:
            missing.append("kappa_trace")

        # Gauge symmetry in contraction
        if not self._gauge_symmetric:
            missing.append("yang_mills_gauge")

        is_complete = (len(missing) == 0)

        # Digest of contraction state
        payload = {
            "phi": phi_method_str,
            "xor": xor_result,
            "kappa_steps": reconcile_trace.steps_taken if reconcile_trace else None,
            "dims": list(self.dims),
            "coverage_hash": self.proof.coverage_hash,
            "missing": missing,
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        return PillarContractionResult(
            phi_method=phi_method_str,
            xor_05625=xor_result,
            kappa_trace=reconcile_trace,
            is_complete=is_complete,
            missing_pillars=tuple(missing),
            contraction_hash=digest,
        )

    def build_search_plan(
        self,
        identity: WorkIdentity,
        base_step: int,
        window: int,
        extranonce2: str,
        executor_route: str = "chronus_batch",
        policy_id: str = "kellogg_600_mother_tensor",
        toe_frame_id: str | None = None,
        source: PlanSource = PlanSource.AGENTIC_PRECOMPUTED,
        plan_fallback_reason: str | None = None,
    ) -> SearchPlan:
        """Collapse mother-tensor state to an immutable, verifiable SearchPlan."""
        # Top 32 prioritized lanes for the M32 frame execution window
        lane_order = tuple(c.lane_id for c in self.chunks[:_LANES])

        contraction = self.contract()
        if not contraction.is_complete:
            raise RuntimeError(
                f"Cannot collapse SearchPlan: missing pillars {contraction.missing_pillars}"
            )

        evidence = {
            "kellogg_mother_tensor_600": True,
            "dims": list(self.dims),
            "partition_proof": self.proof.as_dict(),
            "contraction_hash": contraction.contraction_hash,
            "ansatz_version": self.ansatz.version,
            "requested_route": executor_route,
            "gauge_symmetric": self._gauge_symmetric,
        }
        if toe_frame_id is not None:
            evidence["toe_frame_digest"] = toe_frame_id

        return SearchPlan(
            job_fingerprint=identity.job_fingerprint,
            pool_session_id=identity.pool_session_id,
            generation=identity.generation,
            base_step=base_step,
            window=window,
            extranonce2=extranonce2,
            lane_order=lane_order,
            preferred_face=0,
            dispatch_breadth=min(len(lane_order), 32),
            executor_route=executor_route,
            policy_id=policy_id,
            evidence_refs=evidence,
            created_at=time.monotonic(),
            plan_id=str(uuid.uuid4()),
            nonce_order="hendrix_coprime_stride",
            toe_frame_id=toe_frame_id,
            source=source,
            plan_fallback_reason=plan_fallback_reason,
        )


def kellogg_state_600(
    base_step: int,
    window: int,
    seed: int = 1337,
    stride: int = 5,
    futures: tuple[str, ...] = ("job_primary",),
    future_probabilities: tuple[float, ...] = (1.0,),
    ansatz_version: str = "ansatz_v3",
    header_prefix: bytes | None = None,
    target_int: int | None = None,
) -> KelloggMotherTensor:
    """Build and initialize the canonical 600-lane KelloggMotherTensor state."""
    chunks, proof = build_600_partition(
        base_step=base_step,
        window=window,
        seed=seed,
        stride=stride,
        header_prefix=header_prefix,
        target_int=target_int,
    )
    ansatz = load_ansatz(ansatz_version)
    mt = KelloggMotherTensor(
        chunks=chunks,
        proof=proof,
        futures=futures,
        future_probabilities=future_probabilities,
        ansatz=ansatz,
    )
    mt.enforce_gauge_symmetry()
    return mt
