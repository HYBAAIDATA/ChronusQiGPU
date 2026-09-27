"""Canonical observed-data coordinator and control-plane router.

The coordinator is the only composition point between the live Stratum proof
boundary, measured execution, TOE context, persistence, and the emergent
control plane.  Intelligence produces deterministic signals; the injected
control sink is responsible for routing those signals to real hardware,
Stratum, or PRIME-DB adapters.  No sink is silently replaced with a mock.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from mla1517.mining.intelligence_controller import (
    ControlCommand,
    ControlSignal,
    ControllerDecision,
    IntelligenceController,
)
from mla1517.mining.persistence import PersistedRecord, PrimeDBPersistence
from mla1517.mining.session import MiningSession
from mla1517.mining.self_healing_agent import (
    RecoveryAction,
    RecoveryCommand,
    RecoveryPlan,
    SelfHealingAgent,
)
from mla1517.mining.toe_context import TOEContext, TOEContextBuilder


def _freeze(value: Any) -> Any:
    """Return a deterministic hashable representation for ABI parameters."""
    if isinstance(value, Mapping):
        return tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze(item) for item in value))
    try:
        hash(value)
    except TypeError:
        return repr(value)
    return value


class CoordinatorUnavailable(RuntimeError):
    """The canonical coordinator cannot establish required observed state."""


class ControlSink(Protocol):
    """Execution ABI for actual hardware, scheduler, Stratum, and persistence.

    Implementations must be non-blocking at the call boundary.  They may queue
    work for their own event loop, but they must not report success unless the
    requested routing was accepted by the real subsystem.
    """

    def flush_lane(
        self, *, job_id: str, parameters: Mapping[str, Any], evidence: Mapping[str, Any]
    ) -> None: ...

    def resize_workgroup(
        self, *, parameters: Mapping[str, Any], evidence: Mapping[str, Any]
    ) -> None: ...

    def prune_window(
        self, *, parameters: Mapping[str, Any], evidence: Mapping[str, Any]
    ) -> None: ...

    def sever_lane(self, *, parameters: Mapping[str, Any], evidence: Mapping[str, Any]) -> None: ...

    def restart_lane(
        self, *, parameters: Mapping[str, Any], evidence: Mapping[str, Any]
    ) -> None: ...

    def apply_backpressure(
        self, *, parameters: Mapping[str, Any], evidence: Mapping[str, Any]
    ) -> None: ...

    def quarantine_record(
        self, *, parameters: Mapping[str, Any], evidence: Mapping[str, Any]
    ) -> None: ...

    def flush_persistence_ring(
        self, *, parameters: Mapping[str, Any], evidence: Mapping[str, Any]
    ) -> None: ...

    def reset_cursor(
        self, *, parameters: Mapping[str, Any], evidence: Mapping[str, Any]
    ) -> None: ...


@dataclass(frozen=True)
class CandidateRequest:
    job_id: str
    extranonce2: str
    ntime: str
    nonce: int | str
    hardware_state: bytes
    lane_id: int
    node_id: int
    sequence: int
    watermark: int
    telemetry: Mapping[str, Any]


@dataclass(frozen=True)
class CoordinatorResult:
    proof_checked: bool
    proof_digest: str
    persisted_record_id: str
    pool_accepted: bool | None
    toe_context: TOEContext


@dataclass(frozen=True)
class ObservationRoutingResult:
    """Evidence that one observed snapshot was routed to the control sink."""

    controller_decision: ControllerDecision
    recovery_plan: RecoveryPlan
    dispatched_commands: tuple[str, ...]


class CoordinatorControlRouter:
    """Route explicit ABI commands without inventing an execution fallback."""

    @staticmethod
    def _method(sink: ControlSink, name: str) -> Any:
        method = getattr(sink, name, None)
        if not callable(method):
            raise CoordinatorUnavailable(f"control sink does not implement {name}()")
        return method

    def dispatch_signal(self, sink: ControlSink, signal: ControlSignal) -> str | None:
        if signal.command == ControlCommand.HOLD:
            return None
        methods = {
            ControlCommand.FLUSH_LANE: "flush_lane",
            ControlCommand.RESIZE_WORKGROUP: "resize_workgroup",
            ControlCommand.PRUNE_WINDOW: "prune_window",
            ControlCommand.PAUSE: "apply_backpressure",
        }
        method_name = methods.get(signal.command)
        if method_name is None:
            raise CoordinatorUnavailable(f"unsupported control command {signal.command}")
        self._method(sink, method_name)(
            **({"job_id": signal.job_id} if signal.command == ControlCommand.FLUSH_LANE else {}),
            parameters=signal.parameters,
            evidence=signal.evidence,
        )
        return signal.command.value

    def dispatch_recovery(self, sink: ControlSink, action: RecoveryAction) -> str | None:
        if action.command == RecoveryCommand.HOLD:
            return None
        methods = {
            RecoveryCommand.SEVER_LANE: "sever_lane",
            RecoveryCommand.FLUSH_LANE: "flush_lane",
            RecoveryCommand.RESTART_LANE: "restart_lane",
            RecoveryCommand.APPLY_BACKPRESSURE: "apply_backpressure",
            RecoveryCommand.QUARANTINE_RECORD: "quarantine_record",
            RecoveryCommand.FLUSH_PERSISTENCE_RING: "flush_persistence_ring",
            RecoveryCommand.RESET_CURSOR: "reset_cursor",
        }
        method_name = methods.get(action.command)
        if method_name is None:
            raise CoordinatorUnavailable(f"unsupported recovery command {action.command}")
        kwargs: dict[str, Any] = {
            "parameters": action.parameters,
            "evidence": action.evidence,
        }
        if action.command == RecoveryCommand.FLUSH_LANE:
            kwargs["job_id"] = action.job_id
        self._method(sink, method_name)(**kwargs)
        return action.command.value


class CanonicalMiningCoordinator:
    """Compose proof validation, observed context, persistence, and control."""

    def __init__(
        self,
        pool_coordinator: Any,
        persistence: PrimeDBPersistence,
        *,
        intelligence: IntelligenceController | None = None,
        self_healing: SelfHealingAgent | None = None,
        control_sink: ControlSink | None = None,
    ) -> None:
        # One authoritative session: the injected pool coordinator must be the
        # lifecycle-bound intelligent coordinator, not the raw transport.
        if not isinstance(getattr(pool_coordinator, "session", None), MiningSession):
            raise TypeError(
                "pool_coordinator must expose a MiningSession; "
                "wire IntelligentPoolCoordinator, not the bare transport"
            )
        self.pool = pool_coordinator
        self.persistence = persistence
        self.intelligence = intelligence or IntelligenceController()
        self.self_healing = self_healing or SelfHealingAgent()
        self.control_sink = control_sink
        self.control_router = CoordinatorControlRouter()

    def _context(self, request: CandidateRequest, job: Any) -> TOEContext:
        return (
            TOEContextBuilder()
            .with_job(
                {
                    "job_id": str(getattr(job, "job_id", request.job_id)),
                    "params": tuple(getattr(job, "params", ())),
                }
            )
            .with_hardware_state(request.hardware_state)
            .with_coordinates(
                lane_id=request.lane_id,
                node_id=request.node_id,
                sequence=request.sequence,
                watermark=request.watermark,
            )
            .with_telemetry(request.telemetry)
            .build()
        )

    def route_observation(
        self,
        *,
        context: TOEContext,
        telemetry: Mapping[str, Any],
        observed_at_ns: int,
        current_job_id: str | None = None,
        record_id: str | None = None,
        cassini_error: str | None = None,
        queue_backpressure: bool = False,
    ) -> ObservationRoutingResult:
        """Evaluate and route one observed snapshot without blocking.

        Recovery actions are dispatched before controller signals so stale work
        is severed before a lane flush.  Identical ABI commands with identical
        parameters are de-duplicated within this observation; distinct intents
        remain observable at the sink.
        """
        decision = self.intelligence.evaluate(
            context=context,
            telemetry=telemetry,
            observed_at_ns=observed_at_ns,
        )
        recovery = self.self_healing.observe(
            context=context,
            telemetry=telemetry,
            observed_at_ns=observed_at_ns,
            current_job_id=current_job_id,
            record_id=record_id,
            cassini_error=cassini_error,
            queue_backpressure=queue_backpressure,
        )
        commands: list[str] = []
        if self.control_sink is None:
            non_hold = [
                action.command.value
                for action in recovery.actions
                if action.command != RecoveryCommand.HOLD
            ] + [
                signal.command.value
                for signal in decision.signals
                if signal.command != ControlCommand.HOLD
            ]
            if non_hold:
                raise CoordinatorUnavailable(
                    "observed control action requires an injected real control sink"
                )
            return ObservationRoutingResult(decision, recovery, ())

        seen: set[tuple[str, Any]] = set()
        for action in recovery.actions:
            command = action.command.value
            key = (command, _freeze(action.parameters))
            if key in seen or command == RecoveryCommand.HOLD.value:
                continue
            routed = self.control_router.dispatch_recovery(self.control_sink, action)
            if routed is not None:
                seen.add(key)
                commands.append(routed)
        for signal in decision.signals:
            command = signal.command.value
            key = (command, _freeze(signal.parameters))
            if key in seen or command == ControlCommand.HOLD.value:
                continue
            routed = self.control_router.dispatch_signal(self.control_sink, signal)
            if routed is not None:
                seen.add(key)
                commands.append(routed)
        return ObservationRoutingResult(decision, recovery, tuple(commands))

    async def submit_observed_candidate(self, request: CandidateRequest) -> CoordinatorResult:
        client = getattr(self.pool, "client", None)
        adapter = getattr(client, "proof_adapter", None)
        job = getattr(client, "latest_job", lambda: None)()
        if client is None or adapter is None or job is None:
            raise CoordinatorUnavailable("live Stratum client, proof adapter, and job are required")
        context = self._context(request, job)
        proof = adapter.validate_candidate(
            job_id=request.job_id,
            extranonce2=request.extranonce2,
            ntime=request.ntime,
            nonce=request.nonce,
        )
        record: PersistedRecord = self.persistence.append(
            state=request.hardware_state,
            sequence=request.sequence,
            watermark=request.watermark,
            lane_id=request.lane_id,
        )
        accepted = await self.pool.submit_candidate(
            job_id=request.job_id,
            extranonce2=request.extranonce2,
            ntime=request.ntime,
            nonce=request.nonce,
        )
        return CoordinatorResult(
            proof_checked=True,
            proof_digest=proof.digest.hex(),
            persisted_record_id=record.record_id,
            pool_accepted=accepted if bool(getattr(self.pool, "submit_enabled", False)) else None,
            toe_context=context,
        )
