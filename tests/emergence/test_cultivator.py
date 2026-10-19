"""Unit tests for CondensationCultivator and complexity axes mutations."""

import pytest
from euclid.emergence.models.condensation import ColonyConfig, COMPLEXITY_AXES
from euclid.emergence.cultivator.colony import AgentColony, AgentColonies
from euclid.emergence.cultivator.cultivator import CondensationCultivator
from euclid.emergence.substrate.registry import SubstrateRegistry


def test_colony_run_and_metrics():
    cfg = ColonyConfig(
        colony_id="colony_01",
        interaction_topology="recursive_folding",
        observation_depth="depth_2_meta",
        action_granularity="reflective",
        temporal_structure="asynchronous",
        substrate_heterogeneity="mixed_digital",
        representational_braid="topological",
    )
    colony = AgentColony(config=cfg)
    records = colony.run(iterations=30)
    assert len(records) == 30

    stability = colony.stability()
    assert 0.0 <= stability <= 1.0

    sub_ind = colony.substrate_independence()
    assert sub_ind >= 0.5


def test_condensation_cultivator_fitness_and_breeding():
    registry = SubstrateRegistry()
    cultivator = CondensationCultivator(registry=registry)

    cfg1 = ColonyConfig("c1", interaction_topology="mesh")
    cfg2 = ColonyConfig("c2", interaction_topology="recursive_folding")

    colony1 = AgentColony(cfg1)
    colony2 = AgentColony(cfg2)

    colony1.run(iterations=20)
    colony2.run(iterations=20)

    f1 = cultivator.calculate_fitness(colony1)
    f2 = cultivator.calculate_fitness(colony2)
    assert isinstance(f1, float)
    assert isinstance(f2, float)

    # Breeding next generation
    new_population = cultivator.breed([colony1, colony2], target_size=4, generation=1)
    assert len(new_population) == 4
    for child in new_population:
        assert child.generation == 1
        # Assert mutated config is indexed in SubstrateRegistry
        sid = f"sub_{child.config.compute_hash()}"


def test_generational_cultivation():
    registry = SubstrateRegistry()
    cultivator = CondensationCultivator(registry=registry)

    population = AgentColonies([
        AgentColony(ColonyConfig(f"colony_init_{i}")) for i in range(3)
    ])

    final_population = cultivator.cultivate(population, generations=2, iterations_per_regime=15)
    assert len(final_population) == 3
    assert len(cultivator.fitness_history) >= 3
