"""Salamander recovery authority: one governor, one writer.

``SelfHealingAgent`` diagnoses and *proposes*. This governor is the only
component that decides and dispatches recovery inside the miner, and it
yields lane-mask actuation to the external Salamander supervisor whenever
that supervisor is alive, so the MMIO lane mask never has two writers.

Every recovery carries a ``recovery_id`` and a verified lifecycle:

    PROPOSED → DISPATCHED → ACKED → VERIFIED        (healthy post-observation)
             ↘ DEFERRED (Salamander actuates) ↗
                                   ↘ FAILED        (dispatch error, NACK, or
                                                    still unhealthy after N looks)

Planning a recovery is never evidence that it worked; only a later healthy
observation verifies it.
"""

from __future__ import annotations

import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Deque, Iterable

FREEZING_MODES = frozenset({"FREEZE_SPECULATION", "RECOVERING", "PAUSED", "FAULTED"})
SALAMANDER_MODES = FREEZING_MODES | {"NORMAL", "DE_RATE"}
LANE_MASK_COMMANDS = frozenset({"SEVER_LANE", "FLUSH_LANE"})


class RecoveryState(StrEnum):
    PROPOSED = "PROPOSED"
    DEFERRED = "DEFERRED"
    DISPATCHED = "DISPATCHED"
    ACKED = "ACKED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"


_OPEN = frozenset(
    {RecoveryState.PROPOSED, RecoveryState.DEFERRED, RecoveryState.DISPATCHED, RecoveryState.ACKED}
)


@dataclass
class RecoveryRecord:
    recovery_id: str
    origin: str
    commands: tuple[str, ...]
    reason: str
    state: RecoveryState = RecoveryState.PROPOSED
    proposed_at: float = field(default_factory=time.time)
    dispatched: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)
    ack: bool | None = None
    unhealthy_observations: int = 0
    closed_at: float | None = None
    failure: str | None = None

    @property
    def open(self) -> bool:
        return self.state in _OPEN

    def as_dict(self) -> dict[str, Any]:
        return {
            "recovery_id": self.recovery_id,
            "origin": self.origin,
            "commands": list(self.commands),
            "reason": self.reason,
            "state": self.state.value,
            "proposed_at": self.proposed_at,
            "dispatched": list(self.dispatched),
            "deferred": list(self.deferred),
            "ack": self.ack,
            "unhealthy_observations": self.unhealthy_observations,
            "closed_at": self.closed_at,
            "failure": self.failure,
        }


class RecoveryGovernor:
    def __init__(
        self,
        *,
        fail_after: int = 3,
        salamander_ttl_s: float = 10.0,
        history: int = 64,
        clock: Callable[[], float] = time.monotonic,
        on_event: Callable[[str, RecoveryRecord], None] | None = None,
    ) -> None:
        if fail_after <= 0 or salamander_ttl_s <= 0:
            raise ValueError("governor bounds must be positive")
        self._fail_after = fail_after
        self._ttl = salamander_ttl_s
        self._clock = clock
        self._on_event = on_event
        self._records: dict[str, RecoveryRecord] = {}
        self._closed: Deque[RecoveryRecord] = deque(maxlen=history)
        self._external_mode = "NORMAL"
        self._external_recovery_id: str | None = None
        self._external_seen: float | None = None
        self._faulted = False

    # ---------------------------------------------------------------- mode
    def salamander_alive(self) -> bool:
        return self._external_seen is not None and self._clock() - self._external_seen < self._ttl

    def external_mode(self, mode: str, recovery_id: str | None = None) -> RecoveryRecord | None:
        """Consume a mode report from the external Salamander supervisor."""
        if mode not in SALAMANDER_MODES:
            raise ValueError(f"unknown Salamander mode {mode!r}")
        self._external_seen = self._clock()
        self._external_mode = mode
        record = None
        if mode in FREEZING_MODES and recovery_id:
            record = self._records.get(recovery_id)
            if record is None:
                record = RecoveryRecord(recovery_id, "salamander", (mode,), "supervisor report")
                record.state = RecoveryState.DISPATCHED
                self._records[recovery_id] = record
                self._emit("recovery_external", record)
            self._external_recovery_id = recovery_id
        elif mode not in FREEZING_MODES and self._external_recovery_id:
            record = self._records.get(self._external_recovery_id)
            if record is not None and record.open:
                self._close(record, RecoveryState.VERIFIED)
            self._external_recovery_id = None
        return record

    @property
    def mode(self) -> str:
        if self.salamander_alive() and self._external_mode in FREEZING_MODES:
            return self._external_mode
        if any(r.open for r in self._records.values()):
            return "RECOVERING"
        if self._faulted:
            return "FAULTED"
        if self.salamander_alive():
            return self._external_mode
        return "NORMAL"

    @property
    def freezes_speculation(self) -> bool:
        return self.mode in FREEZING_MODES

    def active_recovery_id(self) -> str | None:
        open_ids = [r.recovery_id for r in self._records.values() if r.open]
        return open_ids[-1] if open_ids else None

    # ----------------------------------------------------------- lifecycle
    def propose(self, commands: Iterable[str], reason: str) -> RecoveryRecord | None:
        actionable = tuple(c for c in commands if c != "HOLD")
        if not actionable:
            return None
        record = RecoveryRecord(
            f"recovery:{uuid.uuid4()}", "self_healing_agent", actionable, reason
        )
        self._records[record.recovery_id] = record
        self._emit("recovery_proposed", record)
        return record

    def defers(self, command: str) -> bool:
        """Lane-mask writes belong to Salamander while it is alive."""
        return command in LANE_MASK_COMMANDS and self.salamander_alive()

    def dispatch(
        self,
        record: RecoveryRecord,
        steps: Iterable[tuple[str, Callable[[], str | None]]],
        *,
        ack: Callable[[], bool | None] | None = None,
    ) -> RecoveryRecord:
        """Run ``(command, action)`` steps; lane-mask steps defer to Salamander."""
        for command, action in steps:
            if command == "HOLD":
                continue
            if self.defers(command):
                record.deferred.append(command)
                continue
            try:
                routed = action()
            except Exception as exc:
                record.failure = f"{command}: {exc}"
                self._close(record, RecoveryState.FAILED)
                raise
            if routed is not None:
                record.dispatched.append(routed)
        if not record.dispatched:
            record.state = RecoveryState.DEFERRED if record.deferred else RecoveryState.DISPATCHED
            self._emit("recovery_" + record.state.value.lower(), record)
            return record
        record.state = RecoveryState.DISPATCHED
        self._emit("recovery_dispatched", record)
        if ack is not None and any(c in LANE_MASK_COMMANDS for c in record.dispatched):
            record.ack = ack()
            if record.ack is False:
                record.failure = "supervisor commit was not acknowledged"
                self._close(record, RecoveryState.FAILED)
                return record
            if record.ack is True:
                record.state = RecoveryState.ACKED
                self._emit("recovery_acked", record)
        return record

    def observe(self, healthy: bool) -> list[RecoveryRecord]:
        """Advance open internal recoveries from a fresh post-action observation."""
        closed = []
        for record in list(self._records.values()):
            if not record.open or record.origin != "self_healing_agent":
                continue
            if record.state is RecoveryState.PROPOSED:
                continue
            if healthy:
                self._close(record, RecoveryState.VERIFIED)
                closed.append(record)
                continue
            record.unhealthy_observations += 1
            if record.unhealthy_observations >= self._fail_after:
                record.failure = f"unhealthy after {record.unhealthy_observations} observations"
                self._close(record, RecoveryState.FAILED)
                closed.append(record)
        if healthy:
            self._faulted = False
        return closed

    def _close(self, record: RecoveryRecord, state: RecoveryState) -> None:
        record.state = state
        record.closed_at = time.time()
        if state is RecoveryState.FAILED:
            self._faulted = True
        self._records.pop(record.recovery_id, None)
        self._closed.append(record)
        self._emit("recovery_" + state.value.lower(), record)

    def _emit(self, kind: str, record: RecoveryRecord) -> None:
        if self._on_event is not None:
            self._on_event(kind, record)

    def snapshot(self) -> dict[str, Any]:
        return {
            "authority": "salamander",
            "mode": self.mode,
            "salamander_supervisor_alive": self.salamander_alive(),
            "external_mode": self._external_mode if self.salamander_alive() else None,
            "open": [r.as_dict() for r in self._records.values()],
            "recent": [r.as_dict() for r in list(self._closed)[-8:]],
        }
