"""The Active Discovery Engine finds what is really there, and only that.

Before the engine predicted untested compositions from its own theory, a
planted synergy went unfound while 27 additive chains (a, a∘a, a∘a∘a, ...)
were reported as discoveries: surprise was measured against a blank prior.
"""

from __future__ import annotations

import random

from Intelligence.asi.compositional_generalization import CompositionalRule
from Intelligence.asi.discovery_engine import ActiveDiscoveryEngine

EFFECTS = {"a": 0.1, "b": 0.0, "c": -0.1}


def _primitives():
    return [CompositionalRule(name=n, input_pattern=n, output_pattern=n) for n in EFFECTS]


def _environment(*, synergy=0.5, noise=0.005, seed=1):
    rng = random.Random(seed)

    def env(rules, _state):
        effect = sum(EFFECTS[r] for r in rules)
        effect += synergy * sum(1 for x, y in zip(rules, rules[1:]) if (x, y) == ("a", "b"))
        return effect + rng.gauss(0.0, noise)

    return env


def test_the_planted_synergy_is_found_and_nothing_else():
    engine = ActiveDiscoveryEngine(_environment(), _primitives(), n_trials=5)
    report = engine.discover(initial_state=None, n_cycles=40, max_composition_length=2)
    ledger = engine.get_discovery_ledger()
    assert [d["composition"] for d in ledger] == ["a ∘ b"]
    only = ledger[0]
    assert abs(only["predicted"] - 0.1) < 0.02  # additive: a + b
    assert abs(only["observed"] - 0.6) < 0.02
    assert report["discoveries"] == 1 and report["broadcasts"] == 1


def test_additive_compositions_are_confirmations_not_discoveries():
    engine = ActiveDiscoveryEngine(_environment(synergy=0.0), _primitives(), n_trials=5)
    engine.discover(initial_state=None, n_cycles=40, max_composition_length=2)
    assert engine.discoveries == []
    # Every pair was tested, and each was predicted from the singletons.
    assert len(engine.hypotheses_tested) == 3 + 9


def test_untested_compositions_are_predicted_from_the_theory():
    engine = ActiveDiscoveryEngine(_environment(synergy=0.0), _primitives(), n_trials=5)
    engine.discover(initial_state=None, n_cycles=3, max_composition_length=1)
    predictions = {h.hypothesis_id: h.predicted_effect for h in engine.generate_hypotheses(2)}
    assert abs(predictions["a∘c"] - 0.0) < 0.02
    assert abs(predictions["a∘a"] - 0.2) < 0.02


def test_an_effect_that_does_not_replicate_is_never_a_discovery():
    # A real +0.5 synergy buried in noise far above the replication tolerance.
    engine = ActiveDiscoveryEngine(
        _environment(noise=0.5), _primitives(), n_trials=5, replication_tolerance=0.05
    )
    engine.discover(initial_state=None, n_cycles=40, max_composition_length=2)
    assert engine.discoveries == []


def test_irreversible_experiments_are_refused_before_they_run():
    calls = []

    def env(rules, _state):
        calls.append(rules)
        return 0.0

    engine = ActiveDiscoveryEngine(env, _primitives(), experiments_reversible=False)
    engine.discover(initial_state=None, n_cycles=5)
    assert calls == [] and engine.experiment_log == []


def test_a_composition_is_tested_only_after_its_parts():
    # At a fine surprise threshold every unmeasured part would read as a
    # surprise of the whole: a discovered "a" once pulled a∘c ahead of c.
    engine = ActiveDiscoveryEngine(
        _environment(noise=0.0), _primitives(), n_trials=5, surprise_threshold=0.01
    )
    engine.discover(initial_state=None, n_cycles=40, max_composition_length=2)
    seen: set[tuple[str, ...]] = set()
    for hypothesis in engine.hypotheses_tested:
        atoms = engine._expand(hypothesis.rule_composition)
        if len(atoms) > 1:
            assert all((atom,) in seen for atom in atoms), hypothesis.hypothesis_id
        if len(atoms) > 2:
            pairs = [tuple(atoms[i : i + 2]) for i in range(len(atoms) - 1)]
            assert all(pair in seen for pair in pairs), hypothesis.hypothesis_id
        seen.add(tuple(atoms))
    found = sorted(d["composition"] for d in engine.get_discovery_ledger())
    assert found == ["a", "a ∘ b", "c"]  # the two levers that act, and the synergy
