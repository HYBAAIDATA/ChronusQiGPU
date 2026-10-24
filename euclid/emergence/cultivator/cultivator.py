"""CondensationCultivator module optimizing the conditions for emergence condensation."""

from __future__ import annotations
import random
from typing import Dict, List, Optional

from ..models.condensation import COMPLEXITY_AXES, ColonyConfig
from ..analyzer.emergence_analyzer import EmergenceAnalyzer
from ..substrate.harness import TIER_20
from ..substrate.registry import SubstrateRegistry
from .colony import AgentColony, AgentColonies


class CondensationCultivator:
    """Cultivates the conditions under which unprogrammed capability condenses.
    
    Anti-Goodhart Selection Pressure: Fitness is NOT task score, but:
    fitness = novelty_entropy * stability * substrate_independence
    """

    def __init__(self, registry: Optional[SubstrateRegistry] = None):
        self.registry = registry or SubstrateRegistry()
        self.fitness_history: Dict[str, float] = {}

    def calculate_fitness(self, colony: AgentColony) -> float:
        analyzer = EmergenceAnalyzer(colony.telemetry_records)
        entropy = analyzer.novelty_entropy
        stability = colony.stability()
        sub_ind = colony.substrate_independence()

        # Fitness is DIVERSITY of unattributed behaviors * stability * substrate_independence
        fitness = entropy * stability * sub_ind
        return round(float(fitness), 6)

    def mutate_config(self, parent_config: ColonyConfig, generation: int, idx: int) -> ColonyConfig:
        """Mutate configuration along one or more complexity axes and register in SubstrateRegistry."""
        axes = list(COMPLEXITY_AXES.keys())
        axis_to_mutate = random.choice(axes)
        new_val = random.choice(COMPLEXITY_AXES[axis_to_mutate])

        config_dict = {
            "colony_id": f"colony_gen{generation}_{idx}",
            "interaction_topology": parent_config.interaction_topology,
            "observation_depth": parent_config.observation_depth,
            "action_granularity": parent_config.action_granularity,
            "temporal_structure": parent_config.temporal_structure,
            "substrate_heterogeneity": parent_config.substrate_heterogeneity,
            "representational_braid": parent_config.representational_braid,
        }
        config_dict[axis_to_mutate] = new_val
        new_config = ColonyConfig(**config_dict)

        # Register mutated axis configuration in SubstrateRegistry to ensure substrate indexing
        self.registry.register(
            executor_type=f"cultivator_{new_config.action_granularity}",
            observation_latency=10.0,
            action_granularity=new_config.action_granularity,
            compute_substrate=f"heterogeneous_{new_config.substrate_heterogeneity}",
            complexity_axis_tags=(
                f"topology:{new_config.interaction_topology}",
                f"depth:{new_config.observation_depth}",
                f"temporal:{new_config.temporal_structure}",
                f"braid:{new_config.representational_braid}",
            ),
        )

        return new_config

    def breed(self, top_colonies: List[AgentColony], target_size: int, generation: int) -> List[AgentColony]:
        """Breed the next generation by mutating top performers along complexity axes."""
        new_population: List[AgentColony] = []
        if not top_colonies:
            return new_population

        for i in range(target_size):
            parent = top_colonies[i % len(top_colonies)]
            mutated_cfg = self.mutate_config(parent.config, generation, i)
            child = AgentColony(config=mutated_cfg, manifest=parent.manifest)
            child.generation = generation
            new_population.append(child)

        return new_population

    def cultivate(
        self,
        population: AgentColonies,
        generations: int,
        iterations_per_regime: int = TIER_20,
        top_k_ratio: float = 0.5,
    ) -> AgentColonies:
        """Execute generational cultivation loop."""
        current_colonies = list(population.colonies)

        for gen in range(1, generations + 1):
            fitness_scores: List[tuple[AgentColony, float]] = []

            for colony in current_colonies:
                colony.run(iterations=iterations_per_regime)
                score = self.calculate_fitness(colony)
                self.fitness_history[colony.colony_id] = score
                fitness_scores.append((colony, score))

            # Sort descending by fitness
            fitness_scores.sort(key=lambda x: x[1], reverse=True)
            k = max(1, int(len(fitness_scores) * top_k_ratio))
            top_k = [c for c, _ in fitness_scores[:k]]

            # Breed next generation
            current_colonies = self.breed(top_k, target_size=len(population), generation=gen)

        return AgentColonies(current_colonies)
