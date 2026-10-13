"""Empirical State Controller — deterministic agent over an append-only ledger.

The agent is a strict deterministic state machine, not a learned model.
"Training" means accumulating an immutable JSONL ledger of physical
interventions and their verified outcomes; "thinking" is a deterministic
scan of that ledger for causal support before an action is executed.

Boundaries:
  - YAML policy (``agent_policy.yml``) is the declarative rulebook: ladder
    rungs, Salamander limits, Stratum endpoints. Read once at boot.
  - JSONL ledger is the experience: one flat JSON object per tick,
    append-only, never rewritten.
  - Veto gates are physical/cryptographic facts: Salamander thermal and
    lane limits, and Stratum share acceptance. The agent cannot override
    them — it can only refuse to act.

No floating-point weights, no gradient descent, no projected performance.
An action executes only when the ledger contains causal evidence that the
same action, in a comparable state, was previously SUPPORTED.

LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
inline below. MUST NOT import from any sibling algorithm.
Substrate route: mining
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import logging
import os
import time
from typing import Any, Callable, Dict, List, Optional

import yaml

logger = logging.getLogger("Intelligence.empirical_state_controller")


class AgentAction(str, Enum):
    SCALE_UP = "SCALE_UP"
    SCALE_DOWN = "SCALE_DOWN"
    DWELL = "DWELL"
    FAILOVER = "FAILOVER"


class CausalStatus(str, Enum):
    SUPPORTED = "SUPPORTED"
    UNSUPPORTED = "UNSUPPORTED"  # no causal evidence in ledger — refused
    VETO_SALAMANDER_TEMP = "VETO_SALAMANDER_TEMP"
    VETO_SALAMANDER_LANES = "VETO_SALAMANDER_LANES"
    VETO_STRATUM_REJECTED = "VETO_STRATUM_REJECTED"
    VETO_LADDER = "VETO_LADDER"  # target off the declared ladder


@dataclass(frozen=True)
class AgentPolicy:
    """Immutable governance boundary loaded from agent_policy.yml."""

    mode: str
    ladder: tuple
    max_temp_celsius: float
    min_active_lanes: int
    stratum_primary: str
    stratum_failover: str
    max_rejected_shares_per_window: int

    @classmethod
    def load(cls, path: str) -> "AgentPolicy":
        with open(path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
        gov = raw["agent_governance"]
        sal = gov["salamander_limits"]
        strat = gov["stratum_endpoints"]
        return cls(
            mode=str(gov["mode"]),
            ladder=tuple(int(r) for r in gov["lucas_pisot_ladder"]),
            max_temp_celsius=float(sal["max_temp_celsius"]),
            min_active_lanes=int(sal["min_active_lanes"]),
            stratum_primary=str(strat["primary"]),
            stratum_failover=str(strat["failover"]),
            max_rejected_shares_per_window=int(
                strat["max_rejected_shares_per_window"]
            ),
        )


@dataclass(frozen=True)
class AgentState:
    """Measured physical state at decision time — facts, not estimates."""

    temp_celsius: float
    active_lanes: int
    current_rung: int
    rejected_shares_in_window: int = 0


class EmpiricalLedger:
    """Append-only JSONL ledger of interventions and verified outcomes.

    The ledger is the agent's entire memory of the physical world. Entries
    are written once and never mutated; ``query`` is the causal scan the
    controller performs before acting.
    """

    def __init__(self, path: str) -> None:
        self.path = path
        self._entries: Optional[List[Dict[str, Any]]] = None

    def append(
        self,
        *,
        action: AgentAction,
        target_rung: Optional[int],
        state: AgentState,
        outcome: Dict[str, int],
        causal_status: CausalStatus,
        timestamp: Optional[float] = None,
    ) -> Dict[str, Any]:
        entry = {
            "timestamp": time.time() if timestamp is None else float(timestamp),
            "action": action.value,
            "target_rung": target_rung,
            "state": {
                "temp": state.temp_celsius,
                "lanes": state.active_lanes,
                "rung": state.current_rung,
            },
            "outcome": {
                "accepted": int(outcome.get("accepted", 0)),
                "rejected": int(outcome.get("rejected", 0)),
            },
            "causal_status": causal_status.value,
        }
        os.makedirs(os.path.dirname(os.path.abspath(self.path)) or ".", exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
        if self._entries is not None:
            self._entries.append(entry)
        return entry

    def _load(self) -> List[Dict[str, Any]]:
        if self._entries is None:
            entries: List[Dict[str, Any]] = []
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if line:
                            entries.append(json.loads(line))
            self._entries = entries
        return self._entries

    def query(self, action: AgentAction, target_rung: Optional[int]) -> List[Dict[str, Any]]:
        """All ledger entries for this (action, target_rung) pair."""
        return [
            e
            for e in self._load()
            if e["action"] == action.value and e["target_rung"] == target_rung
        ]

    def entries(self) -> List[Dict[str, Any]]:
        return list(self._load())


@dataclass(frozen=True)
class Decision:
    """The result of evaluating a proposed action."""

    action: AgentAction
    target_rung: Optional[int]
    status: CausalStatus
    execute: bool
    reason: str


class CommissionedSCM:
    """Deterministic state controller gated by physics and evidence.

    Evaluation order is fixed:
      1. Salamander vetoes (temperature, active lanes) — physical limits.
      2. Stratum veto (rejected shares in the current window exceed the
         policy bound) — cryptographic acceptance.
      3. Ladder legality (scale actions must land on a declared rung).
      4. Causal support — the ledger must contain a prior SUPPORTED entry
         for the same (action, target_rung); DWELL is always permitted and
         FAILOVER is permitted when the Stratum veto fired.

    ``strict_empirical`` mode refuses any action lacking prior causal
    support; the refusal is itself recorded, so the ledger grows evidence
    even when nothing executes.
    """

    def __init__(
        self,
        policy: AgentPolicy,
        ledger: EmpiricalLedger,
        execute: Optional[Callable[[AgentAction, Optional[int]], Dict[str, int]]] = None,
    ) -> None:
        if policy.mode != "strict_empirical":
            raise ValueError(f"unsupported governance mode: {policy.mode!r}")
        self.policy = policy
        self.ledger = ledger
        # ``execute`` performs the physical intervention and returns the
        # measured outcome {accepted, rejected}. Default is a no-op that
        # reports zero — callers must inject the real actuator.
        self._execute = execute or (lambda _a, _r: {"accepted": 0, "rejected": 0})

    def next_rung(self, current: int, direction: int) -> Optional[int]:
        """Adjacent declared rung in the ladder, or None at the boundary."""
        ladder = list(self.policy.ladder)
        if current not in ladder:
            return ladder[0] if direction > 0 else None
        idx = ladder.index(current) + direction
        return ladder[idx] if 0 <= idx < len(ladder) else None

    def evaluate(
        self, action: AgentAction, target_rung: Optional[int], state: AgentState
    ) -> Decision:
        if state.temp_celsius > self.policy.max_temp_celsius:
            return Decision(action, target_rung, CausalStatus.VETO_SALAMANDER_TEMP,
                            False, "temperature exceeds policy ceiling")
        if state.active_lanes < self.policy.min_active_lanes:
            return Decision(action, target_rung, CausalStatus.VETO_SALAMANDER_LANES,
                            False, "active lanes below policy floor")

        stratum_veto = (
            state.rejected_shares_in_window
            > self.policy.max_rejected_shares_per_window
        )
        if stratum_veto and action is not AgentAction.FAILOVER:
            return Decision(action, target_rung, CausalStatus.VETO_STRATUM_REJECTED,
                            False, "pool rejected shares in current window")

        if action in (AgentAction.SCALE_UP, AgentAction.SCALE_DOWN):
            if target_rung not in self.policy.ladder:
                return Decision(action, target_rung, CausalStatus.VETO_LADDER,
                                False, "target rung not on the declared ladder")
            if target_rung == state.current_rung:
                return Decision(action, target_rung, CausalStatus.UNSUPPORTED,
                                False, "scale action targets the current rung")

        if action is AgentAction.DWELL:
            return Decision(action, state.current_rung, CausalStatus.SUPPORTED,
                            True, "dwell requires no causal evidence")
        if action is AgentAction.FAILOVER:
            status = CausalStatus.SUPPORTED if stratum_veto else CausalStatus.UNSUPPORTED
            return Decision(action, None, status, stratum_veto,
                            "stratum veto active — failover commissioned"
                            if stratum_veto else "no stratum veto — failover not commissioned")

        # SCALE_* — strict empirical gate: prior causal evidence required.
        history = self.ledger.query(action, target_rung)
        vetoes = [e for e in history if e["causal_status"].startswith("VETO")]
        if vetoes:
            last = vetoes[-1]
            return Decision(action, target_rung, CausalStatus[last["causal_status"]],
                            False, f"ledger veto: {last['causal_status']}")
        if any(e["causal_status"] == CausalStatus.SUPPORTED.value for e in history):
            return Decision(action, target_rung, CausalStatus.SUPPORTED,
                            True, "prior SUPPORTED outcome in ledger")
        return Decision(action, target_rung, CausalStatus.UNSUPPORTED,
                        False, "no causal evidence for this action")

    def step(self, proposed: AgentAction, state: AgentState) -> Decision:
        """Evaluate one proposal, execute if commissioned, record to ledger."""
        target: Optional[int] = state.current_rung
        if proposed is AgentAction.SCALE_UP:
            target = self.next_rung(state.current_rung, +1)
        elif proposed is AgentAction.SCALE_DOWN:
            target = self.next_rung(state.current_rung, -1)
        elif proposed is AgentAction.FAILOVER:
            target = None

        if proposed in (AgentAction.SCALE_UP, AgentAction.SCALE_DOWN) and target is None:
            decision = Decision(proposed, None, CausalStatus.VETO_LADDER,
                                False, "ladder boundary reached")
            self.ledger.append(action=proposed, target_rung=None, state=state,
                               outcome={}, causal_status=decision.status)
            return decision

        decision = self.evaluate(proposed, target, state)
        outcome = self._execute(proposed, target) if decision.execute else {}
        self.ledger.append(
            action=proposed,
            target_rung=decision.target_rung,
            state=state,
            outcome=outcome,
            causal_status=decision.status,
        )
        return decision
