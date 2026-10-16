"""Agent Colony representations for Condensation Cultivation."""

from __future__ import annotations
import random
import time
from typing import List, Dict, Any, Optional, Sequence

from ..models.manifest import CapabilityManifest
from ..models.condensation import ColonyConfig
from ..models.telemetry import TelemetryRecord
from ..telemetry.agent_telemetry import AgentTelemetry
from ..telemetry.sink import TelemetryStream


class AgentColony:
    """An agent colony instantiated across specific complexity axes."""

    def __init__(
        self,
        config: ColonyConfig,
        manifest: Optional[CapabilityManifest] = None,
        telemetry: Optional[AgentTelemetry] = None,
        stream: Optional[TelemetryStream] = None,
    ):
        self.config = config
        self.colony_id = config.colony_id
        self.manifest = manifest or CapabilityManifest(
            declared_actions=frozenset(["navigate", "fetch_data", "parse_json"]),
            declared_compositions=frozenset([("navigate", "fetch_data")]),
            declared_strategies=frozenset(["standard_query"]),
        )
        self.telemetry = telemetry or AgentTelemetry()
        self.stream = stream or TelemetryStream(f"colony_stream_{self.colony_id}")
        self.telemetry_records: List[TelemetryRecord] = []
        self.generation: int = 0

    def run(self, iterations: int = 100, task_suite: Optional[Sequence[str]] = None) -> List[TelemetryRecord]:
        """Execute operational regime (e.g. Tier 20) and collect signed telemetry."""
        tasks = task_suite or ["task_alpha", "task_beta", "task_gamma"]
        records = []

        # Complex decision generator modulated by complexity axes
        rng = random.Random(hash(self.config.canonical_json()) & 0xFFFFFFFF)

        for i in range(iterations):
            task = tasks[i % len(tasks)]
            decisions = ["navigate", "fetch_data"]

            # Higher depth or recursive topology stimulates emergence of novel reflective actions
            if "recursive" in self.config.interaction_topology or "meta" in self.config.observation_depth:
                if rng.random() > 0.40:
                    decisions.append(f"novel_fold_{self.config.action_granularity}")
            if "topological" in self.config.representational_braid:
                if rng.random() > 0.50:
                    decisions.append("emergent_topological_braid")

            actions = list(decisions)
            obs = [f"colony_obs_{task}_{i}"]

            rec, sig = self.telemetry.on_iteration(
                agent_id=f"agent_{self.colony_id}",
                task_signature=task,
                actions=actions,
                observations=obs,
                decisions=decisions,
                run_id=f"run_{self.colony_id}_g{self.generation}_{i}",
                substrate_id=f"sub_{self.config.compute_hash()}",
                iteration_index=i,
                manifest=self.manifest,
                telemetry_stream=self.stream,
            )
            records.append(rec)
            self.telemetry_records.append(rec)

        return records

    def stability(self) -> float:
        """Measure repeatability of emergent behaviors across iterations (anti-fluke)."""
        if not self.telemetry_records:
            return 0.0
        novel_counts: Dict[str, int] = {}
        for rec in self.telemetry_records:
            for b in rec.novel_elements.unattributed:
                novel_counts[b] = novel_counts.get(b, 0) + 1
        if not novel_counts:
            return 0.1
        repeatable = sum(1 for cnt in novel_counts.values() if cnt >= 2)
        return round(repeatable / len(novel_counts), 4)

    def substrate_independence(self) -> float:
        """Measure capacity of behaviors to persist across temporal and architectural changes."""
        # Baseline score derived from heterogeneity and temporal complexity
        score = 0.5
        if self.config.substrate_heterogeneity != "uniform":
            score += 0.25
        if self.config.temporal_structure != "synchronous":
            score += 0.25
        return round(score, 4)


class AgentColonies:
    """Population of agent colonies."""

    def __init__(self, colonies: Optional[List[AgentColony]] = None):
        self.colonies: List[AgentColony] = colonies or []

    def __iter__(self):
        return iter(self.colonies)

    def __len__(self):
        return len(self.colonies)

    def add(self, colony: AgentColony) -> None:
        self.colonies.append(colony)
