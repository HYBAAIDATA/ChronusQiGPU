"""PYTHIA Agentic Mining Workflow — deterministic orchestration loop.

Rule 7 (Strict Honest Measurement): the agent cannot hallucinate, guess, or
use probabilistic weights. Every tick is a fixed pipeline:

    MEASURE  — read the physical state (temperature, active lanes, current
               ladder rung, rejected-share count) from a real telemetry
               source. If no source is bound the tick fails closed.
    PROPOSE  — a deterministic function of the measured state only:
               rejections above the policy bound or thermal pressure ->
               SCALE_DOWN; a fully accepted window with ladder headroom ->
               SCALE_UP; otherwise DWELL. No weights, no sampling.
    QUERY    — CommissionedSCM scans the JSONL ledger for causal precedent
               on the proposed (action, target_rung): a prior veto or a
               zero-acceptance outcome in history rejects the proposal.
    VETO     — Salamander limits and Stratum acceptance from the YAML
               policy are hard boundaries checked on the live measurement.
    ACTUATE  — execute via an injected actuator (OpenCL Lucas-Pisot scale,
               Stratum failover). Without a real actuator the agent refuses
               to claim an intervention.
    APPEND   — the exact transition lands in empirical_ledger.jsonl.

"Training" is the ledger itself: intelligence is deterministic search over
recorded physical precedent.

LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
inline below. MUST NOT import from any sibling algorithm.
Substrate route: mining
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from typing import Dict, Optional, Protocol

_REPO = os.path.dirname(os.path.abspath(__file__))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from Intelligence.empirical_state_controller import (
    AgentAction,
    AgentPolicy,
    AgentState,
    CommissionedSCM,
    Decision,
    EmpiricalLedger,
)

logger = logging.getLogger("pythia_agent")

DEFAULT_POLICY_PATH = os.path.join(_REPO, "agent_policy.yml")
DEFAULT_LEDGER_PATH = os.path.join(_REPO, "empirical_ledger.jsonl")


class TelemetrySource(Protocol):
    """Measured physical state provider. Returns None when measurement is
    impossible — the agent must fail closed, never fabricate a state."""

    def measure(self) -> Optional[AgentState]: ...


class Actuator(Protocol):
    """Physical intervention executor. Returns the measured pool outcome
    {accepted, rejected} after the action lands."""

    def actuate(self, action: AgentAction, target_rung: Optional[int]) -> Dict[str, int]: ...


class PythiaAgent:
    """Deterministic mining-workflow controller.

    Wires a TelemetrySource and an Actuator around CommissionedSCM. The
    agent owns no state beyond its current-rung bookkeeping; all memory of
    consequence lives in the append-only ledger.
    """

    def __init__(
        self,
        policy: AgentPolicy,
        ledger: EmpiricalLedger,
        telemetry: TelemetrySource,
        actuator: Optional[Actuator] = None,
    ) -> None:
        self.policy = policy
        self.ledger = ledger
        self.telemetry = telemetry
        self.actuator = actuator
        self._scm = CommissionedSCM(policy, ledger, execute=self._actuate)

    def _actuate(self, action: AgentAction, target_rung: Optional[int]) -> Dict[str, int]:
        if self.actuator is None:
            return {"accepted": 0, "rejected": 0}
        result = self.actuator.actuate(action, target_rung)
        return {
            "accepted": int(result.get("accepted", 0)),
            "rejected": int(result.get("rejected", 0)),
        }

    def propose(self, state: AgentState) -> AgentAction:
        """Deterministic proposal from the measured state only.

        - Rejections in the window, or temperature within 5 C of the
          ceiling -> SCALE_DOWN (back off the physical edge).
        - Zero rejections with a healthy thermal margin and ladder headroom
          -> SCALE_UP.
        - Otherwise DWELL.
        """
        if state.rejected_shares_in_window > self.policy.max_rejected_shares_per_window:
            return AgentAction.SCALE_DOWN
        thermal_margin = self.policy.max_temp_celsius - state.temp_celsius
        if thermal_margin <= 5.0:
            return AgentAction.SCALE_DOWN
        if self._scm.next_rung(state.current_rung, +1) is not None:
            return AgentAction.SCALE_UP
        return AgentAction.DWELL

    def tick(self) -> Optional[Decision]:
        """One full MEASURE -> PROPOSE -> QUERY -> VETO -> ACTUATE -> APPEND.

        Returns None (and records nothing) when telemetry is unavailable:
        acting on an unmeasured state would violate Rule 7.
        """
        state = self.telemetry.measure()
        if state is None:
            logger.warning("tick skipped: telemetry unavailable — fail closed")
            return None
        if self.actuator is None:
            logger.warning("tick skipped: no actuator bound — fail closed")
            return None
        proposal = self.propose(state)
        decision = self._scm.step(proposal, state)
        logger.info(
            "tick: proposed=%s target=%s status=%s executed=%s",
            proposal.value, decision.target_rung, decision.status.value, decision.execute,
        )
        return decision

    def run(self, tick_seconds: float, max_ticks: Optional[int] = None) -> None:
        ticks = 0
        while max_ticks is None or ticks < max_ticks:
            self.tick()
            ticks += 1
            time.sleep(tick_seconds)


class _UnavailableTelemetry:
    def measure(self) -> Optional[AgentState]:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="PYTHIA deterministic mining agent")
    ap.add_argument("--policy", default=DEFAULT_POLICY_PATH)
    ap.add_argument("--ledger", default=DEFAULT_LEDGER_PATH)
    ap.add_argument("--tick-seconds", type=float, default=20.0)
    ap.add_argument("--ticks", type=int, default=None)
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    policy = AgentPolicy.load(args.policy)
    ledger = EmpiricalLedger(args.ledger)
    # No production telemetry/actuator adapters are bound by default: the
    # agent fails closed rather than simulate measurements. Wire real
    # sources (Salamander/Cassini iGPU telemetry, Stratum client, OpenCL
    # scale actuator) here when commissioning against hardware.
    agent = PythiaAgent(policy, ledger, telemetry=_UnavailableTelemetry(), actuator=None)
    agent.run(args.tick_seconds, args.ticks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
