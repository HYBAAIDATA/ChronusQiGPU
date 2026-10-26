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
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Callable, Deque, Iterable, Mapping

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
    target: str = "pythia.mining.runtime"
    authorizations: list[dict[str, Any]] = field(default_factory=list)

    @property
    def open(self) -> bool:
        return self.state in _OPEN

    def as_dict(self) -> dict[str, Any]:
        return {
            "recovery_id": self.recovery_id,
            "origin": self.origin,
            "commands": list(self.commands),
            "reason": self.reason,
            "target": self.target,
            "state": self.state.value,
            "proposed_at": self.proposed_at,
            "dispatched": list(self.dispatched),
            "deferred": list(self.deferred),
            "ack": self.ack,
            "unhealthy_observations": self.unhealthy_observations,
            "closed_at": self.closed_at,
            "failure": self.failure,
            "authorizations": [dict(item) for item in self.authorizations],
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
        recovery_authorizer: Callable[
            [RecoveryRecord, str, str], Mapping[str, Any]
        ] | None = None,
        require_authorization: bool = False,
        recovery_target: str = "pythia.mining.runtime",
    ) -> None:
        if fail_after <= 0 or salamander_ttl_s <= 0:
            raise ValueError("governor bounds must be positive")
        if require_authorization and not callable(recovery_authorizer):
            raise ValueError("required recovery authorization has no authorizer")
        if not str(recovery_target).strip():
            raise ValueError("recovery target is required")
        self._dispatch_lock = threading.RLock()
        self._dispatching: set[str] = set()
        self._fail_after = fail_after
        self._ttl = salamander_ttl_s
        self._clock = clock
        self._on_event = on_event
        self._recovery_authorizer = recovery_authorizer
        self._require_authorization = bool(require_authorization)
        self._recovery_target = str(recovery_target).strip()
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
                record = RecoveryRecord(
                    recovery_id,
                    "salamander",
                    (mode,),
                    "supervisor report",
                    target=self._recovery_target,
                )
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
            f"recovery:{uuid.uuid4()}",
            "self_healing_agent",
            actionable,
            reason,
            target=self._recovery_target,
        )
        self._records[record.recovery_id] = record
        self._emit("recovery_proposed", record)
        return record

    def defers(self, command: str) -> bool:
        """Lane-mask writes belong to Salamander while it is alive."""
        return command in LANE_MASK_COMMANDS and self.salamander_alive()

    def _authorize_dispatch(self, record: RecoveryRecord, command: str) -> None:
        """Require a bound AL HARAS decision before a real recovery side effect."""
        if self._recovery_authorizer is None:
            if self._require_authorization:
                raise PermissionError("AL HARAS recovery authorization unavailable")
            return
        try:
            verdict = dict(
                self._recovery_authorizer(record, str(command), str(record.target))
            )
        except Exception as exc:
            raise PermissionError(
                f"AL HARAS recovery authorization unavailable:{type(exc).__name__}"
            ) from exc
        evidence_id = (
            verdict.get("authorization_evidence_id")
            or verdict.get("evidence_id")
        )
        record.authorizations.append(
            {
                "command": str(command),
                "target": str(record.target),
                "allowed": verdict.get("allowed") is True,
                "reason": verdict.get("reason"),
                "evidence_id": evidence_id,
                "version_id": verdict.get("authorization_version_id"),
                "policy_version": verdict.get("policy_version"),
            }
        )
        if verdict.get("allowed") is not True:
            reason = str(verdict.get("reason") or "AL_HARAS_DENIED")
            raise PermissionError(f"AL HARAS recovery authorization denied:{reason}")
        if self._require_authorization and not evidence_id:
            raise PermissionError("AL HARAS recovery authorization has no evidence identity")

    def dispatch(
        self,
        record: RecoveryRecord,
        steps: Iterable[tuple[str, Callable[[], str | None]]],
        *,
        ack: Callable[[], bool | None] | None = None,
    ) -> RecoveryRecord:
        """Dispatch one owned proposal once, including reentrant/concurrent callers.

        A deferred or failed proposal is not retried implicitly: a fresh proposal
        and authorization are required. An ACK exception is failed evidence, not
        permission to verify the action on a later healthy observation.
        """
        with self._dispatch_lock:
            if self._records.get(record.recovery_id) is not record:
                raise ValueError("recovery record is not an active owned proposal")
            if record.state is not RecoveryState.PROPOSED:
                raise ValueError("recovery proposal has already been dispatched")
            # Claim before invoking iterable/user callbacks; recursive dispatch
            # must not enter the side-effect path a second time.
            record.state = RecoveryState.DISPATCHED
            self._dispatching.add(record.recovery_id)
            phase = "prepare dispatch"
            try:
                prepared = list(steps)
                for command, action in prepared:
                    if command != "HOLD" and command not in record.commands:
                        raise ValueError("dispatch command was not proposed")
                    if not callable(action):
                        raise ValueError("dispatch action must be callable")
                for command, action in prepared:
                    phase = command
                    if command == "HOLD":
                        continue
                    if self.defers(command):
                        record.deferred.append(command)
                        continue
                    self._authorize_dispatch(record, command)
                    routed = action()
                    if routed is not None:
                        record.dispatched.append(routed)
                if not record.dispatched:
                    record.state = (
                        RecoveryState.DEFERRED if record.deferred else RecoveryState.DISPATCHED
                    )
                    self._emit("recovery_" + record.state.value.lower(), record)
                    return record
                self._emit("recovery_dispatched", record)
                if ack is not None and any(c in LANE_MASK_COMMANDS for c in record.dispatched):
                    phase = "supervisor acknowledgement"
                    record.ack = ack()
                    if record.ack is False:
                        record.failure = "supervisor commit was not acknowledged"
                        self._close(record, RecoveryState.FAILED)
                        return record
                    if record.ack is True:
                        record.state = RecoveryState.ACKED
                        self._emit("recovery_acked", record)
                return record
            except Exception as exc:
                record.failure = f"{phase}: {exc}"
                if record.open:
                    self._close(record, RecoveryState.FAILED)
                raise
            finally:
                self._dispatching.discard(record.recovery_id)

    def observe(self, healthy: bool, *, recovery_id: str | None = None) -> list[RecoveryRecord]:
        """Advance open internal recoveries from a fresh post-action observation."""
        closed = []
        for record in list(self._records.values()):
            if recovery_id is not None and record.recovery_id != recovery_id:
                continue
            if not record.open or record.origin != "self_healing_agent":
                continue
            if (record.state is RecoveryState.PROPOSED
                    or record.recovery_id in self._dispatching):
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
        if healthy and recovery_id is None:
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
        open_records = list(self._records.values())
        return {
            "authority": "salamander",
            "mode": self.mode,
            "salamander_supervisor_alive": self.salamander_alive(),
            "external_mode": self._external_mode if self.salamander_alive() else None,
            # The circuit state the operator sees: whether speculation is
            # frozen and which recovery owns it. False means the ledger is
            # clear — not guessed, derived from the declared mode.
            "freezes_speculation": self.mode in FREEZING_MODES,
            "faulted": self._faulted,
            "active_recovery_id": open_records[0].recovery_id if open_records else None,
            "open": [r.as_dict() for r in open_records],
            "recent": [r.as_dict() for r in list(self._closed)[-8:]],
        }
