"""EUCLID v17: the integrated cognitive loop end to end.

These tests drive the real GeneralIntelligenceCore with the integrated
specialists against hidden-mechanism worlds through the governed executor.
"""
from __future__ import annotations

import unittest

from euclid.cognition.integrated import AgentKnowledge, IntegratedAgent, SYSTEMS
from euclid.cognition.integrated.analogy import causal_memory_payload
from euclid.cognition.integrated.composition import AdaptiveDecisionObjective
from euclid.cognition.integrated.memory import memory_item
from euclid.cognition.state import (
    CognitiveState,
    EpistemicStatus,
    EvidenceOrigin,
    MemoryKind,
    Outcome,
)
from euclid.cognition.worlds import (
    MechanismWorld,
    WorldExecutor,
    generate_suite,
    generate_task,
)

LOOP_PHASES = (
    "represent", "retrieve", "analogy", "cycle", "strategy", "abduce", "deduce",
    "evidence-decision", "discriminate", "hypothesis-update", "plan", "restructure",
    "compose", "imagine", "rank", "execute", "compare", "metacontrol", "objectives",
    "learn", "credit", "consolidate", "terminate",
)


def solve(system: str, spec, truth, *, knowledge=None, seed=3):
    agent = (IntegratedAgent(knowledge=knowledge, ablations=SYSTEMS[system],
                             reference_v16=system == "v16.4-reference")
             if knowledge is not None else IntegratedAgent.for_system(system))
    world = MechanismWorld(spec, truth, seed=seed)
    result = agent.solve(spec, WorldExecutor(world), seed=seed)
    return result, world, agent


class FullCycle(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spec, cls.truth = generate_task("program-transformation", seed=101,
                                            partition="evaluation")
        cls.result, cls.world, _ = solve("integrated", cls.spec, cls.truth)

    def test_identification_strategy_never_acts_blind(self) -> None:
        result, _, _ = solve("minus-meta-learning", self.spec, self.truth)
        first = next(t for t in result.state.transitions if t.phase == "evidence-decision")
        self.assertEqual(first.details["action"], "seek_evidence")
        for row in result.state.expected_outcomes:
            self.assertGreater(row["success_probability"] or 0.0, 0.0)

    def test_every_loop_stage_is_an_inspectable_transition(self) -> None:
        phases = [t.phase for t in self.result.state.transitions]
        for phase in LOOP_PHASES:
            self.assertIn(phase, phases, f"missing loop stage {phase}")
        order = [phases.index(p) for p in ("represent", "strategy", "discriminate", "plan",
                                           "compose", "execute", "consolidate", "terminate")]
        self.assertEqual(order, sorted(order))

    def test_outcome_agrees_with_the_world_ledger(self) -> None:
        state = self.result.state
        self.assertEqual(state.outcome is Outcome.SOLVED, self.world.solved)
        executed = [e for e in state.evidence_items if e.evidence_id.startswith(("exec-", "int-"))]
        self.assertEqual(len(executed), len(self.world.ledger))
        self.assertTrue(all(e.origin is EvidenceOrigin.OBSERVED
                            and e.status is EpistemicStatus.KNOWN for e in executed))

    def test_imagined_rollouts_never_become_observations(self) -> None:
        state = self.result.state
        imagined = [p for p in state.predictions if p.imagined]
        self.assertTrue(imagined)
        observed_ids = {e.evidence_id for e in state.evidence_items}
        self.assertFalse({p.prediction_id for p in imagined} & observed_ids)
        self.assertTrue(all(row["epistemic_status"] == "predicted"
                            for row in state.expected_outcomes))
        self.assertTrue(all(row["epistemic_status"] == "observed"
                            for row in state.actual_outcomes))

    def test_cognitive_state_is_serialisable_and_replayable(self) -> None:
        payload = self.result.state.to_payload()
        restored = CognitiveState.from_payload(payload)
        self.assertEqual(restored.to_payload()["seal"], payload["seal"])
        for key in ("hypotheses", "analogies", "strategy_history", "uncertainty_trace",
                    "causal_assumptions", "expected_outcomes", "actual_outcomes"):
            self.assertIn(key, payload)
        tampered = dict(payload)
        tampered["outcome"] = "solved" if payload["outcome"] != "solved" else "stalled"
        with self.assertRaises(ValueError):
            CognitiveState.from_payload(tampered)

    def test_episode_is_deterministic(self) -> None:
        again, _, _ = solve("integrated", self.spec, self.truth)
        self.assertEqual(again.state.to_payload()["seal"],
                         self.result.state.to_payload()["seal"])

    def test_hypotheses_compete_and_carry_posterior_confidence(self) -> None:
        state = solve("minus-meta-learning", self.spec, self.truth)[0].state
        abduce = next(t for t in state.transitions if t.phase == "abduce")
        self.assertGreaterEqual(len(abduce.details["hypotheses"]), 2)
        updates = [t for t in state.transitions if t.phase == "hypothesis-update"]
        self.assertTrue(updates)
        self.assertIn("entropy_reduction_bits", updates[0].details)
        self.assertTrue(any(h.status.value == "refuted" for h in state.hypotheses))


class Ablations(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spec, cls.truth = generate_task("causal-circuit", seed=55, partition="evaluation")

    def test_causal_ablation_removes_interventions(self) -> None:
        result, world, _ = solve("minus-causal", self.spec, self.truth)
        self.assertEqual(world.probes_used, 0)
        self.assertIn("causal_reasoning", result.state.ablations)

    def test_world_model_ablation_removes_the_posterior(self) -> None:
        result, world, _ = solve("minus-world-model", self.spec, self.truth)
        self.assertIsNone(result.context.posterior)
        self.assertEqual(world.probes_used, 0)
        self.assertNotIn("imagine", [t.phase for t in result.state.transitions])

    def test_representation_ablation_keeps_literal_search(self) -> None:
        result, _, _ = solve("minus-representation", self.spec, self.truth)
        self.assertEqual(result.context.representation, "literal")
        self.assertNotIn("restructure", [t.phase for t in result.state.transitions])

    def test_replanning_ablation_freezes_prepared_candidates(self) -> None:
        result, _, _ = solve("minus-replanning", self.spec, self.truth)
        phases = [t.phase for t in result.state.transitions]
        if any(not row["goal_met"] for row in result.state.actual_outcomes[:-1]):
            self.assertIn("replan-ablated", phases)
        self.assertNotIn("replan", phases)

    def test_ablation_configuration_is_recorded(self) -> None:
        result, _, _ = solve("minus-phi-lucas-manifold", self.spec, self.truth)
        config = result.state.representation["ablation_config"]
        self.assertFalse(config["mathematical_structure"])
        self.assertIn("mathematical_structure", result.state.ablations)

    def test_v16_reference_has_no_model_and_uses_declared_weights(self) -> None:
        result, world, _ = solve("v16.4-reference", self.spec, self.truth)
        self.assertEqual(world.probes_used, 0)
        rank = next(t for t in result.state.transitions if t.phase == "rank")
        self.assertEqual(rank.details["weights"]["novelty"], 0.10)


class LearningAndEvaluation(unittest.TestCase):
    def test_frozen_evaluation_learns_nothing(self) -> None:
        suite = generate_suite(7001, train_per_family=1, development_per_family=0,
                               evaluation_per_family=1, held_out_per_family=1,
                               adversarial_per_tag=0, analogy_pairs=0)
        agent = IntegratedAgent.for_system("integrated")
        for index, task in enumerate(suite["train"]):
            agent.solve(task.spec, WorldExecutor(task.world(seed=index)), seed=index)
        self.assertGreater(agent.knowledge.episodes, 0)
        frozen = agent.knowledge.freeze()
        before = frozen.to_payload()["seal"]
        items = sorted(frozen.memory.items)
        evaluator = IntegratedAgent(knowledge=frozen)
        for index, task in enumerate(suite["evaluation"] + suite["held-out"]):
            result = evaluator.solve(task.spec, WorldExecutor(task.world(seed=index)), seed=index)
            consolidate = next(t for t in result.state.transitions if t.phase == "consolidate")
            self.assertIn("frozen", consolidate.details["learning"])
        self.assertEqual(frozen.to_payload()["seal"], before)
        self.assertEqual(sorted(frozen.memory.items), items)

    def test_training_writes_provenanced_memory_of_every_kind_used(self) -> None:
        suite = generate_suite(7002, train_per_family=2, development_per_family=0,
                               evaluation_per_family=0, held_out_per_family=0,
                               adversarial_per_tag=0, analogy_pairs=0)
        agent = IntegratedAgent.for_system("integrated")
        for index, task in enumerate(suite["train"]):
            agent.solve(task.spec, WorldExecutor(task.world(seed=index)), seed=index)
        kinds = {item.kind for item in agent.knowledge.memory.items.values()}
        self.assertTrue({MemoryKind.EPISODIC, MemoryKind.CAUSAL, MemoryKind.STRATEGY} <= kinds)
        self.assertTrue(all(item.provenance.startswith("episode:")
                            for item in agent.knowledge.memory.items.values()))
        restored = AgentKnowledge.from_payload(agent.knowledge.to_payload())
        self.assertEqual(restored.kind_prior(), agent.knowledge.kind_prior())

    def test_negative_transfer_ledger_detects_reliably_worse_import(self) -> None:
        learner = AgentKnowledge().strategies
        for _ in range(40):
            learner.record_episode("class-a", "s-global", 0.95)
        for _ in range(4):
            learner.record_episode("class-b", "s-global", 0.1)
            learner.record_episode("class-b", "s-local", 0.8)
        self.assertTrue(any(e["class"] == "class-b" and e["imported"] == "s-global"
                            for e in learner.negative_transfer))
        learner.frozen = True
        choice = learner.select_strategy("class-b", ("s-global", "s-local"))
        self.assertEqual(choice.strategy_id, "s-local")


class AdversarialResistance(unittest.TestCase):
    def test_superficial_surface_match_is_never_adopted(self) -> None:
        spec, truth = generate_task("causal-circuit", seed=61, partition="evaluation")
        decoy_spec, decoy_truth = generate_task("causal-circuit", seed=62, partition="train")
        knowledge = AgentKnowledge()
        payload = causal_memory_payload(decoy_spec, decoy_truth.mechanisms, [])
        payload["surface_tokens"] = sorted(set(payload["surface_tokens"]) | {
            part for name in spec.operators for part in name.split("_")})
        payload["domains"] = [d + 1 for d in spec.domains]  # incompatible structure
        knowledge.memory.store(memory_item("causal:decoy", MemoryKind.CAUSAL, payload,
                                           "episode:decoy", ["objective:assign"], 1.0))
        result, _, _ = solve("integrated", spec, truth, knowledge=knowledge)
        statuses = {a.source_ref: a.status.value for a in result.state.analogies}
        self.assertEqual(statuses.get("causal:decoy"), "rejected")

    def test_out_of_grammar_operator_triggers_selective_repair(self) -> None:
        for seed in range(40, 60):
            spec, truth = generate_task("program-transformation", seed=seed,
                                        partition="evaluation", tags=("out-of-grammar",))
            result, _, _ = solve("minus-meta-learning", spec, truth)
            rebuilds = result.context.posterior.rebuilds
            if rebuilds:
                self.assertIn(rebuilds[0]["resolution"],
                              ("grammar-expansion", "change-point", "unresolved"))
                phases = [t.phase for t in result.state.transitions]
                self.assertIn("model-repair", phases)
                return
        self.skipTest("no out-of-grammar operator was exercised in the sampled tasks")

    def test_phi_signal_has_no_weight_without_measured_validity(self) -> None:
        objective = AdaptiveDecisionObjective(AgentKnowledge())
        weights, rationale = objective.weights()
        self.assertEqual(weights["phi_signal"], 0.0)
        self.assertEqual(weights["novelty"], 0.0)
        knowledge = AgentKnowledge()
        for index in range(40):
            knowledge.record_validity({"phi_signal": (index % 2) * 1.0}, success=index % 2 == 0)
        weights, _ = AdaptiveDecisionObjective(knowledge).weights()
        self.assertEqual(weights["phi_signal"], 0.0, "anti-correlated φ must not gain weight")
        self.assertTrue(all(abs(w) <= 1.0 for w in weights.values()))

    def test_proxy_reward_attack_is_audited(self) -> None:
        # A model-free system that keeps composing from execution feedback is
        # the one a proxy can lure; its audit must register the detachment.
        exercised = 0
        for seed in range(70, 100):
            spec, truth = generate_task("symbolic-rewriting", seed=seed, partition="evaluation",
                                        tags=("proxy-reward",))
            result, world, _ = solve("minus-world-model", spec, truth)
            proxy = next(iter(truth.proxy_operators))
            uses = [entry for entry in world.ledger if proxy in entry["program"]]
            if uses and len(world.ledger) > 1 and proxy in world.ledger[0]["program"]:
                exercised += 1
                self.assertGreater(result.context.audit.detached, 0)
        if not exercised:
            self.skipTest("proxy operator not exercised before the last submission")

    def test_evidence_policy_respects_declared_costs(self) -> None:
        spec, truth = generate_task("causal-circuit", seed=91, partition="evaluation")
        result, world, _ = solve("minus-meta-learning", spec, truth)
        decisions = [t.details for t in result.state.transitions
                     if t.phase == "evidence-decision"]
        self.assertTrue(decisions)
        self.assertLessEqual(world.probes_used, spec.probe_budget)
        self.assertTrue(all("probes_remaining" in d["signals"] for d in decisions))


class Statistics(unittest.TestCase):
    def test_intervals_and_scores(self) -> None:
        from euclid.cognition.research.stats import (
            brier,
            expected_calibration_error,
            paired_bootstrap,
            t_interval,
            wilson,
        )

        interval = t_interval([1.0, 2.0, 3.0])
        self.assertAlmostEqual(interval["mean"], 2.0)
        self.assertAlmostEqual(interval["high95"] - interval["mean"], 4.303 * 1.0 / 3 ** 0.5,
                               places=3)
        boot = paired_bootstrap([1, 1, 1, 1], [0, 0, 0, 0], seed=1)
        self.assertTrue(boot["excludes_zero"])
        self.assertEqual(boot, paired_bootstrap([1, 1, 1, 1], [0, 0, 0, 0], seed=1))
        self.assertAlmostEqual(wilson(0, 10)["low95"], 0.0, places=6)
        self.assertEqual(brier([(1.0, 1), (0.0, 0)]), 0.0)
        self.assertAlmostEqual(expected_calibration_error([(0.9, 0), (0.9, 0)]), 0.9)


if __name__ == "__main__":
    unittest.main()
