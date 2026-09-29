"""Agentic mining controller: Intelligence leads, executor follows.

  STRATUM (sole identity authority)      INTELLIGENCE                EXECUTOR
  StratumJobGeneration ─► bind_work() ─► lease + SearchPlan ─► consume ─► begin_execution
                                         (lookahead-bounded)            ExecutionRecord
                                                                        record_outcome()

* Work identity (pool session, Stratum generation, Stratum fingerprint) is
  supplied by the coordinator from ``StratumRuntimeState``. This module never
  fingerprints a job itself and never decides two jobs are equivalent.
* Every queued plan owns a RESERVED nonce lease; a rebind, ``clean_jobs``
  job, target change or reconnect drains the queue and invalidates leases.
* Salamander: ``set_recovery_active(True)`` drains speculative plans and
  closes admission; clearing it requires the live identity to be
  re-bound before any new plan is admitted.
* Authority: WHEN / WHERE / HOW MUCH / WHICH LANE / WHICH ORDER only.
  SHA256d, targets, shares and pool outcomes stay outside this module.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import pathlib
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from queue import Empty, Full, Queue
from typing import Any, Callable, Deque

from .nonce_lease import LeaseConflict, LeaseRecord, NonceLeaseLedger
from .scale_state import ScaleEvidence, ScaleState, ScaleStateClassifier
from .quality import QualityLedger
from .search_plan import ExecutionRecord, LeaseState, PoolOutcome, SearchPlan, WorkIdentity

LOG = logging.getLogger("mla1517.mining.agentic")

_DEFAULT_QUEUE_DEPTH = 3
_MAX_QUEUE_DEPTH = 8
_DEFAULT_LOOKAHEAD = 2
_LEAD_HISTORY_WINDOW = 20
_ADAPT_WINDOW = 32
_ADAPT_MIN_EVENTS = 4
_HIGH_WASTE = 0.5
_LOW_WASTE = 0.2
_STARVATION_EVENTS = 2

STATE_SCHEMA_VERSION = 2
MAX_STATE_BYTES = 64 * 1024
_MAX_POLICIES = 32
_MAX_POLICY_ID = 64


@dataclass
class AgenticTelemetry:
    """Live evidence-backed telemetry; every field is set from a measured event."""

    agentic_state: str = "IDLE"
    current_policy: str = ""
    current_search_plan: str | None = None
    next_plan_ready: bool = False
    plans_created: int = 0
    plans_consumed: int = 0
    plans_invalidated: int = 0
    plans_stale: int = 0
    clean_job_invalidations: int = 0
    planned_window: int = 0
    executed_window: int = 0
    lane_order: tuple[int, ...] = ()
    preferred_face: int = 0
    dispatch_breadth: int = 320
    device_route: str = "cpu_reference"
    last_plan_source: str | None = None
    last_fallback_reason: str | None = None
    last_consume_miss_reason: str | None = None
    last_outcome: dict[str, Any] | None = None
    learning_update_applied: bool = False
    executor_idle_waiting_for_plan_ms: float = 0.0
    scale_state: str = "UNCERTAIN"
    lookahead_change_reason: str | None = None
    fallback_counts: Counter = field(default_factory=Counter)


class AgenticMiningController:
    """Owns the SearchPlan queue, nonce leases and bounded lookahead.

    Thread safety: identity/recovery flags are guarded by ``_lock``; the
    Queue is thread-safe. The coordinator drives everything from one loop.
    """

    def __init__(
        self,
        *,
        queue_depth: int = _DEFAULT_QUEUE_DEPTH,
        initial_lookahead: int = _DEFAULT_LOOKAHEAD,
        scale_classifier: ScaleStateClassifier | None = None,
    ) -> None:
        if not (1 <= queue_depth <= _MAX_QUEUE_DEPTH):
            raise ValueError(f"queue_depth must be 1..{_MAX_QUEUE_DEPTH}")
        self._capacity = queue_depth
        self._queue: Queue[SearchPlan] = Queue(maxsize=queue_depth)
        self._lookahead = max(1, min(initial_lookahead, queue_depth))
        self._policy_depth = False
        self._leases = NonceLeaseLedger(max_active=queue_depth + 2)
        self._scale_classifier = scale_classifier or ScaleStateClassifier()
        self._lock = threading.Lock()
        self._identity: WorkIdentity | None = None
        self._unavailable_reason: str | None = "NO_WORK_IDENTITY"
        self._recovery_active = False
        self._revalidation_required = False
        self._binding_epoch = 0
        self._historical_epoch = 0
        self._recent: Deque[str] = deque(maxlen=_ADAPT_WINDOW)
        self.telemetry = AgenticTelemetry()
        self._outcome_history: Deque[ExecutionRecord] = deque(maxlen=256)
        self._lead_history: dict[str, deque] = {}
        self.quality = QualityLedger()

    # ------------------------------------------------------------------ #
    # Stratum work identity
    # ------------------------------------------------------------------ #

    def bind_work(self, identity: WorkIdentity) -> bool:
        """Bind to the live Stratum identity. Returns True when it changed.

        Re-binding the same identity is how the coordinator re-validates
        work after recovery; it never invalidates anything.
        """
        with self._lock:
            self._revalidation_required = False
            self._unavailable_reason = None
            if self._identity is not None and self._identity.key == identity.key:
                self._identity = identity
                return False
            self._identity = identity
            self._binding_epoch += 1
        drained = self._drain_queue()
        self._leases.bind(
            identity.key,
            identity.generation,
            work_space=identity.work_space or identity.job_fingerprint,
        )
        self.telemetry.plans_invalidated += drained
        self._recent.extend(["invalidated"] * drained)
        if identity.clean_jobs:
            self.telemetry.clean_job_invalidations += 1
        self.telemetry.agentic_state = "NEW_JOB"
        self.telemetry.next_plan_ready = False
        self._adapt()
        LOG.info(
            "bound Stratum generation=%d session=%s fingerprint=%s clean=%s invalidated=%d",
            identity.generation,
            identity.pool_session_id[:8],
            identity.job_fingerprint[:12],
            identity.clean_jobs,
            drained,
        )
        return True

    def clear_work(self, reason: str) -> None:
        """No trustworthy Stratum identity exists; nothing may be planned."""
        with self._lock:
            had_identity = self._identity is not None
            self._identity = None
            self._unavailable_reason = reason
        if had_identity:
            drained = self._drain_queue()
            self._leases.unbind()
            self.telemetry.plans_invalidated += drained
            self._recent.extend(["invalidated"] * drained)
            self.telemetry.agentic_state = "NO_WORK"
            LOG.info("work identity cleared (%s); invalidated=%d", reason, drained)

    def current_identity(self) -> WorkIdentity | None:
        with self._lock:
            return self._identity

    def _drain_queue(self) -> int:
        drained = 0
        while True:
            try:
                plan = self._queue.get_nowait()
            except Empty:
                return drained
            self._leases.invalidate(plan.plan_id)
            drained += 1

    # ------------------------------------------------------------------ #
    # Salamander gate
    # ------------------------------------------------------------------ #

    def set_recovery_active(self, active: bool) -> None:
        """Recovery drains speculation; clearing it demands identity revalidation."""
        with self._lock:
            if self._recovery_active == active:
                return
            self._recovery_active = active
            if not active:
                self._revalidation_required = True
        if active:
            drained = self._drain_queue()
            self._leases.invalidate_reserved()
            self.telemetry.plans_invalidated += drained
            self.telemetry.next_plan_ready = False
            self.telemetry.agentic_state = "RECOVERY"
            LOG.warning("recovery active: admission closed, %d speculative plans dropped", drained)
        else:
            self.telemetry.agentic_state = "RESUMING"
            LOG.info("recovery cleared: awaiting fresh Stratum identity revalidation")

    def is_recovery_active(self) -> bool:
        with self._lock:
            return self._recovery_active

    def admission_block_reason(self) -> str | None:
        with self._lock:
            if self._identity is None:
                return self._unavailable_reason or "NO_WORK_IDENTITY"
            if self._recovery_active:
                return "RECOVERY"
            if self._revalidation_required:
                return "REVALIDATION_REQUIRED"
        return None

    # ------------------------------------------------------------------ #
    # Lookahead and plan admission
    # ------------------------------------------------------------------ #

    @property
    def lookahead(self) -> int:
        return self._lookahead

    @property
    def capacity(self) -> int:
        return self._capacity

    def set_lookahead(self, depth: int | None, reason: str = "") -> None:
        """Precompute depth from the operating policy's world model.

        While set, the policy is the single authority over the depth and the
        reactive waste/starvation adaptation stands down; ``None`` hands the
        depth back to it.
        """
        if depth is None:
            self._policy_depth = False
            return
        depth = max(1, min(int(depth), self._capacity))
        self._policy_depth = True
        if depth != self._lookahead:
            self._lookahead = depth
            self.telemetry.lookahead_change_reason = f"policy: {reason}" if reason else "policy"

    def plans_needed(self) -> int:
        if self.admission_block_reason() is not None:
            return 0
        return max(0, self._lookahead - self._queue.qsize())

    def reserve_lease(
        self, plan_id: str, window: int, allocate_extranonce2: Callable[[], str]
    ) -> LeaseRecord:
        if self.admission_block_reason() is not None:
            raise LeaseConflict(f"admission closed: {self.admission_block_reason()}")
        return self._leases.allocate(plan_id, window, allocate_extranonce2)

    def release_lease(self, lease_id: str) -> None:
        self._leases.invalidate(lease_id)

    def submit_plan(self, plan: SearchPlan) -> bool:
        """Queue a plan that owns a matching RESERVED lease for the live identity."""
        identity = self.current_identity()
        blocked = self.admission_block_reason()
        lease = self._leases.get(plan.plan_id)
        if not plan.is_valid_for(identity):
            self.telemetry.plans_stale += 1
            self._leases.invalidate(plan.plan_id)
            return False
        if (
            blocked is not None
            or lease is None
            or lease.state is not LeaseState.RESERVED
            or lease.identity_key != identity.key
            or lease.extranonce2 != plan.extranonce2
            or lease.start != plan.base_step
            or lease.count < plan.window
        ):
            self._leases.invalidate(plan.plan_id)
            return False
        try:
            self._queue.put_nowait(plan)
        except Full:
            self._leases.invalidate(plan.plan_id)
            return False
        self.telemetry.plans_created += 1
        self.telemetry.next_plan_ready = True
        self.telemetry.current_search_plan = plan.plan_id
        return True

    def consume_plan(self, *, timeout_ms: float = 0.0) -> SearchPlan | None:
        """Pull the next valid plan; ``telemetry.last_consume_miss_reason`` says why not."""
        idle_start = time.monotonic()
        try:
            plan = self._queue.get(timeout=max(0.0, timeout_ms) / 1000.0)
        except Empty:
            self.telemetry.executor_idle_waiting_for_plan_ms += (
                time.monotonic() - idle_start
            ) * 1000.0
            self.telemetry.next_plan_ready = False
            blocked = self.admission_block_reason()
            self.telemetry.last_consume_miss_reason = (
                "recovery"
                if blocked == "RECOVERY"
                else "queue_empty" if blocked is None else "precompute_unavailable"
            )
            return None
        self.telemetry.executor_idle_waiting_for_plan_ms += (time.monotonic() - idle_start) * 1000.0
        if not plan.is_valid_for(self.current_identity()):
            self.telemetry.plans_stale += 1
            self._recent.append("invalidated")
            self._leases.invalidate(plan.plan_id)
            self.telemetry.last_consume_miss_reason = "stale_plan"
            self._adapt()
            return None
        self.telemetry.last_consume_miss_reason = None
        self.telemetry.plans_consumed += 1
        self._recent.append("consumed")
        self.telemetry.next_plan_ready = self._queue.qsize() > 0
        self.telemetry.current_policy = plan.policy_id
        self.telemetry.planned_window = plan.window
        self.telemetry.lane_order = plan.lane_order
        self.telemetry.preferred_face = plan.preferred_face
        self.telemetry.dispatch_breadth = plan.dispatch_breadth
        self.telemetry.device_route = plan.executor_route
        self._adapt()
        return plan

    def queue_depth(self) -> int:
        return self._queue.qsize()

    # ------------------------------------------------------------------ #
    # Execution handoff (leases)
    # ------------------------------------------------------------------ #

    def begin_execution(self, plan: SearchPlan) -> LeaseRecord:
        identity = self.current_identity()
        if not plan.is_valid_for(identity):
            self._leases.invalidate(plan.plan_id)
            raise LeaseConflict("plan no longer matches the live Stratum identity")
        return self._leases.begin(plan.plan_id, identity.key)

    def begin_fallback(self, window: int, allocate_extranonce2: Callable[[], str]) -> LeaseRecord:
        """Baseline work is leased too, so it can never duplicate agentic coverage."""
        lease = self.reserve_fallback(window, allocate_extranonce2)
        return self.begin_reserved(lease.lease_id)

    def reserve_fallback(self, window: int, allocate_extranonce2: Callable[[], str]) -> LeaseRecord:
        if self.current_identity() is None:
            raise LeaseConflict("no Stratum work identity is bound")
        return self._leases.allocate(
            NonceLeaseLedger.new_fallback_id(), window, allocate_extranonce2
        )

    def begin_reserved(self, lease_id: str) -> LeaseRecord:
        identity = self.current_identity()
        if identity is None:
            self._leases.invalidate(lease_id)
            raise LeaseConflict("no Stratum work identity is bound")
        return self._leases.begin(lease_id, identity.key)

    def lease(self, lease_id: str) -> LeaseRecord | None:
        return self._leases.get(lease_id)

    def finish_execution(self, lease_id: str, *, scanned: bool) -> bool:
        if scanned:
            return self._leases.complete(lease_id)
        return self._leases.invalidate(lease_id)

    def note_fallback(self, reason: str) -> None:
        self.telemetry.fallback_counts[reason] += 1
        self.telemetry.last_fallback_reason = reason
        if reason == "queue_empty":
            self._recent.append("starved")
            self._adapt()

    # ------------------------------------------------------------------ #
    # Adaptive lookahead
    # ------------------------------------------------------------------ #

    @property
    def precompute_waste_ratio(self) -> float | None:
        created = self.telemetry.plans_created
        if created == 0:
            return None
        return (self.telemetry.plans_invalidated + self.telemetry.plans_stale) / created

    def _adapt(self) -> None:
        if self._policy_depth:
            return
        consumed = self._recent.count("consumed")
        invalidated = self._recent.count("invalidated")
        starved = self._recent.count("starved")
        if consumed + invalidated < _ADAPT_MIN_EVENTS and starved < _STARVATION_EVENTS:
            return
        waste = invalidated / max(1, consumed + invalidated)
        if waste > _HIGH_WASTE and self._lookahead > 1:
            self._lookahead -= 1
            self.telemetry.lookahead_change_reason = f"shrink: windowed waste {waste:.2f}"
            self._recent.clear()
        elif starved >= _STARVATION_EVENTS and waste < _LOW_WASTE:
            if self._lookahead < self._capacity:
                self._lookahead += 1
                self.telemetry.lookahead_change_reason = (
                    f"grow: {starved} starved executions, waste {waste:.2f}"
                )
            self._recent.clear()

    # ------------------------------------------------------------------ #
    # Outcome recording and learning
    # ------------------------------------------------------------------ #

    def record_outcome(self, record: ExecutionRecord) -> None:
        """Only literal ACCEPTED/REJECTED pool responses train policy history."""
        self._outcome_history.append(record)
        self.quality.observe(record)
        self.telemetry.learning_update_applied = False
        self.telemetry.last_plan_source = record.plan_source.value
        self.telemetry.last_outcome = {
            "plan_id": record.plan_id,
            "plan_source": record.plan_source.value,
            "plan_fallback_reason": record.plan_fallback_reason,
            "pool_outcome": record.pool_outcome.value,
            "pool_accepted": record.pool_accepted,
            "pool_rejected": record.pool_rejected,
            "hash_count": record.hash_count,
            "elapsed_seconds": record.elapsed_seconds,
            "generation": record.generation,
            "nonce_start": record.nonce_start,
            "recovery_event": record.recovery_event,
        }
        self.telemetry.executed_window = record.actual_window
        if record.pool_outcome in (PoolOutcome.ACCEPTED, PoolOutcome.REJECTED):
            hist = self._lead_history.setdefault(
                record.policy_id, deque(maxlen=_LEAD_HISTORY_WINDOW)
            )
            hist.append(record.pool_outcome is PoolOutcome.ACCEPTED)
            self.telemetry.learning_update_applied = True

    def accept_rates(self) -> dict[str, float | None]:
        return {
            policy: (sum(hist) / len(hist)) if len(hist) >= 3 else None
            for policy, hist in self._lead_history.items()
        }

    # ------------------------------------------------------------------ #
    # Scale-state classification
    # ------------------------------------------------------------------ #

    def classify_scale(
        self,
        *,
        kernel_latency_ms: float,
        latency_bound_ms: float,
        temperature_c: float,
        thermal_limit_c: float,
        device_errors: int = 0,
        prior_throughput: float | None = None,
        current_throughput: float | None = None,
    ) -> ScaleState:
        evidence = ScaleEvidence(
            kernel_latency_ms=kernel_latency_ms,
            latency_bound_ms=latency_bound_ms,
            temperature_c=temperature_c,
            thermal_limit_c=thermal_limit_c,
            queue_depth=self._queue.qsize(),
            executor_idle_ms=self.telemetry.executor_idle_waiting_for_plan_ms,
            recovery_active=self.is_recovery_active(),
            device_errors=device_errors,
            prior_throughput=prior_throughput,
            current_throughput=current_throughput,
        )
        classification = self._scale_classifier.classify(evidence)
        self.telemetry.scale_state = classification.state.value
        return classification.state

    # ------------------------------------------------------------------ #
    # Telemetry snapshot
    # ------------------------------------------------------------------ #

    def snapshot(self) -> dict[str, Any]:
        """Unknown values stay None — they are never fabricated."""
        t = self.telemetry
        identity = self.current_identity()
        waste = self.precompute_waste_ratio
        return {
            "agentic_state": t.agentic_state,
            "admission_block_reason": self.admission_block_reason(),
            "work_identity": (
                None
                if identity is None
                else {
                    "pool_session_id": identity.pool_session_id,
                    "generation": identity.generation,
                    "job_id": identity.job_id,
                    "job_fingerprint": identity.job_fingerprint,
                    "target_generation": identity.target_generation,
                    "clean_jobs": identity.clean_jobs,
                }
            ),
            "binding_epoch": self._binding_epoch,
            "historical_binding_epoch": self._historical_epoch,
            "current_policy": t.current_policy,
            "current_search_plan": t.current_search_plan,
            "next_plan_ready": t.next_plan_ready,
            "precompute_queue_depth": self._queue.qsize(),
            "lookahead": self._lookahead,
            "lookahead_max": self._capacity,
            "lookahead_change_reason": t.lookahead_change_reason,
            "precompute_waste_ratio": None if waste is None else round(waste, 4),
            "plans_created": t.plans_created,
            "plans_consumed": t.plans_consumed,
            "plans_invalidated": t.plans_invalidated,
            "plans_stale": t.plans_stale,
            "clean_job_invalidations": t.clean_job_invalidations,
            "planned_window": t.planned_window,
            "executed_window": t.executed_window,
            "lane_order": list(t.lane_order) if t.lane_order else None,
            "preferred_face": t.preferred_face,
            "dispatch_breadth": t.dispatch_breadth,
            "device_route": t.device_route,
            "last_plan_source": t.last_plan_source,
            "last_fallback_reason": t.last_fallback_reason,
            "last_consume_miss_reason": t.last_consume_miss_reason,
            "fallback_counts": dict(t.fallback_counts),
            "leases": self._leases.snapshot(),
            "last_outcome": t.last_outcome,
            "learning_update_applied": t.learning_update_applied,
            "executor_idle_waiting_for_plan_ms": t.executor_idle_waiting_for_plan_ms,
            "scale_state": t.scale_state,
            "quality": self.quality.snapshot(),
        }

    # ------------------------------------------------------------------ #
    # Policy persistence
    # ------------------------------------------------------------------ #
    # Only historical learning is persisted. Work identity, plans, leases,
    # targets and Stratum sessions are never written, so a restart cannot
    # resurrect actionable work: nothing is admissible until bind_work().

    def save_state(self, path: str | pathlib.Path) -> bool:
        try:
            body = {
                "historical_epoch": max(self._historical_epoch, self._binding_epoch),
                "lead_history": {p: list(h) for p, h in self._lead_history.items()},
            }
            canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
            payload = json.dumps(
                {
                    "schema_version": STATE_SCHEMA_VERSION,
                    "body": body,
                    "sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
                },
                sort_keys=True,
            ).encode("utf-8")
            if len(payload) > MAX_STATE_BYTES:
                raise ValueError("policy state exceeds the size bound")
            target = pathlib.Path(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_name(target.name + ".tmp")
            with tmp.open("wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, target)
            if os.name != "nt":
                fd = os.open(target.parent, os.O_RDONLY)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            return True
        except Exception as exc:
            LOG.warning("failed to save policy state: %s", exc)
            return False

    def load_state(self, path: str | pathlib.Path) -> bool:
        """Restore historical learning only; any defect yields a clean baseline."""
        try:
            target = pathlib.Path(path)
            if not target.exists():
                return False
            if target.stat().st_size > MAX_STATE_BYTES:
                raise ValueError("policy state exceeds the size bound")
            envelope = json.loads(target.read_bytes().decode("utf-8"))
            if not isinstance(envelope, dict) or set(envelope) != {
                "schema_version",
                "body",
                "sha256",
            }:
                raise ValueError("unexpected policy state envelope")
            if envelope["schema_version"] != STATE_SCHEMA_VERSION:
                raise ValueError(f"unsupported schema_version {envelope['schema_version']!r}")
            body = envelope["body"]
            if not isinstance(body, dict) or set(body) != {"historical_epoch", "lead_history"}:
                raise ValueError("unexpected policy state body")
            canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
            if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != envelope["sha256"]:
                raise ValueError("policy state integrity check failed")
            epoch = body["historical_epoch"]
            if type(epoch) is not int or epoch < 0:
                raise ValueError("historical_epoch must be a non-negative integer")
            raw_history = body["lead_history"]
            if not isinstance(raw_history, dict) or len(raw_history) > _MAX_POLICIES:
                raise ValueError("lead_history must be a bounded object")
            history: dict[str, deque] = {}
            for policy, entries in raw_history.items():
                if not policy or len(policy) > _MAX_POLICY_ID:
                    raise ValueError("invalid policy id")
                if not isinstance(entries, list) or not all(type(v) is bool for v in entries):
                    raise ValueError("lead history entries must be boolean lists")
                history[policy] = deque(
                    entries[-_LEAD_HISTORY_WINDOW:], maxlen=_LEAD_HISTORY_WINDOW
                )
        except Exception as exc:
            LOG.warning("policy state rejected; starting from a clean baseline: %s", exc)
            self._lead_history = {}
            self._historical_epoch = 0
            return False
        self._lead_history = history
        self._historical_epoch = epoch
        LOG.info("policy history restored (%d policies); no work is restored", len(history))
        return True
