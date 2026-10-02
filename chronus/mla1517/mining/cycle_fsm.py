"""Guarded operational state machine for one production mining cycle.

The canonical loop is driven by the coordinator; this machine is its
explicit, evidence-emitting state model:

    STARTUP -> SCAN -> PLAN -> MINE -> VERIFY -> SUBMIT -> ACKNOWLEDGE
                -> EVALUATE -> (HEAL) -> NEXT_CYCLE -> SCAN ...

Every state declares its entry condition, the inputs/actions it performs,
the bound that keeps it finite, and the transitions allowed on success,
failure and stale evidence. Transitions are validated against the edge
table: an undeclared edge raises ``IllegalCycleTransition`` and is counted,
so nothing falls through silently. Each transition emits a durable record
through the coordinator's causal ledger and is retained in a bounded
history for telemetry.

This machine records what the real loop did; it never performs hashing,
verification, submission or recovery itself, and a transition is evidence
of the action taken, not a substitute for it.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Mapping

SCHEMA = "pythia.mining_cycle/1"
THEOREM_PROVEN = False


class MiningCycleState(StrEnum):
    STARTUP = "STARTUP"
    SCAN = "SCAN"
    PLAN = "PLAN"
    MINE = "MINE"
    VERIFY = "VERIFY"
    SUBMIT = "SUBMIT"
    ACKNOWLEDGE = "ACKNOWLEDGE"
    EVALUATE = "EVALUATE"
    HEAL = "HEAL"
    NEXT_CYCLE = "NEXT_CYCLE"
    SHUTDOWN = "SHUTDOWN"


# Declared edges — the only legal transitions. ``* -> SHUTDOWN`` is legal
# from every state and handled in ``_go``.
EDGES: dict[MiningCycleState, tuple[MiningCycleState, ...]] = {
    MiningCycleState.STARTUP: (MiningCycleState.SCAN,),
    MiningCycleState.SCAN: (
        MiningCycleState.PLAN,
        MiningCycleState.HEAL,
    ),
    MiningCycleState.PLAN: (
        MiningCycleState.MINE,
        MiningCycleState.SCAN,
        MiningCycleState.EVALUATE,
    ),
    MiningCycleState.MINE: (
        MiningCycleState.VERIFY,
        MiningCycleState.SCAN,
        MiningCycleState.EVALUATE,
        MiningCycleState.HEAL,
    ),
    MiningCycleState.VERIFY: (
        MiningCycleState.SUBMIT,
        MiningCycleState.EVALUATE,
        MiningCycleState.SCAN,
        MiningCycleState.HEAL,
    ),
    MiningCycleState.SUBMIT: (
        MiningCycleState.ACKNOWLEDGE,
        MiningCycleState.EVALUATE,
        MiningCycleState.HEAL,
    ),
    MiningCycleState.ACKNOWLEDGE: (MiningCycleState.EVALUATE,),
    MiningCycleState.EVALUATE: (
        MiningCycleState.NEXT_CYCLE,
        MiningCycleState.HEAL,
    ),
    MiningCycleState.HEAL: (MiningCycleState.NEXT_CYCLE,),
    MiningCycleState.NEXT_CYCLE: (MiningCycleState.SCAN,),
    MiningCycleState.SHUTDOWN: (),
}


@dataclass(frozen=True)
class StateSpec:
    """The declared contract of one operational state."""

    entry_condition: str
    inputs_actions: str
    bound: str
    on_success: str
    on_failure: str
    on_stale: str


# The auditable contract for each state: entry condition, what it does,
# the bound that keeps it finite, and where each evidence class leads.
STATE_SPECS: dict[MiningCycleState, StateSpec] = {
    MiningCycleState.STARTUP: StateSpec(
        entry_condition="process boot; coordinator constructed",
        inputs_actions="resolve pool endpoints, backend selection, durable stores",
        bound="no external wait",
        on_success="SCAN",
        on_failure="raises before the loop starts (SystemExit)",
        on_stale="n/a",
    ),
    MiningCycleState.SCAN: (
        StateSpec(
            entry_condition="endpoints resolved or the session/identity was lost or completed a cycle",
            inputs_actions="connect+subscribe+authorize+await job/target through the Stratum runtime state; failure retries with bounded exponential backoff across endpoints",
            bound="connect_timeout + request_timeout per attempt; reconnect backoff capped by PYTHIA_RECONNECT_MAX_S",
            on_success="PLAN (a bound work identity exists)",
            on_failure="HEAL (every endpoint failed or refused authorization; bounded backoff)",
            on_stale="SCAN (session/job invalidated by pool or reconnect)",
        )
    ),
    MiningCycleState.PLAN: (
        StateSpec(
            entry_condition="a live WorkIdentity (pool session, generation, fingerprint, target) is bound",
            inputs_actions="consume a leased agentic SearchPlan or build a leased baseline plan; the dispatch algebra certificate must pass before any hashing",
            bound="lookahead-bounded queue and nonce-lease space",
            on_success="MINE (sealed plan + executable lease + certificate)",
            on_failure="EVALUATE (dispatch refused, recorded) or SCAN (no work identity)",
            on_stale="SCAN (identity changed before dispatch)",
        )
    ),
    MiningCycleState.MINE: (
        StateSpec(
            entry_condition="certified plan, executable lease, fresh identity",
            inputs_actions="ExecutionRouter runs the leased nonce window on the selected backend with freshness re-checks between chunks",
            bound="window bounded by PYTHIA_MAX_WINDOW_SECONDS guidance and chunk caps; cancellation between chunks",
            on_success="VERIFY (an execution record exists)",
            on_failure="EVALUATE with completion_state REFUSED/DEVICE_ERROR (recorded) or HEAL on device fault",
            on_stale="EVALUATE with completion_state INVALIDATED (stale work is rejected, never submitted)",
        )
    ),
    MiningCycleState.VERIFY: (
        StateSpec(
            entry_condition="an executed window exists and produced a record",
            inputs_actions="host SHA256d recheck inside the router, proof-adapter validation (job/epoch/target/extranonce), chain-tip parent check",
            bound="local rehash only; one bounded chain-tip poll",
            on_success="SUBMIT when a proof-checked candidate exists and submission is permitted",
            on_failure="EVALUATE (no candidate, gate refusal) or HEAL (verification fault)",
            on_stale="EVALUATE with event 'stale' (candidate abandoned before write)",
        )
    ),
    MiningCycleState.SUBMIT: (
        StateSpec(
            entry_condition="proof-checked candidate, permitted submission, unique digest, Searcher lifecycle open",
            inputs_actions="single owner writes mining.submit under the submission lock after a durable begin_submission record",
            bound="request_timeout on the pool write/read",
            on_success="ACKNOWLEDGE (the write landed)",
            on_failure="HEAL (transport write failed) or EVALUATE (gate refused before any write)",
            on_stale="EVALUATE (generation changed before the write)",
        )
    ),
    MiningCycleState.ACKNOWLEDGE: (
        StateSpec(
            entry_condition="a submission was written and awaits processing",
            inputs_actions="pool response mapped to ACCEPTED/REJECTED/OUTCOME_UNKNOWN; nothing is invented on timeout",
            bound="request_timeout",
            on_success="EVALUATE (literal outcome recorded)",
            on_failure="EVALUATE (OUTCOME_UNKNOWN recorded honestly)",
            on_stale="EVALUATE (session invalidated; outcome stays unknown)",
        )
    ),
    MiningCycleState.EVALUATE: (
        StateSpec(
            entry_condition="a completed execution record (and optionally a share outcome) exists",
            inputs_actions="ExecutionRecord persisted to world model, closed-loop optimiser, tuning gate, loss ledger, learning and evidence sinks",
            bound="no network wait",
            on_success="NEXT_CYCLE",
            on_failure="HEAL when the record carries a device error",
            on_stale="NEXT_CYCLE",
        )
    ),
    MiningCycleState.HEAL: (
        StateSpec(
            entry_condition="observed failure: pool loss, authorization refusal, device error, recovery gate",
            inputs_actions="Salamander detect/classify/isolate/recover/verify under the RecoveryGovernor; bounded retries, failover, then fail closed (FAULTED)",
            bound="recovery history bounded; retry policy bounded by fail_after",
            on_success="NEXT_CYCLE (verified by a fresh healthy observation)",
            on_failure="NEXT_CYCLE with mode FAULTED recorded; escalation stays visible in telemetry",
            on_stale="NEXT_CYCLE",
        )
    ),
    MiningCycleState.NEXT_CYCLE: (
        StateSpec(
            entry_condition="the current cycle's evidence is persisted",
            inputs_actions="bookkeeping transition back to SCAN; never carries an epoch across a boundary",
            bound="no wait",
            on_success="SCAN",
            on_failure="SCAN",
            on_stale="SCAN",
        )
    ),
    MiningCycleState.SHUTDOWN: (
        StateSpec(
            entry_condition="graceful stop or fatal halt",
            inputs_actions="session/evidence persisted, client closed, tasks cancelled",
            bound="terminal",
            on_success="terminal",
            on_failure="terminal",
            on_stale="terminal",
        )
    ),
}


def _path(
    edges: Mapping["MiningCycleState", tuple["MiningCycleState", ...]],
    start: "MiningCycleState",
    goal: "MiningCycleState",
) -> tuple["MiningCycleState", ...] | None:
    """Shortest declared-edge path from ``start`` to ``goal``; None if absent."""
    frontier: list[tuple[MiningCycleState, ...]] = [(start,)]
    seen = {start}
    while frontier:
        current = frontier.pop(0)
        for nxt in edges.get(current[-1], ()):
            if nxt in seen or nxt is MiningCycleState.SHUTDOWN:
                continue
            if nxt is goal:
                return current[1:] + (goal,)
            seen.add(nxt)
            frontier.append(current + (nxt,))
    return None


class IllegalCycleTransition(RuntimeError):
    """A transition outside the declared edge table was attempted."""


@dataclass(frozen=True)
class CycleEvent:
    """One durable record of a guarded transition."""

    seq: int
    cycle_id: str
    at: float
    state: str
    previous: str
    event: str
    reason: str
    evidence: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "seq": self.seq,
            "cycle_id": self.cycle_id,
            "at": self.at,
            "from": self.previous,
            "to": self.state,
            "event": self.event,
            "reason": self.reason,
            "evidence": self.evidence,
        }


class MiningCycleLedger:
    """The guarded cycle machine the production coordinator drives.

    ``transition`` is the only way the operational state moves. It is a
    hard guard: an edge not declared in ``EDGES`` raises
    ``IllegalCycleTransition`` and increments ``illegal_attempts``. Each
    legal transition appends a durable ``CycleEvent`` (mirrored to the
    coordinator's causal ledger via ``on_event``) so the loop's history is
    reconstructible from disk.

    ``try_transition`` is the soft variant for seams where an external
    caller can legally enter mid-cycle (a direct ``submit_candidate`` call
    or the MMIO record path); a rejected soft transition is still recorded
    as evidence, never silent.
    """

    def __init__(
        self,
        *,
        history: int = 256,
        on_event: Callable[[CycleEvent], None] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if history <= 0:
            raise ValueError("history bound must be positive")
        self._state = MiningCycleState.STARTUP
        self._previous: str | None = None
        self._entered_at = clock()
        self._entered_seq = 0
        self._cycle_id = "cycle:boot"
        self._cycle_seq = 0
        self._seq = 0
        self._clock = clock
        self._on_event = on_event
        self._events: deque[CycleEvent] = deque(maxlen=history)
        self.illegal_attempts = 0
        self._emit("boot", "runtime constructed; awaiting pool lifecycle", {})

    # -- core ------------------------------------------------------------ #

    @property
    def state(self) -> MiningCycleState:
        return self._state

    def _emit(self, event: str, reason: str, evidence: Mapping[str, Any]) -> CycleEvent:
        self._seq += 1
        record = CycleEvent(
            seq=self._seq,
            cycle_id=self._cycle_id,
            at=self._clock(),
            state=self._state.value,
            previous=self._previous or "NONE",
            event=event,
            reason=reason,
            evidence=dict(evidence),
        )
        self._events.append(record)
        if self._on_event is not None:
            try:
                self._on_event(record)
            except Exception:
                # Evidence publication must never break the mining loop.
                pass
        return record

    def _go(
        self,
        to: MiningCycleState,
        *,
        event: str,
        reason: str,
        evidence: Mapping[str, Any] | None = None,
    ) -> CycleEvent:
        if self._state is MiningCycleState.SHUTDOWN:
            self.illegal_attempts += 1
            raise IllegalCycleTransition("the machine is shut down")
        if to is MiningCycleState.SHUTDOWN:
            pass  # any state may halt
        elif to not in EDGES[self._state]:
            self.illegal_attempts += 1
            raise IllegalCycleTransition(
                f"{self._state.value} -> {to.value} is not a declared edge"
            )
        if to is MiningCycleState.SCAN and self._state in (
            MiningCycleState.STARTUP,
            MiningCycleState.NEXT_CYCLE,
        ):
            self._cycle_seq += 1
            self._cycle_id = f"cycle:{self._cycle_seq}"
        self._previous = self._state.value
        self._state = to
        self._entered_at = self._clock()
        self._entered_seq = self._seq + 1
        return self._emit(event, reason, evidence or {})

    def transition(
        self,
        to: MiningCycleState,
        *,
        event: str,
        reason: str = "",
        evidence: Mapping[str, Any] | None = None,
    ) -> CycleEvent:
        """Hard transition: an undeclared edge raises and is counted."""
        return self._go(to, event=event, reason=reason, evidence=evidence)

    def try_transition(
        self,
        to: MiningCycleState,
        *,
        event: str,
        reason: str = "",
        evidence: Mapping[str, Any] | None = None,
    ) -> bool:
        """Soft transition for mid-cycle seams; refusals are still recorded."""
        try:
            self._go(to, event=event, reason=reason, evidence=evidence)
            return True
        except IllegalCycleTransition as exc:
            self._emit(
                "transition_refused",
                f"{event}: {exc}",
                {"attempted_to": to.value, **dict(evidence or {})},
            )
            return False

    def ensure(self, state: MiningCycleState, *, reason: str = "") -> bool:
        """Walk to ``state`` along declared edges (BFS, bounded depth)."""
        for _ in range(len(MiningCycleState)):
            if self._state is state:
                return True
            path = _path(EDGES, self._state, state)
            if not path:
                self._emit(
                    "advance_refused",
                    f"cannot reach {state.value} from {self._state.value}: {reason}",
                    {},
                )
                return False
            self._go(path[0], event="advance", reason=reason)
        self._emit(
            "advance_refused",
            f"path to {state.value} exceeded state count: {reason}",
            {},
        )
        return False

    def halt(self, reason: str = "shutdown") -> None:
        """Terminal transition; legal from any state, once."""
        if self._state is MiningCycleState.SHUTDOWN:
            return
        self._go(MiningCycleState.SHUTDOWN, event="shutdown", reason=reason)

    # -- introspection --------------------------------------------------- #

    def snapshot(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "state": self._state.value,
            "cycle_id": self._cycle_id,
            "cycle_seq": self._cycle_seq,
            "entered_at": self._entered_at,
            "transitions": self._seq,
            "illegal_attempts": self.illegal_attempts,
            "spec": {
                state.value: {
                    "entry_condition": spec.entry_condition,
                    "inputs_actions": spec.inputs_actions,
                    "bound": spec.bound,
                    "on_success": spec.on_success,
                    "on_failure": spec.on_failure,
                    "on_stale": spec.on_stale,
                }
                for state, spec in STATE_SPECS.items()
            },
            "recent": [event.as_dict() for event in list(self._events)[-16:]],
            "theorem_proven": False,
        }
