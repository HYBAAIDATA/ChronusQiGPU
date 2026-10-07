"""Canonical immutable SearchPlan contract for the agentic mining pipeline.

A SearchPlan is issued by the Intelligence layer and consumed by the executor.
It is immutable after issuance. The executor may not reinterpret its fields.

Work identity is owned by Stratum. A plan carries the ``WorkIdentity`` it was
issued against (pool session, Stratum generation, Stratum fingerprint) and is
valid only while all three still equal the live Stratum identity. The agentic
layer never decides on its own that two Stratum jobs are equivalent.

Separation of authority:
  - Intelligence issues plans (WHEN, WHERE, HOW MUCH, WHICH LANE, WHICH ORDER)
  - Chronus owns vendor-neutral physical execution admission and dispatch
  - SHA256d / target comparison / Stratum remain the sole proof authorities
  - A plan is never a proof; it is a search direction over a leased range
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

_LANES = 32
_VALID_ROUTES = frozenset(
    ("cpu_reference", "chronus_batch", "opencl_m32", "opencl_gold", "opencl_range")
)
_VALID_NONCE_ORDERS = frozenset(
    (
        "m32_turing_complete",
        "klein_poincare_numerical",
        "sequential",
        "golden_stride",
        "poincare_cassini_11d",
        "hendrix_coprime_stride",
    )
)
_DEFAULT_NONCE_ORDER = "hendrix_coprime_stride"


class PlanSource(str, Enum):
    AGENTIC_PRECOMPUTED = "AGENTIC_PRECOMPUTED"
    BASELINE_FALLBACK = "BASELINE_FALLBACK"


class ExecutionRoute(str, Enum):
    """Routes the executor can physically run.

    ``chronus_batch`` is the canonical vendor-neutral Chronus route. It
    consumes an exact ordered nonce batch through the bound execution
    contract, so Chronus is not defined in terms of CUDA, NVIDIA, OpenCL,
    Metal, or another vendor runtime. The OpenCL-named routes remain
    compatibility routes for implementations that physically expose those
    kernel arms. ``cpu_reference`` remains the independent software oracle.
    """

    cpu_reference = "cpu_reference"
    chronus_batch = "chronus_batch"
    opencl_gold = "opencl_gold"
    opencl_m32 = "opencl_m32"
    opencl_range = "opencl_range"


class CompletionState(str, Enum):
    """Explicit execution outcome.

    A multi-chunk execution that stops early for a recorded reason is
    INVALIDATED or PARTIAL, never COMPLETE.
    """

    COMPLETE = "COMPLETE"
    EARLY_WINNER = "EARLY_WINNER"
    INVALIDATED = "INVALIDATED"
    DEVICE_ERROR = "DEVICE_ERROR"
    FALLBACK_COMPLETE = "FALLBACK_COMPLETE"
    PARTIAL = "PARTIAL"
    REFUSED = "REFUSED"


class FallbackReason(str, Enum):
    """Why a requested route did not execute as requested.

    Unknown stays unknown: an unrecognised cause is never rounded up to a
    success-sounding value, and never left blank on a fallback.
    """

    NONE = "NONE"
    CHRONUS_BATCH_UNAVAILABLE = "CHRONUS_BATCH_UNAVAILABLE"
    OPENCL_UNAVAILABLE = "OPENCL_UNAVAILABLE"
    KERNEL_UNAVAILABLE = "KERNEL_UNAVAILABLE"
    ROUTE_REFUSED = "ROUTE_REFUSED"
    STALE_PLAN = "STALE_PLAN"
    LEASE_INVALID = "LEASE_INVALID"
    DEVICE_ERROR = "DEVICE_ERROR"
    WORKGROUP_UNSUPPORTED = "WORKGROUP_UNSUPPORTED"


class EvidenceClass(str, Enum):
    """Hardware evidence tiers. Never upgrade a class without execution."""

    SOFTWARE_VERIFIED = "SOFTWARE_VERIFIED"
    DEVICE_AVAILABLE = "DEVICE_AVAILABLE"
    HARDWARE_EXECUTED = "HARDWARE_EXECUTED"
    POOL_CONFIRMED = "POOL_CONFIRMED"


VALID_ROUTES = frozenset(r.value for r in ExecutionRoute)


class LeaseState(str, Enum):
    """Nonce-lease lifecycle. Execution may only advance a live lease."""

    RESERVED = "RESERVED"
    EXECUTING = "EXECUTING"
    COMPLETE = "COMPLETE"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True)
class NonceLease:
    """Generation-scoped lease over an exact nonce interval.

    This is the *shape* of the lease Claude's integration layer is expected to
    supply. It deliberately carries no global registry: the owner of the lease
    ledger is upstream, and this module only states the contract execution
    honours. A caller passes a lease in and gets it back transitioned; it never
    reads or mutates a shared ledger of its own.

    Invariants enforced in ``__post_init__``:

    * the interval is a half-open ``[start, start + count)`` over uint32;
    * a COMPLETE or INVALIDATED lease can never be executed again;
    * a lease for a different generation than the plan is refused.
    """

    lease_id: str
    generation: int
    plan_id: str
    start: int
    count: int
    state: LeaseState = LeaseState.RESERVED

    def __post_init__(self) -> None:
        if not self.lease_id or not self.plan_id:
            raise ValueError("lease_id and plan_id are required")
        if self.generation <= 0:
            raise ValueError("lease generation must be positive")
        if self.start < 0 or self.start > 0xFFFFFFFF:
            raise ValueError("lease start must be a valid uint32")
        if self.count <= 0:
            raise ValueError("lease count must be positive")
        if self.start + self.count > 0x100000000:
            raise ValueError("lease interval must stay within the uint32 domain")
        object.__setattr__(self, "state", LeaseState(self.state))

    @property
    def end(self) -> int:
        return self.start + self.count

    def is_executable_for(self, plan: "SearchPlan") -> bool:
        """True only for a live lease belonging to this plan and generation."""
        return (
            self.state is LeaseState.RESERVED
            and self.plan_id == plan.plan_id
            and self.generation == plan.generation
        )

    def transition(self, state: LeaseState) -> "NonceLease":
        """Return a new lease in ``state``; never mutate in place."""
        return NonceLease(
            lease_id=self.lease_id,
            generation=self.generation,
            plan_id=self.plan_id,
            start=self.start,
            count=self.count,
            state=LeaseState(state),
        )


class PoolOutcome(str, Enum):
    """Literal submission outcome. Only Stratum responses populate the last three."""

    NO_CANDIDATE = "NO_CANDIDATE"
    NOT_SUBMITTED = "NOT_SUBMITTED"
    STALE = "STALE"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    OUTCOME_UNKNOWN = "OUTCOME_UNKNOWN"


@dataclass(frozen=True)
class WorkIdentity:
    """Projection of Stratum's ``StratumJobGeneration`` plus its TCP session.

    Built only from ``StratumRuntimeState``; never computed by Intelligence.
    """

    pool_session_id: str
    generation: int
    job_id: str
    job_fingerprint: str
    target_generation: int
    clean_jobs: bool
    received_at: float
    # Hash of only the fields that determine header bytes (not job_id or the
    # share target): identical work spaces must never be hashed twice.
    work_space: str | None = None

    def __post_init__(self) -> None:
        if not self.pool_session_id or not self.job_id or not self.job_fingerprint:
            raise ValueError("pool_session_id, job_id and job_fingerprint are required")
        if self.generation <= 0 or self.target_generation < 0:
            raise ValueError("Stratum generations must be positive")

    @property
    def key(self) -> tuple[str, int, str]:
        return (self.pool_session_id, self.generation, self.job_fingerprint)


@dataclass(frozen=True)
class SearchPlan:
    """Immutable plan issued by Intelligence, consumed by the executor.

    ``base_step``/``window`` are the leased nonce range start and requested
    budget on the header built from ``extranonce2``. The executor scans
    exactly that range; it does not re-derive or expand any field. ``nonce_order``
    is plan-bound so queued work cannot be reinterpreted by later coordinator
    configuration or strategy-state changes.
    """

    job_fingerprint: str
    pool_session_id: str
    generation: int
    base_step: int
    window: int
    extranonce2: str
    lane_order: tuple[int, ...]
    preferred_face: int
    dispatch_breadth: int
    executor_route: str
    policy_id: str
    evidence_refs: Mapping[str, Any]
    created_at: float
    plan_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    nonce_order: str = _DEFAULT_NONCE_ORDER
    toe_frame_id: str | None = None
    source: PlanSource = PlanSource.AGENTIC_PRECOMPUTED
    schedule: tuple[int, ...] = ()
    expires_at: float | None = None
    # Why no agentic plan ran; required for BASELINE_FALLBACK, forbidden otherwise.
    plan_fallback_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.job_fingerprint or not self.pool_session_id:
            raise ValueError("job_fingerprint and pool_session_id are required")
        if self.generation <= 0:
            raise ValueError("generation must be a positive Stratum generation")
        if self.base_step < 0 or self.base_step > 0xFFFFFFFF:
            raise ValueError("base_step must be a valid uint32")
        if type(self.window) is not int or self.window <= 0:
            raise ValueError("window must be a positive integer")
        if type(self.base_step) is not int or self.base_step + self.window > 1 << 32:
            raise ValueError("plan lease must remain inside uint32")
        if len(self.lane_order) != _LANES or sorted(self.lane_order) != list(range(_LANES)):
            raise ValueError("lane_order must contain every M32 lane exactly once")
        if not (0 <= self.preferred_face < _LANES):
            raise ValueError("preferred_face must be in [0, 31]")
        if self.dispatch_breadth <= 0:
            raise ValueError("dispatch_breadth must be positive")
        if self.executor_route not in _VALID_ROUTES:
            raise ValueError(f"unsupported executor_route: {self.executor_route!r}")
        if self.nonce_order not in _VALID_NONCE_ORDERS:
            raise ValueError(f"unsupported nonce_order: {self.nonce_order!r}")
        if not self.policy_id:
            raise ValueError("policy_id is required")
        if self.created_at <= 0:
            raise ValueError("created_at must be a positive monotonic timestamp")
        if self.expires_at is not None and self.expires_at <= self.created_at:
            raise ValueError("expires_at must be after created_at")
        object.__setattr__(self, "source", PlanSource(self.source))
        if self.source is PlanSource.BASELINE_FALLBACK and not self.plan_fallback_reason:
            raise ValueError("a baseline plan must say why no agentic plan ran")
        if self.source is PlanSource.AGENTIC_PRECOMPUTED and self.plan_fallback_reason:
            raise ValueError("an agentic plan cannot carry a plan_fallback_reason")
        refs = dict(self.evidence_refs)
        if "resident_hendrix" in refs:
            from chronus.resident_hendrix import ImmutableJSONMapping, canonical
            refs["resident_hendrix"] = ImmutableJSONMapping(canonical(refs["resident_hendrix"]))
        if self.toe_frame_id is not None:
            if not self.toe_frame_id:
                raise ValueError("toe_frame_id cannot be empty")
            if refs.get("toe_frame_digest") != self.toe_frame_id:
                raise ValueError("toe_frame_id must match evidence_refs.toe_frame_digest")
        object.__setattr__(self, "evidence_refs", MappingProxyType(refs))

    def is_valid_for(self, identity: WorkIdentity | None) -> bool:
        """False unless session, Stratum generation and fingerprint all match."""
        if identity is None:
            return False
        if (
            self.pool_session_id != identity.pool_session_id
            or self.generation != identity.generation
            or self.job_fingerprint != identity.job_fingerprint
        ):
            return False
        if self.expires_at is not None and time.monotonic() >= self.expires_at:
            return False
        return True


@dataclass(frozen=True)
class ExecutionRecord:
    """Measured outcome for one executed search.

    Only measured values may populate this record. ``plan_source`` states
    whether an agentic SearchPlan or the baseline fallback actually executed;
    ``plan_id`` is None for baseline work and ``plan_fallback_reason`` says why
    no plan ran. ``fallback_reason`` is reserved for *route* fallback
    (requested_route != executed_route). Pool counters come only from the
    literal Stratum response carried in ``pool_outcome``.
    """

    plan_id: str | None
    job_fingerprint: str
    policy_id: str
    planned_window: int
    actual_window: int
    device_used: str
    hash_count: int
    elapsed_seconds: float
    kernel_ms: float
    temperature_c: float | None
    locally_valid_shares: int
    pool_accepted: int
    pool_rejected: int
    pool_stale: int
    recovery_event: bool
    lane_order: tuple[int, ...]
    preferred_face: int
    plan_source: PlanSource = PlanSource.AGENTIC_PRECOMPUTED
    fallback_reason: str | None = None
    plan_fallback_reason: str | None = None
    pool_outcome: PoolOutcome = PoolOutcome.NO_CANDIDATE
    lease_id: str | None = None
    generation: int | None = None
    extranonce2: str | None = None
    nonce_start: int | None = None
    recorded_at: float = field(default_factory=time.monotonic)
    plan_digest: str | None = None
    resident_execution_digest: str | None = None
    geometry_digest: str | None = None
    # --- execution provenance (router) -------------------------------------
    # ``device_used`` above is retained for API compatibility. The router
    # populates BOTH: ``requested_route`` is what the plan asked for and
    # ``executed_route`` is what physically ran. They differ on fallback, and
    # conflating them is the failure this field pair exists to prevent.
    requested_route: str | None = None
    executed_route: str | None = None
    completion_state: CompletionState = CompletionState.COMPLETE
    evidence_class: EvidenceClass = EvidenceClass.SOFTWARE_VERIFIED
    device_backend: str | None = None
    device_name: str | None = None
    device_vendor: str | None = None
    kernel_identity: str | None = None
    kernel_build_status: str | None = None
    kernel_launch_count: int = 0
    requested_work_items: int = 0
    completed_work_items: int = 0
    requested_nonce_order: str | None = None
    executed_nonce_order: str | None = None
    planned_lane_order: tuple[int, ...] = ()
    planned_window_start: int | None = None
    chunk_count: int = 0
    power_w: float | None = None
    # Verbatim cause of a DEVICE_ERROR (the device's exception text, or
    # DEVICE_RESULT_MISMATCH when its claimed winner failed the host rehash).
    device_error: str | None = None
    # --- correlation spine: session → generation → plan → lease → execution
    # → candidate → submission (persisted in MiningSession.pending/share_log).
    toe_frame_id: str | None = None
    execution_id: str | None = None
    candidate_id: str | None = None
    submission_id: str | None = None
    learning_record_id: str | None = None
    search_plan_id: str | None = None
    job_id: str | None = None
    candidate_nonce: int | None = None
    candidate_host_verified: bool | None = None
    recovery_id: str | None = None
    toe_advice_reason: str | None = None

    def __post_init__(self) -> None:
        source = PlanSource(self.plan_source)
        object.__setattr__(self, "plan_source", source)
        object.__setattr__(self, "pool_outcome", PoolOutcome(self.pool_outcome))
        object.__setattr__(self, "completion_state", CompletionState(self.completion_state))
        object.__setattr__(self, "evidence_class", EvidenceClass(self.evidence_class))
        if not self.job_fingerprint or not self.policy_id:
            raise ValueError("job_fingerprint and policy_id are required")
        # --- provenance invariants -----------------------------------------
        # The constitutional rules, made mechanical. A record that cannot
        # satisfy them is refused at construction, so no consumer can ever be
        # handed a record claiming work it did not do.
        if self.requested_route is not None and self.requested_route not in VALID_ROUTES:
            raise ValueError(f"unsupported requested_route: {self.requested_route!r}")
        if self.executed_route is not None and self.executed_route not in VALID_ROUTES:
            raise ValueError(f"unsupported executed_route: {self.executed_route!r}")
        if self.kernel_launch_count < 0:
            raise ValueError("kernel_launch_count cannot be negative")
        if self.requested_work_items < 0 or self.completed_work_items < 0:
            raise ValueError("work item counts cannot be negative")
        if self.completed_work_items > self.requested_work_items:
            raise ValueError(
                "completed_work_items cannot exceed requested_work_items: "
                "execution may not invent work outside the plan"
            )
        # Requested route == executed route iff no fallback occurred.
        fell_back = self.requested_route != self.executed_route
        if fell_back and self.executed_route is not None and not self.fallback_reason:
            raise ValueError(
                "executed_route differs from requested_route, so a "
                "fallback_reason is required: no silent fallback"
            )
        if not fell_back and self.fallback_reason:
            raise ValueError(
                "fallback_reason is set but the executed route matches the " "requested route"
            )
        # A completed window must have consumed the work it was asked for.
        if self.completion_state is CompletionState.COMPLETE:
            if self.requested_work_items and self.completed_work_items != self.requested_work_items:
                raise ValueError("COMPLETE requires completed_work_items == requested_work_items")
        if self.completion_state is CompletionState.REFUSED and self.executed_route:
            raise ValueError("REFUSED must not report an executed route")
        if self.device_error is not None and (
            self.completion_state is not CompletionState.DEVICE_ERROR
        ):
            raise ValueError("device_error is only recorded on a DEVICE_ERROR execution")
        # POOL_CONFIRMED is only reachable from a literal ACCEPTED outcome.
        if self.evidence_class is EvidenceClass.POOL_CONFIRMED and (
            self.pool_outcome is not PoolOutcome.ACCEPTED
        ):
            raise ValueError("POOL_CONFIRMED requires a literal ACCEPTED outcome")
        # HARDWARE_EXECUTED requires measured device work, not availability.
        if self.evidence_class is EvidenceClass.HARDWARE_EXECUTED:
            backend = str(self.device_backend or "")
            substrate = backend.split(":", 1)[0]
            # Every admitted backend below is a physical execution surface.
            # Presence is never sufficient: the launch-count and completed-work
            # gates immediately below remain mandatory for promotion.
            if not (
                backend.startswith("opencl")
                or backend == "remote_opencl"
                or substrate in ("cuda", "metal", "asic", "super_asic")
            ):
                raise ValueError("HARDWARE_EXECUTED requires a measured physical device backend")
            if self.kernel_launch_count <= 0:
                raise ValueError("HARDWARE_EXECUTED requires at least one measured kernel launch")
            if self.completed_work_items <= 0:
                raise ValueError("HARDWARE_EXECUTED requires completed work")
        if source is PlanSource.AGENTIC_PRECOMPUTED:
            if not self.plan_id or self.plan_fallback_reason is not None:
                raise ValueError("agentic execution requires plan_id and no plan_fallback_reason")
        elif self.plan_id is not None or not self.plan_fallback_reason:
            raise ValueError("baseline execution requires plan_fallback_reason and no plan_id")
        if self.planned_window <= 0 or self.actual_window < 0:
            raise ValueError("window counts must be positive/non-negative")
        if self.hash_count < 0:
            raise ValueError("hash_count cannot be negative")
        if self.elapsed_seconds < 0 or self.kernel_ms < 0:
            raise ValueError("timing values cannot be negative")
        if self.pool_accepted < 0 or self.pool_rejected < 0 or self.pool_stale < 0:
            raise ValueError("pool counters cannot be negative")
        if self.pool_accepted and self.pool_outcome is not PoolOutcome.ACCEPTED:
            raise ValueError("pool_accepted requires a literal ACCEPTED outcome")
        if self.pool_rejected and self.pool_outcome is not PoolOutcome.REJECTED:
            raise ValueError("pool_rejected requires a literal REJECTED outcome")
        if self.pool_stale and self.pool_outcome is not PoolOutcome.STALE:
            raise ValueError("pool_stale requires a literal STALE outcome")
        if self.pool_outcome is PoolOutcome.STALE and not self.pool_stale:
            raise ValueError("STALE requires a literal stale-work counter")
        if self.candidate_nonce is not None and not 0 <= self.candidate_nonce <= 0xFFFFFFFF:
            raise ValueError("candidate_nonce must be a uint32")
        if self.candidate_host_verified and (
            self.candidate_nonce is None or self.locally_valid_shares <= 0
        ):
            raise ValueError("host-verified candidates require a nonce and a local proof result")
        if len(self.lane_order) != _LANES or sorted(self.lane_order) != list(range(_LANES)):
            raise ValueError("lane_order must contain every M32 lane exactly once")
        if not (0 <= self.preferred_face < _LANES):
            raise ValueError("preferred_face must be in [0, 31]")

    @property
    def truth_class(self) -> str:
        """Evidence tier using explicit software/hardware/pool verification names."""
        return {
            EvidenceClass.SOFTWARE_VERIFIED: "SOFTWARE_EXECUTION_VERIFIED",
            EvidenceClass.DEVICE_AVAILABLE: "DEVICE_AVAILABLE",
            EvidenceClass.HARDWARE_EXECUTED: "HARDWARE_EXECUTION_VERIFIED",
            EvidenceClass.POOL_CONFIRMED: "POOL_VERIFIED",
        }[self.evidence_class]
