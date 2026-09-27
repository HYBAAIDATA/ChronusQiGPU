import unittest

from agentic_mining import (
    Action,
    CommissionedSCM,
    GeomEncoder,
    MeasuredForwardIndex,
    MiningAgent,
    NotCommissioned,
    NotMeasured,
    ObservedCounterfactuals,
    State,
    SupportViolation,
    TopologicalRegime,
    Transition,
)


def sample_state(clock=1000.0, power=500.0, faults=None, hashes=None):
    return State(
        temps=tuple(60.0 + (i % 3) for i in range(32)),
        hashes=tuple(hashes or [1_000_000 for _ in range(32)]),
        faults=tuple(faults or [0 for _ in range(32)]),
        power_w=power,
        clock_mhz=clock,
        pool_latency={"primary": 40.0},
        mempool_fees=(10.0, 12.0),
        btc_price=60_000.0,
    )


def action(clock=1000.0):
    return Action((1 << 32) - 1, (clock,) * 4)


class AgenticMiningTests(unittest.TestCase):
    def test_geometry_is_deterministic_and_not_trained(self):
        encoder = GeomEncoder()
        first = encoder.embed(sample_state())
        second = encoder.embed(sample_state())
        self.assertEqual(first, second)
        self.assertEqual(len(first.coordinates), 16)
        self.assertEqual(first.digest, second.digest)

    def test_topology_is_exact_on_observed_lane_graph(self):
        inv = TopologicalRegime().invariants(sample_state())
        self.assertEqual(inv.healthy_lanes, 32)
        self.assertEqual(inv.b0, 1)
        self.assertGreater(inv.b1, 0)
        self.assertEqual(inv.fault_mass, 0)

    def test_forward_result_requires_real_transition(self):
        ledger = MeasuredForwardIndex()
        regime = TopologicalRegime().invariants(sample_state()).regime_key
        with self.assertRaises(NotMeasured):
            ledger.forward(sample_state(), action(900), regime)

    def test_causal_effect_requires_commissioned_intervention(self):
        scm = CommissionedSCM()
        regime = TopologicalRegime().invariants(sample_state()).regime_key
        with self.assertRaises(NotCommissioned):
            scm.causal_effect(action(900), "power", regime)
        before, after = sample_state(), sample_state(clock=900, power=430)
        transition = Transition(before, action(900), after, 2.0, regime)
        scm.commission(transition)
        self.assertEqual(scm.causal_effect(action(900), "power", regime), -70.0)

    def test_counterfactual_rejects_unobserved_action(self):
        ledger = MeasuredForwardIndex()
        cf = ObservedCounterfactuals(ledger)
        with self.assertRaises(SupportViolation):
            cf.score(action(900), "nominal")

    def test_agent_uses_measured_support_and_salamander_veto(self):
        before = sample_state()
        regime = TopologicalRegime().invariants(before).regime_key
        measured = action(900)
        ledger = MeasuredForwardIndex()
        ledger.record(
            Transition(before, measured, sample_state(clock=900, power=430), 10.0, regime)
        )
        writes = []
        agent = MiningAgent(
            ledger=ledger,
            salamander_permits=lambda _: True,
            actuator=lambda a: writes.append(a) or True,
        )
        decision = agent.tick(before)
        self.assertEqual(decision.reason, "observed_counterfactual_argmax")
        self.assertEqual(writes, [measured])
        vetoed = MiningAgent(ledger=ledger, salamander_permits=lambda _: False)
        safe = vetoed.tick(before)
        self.assertEqual(safe.reason, "no_measured_supported_action")
        self.assertGreaterEqual(safe.action.active_lanes, 24)

    def test_acknowledged_actuation_populates_measured_index(self):
        before = sample_state()
        measured = action(900)
        after = sample_state(clock=900, power=430)
        agent = MiningAgent(
            ledger=MeasuredForwardIndex(),
            actuator=lambda _: True,
        )
        # First expose real support, then execute it and record the measured result.
        regime = agent.topology.invariants(before).regime_key
        agent.ledger.record(Transition(before, measured, after, 10.0, regime))
        decision = agent.tick(before)
        self.assertEqual(decision.action, measured)
        transition = agent.record_observed_result(after, 11.0)
        self.assertEqual(len(agent.ledger.transitions), 2)
        self.assertEqual(transition.reward, 11.0)


if __name__ == "__main__":
    unittest.main()
