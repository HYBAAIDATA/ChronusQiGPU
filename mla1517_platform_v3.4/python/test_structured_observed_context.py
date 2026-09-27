"""Behavioural tests for complete Turing ordering and observed TOE context."""
from __future__ import annotations

import unittest
from dataclasses import dataclass

from mla1517.mining.toe_adapter import TOEMiningAdapter
from mla1517.mining.turing_adapter import TuringMiningSubstrate


class FakeTuringCore:
    @staticmethod
    def extended_nonce_schedule(window: int, *, seed: int, cap: int):
        # Deliberately repeats and emits an out-of-range value. The adapter must
        # repair the ordering by appending every untouched offset exactly once.
        return [seed % window, seed % window, window + 5][:cap]


@dataclass(frozen=True)
class Job:
    job_id: str = "live-job"
    params: tuple = ("live-job", "00" * 32, "01", "02", [], "20000000", "1d00ffff", "65abcdef", True)


class FakeTOE:
    def __init__(self):
        self.observed = None

    def predict(self, observed):
        self.observed = observed
        return {
            "available": True,
            "state_tomography": {"available": True},
            "trajectory_prediction": {"available": True},
            "causal_analysis": {"available": True},
            "causal_ladder": {"available": True},
            "exact_tensor": {"available": True},
        }

    def algebraic_signature(self, data):
        return {"available": True, "family": "golden", "residual": 0.0}

    def execution_evidence(self):
        return {"backend": "observed_test_bridge", "synthetic": False}


class StructuredObservedContextTests(unittest.TestCase):
    def test_exhaustive_order_is_a_true_permutation(self):
        substrate = TuringMiningSubstrate(core=FakeTuringCore())
        order = substrate.exhaustive_order(257, seed=11)
        self.assertEqual(len(order), 257)
        self.assertEqual(set(order), set(range(257)))
        self.assertEqual(len(set(order)), 257)

    def test_toe_receives_only_job_state_lane_and_sequence(self):
        bridge = FakeTOE()
        adapter = TOEMiningAdapter(bridge=bridge)
        context = adapter.analyse(job=Job(), state=bytes(range(64)), node_id=7, sequence=19)
        self.assertEqual(context.job_id, "live-job")
        self.assertEqual(bridge.observed["node_id"], 7)
        self.assertEqual(bridge.observed["sequence"], 19)
        self.assertEqual(bridge.observed["mla1517_state_bytes"], list(range(64)))
        self.assertFalse(context.execution_evidence["synthetic"])


if __name__ == "__main__":
    unittest.main()
