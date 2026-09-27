"""CI enforcement for Rule 7 — the PythiaAgent orchestration loop.

Proves the agent rejects a SCALE_UP proposal purely from JSONL ledger
history: a prior VETO_SALAMANDER_TEMP at the target rung blocks the action
even when the live thermal reading is inside policy limits. Deterministic
physical precedent replaces probabilistic inference.
"""

import json
import os
import sys
import tempfile
import unittest

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_THIS_DIR)
for p in (_REPO, os.path.join(_REPO, "Intelligence")):
    if p not in sys.path:
        sys.path.insert(0, p)

from Intelligence.empirical_state_controller import (  # noqa: E402
    AgentAction,
    AgentPolicy,
    AgentState,
    CausalStatus,
    EmpiricalLedger,
)
from pythia_agent import PythiaAgent  # noqa: E402

POLICY_YAML = """agent_governance:
  mode: strict_empirical
  lucas_pisot_ladder: [10, 12, 15, 18, 20, 31, 50, 76]
  salamander_limits:
    max_temp_celsius: 82.0
    min_active_lanes: 24
  stratum_endpoints:
    primary: "stratum+tcp://pool.braiins.com:3333"
    failover: "stratum+tcp://mining.viabtc.io:3333"
    max_rejected_shares_per_window: 0
"""


class _StaticTelemetry:
    def __init__(self, state):
        self.state = state

    def measure(self):
        return self.state


class _RecordingActuator:
    def __init__(self):
        self.calls = []

    def actuate(self, action, target_rung):
        self.calls.append((action, target_rung))
        return {"accepted": 0, "rejected": 0}


class _Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        p = os.path.join(self.tmp.name, "agent_policy.yml")
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(POLICY_YAML)
        self.policy = AgentPolicy.load(p)
        self.ledger_path = os.path.join(self.tmp.name, "empirical_ledger.jsonl")
        self.ledger = EmpiricalLedger(self.ledger_path)
        self.actuator = _RecordingActuator()

    def tearDown(self):
        self.tmp.cleanup()

    def agent(self, state):
        return PythiaAgent(self.policy, self.ledger, _StaticTelemetry(state), self.actuator)


class TestDeterministicSelfHealing(_Fixture):
    def test_ledger_veto_rejects_scale_up(self):
        """Seeded VETO_SALAMANDER_TEMP at rung 20 must reject SCALE_UP→20
        even though the live temperature is now inside limits."""
        hot = AgentState(temp_celsius=83.2, active_lanes=32, current_rung=18)
        self.ledger.append(
            action=AgentAction.SCALE_UP, target_rung=20, state=hot,
            outcome={"accepted": 0, "rejected": 0},
            causal_status=CausalStatus.VETO_SALAMANDER_TEMP,
        )
        # Live state is safe — only the ledger can stop this action.
        cool = AgentState(temp_celsius=75.4, active_lanes=32, current_rung=18)
        decision = self.agent(cool).tick()
        self.assertIsNotNone(decision)
        self.assertFalse(decision.execute)
        self.assertEqual(decision.status, CausalStatus.VETO_SALAMANDER_TEMP)
        self.assertEqual(self.actuator.calls, [])  # nothing reached hardware
        # The refusal itself was appended — the ledger grew by one entry.
        last = json.loads(open(self.ledger_path, encoding="utf-8").read().strip().splitlines()[-1])
        self.assertEqual(last["causal_status"], "VETO_SALAMANDER_TEMP")

    def test_unproven_scale_refused_fail_closed(self):
        cool = AgentState(temp_celsius=70.0, active_lanes=32, current_rung=18)
        decision = self.agent(cool).tick()
        self.assertEqual(decision.status, CausalStatus.UNSUPPORTED)
        self.assertFalse(decision.execute)
        self.assertEqual(self.actuator.calls, [])

    def test_fail_closed_without_telemetry(self):
        class _None:
            def measure(self):
                return None

        agent = PythiaAgent(self.policy, self.ledger, _None(), self.actuator)
        self.assertIsNone(agent.tick())
        self.assertFalse(os.path.exists(self.ledger_path))

    def test_fail_closed_without_actuator(self):
        cool = AgentState(temp_celsius=70.0, active_lanes=32, current_rung=18)
        agent = PythiaAgent(self.policy, self.ledger, _StaticTelemetry(cool), None)
        self.assertIsNone(agent.tick())
        self.assertFalse(os.path.exists(self.ledger_path))

    def test_full_loop_commissions_supported_action(self):
        """A prior SUPPORTED entry opens the gate; the actuator runs and the
        measured outcome is appended."""
        state = AgentState(temp_celsius=70.0, active_lanes=32, current_rung=18)
        self.ledger.append(
            action=AgentAction.SCALE_UP, target_rung=20, state=state,
            outcome={"accepted": 185, "rejected": 0},
            causal_status=CausalStatus.SUPPORTED,
        )
        decision = self.agent(state).tick()
        self.assertTrue(decision.execute)
        self.assertEqual(decision.target_rung, 20)
        self.assertEqual(self.actuator.calls, [(AgentAction.SCALE_UP, 20)])
        self.assertEqual(len(self.ledger.entries()), 2)


if __name__ == "__main__":
    unittest.main()
