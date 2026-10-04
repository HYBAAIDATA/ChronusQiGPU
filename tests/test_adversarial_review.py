"""Independent adversarial review harness for EUCLID intelligence readiness.

Pins the executable findings of ``eval_harness`` as machine-checkable gates.
A ``FAIL`` verdict for a documented finding is asserted as ``FAIL`` — when the
underlying defect is repaired the assertion flips and the review is rerun.
"""

from __future__ import annotations

import unittest

from eval_harness import (
    falsification,
    heldout_eval,
    memory_influence,
    reachability_audit,
    reward_audit,
)

_falsification = falsification.run_all()
_reward = reward_audit.run_all()
_influence = memory_influence.run_all()
_heldout = heldout_eval.run_all()
_matrix = reachability_audit.run_all()


class FalsificationGateTests(unittest.TestCase):
    """Determinism, integrity and fail-closed gates that must hold."""

    def test_deterministic_seal(self):
        self.assertEqual(_falsification["deterministic_seal"]["verdict"], "PASS")

    def test_replay_identity_stable(self):
        self.assertEqual(_falsification["replay_identity_stable"]["verdict"], "PASS")

    def test_duplicate_replay_fails_closed(self):
        self.assertEqual(_falsification["duplicate_replay_closed"]["verdict"], "PASS")

    def test_memory_db_tamper_rejected(self):
        self.assertEqual(_falsification["memory_db_tamper_rejected"]["verdict"], "PASS")

    def test_reachability_tamper_rejected(self):
        self.assertEqual(_falsification["reachability_tamper_rejected"]["verdict"], "PASS")

    def test_malformed_source_reaches_diagnosis(self):
        self.assertEqual(_falsification["malformed_source_diagnosis"]["verdict"], "PASS")

    def test_terminal_cycle_learned(self):
        self.assertEqual(_falsification["terminal_cycle_learned"]["verdict"], "PASS")

    def test_requested_strategy_reachable(self):
        self.assertEqual(_falsification["requested_strategy_reachable"]["verdict"], "PASS")

    def test_world_model_not_double_counted(self):
        self.assertEqual(_falsification["world_model_single_observation"]["verdict"], "PASS")

    def test_mathematical_structure_ablation(self):
        self.assertEqual(_falsification["mathematical_structure_ablation"]["verdict"], "PASS")

    def test_second_action_same_domain_learns(self):
        self.assertEqual(_falsification["second_action_same_domain"]["verdict"], "PASS")


class DocumentedFindingTests(unittest.TestCase):
    """Findings recorded by the review — assert the documented current state."""

    def test_restart_verified_is_self_certified(self):
        # The in-process self-cert grant was removed (PERSISTED no longer
        # promotes to RESTART_VERIFIED without executed verification); the
        # gate now pins the repaired behavior.
        self.assertEqual(_falsification["restart_verified_self_certified"]["verdict"], "PASS")

    def test_strategy_feedback_loop_connected(self):
        # Measured outcomes must land under a key the decision machinery
        # reads: stats[(class, arm)] for an arm in the composer portfolio or
        # the selected strategy id.
        self.assertEqual(
            _falsification["strategy_feedback_loop_connected"]["verdict"],
            "PASS",
        )
        self.assertTrue(
            _falsification["strategy_feedback_loop_connected"]["executed_arm_stats_keys"]
        )

    def test_transfer_verified_requires_memory_influence(self):
        # TRANSFER_VERIFIED is now produced — and must require episode
        # evidence: no grant on a cold episode; grant only when a durable
        # record observably biases a downstream decision.
        result = _falsification["transfer_verified_requires_memory_influence"]
        self.assertEqual(result["verdict"], "PASS")
        self.assertTrue(result["memory_influence_transition"])


class RewardIntegrityTests(unittest.TestCase):
    def test_reward_audit_all_pass(self):
        for name, result in _reward.items():
            self.assertEqual(
                result["verdict"],
                "PASS",
                f"{name}: {result.get('detail')}",
            )


class MemoryInfluenceTests(unittest.TestCase):
    def test_retrieval_changes_decision_only_when_relevant(self):
        # A retrieved record is influential iff removing it changes a
        # recorded downstream decision; irrelevant memory must stay inert.
        verdicts = _influence["influence_verdicts"]
        self.assertTrue(verdicts["relevant_influential"])
        self.assertFalse(verdicts["irrelevant_changes_decision"])
        self.assertTrue(verdicts["relevant_vs_irrelevant_differ"])


class HeldOutEvaluationTests(unittest.TestCase):
    def test_partitions_and_controls_present(self):
        runs = _heldout["runs"]
        for required in (
            "cold_runtime",
            "warm_runtime",
            "irrelevant_memory_control",
            "absent_reward_control",
            "regression_control",
        ):
            self.assertIn(required, runs)

    def test_cold_warm_rankings_equal(self):
        # Documented negative: learned state produces no decision difference.
        self.assertTrue(_heldout["comparisons"]["cold_vs_warm_ranking_equal"])

    def test_absent_reward_blocks_learning(self):
        self.assertEqual(_heldout["comparisons"]["absent_reward_learner_transitions"], 0)


class CapabilityMatrixTests(unittest.TestCase):
    def test_matrix_covers_required_components(self):
        for component in (
            "euclid.learning_service",
            "euclid.memory_database",
            "euclid.strategy_meta_learning",
            "euclid.v16.search",
        ):
            self.assertIn(component, _matrix["matrix"])

    def test_recorded_stages_match_executable_evidence(self):
        # No recorded stage may exceed what episode evidence supports.
        verdicts = {component: row["verdict"] for component, row in _matrix["matrix"].items()}
        self.assertNotIn("INFLATED", verdicts.values())
        row = _matrix["matrix"]["euclid.strategy_meta_learning"]
        self.assertEqual(row["verdict"], "MATCH")
        self.assertEqual(row["recorded_stage"], "FEEDBACK_CLOSED")


if __name__ == "__main__":
    unittest.main()
