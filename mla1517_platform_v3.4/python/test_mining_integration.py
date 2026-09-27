"""Regression tests for the canonical PYTHIA mining subsystem."""

from __future__ import annotations

import unittest

from mla1517.mining.chooser import MiningIntelligenceChooser
from mla1517.mining.geometry import M32Topology
from mla1517.mining.pow import build_header, check_pow, compact_target
from mla1517.mining.solver import M32SearchSolver

PREV = "00" * 32
MERKLE = "4a5e1e4baab89f3a32518a88c31bc87f618f76673e2cc77ab2127b7afdeda33b"


class MiningIntegrationTests(unittest.TestCase):
    def test_m32_topology_is_connected_and_lane_order_is_complete(self) -> None:
        topology = M32Topology()
        self.assertTrue(topology.connected())
        self.assertEqual(topology.lane_order(7), tuple((7 + i) % 32 for i in range(32)))

    def test_pow_boundary_is_real_sha256d(self) -> None:
        bits = "207fffff"
        target = compact_target(bits)
        header = build_header(1, PREV, MERKLE, 1_700_000_000, bits, 0)
        self.assertEqual(len(header), 80)
        self.assertIsInstance(check_pow(header, target), bool)

    def test_solver_checks_each_complete_header(self) -> None:
        result = M32SearchSolver().scan(
            version=1,
            previous_hash=PREV,
            merkle_root=MERKLE,
            timestamp=1_700_000_000,
            bits="207fffff",
            budget=64,
        )
        self.assertEqual(result.attempts, 1)
        self.assertTrue(result.valid)
        self.assertIsNotNone(result.found_nonce)
        self.assertEqual(result.proof, "sha256d")

    def test_chooser_learns_only_pool_outcomes(self) -> None:
        chooser = MiningIntelligenceChooser()
        decision = chooser.choose(
            has_job=True,
            candidate_window=[1, 1, 2, 3, 5, 8],
            budget=64,
        )
        self.assertEqual(decision.lead, "m32_structured")
        self.assertEqual(decision.policy.structure_prior, "truncated_icosahedron_32f")
        chooser.learn(accepted=True, lead=decision.lead, job_id="job-1")
        chooser.learn(accepted=False, lead=decision.lead, job_id="job-2")
        self.assertEqual(chooser.accepted_count, 1)
        self.assertEqual(chooser.rejected_count, 1)

    def test_phi_score_selects_ordering_and_ignores_a_planted_fibonacci(self) -> None:
        import random

        from mla1517.mining.structure import INV_PHI

        chooser = MiningIntelligenceChooser()
        solver = M32SearchSolver()
        fib = chooser.choose(
            has_job=True,
            candidate_window=[1, 1, 2, 3, 5, 8],
            budget=64,
            solver=solver,
        )
        self.assertEqual(fib.lead, "m32_structured")
        self.assertGreaterEqual(fib.structure_parameter, INV_PHI)
        self.assertEqual(solver.get_candidate_ordering(), "m32_lane_order")
        structured_lanes = [lane for _nonce, lane in solver.candidates(0, 32)]
        self.assertEqual(structured_lanes, list(solver.turing.lane_order(0)))

        rng = random.Random(1)
        planted = [1, 2, 3] + [rng.randrange(2**32) for _ in range(80)]
        flat = chooser.choose(has_job=True, candidate_window=planted, budget=64, solver=solver)
        self.assertEqual(flat.lead, "flat_exhaustive")
        self.assertLess(flat.structure_parameter, INV_PHI)
        self.assertEqual(solver.get_candidate_ordering(), "exhaustive")
        flat_lanes = [lane for _nonce, lane in solver.candidates(0, 32)]
        self.assertEqual(flat_lanes, list(range(32)))
        self.assertEqual(len(set(flat_lanes)), 32)

    def test_unmeasured_window_is_flat_and_not_a_zero_score(self) -> None:
        chooser = MiningIntelligenceChooser()
        decision = chooser.choose(has_job=True, candidate_window=[4, 9])
        self.assertEqual(decision.lead, "flat_exhaustive")
        self.assertIsNone(decision.structure_parameter)
        absent = chooser.choose(has_job=False)
        self.assertEqual(absent.lead, "safe")
        self.assertIsNone(absent.structure_parameter)
        self.assertEqual(absent.policy.candidate_ordering, "exhaustive")


if __name__ == "__main__":
    unittest.main()
