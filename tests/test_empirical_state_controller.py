"""Empirical State Controller verification.

Covers the deterministic control contract end to end, offline only:

- Policy loads from YAML: ladder, Salamander limits, Stratum bounds.
- Ledger is append-only JSONL; query returns causal history per action.
- Salamander vetoes fire on temperature and lane floor before any execute.
- Stratum veto blocks scale actions; FAILOVER is commissioned only then.
- Strict empirical gate: SCALE_* without prior SUPPORTED evidence is
  refused; a ledger veto permanently blocks the same (action, rung).
"""

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
    CommissionedSCM,
    EmpiricalLedger,
)

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


class ControllerFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.policy_path = os.path.join(self.tmp.name, "agent_policy.yml")
        with open(self.policy_path, "w", encoding="utf-8") as fh:
            fh.write(POLICY_YAML)
        self.ledger_path = os.path.join(self.tmp.name, "empirical_ledger.jsonl")
        self.policy = AgentPolicy.load(self.policy_path)
        self.ledger = EmpiricalLedger(self.ledger_path)

    def tearDown(self):
        self.tmp.cleanup()

    def ctrl(self, outcome=None):
        return CommissionedSCM(
            self.policy,
            self.ledger,
            execute=outcome or (lambda a, r: {"accepted": 0, "rejected": 0}),
        )


class TestPolicy(ControllerFixture):
    def test_policy_loads(self):
        self.assertEqual(self.policy.mode, "strict_empirical")
        self.assertEqual(self.policy.ladder, (10, 12, 15, 18, 20, 31, 50, 76))
        self.assertEqual(self.policy.max_temp_celsius, 82.0)
        self.assertEqual(self.policy.min_active_lanes, 24)
        self.assertEqual(self.policy.max_rejected_shares_per_window, 0)

    def test_unknown_mode_rejected(self):
        bad = AgentPolicy(
            mode="heuristic", ladder=(10,), max_temp_celsius=82.0,
            min_active_lanes=24, stratum_primary="x", stratum_failover="y",
            max_rejected_shares_per_window=0,
        )
        with self.assertRaises(ValueError):
            CommissionedSCM(bad, self.ledger)


class TestVetoes(ControllerFixture):
    def test_temp_veto(self):
        d = self.ctrl().evaluate(
            AgentAction.SCALE_UP, 20, AgentState(temp_celsius=83.2, active_lanes=32, current_rung=18)
        )
        self.assertEqual(d.status, CausalStatus.VETO_SALAMANDER_TEMP)
        self.assertFalse(d.execute)

    def test_lane_veto(self):
        d = self.ctrl().evaluate(
            AgentAction.SCALE_UP, 20, AgentState(temp_celsius=70.0, active_lanes=23, current_rung=18)
        )
        self.assertEqual(d.status, CausalStatus.VETO_SALAMANDER_LANES)

    def test_stratum_veto_blocks_scale_commissions_failover(self):
        state = AgentState(temp_celsius=70.0, active_lanes=32, current_rung=18,
                           rejected_shares_in_window=1)
        d = self.ctrl().evaluate(AgentAction.SCALE_UP, 20, state)
        self.assertEqual(d.status, CausalStatus.VETO_STRATUM_REJECTED)
        f = self.ctrl().evaluate(AgentAction.FAILOVER, None, state)
        self.assertTrue(f.execute)
        self.assertEqual(f.status, CausalStatus.SUPPORTED)

    def test_failover_refused_without_veto(self):
        f = self.ctrl().evaluate(
            AgentAction.FAILOVER, None,
            AgentState(temp_celsius=70.0, active_lanes=32, current_rung=18),
        )
        self.assertFalse(f.execute)
        self.assertEqual(f.status, CausalStatus.UNSUPPORTED)

    def test_off_ladder_target_vetoed(self):
        d = self.ctrl().evaluate(
            AgentAction.SCALE_UP, 19, AgentState(temp_celsius=70.0, active_lanes=32, current_rung=18)
        )
        self.assertEqual(d.status, CausalStatus.VETO_LADDER)

    def test_dwell_always_permitted(self):
        d = self.ctrl().evaluate(
            AgentAction.DWELL, 18, AgentState(temp_celsius=70.0, active_lanes=32, current_rung=18)
        )
        self.assertTrue(d.execute)


class TestCausalGate(ControllerFixture):
    def test_scale_refused_without_evidence(self):
        d = self.ctrl().evaluate(
            AgentAction.SCALE_UP, 20, AgentState(temp_celsius=70.0, active_lanes=32, current_rung=18)
        )
        self.assertEqual(d.status, CausalStatus.UNSUPPORTED)
        self.assertFalse(d.execute)

    def test_prior_veto_blocks_reattempt(self):
        state = AgentState(temp_celsius=83.2, active_lanes=32, current_rung=18)
        c = self.ctrl()
        c.step(AgentAction.SCALE_UP, state)  # records VETO_SALAMANDER_TEMP for rung 20
        cool = AgentState(temp_celsius=70.0, active_lanes=32, current_rung=18)
        d = c.evaluate(AgentAction.SCALE_UP, 20, cool)
        self.assertEqual(d.status, CausalStatus.VETO_SALAMANDER_TEMP)
        self.assertFalse(d.execute)

    def test_supported_history_executes(self):
        c = self.ctrl(lambda a, r: {"accepted": 185, "rejected": 0})
        state = AgentState(temp_celsius=70.0, active_lanes=32, current_rung=15)
        # Seed causal support for SCALE_UP→18, then verify the gate opens.
        self.ledger.append(action=AgentAction.SCALE_UP, target_rung=18, state=state,
                           outcome={"accepted": 185, "rejected": 0},
                           causal_status=CausalStatus.SUPPORTED)
        d = c.step(AgentAction.SCALE_UP, state)
        self.assertTrue(d.execute)
        self.assertEqual(d.target_rung, 18)


class TestLedger(ControllerFixture):
    def test_append_only_jsonl_roundtrip(self):
        c = self.ctrl()
        state = AgentState(temp_celsius=72.1, active_lanes=32, current_rung=15)
        c.step(AgentAction.DWELL, state)
        c.step(AgentAction.DWELL, state)
        entries = self.ledger.entries()
        self.assertEqual(len(entries), 2)
        self.assertTrue(all(e["action"] == "DWELL" for e in entries))
        with open(self.ledger_path, encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
        self.assertEqual(len(lines), 2)  # append-only file matches memory

    def test_ladder_boundaries(self):
        c = self.ctrl()
        self.assertEqual(c.next_rung(15, +1), 18)
        self.assertEqual(c.next_rung(18, -1), 15)
        self.assertIsNone(c.next_rung(76, +1))
        self.assertIsNone(c.next_rung(10, -1))


if __name__ == "__main__":
    unittest.main()
