"""Observed-only, non-blocking recovery planning for the PYTHIA control plane.

The self-healing agent does not own a device, socket, hash function, or
persistence connection.  It converts one immutable TOE/telemetry observation
into an ordered recovery plan for the coordinator.  The coordinator is the
only layer allowed to execute the plan against OpenCL, Stratum, or PRIME-DB.

This separation is intentional: planning a recovery action is not evidence
that the action succeeded, and no recovery action can validate or submit a
share.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from queue import Full, Queue
from types import MappingProxyType
from typing import Any, Mapping

from .intelligence_controller import ControlSignal
from .toe_context import TOEContext, TOEContextUnavailable


class RecoveryCommand(StrEnum):
    """Stable ABI consumed by the Phase 4 coordinator executor."""

    HOLD = "HOLD"
    SEVER_LANE = "SEVER_LANE"
    FLUSH_LANE = "FLUSH_LANE"
    RESTART_LANE = "RESTART_LANE"
    APPLY_BACKPRESSURE = "APPLY_BACKPRESSURE"
    QUARANTINE_RECORD = "QUARANTINE_RECORD"
    FLUSH_PERSISTENCE_RING = "FLUSH_PERSISTENCE_RING"
    RESET_CURSOR = "RESET_CURSOR"


@dataclass(frozen=True)
class RecoveryAction:
    """One deterministic, non-blocking recovery instruction."""

    command: RecoveryCommand
    reason: str
    observed_at_ns: int
    source_sequence: int
    job_id: str
    parameters: Mapping[str, Any]
    evidence: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.observed_at_ns <= 0 or self.source_sequence < 0:
            raise ValueError("recovery action requires valid observed coordinates")
        if not self.job_id or not self.reason:
            raise ValueError("recovery action requires job id and reason")
        object.__setattr__(self, "parameters", MappingProxyType(dict(self.parameters)))
        object.__setattr__(self, "evidence", MappingProxyType(dict(self.evidence)))


@dataclass(frozen=True)
class RecoveryPlan:
    """An immutable batch that can be queued without blocking the coordinator."""

    actions: tuple[RecoveryAction, ...]
    observation: Mapping[str, Any]
    non_blocking: bool = True

    def __post_init__(self) -> None:
        if not self.actions:
            raise ValueError("recovery plan must contain at least one action")
        if not self.non_blocking:
            raise ValueError("recovery plans must be non-blocking")
        object.__setattr__(self, "observation", MappingProxyType(dict(self.observation)))


class RecoveryBackpressure(RuntimeError):
    """A recovery queue is full and must not silently discard a plan."""


class NonBlockingRecoveryQueue:
    """Bounded, put-nowait queue for handing plans to the coordinator.

    ``submit`` never waits for hardware, a network socket, or a database.  A
    full queue is reported explicitly so the coordinator can apply its own
    fail-closed backpressure policy rather than dropping a recovery action.
    """

    def __init__(self, max_pending: int = 64) -> None:
        if max_pending <= 0:
            raise ValueError("max_pending must be positive")
        self._queue: Queue[RecoveryPlan] = Queue(maxsize=max_pending)

    def submit(self, plan: RecoveryPlan) -> None:
        try:
            self._queue.put_nowait(plan)
        except Full as exc:
            raise RecoveryBackpressure(
                "recovery queue is full; coordinator must apply backpressure"
            ) from exc

    def receive(self) -> RecoveryPlan:
        return self._queue.get_nowait()


class SelfHealingAgent:
    """Classify observed failures into ordered, side-effect-free recovery plans."""

    def __init__(self, *, default_latency_bound_ms: float = 100.0) -> None:
        if default_latency_bound_ms <= 0:
            raise ValueError("default latency bound must be positive")
        self.default_latency_bound_ms = float(default_latency_bound_ms)
        self._last_job_id: str | None = None
        self._last_sequence = -1

    @staticmethod
    def _number(snapshot: Mapping[str, Any], key: str, default: float) -> float:
        value = snapshot.get(key, default)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TOEContextUnavailable(f"telemetry field {key!r} must be numeric")
        return float(value)

    @staticmethod
    def _add_once(
        actions: list[RecoveryAction],
        *,
        command: RecoveryCommand,
        reason: str,
        context: TOEContext,
        observed_at_ns: int,
        parameters: Mapping[str, Any],
        evidence: Mapping[str, Any],
    ) -> None:
        if any(action.command == command for action in actions):
            return
        actions.append(
            RecoveryAction(
                command=command,
                reason=reason,
                observed_at_ns=observed_at_ns,
                source_sequence=context.sequence,
                job_id=str(context.stratum_job["job_id"]),
                parameters=parameters,
                evidence=evidence,
            )
        )

    def observe(
        self,
        *,
        context: TOEContext,
        telemetry: Mapping[str, Any],
        observed_at_ns: int,
        current_job_id: str | None = None,
        record_id: str | None = None,
        cassini_error: str | None = None,
        queue_backpressure: bool = False,
    ) -> RecoveryPlan:
        """Return recovery actions from one observed snapshot.

        The optional error and queue arguments are facts reported by the
        persistence layer; they are not synthesized by this agent.  Missing
        record identity on a Cassini failure is itself a fail-closed error.
        """
        if context.synthetic:
            raise TOEContextUnavailable("synthetic context cannot drive recovery")
        if observed_at_ns <= 0:
            raise ValueError("observed_at_ns must be positive")
        if context.sequence < self._last_sequence:
            raise TOEContextUnavailable("observed sequence moved backwards")
        if not isinstance(telemetry, Mapping) or not telemetry:
            raise TOEContextUnavailable("read-only telemetry snapshot is required")
        if not isinstance(queue_backpressure, bool):
            raise TOEContextUnavailable("queue_backpressure must be an observed boolean")
        job_id = str(context.stratum_job.get("job_id", ""))
        if not job_id:
            raise TOEContextUnavailable("live Stratum job id is required")
        if current_job_id is not None and current_job_id != job_id:
            raise TOEContextUnavailable("current job identity disagrees with TOE context")
        if cassini_error is not None and (not isinstance(cassini_error, str) or not cassini_error):
            raise TOEContextUnavailable("Cassini failure must include an observed reason")
        if record_id is not None and (not isinstance(record_id, str) or not record_id):
            raise TOEContextUnavailable("record_id must be a non-empty observed identifier")
        if cassini_error is not None and record_id is None:
            raise TOEContextUnavailable(
                "Cassini failure cannot be quarantined without the observed record id"
            )

        snapshot = dict(telemetry)
        latency = self._number(snapshot, "kernel_latency_ms", 0.0)
        latency_bound = self._number(
            snapshot, "kernel_latency_bound_ms", self.default_latency_bound_ms
        )
        if latency < 0 or latency_bound <= 0:
            raise TOEContextUnavailable("kernel latency observation is out of range")
        temperature = self._number(snapshot, "temperature_c", 0.0)
        thermal_limit = self._number(snapshot, "thermal_limit_c", 85.0)
        if thermal_limit <= 0:
            raise TOEContextUnavailable("thermal limit observation is out of range")
        stratum_state = snapshot.get("stratum_state", "READY")
        hardware_status = snapshot.get("hardware_status", "READY")
        if not isinstance(stratum_state, str) or not isinstance(hardware_status, str):
            raise TOEContextUnavailable("state observations must be strings")

        new_job = bool(snapshot.get("new_job_observed", False))
        if self._last_job_id is not None and self._last_job_id != job_id:
            new_job = True
        stale_job = new_job or stratum_state in {"NEW_JOB", "STALE"}
        hang_risk = latency > latency_bound * 2.0 or hardware_status in {"HANG_RISK", "HUNG"}
        evidence = {
            "kernel_latency_ms": latency,
            "kernel_latency_bound_ms": latency_bound,
            "temperature_c": temperature,
            "thermal_limit_c": thermal_limit,
            "stratum_state": stratum_state,
            "hardware_status": hardware_status,
            "new_job_observed": new_job,
            "cassini_error": cassini_error,
            "queue_backpressure": queue_backpressure,
        }
        actions: list[RecoveryAction] = []

        if stale_job:
            self._add_once(
                actions,
                command=RecoveryCommand.SEVER_LANE,
                reason="observed Stratum job transition requires stale-work severance",
                context=context,
                observed_at_ns=observed_at_ns,
                parameters={"stale_job_id": job_id},
                evidence=evidence,
            )
            self._add_once(
                actions,
                command=RecoveryCommand.FLUSH_LANE,
                reason="flush lane before dispatching the observed live job",
                context=context,
                observed_at_ns=observed_at_ns,
                parameters={"job_id": job_id},
                evidence=evidence,
            )

        if hang_risk:
            self._add_once(
                actions,
                command=RecoveryCommand.SEVER_LANE,
                reason="observed hardware latency/status indicates hang risk",
                context=context,
                observed_at_ns=observed_at_ns,
                parameters={"acknowledge_inflight_work": True},
                evidence=evidence,
            )
            self._add_once(
                actions,
                command=RecoveryCommand.FLUSH_LANE,
                reason="flush the lane before hardware restart",
                context=context,
                observed_at_ns=observed_at_ns,
                parameters={"preserve_proof_state": True},
                evidence=evidence,
            )
            self._add_once(
                actions,
                command=RecoveryCommand.RESTART_LANE,
                reason="restart lane after observed hang-risk isolation",
                context=context,
                observed_at_ns=observed_at_ns,
                parameters={"fail_closed": True},
                evidence=evidence,
            )

        if cassini_error is not None:
            self._add_once(
                actions,
                command=RecoveryCommand.QUARANTINE_RECORD,
                reason="observed Cassini seal failure requires record quarantine",
                context=context,
                observed_at_ns=observed_at_ns,
                parameters={"record_id": record_id, "error": cassini_error},
                evidence=evidence,
            )
            self._add_once(
                actions,
                command=RecoveryCommand.FLUSH_PERSISTENCE_RING,
                reason="flush persistence ring without silently dropping records",
                context=context,
                observed_at_ns=observed_at_ns,
                parameters={"preserve_records": True, "drop_records": False},
                evidence=evidence,
            )
            self._add_once(
                actions,
                command=RecoveryCommand.RESET_CURSOR,
                reason="reset PRIME-DB cursor after quarantining corrupt state",
                context=context,
                observed_at_ns=observed_at_ns,
                parameters={"record_id": record_id},
                evidence=evidence,
            )

        if queue_backpressure:
            self._add_once(
                actions,
                command=RecoveryCommand.APPLY_BACKPRESSURE,
                reason="observed persistence backpressure requires fail-closed admission",
                context=context,
                observed_at_ns=observed_at_ns,
                parameters={"drop_records": False, "pause_new_records": True},
                evidence=evidence,
            )
            self._add_once(
                actions,
                command=RecoveryCommand.FLUSH_PERSISTENCE_RING,
                reason="drain persistence work under explicit backpressure",
                context=context,
                observed_at_ns=observed_at_ns,
                parameters={"preserve_records": True, "drop_records": False},
                evidence=evidence,
            )
            self._add_once(
                actions,
                command=RecoveryCommand.RESET_CURSOR,
                reason="recover PRIME-DB cursor after observed queue pressure",
                context=context,
                observed_at_ns=observed_at_ns,
                parameters={"recovery": "cursor_recovery"},
                evidence=evidence,
            )

        if not actions:
            self._add_once(
                actions,
                command=RecoveryCommand.HOLD,
                reason="observed state does not require recovery",
                context=context,
                observed_at_ns=observed_at_ns,
                parameters={},
                evidence=evidence,
            )

        self._last_job_id = job_id
        self._last_sequence = context.sequence
        return RecoveryPlan(actions=tuple(actions), observation=context.observation())

    def plan_from_control_signal(
        self,
        *,
        context: TOEContext,
        signal: ControlSignal,
    ) -> RecoveryPlan:
        """Translate a controller flush signal without inventing observations."""
        if signal.command.value != "FLUSH_LANE":
            raise ValueError("only observed FLUSH_LANE signals are recoverable here")
        if signal.job_id != str(context.stratum_job["job_id"]):
            raise TOEContextUnavailable("control signal job does not match TOE context")
        action = RecoveryAction(
            command=RecoveryCommand.FLUSH_LANE,
            reason=signal.reason,
            observed_at_ns=signal.observed_at_ns,
            source_sequence=signal.source_sequence,
            job_id=signal.job_id,
            parameters=signal.parameters,
            evidence=signal.evidence,
        )
        return RecoveryPlan(actions=(action,), observation=context.observation())
