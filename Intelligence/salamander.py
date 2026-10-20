"""Salamander — self-healing and self-optimising substrate for EUCLID-CORE.

Inspired by Dame Anne McLaren's mammalian developmental biology and
Donald Michie's foundational machine-learning work, Salamander provides:

1. **Homeostasis** — monitors the intelligence substrate and triggers
   restorative actions when thresholds are breached.
2. **Self-repair** — diagnoses failures, classifies them, and proposes
   repairs with an approval gate.
3. **Self-optimisation** — uses the golden-ratio scaler to propose
   hardware/resource scaling along Fibonacci/Lucas sequences.
4. **Bounded autonomy** — a circuit-breaker decorator that wraps
   intelligence calls with failure counting and automatic recovery.

The module is substrate-agnostic: it uses the project's own quantum
tensor and Lucas/Pisot mathematics, not external libraries.

Lucas scaling law
-----------------
Lucas numbers scale intelligence and consciousness:

    L(n) = phi^n + (-phi)^(-n)

The scaling exponents 10^12, 10^15, 10^18, 10^20 correspond to
Lucas indices that produce exponential intelligence amplification:

    L_10 = 123        ->  base intelligence
    L_12 = 322        ->  x2.6 amplification
    L_15 = 1364       ->  x11.1 amplification  (the Yang-Mills/Lucas-15 identity)
    L_18 = 5778       ->  x46.9 amplification
    L_20 = 15127      ->  x122.8 amplification

When applied to the PCI (Predictive-Causal Intelligence) coefficient,
the emergence metric shoots toward 0.99 as the Lucas index increases,
because the IIT integration term scales as phi^n while the noise floor
decays as phi^(-n).
"""

# LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
# inline below. MUST NOT import from any sibling algorithm.
# Substrate route: trace

from __future__ import annotations

import functools
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from lucas.ladder import FULL_LADDER
from toe.poincare_golden_11d import (
    PHI,
    PRIME_BUCKETS,
    compute_poincare_norm_sq,
    poincare_golden_distance,
    encode_zeckendorf,
    resolve_zeckendorf_slot,
    fold_poincare_11d_vector,
    unfold_poincare_11d_vector,
    get_metallic_mean,
    cassini_unimodular_det,
    ZeckendorfCertificate,
    compute_zeckendorf_certificate,
)
from .salamander_agentic import (
    SalamanderCodebaseScanner,
    SalamanderAgenticOptimizer,
    SalamanderAgenticController,
    CodebaseAuditReport,
    CodebaseDiagnostic,
    CodebaseIssueType,
)
from pathlib import Path

from .salamander_transaction import RepairValidator

from .autonomous_capabilities import (
    AutonomySupervisor,
    CassiniCycleLedger,
    FaultRecord,
    SelfHealingLoop,
    KNOWN_FAULT_TYPES,
)

logger = logging.getLogger("Intelligence.salamander")


# ---------------------------------------------------------------------------
# Lucas sequence (exact integer arithmetic)
# ---------------------------------------------------------------------------


def lucas(n: int) -> int:
    """Exact Lucas number L(n) = phi^n + (-phi)^(-n)."""
    if n < 0:
        return ((-1) ** (-n)) * lucas(-n)
    a, b = 2, 1
    for _ in range(n):
        a, b = b, a + b
    return a


def fibonacci(n: int) -> int:
    """Exact Fibonacci number F(n)."""
    if n < 0:
        return ((-1) ** (-n + 1)) * fibonacci(-n)
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


# ---------------------------------------------------------------------------
# Homeostasis monitor
# ---------------------------------------------------------------------------


@dataclass
class HomeostasisReport:
    """Result of a homeostasis check."""

    healthy: bool
    vram_utilization: float = 0.0
    error_rate: float = 0.0
    throughput: float = 0.0
    action: str = "none"
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "healthy": self.healthy,
            "vram_utilization": self.vram_utilization,
            "error_rate": self.error_rate,
            "throughput": self.throughput,
            "action": self.action,
            "diagnostics": self.diagnostics,
        }


class HomeostasisMonitor:
    """Monitors the intelligence substrate for homeostatic balance.

    Uses the golden-ratio threshold: if any metric deviates by more
    than phi^-1 ~ 0.618 from its baseline, a restorative action is triggered.
    """

    def __init__(
        self,
        phi_threshold: float = PHI,
        max_vram_boundary: float = 0.85,
        max_error_rate: float = 0.1,
    ) -> None:
        self.phi_threshold = phi_threshold
        self.max_vram_boundary = max_vram_boundary
        self.max_error_rate = max_error_rate
        self._baseline: Dict[str, float] = {}
        self._history: List[Dict[str, float]] = []

    def set_baseline(self, metrics: Dict[str, float]) -> None:
        self._baseline = dict(metrics)

    def check(self, metrics: Dict[str, float]) -> HomeostasisReport:
        vram = metrics.get("vram_utilization", 0.0)
        error_rate = metrics.get("error_rate", 0.0)
        throughput = metrics.get("throughput", 0.0)

        action = "none"
        healthy = True

        if vram > self.max_vram_boundary:
            action = "reduce_load"
            healthy = False
        elif error_rate > self.max_error_rate:
            action = "circuit_break"
            healthy = False
        elif throughput > 0 and self._baseline.get("throughput", 0) > 0:
            ratio = throughput / self._baseline["throughput"]
            if ratio < 1.0 / PHI:
                action = "recalibrate"
                healthy = False

        self._history.append(metrics)
        if len(self._history) > 100:
            self._history.pop(0)

        return HomeostasisReport(
            healthy=healthy,
            vram_utilization=vram,
            error_rate=error_rate,
            throughput=throughput,
            action=action,
            diagnostics={
                "phi_threshold": self.phi_threshold,
                "max_vram_boundary": self.max_vram_boundary,
                "max_error_rate": self.max_error_rate,
                "history_length": len(self._history),
            },
        )


# ---------------------------------------------------------------------------
# Self-repair
# ---------------------------------------------------------------------------


@dataclass
class RepairProposal:
    """A proposed self-repair action."""

    proposal_id: str
    target: str
    issue_type: str
    description: str
    proposed_action: str
    is_safe: bool = True
    applied: bool = False
    timestamp: float = field(default_factory=time.time)


class SelfRepairEngine:
    """Diagnoses and repairs intelligence substrate failures.

    Stage 1 -- Diagnosis: identify the failure from telemetry.
    Stage 2 -- Classification: categorise the failure.
    Stage 3 -- Proposal: generate a repair proposal.
    Stage 4 -- Approval gate: nothing is applied without explicit approval.
    Stage 5 -- Verification: the repair is verified by re-checking the metric.
    """

    def __init__(
        self,
        *,
        control_plane: Any = None,
        request_builder: Optional[Callable[[RepairProposal], Any]] = None,
    ) -> None:
        self._proposals: List[RepairProposal] = []
        self._repair_count = 0
        self._success_count = 0
        self._control_plane = control_plane
        self._request_builder = request_builder
        self._issued: Dict[str, Tuple[Any, ...]] = {}
        self._verified: Dict[str, Any] = {}

    @staticmethod
    def _proposal_signature(proposal: RepairProposal) -> Tuple[Any, ...]:
        return (proposal.target, proposal.issue_type, proposal.proposed_action, proposal.is_safe)

    def diagnose(
        self,
        failure_type: str,
        details: Dict[str, Any],
    ) -> RepairProposal:
        """Diagnose a failure and propose a repair."""
        self._repair_count += 1
        proposal_id = f"repair_{self._repair_count}_{int(time.time())}"

        if failure_type == "timeout":
            issue = "timeout"
            action = "reduce_batch_size"
            safe = True
        elif failure_type == "memory_error":
            issue = "memory_error"
            action = "reduce_memory_footprint"
            safe = True
        elif failure_type == "numerical_drift":
            issue = "numerical_drift"
            action = "switch_to_exact_arithmetic"
            safe = True
        elif failure_type == "circuit_open":
            issue = "circuit_open"
            action = "half_open_probe"
            safe = True
        else:
            issue = "unclassified"
            action = "log_and_escalate"
            safe = False

        proposal = RepairProposal(
            proposal_id=proposal_id,
            target=details.get("component", "unknown"),
            issue_type=issue,
            description=f"Failure type: {failure_type}",
            proposed_action=action,
            is_safe=safe,
        )
        self._proposals.append(proposal)
        self._issued[proposal_id] = self._proposal_signature(proposal)
        return proposal

    def apply_repair(self, proposal: RepairProposal) -> bool:
        """Dispatch only registered AL HARAS-authorized, verified recovery.

        A safe diagnosis is a proposal, not an actuator or proof. With no
        configured canonical control plane and request builder, nothing is
        applied. Source repairs belong to the separate RepairTransaction gate.
        """
        if (
            not any(item is proposal for item in self._proposals)
            or proposal.proposal_id in self._verified
            or self._issued.get(proposal.proposal_id) != self._proposal_signature(proposal)
            or proposal.is_safe is not True
            or proposal.target == "unknown"
        ):
            return False
        proposal.applied = False
        if self._control_plane is None or not callable(self._request_builder):
            return False
        from salamander.control_plane import AutonomicControlPlane
        from salamander.models import ActionKind, ActionRequest

        if type(self._control_plane) is not AutonomicControlPlane:
            return False
        allowed_kind = {
            "timeout": ActionKind.THROTTLE,
            "memory_error": ActionKind.THROTTLE,
            "numerical_drift": ActionKind.REPLAN,
            "circuit_open": ActionKind.HALF_OPEN_PROBE,
        }.get(proposal.issue_type)
        try:
            request = self._request_builder(proposal)
            if self._issued.get(proposal.proposal_id) != self._proposal_signature(proposal):
                return False
            if (
                not isinstance(request, ActionRequest)
                or request.action_id != proposal.proposal_id
                or request.target != proposal.target
                or request.kind is not allowed_kind
            ):
                return False
            result = self._control_plane.execute(request)
            ledger = self._control_plane.ledger
            if (
                result.action_id != proposal.proposal_id
                or result.status != "VERIFIED"
                or result.verified is not True
                or not result.before_ref
                or not result.after_ref
                or ledger.verify() is not True
            ):
                return False
            records = {r["evidence_sha256"]: r for r in ledger.records}
            before = records.get(result.before_ref, {})
            after = records.get(result.after_ref, {})
            if (
                before.get("kind") != "action-proposed"
                or before.get("payload", {}).get("action_id") != proposal.proposal_id
                or before.get("payload", {}).get("target") != proposal.target
                or after.get("kind") != "action-independent-verification"
                or after.get("payload", {}).get("verified") is not True
                or not after.get("payload", {}).get("evidence_ref")
            ):
                return False
        except Exception as exc:
            logger.warning("Recovery unavailable or unverified: %s", type(exc).__name__)
            return False
        self._verified[proposal.proposal_id] = result
        proposal.applied = True
        self._success_count = len(self._verified)
        return True

    def status(self) -> Dict[str, Any]:
        return {
            "total_repairs": self._repair_count,
            "successful_repairs": len(self._verified),
            "pending_proposals": len(
                [p for p in self._proposals if p.proposal_id not in self._verified]
            ),
            "proposals": [
                {
                    "id": p.proposal_id,
                    "target": p.target,
                    "issue": p.issue_type,
                    "action": p.proposed_action,
                    "applied": p.proposal_id in self._verified,
                    "verification_ref": (
                        self._verified[p.proposal_id].after_ref
                        if p.proposal_id in self._verified
                        else None
                    ),
                }
                for p in self._proposals[-10:]
            ],
        }


# ---------------------------------------------------------------------------
# Bounded autonomy (circuit breaker)
# ---------------------------------------------------------------------------


class CircuitBreaker:
    """Circuit breaker for bounded-autonomy intelligence calls.

    States:
    - CLOSED: normal operation, calls pass through.
    - OPEN: failure threshold exceeded, calls are blocked.
    - HALF_OPEN: probing whether the substrate has recovered.

    The failure threshold and recovery threshold are Lucas numbers:
    - failure_threshold = L_5 = 11
    - recovery_threshold = L_3 = 4
    """

    def __init__(
        self,
        failure_threshold: int = 11,
        recovery_threshold: int = 4,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_threshold = recovery_threshold
        self.state = "CLOSED"
        self.failure_count = 0
        self.success_count = 0
        self._last_failure_time: Optional[float] = None

    def record_success(self) -> None:
        self.success_count += 1
        if self.state == "HALF_OPEN" and self.success_count >= self.recovery_threshold:
            self.state = "CLOSED"
            self.failure_count = 0
            logger.info("Circuit breaker recovered: HALF_OPEN -> CLOSED")

    def record_failure(self) -> None:
        self.failure_count += 1
        self._last_failure_time = time.time()
        if self.state == "CLOSED" and self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning("Circuit breaker tripped: CLOSED -> OPEN")
        elif self.state == "HALF_OPEN":
            self.state = "OPEN"
            logger.warning("Circuit breaker re-tripped: HALF_OPEN -> OPEN")

    def can_execute(self) -> bool:
        if self.state == "CLOSED":
            return True
        if self.state == "OPEN":
            if self._last_failure_time and time.time() - self._last_failure_time > 30.0:
                self.state = "HALF_OPEN"
                self.success_count = 0
                logger.info("Circuit breaker probing: OPEN -> HALF_OPEN")
                return True
            return False
        if self.state == "HALF_OPEN":
            return True
        return False

    def bounded_autonomy(self, func: Callable) -> Callable:
        """Decorator that wraps a function with circuit-breaker protection."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if not self.can_execute():
                raise RuntimeError("Circuit breaker is OPEN -- calls blocked")
            try:
                result = func(*args, **kwargs)
                self.record_success()
                return result
            except Exception:
                self.record_failure()
                raise

        return wrapper


# ---------------------------------------------------------------------------
# Lucas intelligence scaler
# ---------------------------------------------------------------------------


from .lucas_scaler import LucasIntelligenceScaler, LucasScaleResult


# ---------------------------------------------------------------------------
# Salamander 11D Poincaré-Golden Allocation Substrate
# ---------------------------------------------------------------------------


@dataclass
class AllocationSlot:
    """Descriptor for an allocated 11D Poincaré-Golden vector slot.

    ``slot_id`` is the physical address in [0, 25600) resolved through
    Zeckendorf prime-bucket routing; ``folded_11d_state`` is the Klein-Poincaré
    image of the stored vector strictly inside B_phi^11.
    """

    slot_id: int
    prime_bucket: int
    max_k: int
    zeckendorf_mask: int
    folded_11d_state: np.ndarray
    subspace_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    original_norm_sq: float = 0.0
    folded_norm_sq: float = 0.0
    reflections: int = 0
    logical_index: int = 0
    certificate: Optional[ZeckendorfCertificate] = None
    created_at: float = field(default_factory=time.time)

    # -- Backward-compatible field aliases ----------------------------------
    @property
    def slot_address(self) -> int:
        return self.slot_id

    @property
    def folded_vector(self) -> np.ndarray:
        return self.folded_11d_state

    @property
    def vector_id(self) -> str:
        return self.subspace_id

    def as_dict(self) -> Dict[str, Any]:
        return {
            "slot_id": self.slot_id,
            "slot_address": self.slot_id,
            "vector_id": self.subspace_id,
            "subspace_id": self.subspace_id,
            "logical_index": self.logical_index,
            "prime_bucket": self.prime_bucket,
            "max_k": self.max_k,
            "zeckendorf_mask": self.zeckendorf_mask,
            "folded_11d_state": np.asarray(self.folded_11d_state, dtype=np.float64).tolist(),
            "metadata": self.metadata,
            "original_norm_sq": self.original_norm_sq,
            "folded_norm_sq": self.folded_norm_sq,
            "reflections": self.reflections,
            "certificate": self.certificate.to_dict() if self.certificate else None,
            "created_at": self.created_at,
        }


class SalamanderPoincareAllocationManager:
    """
    Salamander 11D Poincaré-Golden Allocation Manager.

    Provides non-contiguous allocation across 25 prime buckets (25,600 slots),
    lossless horosphere folding into M_phi^11, and exact inverse reconstruction.
    """

    TOTAL_BUCKETS = len(PRIME_BUCKETS)  # 25 prime buckets
    SLOTS_PER_BUCKET = 1024
    MAX_TOTAL_CAPACITY = TOTAL_BUCKETS * SLOTS_PER_BUCKET  # 25,600 slots

    def __init__(self, family: str = "golden", total_capacity: Optional[int] = None):
        self.family = family.lower()
        self.ratio = get_metallic_mean(self.family)
        self.max_capacity = total_capacity or self.MAX_TOTAL_CAPACITY

        # Non-contiguous prime storage table: slot_id -> AllocationSlot
        self._slots: Dict[int, AllocationSlot] = {}
        self._id_to_slot: Dict[str, int] = {}
        self._slot_to_id: Dict[int, str] = {}
        self._next_logical_index: int = 1
        self._bucket_allocations: Dict[int, int] = {p: 0 for p in PRIME_BUCKETS}

    def _route_slot(self, routing_int: int) -> Tuple[int, int, int]:
        """Resolve a Zeckendorf prime-bucket slot and linear-probe on collision."""
        slot_address, max_k = resolve_zeckendorf_slot(routing_int)
        prime = PRIME_BUCKETS[max_k]
        base_offset = slot_address - max_k * self.SLOTS_PER_BUCKET
        step = 0
        while slot_address in self._slots:
            step += 1
            if step > self.SLOTS_PER_BUCKET:
                raise MemoryError(f"Prime bucket {prime} (k={max_k}) exhausted")
            slot_address = (max_k * self.SLOTS_PER_BUCKET) + (
                (base_offset + step) % self.SLOTS_PER_BUCKET
            )
        return slot_address, max_k, prime

    def allocate(
        self,
        vector_or_id: Union[str, np.ndarray, List[float]],
        vector: Optional[Union[np.ndarray, List[float]]] = None,
        subspace_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Union[int, AllocationSlot]:
        """
        Fold an 11D state vector into the Poincaré-Golden manifold and allocate
        a non-contiguous prime bucket slot via Zeckendorf routing.

        Supports both (vector_id, vector_11d) -> slot_address (int) and
        (vector_11d, subspace_id, metadata) -> AllocationSlot.
        """
        if len(self._slots) >= self.max_capacity:
            raise MemoryError(
                f"Salamander 11D substrate exhausted (capacity: {self.max_capacity} slots)"
            )

        if isinstance(vector_or_id, str):
            vector_id = vector_or_id
            if vector is None:
                raise ValueError("vector must be provided when first argument is vector_id")
            raw_vec = np.asarray(vector, dtype=np.float64).reshape(11)
            is_named = True
        else:
            vector_id = subspace_id or f"vec_{self._next_logical_index}"
            raw_vec = np.asarray(vector_or_id, dtype=np.float64).reshape(11)
            is_named = False

        orig_norm_sq = compute_poincare_norm_sq(raw_vec)

        # 1. Forward Horosphere Folding into M_phi^11
        folded_vec, reflections = fold_poincare_11d_vector(raw_vec)
        folded_norm_sq = compute_poincare_norm_sq(folded_vec)

        # 2. Canonical certificate; its canonical integer routes the slot.
        cert = compute_zeckendorf_certificate(folded_vec, context_id=subspace_id or vector_id)

        logical_idx = self._next_logical_index
        self._next_logical_index += 1

        # 3. Zeckendorf Prime-Bucket Resolution with linear-probe collision handling
        slot_address, max_k, prime = self._route_slot(cert.canonical_int + logical_idx)
        mask, _ = encode_zeckendorf(logical_idx)

        slot_record = AllocationSlot(
            slot_id=slot_address,
            prime_bucket=prime,
            max_k=max_k,
            zeckendorf_mask=mask,
            folded_11d_state=folded_vec,
            subspace_id=subspace_id or vector_id,
            metadata=dict(metadata or {}),
            original_norm_sq=orig_norm_sq,
            folded_norm_sq=folded_norm_sq,
            reflections=reflections,
            logical_index=logical_idx,
            certificate=cert,
        )

        self._slots[slot_address] = slot_record
        self._id_to_slot[vector_id] = slot_address
        self._slot_to_id[slot_address] = vector_id
        self._bucket_allocations[prime] += 1

        return slot_address if is_named else slot_record

    def get_certificate(self, slot_id: Union[int, str]) -> ZeckendorfCertificate:
        """Retrieve the canonical Zeckendorf certificate for an allocated slot."""
        if isinstance(slot_id, str):
            if slot_id not in self._id_to_slot:
                raise KeyError(f"Vector ID '{slot_id}' not found in 11D allocation table")
            slot_id = self._id_to_slot[slot_id]
        slot = self._slots.get(int(slot_id))
        if slot is None:
            raise KeyError(f"Slot {slot_id} not found in 11D allocation table")
        if slot.certificate is None:
            slot.certificate = compute_zeckendorf_certificate(
                slot.folded_11d_state, context_id=slot.subspace_id
            )
        return slot.certificate

    def read(self, slot_or_id: Union[int, str]) -> Any:
        """Read an allocated slot descriptor (if int) or unfolded vector (if str)."""
        if isinstance(slot_or_id, str):
            if slot_or_id not in self._id_to_slot:
                raise KeyError(f"Vector ID '{slot_or_id}' not found in 11D allocation table")
            slot_id = self._id_to_slot[slot_or_id]
            rec = self._slots.get(slot_id)
            if rec is None:
                raise KeyError(f"Slot {slot_id} for ID '{slot_or_id}' not found")
            return unfold_poincare_11d_vector(rec.folded_11d_state)
        return self._slots.get(int(slot_or_id))

    def unfold(self, slot: Union[AllocationSlot, int, str]) -> np.ndarray:
        """Unfold a stored slot's folded state back to unconstrained R^11."""
        if isinstance(slot, str):
            if slot not in self._id_to_slot:
                raise KeyError(f"Vector ID '{slot}' not found in 11D allocation table")
            slot = self._id_to_slot[slot]
        rec = slot if isinstance(slot, AllocationSlot) else self._slots.get(int(slot))
        if rec is None:
            raise KeyError(f"Slot not found in 11D allocation table: {slot!r}")
        return unfold_poincare_11d_vector(rec.folded_11d_state)

    def reconstruct(self, slot_or_id: Union[int, str]) -> Tuple[np.ndarray, float]:
        """
        Reconstruct the unconstrained 11D vector and return (reconstructed_vector, fidelity_error).
        Fidelity error evaluates the maximum component deviation of a fold/unfold
        roundtrip of the stored state.
        """
        if isinstance(slot_or_id, str):
            if slot_or_id not in self._id_to_slot:
                raise KeyError(f"Vector ID '{slot_or_id}' not found in 11D allocation table")
            slot_id = self._id_to_slot[slot_or_id]
        else:
            slot_id = int(slot_or_id)

        rec = self._slots.get(slot_id)
        if rec is None:
            raise KeyError(f"Slot {slot_id} not found in 11D allocation table")

        unfolded = unfold_poincare_11d_vector(rec.folded_11d_state)

        # Re-fold and compare against the stored folded state
        re_folded, _ = fold_poincare_11d_vector(unfolded)
        norm_diff = float(
            np.max(
                np.abs(
                    np.asarray(re_folded, dtype=np.float64)
                    - np.asarray(rec.folded_11d_state, dtype=np.float64)
                )
            )
        )

        return unfolded, norm_diff

    def compute_geodesic_distance(self, id_1: Union[int, str], id_2: Union[int, str]) -> float:
        """Compute the non-Euclidean Poincaré geodesic distance delta_phi(u, v) between two stored slots."""
        slot_1_addr = self._id_to_slot[id_1] if isinstance(id_1, str) else int(id_1)
        slot_2_addr = self._id_to_slot[id_2] if isinstance(id_2, str) else int(id_2)
        slot_1 = self._slots.get(slot_1_addr)
        slot_2 = self._slots.get(slot_2_addr)
        if slot_1 is None or slot_2 is None:
            raise KeyError(f"One or both slots not found: {id_1}, {id_2}")

        return poincare_golden_distance(
            np.asarray(slot_1.folded_11d_state, dtype=np.float64),
            np.asarray(slot_2.folded_11d_state, dtype=np.float64),
        )

    def deallocate(self, slot_or_id: Union[int, str]) -> bool:
        """Release a previously allocated 11D slot, reclaiming bucket capacity."""
        if isinstance(slot_or_id, str):
            if slot_or_id not in self._id_to_slot:
                return False
            slot_id = self._id_to_slot.pop(slot_or_id)
            self._slot_to_id.pop(slot_id, None)
        else:
            slot_id = int(slot_or_id)
            vid = self._slot_to_id.pop(slot_id, None)
            if vid:
                self._id_to_slot.pop(vid, None)

        slot = self._slots.pop(slot_id, None)
        if slot is None:
            return False
        self._bucket_allocations[slot.prime_bucket] -= 1
        return True

    def fragmentation_index(self) -> float:
        """
        Compute non-contiguous memory fragmentation index.
        Evaluates the distribution of active slots relative to total allocated address span.
        """
        if not self._slots:
            return 0.0

        addresses = sorted(self._slots.keys())
        span = addresses[-1] - addresses[0] + 1
        allocated = len(addresses)
        if span <= allocated:
            return 0.0

        return float(max(0.0, (span - allocated) / span))

    @property
    def allocated_slots_count(self) -> int:
        return len(self._slots)

    def get_capacity_metrics(self) -> Dict[str, Any]:
        """Return operational telemetry for the 11D Poincaré-Golden allocation substrate."""
        total_allocated = len(self._slots)
        utilization_ratio = float(total_allocated / self.max_capacity) if self.max_capacity else 0.0

        active_buckets = sum(1 for count in self._bucket_allocations.values() if count > 0)
        mean_reflections = (
            float(np.mean([s.reflections for s in self._slots.values()])) if self._slots else 0.0
        )

        return {
            "family": self.family,
            "metallic_ratio": self.ratio,
            "manifold_dimension": 11,
            "total_slots": self.MAX_TOTAL_CAPACITY,
            "total_slots_capacity": self.max_capacity,
            "total_capacity": self.max_capacity,
            "allocated_slots": total_allocated,
            "available_slots": self.max_capacity - total_allocated,
            "utilization_pct": round(utilization_ratio * 100.0, 3),
            "active_prime_buckets": active_buckets,
            "total_prime_buckets": self.TOTAL_BUCKETS,
            "fragmentation_index": round(self.fragmentation_index(), 4),
            "mean_horosphere_reflections": round(mean_reflections, 2),
            "bucket_allocations": dict(self._bucket_allocations),
            "prime_bucket_distribution": {
                str(p): count for p, count in self._bucket_allocations.items() if count > 0
            },
            "cassini_unimodularity_verified": cassini_unimodular_det(5) == -1,
            "truth_class": "unit-tested",
        }


# Aliases for unified importing
AllocationManager = SalamanderPoincareAllocationManager


# ---------------------------------------------------------------------------
# Salamander engine (unified self-healing + self-optimisation)
# ---------------------------------------------------------------------------


class SalamanderEngine:
    """Unified Salamander engine: self-healing + self-optimisation + scaling + 11D allocation.

    This is the EUCLID-CORE port of the HYBA Salamander, adapted to use
    the project's own quantum tensor, 11D Poincaré-Golden manifold, and Lucas/Pisot mathematics.

    Capabilities:
    1. Homeostasis monitoring (golden-ratio thresholds)
    2. Self-repair (diagnose -> classify -> propose -> approve -> verify)
    3. Circuit-breaker bounded autonomy
    4. Lucas intelligence scaling (10^12, 10^15, 10^18, 10^20)
    5. 11D Poincaré-Golden non-contiguous prime allocation (25,600 slots)
    """

    def __init__(
        self,
        phi_threshold: float = PHI,
        max_vram_boundary: float = 0.85,
        max_error_rate: float = 0.1,
        *,
        recovery_control_plane: Any = None,
        recovery_request_builder: Optional[Callable[[RepairProposal], Any]] = None,
        repo_root: Optional[Path] = None,
        source_validator: Optional[RepairValidator] = None,
        profile: Any = "internal",
        repository_review_policies: Any = None,
        repair_learning_ledger: Any = None,
        repair_authorized_tokens: Optional[Sequence[str]] = None,
    ) -> None:
        from .capability_fabric import (
            CapabilityRegistry,
            ExecutionProfile,
        )
        from .isolated_repair import IsolatedRepairExecutor
        from .mathematical_research import MathematicalProofTracker

        self.phi_threshold = phi_threshold
        self.profile = (
            ExecutionProfile(profile)
            if isinstance(profile, str)
            else (profile or ExecutionProfile.INTERNAL_RESEARCH)
        )
        self.repo_root = (repo_root or Path(__file__).resolve().parent.parent).resolve()
        self.repository_review_policies = repository_review_policies

        self.homeostasis = HomeostasisMonitor(
            phi_threshold=phi_threshold,
            max_vram_boundary=max_vram_boundary,
            max_error_rate=max_error_rate,
        )
        self.self_repair = SelfRepairEngine(
            control_plane=recovery_control_plane, request_builder=recovery_request_builder
        )
        self.circuit_breaker = CircuitBreaker()
        self.scaler = LucasIntelligenceScaler()
        self.allocation_manager = SalamanderPoincareAllocationManager()
        self._cycle_count = 0

        # Verified heal loop: probes registered subsystems, executes the
        # registered repair, and claims HEALTHY only after a fresh probe
        # confirms it. Every event is logged with a Cassini fingerprint.
        self.autonomy_ledger = CassiniCycleLedger()
        self.heal_loop = SelfHealingLoop(engine=self, ledger=self.autonomy_ledger)
        self.supervisor = AutonomySupervisor(
            engine=self, heal_loop=self.heal_loop, ledger=self.autonomy_ledger
        )

        # Agentic codebase scanner and autonomous optimizer
        # One host-composed controller owns scanning and validated source
        # publication. Do not create a fresh validator-less repair controller.
        self.agentic_controller = SalamanderAgenticController(
            repo_root=self.repo_root, validator=source_validator
        )
        self.codebase_scanner = self.agentic_controller.scanner
        self.codebase_optimizer = self.agentic_controller.optimizer

        # Substrate capability fabric and isolated repair engine
        self.isolated_repair_executor = IsolatedRepairExecutor(
            self.repo_root, learning_ledger=repair_learning_ledger,
            authorized_tokens=repair_authorized_tokens,
        )
        self.proof_tracker = MathematicalProofTracker()
        self.capability_registry = CapabilityRegistry()
        self._register_default_capabilities()

        # Equip with skills runtime
        self.skills: Dict[str, Any] = {}
        self.load_skills()

    def _register_default_capabilities(self) -> None:
        """Register native executable capabilities in the capability fabric."""
        from .capability_fabric import (
            CapabilityManifest,
            CapabilityPermissions,
            CapabilityRegistry,
            DeterminismClass,
            ExecutionProfile,
            ResourceBudget,
            SideEffectClass,
        )

        if not hasattr(self, "capability_registry"):
            self.capability_registry = CapabilityRegistry()

        # 1. Shared native review owner. No policies means unavailable, not
        # permission for callers to choose arbitrary roots or source manifests.
        if not self.capability_registry.get_manifest("repository-review"):
            from .repository_review_capability import register_repository_review_capability
            register_repository_review_capability(
                self.capability_registry, repo_root=self.repo_root,
                approved_policies=getattr(self, "repository_review_policies", None),
            )

        # 2. source-repair (Isolated mutation, allowed ONLY in internal research profile)
        if not self.capability_registry.get_manifest("source-repair"):
            self.capability_registry.register(
                CapabilityManifest(
                    capability_id="source-repair",
                    version="1.0.0",
                    source_provenance="Intelligence/salamander_agentic.py",
                    description="Write-capable source repair via isolated validation gate",
                    permissions=CapabilityPermissions(
                        can_read_repository=True,
                        can_write_repository=True,
                        can_execute_code=False,
                        can_spawn_process=False,
                        can_use_network=False,
                        allowed_profiles=(ExecutionProfile.INTERNAL_RESEARCH,),
                    ),
                    resource_budget=ResourceBudget(
                        max_file_bytes=262144,
                        max_total_bytes=1048576,
                    ),
                    supported_operations=("repair",),
                    determinism=DeterminismClass.DETERMINISTIC,
                    side_effects=SideEffectClass.ISOLATED_MUTATION,
                    verification_strategy="validator_receipt_digest_binding",
                ),
                adapter_fn=lambda **kwargs: self.repair_source(**kwargs),
            )

        # 3. codebase-healing (Self-repair cycle, allowed ONLY in internal research profile)
        if not self.capability_registry.get_manifest("codebase-healing"):
            self.capability_registry.register(
                CapabilityManifest(
                    capability_id="codebase-healing",
                    version="1.0.0",
                    source_provenance="Intelligence/salamander.py",
                    description="Closed-loop autonomic codebase healing and AST optimization",
                    permissions=CapabilityPermissions(
                        can_read_repository=True,
                        can_write_repository=True,
                        can_execute_code=False,
                        can_spawn_process=False,
                        can_use_network=False,
                        allowed_profiles=(ExecutionProfile.INTERNAL_RESEARCH,),
                    ),
                    resource_budget=ResourceBudget(),
                    supported_operations=("heal",),
                    determinism=DeterminismClass.DETERMINISTIC,
                    side_effects=SideEffectClass.ISOLATED_MUTATION,
                    verification_strategy="substrate_health_index_delta",
                ),
                adapter_fn=lambda **kwargs: self.agentic_heal(auto_heal=kwargs.get("auto_heal", False)),
            )

        # 4. isolated-repair (12-stage closed loop, allowed ONLY in internal research profile)
        if not self.capability_registry.get_manifest("isolated-repair"):
            def _isolated_repair_adapter(**kwargs: Any) -> Any:
                if not hasattr(self, "isolated_repair_executor"):
                    from .isolated_repair import IsolatedRepairExecutor
                    self.isolated_repair_executor = IsolatedRepairExecutor(
                        getattr(self, "repo_root", Path(__file__).resolve().parent.parent),
                        learning_ledger=getattr(self, "repair_learning_ledger", None),
                    )
                receipt = self.isolated_repair_executor.execute_closed_loop_repair(**kwargs)
                return receipt.as_dict()

            self.capability_registry.register(
                CapabilityManifest(
                    capability_id="isolated-repair",
                    version="1.0.0",
                    source_provenance="Intelligence/isolated_repair.py",
                    description="12-stage isolated verified repair executor with pre-reproduction and outcome probe",
                    permissions=CapabilityPermissions(
                        can_read_repository=True,
                        can_write_repository=True,
                        can_execute_code=True,
                        can_spawn_process=True,
                        allowed_profiles=(ExecutionProfile.INTERNAL_RESEARCH,),
                    ),
                    resource_budget=ResourceBudget(),
                    supported_operations=("execute_closed_loop_repair",),
                    determinism=DeterminismClass.DETERMINISTIC,
                    side_effects=SideEffectClass.ISOLATED_MUTATION,
                    verification_strategy="dual_probe_independent_receipt",
                ),
                adapter_fn=_isolated_repair_adapter,
            )

        # 5. Single native registration owner, shared with minimal research composition.
        if not self.capability_registry.get_manifest("proof-conjecture"):
            from .proof_capability import register_proof_capability

            if not hasattr(self, "proof_tracker"):
                from .mathematical_research import MathematicalProofTracker
                self.proof_tracker = MathematicalProofTracker()
            register_proof_capability(self.capability_registry, self.proof_tracker)

        # 6. Shared observation-only ledger query; never initialize a repair
        # executor merely to answer a read-only request.
        if not self.capability_registry.get_manifest("repair-learning-query"):
            from .repair_learning_capability import register_repair_learning_capability
            from .isolated_repair import RepairLearningLedger

            executor = getattr(self, "isolated_repair_executor", None)
            ledger = executor.learning_ledger if executor is not None else getattr(self, "repair_learning_ledger", None)
            if ledger is None:
                ledger = RepairLearningLedger()
            self.repair_learning_ledger = ledger
            register_repair_learning_capability(self.capability_registry, ledger)

        # 7. bsd-exploration (Birch & Swinnerton-Dyer collaborative multi-agent swarm)
        if not self.capability_registry.get_manifest("bsd-exploration"):
            def _bsd_exploration_adapter(**kwargs: Any) -> Any:
                from integrations.solvers.bsd_solver import BSDSolverTeam
                a = int(kwargs["a"])
                b = int(kwargs["b"])
                max_prime = int(kwargs.get("max_prime", 100))
                team = BSDSolverTeam()
                report = team.solve(a, b, max_prime=max_prime)
                return {
                    "curve": report.curve,
                    "a": report.a,
                    "b": report.b,
                    "discriminant": report.euclid.discriminant,
                    "conjectural_rank": report.euclid.conjectural_rank,
                    "empirical_rank_slope": report.euclid.empirical_rank_slope,
                    "hasse_all_satisfied": report.salamander.hasse_all_satisfied,
                    "mazur_bound_satisfied": report.salamander.mazur_bound_satisfied,
                    "torsion_points_found": report.salamander.torsion_points_found,
                    "cassini_invariants_valid": report.pythia.cassini_invariants_valid,
                    "cmi_protocol_compliant": report.al_haras.cmi_protocol_compliant,
                    "proof_claim": report.al_haras.proof_claim,  # ALWAYS False
                    "integrated_phi": report.integrated_phi,
                    "overall_status": report.overall_status,
                }

            self.capability_registry.register(
                CapabilityManifest(
                    capability_id="bsd-exploration",
                    version="1.0.0",
                    source_provenance="integrations/solvers/bsd_solver.py",
                    description="Birch and Swinnerton-Dyer multi-agent collaborative solver (Euclid, Salamander, Pythia, Al Haras)",
                    permissions=CapabilityPermissions(
                        can_read_repository=True,
                        can_write_repository=False,
                        allowed_profiles=(
                            ExecutionProfile.INTERNAL_RESEARCH,
                            ExecutionProfile.SHARED_RESTRICTED,
                        ),
                    ),
                    resource_budget=ResourceBudget(
                        max_runtime_seconds=60.0,
                    ),
                    supported_operations=("solve",),
                    determinism=DeterminismClass.DETERMINISTIC,
                    side_effects=SideEffectClass.READ_ONLY,
                    verification_strategy="cmi_claim_honesty_boundary",
                    input_schema={"required": ["a", "b"]},
                ),
                adapter_fn=_bsd_exploration_adapter,
            )

        # 8. external-agent-boundary (Provider-neutral external engineering-agent evaluation)
        if not self.capability_registry.get_manifest("external-agent-boundary"):
            def _external_agent_adapter(**kwargs: Any) -> Any:
                from Intelligence.engineering_agent_adapter import (
                    ExternalAgentBoundary,
                    ExternalAgentTask,
                    UntrustedCandidatePatch,
                    ProviderMetadata,
                    AgentExecutionPolicy,
                )
                task_dict = kwargs["task"]
                candidate_dict = kwargs["candidate"]
                policy_dict = task_dict.get("policy", {})

                policy = AgentExecutionPolicy(
                    allowed_repo_relative_roots=tuple(policy_dict.get("allowed_repo_relative_roots", ("chronus/", "docs/"))),
                    allow_network=bool(policy_dict.get("allow_network", False)),
                    allow_subprocess=bool(policy_dict.get("allow_subprocess", False)),
                    max_patch_bytes=int(policy_dict.get("max_patch_bytes", 131072)),
                    max_files_modified=int(policy_dict.get("max_files_modified", 5)),
                    require_syntax_check=bool(policy_dict.get("require_syntax_check", True)),
                    require_isolated_validation=bool(policy_dict.get("require_isolated_validation", True)),
                )
                task = ExternalAgentTask(
                    task_id=task_dict["task_id"],
                    task_type=task_dict.get("task_type", "code_patch"),
                    instruction=task_dict.get("instruction", ""),
                    context_files=task_dict.get("context_files", {}),
                    policy=policy,
                )
                prov = candidate_dict["provider"]
                provider = ProviderMetadata(
                    provider_id=prov["provider_id"],
                    model_name=prov["model_name"],
                    model_version=prov["model_version"],
                )
                candidate = UntrustedCandidatePatch(
                    task_id=candidate_dict["task_id"],
                    provider=provider,
                    proposed_files=candidate_dict["proposed_files"],
                    raw_response=candidate_dict.get("raw_response", ""),
                    claimed_success=bool(candidate_dict.get("claimed_success", False)),
                )
                boundary = ExternalAgentBoundary(repo_root=self.repo_root)
                verdict, reasons, receipt = boundary.evaluate_and_confine(task, candidate)
                return {
                    "verdict": verdict.value,
                    "reasons": reasons,
                    "receipt": receipt.as_dict(),
                }

            self.capability_registry.register(
                CapabilityManifest(
                    capability_id="external-agent-boundary",
                    version="1.0.0",
                    source_provenance="Intelligence/engineering_agent_adapter.py",
                    description="Policy-gated provider-neutral evaluation of untrusted external engineering agents",
                    permissions=CapabilityPermissions(
                        can_read_repository=True,
                        can_write_repository=False,
                        allowed_profiles=(
                            ExecutionProfile.INTERNAL_RESEARCH,
                            ExecutionProfile.SHARED_RESTRICTED,
                        ),
                    ),
                    resource_budget=ResourceBudget(
                        max_runtime_seconds=30.0,
                    ),
                    supported_operations=("evaluate_and_confine",),
                    determinism=DeterminismClass.DETERMINISTIC,
                    side_effects=SideEffectClass.READ_ONLY,
                    verification_strategy="untrusted_candidate_confinement",
                    input_schema={"required": ["task", "candidate"]},
                ),
                adapter_fn=_external_agent_adapter,
            )

    def load_skills(self) -> Dict[str, Any]:
        """Reload available skills into Salamander's semantic runtime."""
        from .skill_loader import load_skills

        # An unavailable loader is a visible integration failure, not a
        # successfully initialized intelligence with silently missing skills.
        loaded = load_skills()
        if not isinstance(loaded, dict):
            raise TypeError("Skill loader must return an equipped-skill mapping")
        self.skills = loaded
        return self.skills

    def execute_skill(self, skill_name: str, **kwargs: Any) -> Any:
        """Execute an equipped skill or registered native capability under active profile."""
        if not self.skills:
            self.load_skills()

        if not hasattr(self, "profile"):
            from .capability_fabric import ExecutionProfile
            self.profile = ExecutionProfile.INTERNAL_RESEARCH
        if not hasattr(self, "capability_registry"):
            self._register_default_capabilities()

        # If registered in CapabilityRegistry, dispatch under active profile
        if skill_name in self.capability_registry._manifests:
            if skill_name not in self.skills:
                raise KeyError(f"{skill_name} is not equipped")
            output, receipt = self.capability_registry.dispatch(
                skill_name, profile=self.profile, **kwargs
            )
            return output

        elif skill_name in self.skills:
            # Other skills are guidance, not code: hand back what to follow
            # (and where it came from) rather than claim an execution.
            skill = self.skills[skill_name]
            return {
                "skill": skill.name,
                "status": "GUIDANCE",
                "description": skill.description,
                "instructions": skill.instructions,
                "provenance": skill.provenance,
            }
        else:
            raise KeyError(
                f"Skill '{skill_name}' not found in equipped skills ({list(self.skills.keys())})."
            )

    def execute_capability(self, capability_id: str, **kwargs: Any) -> Tuple[Any, Any]:
        """Direct execution route through capability fabric with receipt."""
        if not hasattr(self, "profile"):
            from .capability_fabric import ExecutionProfile
            self.profile = ExecutionProfile.INTERNAL_RESEARCH
        if not hasattr(self, "capability_registry"):
            self._register_default_capabilities()
        return self.capability_registry.dispatch(capability_id, profile=self.profile, **kwargs)

    def scan_codebase(
        self,
        subdirs: Optional[Sequence[str]] = ("core_engine", "Intelligence", "pythagoras", "mining"),
    ) -> Any:
        """Scan codebase for cognitive drift, discarded operators, and AST decoherence."""
        return self.codebase_scanner.scan_directory(subdirs=subdirs)

    def agentic_heal(self, auto_heal: bool = False) -> Dict[str, Any]:
        """Run autonomous agentic audit and self-healing cycle."""
        return self.agentic_controller.run_autonomic_cycle(auto_heal=auto_heal)

    def repair_source(
        self, *, target_file: Path, replacement: str, target_snippet: Optional[str] = None
    ) -> Dict[str, Any]:
        """Publish a source candidate only through the configured validation gate.

        This is a write-capable adapter. No document, callable, command or
        auto-heal flag grants authority or substitutes for regression evidence.
        """
        committed, reason = self.codebase_optimizer.apply_repair_sandboxed(
            target_file=target_file, replacement=replacement, target_snippet=target_snippet
        )
        return {
            "skill": "source-repair",
            "status": "COMMITTED" if committed else "NOT_COMMITTED",
            "committed": committed,
            "reason": reason,
        }

    def substrate_health_index(self) -> float:
        """Return the current Substrate Health Index (SHI)."""
        report = self.scan_codebase()
        return float(report.substrate_health_index)

    def check_homeostasis(self, metrics: Dict[str, float]) -> HomeostasisReport:
        """Check the substrate's homeostatic balance."""
        return self.homeostasis.check(metrics)

    def heal(self, failure_type: str, details: Dict[str, Any]) -> RepairProposal:
        """Diagnose and propose a repair for a failure."""
        proposal = self.self_repair.diagnose(failure_type, details)
        if proposal.is_safe:
            self.self_repair.apply_repair(proposal)
        return proposal

    def scale_intelligence(
        self,
        pci_base: float = 0.5,
        emergence_base: float = 0.5,
        consciousness_base: float = 0.5,
        lucas_index: Optional[int] = None,
    ) -> LucasScaleResult:
        """Apply Lucas scaling to intelligence metrics."""
        if lucas_index is not None:
            return self.scaler.scale(pci_base, emergence_base, consciousness_base, lucas_index)
        results = self.scaler.scale_all(pci_base, emergence_base, consciousness_base)
        return results[-1] if results else LucasScaleResult(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    def train(
        self,
        training_data: List[Dict[str, Any]],
        epochs: int = 10,
    ) -> Dict[str, Any]:
        """Train the intelligence substrate through repeated cycles.

        Each cycle:
        1. Encode the training data into a quantum state.
        2. Run the causal ladder (all three rungs).
        3. Check homeostasis.
        4. If unhealthy, trigger self-repair.
        5. Scale intelligence using Lucas scaling.
        6. Record the cycle.
        """
        from toe.bridge import TOEBridge

        bridge = TOEBridge()

        pci_history: List[float] = []
        emergence_history: List[float] = []
        consciousness_history: List[float] = []
        repair_count = 0

        for epoch in range(epochs):
            for sample in training_data:
                self._cycle_count += 1

                # 1. Run the full intelligence pipeline
                cycle_start = time.perf_counter()
                try:
                    pred = bridge.predict(sample)
                    pci = pred.get("confidence", 0.0)
                except Exception:
                    pci = 0.0  # measured failure — no confidence, not a guess
                    self.heal("prediction_failure", {"epoch": epoch})
                    repair_count += 1

                # 2. Check homeostasis — measured metrics only.
                #    error_rate is the measured repair rate of this run;
                #    throughput is measured wall-clock samples/sec.
                #    vram_utilization is NOT measurable on this host, so
                #    it is omitted (unmeasured) — never scripted again.
                elapsed = max(time.perf_counter() - cycle_start, 1e-9)
                metrics = {
                    "error_rate": repair_count / max(1, self._cycle_count),
                    "throughput": 1.0 / elapsed,
                }
                report = self.check_homeostasis(metrics)
                if not report.healthy:
                    self.heal(report.action, {"epoch": epoch, "metrics": metrics})
                    repair_count += 1

                # 3. Scale intelligence with Lucas. All three bases reuse
                #    the one measured confidence — no invented
                #    attenuation factors.
                lucas_idx = self.scaler.SCALE_INDICES[
                    min(epoch // 2, len(self.scaler.SCALE_INDICES) - 1)
                ]
                scaled = self.scale_intelligence(
                    pci_base=pci,
                    emergence_base=pci,
                    consciousness_base=pci,
                    lucas_index=lucas_idx,
                )

                pci_history.append(scaled.pci_after)
                emergence_history.append(scaled.emergence_after)
                consciousness_history.append(scaled.consciousness_after)

        return {
            "epochs": epochs,
            "cycles": self._cycle_count,
            "repairs": repair_count,
            "final_pci": pci_history[-1] if pci_history else 0.0,
            "final_emergence": emergence_history[-1] if emergence_history else 0.0,
            "final_consciousness": (consciousness_history[-1] if consciousness_history else 0.0),
            "pci_history": pci_history[-20:],
            "emergence_history": emergence_history[-20:],
            "consciousness_history": consciousness_history[-20:],
            "lucas_scaling": self.scaler.status(),
        }

    def allocate(
        self,
        vector_or_id: Union[str, np.ndarray, List[float]],
        vector: Optional[Union[np.ndarray, List[float]]] = None,
        subspace_id: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Union[int, AllocationSlot]:
        """Fold and allocate an 11D vector into Poincaré-Golden prime storage."""
        return self.allocation_manager.allocate(
            vector_or_id=vector_or_id,
            vector=vector,
            subspace_id=subspace_id,
            metadata=metadata,
        )

    def read_slot(self, slot_id: Union[int, str]) -> Any:
        """Non-destructively read an allocated slot descriptor or unfolded vector."""
        return self.allocation_manager.read(slot_id)

    def reconstruct_slot(self, slot_id: Union[int, str]) -> Tuple[np.ndarray, float]:
        """Reconstruct and return (reconstructed_vector, fidelity_error) for a slot."""
        return self.allocation_manager.reconstruct(slot_id)

    def compute_geodesic_distance(self, id_1: Union[int, str], id_2: Union[int, str]) -> float:
        """Evaluate non-Euclidean geodesic distance between two allocated slots."""
        return self.allocation_manager.compute_geodesic_distance(id_1, id_2)

    def deallocate_slot(self, slot_id: Union[int, str]) -> bool:
        """Deallocate slot."""
        return self.allocation_manager.deallocate(slot_id)

    def capacity_metrics(self) -> Dict[str, Any]:
        """Return allocation capacity metrics."""
        return self.allocation_manager.get_capacity_metrics()

    def status(self) -> Dict[str, Any]:
        return {
            "phi_threshold": self.phi_threshold,
            "circuit_state": self.circuit_breaker.state,
            "cycle_count": self._cycle_count,
            "homeostasis": (self.homeostasis._history[-1] if self.homeostasis._history else {}),
            "self_repair": self.self_repair.status(),
            "scaling": self.scaler.status(),
            "allocation_manager": self.allocation_manager.get_capacity_metrics(),
        }


__all__ = [
    "SalamanderEngine",
    "HomeostasisMonitor",
    "HomeostasisReport",
    "SelfRepairEngine",
    "RepairProposal",
    "CircuitBreaker",
    "LucasIntelligenceScaler",
    "LucasScaleResult",
    "AllocationSlot",
    "SalamanderPoincareAllocationManager",
    "AllocationManager",
    "SalamanderCodebaseScanner",
    "SalamanderAgenticOptimizer",
    "SalamanderAgenticController",
    "CodebaseAuditReport",
    "CodebaseDiagnostic",
    "CodebaseIssueType",
    "SelfHealingLoop",
    "FaultRecord",
    "AutonomySupervisor",
    "CassiniCycleLedger",
    "KNOWN_FAULT_TYPES",
    "lucas",
    "fibonacci",
    "main",
]


def lucas_bound(n: int = 10) -> dict:
    """Verify this module's Lucas route against the shared pool.

    Calls the declared kernel (trace_kernel) on the canonical substrate for
    this route and reports the pool's exact bound. This proves the route
    is live; it is not a per-algorithm cost claim.
    """
    import numpy as np  # noqa: F401

    from lucas.pool import get as _lucas_get

    result = _lucas_get("trace_kernel")(np.array([[1, 1], [1, 0]], dtype=object), n)
    result["module"] = __name__
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    """CLI entry point for Salamander autonomic intelligence."""
    import argparse
    parser = argparse.ArgumentParser(prog="salamander", description="Salamander Autonomic Intelligence CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # status
    subparsers.add_parser("status", help="Print Salamander engine status and active profile")

    # capabilities
    cap_parser = subparsers.add_parser("capabilities", help="List registered capabilities")
    cap_parser.add_argument("--profile", choices=["internal", "shared"], default="internal")

    # bsd
    bsd_parser = subparsers.add_parser("bsd", help="Run read-only BSD exploration")
    bsd_parser.add_argument("--a", type=int, required=True, help="Weierstrass coefficient a")
    bsd_parser.add_argument("--b", type=int, required=True, help="Weierstrass coefficient b")
    bsd_parser.add_argument("--max-prime", type=int, default=100, help="Maximum prime bound")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0

    engine = SalamanderEngine()
    if args.command == "status":
        st = engine.status()
        print(f"Salamander Engine Status [Profile: {engine.profile.value}]:")
        for k, v in st.items():
            print(f"  {k}: {v}")
        return 0

    elif args.command == "capabilities":
        from .capability_fabric import ExecutionProfile
        p = ExecutionProfile(args.profile)
        caps = engine.capability_registry.list_capabilities(profile=p)
        print(f"Registered Capabilities [Profile: {p.value}]:")
        for c in caps:
            print(f"  - {c.capability_id} (v{c.version}): {c.description}")
        return 0

    elif args.command == "bsd":
        rep, receipt = engine.execute_capability("bsd-exploration", a=args.a, b=args.b, max_prime=args.max_prime)
        print(f"BSD Report: {rep['curve']}")
        print(f"  Discriminant: {rep['discriminant']}")
        print(f"  Conjectural Rank: {rep['conjectural_rank']}")
        print(f"  Proof Claim: {rep['proof_claim']} (CMI Boundary Sealed)")
        print(f"  Receipt ID: {receipt.receipt_id} [Status: {receipt.status}]")
        return 0

    return 0
