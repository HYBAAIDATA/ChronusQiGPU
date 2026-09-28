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
import logging
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
from .nonce_lease import LeaseConflict, LeaseExhausted, LeaseRecord
from .search_plan import (
    CompletionState,
    ExecutionRecord,
    PlanSource,
    PoolOutcome,
    SearchPlan,
    WorkIdentity,
)
from .solver import M32SearchSolver, SolveResult
from .stratum_adapter import StratumAdapterError
from .tuning_gate import TuningGate
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
# Salamander governor modes (interface owned by the Salamander lead).
_FREEZING_SALAMANDER_MODES = frozenset({"FREEZE_SPECULATION", "RECOVERING", "PAUSED", "FAULTED"})
_SALAMANDER_MODES = _FREEZING_SALAMANDER_MODES | {"NORMAL", "DE_RATE"}


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
        self._salamander_mode = "NORMAL"
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

    def apply_salamander_mode(self, mode: str) -> None:
        """Consume the Salamander governor mode; speculation freezes while it heals."""
        if mode not in _SALAMANDER_MODES:
            raise ValueError(f"unknown Salamander mode {mode!r}")
        self._salamander_mode = mode
        self._sync_recovery_gate()

    def _sync_recovery_gate(self) -> None:
        self.agentic.set_recovery_active(
            self._recovery_backpressure or self._salamander_mode in _FREEZING_SALAMANDER_MODES
        )
        self._precompute_wake.set()

    def agentic_status(self) -> dict[str, Any]:
        decision = self.tuning.last_decision
        return {
            "agentic": self.agentic.snapshot(),
            "last_execution": self.last_execution,
            "tuning": asdict(decision) if decision is not None else None,
            "salamander_mode": self._salamander_mode,
        }

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
            self._precompute_wake.set()
        return identity

    def _set_throttled(self, throttled: bool) -> None:
        self.work_throttled = bool(throttled)

    async def before_hardware_poll(self) -> bool:
        if not self.submit_enabled:
            return not self.work_throttled
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
        return self.session.state == "SEARCHING" and not self.work_throttled

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
        """Execute one recovery plan plus controller signals against the sink.

        Mirrors CanonicalMiningCoordinator.route_observation: recovery actions
        run before controller signals, identical ABI commands are de-duplicated
        within the observation, and HOLD clears the dispatch throttle.
        """
        from coordinator import CoordinatorControlRouter, _freeze

        router = CoordinatorControlRouter()
        dispatched: list[str] = []
        seen: set[tuple[str, Any]] = set()
        for action in plan.actions:
            command = action.command.value
            if command == RecoveryCommand.HOLD.value:
                self._set_throttled(False)
                continue
            key = (command, _freeze(action.parameters))
            if key in seen:
                continue
            routed = router.dispatch_recovery(self._control_sink, action)
            if routed is not None:
                seen.add(key)
                dispatched.append(routed)
        for signal in signals:
            command = signal.command.value
            if command == ControlCommand.HOLD.value:
                continue
            key = (command, _freeze(signal.parameters))
            if key in seen:
                continue
            routed = router.dispatch_signal(self._control_sink, signal)
            if routed is not None:
                seen.add(key)
                dispatched.append(routed)
        return dispatched

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
            built += 1
        return built

    def _next_window(self) -> int:
        from lucas.core import lucas

        cap = lucas(self.session.rung)
        return max(1, min(self._tuned_window or cap, cap))

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
                executor_route="cpu_reference",
                policy_id=decision.lead if decision is not None else "flat_exhaustive",
                evidence_refs={
                    "lane_order_source": order_source,
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
        """Execute one leased window: a precomputed SearchPlan, else the baseline.

        Returns True only for a literal pool ACCEPTED response.
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
            lease: LeaseRecord | None = None
            if plan is not None:
                try:
                    lease = self.agentic.begin_execution(plan)
                except LeaseConflict:
                    plan, fallback_reason = None, "stale_plan"
            self._precompute_wake.set()
            if plan is None:
                window = self._next_window()
                try:
                    lease = self.agentic.begin_fallback(window, adapter.next_extranonce2)
                except (LeaseConflict, LeaseExhausted, StratumAdapterError) as exc:
                    LOG.warning("baseline search refused: %s", exc)
                    self.last_execution = {"executed": False, "reason": f"lease: {exc}"}
                    return False
                self.agentic.note_fallback(fallback_reason)
                order, _source = self._lane_order_for(lease.start)
                budget, policy_id = window, _BASELINE_POLICY
                source = PlanSource.BASELINE_FALLBACK
                preferred_face = self.solver.get_lane_start_offset()
            else:
                order, budget, policy_id = plan.lane_order, plan.window, plan.policy_id
                source, preferred_face = PlanSource.AGENTIC_PRECOMPUTED, plan.preferred_face

            result: SolveResult | None = None
            outcome = PoolOutcome.NO_CANDIDATE
            execution_id = f"execution:{uuid.uuid4()}"
            submission_id: str | None = None
            try:
                header = adapter.build_header(job.job_id, lease.extranonce2, job.ntime, 0)
                result = await asyncio.to_thread(
                    self.solver.scan_header,
                    header=header,
                    target=job.target,
                    budget=budget,
                    lane_order=order,
                    scale_index=self.session.rung,
                    start_nonce=lease.start,
                )
                current = self._refresh_work_identity()
                stale = (
                    client is not self.client
                    or adapter.current_job != job
                    or current is None
                    or current.key != identity.key
                )
                if result.valid and stale:
                    outcome = PoolOutcome.NOT_SUBMITTED
                elif result.valid:
                    self._last_submission_id = None
                    try:
                        await self.submit_candidate(
                            job_id=job.job_id,
                            extranonce2=lease.extranonce2,
                            ntime=job.ntime,
                            nonce=result.found_nonce,
                        )
                    finally:
                        outcome = self._last_pool_outcome
                        submission_id = self._last_submission_id
            finally:
                self.agentic.finish_execution(lease.lease_id, scanned=result is not None)
                if result is not None:
                    self._record_execution(
                        identity=identity,
                        plan=plan,
                        lease=lease,
                        source=source,
                        fallback_reason=fallback_reason,
                        policy_id=policy_id,
                        order=tuple(order),
                        preferred_face=preferred_face,
                        budget=budget,
                        result=result,
                        outcome=outcome,
                        execution_id=execution_id,
                        submission_id=submission_id,
                    )
            return outcome is PoolOutcome.ACCEPTED

    def _record_execution(
        self,
        *,
        identity: WorkIdentity,
        plan: SearchPlan | None,
        lease: LeaseRecord,
        source: PlanSource,
        fallback_reason: str | None,
        policy_id: str,
        order: tuple[int, ...],
        preferred_face: int,
        budget: int,
        result: SolveResult,
        outcome: PoolOutcome,
        execution_id: str,
        submission_id: str | None,
    ) -> None:
        from lucas.core import lucas

        candidate_id = f"candidate:{execution_id.split(':', 1)[1]}" if result.valid else None

        record = ExecutionRecord(
            plan_id=plan.plan_id if plan is not None else None,
            job_fingerprint=identity.job_fingerprint,
            policy_id=policy_id,
            planned_window=budget,
            actual_window=result.attempts,
            device_used="cpu_reference",
            hash_count=result.attempts,
            elapsed_seconds=result.elapsed_seconds,
            kernel_ms=result.elapsed_seconds * 1000.0,
            temperature_c=None,
            locally_valid_shares=1 if result.valid else 0,
            pool_accepted=1 if outcome is PoolOutcome.ACCEPTED else 0,
            pool_rejected=1 if outcome is PoolOutcome.REJECTED else 0,
            pool_stale=0,
            recovery_event=self.agentic.is_recovery_active(),
            lane_order=order,
            preferred_face=preferred_face,
            plan_source=source,
            plan_fallback_reason=(
                fallback_reason if source is PlanSource.BASELINE_FALLBACK else None
            ),
            pool_outcome=outcome,
            lease_id=lease.lease_id,
            generation=identity.generation,
            extranonce2=lease.extranonce2,
            nonce_start=lease.start,
            requested_route="cpu_reference",
            executed_route="cpu_reference",
            completion_state=(
                CompletionState.EARLY_WINNER if result.valid else CompletionState.COMPLETE
            ),
            execution_id=execution_id,
            candidate_id=candidate_id,
            submission_id=submission_id,
        )
        self.agentic.record_outcome(record)
        new_job = self._last_executed_key is not None and self._last_executed_key != identity.key
        self._last_executed_key = identity.key
        decision = self.tuning.evaluate(
            current_window=budget,
            max_window=lucas(self.session.rung),
            kernel_latency_ms=result.elapsed_seconds * 1000.0,
            hashes_computed=result.attempts,
            elapsed_seconds=result.elapsed_seconds,
            new_job_observed=new_job,
            stratum_state="NEW_JOB" if new_job else "READY",
            recovery_active=self.agentic.is_recovery_active(),
        )
        if decision.action != "HOLD":
            self._tuned_window = decision.next_window
        self.last_execution = {
            "executed": True,
            "pool_session_id": identity.pool_session_id,
            "job_fingerprint": identity.job_fingerprint,
            "execution_id": execution_id,
            "candidate_id": candidate_id,
            "submission_id": submission_id,
            "plan_source": source.value,
            "plan_id": record.plan_id,
            "plan_fallback_reason": record.plan_fallback_reason,
            "lease_id": lease.lease_id,
            "generation": identity.generation,
            "extranonce2": lease.extranonce2,
            "nonce_start": lease.start,
            "requested_window": budget,
            "attempts": result.attempts,
            "pool_outcome": outcome.value,
            "tuning_action": decision.action,
        }

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
