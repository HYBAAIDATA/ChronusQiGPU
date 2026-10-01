"""Measured-intelligence adapter for the real MLA1517 Stratum coordinator.

This adapter composes the canonical MMIO/vault/network implementation with the
Turing ordering substrate, TOE tensor context, mining chooser, and the
self-healing recovery plane. It does not create a second network path and it
never turns a lane label into a pool share. Only a real pool response is fed
back into the chooser.

TOE posture — SOFT GATE, DECLARED. If the TOE adapter cannot start (missing
``toe`` package or its optional dependencies) the coordinator logs the
absence and continues with ``self.toe is None``. Without TOE, no causal
signal is produced, so the solver sweep and dispatch breadth keep their
measured defaults — TOE output can steer, never validate. Only operations
enumerated in ``PERMITTED_WITHOUT_TOE`` may proceed without TOE evidence;
anything else raises ``TOEUnavailable``. This posture is locked by
``tests/test_coordinator_toe_posture.py``.
"""

from __future__ import annotations

import contextlib
import asyncio
import hashlib
import json
import logging
import math
import os
import struct
import time
import uuid
from collections import deque
from dataclasses import asdict, replace
from queue import Empty
from typing import Any, Mapping

from chronus.mla1517.hardware import MMIOBridge, VaultRecord
from manifold_pool_coordinator import (
    CURRENT_HOT_STATE_FORMAT,
    ManifoldPoolCoordinator,
    StratumAuthorizationError,
    parse_endpoint,
)

from .chooser import MiningIntelligenceChooser
from .session import MiningSession
from .pow import compact_target
from .geometry import LANES
from .intelligence_controller import ControlCommand, ControlSignal, IntelligenceController
from .self_healing_agent import (
    NonBlockingRecoveryQueue,
    RecoveryBackpressure,
    RecoveryCommand,
    RecoveryPlan,
    SelfHealingAgent,
)
from .agentic_controller import AgenticMiningController
from .causal import CausalCoordinate, CausalLedger
from .dispatch_algebra import certify_dispatch
from .execution_router import NONCE_ORDER_HENDRIX, NONCE_ORDER_M32, ExecutionRouter
from .hendrix_order import NonceOrderUnavailable, hendrix_schedule, load_hendrix
from .recovery_authority import RecoveryGovernor, RecoveryRecord
from .nonce_lease import LeaseConflict, LeaseExhausted, LeaseRecord
from .search_plan import (
    CompletionState,
    ExecutionRecord,
    PlanSource,
    PoolOutcome,
    SearchPlan,
    WorkIdentity,
)
from .solver import M32SearchSolver
from .stratum_adapter import StratumAdapterError
from .tuning_gate import TuningGate
from .intelligence_memory import IntelligenceMemory
from ..knowledge import KnowledgeFabric, default_journal_path
from ..learning import LearningLedger, ResidualScale
from .hashrate_governor import HashrateGovernor
from .loss_ledger import LossLedger
from .promotion import ShadowTrial, applicable
from .recovery_effect import RecoveryEffects
from .operating_policy import OperatingPolicy, PolicyContext
from .policy_audit import PolicyAuditor
from .world_model import MiningWorldModel
from .toe_adapter import TOEUnavailable, TOEMiningAdapter
from .toe_context import TOEContextBuilder, TOEContextUnavailable
from .toe_signal import (
    TOECausalSignal,
    TOEConsensusBoundaryError,
    build_toe_signal,
    lucas_ladder_status,
)
from .toe_decision import (
    TOEDecisionFrameUnavailable,
    TOEMiningDecisionFrame,
    build_toe_decision_frame,
)

LOG = logging.getLogger("chronus.mla1517.stratum.intelligence")

# Bounded observed window the solver materialises per job so the chooser
# sees the real declared ordering, never an invented distribution.
_OBSERVED_WINDOW = 10 * LANES

# Operations allowed to proceed when the TOE adapter is absent. Both are
# proof-free by construction: ``observe_record`` is advisory orchestration
# (context, control, chooser) and ``submit_candidate`` is validated solely
# by the Stratum proof adapter's SHA256d check — neither fabricates TOE
# evidence. Any operation outside this set must raise TOEUnavailable.
PERMITTED_WITHOUT_TOE = frozenset({"observe_record", "submit_candidate"})

# Precompute wakes on Stratum changes, consumption and recovery edges; this
# is only the idle heartbeat, not a polling rate.
_PRECOMPUTE_IDLE_S = 0.25
# Measured hashrate is hashes completed over this trailing wall-clock span.
_HASHRATE_SPAN_S = 30.0
_METRICS_MIN_INTERVAL_S = 1.0
_BASELINE_POLICY = "baseline_fallback"
_EVIDENCE_MIN_INTERVAL_S = 0.5
_NONCE_ORDERS = {"m32": NONCE_ORDER_M32, "hendrix": NONCE_ORDER_HENDRIX}


def _positive_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def resolve_nonce_order(value: str) -> str:
    """The configured nonce order; an unknown or unloadable one fails startup.

    Hendrix is the default: the structured search is part of the miner, and
    both the CPU reference and the OpenCL device (bitcoin_sha256d_hendrix)
    execute it. ``m32`` keeps the Turing lane order.
    """
    key = (value or "hendrix").strip().lower()
    if key not in _NONCE_ORDERS:
        raise ValueError(
            f"PYTHIA_NONCE_ORDER must be one of {sorted(_NONCE_ORDERS)}, got {value!r}"
        )
    if key == "hendrix":
        search_cls, error = load_hendrix()
        if search_cls is None:
            raise NonceOrderUnavailable(f"PYTHIA_NONCE_ORDER=hendrix: {error}")
    return _NONCE_ORDERS[key]


def _header_work_space(generation: Any) -> str:
    """Hash of the Stratum fields that fix the header bytes for a given nonce."""
    fields = [
        generation.prevhash,
        generation.coinb1,
        generation.coinb2,
        list(generation.merkle_branch),
        generation.version,
        generation.nbits,
        generation.ntime,
        generation.extranonce1,
        generation.extranonce2_size,
    ]
    encoded = json.dumps(fields, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class CpuReferenceHasher:
    """Hasher stand-in for the router when no OpenCL device is bound.

    It exposes only what the router reads; every chunk runs through the
    router's CPU executor (the M32 solver), never through this object.
    """

    backend = "cpu"
    device = "CPU (hashlib)"
    vendor = None
    fallback_reason = "execution backend configured as cpu"
    grind_batch = 1 << 20
    launches = 0
    kernel_ms = 0.0
    k_gold = k_m32 = k_range = None


class MMIOControlSink:
    """Execute the control/recovery ABI against the real MMIO bridge.

    Every method performs an actual device, ring, or coordinator-state
    operation; nothing reports success without the underlying call running.
    Coordinator-level effects (submission throttle, record quarantine) are
    delivered through injected callbacks so the sink itself never fabricates
    a side effect.
    """

    def __init__(
        self,
        bridge: MMIOBridge,
        *,
        on_throttle: Any | None = None,
        on_quarantine: Any | None = None,
        on_prune: Any | None = None,
    ) -> None:
        self._bridge = bridge
        self._on_throttle = on_throttle
        self._on_quarantine = on_quarantine
        self._on_prune = on_prune

    def sever_lane(self, *, parameters: Mapping[str, Any], evidence: Mapping[str, Any]) -> None:
        # Mask all lanes off, then commit through the device supervisor.
        self._bridge.stage_lane_mask(0)
        self._bridge.request_supervisor_commit()

    def flush_lane(
        self, *, job_id: str, parameters: Mapping[str, Any], evidence: Mapping[str, Any]
    ) -> None:
        # Restore the full lane mask after severance/stale-work isolation.
        self._bridge.stage_lane_mask(0xFFFFFFFF)
        self._bridge.request_supervisor_commit()

    def restart_lane(self, *, parameters: Mapping[str, Any], evidence: Mapping[str, Any]) -> None:
        self._bridge.stop()
        self._bridge.start()

    def apply_backpressure(
        self, *, parameters: Mapping[str, Any], evidence: Mapping[str, Any]
    ) -> None:
        if self._on_throttle is None:
            raise RuntimeError("no throttle callback wired for backpressure")
        self._on_throttle(True)

    def quarantine_record(
        self, *, parameters: Mapping[str, Any], evidence: Mapping[str, Any]
    ) -> None:
        if self._on_quarantine is None:
            raise RuntimeError("no quarantine callback wired")
        record_id = str(parameters.get("record_id", ""))
        if not record_id:
            raise RuntimeError("quarantine requires the observed record id")
        self._on_quarantine(record_id)

    def flush_persistence_ring(
        self, *, parameters: Mapping[str, Any], evidence: Mapping[str, Any]
    ) -> None:
        self._bridge.reset_ring()

    def reset_cursor(self, *, parameters: Mapping[str, Any], evidence: Mapping[str, Any]) -> None:
        self._bridge.reset_ring()

    def resize_workgroup(
        self, *, parameters: Mapping[str, Any], evidence: Mapping[str, Any]
    ) -> None:
        # The only honest effect available at this layer is throttling new
        # work dispatch; the device exposes no workgroup-resize register.
        if parameters.get("direction") != "down":
            raise RuntimeError("unsupported resize direction at the MMIO layer")
        if self._on_throttle is None:
            raise RuntimeError("no throttle callback wired for resize")
        self._on_throttle(True)

    def prune_window(self, *, parameters: Mapping[str, Any], evidence: Mapping[str, Any]) -> None:
        if self._on_prune is None:
            raise RuntimeError("no prune callback wired")
        self._on_prune(dict(parameters))


class IntelligentPoolCoordinator(ManifoldPoolCoordinator):
    """Canonical coordinator with measured TOE context and lane selection."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        session = kwargs.pop("mining_session", None)
        observer = kwargs.pop("chain_observer", None)
        hasher = kwargs.pop("execution_hasher", None)
        causal_log_path = kwargs.pop("causal_log_path", None)
        super().__init__(*args, **kwargs)
        # A started worker hashes; whether it may submit is a separate,
        # live question (submission_permitted). Unapproved, it mines in
        # shadow: full SHA256d and target checks, shares found and learned
        # from, nothing written to the pool.
        self.mining_enabled = True
        self._live_submit_approved = False
        self.session = session if session is not None else MiningSession()
        self.chain_observer = observer
        self._submission_lock = asyncio.Lock()
        self._search_lock = asyncio.Lock()
        self._chain_tip = None
        self._last_chain_poll = 0.0
        self.mining_intelligence = MiningIntelligenceChooser()
        try:
            self.toe: TOEMiningAdapter | None = TOEMiningAdapter()
        except TOEUnavailable as exc:
            LOG.warning(
                "TOE adapter unavailable at startup; coordinator running without "
                "tensor context (mining continues, TOE evidence will be absent): %s",
                exc,
            )
            self.toe = None
        self.intelligence = IntelligenceController()
        self.self_healing = SelfHealingAgent()
        self.recovery_queue = NonBlockingRecoveryQueue()
        self.solver = M32SearchSolver()
        self.last_mining_decision = None
        self.last_toe_context = None
        self.last_toe_frame: TOEMiningDecisionFrame | None = None
        self.last_toe_signal: TOECausalSignal | None = None
        self.purity_torn_events: list[dict[str, Any]] = []
        self._dispatch_breadth = _OBSERVED_WINDOW
        self.last_recovery_plan: RecoveryPlan | None = None
        self.last_control_signals: tuple[str, ...] = ()
        self.work_throttled = False
        # A throttle pauses vault polling, never observation for good: after
        # ``throttle_probe_s`` one record is let through, and only a fresh
        # observation (a HOLD plan) can clear the throttle or re-assert it.
        self.throttle_probe_s = 5.0
        self._throttled_at = 0.0
        self.quarantined_records: set[str] = set()
        self.proven_exclusions: list[dict[str, Any]] = []
        self._control_sink: MMIOControlSink | None = None
        self._bridge: MMIOBridge | None = None
        self._base_step = 0
        self._records_observed = 0
        self._last_job_id: str | None = None
        self._recovery_backpressure = False
        self.agentic = AgenticMiningController()
        self.tuning = TuningGate()
        self._tuned_window: int | None = None
        # Measured-only operating intelligence: HOW MUCH per window. It never
        # touches SHA256d, targets, shares or pool outcomes.
        self.world = MiningWorldModel()
        self.operating_policy = OperatingPolicy(self.world)
        self.loss = LossLedger()
        try:
            audit_every = int(os.getenv("PYTHIA_POLICY_AUDIT_EVERY", "64"))
        except ValueError:
            audit_every = 64
        self.policy_audit = PolicyAuditor(every=audit_every)
        # The rate the network sees stays under the operator's configured
        # cap and 1% of the network; re-read from runtime config every 5 s.
        self.governor = HashrateGovernor()
        self._governor_config_at = float("-inf")
        self._policy_mode = os.getenv("PYTHIA_OPERATING_POLICY", "model").strip().lower()
        self._nonce_order = resolve_nonce_order(os.getenv("PYTHIA_NONCE_ORDER", "hendrix"))
        try:
            self._max_window_seconds = float(os.getenv("PYTHIA_MAX_WINDOW_SECONDS", "2.0"))
        except ValueError:
            self._max_window_seconds = 2.0
        self._idle_seen_ms = 0.0
        # Learners for the seeded questions recovery.effect, precompute.depth
        # and policy.promotion (see docs/LEARNING.md).
        self.recovery_effects = RecoveryEffects()
        self._ready_record = [0, 0]  # windows that found a plan ready, windows
        self._last_window_s: float | None = None
        self._shadow: ShadowTrial | None = None
        self._shadow_tried: set[tuple[str, ...]] = set()
        self._shadow_published: str | None = None
        self._bound_session: str | None = None
        try:
            self._memory_every_s = float(os.getenv("PYTHIA_INTELLIGENCE_CHECKPOINT_S", "60"))
        except ValueError:
            self._memory_every_s = 60.0
        self._memory_saved_at = time.monotonic()
        self.intelligence_memory: IntelligenceMemory | None = None
        memory_dir = os.getenv("PYTHIA_INTELLIGENCE_DIR", "").strip()
        if memory_dir:
            self._attach_intelligence_memory(memory_dir)
        # What this miner learns, every intelligence can know: the fabric's
        # journal sits beside the Aethel memory and is shared by all workers.
        self.knowledge = KnowledgeFabric(default_journal_path() if memory_dir else None)
        self._knowledge_at = float("-inf")
        # Learning is judged, not assumed: forecasts committed when a plan is
        # made are scored against a null when its window finishes.
        self.learning = LearningLedger.from_seeds(fabric=self.knowledge)
        self._forecasts: dict[str, dict[str, Any]] = {}
        self._elapsed_scale = {"learner": ResidualScale(), "null": ResidualScale()}
        self._sec_per_hash: dict[str, float] = {}
        self.execution_hasher = hasher if hasher is not None else CpuReferenceHasher()
        self.causal = CausalLedger(path=causal_log_path)
        self.recovery = RecoveryGovernor(on_event=self._on_recovery_event)
        self._evidence_sink: Any = None
        self._evidence_published_at = 0.0
        self._pending_correlation: dict[str, Any] | None = None
        self._precompute_task: asyncio.Task | None = None
        self._precompute_wake = asyncio.Event()
        # Wakes the execution/hardware loops the moment pool state, a fresh
        # job, or a recovery edge may have made work available; idle waits
        # stay bounded by their declared slices, never blind.
        self._work_wake = asyncio.Event()
        self._agentic_state_path: str | None = None
        self._identity_block_logged: set[str] = set()
        self._last_pool_outcome = PoolOutcome.NOT_SUBMITTED
        self._last_submission_id: str | None = None
        self._last_executed_key: tuple[str, int, str] | None = None
        self.last_execution: dict[str, Any] | None = None
        self.last_dispatch_algebra: dict[str, Any] | None = None
        self._dispatch_counts = {"certified": 0, "refused": 0}
        self._metrics_sink: Any = None
        self._metrics_published_at = float("-inf")
        self._hash_samples: deque[tuple[float, int]] = deque()
        self._hash_meter_started = time.monotonic()
        self._hashes_total = 0
        self._executions_total = 0
        self._shares_accepted = 0
        upstream_sink = self.stratum_status_sink

        def _stratum_sink(snapshot: dict[str, Any]) -> None:
            # Stratum publishes on every job/target/session edge; re-binding
            # here invalidates queued plans in the same notification.
            if upstream_sink is not None:
                upstream_sink(snapshot)
            try:
                self._refresh_work_identity()
            except Exception:
                LOG.exception("agentic identity refresh from Stratum status failed")
            self._work_wake.set()

        self.stratum_status_sink = _stratum_sink

    async def run_hardware_loop(
        self,
        bridge: MMIOBridge,
        *,
        difficulty_mask: int,
        base_step: int,
        poll_ms: int = 100,
    ) -> None:
        if self.submit_enabled and self.chain_observer is None:
            raise RuntimeError("live mining requires a Bitcoin chain observer")
        # The sink and base step are bound here so per-record observations
        # can execute real recovery actions and materialise the declared
        # candidate window for the chooser.
        self._bridge = bridge
        self._base_step = base_step
        self._control_sink = MMIOControlSink(
            bridge,
            on_throttle=self._set_throttled,
            on_quarantine=self.quarantined_records.add,
            on_prune=self.proven_exclusions.append,
        )
        if self._agentic_state_path:
            self.agentic.load_state(self._agentic_state_path)
        self._precompute_task = asyncio.create_task(self._precompute_loop())
        try:
            await super().run_hardware_loop(
                bridge,
                difficulty_mask=difficulty_mask,
                base_step=base_step,
                poll_ms=poll_ms,
            )
        finally:
            self._precompute_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._precompute_task
            self._precompute_task = None
            if self._agentic_state_path:
                self.agentic.save_state(self._agentic_state_path)
            if self.client is not None:
                with contextlib.suppress(Exception):
                    await self.client.close()
                self.client = None

    async def run_execution_loop(
        self,
        *,
        idle_s: float = 0.05,
        max_backoff_s: float | None = None,
    ) -> None:
        """Mine through the Execution Router alone, with no MMIO bridge.

        The same leased SearchPlan -> router -> host recheck -> proof adapter
        path as the hardware loop, driven by the pool's jobs instead of vault
        records. Pool loss is retried with exponential backoff across every
        configured endpoint (primary first, then failover); an authorization
        refusal from every pool is retried too, so the worker and its
        telemetry stay up while the operator fixes the credentials. The
        backoff cap defaults to ``PYTHIA_RECONNECT_MAX_S`` (30 s), the same
        calibrated bound the hardware loop uses: lost hashrate is linear in
        reconnect latency, so a multi-minute silent gap is not acceptable.
        """
        if max_backoff_s is None:
            max_backoff_s = _positive_env("PYTHIA_RECONNECT_MAX_S", 30.0)
        if max_backoff_s <= 0:
            raise ValueError("max_backoff_s must be positive")
        if self.submit_enabled and self.chain_observer is None:
            raise RuntimeError("live mining requires a Bitcoin chain observer")
        if self._agentic_state_path:
            self.agentic.load_state(self._agentic_state_path)
        try:
            await self._start_control_server()
        except OSError as exc:
            LOG.warning("coordinator control channel unavailable: %s", exc)
        self._hash_meter_started = time.monotonic()
        self._precompute_task = asyncio.create_task(self._precompute_loop())
        delay = self.reconnect_delay
        try:
            while True:
                if not self.client or not self.client.connected:
                    if self.client:
                        with contextlib.suppress(Exception):
                            await self.client.close()
                        self.client = None
                    try:
                        await self.connect_with_failover()
                    except Exception as exc:
                        kind = (
                            "every pool refused authorization"
                            if isinstance(exc, StratumAuthorizationError)
                            else "every pool unavailable"
                        )
                        LOG.warning("%s: %s; retrying in %.1fs", kind, exc, delay)
                        self._publish_metrics(force=True)
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, max_backoff_s)
                        continue
                    delay = self.reconnect_delay
                    LOG.info("mining through %s", self.client.endpoint.name)
                executions_before = self._executions_total
                permitted = await self.before_hardware_poll()
                if permitted:
                    try:
                        await self.search_current_job()
                    except (ConnectionError, asyncio.IncompleteReadError) as exc:
                        LOG.warning("pool connection lost during search: %s", exc)
                        with contextlib.suppress(Exception):
                            await self.client.close()
                        self.client = None
                        continue
                self._publish_metrics()
                if self._executions_total == executions_before:
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(self._work_wake.wait(), idle_s)
                    self._work_wake.clear()
        finally:
            self._precompute_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._precompute_task
            self._precompute_task = None
            if self._agentic_state_path:
                self.agentic.save_state(self._agentic_state_path)
            if self.client is not None:
                with contextlib.suppress(Exception):
                    await self.client.close()
                self.client = None
            if self._control_server:
                self._control_server.close()
                with contextlib.suppress(Exception):
                    await self._control_server.wait_closed()
                with contextlib.suppress(OSError):
                    os.unlink(self.control_socket_path)
            if self.telemetry:
                self.telemetry.close()

    def set_agentic_state_path(self, path: str) -> None:
        """Configure where the agentic controller persists its learned policy."""
        self._agentic_state_path = path

    async def connect_with_failover(self):
        client = await super().connect_with_failover()
        # The handshake's first mining.notify arrives before self.client is set.
        self._refresh_work_identity()
        self._precompute_wake.set()
        self._work_wake.set()
        return client

    def apply_salamander_mode(self, mode: str, recovery_id: str | None = None) -> None:
        """Consume a Salamander supervisor mode; speculation freezes while it heals."""
        record = self.recovery.external_mode(mode, recovery_id)
        self.causal.record(
            "salamander_mode",
            CausalCoordinate(recovery_id=record.recovery_id if record else recovery_id),
            mode=mode,
            governed_mode=self.recovery.mode,
        )
        self._sync_recovery_gate()
        self._publish_evidence(force=True)

    async def _handle_control_request(self, request: Mapping[str, Any]) -> dict[str, Any]:
        if request.get("op") == "salamander_mode":
            try:
                self.apply_salamander_mode(
                    str(request.get("mode")), recovery_id=request.get("recovery_id")
                )
            except ValueError as exc:
                return {"status": "error", "reason": str(exc)}
            return {"status": "ok", "mode": self.recovery.mode}
        return await super()._handle_control_request(request)

    def _sync_recovery_gate(self) -> None:
        active = self._recovery_backpressure or self.recovery.freezes_speculation
        self.agentic.set_recovery_active(active)
        self.loss.observe_recovery(time.monotonic(), active)
        self._precompute_wake.set()
        self._work_wake.set()

    def _on_recovery_event(self, kind: str, record: RecoveryRecord) -> None:
        if kind == "recovery_verified" and hasattr(self, "recovery_effects"):
            self.recovery_effects.recovery_verified(record.recovery_id, list(record.commands))
        if kind in ("recovery_verified", "recovery_failed") and hasattr(self, "knowledge"):
            try:
                self.knowledge.publish(
                    "salamander.recovery_authority",
                    "salamander.recovery",
                    {
                        "recovery_id": record.recovery_id,
                        "state": record.state.value,
                        "commands": list(record.commands),
                        "reason": record.reason,
                        "failure": record.failure,
                    },
                    evidence="measured",
                )
            except Exception as exc:
                LOG.warning("recovery outcome not shared: %s", exc)
        self.causal.record(
            kind,
            CausalCoordinate(recovery_id=record.recovery_id),
            origin=record.origin,
            commands=list(record.commands),
            dispatched=list(record.dispatched),
            deferred=list(record.deferred),
            ack=record.ack,
            failure=record.failure,
        )

    def _supervisor_ack(self) -> bool | None:
        ack = getattr(self._bridge, "supervisor_commit_ack", None)
        return bool(ack()) if callable(ack) else None

    def set_evidence_sink(self, sink: Any) -> None:
        """Receive the evidence snapshot whenever the voyage changes."""
        self._evidence_sink = sink

    def set_metrics_sink(self, sink: Any) -> None:
        """Receive measured worker counters (``hashrate_hs``, ``shares_accepted``)."""
        self._metrics_sink = sink

    def measured_hashing(self) -> dict[str, Any]:
        """Hashes completed over the trailing wall-clock span; nothing estimated."""
        now = time.monotonic()
        while self._hash_samples and self._hash_samples[0][0] < now - _HASHRATE_SPAN_S:
            self._hash_samples.popleft()
        span = min(_HASHRATE_SPAN_S, now - self._hash_meter_started)
        hashes = sum(count for _at, count in self._hash_samples)
        return {
            "hashrate_hs": hashes / span if span > 0 else 0.0,
            "span_s": round(span, 3),
            "hashes_in_span": hashes,
            "hashes_total": self._hashes_total,
            "executions_total": self._executions_total,
            "shares_accepted": self._shares_accepted,
        }

    def _publish_metrics(self, *, force: bool = False) -> None:
        if self._metrics_sink is None:
            return
        now = time.monotonic()
        if not force and now - self._metrics_published_at < _METRICS_MIN_INTERVAL_S:
            return
        self._metrics_published_at = now
        hashing = self.measured_hashing()
        try:
            self._metrics_sink(
                {
                    "hashrate_hs": round(hashing["hashrate_hs"], 3),
                    "hashes_total": hashing["hashes_total"],
                    "shares_accepted": hashing["shares_accepted"],
                    "executions_total": hashing["executions_total"],
                    "backend": str(getattr(self.execution_hasher, "backend", "unknown")),
                }
            )
        except Exception:
            LOG.exception("metrics sink failed")

    def _publish_evidence(self, *, force: bool = False) -> None:
        if self._evidence_sink is None:
            return
        now = time.monotonic()
        if not force and now - self._evidence_published_at < _EVIDENCE_MIN_INTERVAL_S:
            return
        self._evidence_published_at = now
        try:
            self._evidence_sink(self.evidence_snapshot())
        except Exception:
            LOG.exception("evidence sink failed")

    def evidence_snapshot(self) -> dict[str, Any]:
        decision = self.tuning.last_decision
        hasher = self.execution_hasher
        return {
            "schema": "pythia.mining_evidence/1",
            "observed_at": time.time(),
            "agentic": self.agentic.snapshot(),
            "last_execution": self.last_execution,
            "tuning": asdict(decision) if decision is not None else None,
            "recovery": self.recovery.snapshot(),
            "chain_evidence": (
                getattr(self.chain_observer, "source", "bitcoind")
                if self.chain_observer is not None
                else None
            ),
            "execution_backend": {
                "backend": getattr(hasher, "backend", None),
                "device": getattr(hasher, "device", None),
                "vendor": getattr(hasher, "vendor", None),
                "fallback_reason": getattr(hasher, "fallback_reason", None),
                "route": self._execution_route(),
            },
            "session": {
                "state": self.session.state,
                "cycles": self.session.cycles,
                "rung": self.session.rung,
                "share_log_tail": self.session.share_log[-8:],
            },
            "causal_tail": self.causal.snapshot(24),
            "submission": "live" if self.submission_permitted() else "shadow",
            "intelligence": self.intelligence_snapshot(),
            "dispatch_algebra": (
                {**self.last_dispatch_algebra, "counts": dict(self._dispatch_counts)}
                if self.last_dispatch_algebra is not None
                else None
            ),
            "hashing": self.measured_hashing(),
        }

    def agentic_status(self) -> dict[str, Any]:
        return {**self.evidence_snapshot(), "salamander_mode": self.recovery.mode}

    def _resolve_work_identity(self) -> tuple[WorkIdentity | None, str | None]:
        """Project Stratum's canonical job generation; never invent one."""
        client = self.client
        if client is None:
            return None, "NO_CLIENT"
        adapter = getattr(client, "proof_adapter", None)
        if adapter is None:
            return None, "NO_PROOF_ADAPTER"
        state = getattr(client, "runtime_state", None)
        if state is None:
            return None, "NO_RUNTIME_STATE"
        if adapter.subscription is None:
            return None, "NO_SUBSCRIPTION"
        generation = state.current_job
        if generation is None or adapter.current_job is None:
            return None, "NO_CURRENT_JOB"
        if not state.session_id:
            return None, "NO_SESSION"
        if generation.target is None or adapter.current_job.target is None:
            return None, "NO_ACTIVE_TARGET"
        if (
            adapter.current_job.job_id != generation.job_id
            or adapter.current_job.target != generation.target
        ):
            return None, "IDENTITY_MISMATCH"
        return (
            WorkIdentity(
                pool_session_id=state.session_id,
                generation=generation.generation_id,
                job_id=generation.job_id,
                job_fingerprint=generation.fingerprint,
                target_generation=generation.target_generation,
                clean_jobs=generation.clean_jobs,
                received_at=generation.received_at,
                work_space=_header_work_space(generation),
            ),
            None,
        )

    def _refresh_work_identity(self) -> WorkIdentity | None:
        identity, reason = self._resolve_work_identity()
        if identity is None:
            if reason in ("NO_PROOF_ADAPTER", "NO_RUNTIME_STATE") and (
                reason not in self._identity_block_logged
            ):
                self._identity_block_logged.add(reason)
                LOG.warning(
                    "Stratum client lacks %s; agentic precompute and leased execution disabled",
                    reason,
                )
            self.agentic.clear_work(reason or "NO_WORK_IDENTITY")
            return None
        if self.agentic.bind_work(identity):
            # TOE evidence belongs to one observed Stratum identity. Clear it
            # before waking precompute so a new generation can never inherit
            # the previous job's frame or steering signal.
            self.last_toe_context = None
            self.last_toe_frame = None
            self.last_toe_signal = None
            now = time.monotonic()
            new_session = self._bound_session not in (None, identity.pool_session_id)
            self._bound_session = identity.pool_session_id
            self.world.observe_bind(now, clean_jobs=identity.clean_jobs, new_session=new_session)
            self.loss.observe_bind(now)
            self.causal.record(
                "identity_bound",
                CausalCoordinate(
                    pool_session_id=identity.pool_session_id,
                    generation=identity.generation,
                    job_fingerprint=identity.job_fingerprint,
                ),
                job_id=identity.job_id,
                clean_jobs=identity.clean_jobs,
                target_generation=identity.target_generation,
            )
            self._precompute_wake.set()
            self._work_wake.set()
        return identity

    def _set_throttled(self, throttled: bool) -> None:
        self.work_throttled = bool(throttled)
        if throttled:
            self._throttled_at = time.monotonic()

    def _throttle_holds(self) -> bool:
        return self.work_throttled and time.monotonic() - self._throttled_at < self.throttle_probe_s

    async def before_hardware_poll(self) -> bool:
        if not self.submission_permitted():
            return not self._throttle_holds()
        if self.chain_observer is None:
            return False
        if self.session.state == "SUBMITTING" and not self._submission_lock.locked():
            self.session.submission_finished(None)
        now = time.monotonic()
        if now - self._last_chain_poll >= 1.0 or self._chain_tip is None:
            try:
                tip = await asyncio.to_thread(self.chain_observer.tip)
                own_height = None
                pending = self.session.pending
                if (
                    pending
                    and pending["block_candidate"]
                    and (pending["outcome"] is None or pending["outcome"] is True)
                ):
                    own_height = await asyncio.to_thread(
                        self.chain_observer.confirmed_height, pending["block_hash"]
                    )
                self.session.observe_external(**tip, own_block_height=own_height)
                if self.session.state == "COOLDOWN":
                    external = self.session.external
                    active_height = await asyncio.to_thread(
                        self.chain_observer.confirmed_height, external["block_hash"]
                    )
                    if active_height != external["height"]:
                        # The cooldown anchor left the active chain (reorg).
                        # Re-anchor on the current verified tip; refuse only
                        # if the tip itself cannot serve as evidence.
                        if not self.session.replace_external(**tip):
                            return False
                if tip["block_hash"] == self.session.last_block_hash:
                    return False
                self._chain_tip = tip
                self._last_chain_poll = now
            except Exception:
                LOG.exception("chain observation unavailable; mining paused")
                self._chain_tip = None
                return False
        self.session.finish_cooldown()
        return self.session.state == "SEARCHING" and not self._throttle_holds()

    def _toe_or_declared_absent(self, operation: str) -> TOEMiningAdapter | None:
        """Return the live TOE adapter, or None for a declared operation.

        Raises ``TOEUnavailable`` when the adapter is absent and the
        operation is not in ``PERMITTED_WITHOUT_TOE`` — that is the declared
        boundary of the soft gate.
        """
        if self.toe is None and operation not in PERMITTED_WITHOUT_TOE:
            raise TOEUnavailable(
                f"{operation} requires TOE evidence and is not declared in "
                f"PERMITTED_WITHOUT_TOE"
            )
        return self.toe

    @staticmethod
    def _cassini_fault(state: bytes) -> str | None:
        """Torn-state detection: the hot descriptor's Cassini seal must be ±1."""
        if len(state) != 64:
            return "state_not_64_bytes"
        cassini_u32 = struct.unpack(CURRENT_HOT_STATE_FORMAT, state)[9]
        cassini = cassini_u32 if cassini_u32 < 0x80000000 else cassini_u32 - 0x100000000
        if cassini not in (1, -1):
            return f"invalid_cassini_seal:{cassini}"
        return None

    def _observed_candidate_window(self) -> list[int]:
        """The declared solver ordering over a bounded window at base_step.

        The window is materialised from the real M32 allocation contract —
        never an invented distribution — so the chooser evaluates the actual
        candidate stream the engine would visit.
        """
        return [
            nonce
            for nonce, _lane in self.solver.candidates(self._base_step, self._dispatch_breadth)
        ]

    def _build_toe_signal(self) -> TOECausalSignal | None:
        """Convert the last measured TOE context into a causal signal.

        Returns None when no measured context exists or conversion fails;
        the chooser then runs its default measured contract (fail-closed).
        The signal is feed-forward evidence only — it can reorder the solver
        sweep and gate dispatch, but it can never reach the SHA256d/target
        comparison path.
        """
        if self.last_toe_context is None:
            return None
        try:
            return build_toe_signal(self.last_toe_context)
        except TOEConsensusBoundaryError as exc:
            self._record_toe_boundary_violation(exc)
            return None
        except (ValueError, TypeError) as exc:
            LOG.warning(
                "TOE signal conversion failed; continuing without causal signal: %s",
                exc,
            )
            return None

    def _toe_advice_reason(self) -> str:
        signal = self.last_toe_signal
        if signal is None:
            return "TOE_UNAVAILABLE_OR_INCOMPLETE"
        if not signal.is_valid():
            return "INVALID_SIGNAL_FAIL_CLOSED"
        if signal.causal_throttle:
            return "SAFETY_THROTTLE"
        if signal.intervention_optimal and signal.face_confidence > 0:
            return "LANE_BIAS_APPLIED"
        return "NO_OPTIMAL_INTERVENTION"

    def _record_toe_boundary_violation(self, exc: TOEConsensusBoundaryError) -> None:
        """Record a refused TOE output; the evidence is rejected, not sanitized."""
        LOG.warning("TOE consensus boundary violation; evidence refused: %s", exc)
        identity, _reason = self._resolve_work_identity()
        self.causal.record(
            "toe_boundary_violation",
            CausalCoordinate(
                pool_session_id=identity.pool_session_id if identity else None,
                generation=identity.generation if identity else None,
                job_fingerprint=identity.job_fingerprint if identity else None,
            ),
            reason=str(exc),
        )

    def _apply_toe_signal(self, signal: TOECausalSignal | None) -> None:
        """Gate dispatch on a valid causal signal; never touches consensus.

        ``causal_throttle`` latches the chooser throttle and halves the
        per-dispatch nonce window breadth. A False value leaves any existing
        (operator-set or previously latched) throttle untouched. The target,
        the header, and the double-SHA256 path are never reached from here.
        """
        if signal is None or not signal.is_valid():
            return
        if signal.causal_throttle:
            self.mining_intelligence.throttle = True
            self._dispatch_breadth = max(1, _OBSERVED_WINDOW // 2)
            event = {
                "event": "PURITY_TORN",
                "entropy": signal.entropy,
                "purity": signal.coherence,
                "face_bias": signal.face_bias,
                "job_id": signal.job_id,
                "node_id": signal.node_id,
                "sequence": signal.sequence,
            }
            self.purity_torn_events.append(event)
            LOG.warning(
                "PURITY_TORN entropy=%.6f purity=%.6f face_bias=%d job=%s",
                signal.entropy,
                signal.coherence,
                signal.face_bias,
                signal.job_id,
            )

    def _dispatch_observation(
        self,
        plan: RecoveryPlan,
        signals: tuple[ControlSignal, ...] = (),
    ) -> list[str]:
        """Route one recovery plan plus controller signals through the governor.

        SelfHealingAgent and the controller only propose. The Salamander
        governor assigns a recovery_id, dispatches (recovery before signals,
        identical commands de-duplicated), defers lane-mask writes to a live
        Salamander supervisor, and reads the supervisor commit ACK. HOLD
        clears the dispatch throttle and is never a recovery.
        """
        from coordinator import CoordinatorControlRouter, _freeze

        router = CoordinatorControlRouter()
        steps: list[tuple[str, Any]] = []
        seen: set[tuple[str, Any]] = set()
        for action in plan.actions:
            command = action.command.value
            if command == RecoveryCommand.HOLD.value:
                self._set_throttled(False)
                continue
            key = (command, _freeze(action.parameters))
            if key not in seen:
                seen.add(key)
                steps.append(
                    (command, lambda a=action: router.dispatch_recovery(self._control_sink, a))
                )
        for signal in signals:
            command = signal.command.value
            if command == ControlCommand.HOLD.value:
                continue
            key = (command, _freeze(signal.parameters))
            if key not in seen:
                seen.add(key)
                steps.append(
                    (command, lambda s=signal: router.dispatch_signal(self._control_sink, s))
                )
        reason = plan.actions[0].reason if plan.actions else "controller signal"
        record = self.recovery.propose([command for command, _ in steps], reason)
        if record is None:
            return []
        self.recovery.dispatch(record, steps, ack=self._supervisor_ack)
        return list(record.dispatched)

    async def _precompute_loop(self) -> None:
        """Event-driven lookahead; CancelledError propagates for clean shutdown."""
        while True:
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._precompute_wake.wait(), _PRECOMPUTE_IDLE_S)
            self._precompute_wake.clear()
            try:
                self._fill_precompute_queue()
            except Exception:
                LOG.exception("agentic precompute step failed")

    def _fill_precompute_queue(self) -> int:
        """Top the queue up to the adaptive lookahead; bounded, never speculative in recovery."""
        if not self.mining_enabled or self.session.state != "SEARCHING" or self.work_throttled:
            return 0
        identity = self._refresh_work_identity()
        if identity is None:
            return 0
        built = 0
        for _ in range(self.agentic.plans_needed()):
            started = time.perf_counter()
            plan = self._build_plan(identity)
            if plan is None or not self.agentic.submit_plan(plan):
                break
            # What a plan costs to build: the precompute depth is set from it.
            self.world.observe_plan_latency(time.perf_counter() - started)
            self._commit_forecasts(plan)
            self.causal.record(
                "plan_created",
                CausalCoordinate(
                    pool_session_id=plan.pool_session_id,
                    generation=plan.generation,
                    job_fingerprint=plan.job_fingerprint,
                    plan_id=plan.plan_id,
                    lease_id=plan.plan_id,
                ),
                route=plan.executor_route,
                nonce_start=plan.base_step,
                window=plan.window,
                policy=plan.policy_id,
            )
            built += 1
        return built

    def _window_cap(self) -> int:
        """Largest window the executing route should take in one plan.

        The CPU reference keeps its Lucas-rung budget. A bound OpenCL device
        takes the largest Lucas number that fits its measured launch cap:
        tiny launches leave the GPU idle (0.17 MH/s at 96 nonces vs 26 MH/s
        at 1M+ on a UHD 620), and pool difficulties need the throughput.
        """
        from lucas.core import lucas

        if self._execution_route() == "opencl_m32":
            launch = int(getattr(self.execution_hasher, "m32_launch", 0) or 0)
            if launch >= LANES:
                k, best = 0, LANES
                while lucas(k) <= launch:
                    best = max(best, lucas(k))
                    k += 1
                return best
        return lucas(self.session.rung)

    def _next_window(self) -> int:
        cap = self._window_cap()
        window = max(LANES, min(self._tuned_window or cap, cap))
        # Whole 32-lane epochs: the executed interval then equals the lease.
        legacy = window - window % LANES
        if self._policy_mode != "model":
            return legacy
        derated = self.tuning.last_decision is not None and (
            self.tuning.last_decision.action == "DE_RATE"
        )
        ctx = PolicyContext(
            route=self._execution_route(),
            lanes=LANES,
            # The intelligence may climb the Lucas scale ladder; every
            # solver call still enforces budget <= lucas(rung).
            max_window=max(cap, self._intelligence_ceiling()),
            legacy_window=legacy,
            legacy_lookahead=self.agentic.lookahead,
            capacity=self.agentic.capacity,
            chunk_cap=self._chunk_cap(),
            recovery_active=self.agentic.is_recovery_active(),
            derate_cap=self._tuned_window if derated else None,
            max_window_seconds=self._max_window_seconds,
        )
        shadow = self._shadow
        # A promoted candidate's levers tighten the live context; a candidate
        # still in shadow decides beside the policy without acting.
        decision = self.operating_policy.decide(shadow.context(ctx) if shadow else ctx)
        if shadow is not None and shadow.status == "shadow":
            try:
                shadow.observe(ctx, decision)
            except Exception as exc:  # a shadow trial must never stop mining
                LOG.warning("shadow trial failed: %s", exc)
        # One authority over precompute depth: the policy's model once plan
        # latency is measured, the controller's reactive adaptation before.
        measured = decision.source == "model" and "precompute_wait_ms" in decision.expected
        self.agentic.set_lookahead(
            decision.lookahead if measured else None,
            reason=f"job churn {decision.expected.get('job_churn_per_hour', 0.0):.1f}/h",
        )
        try:
            audit = self.policy_audit.maybe_audit(decision)
        except Exception as exc:  # an audit must never stop mining
            LOG.warning("policy audit failed: %s", exc)
            audit = None
        if audit is not None:
            self.causal.record(
                "policy_audit",
                CausalCoordinate(),
                decided_window=audit["decided_window"],
                classical_window=audit["classical_window"],
                vqc_window=audit["vqc"].get("window"),
                agree=audit["agree"],
                digest=audit["attestation"]["digest"],
            )
        return decision.window

    def _intelligence_ceiling(self) -> int:
        """Largest window the operating intelligence may choose.

        OpenCL: the measured launch cap (``_window_cap``). CPU reference: the
        Lucas value of the highest scale rung that fits a uint32 nonce space
        (L_31); ``cpu_sweep`` executes it as rung-sized solver calls, so the
        solver's ``budget <= lucas(rung)`` invariant holds for every call.
        """
        from lucas.core import lucas
        from lucas.ladder import SCALE_RUNGS

        if self._execution_route() == "opencl_m32":
            return self._window_cap()
        top = max(r for r in SCALE_RUNGS if lucas(r) < 2**32)
        return lucas(top)

    def _chunk_cap(self) -> int:
        hasher = self.execution_hasher
        cap = int(getattr(hasher, "grind_batch", 1) or 1)
        if self._execution_route() == "opencl_m32":
            cap = int(getattr(hasher, "m32_window_max", cap) or cap)
        return max(1, cap)

    def _attach_intelligence_memory(self, directory: str) -> None:
        try:
            memory = IntelligenceMemory(directory)
            state = memory.load()
            if state is not None:
                self.world.import_state(state)
                LOG.info("intelligence memory restored from aethel %s", directory)
            self.intelligence_memory = memory
        except Exception as exc:
            LOG.warning("intelligence memory unavailable (%s); learning from scratch", exc)

    def _share_knowledge(self, now: float) -> None:
        """Publish what the miner has learned and read what others have.

        Values are rounded to what is meaningful so a new version means the
        learning changed, not that time passed: dependents decohere only
        when their basis really moved.
        """
        if now - self._knowledge_at < 5.0:
            return
        self._knowledge_at = now

        def sig(value: Any, digits: int = 3) -> Any:
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not value:
                return value
            return float(f"{value:.{digits}g}")

        try:
            self.knowledge.sync()
            world = self.world.snapshot()
            learned = {
                "routes": {
                    name: {
                        "overhead_ms": sig(route.get("overhead_ms")),
                        "hash_rate_hs": sig(route.get("hash_rate_hs")),
                        "method": route.get("method"),
                    }
                    for name, route in sorted(world.get("routes", {}).items())
                },
                "invalidations_per_hour": sig(
                    world.get("invalidation_rate", {}).get("per_hour_mean"), 2
                ),
            }
            sags = {
                name: route["sag"]
                for name, route in sorted(world.get("routes", {}).items())
                if route.get("sag") is not None
            }
            if sags:
                learned["sag"] = {name: sig(value) for name, value in sags.items()}
            world_fact = self.knowledge.publish(
                "mining.world_model", "mining.world", learned, evidence="measured"
            )
            decision = self.operating_policy.last
            if decision is not None:
                self.knowledge.publish(
                    "mining.operating_policy",
                    "mining.policy",
                    {
                        "window": decision.window,
                        "lookahead": decision.lookahead,
                        "source": decision.source,
                    },
                    evidence="computed",
                    depends_on=[world_fact],
                )
            governor = self.governor
            share_yield = governor.share_yield()
            self.knowledge.publish(
                "mining.hashrate_governor",
                "mining.governor",
                {
                    "cap_hs": sig(governor.cap_hs),
                    "network_hs": sig(governor.network_hs),
                    "share_yield": sig(share_yield["ratio"]),
                    "shares": share_yield["shares"],
                },
                evidence="computed",
            )
            # The share law, tested on the governor's totals every cycle.
            self.learning.law(
                "shares.follow.work", expected=governor.expected_shares, observed=governor.shares
            )
            self._follow_promotion()
            self.learning.publish()
        except Exception as exc:
            LOG.warning("knowledge not shared this cycle: %s", exc)

    def submission_permitted(self) -> bool:
        """The operator's --submit, or the dashboard's approval for this very pool."""
        return self.submit_enabled or self._live_submit_approved

    def _approval_binds_here(self, cfg: dict[str, Any], runtime_config: Any) -> bool:
        """The dashboard approval is bound to one pool identity (endpoint and
        worker): it permits submission only while that is the pool this
        session is connected to and authorized as."""
        if not runtime_config.live_submit_permitted(cfg):
            return False
        pool = runtime_config.active_pool(cfg)
        client = self.client
        if pool is None or client is None:
            return False
        approved = parse_endpoint(pool["endpoint"], "approved")
        connected = client.endpoint
        worker = connected.username or self.username
        return (approved.host, approved.port) == (connected.host, connected.port) and (
            pool["worker"] == worker
        )

    def _refresh_governor(self) -> None:
        """Re-read the operator's runtime config: the hashrate cap and the
        live-submission approval both apply within 5 s, without a restart."""
        now = time.monotonic()
        if now - self._governor_config_at < 5.0:
            return
        self._governor_config_at = now
        try:
            import runtime_config

            cfg = runtime_config.load()
            hashrate = cfg.get("hashrate", {})
            self.governor.configure(
                target_hs=hashrate.get("target_hs", 0.0),
                ceiling_hs=hashrate.get("ceiling_hs", runtime_config.HASHRATE_CEILING_HS),
            )
        except Exception as exc:
            # The last good limits stay in force; the network cap always does.
            LOG.warning("hashrate config unavailable, keeping current cap: %s", exc)
            return
        try:
            approved = self._approval_binds_here(cfg, runtime_config)
        except Exception as exc:  # an unreadable approval is no approval
            LOG.warning("live-submit approval unreadable, submission closed: %s", exc)
            approved = False
        if approved != self._live_submit_approved:
            LOG.info("live submission %s", "approved" if approved else "closed (shadow)")
        self._live_submit_approved = approved

    def _forecast_plan_ready(self) -> tuple[float, float] | None:
        """precompute.depth: the depth model's forecast and the base rate's,
        committed before the executor looks at the queue."""
        try:
            if self._last_window_s is None:
                return None
            p = self.world.plan_ready_probability(self.agentic.lookahead, self._last_window_s)
            if p is None:
                return None
            ready, n = self._ready_record
            return p, (ready + 1) / (n + 2)
        except Exception as exc:  # learning must never stop mining
            LOG.warning("plan-ready forecast failed: %s", exc)
            return None

    def _score_plan_ready(self, forecast: tuple[float, float] | None, miss: str | None) -> None:
        # Recovery and admission holds are not a depth question.
        if miss in ("recovery", "precompute_unavailable"):
            return
        ready = miss is None
        self._ready_record[0] += int(ready)
        self._ready_record[1] += 1
        if forecast is not None:
            try:
                self.learning.score_probability("precompute.depth", ready, *forecast)
            except Exception as exc:
                LOG.warning("plan-ready scoring failed: %s", exc)

    def _observe_recovery_effect(self, record: ExecutionRecord) -> None:
        """recovery.effect: the windows before and after each verified recovery."""
        if record.completion_state is not CompletionState.COMPLETE:
            return
        if record.elapsed_seconds > 0:
            self._last_window_s = record.elapsed_seconds
        try:
            if self.recovery_effects.observe_window(record.hash_count, record.elapsed_seconds):
                self.knowledge.publish(
                    "mining.recovery_effect",
                    "salamander.recovery_effect",
                    self.recovery_effects.snapshot(),
                    evidence="measured",
                )
        except Exception as exc:  # learning must never stop mining
            LOG.warning("recovery effect not shared: %s", exc)

    def _follow_promotion(self) -> None:
        """policy.promotion: take a twin-round winner into shadow; publish its status."""
        if self._shadow is None or self._shadow.status != "shadow":
            candidate = self.knowledge.observe("promotion.candidate")
            if (
                candidate is not None
                and not self.knowledge.stale(candidate)
                and candidate.value.get("verdict") == "shadow"
                and self._shadow is None
            ):
                levers = tuple(candidate.value.get("levers") or ())
                if applicable(levers) and levers not in self._shadow_tried:
                    self._shadow_tried.add(levers)
                    self._shadow = ShadowTrial(levers, self.world)
        if self._shadow is None:
            return
        snapshot = self._shadow.snapshot()
        key = f"{snapshot['status']}:{snapshot['epochs']}"
        if key != self._shadow_published:
            self.knowledge.publish(
                "mining.promotion_gate", "promotion.status", snapshot, evidence="measured"
            )
            self._shadow_published = key
        if self._shadow.status == "rejected":
            self._shadow = None

    def _commit_forecasts(self, plan: SearchPlan) -> None:
        """The world model's forecasts for ``plan``, and the nulls', before it runs."""
        try:
            route = self._execution_route()
            model = self.world.route(route)
            estimate = model.estimate() if model is not None else None
            last = self._sec_per_hash.get(route)
            entry: dict[str, Any] = {"route": route, "window": plan.window}
            duration = None
            if estimate is not None:
                duration = estimate[0] + plan.window * estimate[1]
                if last is not None:
                    entry["elapsed"] = (
                        (math.log(duration), self._elapsed_scale["learner"].sigma),
                        (math.log(plan.window * last), self._elapsed_scale["null"].sigma),
                    )
            if duration is not None:
                done = sum(self.world.completions.values())
                invalidated = self.world.completions.get(CompletionState.INVALIDATED.value, 0)
                entry["invalidated"] = (
                    -math.expm1(-self.world.clean.mean * duration),
                    (invalidated + 1) / (done + 2),
                )
            self._forecasts[plan.plan_id] = entry
            while len(self._forecasts) > 256:  # plans a new job discarded
                self._forecasts.pop(next(iter(self._forecasts)))
        except Exception as exc:  # learning must never stop mining
            LOG.warning("forecast failed: %s", exc)

    def _score_forecasts(self, record: ExecutionRecord) -> None:
        """Score the forecasts committed for this window; call before learning from it."""
        try:
            route = record.executed_route or record.device_used
            entry = self._forecasts.pop(record.plan_id, None) if record.plan_id else None
            complete = record.completion_state is CompletionState.COMPLETE
            if entry is not None and entry["route"] == route:
                invalid = record.completion_state is CompletionState.INVALIDATED
                if "invalidated" in entry:
                    self.learning.score_probability(
                        "window.invalidated", invalid, *entry["invalidated"]
                    )
                if "elapsed" in entry and complete and record.elapsed_seconds > 0:
                    x = math.log(record.elapsed_seconds)
                    learner, null = entry["elapsed"]
                    self.learning.score_quantity("window.elapsed", x, learner, null)
                    self._elapsed_scale["learner"].observe(x - learner[0])
                    self._elapsed_scale["null"].observe(x - null[0])
            if complete and record.hash_count > 0 and record.elapsed_seconds > 0:
                self._sec_per_hash[route] = record.elapsed_seconds / record.hash_count
        except Exception as exc:  # learning must never stop mining
            LOG.warning("forecast scoring failed: %s", exc)

    def intelligence_snapshot(self) -> dict[str, Any]:
        last = self.operating_policy.last
        return {
            "schema": "pythia.intelligence/1",
            "policy_mode": self._policy_mode,
            "window_ceiling": self._intelligence_ceiling(),
            "max_window_seconds": self._max_window_seconds,
            "world": self.world.snapshot(),
            "decision": last.as_dict() if last is not None else None,
            "loss": self.loss.snapshot(time.monotonic()),
            "audit": self.policy_audit.snapshot(),
            "governor": self.governor.snapshot(),
            "knowledge": self.knowledge.snapshot(recent=10),
            "learning": self.learning.report(),
            "memory": (
                self.intelligence_memory.snapshot()
                if self.intelligence_memory is not None
                else None
            ),
        }

    def _execution_route(self) -> str:
        hasher = self.execution_hasher
        if str(getattr(hasher, "backend", "")).startswith("opencl") and (
            getattr(hasher, "k_m32", None) is not None
        ):
            return "opencl_m32"
        return "cpu_reference"

    def _router_for(self, plan: SearchPlan) -> ExecutionRouter:
        """Router bound to this plan's M32 lane order for the CPU reference path."""
        order, rung = plan.lane_order, self.session.rung

        from lucas.core import lucas

        rung_budget = max(LANES, lucas(rung) - lucas(rung) % LANES)

        def cpu_sweep(header: bytes, target_le: bytes, start: int, count: int):
            # Whole-epoch sub-windows keep the M32 probe order of one long
            # sweep while respecting the solver's Lucas-rung budget, so a
            # device-sized plan that falls back to the CPU still executes.
            attempts, done = 0, 0
            while done < count:
                take = min(rung_budget, count - done)
                result = self.solver.scan_header(
                    header=header,
                    target=int.from_bytes(target_le, "little"),
                    budget=take,
                    lane_order=order,
                    scale_index=rung,
                    start_nonce=start + done,
                )
                attempts += result.attempts
                if result.valid:
                    blob = header[:76] + struct.pack("<I", result.found_nonce)
                    digest = hashlib.sha256(hashlib.sha256(blob).digest()).digest()
                    return result.found_nonce, digest, attempts
                done += take
            return None, None, attempts

        nonce_order = self._nonce_order
        return ExecutionRouter(
            self.execution_hasher, cpu_sweep, nonce_order=lambda _plan: nonce_order
        )

    def _effective_nonce_order(self) -> str:
        """The order the router will execute for the current route."""
        route = self._execution_route()
        if self._nonce_order == NONCE_ORDER_HENDRIX and route == "opencl_m32":
            on_device = bool(getattr(self.execution_hasher, "hendrix_on_device", False))
            return NONCE_ORDER_HENDRIX if on_device else NONCE_ORDER_M32
        return self._nonce_order

    def _certify_dispatch(
        self, plan: SearchPlan, job_id: str, header: bytes, target_le: bytes
    ) -> dict[str, Any]:
        """Exact-algebra certificate for one dispatch; a failure refuses it."""
        order = self._effective_nonce_order()
        schedule = None
        if order == NONCE_ORDER_HENDRIX and plan.window > 0:
            try:
                schedule = hendrix_schedule(plan.window)
            except NonceOrderUnavailable as exc:
                LOG.warning("Hendrix schedule unavailable for certificate: %s", exc)
        certificate = certify_dispatch(
            plan_id=plan.plan_id,
            job_id=job_id,
            base_step=plan.base_step,
            window=plan.window,
            lane_order=plan.lane_order,
            header=header,
            target_le=target_le,
            ceiling=max(self._window_cap(), self._intelligence_ceiling()),
            nonce_order=order,
            route=plan.executor_route,
            hendrix=schedule,
        )
        self._dispatch_counts["certified" if certificate["ok"] else "refused"] += 1
        self.last_dispatch_algebra = certificate
        return certificate

    def _identity_is(self, key: tuple[str, int, str]) -> bool:
        identity, _reason = self._resolve_work_identity()
        return identity is not None and identity.key == key

    def _baseline_plan(
        self, identity: WorkIdentity, lease: LeaseRecord, window: int, reason: str
    ) -> SearchPlan:
        order, order_source = self._lane_order_for(lease.start)
        return SearchPlan(
            job_fingerprint=identity.job_fingerprint,
            pool_session_id=identity.pool_session_id,
            generation=identity.generation,
            base_step=lease.start,
            window=window,
            extranonce2=lease.extranonce2,
            lane_order=order,
            preferred_face=self.solver.get_lane_start_offset(),
            dispatch_breadth=self._dispatch_breadth,
            executor_route=self._execution_route(),
            policy_id=_BASELINE_POLICY,
            evidence_refs={
                "lane_order_source": order_source,
                "toe_advice_reason": self._toe_advice_reason(),
                **(self.last_toe_frame.evidence_refs() if self.last_toe_frame else {}),
            },
            created_at=time.monotonic(),
            toe_frame_id=(self.last_toe_frame.frame_digest if self.last_toe_frame else None),
            plan_id=lease.lease_id,
            source=PlanSource.BASELINE_FALLBACK,
            plan_fallback_reason=reason,
        )

    def _lane_order_for(self, start: int) -> tuple[tuple[int, ...], str]:
        """The exact order the baseline would sweep: winner rotation or solver order."""
        remembered = self.session.memory.lane_order()
        if remembered is not None:
            return tuple(remembered), "winner_memory"
        return tuple(lane for _nonce, lane in self.solver.candidates(start, LANES)), "solver"

    def _build_plan(self, identity: WorkIdentity) -> SearchPlan | None:
        adapter = self.client.proof_adapter
        window = self._next_window()
        plan_id = str(uuid.uuid4())
        try:
            lease = self.agentic.reserve_lease(plan_id, window, adapter.next_extranonce2)
        except (LeaseConflict, LeaseExhausted, StratumAdapterError) as exc:
            LOG.debug("precompute lease unavailable: %s", exc)
            return None
        order, order_source = self._lane_order_for(lease.start)
        decision = self.last_mining_decision
        tuning = self.tuning.last_decision
        try:
            return SearchPlan(
                job_fingerprint=identity.job_fingerprint,
                pool_session_id=identity.pool_session_id,
                generation=identity.generation,
                base_step=lease.start,
                window=window,
                extranonce2=lease.extranonce2,
                lane_order=order,
                preferred_face=self.solver.get_lane_start_offset(),
                dispatch_breadth=self._dispatch_breadth,
                executor_route=self._execution_route(),
                policy_id=decision.lead if decision is not None else "flat_exhaustive",
                evidence_refs={
                    "lane_order_source": order_source,
                    "window_basis": (
                        "device_launch_lucas"
                        if self._execution_route() == "opencl_m32"
                        else "cpu_lucas_rung"
                    ),
                    "lookahead": self.agentic.lookahead,
                    "tuning_action": tuning.action if tuning is not None else None,
                    "toe_face_bias": (
                        self.last_toe_signal.face_bias if self.last_toe_signal is not None else None
                    ),
                    "toe_advice_reason": self._toe_advice_reason(),
                    **(self.last_toe_frame.evidence_refs() if self.last_toe_frame else {}),
                },
                created_at=time.monotonic(),
                toe_frame_id=(self.last_toe_frame.frame_digest if self.last_toe_frame else None),
                plan_id=plan_id,
            )
        except ValueError as exc:
            self.agentic.release_lease(plan_id)
            LOG.warning("precomputed plan rejected by contract: %s", exc)
            return None

    def _record_submission_gate(self, reason: str, job_id: str) -> None:
        coordinate = CausalCoordinate(**(self._pending_correlation or {}))
        self.causal.record(
            "submission_gate_refused",
            coordinate,
            reason=reason,
            job_id=job_id,
        )

    async def submit_candidate(
        self,
        *,
        job_id: str,
        extranonce2: str,
        ntime: str,
        nonce: int | str,
    ) -> bool:
        """Serialize proof-checked submissions through the persisted lifecycle."""
        async with self._submission_lock:
            return await self._submit_candidate_locked(
                job_id=job_id, extranonce2=extranonce2, ntime=ntime, nonce=nonce
            )

    async def _submit_candidate_locked(
        self, *, job_id: str, extranonce2: str, ntime: str, nonce: int | str
    ) -> bool:
        self._last_pool_outcome = PoolOutcome.NOT_SUBMITTED
        if not self.client:
            raise ConnectionError("no active Stratum client")
        if self.session.state != "SEARCHING" or self.work_throttled:
            self._record_submission_gate("NOT_SEARCHING_OR_THROTTLED", job_id)
            return False
        proof = self.client.proof_adapter.validate_candidate(
            job_id=job_id, extranonce2=extranonce2, ntime=ntime, nonce=nonce
        )
        if not self.submission_permitted():
            self._record_submission_gate("SUBMISSION_DISABLED", job_id)
            return False  # shadow: a proof-checked share, never written
        if self.chain_observer is None:
            raise RuntimeError("live submission requires a Bitcoin chain observer")
        tip = await asyncio.to_thread(self.chain_observer.tip)
        if proof.header[4:36][::-1].hex() != tip["block_hash"]:
            LOG.warning("candidate parent differs from verified chain tip")
            self._record_submission_gate("PARENT_MISMATCH", job_id)
            return False
        if self.session.already_submitted(proof.digest[::-1].hex()):
            LOG.warning("share already submitted; refusing a duplicate mining.submit")
            self._record_submission_gate("DUPLICATE_SUBMISSION", job_id)
            return False
        self._last_submission_id = f"submission:{uuid.uuid4()}"
        self.session.begin_submission(
            header=proof.header,
            target=proof.target,
            job_id=job_id,
            parent_hash=tip["block_hash"],
            parent_height=tip["height"],
            block_candidate=int.from_bytes(proof.digest, "little")
            <= compact_target(int.from_bytes(proof.header[72:76], "little")),
            submission_id=self._last_submission_id,
            correlation=self._pending_correlation,
        )
        self.causal.record(
            "submission_sent",
            CausalCoordinate(**(self._pending_correlation or {})).extend(
                submission_id=self._last_submission_id
            ),
            job_id=job_id,
            block_hash=proof.digest[::-1].hex(),
        )
        if self._bridge is not None:
            self._bridge.stop()
        runtime = getattr(self.client, "runtime_state", None)
        submitted_before = runtime.submitted if runtime is not None else None
        result = None
        try:
            result = await super().submit_candidate(
                job_id=job_id, extranonce2=extranonce2, ntime=ntime, nonce=nonce
            )
        except BaseException:
            # Unknown stays unknown: once mining.submit may have been written,
            # neither acceptance nor rejection can be claimed.
            wrote = runtime is None or runtime.submitted != submitted_before
            self._last_pool_outcome = (
                PoolOutcome.OUTCOME_UNKNOWN if wrote else PoolOutcome.NOT_SUBMITTED
            )
            raise
        finally:
            self.session.submission_finished(result)
            # A resolved share returns the lifecycle to SEARCHING directly; the
            # base loop only restarts the bridge after a refused poll, so the
            # device paused for this submission must be resumed here.
            if self._bridge is not None and self.session.state == "SEARCHING":
                self._bridge.start()
        self._last_pool_outcome = PoolOutcome.ACCEPTED if result is True else PoolOutcome.REJECTED
        return result

    async def search_current_job(self) -> bool:
        """Execute one leased window through the Execution Router.

        A precomputed agentic SearchPlan runs when one is ready; otherwise a
        leased, labelled baseline SearchPlan does. Returns True only for a
        literal pool ACCEPTED response.
        """
        async with self._search_lock:
            if (
                not self.mining_enabled
                or self.session.state != "SEARCHING"
                or self.work_throttled
                or not self.client
            ):
                return False
            identity = self._refresh_work_identity()
            if identity is None:
                self.last_execution = {
                    "executed": False,
                    "reason": self.agentic.admission_block_reason(),
                }
                return False
            client = self.client
            adapter = client.proof_adapter
            job = adapter.current_job
            self._refresh_governor()
            try:
                self.governor.observe_network(job.nbits)
            except (AttributeError, ValueError) as exc:
                LOG.debug("network rate unavailable from job nbits: %s", exc)
            if not self.governor.admit():
                self.last_execution = {
                    "executed": False,
                    "reason": "hashrate_governor",
                    "cap_hs": self.governor.cap_hs,
                }
                return False
            ready_forecast = self._forecast_plan_ready()
            plan = self.agentic.consume_plan(timeout_ms=0)
            fallback_reason = (
                None
                if plan is not None
                else self.agentic.telemetry.last_consume_miss_reason or "queue_empty"
            )
            self._score_plan_ready(ready_forecast, fallback_reason)
            reserved: LeaseRecord | None = None
            lease: LeaseRecord | None = None
            if plan is not None:
                reserved = self.agentic.lease(plan.plan_id)
                try:
                    lease = self.agentic.begin_execution(plan)
                except LeaseConflict:
                    plan, reserved, fallback_reason = None, None, "stale_plan"
            self._precompute_wake.set()
            self._work_wake.set()
            if plan is None:
                window = self._next_window()
                try:
                    reserved = self.agentic.reserve_fallback(window, adapter.next_extranonce2)
                    plan = self._baseline_plan(identity, reserved, window, fallback_reason)
                    lease = self.agentic.begin_reserved(reserved.lease_id)
                except (LeaseConflict, LeaseExhausted, StratumAdapterError, ValueError) as exc:
                    if reserved is not None:
                        self.agentic.release_lease(reserved.lease_id)
                    LOG.warning("baseline search refused: %s", exc)
                    self.last_execution = {"executed": False, "reason": f"lease: {exc}"}
                    return False
                self.agentic.note_fallback(fallback_reason)

            coordinate = CausalCoordinate(
                pool_session_id=identity.pool_session_id,
                generation=identity.generation,
                job_fingerprint=identity.job_fingerprint,
                job_id=identity.job_id,
                toe_frame_id=plan.toe_frame_id,
                plan_id=plan.plan_id,
                lease_id=lease.lease_id,
                execution_id=f"execution:{uuid.uuid4()}",
                recovery_id=self.recovery.active_recovery_id(),
            )
            self.causal.record(
                "execution_started",
                coordinate,
                source=plan.source.value,
                requested_route=plan.executor_route,
                extranonce2=lease.extranonce2,
                nonce_start=lease.start,
                window=plan.window,
            )
            record: ExecutionRecord | None = None
            candidate = None
            outcome = PoolOutcome.NO_CANDIDATE
            try:
                header = adapter.build_header(job.job_id, lease.extranonce2, job.ntime, 0)
                target_le = job.target.to_bytes(32, "little")
                certificate = self._certify_dispatch(plan, job.job_id, header, target_le)
                if not certificate["ok"]:
                    LOG.error("dispatch refused by algebra certificate: %s", certificate["refusal"])
                    self.causal.record(
                        "dispatch_refused", coordinate, reason=certificate["refusal"]
                    )
                    self.last_execution = {
                        "executed": False,
                        "reason": f"dispatch_algebra: {certificate['refusal']}",
                    }
                    self._publish_evidence(force=True)
                    return False
                record, candidate = await asyncio.to_thread(
                    self._router_for(plan).execute_plan,
                    plan,
                    header,
                    target_le,
                    identity=identity,
                    lease=reserved.contract(),
                    is_still_fresh=lambda: self._identity_is(identity.key),
                )
                record = replace(
                    record,
                    job_id=job.job_id,
                    candidate_nonce=candidate["nonce"] if candidate is not None else None,
                    candidate_host_verified=(
                        bool(candidate["independently_rechecked"])
                        if candidate is not None
                        else None
                    ),
                    recovery_id=coordinate.recovery_id,
                )
                current = self._refresh_work_identity()
                stale = (
                    client is not self.client
                    or adapter.current_job != job
                    or current is None
                    or current.key != identity.key
                )
                if candidate is not None:
                    coordinate = coordinate.extend(
                        candidate_id="candidate:" + coordinate.execution_id.split(":", 1)[1]
                    )
                    self.causal.record("candidate_found", coordinate, nonce=candidate["nonce"])
                    if stale:
                        outcome = PoolOutcome.STALE
                    else:
                        self._last_submission_id = None
                        self._pending_correlation = coordinate.as_dict()
                        try:
                            await self.submit_candidate(
                                job_id=job.job_id,
                                extranonce2=lease.extranonce2,
                                ntime=job.ntime,
                                nonce=candidate["nonce"],
                            )
                        finally:
                            outcome = self._last_pool_outcome
                            self._pending_correlation = None
                            if self._last_submission_id is not None:
                                coordinate = coordinate.extend(
                                    submission_id=self._last_submission_id
                                )
            except Exception as exc:
                self.causal.record(
                    "execution_failed",
                    coordinate,
                    job_id=identity.job_id,
                    plan_id=plan.plan_id,
                    lease_id=lease.lease_id,
                    reason=f"{type(exc).__name__}: {exc}",
                )
                self.last_execution = {
                    "executed": False,
                    **coordinate.as_dict(),
                    "plan_id": plan.plan_id,
                    "pool_outcome": PoolOutcome.NOT_SUBMITTED.value,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
                raise
            finally:
                completed = record is not None and record.completed_work_items > 0
                self.agentic.finish_execution(lease.lease_id, scanned=completed)
                if record is not None:
                    self.governor.record(
                        hashes=record.hash_count,
                        share_target=job.target,
                        shares=int(candidate is not None),
                    )
                    self._record_execution(identity, plan, lease, record, outcome, coordinate)
            return outcome is PoolOutcome.ACCEPTED

    def _record_execution(
        self,
        identity: WorkIdentity,
        plan: SearchPlan,
        lease: LeaseRecord,
        record: ExecutionRecord,
        outcome: PoolOutcome,
        coordinate: CausalCoordinate,
    ) -> None:
        learning_record_id = (
            f"learning:{uuid.uuid4()}"
            if outcome in (PoolOutcome.ACCEPTED, PoolOutcome.REJECTED)
            else None
        )
        if learning_record_id is not None:
            coordinate = coordinate.extend(learning_record_id=learning_record_id)
        final = replace(
            record,
            pool_outcome=outcome,
            pool_accepted=int(outcome is PoolOutcome.ACCEPTED),
            pool_rejected=int(outcome is PoolOutcome.REJECTED),
            pool_stale=int(outcome is PoolOutcome.STALE),
            recovery_event=self.agentic.is_recovery_active(),
            lease_id=lease.lease_id,
            generation=identity.generation,
            extranonce2=lease.extranonce2,
            nonce_start=lease.start,
            execution_id=coordinate.execution_id,
            candidate_id=coordinate.candidate_id,
            submission_id=coordinate.submission_id,
            learning_record_id=coordinate.learning_record_id,
            job_id=identity.job_id,
            recovery_id=coordinate.recovery_id,
        )
        self.agentic.record_outcome(final)
        if outcome in (PoolOutcome.ACCEPTED, PoolOutcome.REJECTED):
            self.mining_intelligence.learn(
                accepted=outcome is PoolOutcome.ACCEPTED,
                lead=plan.policy_id,
                job_id=identity.job_id,
            )
        self.causal.record(
            "learning_observed",
            coordinate,
            applied=self.agentic.telemetry.learning_update_applied,
            pool_outcome=outcome.value,
            plan_id=plan.plan_id,
            toe_frame_id=plan.toe_frame_id,
        )
        now = time.monotonic()
        self.world.tick(now)
        self._score_forecasts(final)
        self.world.observe_execution(final)
        self._observe_recovery_effect(final)
        self._share_knowledge(now)
        self.loss.observe_execution(final, self.world, started_at=now - final.elapsed_seconds)
        idle_ms = self.agentic.telemetry.executor_idle_waiting_for_plan_ms
        self.loss.observe_idle(max(0.0, idle_ms - self._idle_seen_ms) / 1000.0)
        self._idle_seen_ms = idle_ms
        if (
            self.intelligence_memory is not None
            and now - self._memory_saved_at >= self._memory_every_s
        ):
            self._memory_saved_at = now
            try:
                self.intelligence_memory.checkpoint(self.world.export_state())
            except Exception as exc:
                LOG.warning("intelligence checkpoint failed: %s", exc)
        self.causal.record(
            "execution_finished",
            coordinate,
            completion=final.completion_state.value,
            requested_route=final.requested_route,
            executed_route=final.executed_route,
            evidence_class=final.evidence_class.value,
            hashes=final.hash_count,
            pool_outcome=outcome.value,
        )
        new_job = self._last_executed_key is not None and self._last_executed_key != identity.key
        self._last_executed_key = identity.key
        latency_ms = final.kernel_ms if final.kernel_ms > 0 else final.elapsed_seconds * 1000.0
        decision = self.tuning.evaluate(
            current_window=plan.window,
            max_window=self._window_cap(),
            kernel_latency_ms=latency_ms,
            hashes_computed=final.hash_count,
            elapsed_seconds=final.elapsed_seconds,
            new_job_observed=new_job,
            stratum_state="NEW_JOB" if new_job else "READY",
            recovery_active=self.agentic.is_recovery_active(),
        )
        if decision.action != "HOLD":
            self._tuned_window = decision.next_window
        self.last_execution = {
            "executed": True,
            **coordinate.as_dict(),
            "plan_source": final.plan_source.value,
            "plan_id": final.plan_id,
            "search_plan_id": final.search_plan_id,
            "plan_fallback_reason": final.plan_fallback_reason,
            "extranonce2": lease.extranonce2,
            "nonce_start": lease.start,
            "requested_window": plan.window,
            "attempts": final.hash_count,
            "candidate_nonce": final.candidate_nonce,
            "candidate_host_verified": final.candidate_host_verified,
            "requested_route": final.requested_route,
            "executed_route": final.executed_route,
            "route_fallback_reason": final.fallback_reason,
            "evidence_class": final.evidence_class.value,
            "truth_class": final.truth_class,
            "completion_state": final.completion_state.value,
            "toe_advice_reason": final.toe_advice_reason,
            "device_backend": final.device_backend,
            "device_name": final.device_name,
            "elapsed_seconds": final.elapsed_seconds,
            "pool_stale": final.pool_stale,
            "kernel_launch_count": final.kernel_launch_count,
            "kernel_ms": final.kernel_ms,
            "pool_outcome": outcome.value,
            "tuning_action": decision.action,
        }
        self._executions_total += 1
        if final.hash_count > 0:
            self._hash_samples.append((time.monotonic(), int(final.hash_count)))
            self._hashes_total += int(final.hash_count)
        self._shares_accepted += int(outcome is PoolOutcome.ACCEPTED)
        self._publish_evidence()
        self._publish_metrics(force=True)

    async def submit_record(self, record: VaultRecord) -> bool:
        if not self.client:
            raise ConnectionError("no active Stratum client")
        job = self.client.latest_job()
        if job is None:
            LOG.warning("dropping node %d record: no Stratum job", record.node_id)
            return False

        self._records_observed += 1
        new_job = self._last_job_id is not None and self._last_job_id != job.job_id
        self._last_job_id = job.job_id

        # Stratum is the sole authority for work identity.
        self._refresh_work_identity()

        cassini_error = self._cassini_fault(record.state)
        device_error = self._bridge.last_error() if self._bridge is not None else 0

        telemetry: dict[str, Any] = {
            "stratum_state": "NEW_JOB" if new_job else "READY",
            "new_job_observed": new_job,
            "hardware_status": "FAULT" if cassini_error or device_error else "READY",
            "device_error_code": device_error,
            "records_observed": self._records_observed,
            "record_node_id": record.node_id,
            "record_sequence": record.sequence,
        }

        try:
            context = (
                TOEContextBuilder()
                .with_job({"job_id": job.job_id, "params": tuple(job.params)})
                .with_hardware_state(record.state)
                .with_coordinates(
                    lane_id=record.node_id % LANES,
                    node_id=record.node_id,
                    sequence=record.sequence,
                    watermark=record.sequence,
                )
                .with_telemetry(telemetry)
                .build()
            )
        except TOEContextUnavailable as exc:
            LOG.error("observed context invalid; record quarantined: %s", exc)
            self.quarantined_records.add(f"node{record.node_id}:{record.sequence}")
            return False

        # Control + self-healing planes: classify the observed snapshot into
        # controller signals and an ordered recovery plan, then execute real
        # repair commands against the device before any fail-closed halt.
        record_id = f"node{record.node_id}:{record.sequence}"
        observed_ns = time.monotonic_ns()
        try:
            controller_decision = self.intelligence.evaluate(
                context=context,
                telemetry=telemetry,
                observed_at_ns=observed_ns,
            )
            plan = self.self_healing.observe(
                context=context,
                telemetry=telemetry,
                observed_at_ns=observed_ns,
                current_job_id=job.job_id,
                record_id=record_id,
                cassini_error=cassini_error,
                queue_backpressure=self._recovery_backpressure,
            )
        except TOEContextUnavailable as exc:
            LOG.error("observed control/recovery planning failed: %s", exc)
            if self._control_sink is not None:
                with contextlib.suppress(Exception):
                    self._control_sink.restart_lane(parameters={}, evidence={})
            return False
        self.last_recovery_plan = plan
        # A fresh observation is the only thing that can verify a recovery.
        self.recovery.observe(
            not cassini_error
            and not device_error
            and all(a.command == RecoveryCommand.HOLD for a in plan.actions)
        )
        self.last_control_signals = tuple(
            signal.command.value for signal in controller_decision.signals
        )
        try:
            self.recovery_queue.submit(plan)
            self._recovery_backpressure = False
        except RecoveryBackpressure as exc:
            LOG.error("recovery queue saturated; applying fail-closed backpressure: %s", exc)
            self._set_throttled(True)
            self._recovery_backpressure = True
        # Salamander gate: speculation freezes while recovery runs.
        self._sync_recovery_gate()
        if self._control_sink is not None:
            # The coordinator is the only executor of recovery plans; drain
            # the non-blocking queue and dispatch each pending plan. Signals
            # are immediate and attach to the observation that produced them.
            while True:
                try:
                    pending = self.recovery_queue.receive()
                except Empty:
                    break
                self._dispatch_observation(
                    pending,
                    controller_decision.signals if pending is plan else (),
                )
        self._sync_recovery_gate()
        self._publish_evidence()

        # TOE consumes only the real pool job and the real 64-byte vault state.
        # It supplies context/evidence; it cannot accept or reject proof. When
        # TOE is absent the coordinator proceeds only because observe_record is
        # declared in PERMITTED_WITHOUT_TOE — no fabricated evidence is
        # substituted and the chooser still sees the real candidate window.
        if self._toe_or_declared_absent("observe_record") is not None:
            try:
                self.last_toe_context = self.toe.analyse(
                    job=job,
                    state=record.state,
                    node_id=record.node_id,
                    sequence=record.sequence,
                )
            except TOEUnavailable as exc:
                LOG.warning(
                    "TOE context unavailable for record %s; continuing without it: %s",
                    record_id,
                    exc,
                )
                self.last_toe_context = None

        self.last_toe_frame = None
        if self.last_toe_context is not None:
            try:
                self.last_toe_frame = build_toe_decision_frame(self.last_toe_context)
            except TOEConsensusBoundaryError as exc:
                self._record_toe_boundary_violation(exc)
            except TOEDecisionFrameUnavailable as exc:
                LOG.warning("TOE decision frame unavailable for %s: %s", record_id, exc)

        # Feed-forward TOE wiring: convert the measured context into a causal
        # signal, apply its throttle gate, then let the chooser apply
        # face_bias to the solver's start lane. The signal is derived only
        # from the real job/vault observation; an absent or invalid signal
        # leaves the measured default contract untouched.
        toe_signal = self._build_toe_signal()
        self._apply_toe_signal(toe_signal)
        # The chooser sees the real declared candidate window for this job,
        # so its decision orchestrates the actual allocation contract.
        candidate_window = self._observed_candidate_window()
        if toe_signal is not None:
            toe_signal = replace(toe_signal, ladder=lucas_ladder_status(candidate_window))
        self.last_toe_signal = toe_signal
        decision = self.mining_intelligence.choose(
            has_job=True,
            candidate_window=candidate_window,
            budget=250_000,
            toe_signal=toe_signal,
            solver=self.solver,
        )
        self.last_mining_decision = decision
        if decision.throttle:
            self._set_throttled(True)
        toe_backend = (
            self.last_toe_context.execution_evidence.get("backend", "unknown")
            if self.last_toe_context is not None
            else "toe_absent"
        )
        LOG.info(
            "selected lane=%s reason=%s ordering=%s structure_s=%s toe_backend=%s throttled=%s",
            decision.lead,
            decision.reason,
            decision.policy.candidate_ordering,
            (
                "none"
                if decision.structure_parameter is None
                else f"{decision.structure_parameter:.3f}"
            ),
            toe_backend,
            self.work_throttled,
        )
        return await self.search_current_job()
