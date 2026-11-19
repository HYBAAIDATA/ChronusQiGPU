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
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping


class _EvidenceSnapshot(Mapping):
    """Own a deep snapshot and return detached values to consumers."""

    def __init__(self, values):
        self._values = {k: self._copy(v) for k, v in values.items()}

    @classmethod
    def _copy(cls, value):
        from chronus.execution.resident_hendrix import ImmutableJSONMapping

        if isinstance(value, ImmutableJSONMapping):
            return value
        if isinstance(value, Mapping):
            return _EvidenceSnapshot(value)
        if isinstance(value, list):
            return [cls._copy(v) for v in value]
        if isinstance(value, tuple):
            return tuple(cls._copy(v) for v in value)
        return deepcopy(value)

    def __getitem__(self, key):
        return self._copy(self._values[key])

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)


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
        # ResidentExecutionRouter's internal composite marker: Hendrix over the
        # complete structured itinerary on the PYTHIA lattice route.
        "pythia_hendrix_structured_composed",
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
        state = LeaseState(state)
        allowed = {
            LeaseState.RESERVED: {LeaseState.EXECUTING, LeaseState.INVALIDATED},
            LeaseState.EXECUTING: {LeaseState.COMPLETE, LeaseState.INVALIDATED},
            LeaseState.COMPLETE: set(),
            LeaseState.INVALIDATED: set(),
        }
        if state not in allowed[self.state]:
            raise ValueError(f"invalid lease transition: {self.state} -> {state}")
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
        object.__setattr__(self, "executor_route", ExecutionRoute(self.executor_route))
        if self.source is PlanSource.BASELINE_FALLBACK and not self.plan_fallback_reason:
            raise ValueError("a baseline plan must say why no agentic plan ran")
        if self.source is PlanSource.AGENTIC_PRECOMPUTED and self.plan_fallback_reason:
            raise ValueError("an agentic plan cannot carry a plan_fallback_reason")
        refs = dict(self.evidence_refs)
        if "resident_hendrix" in refs:
            from chronus.execution.resident_hendrix import ImmutableJSONMapping, canonical
            refs["resident_hendrix"] = ImmutableJSONMapping(canonical(refs["resident_hendrix"]))
        if self.toe_frame_id is not None:
            if not self.toe_frame_id:
                raise ValueError("toe_frame_id cannot be empty")
            if refs.get("toe_frame_digest") != self.toe_frame_id:
                raise ValueError("toe_frame_id must match evidence_refs.toe_frame_digest")
        object.__setattr__(self, "evidence_refs", _EvidenceSnapshot(refs))

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
