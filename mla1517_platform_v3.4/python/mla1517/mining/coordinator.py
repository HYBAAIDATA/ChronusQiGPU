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
import os
import struct
import time
import uuid
from dataclasses import asdict, replace
from queue import Empty
from typing import Any, Mapping

from mla1517.hardware import MMIOBridge, VaultRecord
from manifold_pool_coordinator import CURRENT_HOT_STATE_FORMAT, ManifoldPoolCoordinator

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
from .execution_router import NONCE_ORDER_M32, ExecutionRouter
from .recovery_authority import RecoveryGovernor, RecoveryRecord
from .nonce_lease import LeaseConflict, LeaseExhausted, LeaseRecord
from .search_plan import (
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
from .loss_ledger import LossLedger
from .operating_policy import OperatingPolicy, PolicyContext
from .policy_audit import PolicyAuditor
from .world_model import MiningWorldModel
from .toe_adapter import TOEUnavailable, TOEMiningAdapter
from .toe_context import TOEContextBuilder, TOEContextUnavailable
from .toe_signal import TOECausalSignal, build_toe_signal, lucas_ladder_status

LOG = logging.getLogger("mla1517.stratum.intelligence")

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
_BASELINE_POLICY = "baseline_fallback"
_EVIDENCE_MIN_INTERVAL_S = 0.5


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
        self._policy_mode = os.getenv("PYTHIA_OPERATING_POLICY", "model").strip().lower()
        try:
            self._max_window_seconds = float(os.getenv("PYTHIA_MAX_WINDOW_SECONDS", "2.0"))
        except ValueError:
            self._max_window_seconds = 2.0
        self._idle_seen_ms = 0.0
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
        self.execution_hasher = hasher if hasher is not None else CpuReferenceHasher()
        self.causal = CausalLedger(path=causal_log_path)
        self.recovery = RecoveryGovernor(on_event=self._on_recovery_event)
        self._evidence_sink: Any = None
        self._evidence_published_at = 0.0
        self._pending_correlation: dict[str, Any] | None = None
        self._precompute_task: asyncio.Task | None = None
        self._precompute_wake = asyncio.Event()
        self._agentic_state_path: str | None = None
        self._identity_block_logged: set[str] = set()
        self._last_pool_outcome = PoolOutcome.NOT_SUBMITTED
        self._last_submission_id: str | None = None
        self._last_executed_key: tuple[str, int, str] | None = None
        self.last_execution: dict[str, Any] | None = None
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

    def set_agentic_state_path(self, path: str) -> None:
        """Configure where the agentic controller persists its learned policy."""
        self._agentic_state_path = path

    async def connect_with_failover(self):
        client = await super().connect_with_failover()
        # The handshake's first mining.notify arrives before self.client is set.
        self._refresh_work_identity()
        self._precompute_wake.set()
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

    def _on_recovery_event(self, kind: str, record: RecoveryRecord) -> None:
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
            "intelligence": self.intelligence_snapshot(),
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
        return identity

    def _set_throttled(self, throttled: bool) -> None:
        self.work_throttled = bool(throttled)
        if throttled:
            self._throttled_at = time.monotonic()

    def _throttle_holds(self) -> bool:
        return (
            self.work_throttled
            and time.monotonic() - self._throttled_at < self.throttle_probe_s
        )

    async def before_hardware_poll(self) -> bool:
        if not self.submit_enabled:
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
                if pending and pending["block_candidate"] and (
                    pending["outcome"] is None or pending["outcome"] is True
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
        except (ValueError, TypeError) as exc:
            LOG.warning(
                "TOE signal conversion failed; continuing without causal signal: %s",
                exc,
            )
            return None

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
        if not self.submit_enabled or self.session.state != "SEARCHING" or self.work_throttled:
            return 0
        identity = self._refresh_work_identity()
        if identity is None:
            return 0
        built = 0
        for _ in range(self.agentic.plans_needed()):
            plan = self._build_plan(identity)
            if plan is None or not self.agentic.submit_plan(plan):
                break
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
        decision = self.operating_policy.decide(
            PolicyContext(
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

        return ExecutionRouter(
            self.execution_hasher, cpu_sweep, nonce_order=lambda _plan: NONCE_ORDER_M32
        )

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
            evidence_refs={"lane_order_source": order_source},
            created_at=time.monotonic(),
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
                },
                created_at=time.monotonic(),
                plan_id=plan_id,
            )
        except ValueError as exc:
            self.agentic.release_lease(plan_id)
            LOG.warning("precomputed plan rejected by contract: %s", exc)
            return None

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
            return False
        proof = self.client.proof_adapter.validate_candidate(
            job_id=job_id, extranonce2=extranonce2, ntime=ntime, nonce=nonce
        )
        if not self.submit_enabled:
            return False
        if self.chain_observer is None:
            raise RuntimeError("live submission requires a Bitcoin chain observer")
        tip = await asyncio.to_thread(self.chain_observer.tip)
        if proof.header[4:36][::-1].hex() != tip["block_hash"]:
            LOG.warning("candidate parent differs from verified chain tip")
            return False
        if self.session.already_submitted(proof.digest[::-1].hex()):
            LOG.warning("share already submitted; refusing a duplicate mining.submit")
            return False
        decision = self.mining_intelligence.choose(
            has_job=True,
            candidate_window=self._observed_candidate_window(),
            budget=250_000,
        )
        self.last_mining_decision = decision
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
        self.mining_intelligence.learn(accepted=result, lead=decision.lead, job_id=job_id)
        return result

    async def search_current_job(self) -> bool:
        """Execute one leased window through the Execution Router.

        A precomputed agentic SearchPlan runs when one is ready; otherwise a
        leased, labelled baseline SearchPlan does. Returns True only for a
        literal pool ACCEPTED response.
        """
        async with self._search_lock:
            if (
                not self.submit_enabled
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
            plan = self.agentic.consume_plan(timeout_ms=0)
            fallback_reason = (
                None
                if plan is not None
                else self.agentic.telemetry.last_consume_miss_reason or "queue_empty"
            )
            reserved: LeaseRecord | None = None
            lease: LeaseRecord | None = None
            if plan is not None:
                reserved = self.agentic.lease(plan.plan_id)
                try:
                    lease = self.agentic.begin_execution(plan)
                except LeaseConflict:
                    plan, reserved, fallback_reason = None, None, "stale_plan"
            self._precompute_wake.set()
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
            outcome = PoolOutcome.NO_CANDIDATE
            try:
                header = adapter.build_header(job.job_id, lease.extranonce2, job.ntime, 0)
                record, candidate = await asyncio.to_thread(
                    self._router_for(plan).execute_plan,
                    plan,
                    header,
                    job.target.to_bytes(32, "little"),
                    identity=identity,
                    lease=reserved.contract(),
                    is_still_fresh=lambda: self._identity_is(identity.key),
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
                        outcome = PoolOutcome.NOT_SUBMITTED
                    else:
                        self._last_submission_id = None
                        self._pending_correlation = {
                            k: v for k, v in coordinate.as_dict().items() if k != "recovery_id"
                        }
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
            finally:
                completed = record is not None and record.completed_work_items > 0
                self.agentic.finish_execution(lease.lease_id, scanned=completed)
                if record is not None:
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
        final = replace(
            record,
            pool_outcome=outcome,
            pool_accepted=int(outcome is PoolOutcome.ACCEPTED),
            pool_rejected=int(outcome is PoolOutcome.REJECTED),
            recovery_event=self.agentic.is_recovery_active(),
            lease_id=lease.lease_id,
            generation=identity.generation,
            extranonce2=lease.extranonce2,
            nonce_start=lease.start,
            execution_id=coordinate.execution_id,
            candidate_id=coordinate.candidate_id,
            submission_id=coordinate.submission_id,
        )
        self.agentic.record_outcome(final)
        now = time.monotonic()
        self.world.tick(now)
        self.world.observe_execution(final)
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
            "plan_fallback_reason": final.plan_fallback_reason,
            "extranonce2": lease.extranonce2,
            "nonce_start": lease.start,
            "requested_window": plan.window,
            "attempts": final.hash_count,
            "requested_route": final.requested_route,
            "executed_route": final.executed_route,
            "route_fallback_reason": final.fallback_reason,
            "evidence_class": final.evidence_class.value,
            "completion_state": final.completion_state.value,
            "device_name": final.device_name,
            "kernel_launch_count": final.kernel_launch_count,
            "kernel_ms": final.kernel_ms,
            "pool_outcome": outcome.value,
            "tuning_action": decision.action,
        }
        self._publish_evidence()

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
