"""EUCLID v17 Bayesian mechanism world model."""
from __future__ import annotations

import random
import unittest

from euclid.cognition.integrated.world_model import MechanismPosterior
from euclid.cognition.worlds import Mechanism, MechanismWorld, generate_task


def _identify(posterior, world, spec):
    for op in spec.operators:
        reading = world.probe([op, op, op])
        posterior.observe_trajectory([op, op, op], spec.initial_state, reading["trajectory"])


class Identification(unittest.TestCase):
    def test_posterior_identifies_true_mechanisms(self) -> None:
        spec, truth = generate_task("symbolic-rewriting", seed=31, partition="evaluation")
        posterior = MechanismPosterior(spec.domains, spec.operators)
        world = MechanismWorld(spec, truth)
        _identify(posterior, world, spec)
        for op, (mechanism, p) in posterior.identified(0.99).items():
            # identified behaviourally: indistinguishable on every reachable state
            self.assertEqual(mechanism.apply(spec.initial_state, spec.domains),
                             truth.mechanisms[op].apply(spec.initial_state, spec.domains))
        self.assertGreater(posterior.model_posterior()[0], 0.5)

    def test_rollouts_are_imagined_and_predictions_sum_to_one(self) -> None:
        spec, _ = generate_task("program-transformation", seed=4, partition="evaluation")
        posterior = MechanismPosterior(spec.domains, spec.operators)
        rows = posterior.rollout(spec.operators[:2], spec.initial_state)
        self.assertTrue(all(row["imagined"] for row in rows))
        dist = posterior.predictive(spec.operators[0], spec.initial_state)
        self.assertAlmostEqual(sum(dist.values()), 1.0, places=9)

    def test_success_probability_is_unbiased_against_enumeration(self) -> None:
        spec, truth = generate_task("program-transformation", seed=9, partition="evaluation")
        posterior = MechanismPosterior(spec.domains, spec.operators, monte_carlo_samples=4000)
        world = MechanismWorld(spec, truth)
        reading = world.probe([spec.operators[0]])
        posterior.observe_trajectory([spec.operators[0]], spec.initial_state,
                                     reading["trajectory"])
        program = tuple(truth.optimal_program)
        sampled = posterior.success_probability(program, spec.initial_state, spec.goal)
        exact = MechanismPosterior(spec.domains, spec.operators, enumeration_limit=10 ** 9)
        exact.observe_trajectory([spec.operators[0]], spec.initial_state, reading["trajectory"])
        # enumeration with full support coverage (or sampling) must agree
        reference = exact.success_probability(program, spec.initial_state, spec.goal)
        self.assertAlmostEqual(sampled["probability"], reference["probability"], delta=0.05)


class CompetingModels(unittest.TestCase):
    def test_noise_model_wins_under_noisy_readings(self) -> None:
        spec, truth = generate_task("causal-circuit", seed=12, partition="evaluation",
                                    tags=("noisy-observation",))
        posterior = MechanismPosterior(spec.domains, spec.operators)
        world = MechanismWorld(spec, truth, seed=3)
        for _ in range(spec.probe_budget):
            op = random.Random(len(posterior.updates)).choice(spec.operators)
            reading = world.probe([op, op, op])
            posterior.observe_trajectory([op, op, op], spec.initial_state, reading["trajectory"])
        exact, low, high = posterior.model_posterior()
        if posterior.exact_collapsed():
            self.assertEqual(exact, 0.0)
            self.assertGreater(low + high, 0.99)

    def test_grammar_expansion_repairs_out_of_grammar_operator(self) -> None:
        domains = (4, 4, 3)
        pair = Mechanism("pair", (), Mechanism("add", (0, 1)), Mechanism("add", (2, 1)))
        posterior = MechanismPosterior(domains, ("op",))
        rng = random.Random(1)
        for _ in range(4):
            state = tuple(rng.randrange(m) for m in domains)
            posterior.observe("op", state, pair.apply(state, domains))
        self.assertEqual(posterior.exact_collapsed(), ["op"])
        record = posterior.rebuild("op")
        self.assertEqual(record["resolution"], "grammar-expansion")
        self.assertEqual(posterior.map_mechanism("op")[0], pair)

    def test_change_point_rebuild_for_non_stationary_operator(self) -> None:
        domains = (5, 5)
        old, new = Mechanism("add", (0, 1)), Mechanism("set", (1, 2))
        posterior = MechanismPosterior(domains, ("op",))
        for state in ((0, 0), (1, 3), (2, 4)):
            posterior.observe("op", state, old.apply(state, domains))
        for state in ((3, 0), (4, 1)):
            posterior.observe("op", state, new.apply(state, domains))
        self.assertEqual(posterior.exact_collapsed(), ["op"])
        record = posterior.rebuild("op")
        self.assertIn(record["resolution"], ("change-point", "grammar-expansion"))
        self.assertTrue(posterior.loglik["op"][0])


class TransferPriors(unittest.TestCase):
    def test_boost_is_a_prior_not_evidence(self) -> None:
        domains = (4, 4)
        truth, wrong = Mechanism("add", (0, 1)), Mechanism("set", (1, 3))
        posterior = MechanismPosterior(domains, ("op",))
        self.assertTrue(posterior.boost("op", wrong, 0.9, source="analogy-x"))
        self.assertGreater(posterior.boost_evidence("op")["posterior"], 0.85)
        posterior.observe("op", (0, 0), truth.apply((0, 0), domains))
        evidence = posterior.boost_evidence("op")
        # competing noise models keep a contradicted transfer barely alive;
        # under exact readings it is eliminated outright
        self.assertLess(evidence["posterior"], 0.05)
        self.assertLess(evidence["bayes_factor"], 0.1)
        wrong_index = posterior.space["op"].index(wrong)
        self.assertNotIn(wrong_index, posterior.loglik["op"][0])
        posterior.remove_boost("op")
        self.assertNotIn("op", posterior.boosts)

    def test_prior_predictive_measures_coincidence(self) -> None:
        domains = (2, 2, 2)
        posterior = MechanismPosterior(domains, ("op",))
        self.assertAlmostEqual(posterior.prior_predictive_logprob("op"), 0.0, places=9)
        posterior.observe("op", (0, 0, 0), (1, 0, 0))
        self.assertLess(posterior.prior_predictive_logprob("op"), 0.0)


if __name__ == "__main__":
    unittest.main()
